/** Task-first public catalog. Every preview is rendered from its actual
 * manufacturer-derived MuJoCo model; capability claims stay tied to evidence.
 * A task being available to explore does NOT imply that a policy can complete it.
 */
export type GalleryCategory = 'All tasks'|'Manipulation'|'Navigation'|'Humanoids'|'Aerial';
export type GalleryClaim = 'validated'|'assisted'|'experimental'|'physics';

export type GalleryTask = {
  robotId: string;
  number: string;
  category: Exclude<GalleryCategory,'All tasks'>;
  title: string;
  robotName: string;
  overview: string;
  label: string;
  provenance: string;
  claim: GalleryClaim;
  action: string;
};

export const GALLERY_CATEGORIES: GalleryCategory[] = [
  'All tasks', 'Manipulation', 'Navigation', 'Humanoids', 'Aerial',
];

export const GALLERY_TASKS: GalleryTask[] = [
  {
    robotId:'franka_panda', number:'01', category:'Manipulation',
    title:'Stack two physical cubes',
    robotName:'Franka Panda',
    overview:'Watch the arm grasp, lift, carry and release a cube onto another. The stack is checked against native MuJoCo contacts and object state.',
    label:'Contact-verified scripted trial', provenance:'Deterministic IK · motor control · 50 Hz',
    claim:'validated', action:'Watch cube stacking',
  },
  {
    robotId:'unitree_go2', number:'02', category:'Navigation',
    title:'Cross an obstacle course',
    robotName:'Unitree Go2',
    overview:'Explore a colliding curb, raised step and pylon. Run an assisted physics attempt or steer the simulated robot yourself.',
    label:'Assisted physics · outcome unqualified', provenance:'External-force assistance · real contacts',
    claim:'assisted', action:'Explore obstacle course',
  },
  {
    robotId:'anymal_c', number:'03', category:'Navigation',
    title:'Traverse uneven terrain',
    robotName:'ANYmal C',
    overview:'Inspect body stability and obstacle contact on real colliding terrain. The available reference is force-assisted, not a qualified walking gait.',
    label:'Assisted physics · outcome unqualified', provenance:'MuJoCo Menagerie · physical terrain',
    claim:'assisted', action:'Explore terrain',
  },
  {
    robotId:'hello_robot_stretch', number:'04', category:'Manipulation',
    title:'Move a parcel to the station',
    robotName:'Hello Robot Stretch',
    overview:'A movable source parcel and receiving platform are present in the scene. Explore the physical workspace; a verified pick-and-deliver controller is still pending.',
    label:'Task scene · controller pending', provenance:'Free-body object · receiving table',
    claim:'physics', action:'Explore delivery scene',
  },
  {
    robotId:'unitree_g1', number:'05', category:'Humanoids',
    title:'Reach an inspection point',
    robotName:'Unitree G1',
    overview:'Inspect the G1 humanoid in a live physics sandbox and switch to the real experimental P37 ONNX controller. Walking has not been qualified.',
    label:'Experimental P37 · not qualified', provenance:'P37 recurrent ONNX · manufacturer model',
    claim:'experimental', action:'Open G1 experiment',
  },
  {
    robotId:'boston_dynamics_spot', number:'06', category:'Navigation',
    title:'Approach an inspection zone',
    robotName:'Boston Dynamics Spot',
    overview:'Steer the manufacturer-derived quadruped toward a marked inspection point and measure displacement. This is an assisted test.',
    label:'Assisted physics · no trained gait', provenance:'External forces · rigid-body contacts',
    claim:'physics', action:'Explore inspection',
  },
  {
    robotId:'universal_robots_ur5e', number:'07', category:'Manipulation',
    title:'Precision arm positioning',
    robotName:'Universal Robots UR5e',
    overview:'Run native joint motion and inspect a measured joint excursion. A complete assembly or insertion policy is not attached.',
    label:'Joint-motion experiment', provenance:'Source robot actuators · angle telemetry',
    claim:'physics', action:'Explore arm control',
  },
  {
    robotId:'unitree_h1', number:'08', category:'Humanoids',
    title:'Warehouse transit checkpoint',
    robotName:'Unitree H1',
    overview:'Study motor motion, body height and movement through a marked zone. Successful independent locomotion is not established.',
    label:'Movement research · unqualified', provenance:'Native articulated H1 model',
    claim:'physics', action:'Explore H1 motion',
  },
  {
    robotId:'booster_t1', number:'09', category:'Humanoids',
    title:'Short-range motion trial',
    robotName:'Booster T1',
    overview:'Inspect articulated body motion in live contact physics and a short waypoint test. No trained balance controller is attached.',
    label:'Movement research · unqualified', provenance:'Native articulated T1 model',
    claim:'physics', action:'Explore T1 motion',
  },
  {
    robotId:'crazyflie_2', number:'10', category:'Aerial',
    title:'Measure a flight checkpoint',
    robotName:'Crazyflie 2',
    overview:'Inspect source motor actuation, native dynamics and altitude measurements for a micro aerial robot. Controlled flight is not qualified.',
    label:'Flight dynamics · unqualified', provenance:'Native quadrotor motor model',
    claim:'physics', action:'Explore flight physics',
  },
];

export function getGalleryTask(robotId: string): GalleryTask {
  return GALLERY_TASKS.find(item=>item.robotId===robotId) ?? GALLERY_TASKS[0];
}
