import { useEffect, useRef, useState } from 'react';
import {
  Physics, Scene, type SceneHandle, type SimStatsSample,
} from '@skild-ai/steel-webgpu/react';
import { Workcell, PRESETS, initialItems, nextItemId } from './Workcell';
import type { LooseItem, ObjectType, Preset, RobotType } from './Workcell';
import type { SourceFrame } from './SourceTrajectory';

type SourceData = {
  publication: { source: string; learned_policy_attached: boolean };
  traces: { episode_id: string; frames: SourceFrame[] }[];
};
type CameraView = 'three-quarter' | 'front' | 'overhead';
const CAMERAS: Record<CameraView, {
  position: [number,number,number]; target: [number,number,number]; fov: number;
}> = {
  'three-quarter': { position: [2.5,-3.2,2.12], target: [-.02,0,.91], fov: 41 },
  front: { position: [0,-3.5,1.43], target: [0,0,.88], fov: 39 },
  overhead: { position: [1.8,-2.0,3.45], target: [0,0,.73], fov: 43 },
};
const ROBOTS: {id:RobotType; name:string; detail:string}[] = [
  {id:'compact', name:'Compact arm', detail:'Reference · shorter arm geometry'},
  {id:'extended', name:'Extended arm', detail:'Reference · longer arm geometry'},
];
const OBJECTS: {id:ObjectType; name:string; detail:string}[] = [
  {id:'parcel',name:'Parcel',detail:'Cardboard package'},
  {id:'canister',name:'Canister',detail:'Machined metal cylinder'},
  {id:'ball',name:'Sphere',detail:'Rubber contact test'},
  {id:'bin',name:'Bin',detail:'Open storage container'},
];
const MAX_ITEMS=12;
function LiveScene({
  preset, robot, items, paused, collision, pose, camera, sceneRef,
  onSample, onReady, onError, sourceFrames, sourcePlaying,
}: {
  preset: Preset; robot: RobotType; items: LooseItem[]; paused:boolean;
  collision:boolean; pose:number; camera:CameraView;
  sceneRef:React.RefObject<SceneHandle | null>;
  onSample:(data:SimStatsSample | null)=>void;
  onReady:()=>void; onError:(message:string)=>void;
  sourceFrames:SourceFrame[];sourcePlaying:boolean;
}) {
  return <Physics
    style={{position:'absolute',inset:0,width:'100%',height:'100%'}}
    fallback={<div className="viewer-notice">
      <div className="spinner"/>
      <strong>Preparing the physical environment</strong>
      <p>Starting Steel and compiling the workcell on your GPU.</p>
    </div>}
    unsupported={reason=><div className="viewer-notice">
      <strong>This scene needs WebGPU</strong>
      <p>{reason}</p>
      <p>Use a current Chrome, Edge or Safari browser with WebGPU and hardware acceleration enabled.</p>
      <a href="../../?robot=franka_panda">Open the existing MuJoCo Panda viewer instead ↗</a>
    </div>}
    onError={error=>onError(String(error))}
  >
    <Scene
      ref={sceneRef} gravity={[0,0,-9.81]} fps={60}
      paused={paused} collision={collision}
      pickable controls camera={CAMERAS[camera]}
      onLoaded={onReady} onError={error=>onError(String(error))}
    >
      <Workcell preset={preset} robot={robot} items={items} pose={pose}
        onStats={onSample} sourceFrames={sourceFrames} sourcePlaying={sourcePlaying}/>
    </Scene>
  </Physics>;
}
export function App() {
  const [preset,setPreset]=useState<Preset>('workcell');
  const [robot,setRobot]=useState<RobotType>('compact');
  const [items,setItems]=useState<LooseItem[]>(()=>initialItems('workcell'));
  const [selectedObject,setSelectedObject]=useState<ObjectType>('parcel');
  const [pose,setPose]=useState(.18);
  const [paused,setPaused]=useState(false);
  const [collision,setCollision]=useState(false);
  const [camera,setCamera]=useState<CameraView>('three-quarter');
  const [status,setStatus]=useState('Starting Steel WebGPU');
  const [ready,setReady]=useState(false);
  const [stats,setStats]=useState<SimStatsSample | null>(null);
  const [showControls,setShowControls]=useState(false);
  const [sourceData,setSourceData]=useState<SourceData | null>(null);
  const [showSource,setShowSource]=useState(false);
  const [sourceEpisode,setSourceEpisode]=useState(0);
  const [sourcePlaying,setSourcePlaying]=useState(true);
  const scene=useRef<SceneHandle>(null);
  const stage=useRef<HTMLElement>(null);

  useEffect(()=>{
    if(!showSource || sourceData)return;
    const abort=new AbortController();
    const sourceUrl=import.meta.env.BASE_URL+'samples/mimicgen-square-source.json';
    fetch(sourceUrl,{signal:abort.signal}).then(async response=>{
      if(!response.ok)throw new Error('Official recording has not been published in this build');
      const value=await response.json() as SourceData;
      if(value.publication?.source!=='amandlek/mimicgen_datasets' ||
         value.publication?.learned_policy_attached!==false ||
         !Array.isArray(value.traces) || value.traces.length<2 ||
         value.traces.some(trace=>trace.frames.length<2 ||
           trace.frames.some(frame=>![0,1,2].every(i=>
             Number.isFinite(frame.state['eef_position_'+i])))))
        throw new Error('Missing or invalid original source evidence');
      setSourceData(value);
      setStatus('Official source path loaded — external recording, no policy');
    }).catch(error=>{
      if(abort.signal.aborted)return;
      setStatus('Could not load verified source data: '+String(error));
      setShowSource(false);
    });
    return ()=>abort.abort();
  },[showSource,sourceData]);

  const changePreset=(next:Preset)=>{
    if(next===preset)return;
    setPreset(next);
    setItems(initialItems(next));
    setReady(false);
    setStatus('Loading '+PRESETS.find(p=>p.id===next)?.label);
  };
  const reset=()=>{
    setItems(initialItems(preset));
    scene.current?.reset();
    setStatus('Physics scene reset');
  };
  const addItem=()=>{
    if(items.length>=MAX_ITEMS){setStatus('Object limit reached — reset to clear the scene');return;}
    const n=items.length,row=n%3,col=Math.floor(n/3)%3;
    const position:[number,number,number]=[.05+row*.24,-.25+col*.23,1.28+Math.floor(n/3)*.18];
    setItems(previous=>[...previous,{id:nextItemId(),type:selectedObject,position}]);
    setStatus('Added physical '+selectedObject+' · resetting solver state');
  };
  useEffect(()=>{
    const keydown=(event:KeyboardEvent)=>{
      if(event.target instanceof HTMLElement &&
         /^(INPUT|TEXTAREA|SELECT|BUTTON)$/.test(event.target.tagName))return;
      if(event.code==='Space'){event.preventDefault();setPaused(value=>!value);}
      if(event.key.toLowerCase()==='r')reset();
      if(event.key==='Escape')setShowControls(false);
    };
    window.addEventListener('keydown',keydown);
    return ()=>window.removeEventListener('keydown',keydown);
    // The latest reset handler is not needed until the next render; the effect
    // re-registers when the environment changes.
  },[preset]);
  const activeSource=showSource ? sourceData?.traces[sourceEpisode]?.frames ?? [] : [];
  return <div className="app-shell">
    <header className="site-header">
      <a href="../../" className="brand" aria-label="Ontos P37 Brain Lab home">
        <span className="brand-icon">O</span>
        <span>ONTOS <span className="brand-secondary">/ P37 NEURO</span></span>
      </a>
      <nav aria-label="Research navigation">
        <a href="../../">Brain Lab</a>
        <a href="../../demos/">Simulations</a>
        <a href="../compare/?sample=mimicgen">Recorded data</a>
        <a href="https://github.com/OntosRobotics/P37-Neuro" target="_blank" rel="noreferrer">Source ↗</a>
      </nav>
      <span className="header-id">RESEARCH / 02</span>
    </header>
    <main>
      <section className="intro">
        <div>
          <p className="eyebrow">P37-Neuro / Interactive physics</p>
          <h1>Machines in the world.</h1>
          <p className="lede">A real-time robotics workcell. Move physical objects, change the environment and inspect the behavior of two reference robot configurations.</p>
        </div>
        <div className="intro-aside">
          <span className="status-circle"/>
          <p><strong>Physics is live.</strong> Object contacts run in Steel WebGPU. The robot uses a deterministic joint controller; no trained P37 policy is attached.</p>
        </div>
      </section>

      <section ref={stage} className="experiment-stage" aria-label="Interactive industrial robot simulation">
        <div className="stage-canvas">
          <LiveScene key={preset+'-'+robot} preset={preset} robot={robot}
            items={items} paused={paused} collision={collision} pose={pose}
            camera={camera} sceneRef={scene}
            onSample={setStats}
            onReady={()=>{setReady(true);setStatus('Steel physical environment active');}}
            onError={message=>{setReady(false);setStatus('Physics error: '+message);}}
            sourceFrames={activeSource} sourcePlaying={showSource&&sourcePlaying&&!paused}/>
          <div className="stage-top" aria-hidden="true">
            <div className="stage-caption">
              <span className="stage-kicker">LIVE EXPERIMENT</span>
              <strong>{PRESETS.find(p=>p.id===preset)?.label}</strong>
              <span>DETERMINISTIC REFERENCE CONTROL</span>
            </div>
            <div className="live-status"><span className={ready?'status-light active':'status-light'}/>
              {ready?'WEBGPU / LIVE':'WEBGPU / STARTING'}
            </div>
          </div>
          <div className="scene-tabs" role="group" aria-label="Choose physical environment">
            {PRESETS.map((entry,i)=><button
              key={entry.id} type="button" className={preset===entry.id?'scene-tab active':'scene-tab'}
              onClick={()=>changePreset(entry.id)} aria-pressed={preset===entry.id}>
              <span>{String(i+1).padStart(2,'0')}</span>{entry.label}
            </button>)}
          </div>
          <div className="stage-bottom">
            <div className="scene-hint">DRAG AN OBJECT TO PULL IT <span>·</span> DRAG EMPTY SPACE TO ORBIT</div>
            <div className="camera-switch" role="group" aria-label="Camera angle">
              <button className={camera==='three-quarter'?'active':''} onClick={()=>setCamera('three-quarter')} aria-pressed={camera==='three-quarter'}>3/4</button>
              <button className={camera==='front'?'active':''} onClick={()=>setCamera('front')} aria-pressed={camera==='front'}>Front</button>
              <button className={camera==='overhead'?'active':''} onClick={()=>setCamera('overhead')} aria-pressed={camera==='overhead'}>Top</button>
            </div>
          </div>
          {showSource&&<div className="source-overlay">
            <span className="source-dot"/> EXTERNAL SOURCE TRAJECTORY / MIMICGEN
            <small>This path does not drive the reference robot.</small>
          </div>}
        </div>
        <div className="command-bar">
          <div className="command-leading">
            <span className="command-label">OBJECT INTERACTION</span>
            <select aria-label="Object type" value={selectedObject}
              onChange={e=>setSelectedObject(e.target.value as ObjectType)}>
              {OBJECTS.map(o=><option key={o.id} value={o.id}>{o.name}</option>)}
            </select>
            <button className="primary-action" onClick={addItem}>+ Drop into scene</button>
          </div>
          <div className="command-actions">
            <button type="button" onClick={()=>setPaused(!paused)}>{paused?'▶ Resume':'Ⅱ Pause'}</button>
            <button type="button" onClick={reset}>↻ Reset</button>
            <button type="button" aria-expanded={showControls} aria-controls="lab-settings"
              onClick={()=>setShowControls(!showControls)}>{showControls?'Close controls':'Controls'} <span>☷</span></button>
            <button type="button" className="fullscreen" onClick={()=>{
              if(document.fullscreenElement)void document.exitFullscreen();
              else if(stage.current?.requestFullscreen)void stage.current.requestFullscreen();
            }}>⛶ <span>Expand</span></button>
          </div>
          <span className="sim-status" role="status">{status}</span>
        </div>
        {showControls&&<aside className="controls-drawer" id="lab-settings" aria-label="Experiment controls">
          <div className="drawer-head"><div><span className="eyebrow">ENGINEERING CONTROLS</span><h2>Workcell configuration</h2></div><button onClick={()=>setShowControls(false)} aria-label="Close experiment controls">×</button></div>
          <div className="drawer-fields">
            <label htmlFor="robot">Robot morphology</label>
            <select id="robot" value={robot} onChange={e=>{setRobot(e.target.value as RobotType);setReady(false);setStatus('Switching reference body');}}>
              {ROBOTS.map(r=><option value={r.id} key={r.id}>{r.name} / {r.detail}</option>)}
            </select>
            <p className="field-explain">Original procedural arms with different link dimensions. Neither is a manufacturer model.</p>
            <label htmlFor="pose">Joint target <output>{pose.toFixed(2)} rad</output></label>
            <input id="pose" type="range" min="-1.2" max="1.2" step=".01"
              value={pose} onChange={e=>setPose(Number(e.target.value))}/>
            <button className="outline-action" aria-pressed={collision}
              onClick={()=>setCollision(!collision)}>{collision?'Hide collision geometry':'Inspect collision geometry'}</button>
          </div>
          <div className="drawer-fields">
            <p className="eyebrow">OFFLINE DATA / ATTRIBUTED</p>
            <button className="outline-action" onClick={()=>setShowSource(!showSource)}>
              {showSource?'Hide original recorded trajectory':'Show genuine MimicGen motion'}
            </button>
            {showSource&&sourceData&&<>
              <label htmlFor="episode">Recorded episode</label>
              <select id="episode" value={sourceEpisode}
                onChange={e=>setSourceEpisode(Number(e.target.value))}>
                {sourceData.traces.map((trace,i)=><option value={i} key={trace.episode_id}>
                  Panda source recording {i+1}
                </option>)}
              </select>
              <button className="outline-action" onClick={()=>setSourcePlaying(!sourcePlaying)}>
                {sourcePlaying?'Pause original recording':'Play original recording'}
              </button>
            </>}
            <p className="field-explain">The path comes from external MimicGen data. It visualizes source observations and does not actuate this reference arm.</p>
            <a className="inline-link" href="../compare/?sample=mimicgen">Inspect original joint states and actions ↗</a>
          </div>
        </aside>}
      </section>

      <section className="experiment-ledger" aria-label="Physics and model provenance">
        <div><span className="ledger-number">01 / SOLVER</span><strong>Steel WebGPU</strong><p>Real-time rigid-body contact and articulated dynamics.</p></div>
        <div><span className="ledger-number">02 / SCENE</span><strong>{items.length} movable objects</strong><p>Industrial workcell, authored materials and physical furniture.</p></div>
        <div><span className="ledger-number">03 / CONTROL</span><strong>Deterministic baseline</strong><p>Reference robot joint targets. No P37 policy checkpoint.</p></div>
        <div><span className="ledger-number">04 / MEASUREMENT</span><strong>{stats?stats.contacts:'—'} solver contacts</strong><p>Simulation time {stats?stats.time.toFixed(1)+' s':'—'} · not a task success metric.</p></div>
      </section>
      <section className="research-strip">
        <div><span className="eyebrow">SOURCE DATA / TRANSPARENT EVIDENCE</span>
          <h2>Inspect a real robot recording.</h2>
          <p>Two original MimicGen Panda demonstrations are available through P37’s episode normalization and trace playback. They show genuine recorded observations. They do not establish learned P37 cross-embodiment transfer.</p>
          <div className="research-actions">
            <a href="../compare/?sample=mimicgen" className="research-primary">Play recorded episodes ↗</a>
            <a href="../../?robot=franka_panda">Explore official Panda model ↗</a>
          </div>
        </div>
        <div className="research-stat">
          <span>VERIFIED SOURCE / MIMICGEN</span>
          <strong>250</strong>
          <span>recorded frames across two source episodes</span>
          <p>These recordings are offline data. The 3D workcell uses procedural reference geometry and independent interactive physics.</p>
        </div>
      </section>
    </main>
    <footer className="footer">
      <span>ONTOS / P37 NEURO <i>© 2026</i></span>
      <div><a href="../../">Brain Lab</a><a href="https://github.com/skild-ai/steel-webgpu">Steel ↗</a>
      <a href="https://mimicgen.github.io/">MimicGen ↗</a><a href="https://github.com/OntosRobotics/P37-Neuro">Source ↗</a></div>
    </footer>
  </div>;
}
