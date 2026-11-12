import { useEffect, useMemo, useState } from 'react';

type Robot = {
  id: string; name: string; model: string; kind: string;
  short: string; task: string; capability: string;
};
type Catalog = { robots: Robot[] };
type BuildInfo = {
  trained_p37_policy_attached: boolean;
  qualified_cross_body_transfer: boolean;
  manufacturer_robots: string[];
  experimental_policy_robot?: string;
  p37_checkpoint_sha256?: string;
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

export function App() {
  const [catalog, setCatalog] = useState<Robot[]>([]);
  const [selected, setSelected] = useState('unitree_g1');
  const [category, setCategory] = useState('All');
  const [panel, setPanel] = useState(false);
  const [reload, setReload] = useState(0);
  const [stageLoaded, setStageLoaded] = useState(false);
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
    ]).then(([data, info, trials, evaluation]) => {
      if (!Array.isArray(data.robots) || data.robots.length !== 10
        || !data.robots.some(r => r.id === 'unitree_g1')
        || info.manufacturer_robots.length !== 10
        || trials.qualified_for_walking !== false
        || trials.qualified_for_cross_body_task_transfer !== false
        || evaluation.qualification !== 'unqualified') {
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
  const selection = useMemo(() => catalog.filter(robot =>
    category === 'All' || robot.kind === category), [catalog, category]);
  const p37Active = selected === 'unitree_g1'
    && build?.trained_p37_policy_attached === true
    && build.experimental_policy_robot === 'unitree_g1'
    && build.p37_checkpoint_sha256 === evidence?.checkpoint_sha256;
  const selectRobot = (robot: Robot) => {
    setSelected(robot.id);
    setStageLoaded(false);
    setReload(x => x + 1);
  };
  const url = import.meta.env.BASE_URL + 'simulator/?project=p37_robot_models&scene='
    + encodeURIComponent(selected) + '&panel=' + (panel ? '1' : '0');
  return <div className="app-shell p37-real">
    <header className="site-header">
      <a className="brand" href="./">ONTOS <span>/ P37 NEURO</span></a>
      <nav aria-label="P37 navigation">
        <a href="#simulator">Simulation</a>
        <a href="#evidence">Research evidence</a>
        <a href="https://github.com/OntosRobotics/P37-Neuro" target="_blank" rel="noreferrer">GitHub ↗</a>
      </nav>
      <span className="build-tag">LIVE EXPERIMENT / 01</span>
    </header>
    <main>
      <section className="title-row">
        <span className="overline">P37 / CROSS-EMBODIMENT ROBOTICS</span>
        <h1>One brain. Different bodies.</h1>
        <p className="intro">
          Explore ten real robot models in a live physics environment.
          Unitree G1 runs an experimental P37 policy in the browser when its
          verified model is available. Other robots run native MuJoCo physics
          without a learned controller.
        </p>
      </section>
      <section className="lab-grid" id="simulator" aria-label="Live manufacturer robot simulation">
        <div className="viewport">
          <div className="playground-scenes p37-scenes" role="group" aria-label="Choose robot category">
            <span className="playground-scenes-label">Explore</span>
            {CATEGORIES.map(item => <button key={item} type="button"
              aria-pressed={category === item} onClick={() => setCategory(item)}>{item}</button>)}
          </div>
          <div className="viewport-top">
            <div><span className="live-dot"/> NATIVE ROBOT PHYSICS
              <span className="muted"> / MuJoCo · WebAssembly</span></div>
            <div className="stage-tools-head">
              <span>{p37Active ? 'P37 RECURRENT ONNX / EXPERIMENTAL' :
                'MANUFACTURER MODEL / PASSIVE PHYSICS'}</span>
            </div>
          </div>
          <div className="canvas-wrap p37-scene">
            {catalog.length > 0 && current ? <iframe
              key={selected + '-' + reload + '-' + panel}
              title={current.name + ' — real MuJoCo robot'}
              className="menagerie-viewer"
              src={url}
              allow="fullscreen"
              loading="eager"
              onLoad={() => setStageLoaded(true)}/>
              : <div className="viewer-notice">
                {error ? 'Robot models unavailable: ' + error : 'Loading real robot models…'}
              </div>}
            {current && <div className="p37-stage-name">
              <small>ROBOT {String(catalog.indexOf(current) + 1).padStart(2, '0')} / {catalog.length}</small>
              <strong>{current.name}</strong>
              <span>{current.short}</span>
            </div>}
            <div className="camera-tip">DRAG TO ORBIT · SELECT A BODY TO INTERACT</div>
          </div>
          <div className="playground-embodiment p37-stage-actions">
            <span>Controller</span>
            <strong>{p37Active ? 'P37 learned policy · unqualified' : 'Native physics · no policy'}</strong>
            <span className="playground-disclaimer">{stageLoaded ?
              'Viewer loaded · inspect motion inside the live scene' : 'Loading native simulation…'}</span>
          </div>
          <div className="viewport-controls">
            <div className="action-row">
              <button type="button" onClick={() => {
                setStageLoaded(false); setReload(x => x + 1);
              }}>↻ Reset simulation</button>
              <button type="button" aria-pressed={panel} onClick={() => {
                setPanel(x => !x); setStageLoaded(false);
              }}>{panel ? 'Hide physics controls' : 'Show physics controls'}</button>
            </div>
            <div className="status-line" role="status">{p37Active ?
              'Experimental P37 inference · walking not qualified' :
              'Real robot model · manual physics interaction'}</div>
          </div>
        </div>
        <aside className="playground-panel p37-real-panel">
          <div className="side-panel">
            <div className="section-heading"><span>ROBOT LIBRARY</span><span>10 / VERIFIED MODELS</span></div>
            <label htmlFor="real-robot">Select a robot</label>
            <select id="real-robot" value={selected} onChange={e => {
              const robot = catalog.find(r => r.id === e.target.value);
              if (robot) selectRobot(robot);
            }}>
              {catalog.map(robot => <option value={robot.id} key={robot.id}>
                {robot.name} · {robot.kind}
              </option>)}
            </select>
            <p className="helper">Official MuJoCo Menagerie geometry, articulated joints,
              native body collisions and accurate proportions.</p>
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
            <div className="rule"/>
            <div className="section-cap">Selected experiment</div>
            <p className="evidence-copy">{current?.task ?? 'Select a robot'}. {current?.capability ?? ''}
              {' '}{p37Active ? 'G1 receives ONNX inference and joint commands at 50Hz.' :
              'This model has passive physics and user forces; it is not a trained autonomous task.'}</p>
            <div className="info-row"><span>Physics engine</span><strong>MuJoCo</strong></div>
            <div className="info-row"><span>3D geometry</span><strong>Manufacturer-derived</strong></div>
            <div className="info-row"><span>Policy</span><strong>{p37Active ? 'P37 recurrent PPO' : 'None'}</strong></div>
            <div className="info-row"><span>Learning qualification</span><strong>Unqualified</strong></div>
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
          Only the G1 scene has an experimental browser policy; other robot models
          are physical viewers, not policy-transfer demonstrations.
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
