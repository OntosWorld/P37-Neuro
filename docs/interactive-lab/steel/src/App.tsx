import { useEffect, useRef, useState } from 'react';
import { Physics, Scene, type SceneHandle, type SimStatsSample } from '@skild-ai/steel-webgpu/react';
import { Workcell, PRESETS, initialItems, nextItemId } from './Workcell';
import type { LooseItem, ObjectType, Preset, RobotType } from './Workcell';
import type { SourceFrame } from './SourceTrajectory';

type SourceData = { publication: { source: string; learned_policy_attached: boolean }; traces: { frames: SourceFrame[] }[] };


const CAMERA = {
  position: [2.65, -3.2, 2.2] as [number,number,number],
  target: [0, 0, .89] as [number,number,number],
  fov: 40,
};
function LiveScene({ preset, robot, items, paused, collision, pose,
  sceneRef, onSample, onReady, onError, sourceFrames, sourcePlaying }: {
  preset: Preset; robot: RobotType; items: LooseItem[]; paused: boolean; collision: boolean;
  pose: number; sceneRef: React.RefObject<SceneHandle | null>;
  onSample: (s: SimStatsSample | null) => void; onReady: () => void; onError: (s: string) => void;
  sourceFrames: SourceFrame[]; sourcePlaying: boolean;
}) {
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
      pickable controls camera={CAMERA} onLoaded={onReady} onError={e=>onError(String(e))}>
      <Workcell preset={preset} robot={robot} items={items} pose={pose} onStats={onSample} sourceFrames={sourceFrames} sourcePlaying={sourcePlaying}/>
    </Scene>
  </Physics>;
}
export function App() {
  const [preset, setPreset] = useState<Preset>('workcell');
  const [robot, setRobot] = useState<RobotType>('compact');
  const [items, setItems] = useState<LooseItem[]>(() => initialItems('workcell'));
  const [selectedObject, setSelectedObject] = useState<ObjectType>('parcel');
  const [pose, setPose] = useState(.18);
  const [paused, setPaused] = useState(false);
  const [collision, setCollision] = useState(false);
  const [status, setStatus] = useState('Requesting WebGPU');
  const [stats, setStats] = useState<SimStatsSample | null>(null);
  const [sourceData, setSourceData] = useState<SourceData | null>(null);
  const [showSource, setShowSource] = useState(false);
  const [sourceEpisode, setSourceEpisode] = useState(0);
  const [sourcePlaying, setSourcePlaying] = useState(true);
  const scene = useRef<SceneHandle>(null);
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
    setPreset(next); setItems(initialItems(next)); setStatus('Loading physics environment');
  };
  const reset = () => {
    setItems(initialItems(preset));
    scene.current?.reset();
    setStatus('Resetting scene');
  };
  const addItem = () => {
    if (items.length >= 12) { setStatus('Maximum of 12 loose objects'); return; }
    const row = items.length % 3, col = Math.floor(items.length / 3) % 3;
    const position: [number,number,number] = [.10 + row * .23, -.25 + col * .24, 1.3 + Math.floor(items.length / 3) * .16];
    setItems([...items, { id: nextItemId(), type: selectedObject, position }]);
    setStatus('Scene rebuilt with added ' + selectedObject);
  };
  return <div className="app-shell">
    <header className="site-header">
      <a className="brand" href="../index.html">ONTOS <span>/ P37 NEURO</span></a>
      <nav aria-label="Research navigation">
        <a href="../index.html">Architecture</a>
        <a href="../compare/index.html?sample=mimicgen">Recorded evidence</a>
        <a href="https://ontosrobotics.github.io/P37-Neuro/">Existing Brain Lab ↗</a>
      </nav>
      <span className="build-tag">EXPERIMENT / 01</span>
    </header>
    <main>
      <div className="title-row">
        <div>
          <span className="overline">Interactive simulation / WebGPU</span>
          <h1>Steel physics.<br/>P37 experiments.</h1>
          <p className="intro">Pick a scene, move objects and change robot geometry. Every interaction runs inside a live WebGPU physics workcell.</p>
        </div>
        <div className="hero-note"><strong>About this demonstration</strong>
          <p>Live Steel physics and a deterministic joint controller. No trained P37-Neuro checkpoint is attached. MimicGen demonstrations are imported separately and never presented as this robot’s learned behavior.</p>
        </div>
      </div>
      <section className="lab-grid" aria-label="Interactive Steel research workcell">
        <aside className="side-panel">
          <div className="section-heading"><span>CONFIGURATION</span><span>01 / 04</span></div>
          <label htmlFor="preset">Environment</label>
          <select id="preset" value={preset} onChange={e=>changePreset(e.target.value as Preset)}>
            {PRESETS.map(p=><option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
          <p className="helper">{PRESETS.find(p=>p.id===preset)?.detail}</p>
          <div className="rule"/>
          <label htmlFor="robot">Reference embodiment</label>
          <select id="robot" value={robot} onChange={e=>{setRobot(e.target.value as RobotType);setStatus('Switching robot morphology');}}>
            <option value="compact">P37 reference / compact</option>
            <option value="extended">P37 reference / extended</option>
          </select>
          <p className="helper">Original procedural robots with different link lengths. Neither is a Panda, Sawyer, IIWA or UR5e model.</p>
          <label htmlFor="pose">Shoulder target <output>{pose.toFixed(2)} rad</output></label>
          <input id="pose" type="range" min="-1.2" max="1.2" step=".01" value={pose} onChange={e=>setPose(Number(e.target.value))}/>
          <div className="rule"/>
          <label htmlFor="item">Add real-world object</label>
          <select id="item" value={selectedObject} onChange={e=>setSelectedObject(e.target.value as ObjectType)}>
            <option value="parcel">Cardboard parcel</option>
            <option value="canister">Metal canister</option>
            <option value="ball">Rubber ball</option>
            <option value="bin">Storage bin</option>
          </select>
          <button className="primary" onClick={addItem}>+ Drop object into scene</button>
          <p className="helper">Objects have mass and contact geometry. Adding an object rebuilds the scene, resetting existing bodies.</p>
          <div className="rule"/>
          <label>Source-data replay</label>
          <button className="primary" onClick={() => setShowSource(!showSource)}>
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
          <p className="helper">The green line and moving marker follow original source end-effector coordinates, independent of the reference arm. This is P37 data playback, not trained policy inference or verified contact replay.</p>
          <div className="rule"/>
          <a className="small-link" href="https://huggingface.co/datasets/amandlek/mimicgen_datasets" target="_blank" rel="noreferrer">MimicGen source dataset ↗</a>
          <a className="small-link" href="../compare/index.html?sample=mimicgen">Watch official source motion in P37 ↗</a>
        </aside>
        <div className="viewport">
          <div className="playground-scenes" role="group" aria-label="Choose physics environment">
            <span className="playground-scenes-label">Scenes</span>
            {PRESETS.map(p=><button type="button" key={p.id}
              aria-pressed={preset===p.id} className={preset===p.id?'active':''}
              onClick={()=>changePreset(p.id)}>{p.label}</button>)}
          </div>
          <div className="viewport-top">
            <div><span className="live-dot"/> LIVE GPU PHYSICS <span className="muted">/ Steel WebGPU</span></div>
            <span>REFERENCE ROBOT · NO TRAINED POLICY</span>
          </div>
          <div className="canvas-wrap">
            <LiveScene key={preset + '-' + robot} preset={preset} robot={robot} items={items}
              paused={paused} collision={collision} pose={pose} sceneRef={scene}
              onSample={setStats} onReady={()=>setStatus('Steel physics active')}
              onError={setStatus} sourceFrames={showSource ? (sourceData?.traces[sourceEpisode]?.frames ?? []) : []}
              sourcePlaying={showSource && sourcePlaying && !paused}/>
            <div className="camera-tip">DRAG OBJECTS TO PULL · DRAG EMPTY SPACE TO ORBIT</div>
          </div>
          <div className="playground-embodiment" role="group" aria-label="Choose reference robot">
            <span>Reference robot</span>
            <button type="button" aria-pressed={robot==='compact'} onClick={()=>setRobot('compact')}>Compact arm</button>
            <button type="button" aria-pressed={robot==='extended'} onClick={()=>setRobot('extended')}>Extended arm</button>
            <span className="playground-disclaimer">Procedural geometry · no learned P37 policy</span>
          </div>
          <div className="viewport-controls">
            <div className="action-row">
              <button onClick={()=>setPaused(!paused)}>{paused ? '▶ Resume' : 'Ⅱ Pause'}</button>
              <button onClick={reset}>↻ Reset</button>
              <button aria-pressed={collision} onClick={()=>setCollision(!collision)}>
                {collision ? 'Hide collision geometry' : 'Show collision geometry'}
              </button>
            </div>
            <div className="status-line" role="status">{status}</div>
          </div>
        </div>
        <aside className="evidence-panel">
          <div className="section-heading"><span>EXPERIMENT STATUS</span><span>02 / 04</span></div>
          <div className="info-row"><span>Physics backend</span><strong>Steel / WebGPU</strong></div>
          <div className="info-row"><span>Simulation time</span><strong>{stats ? stats.time.toFixed(1) + ' s' : '—'}</strong></div>
          <div className="info-row"><span>Solver contacts</span><strong>{stats?.contacts ?? '—'}</strong></div>
          <div className="info-row"><span>Movable objects</span><strong>{items.length}</strong></div>
          <div className="info-row"><span>Robot geometry</span><strong>{robot}</strong></div>
          <div className="info-row"><span>Recorded dataset</span><strong>{showSource ? "MimicGen Panda source" : "None"}</strong></div>
          <div className="rule"/>
          <div className="section-cap">What is running</div>
          <p className="evidence-copy">Steel simulates rigid-body contacts. The reference robot receives deterministic joint position commands. All furniture and materials were created for this demo.</p>
          <div className="flag">Policy checkpoint: <b>None</b><br/>MimicGen model training: <b>Not executed</b><br/>Recorded source playback: <b>{showSource ? "Active" : "Off"}</b><br/>Learned cross-body transfer: <b>Unverified</b></div>
          <div className="section-cap">P37 integration</div>
          <p className="evidence-copy">The <a href="../compare/index.html">recorded experiment viewer</a> accepts canonical P37 episodes. The MimicGen HDF5 adapter preserves dataset-native actions without claiming they are joint commands.</p>
        </aside>
      </section>
      <section className="bottom-grid">
        <div><span className="overline">01 / Physics</span><h2>Interact with the scene.</h2><p>A table, chair, monitor and loose objects have physical collision geometry. Studio lighting and procedural materials provide a realistic industrial workcell.</p></div>
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
