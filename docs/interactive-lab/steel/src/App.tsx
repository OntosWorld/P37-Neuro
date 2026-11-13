import { useEffect, useMemo, useRef, useState } from 'react';
import { TASK_EXPERIMENTS, taskProgress } from './taskExperiments';
import { TaskGallery } from './TaskGallery';
import { GALLERY_TASKS, type GalleryTask } from './taskGallery';

type Robot = {
  id: string; name: string; model: string; kind: string;
  short: string; task: string; capability: string;
};
type Catalog = { robots: Robot[] };
type MotionMode = 'motion_cycle' | 'articulation' | 'hold' | 'p37_experimental' | 'panda_scripted_stack';
type Experience = 'simulation' | 'recorded' | 'policy';
type MotionClip = {
  robot_id: string; id: string; name: string; source: string;
  dataset_file: string; frames: number; control_hz: number;
  is_learned_p37_policy: boolean; is_qualified_locomotion: boolean;
};
type MotionLibrary = {
  schema_version: number; kind: string; motions: Record<string, MotionClip[]>;
};
type SteeringKey = 'forward'|'back'|'left'|'right'|'turnLeft'|'turnRight';
type SteeringTelemetry = {
  status: 'waiting'|'ready'|'running'|'fixed';
  controllable?: boolean;
  x?: number; y?: number; z?: number; distance?: number; moved?: number;
  message?: string; steering?: boolean;
  relativeX?: number; relativeY?: number; relativeZ?: number;
  jointDelta?: number; jointName?: string;
  objectDistance?: number; stackHeight?: number; stackStable?: boolean;
  objectDelivered?: boolean; observedObjects?: number;
  scriptedTaskRunning?: boolean; scriptedTaskElapsed?: number;
  taskTime?: number;
};
type BuildInfo = {
  trained_p37_policy_attached: boolean;
  qualified_cross_body_transfer: boolean;
  manufacturer_robots: string[];
  experimental_policy_robot?: string;
  p37_checkpoint_sha256?: string;
  panda_physical_cube_stack?: {
    mode: string;
    qualified_native_contact_and_replay: boolean;
    learned_p37_policy: boolean;
    control_sha256: string;
    frames: number;
    control_hz: number;
    left_contact_frames: number;
    right_contact_frames: number;
  };
};
type Trial = { seed: number; commands_sent: number; sim_seconds: number };
type Evidence = {
  checkpoint_sha256: string;
  same_checkpoint_used_for_all_bodies: boolean;
  qualified_for_cross_body_task_transfer: boolean;
  qualified_for_walking: boolean;
  bodies: Record<string, { actuators: number; trials: Trial[] }>;
  provenance: { workflow: string };
  limitation: string;
};
type G1Evidence = { evaluation: { seeds: { fallen: boolean }[] }; qualification: string };

const CATEGORIES = ['All', 'Humanoids', 'Quadrupeds', 'Manipulators', 'Mobile', 'Aerial'];
const PANDA_STAGES = [
  { name:'Approach', start:0, end:5.0 },
  { name:'Grasp', start:5.0, end:6.5 },
  { name:'Lift', start:6.5, end:8.9 },
  { name:'Carry', start:8.9, end:11.5 },
  { name:'Place', start:11.5, end:15.0 },
  { name:'Verify', start:15.0, end:18.2 },
];

export function App() {
  const [catalog, setCatalog] = useState<Robot[]>([]);
  const [selected, setSelected] = useState('franka_panda');
  const [activeTaskId, setActiveTaskId] = useState('panda-stack');
  const [experience, setExperience] = useState<Experience>('simulation');
  const [motion, setMotion] = useState<MotionMode>('panda_scripted_stack');
  const [lastMotion, setLastMotion] = useState<MotionMode>('panda_scripted_stack');
  const [category, setCategory] = useState('All');
  const [panel, setPanel] = useState(false);
  const [reload, setReload] = useState(0);
  const [stageLoaded, setStageLoaded] = useState(false);
  const [telemetry, setTelemetry] = useState<SteeringTelemetry>({status:'waiting'});
  const iframeRef = useRef<HTMLIFrameElement|null>(null);
  const heldRef = useRef<Set<SteeringKey>>(new Set());
  const [error, setError] = useState('');
  const [build, setBuild] = useState<BuildInfo | null>(null);
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [g1Evidence, setG1Evidence] = useState<G1Evidence | null>(null);
  useEffect(() => {
    const abort = new AbortController();
    Promise.all([
      fetch(import.meta.env.BASE_URL + 'catalog.json', { signal: abort.signal })
        .then(async r => { if (!r.ok) throw new Error('Robot catalog not deployed'); return r.json() as Promise<Catalog>; }),
      fetch(import.meta.env.BASE_URL + 'build-info.json', { signal: abort.signal })
        .then(async r => { if (!r.ok) throw new Error('Build metadata not deployed'); return r.json() as Promise<BuildInfo>; }),
      fetch(import.meta.env.BASE_URL + 'p37-cross-body-evidence.json', { signal: abort.signal })
        .then(async r => { if (!r.ok) throw new Error('Policy evidence missing'); return r.json() as Promise<Evidence>; }),
      fetch(import.meta.env.BASE_URL + 'p37-evidence.json', { signal: abort.signal })
        .then(async r => { if (!r.ok) throw new Error('G1 evidence missing'); return r.json() as Promise<G1Evidence>; }),
      fetch(import.meta.env.BASE_URL + 'simulator/motion_data/index.json',
        { signal: abort.signal }).then(async r => {
          if (!r.ok) throw new Error('Movement dataset not deployed');
          return r.json() as Promise<MotionLibrary>;
        }),
    ]).then(([data, info, trials, evaluation, motions]) => {
      if (!Array.isArray(data.robots) || data.robots.length !== 10
        || !data.robots.some(r => r.id === 'unitree_g1')
        || info.manufacturer_robots.length !== 10
        || trials.qualified_for_walking !== false
        || trials.qualified_for_cross_body_task_transfer !== false
        || evaluation.qualification !== 'unqualified'
        || motions.schema_version !== 1
        || motions.kind !== 'p37_model_derived_motions'
        || data.robots.some(r => !motions.motions[r.id]
          || motions.motions[r.id].length !== 3)) {
        throw new Error('Robot catalog and P37 evidence did not pass integrity checks');
      }
      setCatalog(data.robots);
      setBuild(info);
      setEvidence(trials);
      setG1Evidence(evaluation);
    }).catch(reason => {
      if (!abort.signal.aborted) setError(String(reason));
    });
    return () => abort.abort();
  }, []);
  const current = catalog.find(r => r.id === selected);
  const activeTask = GALLERY_TASKS.find(task => task.id === activeTaskId);
  const pandaTime = telemetry.taskTime ?? 0;
  const experiment = TASK_EXPERIMENTS[selected];
  const result = experiment ? taskProgress(experiment, telemetry) : null;
  const selection = useMemo(() => catalog.filter(robot =>
    category === 'All' || robot.kind === category), [catalog, category]);
  const p37Available = selected === 'unitree_g1'
    && build?.trained_p37_policy_attached === true
    && build.experimental_policy_robot === 'unitree_g1'
    && build.p37_checkpoint_sha256 === evidence?.checkpoint_sha256;
  const p37Active = p37Available && motion === 'p37_experimental';
  const pandaActive = selected === 'franka_panda' && motion === 'panda_scripted_stack';
  const isFixedArm = current?.kind === 'Manipulators';
  const canSteer = !isFixedArm && telemetry.status !== 'fixed';
  const sendSteer = (key: SteeringKey, down: boolean) => {
    const message = { type:'p37:steering', robot:selected, action:'input', key, down };
    iframeRef.current?.contentWindow?.postMessage(message, window.location.origin);
    if (down) heldRef.current.add(key);
    else heldRef.current.delete(key);
  };
  const releaseSteer = () => {
    heldRef.current.clear();
    iframeRef.current?.contentWindow?.postMessage(
      {type:'p37:steering', robot:selected, action:'release'}, window.location.origin
    );
  };
  useEffect(() => {
    const accepted: Record<string, SteeringKey> = {
      w:'forward', ArrowUp:'forward', s:'back', ArrowDown:'back',
      a:'left', ArrowLeft:'left', d:'right', ArrowRight:'right',
      q:'turnLeft', e:'turnRight',
    };
    const handleKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement|null;
      if (target?.closest('input, select, textarea, [contenteditable="true"]')) return;
      const key = accepted[event.key] ?? accepted[event.key.toLowerCase()];
      if (!key || isFixedArm) return;
      event.preventDefault();
      if (event.type==='keydown' && event.repeat) return;
      sendSteer(key,event.type==='keydown');
    };
    const keydown = (event: KeyboardEvent) => handleKey(event);
    const keyup = (event: KeyboardEvent) => handleKey(event);
    const blur = () => releaseSteer();
    window.addEventListener('keydown',keydown);
    window.addEventListener('keyup',keyup);
    window.addEventListener('blur',blur);
    return () => {
      window.removeEventListener('keydown',keydown);
      window.removeEventListener('keyup',keyup);
      window.removeEventListener('blur',blur);
      releaseSteer();
    };
  }, [selected,isFixedArm]);
  useEffect(() => {
    const receive = (event: MessageEvent) => {
      if (event.origin!==window.location.origin ||
          event.source!==iframeRef.current?.contentWindow) return;
      const msg = event.data;
      if (!msg || msg.type!=='p37:telemetry' || msg.robot!==selected) return;
      const status = msg.status;
      if (!['ready','running','fixed'].includes(status)) return;
      setTelemetry({
        status, controllable: msg.controllable===true,
        x: Number.isFinite(msg.x)?msg.x:undefined,
        y: Number.isFinite(msg.y)?msg.y:undefined,
        z: Number.isFinite(msg.z)?msg.z:undefined,
        distance: Number.isFinite(msg.distance)?msg.distance:undefined,
        moved: Number.isFinite(msg.moved)?msg.moved:undefined,
        message: typeof msg.message==='string'?msg.message:undefined,
        steering: msg.steering===true,
        relativeX: Number.isFinite(msg.relativeX)?msg.relativeX:undefined,
        relativeY: Number.isFinite(msg.relativeY)?msg.relativeY:undefined,
        relativeZ: Number.isFinite(msg.relativeZ)?msg.relativeZ:undefined,
        jointDelta: Number.isFinite(msg.jointDelta)?msg.jointDelta:undefined,
        jointName: typeof msg.jointName==='string'?msg.jointName:undefined,
        objectDistance: Number.isFinite(msg.objectDistance)?msg.objectDistance:undefined,
        stackHeight: Number.isFinite(msg.stackHeight)?msg.stackHeight:undefined,
        stackStable: msg.stackStable === true,
        objectDelivered: msg.objectDelivered === true,
        observedObjects: Number.isInteger(msg.observedObjects)?msg.observedObjects:undefined,
        scriptedTaskRunning: msg.scriptedTaskRunning === true,
        scriptedTaskElapsed: Number.isFinite(msg.scriptedTaskElapsed)?msg.scriptedTaskElapsed:undefined,
        taskTime: Number.isFinite(msg.taskTime)?msg.taskTime:undefined,
      });
    };
    window.addEventListener('message',receive);
    return () => window.removeEventListener('message',receive);
  },[selected]);
  const setPlayback = (next: MotionMode) => {
    if (next === 'p37_experimental' && !p37Available) return;
    if (next === 'panda_scripted_stack' && selected !== 'franka_panda') return;
    if (next !== 'hold') setLastMotion(next);
    releaseSteer();
    setExperience(next === 'p37_experimental' ? 'policy' : 'simulation');
    setMotion(next);
    setTelemetry({status:'waiting'});
    setStageLoaded(false);
    setReload(x => x + 1);
  };
  const playableMode = (mode: MotionMode) => ({
    motion_cycle: 'movement_cycle',
    articulation: 'motor_articulation',
    hold: 'hold_position',
    p37_experimental: 'p37_g1_experimental_recurrent_ppo',
    panda_scripted_stack: 'panda_physical_cube_stack_scripted',
  })[mode];
  const selectRobot = (robot: Robot) => {
    releaseSteer();
    setSelected(robot.id);
    setActiveTaskId(GALLERY_TASKS.find(task =>
      task.robotId === robot.id && task.route !== 'recorded')?.id ?? '');
    setExperience('simulation');
    setTelemetry({status:'waiting'});
    setMotion(robot.id === 'franka_panda' ? 'panda_scripted_stack' : 'motion_cycle');
    setLastMotion(robot.id === 'franka_panda' ? 'panda_scripted_stack' : 'motion_cycle');
    setStageLoaded(false);
    setReload(x => x + 1);
  };
  const changeExperience = (next: Experience) => {
    if (next === experience) return;
    releaseSteer();
    setTelemetry({status:'waiting'});
    setStageLoaded(false);
    if (next === 'policy') {
      if (!build?.trained_p37_policy_attached ||
          build.experimental_policy_robot !== 'unitree_g1') return;
      setSelected('unitree_g1');
      setMotion('p37_experimental');
    } else if (experience === 'policy') {
      setMotion('motion_cycle');
    }
    setExperience(next);
    setReload(n => n + 1);
  };
  const openTask = (task: GalleryTask) => {
    releaseSteer();
    setActiveTaskId(task.id);
    setSelected(task.robotId);
    const mode: MotionMode = task.route === 'panda' || task.route === 'recorded'
      ? 'panda_scripted_stack'
      : task.route === 'p37' ? 'p37_experimental' : 'motion_cycle';
    setMotion(mode);
    setLastMotion(mode);
    setExperience(task.route === 'recorded' ? 'recorded'
      : task.route === 'p37' ? 'policy' : 'simulation');
    setTelemetry({status:'waiting'});
    setStageLoaded(false);
    setReload(value => value + 1);
    window.requestAnimationFrame(() => document.getElementById('simulator')
      ?.scrollIntoView({ behavior:'smooth', block:'start' }));
  };
  const toggleReferenceTask = () => {
    if (experiment?.kind !== 'terrain') return;
    iframeRef.current?.contentWindow?.postMessage({
      type:'p37:steering', robot:selected,
      action:telemetry.scriptedTaskRunning ? 'stop-task' : 'start-task'
    }, window.location.origin);
  };
  const url = import.meta.env.BASE_URL + 'simulator/?project=p37_robot_models&scene='
    + encodeURIComponent(selected)
    + '&policy=' + encodeURIComponent(playableMode(motion))
    + '&panel=' + (panel ? '1' : '0');
  return <div className="app-shell p37-real">
    <header className="site-header">
      <a className="brand" href="./">ONTOS <span>/ P37 NEURO</span></a>
      <nav aria-label="P37 navigation">
        <a href="#tasks">Experiments</a>
        <a href="#simulator">Live simulation</a>
        <a href="#evidence">Research evidence</a>
        <a href="https://github.com/OntosRobotics/P37-Neuro" target="_blank" rel="noreferrer">GitHub ↗</a>
      </nav>
      <span className="build-tag">POWERED BY P37-NEURO</span>
    </header>
    <main>
      <TaskGallery activeId={activeTaskId} onSelect={openTask} baseUrl={import.meta.env.BASE_URL}/>
      <section className="title-row p37-experiment-heading">
        <span className="overline">OPEN EXPERIMENT / {activeTask?.kicker ?? 'MANUFACTURER ROBOT'}</span>
        <div className="p37-experiment-heading-row">
          <div>
            <h2>{activeTask?.title ?? current?.name ?? 'Inspect a robot'}</h2>
            <p className="intro">{activeTask?.description ??
              'Explore manufacturer-derived articulated robots in live MuJoCo physics.'}</p>
          </div>
          <div className="p37-task-definition">
            <small>EXECUTION STATUS</small>
            <strong>{activeTask?.status ?? 'Model-derived physics'}</strong>
            <span>{activeTask?.limits ?? 'No qualified task controller attached.'}</span>
          </div>
        </div>
      </section>
      <section className="lab-grid" id="simulator" aria-label="Live manufacturer robot simulation">
        <div className="viewport">
          <div className="p37-live-task-header">
            <span>SIMULATION / {activeTask?.robotName ?? current?.name ?? 'SELECT ROBOT'}</span>
            <strong>{activeTask?.title ?? 'Physical model exploration'}</strong>
            <span className="p37-sim-kind">{activeTask?.status ?? 'Native MuJoCo'}</span>
          </div>
          <div className="p37-experience-tabs" role="group" aria-label="Choose experiment experience">
            <button type="button" aria-pressed={experience==='simulation'}
              onClick={()=>changeExperience('simulation')}>Live physical tasks</button>
            <button type="button" aria-pressed={experience==='recorded'}
              onClick={()=>changeExperience('recorded')}>Recorded execution</button>
            <button type="button" aria-pressed={experience==='policy'}
              disabled={!build?.trained_p37_policy_attached}
              onClick={()=>changeExperience('policy')}>P37 model experiment</button>
          </div>
          <div className="viewport-top">
            <div><span className="live-dot"/> {experience==='recorded'?'SOURCE-RECORDED EPISODE':'NATIVE ROBOT PHYSICS'}
              <span className="muted"> / MuJoCo · WebAssembly</span></div>
            <div className="stage-tools-head">
              <span>{pandaActive ? 'PANDA SCRIPTED TASK / VERIFIED NATIVE PHYSICS' :
                p37Active ? 'P37 RECURRENT ONNX / EXPERIMENTAL' :
                motion === 'hold' ? 'HOLD POSITION / NATIVE PHYSICS' :
                'MOTION DATASET / NATIVE PHYSICS'}</span>
            </div>
          </div>
          <div className="canvas-wrap p37-scene">
            {experience==='recorded' ? <iframe
              title="Source-attributed MimicGen Panda robot task recording"
              className="p37-recorded-viewer"
              src={import.meta.env.BASE_URL + 'recorded/?sample=mimicgen'}
              loading="eager"/> : catalog.length > 0 && current ? <iframe
              ref={iframeRef}
              key={selected + '-' + reload + '-' + panel + '-' + motion}
              title={current.name + ' — real MuJoCo robot'}
              className="menagerie-viewer"
              src={url}
              allow="fullscreen"
              loading="eager"
              onLoad={() => setStageLoaded(true)}/>
              : <div className="viewer-notice">
                {error ? 'Robot models unavailable: ' + error : 'Loading real robot models…'}
              </div>}
            {experience!=='recorded' && current && <div className="p37-stage-name">
              <small>ROBOT {String(catalog.indexOf(current) + 1).padStart(2, '0')} / {catalog.length}</small>
              <strong>{current.name}</strong>
              <span>{current.short}</span>
            </div>}
            {experience!=='recorded' && <div className="camera-tip">DRAG TO ORBIT · WASD TO STEER · Q/E TO TURN</div>}
          </div>
          <div className="playground-embodiment p37-stage-actions">
            <span>Execution source</span>
            <strong>{experience==='recorded' ? 'MimicGen original Panda episodes · CC BY 4.0' :
              pandaActive ? 'Validated scripted Panda motor reference · not learned' :
              p37Active ? 'Experimental P37 recurrent PPO' :
              motion === 'hold' ? 'Hold pose · model-derived' :
              'Recorded joint targets · model-derived'}</strong>
            <span className="playground-disclaimer">{experience==='recorded'
              ? 'Source data replay · separate from live simulation' : stageLoaded ?
              'Viewer loaded · inspect motion inside the live scene' : 'Loading native simulation…'}</span>
          </div>
          {experience!=='recorded' && experiment && result && <section className="p37-task-experiment" aria-label="Measured robot task experiment">
            <div className="p37-task-topline">
              <span>ACTIVE TASK / {experiment.id.toUpperCase()}</span>
              <span>{result.reached ? 'MEASURED CONDITION MET' : 'TASK UNDER EVALUATION'}</span>
            </div>
            <h2>{experiment.title}</h2>
            <p>{experiment.objective}</p>
            {pandaActive && <div className="p37-task-timeline"
              role="list" aria-label="Measured Panda task sequence">
              {PANDA_STAGES.map((stage, index) => <div key={stage.name}
                role="listitem"
                className={'p37-task-step' +
                  (pandaTime >= stage.start ? ' is-started' : '') +
                  (pandaTime >= stage.end ? ' is-finished' : '')}
                aria-current={pandaTime >= stage.start && pandaTime < stage.end ? 'step' : undefined}>
                <span className="p37-step-number">{String(index+1).padStart(2,'0')}</span>
                <strong>{stage.name}</strong>
              </div>)}
              <div className="p37-task-clock">{pandaTime.toFixed(1)} / 18.2s</div>
            </div>}
            {pandaActive && build?.panda_physical_cube_stack && <div
              className="p37-scripted-evidence" aria-label="Panda source experiment evidence">
              <strong>Native task verified · deterministic motor reference</strong>
              <span>{build.panda_physical_cube_stack.frames} recorded 50 Hz controls ·
                {' '}{build.panda_physical_cube_stack.left_contact_frames} left-finger contact frames ·
                {' '}{build.panda_physical_cube_stack.right_contact_frames} right-finger contact frames</span>
              <small>Independent native MuJoCo replay passed. Browser playback is
                measured separately below. No P37 learned policy is claimed.</small>
            </div>}
            <div className="p37-task-progress">
              <progress aria-label="Measured task progress" max={1} value={result.progress}/>
              <div><strong>{result.measure}</strong><span>{result.goal}</span></div>
            </div>
            <p className="p37-task-boundary">{result.reached
              ? 'Measured condition reached in this physics sandbox. This is not a qualified autonomous-policy task success.'
              : 'Goal checks use simulated state. A robot can fall, miss the target, or fail to reach it.'}
            </p>
            {experiment.kind==='terrain' && experience==='simulation' && <div className="p37-task-execution">
              <button type="button" onClick={toggleReferenceTask}>
                {telemetry.scriptedTaskRunning ? 'Stop scripted attempt' : 'Run assisted terrain attempt'}
              </button>
              <span>External-force reference controller · no learned gait · up to 18 simulation seconds</span>
            </div>}
            {((experiment.kind==='cube-stack' && !pandaActive) || experiment.kind==='delivery') && <p className="p37-task-source-note">
              Physical objects and success checks are live. A qualified grasp/placement task policy
              is not attached; the motor replay does not automatically complete the task.
            </p>}
            <div className="p37-task-next">
              <span>Next research experiment: {experiment.nextTask}</span>
              <a href={experiment.upstreamUrl} target="_blank" rel="noreferrer">
                {experiment.upstream} ↗
              </a>
            </div>
          </section>}
          {experience!=='recorded' && <div className="viewport-controls">
            <div className="action-row">
              {pandaActive ? <button type="button"
                onClick={() => setPlayback('panda_scripted_stack')}>↻ Replay full task</button>
                : <button type="button" onClick={() => setPlayback(
                  motion === 'hold' ? lastMotion : 'hold'
                )}>{motion === 'hold' ? 'Play motion' : 'Hold motion'}</button>}
              <button type="button" onClick={() => {
                releaseSteer(); setTelemetry({status:'waiting'});
                setStageLoaded(false); setReload(x => x + 1);
              }}>↻ Reset simulation</button>
              <button type="button" aria-pressed={panel} onClick={() => {
                setPanel(x => !x); setStageLoaded(false);
              }}>{panel ? 'Hide physics controls' : 'Show physics controls'}</button>
            </div>
            <div className="p37-steer-panel" aria-label="User-controlled physical movement">
              <div className="p37-steer-heading">
                <strong>{isFixedArm ? 'Fixed-base robot' : 'Drive the robot'}</strong>
                <span>{isFixedArm ? 'Joint articulation only' : 'WASD / arrow keys · Q/E turn'}</span>
              </div>
              {isFixedArm ? <p className="p37-steer-help">
                This industrial arm cannot walk. Use the movement dataset controls to move its real joints.
              </p> : <>
                <div className="p37-steer-pad" role="group" aria-label="Steering direction controls">
                  {([
                    {key:'forward',label:'Forward',glyph:'↑'},
                    {key:'left',label:'Left',glyph:'←'},
                    {key:'back',label:'Backward',glyph:'↓'},
                    {key:'right',label:'Right',glyph:'→'},
                    {key:'turnLeft',label:'Turn left',glyph:'↶'},
                    {key:'turnRight',label:'Turn right',glyph:'↷'},
                  ] as {key:SteeringKey; label:string; glyph:string}[]).map(button =>
                    <button key={button.key} type="button" aria-label={button.label}
                      disabled={!canSteer}
                      onPointerDown={event=>{event.preventDefault();event.currentTarget.setPointerCapture(event.pointerId);sendSteer(button.key,true);}}
                      onPointerUp={()=>sendSteer(button.key,false)}
                      onPointerCancel={()=>sendSteer(button.key,false)}
                      onLostPointerCapture={()=>sendSteer(button.key,false)}>
                      {button.glyph}<small>{button.label}</small>
                    </button>)}
                  <button type="button" className="p37-stop" onClick={releaseSteer}>Stop</button>
                </div>
                <div className="p37-steering-telemetry" role="status" aria-live="polite">
                  <span>{telemetry.status==='fixed' ? 'Model has no floating base' :
                    telemetry.status==='waiting' ? 'Connecting steering…' :
                    telemetry.steering ? 'Physical steering active' : 'Ready for input'}</span>
                  <strong>{telemetry.distance===undefined?'—':telemetry.distance.toFixed(2)+' m'} traveled</strong>
                </div>
                <p className="p37-steer-help">Experimental assisted steering applies a bounded
                  external force to the real simulated body while its motion clip
                  moves the joints. Contacts and gravity remain physical.
                  This is not a qualified learned walking controller.</p>
              </>}
            </div>
            <div className="status-line" role="status">{pandaActive ?
              'Panda verified contact-based grasp / lift / release / stack · scripted reference, not learned P37' :
              p37Active ?
              'Experimental P37 inference plus user-assisted steering · walking not qualified' :
              'Physical motion replay with user-assisted steering · no learned walking claim'}</div>
          </div>}
        </div>
        <aside className="playground-panel p37-real-panel">
          <div className="side-panel">
            <div className="section-heading"><span>TASK CONTROLS</span><span>NATIVE MUJOCO</span></div>
            <label htmlFor="real-robot">Select a robot</label>
            <select id="real-robot" value={selected} onChange={e => {
              const robot = catalog.find(r => r.id === e.target.value);
              if (robot) selectRobot(robot);
            }}>
              {catalog.map(robot => <option value={robot.id} key={robot.id}>
                {robot.name} · {robot.kind}
              </option>)}
            </select>
            <p className="helper">Open the selected experiment above. Robot meshes,
              task objects and contacts run in the native MuJoCo physics engine.</p>
            <details className="p37-all-robots">
              <summary>Browse all ten robot bodies</summary>
              <div className="playground-scenes p37-scenes" role="group" aria-label="Choose robot category">
                <span className="playground-scenes-label">Filter</span>
                {CATEGORIES.map(item => <button key={item} type="button"
                  aria-pressed={category === item} onClick={() => setCategory(item)}>{item}</button>)}
              </div>
            <div className="robot-catalog" role="group" aria-label="Select real robot body">
              <div className="catalog-heading">AVAILABLE BODIES <span>{selection.length} SHOWN</span></div>
              <div className="catalog-choices">
                {selection.map(robot => <button type="button" key={robot.id}
                  className={selected === robot.id ? 'selected' : ''}
                  aria-pressed={selected === robot.id}
                  onClick={() => selectRobot(robot)}>
                  <strong>{robot.name}</strong><small>{robot.short}</small>
                </button>)}
              </div>
            </div>
            </details>
            <div className="rule"/>
            <div className="section-cap">Task execution and motor controls</div>
            <div className="p37-motion-controls" role="group" aria-label="Choose motion dataset">
              {selected === 'franka_panda' && <button type="button"
                className="p37-task-primary" aria-pressed={pandaActive}
                onClick={()=>setPlayback('panda_scripted_stack')}>
                {pandaActive ? '↻ Replay Panda stack' : '▶ Run physical Panda stack'}
              </button>}
              {p37Available && <button type="button" aria-pressed={p37Active}
                onClick={()=>setPlayback('p37_experimental')}>Experimental P37 G1</button>}
              <button type="button" aria-pressed={motion==='motion_cycle'}
                onClick={()=>setPlayback('motion_cycle')}>Movement cycle</button>
              <button type="button" aria-pressed={motion==='articulation'}
                onClick={()=>setPlayback('articulation')}>Motor articulation</button>
              <button type="button" aria-pressed={motion==='hold'}
                onClick={()=>setPlayback('hold')}>Hold pose</button>
            </div>
            <p className="helper">{pandaActive
              ? 'The scripted Panda run starts in native MuJoCo. Orbit the camera, inspect the cube, or replay the complete 18.2-second sequence.'
              : 'Use WASD or the on-screen controls on supported floating-base robots. Motion clips and assisted movement are not qualified learned walking policies.'}</p>
             <div className="rule"/>
            <div className="section-cap">Research boundary</div>
            <p className="evidence-copy">{current?.task ?? 'Select a robot'}. {current?.capability ?? ''}
              {' '}{pandaActive ? 'A validated deterministic Panda reference replays eight physical motor controls at 50Hz. Its grasp, lift, release and stable stack were verified in native MuJoCo and independent replay. This is scripted control, not a P37 learned policy.' :
              p37Active ? 'G1 receives genuine experimental ONNX inference and 29-joint commands at 50Hz.' :
              'The motion dataset supplies model-compatible joint or motor targets through MuJoCo physics. It is not a trained autonomous skill.'}</p>
            <div className="info-row"><span>Physics engine</span><strong>MuJoCo</strong></div>
            <div className="info-row"><span>3D geometry</span><strong>Manufacturer-derived</strong></div>
            <div className="info-row"><span>Controller</span><strong>{pandaActive ? 'Validated scripted Panda reference' : p37Active ? 'P37 recurrent PPO' : 'Dataset motor replay'}</strong></div>
            <div className="info-row"><span>Source</span><strong>{pandaActive ? 'Native verified grasp and stack trial' : p37Active ? 'Experimental P37 checkpoint' : 'MuJoCo model-derived motion'}</strong></div>
            <div className="info-row"><span>Learning qualification</span><strong>{pandaActive ? 'Scripted · physical task verified' : 'Unqualified'}</strong></div>
            {error && <p className="helper" role="alert">{error}</p>}
          </div>
        </aside>
      </section>
      <section className="policy-evidence" id="evidence" aria-label="Recorded P37 native policy evidence">
        <div className="policy-evidence-heading">
          <span className="overline">MEASURED / REPRODUCIBLE RESEARCH</span>
          <h2>What P37 has demonstrated.</h2>
          <p>The same experimental checkpoint was evaluated on G1 and Go2 in short
            native MuJoCo trials. These results do not establish walking, recovery,
            or successful cross-body task transfer.</p>
        </div>
        {evidence && g1Evidence && <div className="policy-facts">
          <div><span>Checkpoint SHA-256</span>
            <strong className="checkpoint-hash">{evidence.checkpoint_sha256.slice(0, 16)}…</strong></div>
          <div><span>G1 browser controller</span><strong>{
            build?.trained_p37_policy_attached ? 'Experimental ONNX attached' : 'Unavailable'
          }</strong></div>
          <div><span>G1 + Go2 native inference</span><strong>Same checkpoint</strong></div>
          <div><span>Walking qualification</span><strong>Not achieved</strong></div>
        </div>}
        {evidence && <div className="policy-evidence-grid">
          {(['unitree_g1', 'unitree_go2'] as const).map(id => <div className="policy-evidence-card" key={id}>
            <div className="policy-body-name">{id === 'unitree_g1' ? 'Unitree G1' : 'Unitree Go2'}</div>
            <p>{evidence.bodies[id].actuators} actuators · recorded native model experiment</p>
            <div className="policy-trial-list">{evidence.bodies[id].trials.map(t =>
              <div key={t.seed}><span>Seed {t.seed}</span>
                <strong>{t.commands_sent} actions / {t.sim_seconds.toFixed(1)}s</strong></div>)}
            </div>
          </div>)}
        </div>}
        <p className="policy-disclaimer">
          <strong>Evidence boundary:</strong> {evidence?.limitation ||
            'Qualification results are unavailable.'}
          {' '}The independent G1 walking smoke test recorded falls in
          {' '}{g1Evidence?.evaluation.seeds.filter(t => t.fallen).length ?? '—'} of
          {' '}{g1Evidence?.evaluation.seeds.length ?? '—'} trials.
          All ten robots have model-derived movement datasets controlling their
          physical actuators. Only G1 has an experimental learned P37 policy.
          Dataset playback on other models is not evidence of learned skill transfer.
        </p>
        {evidence && <a className="policy-source-link"
          href={evidence.provenance.workflow} target="_blank" rel="noreferrer">
          View experiment and checkpoint provenance ↗</a>}
      </section>
    </main>
    <footer><span>© 2026 ONTOS / P37 NEURO</span>
      <a href="https://github.com/OntosRobotics/P37-Neuro" target="_blank" rel="noreferrer">
        SOURCE / MODELS / EXPERIMENTS ↗</a></footer>
  </div>;
}
