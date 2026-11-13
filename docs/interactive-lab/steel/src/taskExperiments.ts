/**
 * P37 task-experiment definitions for the ten published manufacturer bodies.
 * Measured checkpoints in live MuJoCo are NOT demonstrations of autonomous
 * learned task execution. External benchmark references are integration leads,
 * not automatically compatible replay datasets.
 */
export type TaskKind = 'checkpoint' | 'joint-excursion' | 'altitude';
export type TaskExperiment = {
  id: string;
  robotId: string;
  title: string;
  objective: string;
  kind: TaskKind;
  target: number;
  tolerance?: number;
  minBodyHeight?: number;
  upstream: string;
  upstreamUrl: string;
  nextTask: string;
};
export type TaskTelemetry = {
  status: string;
  relativeX?: number;
  relativeY?: number;
  relativeZ?: number;
  z?: number;
  jointDelta?: number;
  jointName?: string;
};

export const TASK_EXPERIMENTS: Record<string, TaskExperiment> = {
  unitree_g1: {
    id:'g1-checkpoint', robotId:'unitree_g1', title:'Move to the inspection point',
    objective:'Steer G1 toward the marked checkpoint while observing its upright state.',
    kind:'checkpoint', target:1.0, tolerance:0.35, minBodyHeight:0.55,
    upstream:'MuJoCo Playground · G1 velocity tracking',
    upstreamUrl:'https://playground.mujoco.org/',
    nextTask:'Qualified G1 locomotion and fall recovery with policy observations',
  },
  unitree_h1: {
    id:'h1-checkpoint', robotId:'unitree_h1', title:'Reach a warehouse checkpoint',
    objective:'Move the simulated H1 body to a floor waypoint and monitor its base height.',
    kind:'checkpoint', target:1.0, tolerance:0.4, minBodyHeight:0.65,
    upstream:'MuJoCo Playground · humanoid locomotion',
    upstreamUrl:'https://playground.mujoco.org/',
    nextTask:'Whole-body motion tracking and timed waypoint navigation',
  },
  booster_t1: {
    id:'t1-checkpoint', robotId:'booster_t1', title:'Complete a short transit',
    objective:'Steer the T1 body to the marked station, with balance visible in physics.',
    kind:'checkpoint', target:0.9, tolerance:0.4, minBodyHeight:0.45,
    upstream:'MuJoCo Playground · Booster locomotion and recovery',
    upstreamUrl:'https://playground.mujoco.org/rss2025/demo/',
    nextTask:'Test a licensed Booster T1 recovery checkpoint and control policy',
  },
  unitree_go2: {
    id:'go2-patrol', robotId:'unitree_go2', title:'Patrol to a waypoint',
    objective:'Drive the Go2 through real contact dynamics to the inspection checkpoint.',
    kind:'checkpoint', target:1.1, tolerance:0.35, minBodyHeight:0.16,
    upstream:'ManiSkill · UnitreeGo2-Reach task',
    upstreamUrl:'https://maniskill.readthedocs.io/en/latest/tasks/quadruped/',
    nextTask:'Closed-loop gait control and obstacle-course evaluation',
  },
  boston_dynamics_spot: {
    id:'spot-inspection', robotId:'boston_dynamics_spot', title:'Approach an inspection zone',
    objective:'Steer Spot into an inspection region and track physical displacement.',
    kind:'checkpoint', target:1.2, tolerance:0.38, minBodyHeight:0.24,
    upstream:'MuJoCo Playground · quadruped locomotion environments',
    upstreamUrl:'https://playground.mujoco.org/',
    nextTask:'Multi-waypoint inspection with obstacle contact and recovery',
  },
  anymal_c: {
    id:'anymal-survey', robotId:'anymal_c', title:'Reach the terrain survey point',
    objective:'Steer ANYmal C to a marked floor waypoint in the live rigid-body scene.',
    kind:'checkpoint', target:1.0, tolerance:0.35, minBodyHeight:0.18,
    upstream:'ManiSkill · AnymalC-Reach',
    upstreamUrl:'https://maniskill.readthedocs.io/en/latest/tasks/quadruped/',
    nextTask:'AnymalC-Reach task port and rough-ground stability benchmark',
  },
  franka_panda: {
    id:'panda-joint', robotId:'franka_panda', title:'Move a real arm joint to a target',
    objective:'Inspect the Panda articulated motion until a measured hinge has moved 0.15 rad.',
    kind:'joint-excursion', target:0.15,
    upstream:'ManiSkill · PickCube and StackCube experts',
    upstreamUrl:'https://maniskill.readthedocs.io/en/latest/user_guide/demos/scripts.html',
    nextTask:'Source-verified cube pickup and stacking with object contact and success predicates',
  },
  universal_robots_ur5e: {
    id:'ur5e-joint', robotId:'universal_robots_ur5e', title:'Precision joint positioning',
    objective:'Inspect UR5e motor control until a physical hinge moves 0.15 rad.',
    kind:'joint-excursion', target:0.15,
    upstream:'DexSuite · UR5e manipulation environments',
    upstreamUrl:'https://dexsuiteorg.github.io/',
    nextTask:'Task-space reach, assembly insertion and tool interaction',
  },
  hello_robot_stretch: {
    id:'stretch-delivery', robotId:'hello_robot_stretch', title:'Reach a delivery station',
    objective:'Move Stretch to a marked station. The arm motion is separate from payload handling.',
    kind:'checkpoint', target:0.8, tolerance:0.35, minBodyHeight:0.12,
    upstream:'RoboCasa365 · mobile manipulation scenes',
    upstreamUrl:'https://robocasa.ai/',
    nextTask:'Pickup, navigate and place using a payload and gripper contact predicate',
  },
  crazyflie_2: {
    id:'crazyflie-climb', robotId:'crazyflie_2', title:'Climb to a flight checkpoint',
    objective:'Measure actual simulated altitude above the initial position.',
    kind:'altitude', target:0.25,
    upstream:'MuJoCo Menagerie · Crazyflie motor and flight model',
    upstreamUrl:'https://github.com/google-deepmind/mujoco_menagerie',
    nextTask:'Motor-policy waypoint flight and attitude-stabilized gate traversal',
  },
};

export function taskProgress(task: TaskExperiment, t: TaskTelemetry) {
  const bounded = (n: number) => Math.max(0, Math.min(1, n));
  if (task.kind === 'joint-excursion') {
    const movement = t.jointDelta ?? 0;
    return {
      progress: bounded(movement / task.target),
      reached: t.jointDelta !== undefined && movement >= task.target,
      measure: t.jointDelta === undefined ? '—' : movement.toFixed(3) + ' rad',
      goal: task.target.toFixed(2) + ' rad joint excursion',
    };
  }
  if (task.kind === 'altitude') {
    const climb = t.relativeZ ?? 0;
    return {
      progress: bounded(climb / task.target),
      reached: t.relativeZ !== undefined && climb >= task.target,
      measure: t.relativeZ === undefined ? '—' : climb.toFixed(2) + ' m',
      goal: '+' + task.target.toFixed(2) + ' m altitude',
    };
  }
  const x = t.relativeX ?? 0;
  const y = t.relativeY ?? 0;
  const remaining = Math.hypot(task.target - x, y);
  const upright = task.minBodyHeight === undefined || (t.z !== undefined && t.z >= task.minBodyHeight);
  return {
    progress: bounded(1 - remaining / task.target),
    reached: t.relativeX !== undefined && t.relativeY !== undefined
      && remaining <= (task.tolerance ?? 0.3) && upright,
    measure: t.relativeX === undefined || t.relativeY === undefined ? '—' :
      remaining.toFixed(2) + ' m from goal',
    goal: 'Checkpoint at x = ' + task.target.toFixed(1) + ' m',
  };
}
