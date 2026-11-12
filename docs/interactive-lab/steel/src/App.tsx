import { useEffect, useMemo, useRef, useState } from 'react';

type Body = { id:string; name:string; kind:string; short:string; task:string; model:string };
type Catalog = { robots: Body[] };
type Mode = 'p37' | 'passive';
type Evidence = {
  checkpoint_sha256:string;
  trained_on:string;
  qualified_for_walking:boolean;
  qualified_for_cross_body_task_transfer:boolean;
  same_checkpoint_used_for_all_bodies:boolean;
  bodies:Record<string,{actuators:number;trials:{seed:number;commands_sent:number;sim_seconds:number}[]}>;
  limitation:string;
  provenance:{workflow:string};
};
type G1Evidence = {
  evaluation:{seeds:{seed:number;fallen:boolean}[]};
};
type Build = {
  trained_p37_policy_attached:boolean;
  qualified_cross_body_transfer:boolean;
  active_policy_robots:string[];
  model_only_robots:string[];
  onnx_sha256:string;
};
const GROUPS = ['All','Humanoids','Quadrupeds','Manipulators','Mobile','Aerial'] as const;
const LEARNED_BODIES = new Set(['unitree_g1','unitree_go2']);
const BASE = import.meta.env.BASE_URL;
const P37_POLICY = 'p37_experimental_recurrent_ppo';

export function App() {
  const [robots,setRobots] = useState<Body[]>([]);
  const [selected,setSelected] = useState('unitree_g1');
  const [category,setCategory] = useState<string>('All');
  const [mode,setMode] = useState<Mode>('p37');
  const [loading,setLoading] = useState(true);
  const [frameError,setFrameError] = useState('');
  const [evidence,setEvidence] = useState<Evidence|null>(null);
  const [g1Evidence,setG1Evidence] = useState<G1Evidence|null>(null);
  const [build,setBuild] = useState<Build|null>(null);
  const [error,setError] = useState('');
  const frame=useRef<HTMLIFrameElement>(null);
  const canLearn = LEARNED_BODIES.has(selected) && build?.active_policy_robots.includes(selected) === true;
  const activeMode:Mode = canLearn && mode==='p37' ? 'p37' : 'passive';
  const selectedRobot=robots.find(robot=>robot.id===selected);
  const filtered=useMemo(()=>
    category==='All' ? robots : robots.filter(item=>item.kind===category),
    [category,robots]);
  const sceneId = activeMode === 'p37' ? selected + '_p37_experimental' : selected;
  const url = BASE + 'simulator/?project=p37_robot_models&scene=' +
    encodeURIComponent(sceneId) +
    (activeMode==='p37' ? '&policy='+encodeURIComponent(P37_POLICY):'') +
    '&panel=0';

  useEffect(()=>{
    const abort=new AbortController();
    Promise.all([
      fetch(BASE+'catalog.json',{signal:abort.signal}).then(r=>{if(!r.ok)throw Error('Robot catalog missing');return r.json() as Promise<Catalog>}),
      fetch(BASE+'build-info.json',{signal:abort.signal}).then(r=>{if(!r.ok)throw Error('Build contract missing');return r.json() as Promise<Build>}),
      fetch(BASE+'p37-cross-body-evidence.json',{signal:abort.signal}).then(r=>{if(!r.ok)throw Error('Model evidence missing');return r.json() as Promise<Evidence>}),
      fetch(BASE+'p37-evidence.json',{signal:abort.signal}).then(r=>{if(!r.ok)throw Error('G1 evidence missing');return r.json() as Promise<G1Evidence>}),
    ]).then(([catalog,metadata,cross,g1])=>{
      if(catalog.robots.length!==10 || new Set(catalog.robots.map(r=>r.id)).size!==10)
        throw Error('Real-robot catalog mismatch');
      if(metadata.trained_p37_policy_attached!==true ||
         metadata.qualified_cross_body_transfer!==false ||
         !['unitree_g1','unitree_go2'].every(id=>metadata.active_policy_robots?.includes(id)))
        throw Error('P37 browser policy bundle missing or not verified');
      if(cross.qualified_for_walking!==false ||
         cross.qualified_for_cross_body_task_transfer!==false ||
         cross.same_checkpoint_used_for_all_bodies!==true)
        throw Error('Published policy data does not have an honest qualification boundary');
      setRobots(catalog.robots);
      setBuild(metadata);
      setEvidence(cross);
      setG1Evidence(g1);
    }).catch(e=>{if(!abort.signal.aborted)setError(String(e))});
    return ()=>abort.abort();
  },[]);

  useEffect(()=>{
    setLoading(true);
    setFrameError('');
  },[url]);

  useEffect(()=>{
    if(!selectedRobot)return;
    let gone=false;
    // Only declare scene ready after the embedded real MuJoCo runtime reports
    // it is ready. An iframe load event alone is not a physics qualification.
    const tick=()=>{
      if(gone)return;
      try {
        const win=frame.current?.contentWindow as
          (Window & {__mjswanReady?:boolean})|null;
        if(win?.__mjswanReady===true) {
          setLoading(false);
          return;
        }
      } catch { /* Same-origin assets are required; wait for runtime. */ }
    };
    const id=window.setInterval(tick,350);
    tick();
    return ()=>{gone=true;window.clearInterval(id)};
  },[url,selectedRobot]);

  const choose=(id:string)=>{
    if(!robots.some(item=>item.id===id))return;
    setSelected(id);
    // Each body gets its own explicit controller qualification; never imply
    // that an untrained humanoid or manipulator is using the P37 checkpoint.
    setMode(LEARNED_BODIES.has(id)?'p37':'passive');
  };
  const fallen=g1Evidence?.evaluation.seeds.filter(t=>t.fallen).length;
  return <div className="page">
    <header className="topbar">
      <a href={BASE} className="identity">ONTOS <span>/ P37 NEURO</span></a>
      <nav aria-label="Primary navigation">
        <a href="#robots">Robots</a>
        <a href="#simulation">Simulation</a>
        <a href="#evidence">Research</a>
        <a href="https://github.com/OntosRobotics/P37-Neuro" target="_blank" rel="noreferrer">GitHub ↗</a>
      </nav>
      <div className="topbar-label">EXPERIMENTAL PHYSICAL AI</div>
    </header>
    <main>
      <section className="intro">
        <div className="eyebrow">P37 NEURO / LIVE ROBOT PHYSICS</div>
        <h1>One intelligence. Different robot bodies.</h1>
        <p>Explore real manufacturer-derived robots in MuJoCo. Run the
          experimental P37 recurrent model on G1 and Go2, inspect the physics,
          and compare it with the same robot without the policy.</p>
        <div className="intro-footnote">Experimental checkpoint · Browser inference ·
          Walking and cross-body task transfer remain unqualified</div>
      </section>
      <section className="showcase" id="simulation" aria-label="Real robot simulation">
        <div className="stage">
          <div className="stage-head">
            <div className="stage-name"><span className="live-indicator"/>
              {selectedRobot?.name ?? 'Loading robot'}
              <span className="stage-tech"> / MuJoCo · WebAssembly</span>
            </div>
            <span className="stage-label">{activeMode==='p37'?'P37 ONNX CONTROLLER':'MODEL PHYSICS ONLY'}</span>
          </div>
          <div className="stage-body">
            {selectedRobot && <iframe key={url} ref={frame} className="real-robot-frame"
              src={url} title={selectedRobot.name+' real MuJoCo physical scene'}
              allow="fullscreen" loading="eager"
              onError={()=>{setFrameError('MuJoCo scene could not initialize');setLoading(false)}}
            />}
            {(!selectedRobot||loading||frameError) &&
              <div className="stage-loading" role="status">
                <div className="stage-loader"/>
                <strong>{frameError||(!selectedRobot?'Loading robot catalog':'Preparing physical robot model')}</strong>
                <span>{error||'Full manufacturer geometry · MuJoCo rigid-body contacts'}</span>
              </div>}
            <div className="stage-footlabel">DRAG TO ORBIT · PUSH A PHYSICAL BODY · LIVE SIMULATION</div>
          </div>
          <div className="stage-controls">
            <div className="mode-controls" role="group" aria-label="Robot controller mode">
              <button type="button" className={activeMode==='p37'?'chosen':''}
                disabled={!canLearn} aria-pressed={activeMode==='p37'}
                onClick={()=>setMode('p37')}>Run P37 experimental</button>
              <button type="button" className={activeMode==='passive'?'chosen':''}
                aria-pressed={activeMode==='passive'}
                onClick={()=>setMode('passive')}>Model only</button>
              <button type="button" onClick={()=>{
                // Real reset: remount the scene rather than fake a visual motion.
                const current=frame.current;
                if(current){setLoading(true);current.src=url;}
              }}>Reset simulation</button>
            </div>
            <span className="mode-note">{activeMode==='p37'
              ? 'Real ONNX inference sends physical actuator commands. This policy can fall or fail.'
              : 'The robot uses passive physics. No P37 policy is controlling it.'}</span>
          </div>
        </div>
        <aside className="robot-sidebar" id="robots">
          <div className="side-heading"><strong>Robot library</strong><span>10 PHYSICAL MODELS</span></div>
          <div className="filters" role="group" aria-label="Robot categories">
            {GROUPS.map(group=><button type="button" key={group}
              aria-pressed={category===group} className={category===group?'active':''}
              onClick={()=>setCategory(group)}>{group}</button>)}
          </div>
          <div className="robot-options" role="group" aria-label="Choose manufacturer robot">
            {filtered.map(robot=><button type="button" key={robot.id}
              className={'robot-option '+(selected===robot.id?'selected':'')}
              aria-pressed={selected===robot.id} onClick={()=>choose(robot.id)}>
              <span className="robot-info"><strong>{robot.name}</strong>
                <small>{robot.short}</small></span>
              <span className="robot-option-tag">{LEARNED_BODIES.has(robot.id)?'P37 / ONNX':'PHYSICS'}</span>
            </button>)}
          </div>
          <div className="robot-identity">
            <span>ACTIVE EMBODIMENT</span>
            <strong>{selectedRobot?.name??'—'}</strong>
            <p>{selectedRobot?.task??'—'}</p>
            <dl><div><dt>Robot source</dt><dd>MuJoCo Menagerie</dd></div>
              <div><dt>Controller</dt><dd>{activeMode==='p37'?'P37 recurrent PPO':'None'}</dd></div>
              <div><dt>Qualification</dt><dd>Experimental</dd></div>
            </dl>
          </div>
        </aside>
      </section>
      {error&&<p className="load-error" role="alert">{error}</p>}
      <section className="evidence" id="evidence">
        <div className="evidence-head">
          <span className="eyebrow">P37 / MEASURED EXPERIMENTS</span>
          <h2>What the model has demonstrated.</h2>
          <p>The same experimental P37 checkpoint was used on G1 and Go2 in
            short native MuJoCo tests. The live viewer uses that ONNX model,
            with observation inputs and actuator mappings provided by our
            browser adapter. This is an early research baseline.</p>
        </div>
        <div className="metrics">
          <div><span>Experiment</span><strong>Recurrent PPO</strong></div>
          <div><span>Physics bodies</span><strong>G1 and Go2</strong></div>
          <div><span>Control timestep</span><strong>20 ms</strong></div>
          <div><span>Checkpoint</span><strong className="hash">
            {evidence?.checkpoint_sha256.slice(0,16)??'—'}…</strong></div>
        </div>
        <div className="evidence-grid">
          {(['unitree_g1','unitree_go2'] as const).map(id=>{
            const body=evidence?.bodies[id];
            return <article key={id}>
              <div className="evidence-item-name">{id==='unitree_g1'?'Unitree G1':'Unitree Go2'}</div>
              <p>{body ? body.actuators+' actuated joints' : 'Loading measured trials'}</p>
              {body?.trials.map(t=><div className="trial" key={t.seed}>
                <span>Seed {t.seed}</span><strong>{t.commands_sent} commands · {t.sim_seconds.toFixed(1)} s</strong>
              </div>)}
            </article>;
          })}
        </div>
        <p className="evidence-boundary">
          <strong>Research limitation.</strong> {evidence?.limitation??'Loading qualification metadata.'}
          {fallen!==undefined?' The separate G1 locomotion smoke test fell in '+fallen+
            ' of '+g1Evidence?.evaluation.seeds.length+' trials.':''}
          {' '}The browser controller is experimental; these results do not demonstrate
          reliable walking, disturbance recovery, or successful task transfer.
        </p>
        <a className="research-link" href={evidence?.provenance.workflow ??
          'https://github.com/OntosRobotics/P37-Neuro'}
          target="_blank" rel="noreferrer">View measured experiment and source ↗</a>
      </section>
    </main>
    <footer><span>© 2026 ONTOS WORLD / P37 NEURO</span>
      <span>MODEL PROVENANCE · PHYSICS FIRST · MEASURABLE RESULTS</span></footer>
  </div>;
}
