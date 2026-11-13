import { useMemo, useState } from 'react';
import {
  GALLERY_CATEGORIES, GALLERY_TASKS, type GalleryCategory, type GalleryTask,
} from './taskGallery';

type Props = {
  onOpen: (task: GalleryTask) => void;
  ready: boolean;
};

function TaskPoster({ task, priority = false }: { task: GalleryTask; priority?: boolean }) {
  return <img
    className="task-poster"
    src={import.meta.env.BASE_URL + 'task-posters/' + task.robotId + '.webp'}
    alt={task.robotName + ' manufacturer-derived MuJoCo model in its physical simulation scene'}
    loading={priority ? 'eager' : 'lazy'}
    decoding="async"
    draggable={false}
  />;
}

export function TaskGallery({ onOpen, ready }: Props) {
  const [category, setCategory] = useState<GalleryCategory>('All tasks');
  const featured = GALLERY_TASKS[0];
  const showFeatured = category === 'All tasks' || category === 'Manipulation';
  const visible = useMemo(() => GALLERY_TASKS.slice(1).filter(task =>
    category === 'All tasks' || task.category === category), [category]);

  return <section className="task-gallery" id="gallery" aria-label="Task-first simulation gallery">
    <div className="task-gallery-heading">
      <div className="gallery-eyebrow"><span className="gallery-active-dot"/> EXPERIMENT LIBRARY
        <span className="gallery-eyebrow-rule"/> MUJOCO / LIVE IN BROWSER</div>
      <div className="gallery-heading-grid">
        <h1>Robots at work.<span> Explore the simulations.</span></h1>
        <div className="gallery-heading-aside">
          <span>10 MANUFACTURER-DERIVED ROBOTS</span>
          <p>Choose a task, open its real 3D environment, and inspect what the robot
            actually does. Each experiment separates measured results from unqualified research.</p>
        </div>
      </div>
    </div>

    {showFeatured && <article className="gallery-feature" aria-label="Featured verified physical task">
      <button className="gallery-feature-stage" type="button"
        onClick={() => onOpen(featured)}
        aria-label="Open Franka Panda physical cube stacking simulation">
        <TaskPoster task={featured} priority />
        <span className="gallery-stage-corner">01 / 10 <span>MANIPULATION</span></span>
        <span className="gallery-stage-play" aria-hidden="true"><span>▶</span></span>
        <span className="gallery-stage-source">REAL MUJOCO GEOMETRY <span> / </span> PHYSICAL OBJECT CONTACTS</span>
      </button>
      <div className="gallery-feature-copy">
        <div className="gallery-feature-top"><span>FEATURED EXPERIMENT</span><span>01 / 10</span></div>
        <div className="gallery-feature-main">
          <div className="gallery-feature-robot">FRANKA PANDA <span> / 7-AXIS ROBOT ARM</span></div>
          <h2>Grasp. Lift.<br/>Carry. Stack.</h2>
          <p>Watch Panda pick up a real simulated cube and stack it on another. Finger
            contact, lift, release and final stability are checked in MuJoCo.</p>
          <div className="gallery-feature-facts" aria-label="Measured source experiment evidence">
            <div><strong>18.2 s</strong><span>source trial</span></div>
            <div><strong>50 Hz</strong><span>motor control</span></div>
            <div><strong>Passed</strong><span>native replay</span></div>
          </div>
        </div>
        <div className="gallery-feature-bottom">
          <div className="gallery-claim">
            <span className="gallery-claim-dot"/>
            Verified physical task · scripted control
          </div>
          <button type="button" className="gallery-main-action"
            onClick={() => onOpen(featured)}>
            Watch the simulation <span aria-hidden="true">↗</span>
          </button>
        </div>
      </div>
    </article>}

    <div className="gallery-collection-heading">
      <div>
        <span className="gallery-section-index">THE EXPERIMENTS / 01—10</span>
        <h2>Choose a task.</h2>
      </div>
      <span className="gallery-count">10 physical robot models · one task per scene</span>
    </div>
    <div className="gallery-filter" role="group" aria-label="Filter simulation tasks">
      {GALLERY_CATEGORIES.map(option => <button type="button"
        key={option} aria-pressed={category===option}
        onClick={()=>setCategory(option)}>{option}</button>)}
    </div>
    <div className="gallery-task-grid" aria-live="polite">
      {visible.map(task => <button type="button" className="gallery-task-card"
        key={task.robotId} onClick={() => onOpen(task)}
        aria-label={'Open task: ' + task.title + ' — ' + task.robotName}>
        <span className="gallery-task-visual">
          <TaskPoster task={task}/>
          <span className="gallery-task-visual-number">{task.number} / 10</span>
          <span className="gallery-task-visual-arrow" aria-hidden="true">↗</span>
        </span>
        <span className="gallery-task-info">
          <span className="gallery-task-topline"><span>{task.robotName}</span>
            <span>{task.category.toUpperCase()}</span></span>
          <strong>{task.title}</strong>
          <span className="gallery-task-summary">{task.overview}</span>
          <span className="gallery-task-foot"><span>{task.label}</span>
            <span aria-hidden="true">OPEN ↗</span></span>
        </span>
      </button>)}
    </div>
    <div className="gallery-evidence-note">
      <span>RESEARCH DISCLOSURE</span>
      <p>The Panda stacking experiment is a contact-verified scripted motor sequence.
        Terrain examples use external-force assistance. Other scenes are exploratory
        physics experiments, and G1 uses an experimental, unqualified P37 checkpoint.
        None of these demonstrates qualified autonomous task transfer across ten robots.</p>
    </div>
    {!ready && <div className="gallery-loading" role="status">
      Loading manufacturer-derived 3D scenes and experiment evidence…
    </div>}
  </section>;
}
