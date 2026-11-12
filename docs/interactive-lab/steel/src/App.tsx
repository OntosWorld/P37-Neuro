import { useCallback, useEffect, useRef, useState } from 'react';
import { Physics, Scene, type SceneHandle, type SimStatsSample } from '@skild-ai/steel-webgpu/react';
import { Workcell, PRESETS, initialItems, nextItemId } from './Workcell';
import type { GripStateSample, ItemMotionSample, LooseItem, ObjectType, Preset, RobotType } from './Workcell';
import type { SourceFrame } from './SourceTrajectory';

type RealRobot = { id: string; name: string; kind: string; short: string; task: string; model: string };
type RobotCatalog = { robots: RealRobot[] };
const MODEL_IDS = new Set([
  'unitree_g1', 'unitree_h1', 'booster_t1', 'unitree_go2',
  'boston_dynamics_spot', 'anymal_c', 'franka_panda',
  'universal_robots_ur5e', 'hello_robot_stretch', 'crazyflie_2',
]);
type SourceData = { publication: { source: string; learned_policy_attached: boolean }; traces: { frames: SourceFrame[] }[] };


const CAMERA_DESKTOP = {
  position: [2.05, -2.65, 1.82] as [number,number,number],
  target: [0, 0, .88] as [number,number,number],
  fov: 40,
};
const CAMERA_MOBILE = {
  position: [2.75, -3.35, 2.20] as [number,number,number],
  target: [0, 0, .88] as [number,number,number],
  fov: 46,
};
function LiveScene({ preset, robot, items, paused, collision, pose, gripper, baseline,
  sceneRef, onSample, onMotion, onGripSample, onReady, onError, sourceFrames, sourcePlaying }: {
  preset: Preset; robot: RobotType; items: LooseItem[]; paused: boolean; collision: boolean;
  pose: number; gripper: number; baseline: boolean; sceneRef: React.RefObject<SceneHandle | null>;
  onMotion: (sample: ItemMotionSample) => void;
  onGripSample: (sample: GripStateSample) => void;
  onSample: (s: SimStatsSample | null) => void; onReady: () => void; onError: (s: string) => void;
  sourceFrames: SourceFrame[]; sourcePlaying: boolean;
}) {
  const [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 690px)').matches);
  useEffect(() => {
    const query = window.matchMedia('(max-width: 690px)');
    const onChange = () => setMobile(query.matches);
    query.addEventListener('change', onChange);
    return () => query.removeEventListener('change', onChange);
  }, []);
  return <Physics
    style={{ position: 'absolute', inset: 0 }}
    fallback={<div className="viewer-notice"><div className="spinner"/>Requesting Steel WebGPU device...</div>}
    unsupported={reason => <div className="viewer-notice">
      <strong>WebGPU unavailable</strong><p>{reason}</p>
      <p>Try a recent Chrome, Edge or Safari with WebGPU enabled.</p>
    </div>}
    onError={e => onError(String(e))}
  >
    <Scene ref={sceneRef} gravity={[0,0,-9.81]} fps={60} paused={paused} collision={collision}
      pickable controls camera={mobile ? CAMERA_MOBILE : CAMERA_DESKTOP} onLoaded={onReady} onError={e=>onError(String(e))}>
      <Workcell preset={preset} robot={robot} items={items} pose={pose} gripper={gripper} baseline={baseline} onStats={onSample} onMotion={onMotion} onGripSample={onGripSample} sourceFrames={sourceFrames} sourcePlaying={sourcePlaying}/>
    </Scene>
  </Physics>;
}
export function App() {
  const [preset, setPreset] = useState<Preset>('workcell');
  const [robot, setRobot] = useState<RobotType>('compact');
  const [activeModel, setActiveModel] = useState('compact');
  const [robotCatalog, setRobotCatalog] = useState<RealRobot[]>([]);
  const [catalogError, setCatalogError] = useState('');
  const isMuJoCo = MODEL_IDS.has(activeModel);
  const activeRealRobot = robotCatalog.find(item => item.id === activeModel);
  const selectModel = (id: string) => {
    if (!MODEL_IDS.has(id) && id !== 'compact' && id !== 'extended') return;
    setActiveModel(id);
    if (id === 'compact' || id === 'extended') setRobot(id);
    setGripState(null);
    setItemMotion({});
    setStatus(MODEL_IDS.has(id)
      ? 'Loading official MuJoCo Menagerie model'
      : 'Loading Steel articulated reference robot');
  };
  const [items, setItems] = useState<LooseItem[]>(() => initialItems('workcell'));
  const [selectedObject, setSelectedObject] = useState<ObjectType>('parcel');
  const [pose, setPose] = useState(.18);
  const [gripper, setGripper] = useState(.035);
  const [reachCycle, setReachCycle] = useState(true);
  const [gripState, setGripState] = useState<GripStateSample | null>(null);
  const [trackedId, setTrackedId] = useState<number | null>(null);
  const [itemMotion, setItemMotion] = useState<Record<number, ItemMotionSample>>({});
  const [paused, setPaused] = useState(false);
  const [collision, setCollision] = useState(false);
  const [status, setStatus] = useState('Requesting WebGPU');
  const [stats, setStats] = useState<SimStatsSample | null>(null);
  const [sourceData, setSourceData] = useState<SourceData | null>(null);
  const [showSource, setShowSource] = useState(false);
  const [sourceEpisode, setSourceEpisode] = useState(0);
  const [sourcePlaying, setSourcePlaying] = useState(true);
  const scene = useRef<SceneHandle>(null);
  const onMotion = useCallback((sample: ItemMotionSample) => {
    setItemMotion(previous => {
      const last = previous[sample.id];
      if (last &&
          Math.hypot(
            sample.position[0] - last.position[0],
            sample.position[1] - last.position[1],
            sample.position[2] - last.position[2],
          ) < .004 &&
          sample.at - last.at < 1.5) return previous;
      return { ...previous, [sample.id]: sample };
    });
  }, []);
  const tracked = items.find(item => item.id === trackedId) ?? items[0];
  const livePosition = tracked ? itemMotion[tracked.id]?.position : undefined;
  const gripBaseMm = robot === 'panda' ? 0 : 44;
  const measuredGripMm = gripState ? gripBaseMm+1000*(gripState.left+gripState.right) : undefined;
  const travel = tracked && livePosition ?
    Math.hypot(
      livePosition[0] - tracked.position[0],
      livePosition[1] - tracked.position[1],
      livePosition[2] - tracked.position[2],
    ) : undefined;
  useEffect(() => {
    const controller = new AbortController();
    fetch(import.meta.env.BASE_URL + 'catalog.json', { signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error('Robot catalog missing from website bundle');
        const data = await response.json() as RobotCatalog;
        if (!Array.isArray(data.robots) ||
            data.robots.length !== MODEL_IDS.size ||
            data.robots.some(item => !MODEL_IDS.has(item.id)))
          throw new Error('Real robot catalog does not match the physics bundle');
        setRobotCatalog(data.robots);
      }).catch(error => {
        if (!controller.signal.aborted) setCatalogError(String(error));
      });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    if (!showSource || sourceData) return;
    const abort = new AbortController();
    const sourceUrl = import.meta.env.BASE_URL + 'samples/mimicgen-square-source.json';
    fetch(sourceUrl, { signal: abort.signal }).then(async response => {
      if (!response.ok) throw new Error('Source example is not published in this build');
      const value = await response.json() as SourceData;
      if (value.publication?.source !== 'amandlek/mimicgen_datasets' ||
          value.publication.learned_policy_attached !== false ||
          value.traces.length < 2 ||
          value.traces.some(item => item.frames.length < 2 ||
            item.frames.some(f => ![0, 1, 2].every(i => Number.isFinite(f.state['eef_position_' + i]))))) {
        throw new Error('Source replay metadata or coordinates invalid');
      }
      setSourceData(value);
      setStatus('Genuine MimicGen Panda source trajectory loaded');
    }).catch(error => {
      if (!abort.signal.aborted) {
        setStatus('Source data unavailable: ' + String(error));
        setShowSource(false);
      }
    });
    return () => abort.abort();
  }, [showSource, sourceData]);
  const changePreset = (next: Preset) => {
    // Workcell presets belong to the motor-driven Steel reference arm.
    // Selecting one from a native MuJoCo model loads the associated task
    // rather than leaving an inert scene button.
    if (isMuJoCo) selectModel('compact');
    setPreset(next); setItems(initialItems(next)); setItemMotion({}); setTrackedId(null); setGripState(null);
    setStatus('Loading physics environment');
  };
  const reset = () => {
    setItems(initialItems(preset));
    setItemMotion({}); setTrackedId(null); setGripState(null);
    scene.current?.reset();
    setStatus('Resetting scene');
  };
  const addItem = () => {
    if (items.length >= 12) { setStatus('Maximum of 12 loose objects'); return; }
    const row = items.length % 3, col = Math.floor(items.length / 3) % 3;
    const position: [number,number,number] = [.10 + row * .23, -.25 + col * .24, 1.3 + Math.floor(items.length / 3) * .16];
    const item: LooseItem = { id: nextItemId(), type: selectedObject, position };
    setItems([...items, item]); setTrackedId(item.id);
    setStatus('New ' + selectedObject + ' added to the physics scene');
  };
  const dropTest = () => {
    const item: LooseItem = {
      id: nextItemId(),
      type: 'parcel',
      position: [.46, -.19, 1.43],
    };
    // Isolate the contact experiment. The former test put another parcel
    // into an already active packing cell with overlapping loose objects;
    // those collisions could launch the parcel off the workbench.
    // Keep the existing Scene mounted. Switching presets here remounted the
    // WebGPU Scene while the QA readback was in flight; zero-valued default
    // poses were then mistaken for a parcel falling through the tabletop.
    // Rebuild only the loose-object set, retaining the current fixed workbench.
    setItems([item]);
    setItemMotion({});
    setTrackedId(item.id);
    setGripState(null);
    setReachCycle(true);
    setPaused(false);
    setStatus('Isolated tabletop drop: waiting for physics readback');
  };
  return <div className="app-shell">
    <header className="site-header">
      <a className="brand" href="./">ONTOS <span>/ P37 NEURO</span></a>
      <nav aria-label="Research navigation">
        <a href="#simulation">Live simulation</a>
        <a href="#research">Research evidence</a>
        <a href="https://github.com/OntosRobotics/P37-Neuro" target="_blank" rel="noreferrer">Source ↗</a>
      </nav>
      <span className="build-tag">EXPERIMENT / 01</span>
    </header>
    <main>
      <div className="title-row">
        <div>
          <span className="overline">P37 / LIVE PHYSICS DEMONSTRATION</span>
          <h1>Robots, interacting with the world.</h1>
          <p className="intro">Explore real robot models and physical interactions in your browser. The reference arm performs a motor-driven reach sequence; manufacturer-derived robots can be inspected in native MuJoCo physics. Qualified P37 learned-policy inference is not yet attached.</p>
        </div>
        <div className="hero-note"><strong>About this demonstration</strong>
          <p>Live Steel physics and a deterministic joint controller. No trained P37-Neuro checkpoint is attached. MimicGen demonstrations are imported separately and never presented as this robot’s learned behavior.</p>
        </div>
      </div>
      <section className="lab-grid" id="simulation" aria-label="Interactive Steel research workcell">
        <div className="viewport">
          <div className="playground-scenes" role="group" aria-label="Choose physics environment">
            <span className="playground-scenes-label">Scenes</span>
            {PRESETS.map(p=><button type="button" key={p.id}
              aria-pressed={preset===p.id} className={preset===p.id?'active':''}
              onClick={()=>changePreset(p.id)}>{p.label}</button>)}
          </div>
          <div className="viewport-top">
            <div><span className="live-dot"/> LIVE PHYSICS <span className="muted">/ {isMuJoCo ? 'MuJoCo · WebAssembly' : 'Steel · WebGPU'}</span></div>
            <div className="stage-tools-head">
              <span>{isMuJoCo ? 'REAL MANUFACTURER MODEL · NO TRAINED POLICY' : 'REFERENCE TASK · REAL JOINT CONTROL'}</span>
              <button type="button" className="stage-expand" title="Expand simulation"
                aria-label="Expand simulation" onClick={event=>{
                  const viewport=event.currentTarget.closest('.viewport');
                  if(document.fullscreenElement)void document.exitFullscreen();
                  else if(viewport)void viewport.requestFullscreen();
                }}>⛶</button>
            </div>
          </div>
          <div className="canvas-wrap">
            {isMuJoCo ?
              <iframe
                className="menagerie-viewer"
                key={activeModel}
                title={activeRealRobot ? activeRealRobot.name + ' — MuJoCo physical robot model' : 'MuJoCo real robot'}
                src={import.meta.env.BASE_URL + 'simulator/?project=p37_robot_models&scene=' + encodeURIComponent(activeModel) + '&panel=0'}
                allow="fullscreen"
                loading="eager"
              /> :
              <LiveScene key={preset + '-' + robot} preset={preset} robot={robot} items={items}
                paused={paused} collision={collision} pose={pose} gripper={gripper} baseline={reachCycle} sceneRef={scene}
                onMotion={onMotion} onGripSample={setGripState}
                onSample={setStats} onReady={()=>setStatus('Steel physics active')}
                onError={setStatus} sourceFrames={showSource ? (sourceData?.traces[sourceEpisode]?.frames ?? []) : []}
                sourcePlaying={showSource && sourcePlaying && !paused}/>
            }
            <div className="camera-tip">{isMuJoCo ? 'M U J O C O · MODEL-ONLY PHYSICS · DRAG TO ORBIT / APPLY FORCE' :
              'DRAG OBJECTS TO PULL · DRAG EMPTY SPACE TO ORBIT'}</div>
          </div>
          <div className="playground-embodiment" role="group" aria-label="Choose reference robot">
            <span>Robot model</span>
            <button type="button" aria-pressed={activeModel==='compact'} onClick={()=>selectModel('compact')}>Reference arm</button>
            <button type="button" aria-pressed={activeModel==='extended'} onClick={()=>selectModel('extended')}>Extended arm</button>
            <span className="playground-disclaimer">{isMuJoCo ? 'Manufacturer-derived MuJoCo geometry · passive physics' :
              'Articulated deterministic reference controller'} · no qualified P37 browser policy</span>
          </div>
          <div className="viewport-controls">
            <div className="action-row">
              {isMuJoCo && <span className="model-mode-label">Model-only physics. Use the embedded MuJoCo controls.</span>}
              <fieldset disabled={isMuJoCo} className="stage-robot-actions">
              <button onClick={()=>setReachCycle(active=>!active)} aria-pressed={reachCycle}>
                {reachCycle ? 'Pause robot task' : 'Run robot task'}
              </button>
              <button onClick={()=>setPaused(!paused)}>{paused ? '▶ Resume' : 'Ⅱ Pause'}</button>
              <button onClick={reset}>↻ Reset</button>
              <button aria-pressed={collision} onClick={()=>setCollision(!collision)}>
                {collision ? 'Hide collision geometry' : 'Show collision geometry'}
              </button>
              </fieldset>
            </div>
            <div className="status-line" role="status">{isMuJoCo ? 'Passive model physics · no trained P37 controller' : status}</div>
          </div>
        </div>
        <div className="playground-panel">
        <aside className="side-panel">
          <div className="section-heading"><span>CONFIGURATION</span><span>01 / 04</span></div>
          <label htmlFor="preset">Environment</label>
          <select id="preset" value={preset} onChange={e=>changePreset(e.target.value as Preset)}>
            {PRESETS.map(p=><option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
          <p className="helper">{PRESETS.find(p=>p.id===preset)?.detail}</p>
          <div className="rule"/>
          <label htmlFor="robot">Robot embodiment</label>
          <select id="robot" value={activeModel} onChange={e=>selectModel(e.target.value)}>
            <optgroup label="Motor-driven reference arms">
              <option value="compact">Reference arm / compact</option>
              <option value="extended">Reference arm / extended</option>
            </optgroup>
            <optgroup label="Real manufacturer-derived robots">
              {robotCatalog.map(item => <option key={item.id} value={item.id}>{item.name} / {item.kind}</option>)}
            </optgroup>
          </select>
          <p className="helper">{catalogError || (isMuJoCo
            ? activeRealRobot?.name + ' — ' + activeRealRobot?.short + '. Real MuJoCo model, physical joints and contacts. Passive model exploration: no P37 learned controller.'
            : 'Motor-driven reference arm, deterministic reach cycle and measured gripper movement. No trained checkpoint attached.')}
          </p>
          <div className="robot-catalog" role="group" aria-label="Select real robot body">
            <div className="catalog-heading">REAL ROBOT LIBRARY <span>{robotCatalog.length} MODELS</span></div>
            <div className="catalog-choices">
              {robotCatalog.map(item =>
                <button type="button" className={activeModel===item.id?'selected':''}
                  key={item.id} aria-pressed={activeModel===item.id}
                  onClick={()=>selectModel(item.id)}>
                  <strong>{item.name}</strong><small>{item.short}</small>
                </button>)}
            </div>
          </div>
          <fieldset className="reference-controls" disabled={isMuJoCo} aria-label="Reference arm motor controls">
          <legend>{isMuJoCo ? 'Reference-arm controls unavailable for this model' : 'Reference arm motor controls'}</legend>
          <label htmlFor="jaw-aperture">Gripper target <output>{(gripBaseMm + gripper * 2000).toFixed(0)} mm</output></label>
          <input id="jaw-aperture" type="range" min="0" max=".035" step=".001"
            value={gripper} onChange={e=>{setReachCycle(false);setGripper(Number(e.target.value));}}/>
          <div className="jaw-actions">
            <button type="button" onClick={()=>{setReachCycle(false);setGripper(0);}}>Close fingers</button>
            <button type="button" onClick={()=>{setReachCycle(false);setGripper(.035);}}>Open fingers</button>
          </div>
          <label htmlFor="pose">Shoulder target <output>{robot==='panda' ? 'fixed baseline' : pose.toFixed(2)+' rad'}</output></label>
          <input id="pose" type="range" min="-1.2" max="1.2" step=".01" value={pose} disabled={robot==='panda'} onChange={e=>setPose(Number(e.target.value))}/>
          <div className="rule"/>
          <label htmlFor="item">Add real-world object</label>
          <select id="item" value={selectedObject} onChange={e=>setSelectedObject(e.target.value as ObjectType)}>
            <option value="parcel">Cardboard parcel</option>
            <option value="canister">Metal canister</option>
            <option value="ball">Rubber ball</option>
            <option value="bin">Storage bin</option>
          </select>
          <button className="primary" onClick={addItem}>+ Drop object into scene</button>
          <button className="contact-demo" onClick={dropTest}>Run gravity & contact test</button>
          <label htmlFor="tracked-body">Inspect physical object</label>
          <select id="tracked-body" value={tracked?.id ?? ''} onChange={e=>setTrackedId(Number(e.target.value))}>
            {items.map(item=><option key={item.id} value={item.id}>{item.type} #{item.id}</option>)}
          </select>
          <p className="helper">Objects have mass and contact geometry. Run the isolated drop test to measure worktop contact without other loose objects interfering.</p>
          </fieldset>
          <div className="rule"/>
          <label>Source-data replay</label>
          <button className="primary" disabled={isMuJoCo} onClick={() => setShowSource(!showSource)}>
            {showSource ? 'Hide recorded path' : 'Show real MimicGen motion'}
          </button>
          {showSource && sourceData && <>
            <label htmlFor="source-episode">Recorded episode</label>
            <select id="source-episode" value={sourceEpisode} onChange={e=>setSourceEpisode(Number(e.target.value))}>
              <option value={0}>Panda / Source episode 0</option>
              <option value={1}>Panda / Source episode 1</option>
            </select>
            <button onClick={() => setSourcePlaying(!sourcePlaying)}>
              {sourcePlaying ? 'Pause recorded motion' : 'Play recorded motion'}
            </button>
          </>}
          <p className="helper">{isMuJoCo
            ? 'MimicGen trajectory replay is available with the reference workcell, not inside the native MuJoCo model viewer.'
            : 'The green line and marker follow original source end-effector coordinates independently of the reference arm. This is recorded-data playback, not learned policy inference.'}</p>
          <div className="rule"/>
          <a className="small-link" href="https://huggingface.co/datasets/amandlek/mimicgen_datasets" target="_blank" rel="noreferrer">MimicGen source dataset ↗</a>
          <a className="small-link" href="#research">Read the evidence boundary ↓</a>
        </aside>
        <aside className="evidence-panel">
          <div className="section-heading"><span>EXPERIMENT STATUS</span><span>02 / 04</span></div>
          <div className="info-row"><span>Physics backend</span><strong>{isMuJoCo ? 'MuJoCo / WebAssembly' : 'Steel / WebGPU'}</strong></div>
          <div className="info-row"><span>Simulation time</span><strong>{!isMuJoCo && stats ? stats.time.toFixed(1) + ' s' : '—'}</strong></div>
          <div className="info-row"><span>Solver contacts</span><strong>{isMuJoCo ? 'See MuJoCo controls' : (stats?.contacts ?? '—')}</strong></div>
          <div className="info-row"><span>Tracked object</span><strong>{tracked ? tracked.type + ' #' + tracked.id : '—'}</strong></div>
          <div className="info-row"><span>Object height</span><strong>{livePosition ? livePosition[2].toFixed(3) + ' m' : '—'}</strong></div>
          <div className="info-row"><span>Object travel</span><strong>{travel !== undefined ? (1000 * travel).toFixed(0) + ' mm' : '—'}</strong></div>
          <div className="info-row"><span>Jaw target</span><strong>{(gripBaseMm+gripper*2000).toFixed(0)} mm</strong></div>
          <div className="info-row"><span>Measured jaw clearance</span>
            <strong>{measuredGripMm !== undefined ? measuredGripMm.toFixed(0)+' mm' : '—'}</strong>
          </div>
          <div className="info-row"><span>Movable objects</span><strong>{items.length}</strong></div>
          <div className="info-row"><span>Robot geometry</span><strong>{isMuJoCo ? (activeRealRobot?.name || activeModel) + ' / Menagerie' : robot + ' / P37 reference'}</strong></div>
          <div className="info-row"><span>Recorded dataset</span><strong>{showSource ? "MimicGen Panda source" : "None"}</strong></div>
          <div className="rule"/>
          <div className="section-cap">What is running</div>
          <p className="evidence-copy">{isMuJoCo
            ? 'These 10 manufacturer-derived bodies run MuJoCo physics in a built-in viewer. Drag the robot to apply forces and inspect passive contacts. No learned walking, recovery, or manipulation success is claimed.'
            : 'Steel simulates articulated reference arms, actuated fingers and finite-mass objects. Solver positions and contacts are measured; reference actions use a deterministic controller.'}</p>
          <div className="flag">Policy checkpoint: <b>None</b><br/>MimicGen model training: <b>Not executed</b><br/>Recorded source playback: <b>{showSource ? "Active" : "Off"}</b><br/>Learned cross-body transfer: <b>Unverified</b></div>
          <div className="section-cap">P37 integration</div>
          <p className="evidence-copy">The recorded MimicGen source motion can be enabled above for side-by-side inspection. The visible reference arm uses an explicit deterministic controller; a trained P37 checkpoint is not driving these actions.</p>
        </aside>
        </div>
      </section>
      <section className="bottom-grid" id="research">
        <div><span className="overline">01 / Physics</span><h2>Interact with the scene.</h2><p>Ten manufacturer-derived MuJoCo bodies and two motor-driven reference arms. Test contact, inspect actual robot geometry and use the workcell's physical gripper controls.</p></div>
        <div><span className="overline">02 / Training data</span><h2>Work with published demonstrations.</h2><p>MimicGen supplies HDF5 manipulation data from Panda, Sawyer, IIWA and UR5e. The P37 adapter imports recorded observations and controller-native actions for inspection.</p></div>
        <div><span className="overline">03 / Qualification</span><h2>Measure before claiming.</h2><p>Actual P37 checkpoints and held-out task evaluation are required for learned transfer claims. An interactive physics workcell is a separate engineering milestone.</p></div>
      </section>
    </main>
    <footer><span>© 2026 ONTOS / P37 NEURO</span><span>
      <a href="https://github.com/OntosRobotics/P37-Neuro">Source ↗</a> ·
      <a href="https://github.com/skild-ai/steel-webgpu">Steel ↗</a> ·
      <a href="https://mimicgen.github.io/">MimicGen ↗</a>
    </span></footer>
  </div>;
}
