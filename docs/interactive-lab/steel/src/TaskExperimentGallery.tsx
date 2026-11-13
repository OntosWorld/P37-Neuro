import { useMemo, useState } from 'react';
import { GALLERY_FILTERS, GALLERY_TASKS, type GalleryTask } from './taskGallery';

type Props = {
  activeId: string;
  onSelect: (task: GalleryTask) => void;
  baseUrl: string;
};

export function TaskGallery({ activeId, onSelect, baseUrl }: Props) {
  const [filter, setFilter] = useState<(typeof GALLERY_FILTERS)[number]>('All experiments');
  const tasks = useMemo(
    () => GALLERY_TASKS.filter(task => filter === 'All experiments' || task.category === filter),
    [filter]
  );
  return <section className="task-gallery" id="tasks" aria-label="Robot task experiment gallery">
    <div className="task-gallery-heading">
      <div className="task-gallery-label">
        <span className="gallery-kicker">ONTOS / P37-NEURO</span>
        <span className="gallery-index">TASK EXPERIMENTS <b>001—007</b></span>
      </div>
      <h1>Watch the robots<br/><em>do the work.</em></h1>
      <p>Choose an experiment. Watch a physical task unfold, take control where supported,
        and inspect what the simulator actually measured.</p>
    </div>
    <div className="task-gallery-toolbar">
      <div className="task-gallery-filters" role="group" aria-label="Filter robot task experiments">
        {GALLERY_FILTERS.map(option =>
          <button key={option} type="button"
            aria-pressed={filter === option} onClick={() => setFilter(option)}>
            {option}
          </button>
        )}
      </div>
      <span className="task-gallery-count">{String(tasks.length).padStart(2,'0')} EXPERIMENTS</span>
    </div>
    <div className="task-gallery-grid">
      {tasks.map((task, index) =>
        <button type="button" key={task.id} className={'task-gallery-card'+
          (index === 0 && filter === 'All experiments' ? ' task-gallery-featured' : '')+
          (activeId === task.id ? ' task-gallery-selected' : '')}
          aria-pressed={activeId === task.id}
          aria-label={task.action + ' — ' + task.title}
          onClick={() => onSelect(task)}>
          <span className="task-card-image">
            <img loading={index < 3 ? 'eager' : 'lazy'}
              src={baseUrl + 'task-previews/' + task.image}
              alt={task.route === 'recorded'
                ? 'MuJoCo Panda model reference, separate from the original recorded MimicGen data'
                : 'Native MuJoCo scene preview of ' + task.robotName}
              onError={event => {
                const image = event.currentTarget;
                if (image.src !== task.sourceImage) {
                  image.src = task.sourceImage;
                  image.alt = 'Upstream MuJoCo Menagerie robot model preview of ' + task.robotName;
                }
              }}
            />
            {task.id === 'panda-stack' && <video
              aria-hidden="true"
              className="task-card-video"
              autoPlay muted loop playsInline preload="metadata"
              poster={baseUrl + 'task-previews/panda-stack.jpg'}
              onError={event => { event.currentTarget.style.display = 'none'; }}>
              <source src={baseUrl + 'task-previews/panda-stack.mp4'} type="video/mp4"/>
            </video>}
            <span className="task-card-image-shade"/>
            <span className="task-card-top">
              <small>{task.kicker}</small>
              <small className="task-card-source">{task.route === 'recorded'
                ? 'MODEL PREVIEW / SOURCE DATA'
                : task.id === 'panda-stack'
                  ? 'ACTUAL SIMULATED TASK'
                  : 'MUJOCO / NATIVE MESH'}</small>
            </span>
            <span className="task-card-robot">{task.robotName}</span>
          </span>
          <span className="task-card-copy">
            <span className="task-card-type">{task.status}</span>
            <span className="task-card-title">{task.title}</span>
            <span className="task-card-description">{task.description}</span>
            <span className="task-card-bottom">
              <span>{task.action}<span aria-hidden="true"> ↗</span></span>
              <span className="task-card-round" aria-hidden="true">↗</span>
            </span>
          </span>
        </button>
      )}
    </div>
    <div className="task-gallery-footnote">
      <p><strong>Task status matters.</strong> The Panda stack and pick-place reference require native
        grasp, lift, release and placement controller. Navigation scenes use assisted
        physics; the Stretch workcell and G1 learned controller are still experimental.</p>
      <span>Manufacturer-derived robots · Native contact simulation · Source-linked evidence</span>
    </div>
  </section>;
}
