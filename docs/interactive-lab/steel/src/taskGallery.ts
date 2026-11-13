/**
 * Editorial task-first experiment catalog.
 *
 * Every card names the actual execution path. Thumbnails are captured from the
 * published MuJoCo Menagerie scene with the current task geometry; they do not
 * claim that a qualified P37 policy executed the task.
 */
export type TaskCategory = 'Manipulation' | 'Navigation' | 'Recordings' | 'Research';
export type TaskRoute = 'panda' | 'pick' | 'terrain' | 'workcell' | 'recorded' | 'p37';

export type GalleryTask = {
  id: string;
  title: string;
  kicker: string;
  description: string;
  robotId: string;
  robotName: string;
  category: TaskCategory;
  route: TaskRoute;
  status: string;
  source: string;
  image: string;
  sourceImage: string;
  action: string;
  evidence: string;
  limits: string;
};

const menagerie = 'https://raw.githubusercontent.com/google-deepmind/mujoco_menagerie/main/';

export const GALLERY_TASKS: GalleryTask[] = [
  {
    id: 'panda-pick-place',
    title: 'Pick and place a cube.',
    kicker: '01 / PHYSICAL MANIPULATION',
    description: 'Grasp a cube on the tabletop, carry it to a marked location, release it and verify it settles.',
    robotId: 'franka_panda', robotName: 'Franka Panda',
    category: 'Manipulation', route: 'pick',
    status: 'Build-gated physical task',
    source: 'MuJoCo Menagerie · native Panda',
    image: 'panda-stack.jpg',
    sourceImage: menagerie + 'franka_emika_panda/panda.png',
    action: 'Run physical pick-and-place',
    evidence: 'Separate cube/tabletop scene; contact and placement qualification is build-gated',
    limits: 'Deterministic reference controller. Learned manipulation remains unqualified.',
  },
  {
    id: 'panda-stack',
    title: 'Pick up. Move. Stack.',
    kicker: '02 / CONTACT MANIPULATION',
    description: 'Watch the Panda grasp a blue cube, lift it, carry it across the bench and release it onto another cube.',
    robotId: 'franka_panda', robotName: 'Franka Panda',
    category: 'Manipulation', route: 'panda',
    status: 'Verified scripted task',
    source: 'MuJoCo Menagerie · native Panda',
    image: 'panda-stack.jpg',
    sourceImage: menagerie + 'franka_emika_panda/panda.png',
    action: 'Watch the physical task',
    evidence: '18.2s · 910 motor commands · independent replay passed',
    limits: 'Deterministic reference controller. No trained P37 manipulation policy.',
  },
  {
    id: 'go2-terrain',
    title: 'Cross the obstacle course.',
    kicker: '02 / TERRAIN NAVIGATION',
    description: 'Guide Go2 across a curb, a raised step and an offset pylon. Contacts, inertia and falls remain in the physics engine.',
    robotId: 'unitree_go2', robotName: 'Unitree Go2',
    category: 'Navigation', route: 'terrain',
    status: 'Live assisted physics',
    source: 'MuJoCo Menagerie · Unitree Go2',
    image: 'go2-terrain.jpg',
    sourceImage: menagerie + 'unitree_go2/go2.png',
    action: 'Drive the terrain course',
    evidence: 'Colliding obstacles · live body position and height',
    limits: 'Assisted external-force motion, without a qualified learned gait.',
  },
  {
    id: 'anymal-terrain',
    title: 'Navigate uneven ground.',
    kicker: '03 / OBSTACLE TRAVERSAL',
    description: 'Explore the same physical terrain course using a different quadruped body. Watch how contacts affect the result.',
    robotId: 'anymal_c', robotName: 'ANYmal C',
    category: 'Navigation', route: 'terrain',
    status: 'Live assisted physics',
    source: 'MuJoCo Menagerie · ANYbotics ANYmal C',
    image: 'anymal-terrain.jpg',
    sourceImage: menagerie + 'anybotics_anymal_c/anymal_c.png',
    action: 'Explore ANYmal physics',
    evidence: 'Colliding obstacle course · measured position and height',
    limits: 'Assisted external-force experiment; no qualified terrain policy.',
  },
  {
    id: 'stretch-delivery',
    title: 'Move a parcel between stations.',
    kicker: '04 / DELIVERY WORKCELL',
    description: 'Inspect the source object and receiving station in Stretch’s physical workcell. The placement goal is measured live.',
    robotId: 'hello_robot_stretch', robotName: 'Hello Robot Stretch',
    category: 'Manipulation', route: 'workcell',
    status: 'Workcell · under test',
    source: 'MuJoCo Menagerie · Hello Robot Stretch',
    image: 'stretch-delivery.jpg',
    sourceImage: menagerie + 'hello_robot_stretch/stretch.png',
    action: 'Inspect the delivery workcell',
    evidence: 'Physical parcel and receiving station · goal-position checks',
    limits: 'Pickup and delivery controller not qualified; no completed task claim.',
  },
  {
    id: 'mimicgen-replay',
    title: 'Inspect a recorded robot task.',
    kicker: '05 / RECORDED TASK DATA',
    description: 'Explore source-attributed Panda manipulation episodes and their measured trajectory data.',
    robotId: 'franka_panda', robotName: 'Franka Panda',
    category: 'Recordings', route: 'recorded',
    status: 'Source-recorded episodes',
    source: 'MimicGen dataset · CC BY 4.0',
    image: 'panda-recorded.jpg',
    sourceImage: menagerie + 'franka_emika_panda/panda.png',
    action: 'Open recorded episodes',
    evidence: 'Source-attributed episode replay · original task data',
    limits: 'A recorded data viewer, not live physics or a cinematic task video.',
  },
  {
    id: 'g1-policy',
    title: 'Test a learned G1 controller.',
    kicker: '06 / LEARNED POLICY EXPERIMENT',
    description: 'Run the experimental recurrent ONNX controller on a real Unitree G1 model and inspect its limitations.',
    robotId: 'unitree_g1', robotName: 'Unitree G1',
    category: 'Research', route: 'p37',
    status: 'Experimental policy',
    source: 'P37 checkpoint · MuJoCo G1',
    image: 'g1-policy.jpg',
    sourceImage: menagerie + 'unitree_g1/g1.png',
    action: 'Inspect P37 experiment',
    evidence: 'Actual learned checkpoint inference in MuJoCo',
    limits: 'Unqualified walking, recovery and cross-embodiment task transfer.',
  },
];

export const GALLERY_FILTERS = ['All experiments', 'Manipulation', 'Navigation', 'Recordings', 'Research'] as const;
