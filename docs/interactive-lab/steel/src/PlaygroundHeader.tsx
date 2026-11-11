export function OntosMark({ size=27 }: {size?:number}) {
  return <svg width={size} height={size} className="pg-mark" viewBox="0 0 32 32"
    fill="none" aria-hidden="true">
    <circle cx="15.5" cy="16.5" r="9.1" stroke="currentColor" strokeWidth="2"/>
    <circle cx="22" cy="10" r="2.15" fill="currentColor"/>
  </svg>;
}
export function PlaygroundHeader({onScenes}: {onScenes:()=>void}) {
  return <header className="pg-header">
    <a href="../../" className="pg-brand" aria-label="Ontos P37 Brain Lab">
      <OntosMark size={26}/><b>ONTOS</b><span className="pg-slash">/</span><span>P37 Playground</span>
    </a>
    <nav className="pg-links" aria-label="P37 navigation">
      <a href="../../">Robots</a>
      <a href="../../demos/">Simulations</a>
      <a href="../compare/?sample=mimicgen">Recorded data</a>
      <a href="../">Architecture</a>
      <a href="../sim/">Kinematics</a>
    </nav>
    <div className="pg-header-actions">
      <span className="pg-status"><i/> Experimental physics</span>
      <button onClick={onScenes} className="pg-menu-button" type="button">Scenes <span>▦</span></button>
    </div>
  </header>;
}