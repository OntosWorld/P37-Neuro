import { useEffect, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import {
  BoxCollider, CylinderCollider, Ground, RigidBody,
  SphereCollider, URDF, MJCF, useBeforeStep, useSimStats, useWorld,
  type RigidBodyHandle, type RobotHandle, type SceneHandle, type SimStatsSample,
} from '@skild-ai/steel-webgpu/react';
import type { Vec3 } from '@skild-ai/steel-webgpu';
import { Group } from 'three';
import { IndustrialSet, ProductDetail } from './IndustrialSet';
import { SourceTrajectory, type SourceFrame } from './SourceTrajectory';

export type Preset = 'workcell' | 'packing' | 'inspection';
export type RobotType = 'compact' | 'extended' | 'panda';
export type ObjectType = 'parcel' | 'canister' | 'ball' | 'bin';
export type LooseItem = { id: number; type: ObjectType; position: Vec3 };
export type ItemMotionSample = { id: number; position: Vec3; at: number };
export type GripStateSample = { left: number; right: number; time: number };
export const PRESETS: { id: Preset; label: string; detail: string }[] = [
  { id: 'workcell', label: 'Robotics workcell', detail: 'Table, chair, reference arm and loose objects' },
  { id: 'packing', label: 'Packing station', detail: 'Physical parcels, bins and contact' },
  { id: 'inspection', label: 'Inspection bench', detail: 'Metal finish, loose test objects' },
];
let nextId = 100;
export function nextItemId(): number { return nextId++; }
export function initialItems(preset: Preset): LooseItem[] {
  const lists: Record<Preset, { type: ObjectType; position: Vec3 }[]> = {
    workcell: [
      { type: 'parcel', position: [.23, -.15, 1.05] },
      { type: 'ball', position: [.55, .20, 1.11] },
      { type: 'canister', position: [.01, .29, 1.05] },
    ],
    packing: [
      { type: 'parcel', position: [.14, -.11, .96] },
      { type: 'parcel', position: [.42, .12, 1.19] },
      { type: 'bin', position: [.71, -.14, 1.04] },
    ],
    inspection: [
      { type: 'canister', position: [.24, -.18, .99] },
      { type: 'ball', position: [.45, .21, 1.14] },
      { type: 'bin', position: [-.02, -.21, 1.02] },
    ],
  };
  return lists[preset].map(item => ({ ...item, id: nextItemId() }));
}
function FurnitureColliders({ preset }: { preset: Preset }) {
  const top: Vec3 = preset === 'inspection' ? [.36,.39,.41] : [.53,.38,.26];
  return <>
    <Ground />
    <RigidBody name="fixed-workbench" position={[0,0,.76]} kinematic>
      <BoxCollider hx={.91} hy={.48} hz={.054} color={top} />
      {[-.78,.78].flatMap(x => [-.34,.34].map(y =>
        <BoxCollider key={String(x)+String(y)} hx={.036} hy={.036} hz={.36}
          position={[x,y,-.37]} color={[.24,.27,.29]}/>,
      ))}
    </RigidBody>
    <RigidBody name="fixed-chair" position={[-1.18,.68,.46]} kinematic>
      <BoxCollider hx={.24} hy={.24} hz={.048} color={[.19,.23,.24]}/>
      <BoxCollider hx={.044} hy={.24} hz={.28} position={[-.21,0,.29]} color={[.18,.21,.23]}/>
      {[-.18,.18].flatMap(x => [-.18,.18].map(y =>
        <BoxCollider key={String(x)+String(y)} hx={.028} hy={.028} hz={.20}
          position={[x,y,-.23]} color={[.15,.18,.20]}/>,
      ))}
    </RigidBody>
    <RigidBody name="fixed-monitor" position={[.66,.294,1.157]} kinematic>
      <BoxCollider hx={.24} hy={.035} hz={.16} color={[.20,.23,.25]}/>
      <BoxCollider hx={.019} hy={.019} hz={.095} position={[0,-.024,-.241]} color={[.34,.40,.44]}/>
      <BoxCollider hx={.14} hy={.09} hz={.01} position={[0,-.024,-.342]} color={[.25,.28,.31]}/>
    </RigidBody>
  </>;
}
function FollowPbr({ item, body, onMotion }: {
  item: LooseItem;
  body: React.RefObject<RigidBodyHandle | null>;
  onMotion: (sample: ItemMotionSample) => void;
}) {
  const group = useRef<Group>(null);
  const sampleElapsed = useRef(0);
  useFrame((state, delta) => {
    const pose = body.current && body.current.index >= 0 ? body.current.pose : null;
    if (group.current && pose) {
      group.current.position.copy(pose.position);
      group.current.quaternion.copy(pose.quaternion);
      sampleElapsed.current += delta;
      if (sampleElapsed.current >= .4) {
        sampleElapsed.current = 0;
        onMotion({
          id: item.id,
          position: [pose.position.x, pose.position.y, pose.position.z],
          at: state.clock.elapsedTime,
        });
      }
    }
  });
  return <group ref={group} position={item.position}>
    <ProductDetail type={item.type}/>
  </group>;
}
function LooseObject({ item, onMotion }: {
  item: LooseItem; onMotion: (sample: ItemMotionSample) => void;
}) {
  const ref = useRef<RigidBodyHandle>(null);
  return <>
    <RigidBody ref={ref} name={'item-'+item.id} position={item.position} mass={{ parcel: .45, canister: .36, ball: .13, bin: .62 }[item.type]}>
      {item.type === 'ball' && <SphereCollider radius={.062} restitution={.55} color={[.67,.78,.73]}/>}
      {item.type === 'canister' && <CylinderCollider radius={.053} halfHeight={.076} color={[.66,.73,.77]}/>}
      {item.type === 'parcel' && <BoxCollider hx={.113} hy={.094} hz={.078} color={[.57,.42,.29]}/>}
      {item.type === 'bin' && <>
        <BoxCollider hx={.118} hy={.094} hz={.008} position={[0,0,-.052]} color={[.36,.45,.5]}/>
        {[-.111,.111].map(x => <BoxCollider key={'bx'+x} hx={.006} hy={.095} hz={.064} position={[x,0,.005]} color={[.36,.45,.5]}/>)}
        {[-.088,.088].map(y => <BoxCollider key={'by'+y} hx={.119} hy={.007} hz={.064} position={[0,y,.005]} color={[.36,.45,.5]}/>)}
      </>}
    </RigidBody>
    <FollowPbr item={item} body={ref} onMotion={onMotion}/>
  </>;
}
// Deterministic reference reaching motion. Explicitly NOT P37 policy inference.
// The target is a fixed reference location above the table; this cycle does not
// claim to grasp, lift, or complete any task.
export function referenceReachPose(body: RobotType): [number, number, number] {
  const upper = body === 'compact' ? .40 : .52;
  const lower = (body === 'compact' ? .28 : .39) + .095;
  const dx = -.06 - (-.63), dy = -.08 - .05;
  const radius = Math.hypot(dx, dy);
  const dz = .95 - (.805 + .12 + .29);
  const cosine = Math.max(-1, Math.min(1,
    (radius * radius + dz * dz - upper * upper - lower * lower) / (2 * upper * lower)));
  const fold = Math.acos(cosine);
  const planarAngle = Math.atan2(dz, radius) -
    Math.atan2(lower * Math.sin(fold), upper + lower * Math.cos(fold));
  // MuJoCo/URDF Y-axis hinge positive pitch rotates the X-pointing link down.
  return [Math.atan2(dy, dx), -planarAngle, -fold];
}
function smooth(t: number): number {
  const x = Math.max(0, Math.min(1, t));
  return x * x * (3 - 2 * x);
}
type JointReading = { q: number; qd: number };
function ReferenceRobotControl({ refRobot, target, body, baseline, gripper, onGripSample }: {
  refRobot: React.RefObject<RobotHandle | null>;
  target: number;
  body: RobotType;
  baseline: boolean;
  gripper: number;
  onGripSample: (sample: GripStateSample) => void;
}) {
  const world = useWorld();
  const readings = useRef<Map<string, JointReading>>(new Map());
  const goal = referenceReachPose(body);

  useEffect(() => {
    if (!world) return;
    let active = true;
    let busy = false;
    let lastReport = 0;
    const timer = setInterval(async () => {
      const robot = refRobot.current;
      if (!robot || busy) return;
      busy = true;
      try {
        // Direct, real solver joint-coordinate GPU readback. URDF joints do not
        // have motor Kp by default in steel-webgpu v0.1.0; the PD controller
        // below needs this observation to apply *physical joint forces*.
        const state = await world.sim.state();
        if (!active) return;
        // RobotHandle.dofs stores Newton qd indices. The GPU's jointQ array
        // uses a *different* coordinate layout: every free body contributes
        // 7 q values but only 6 qd values. Never index jointQ with a qd index.
        const joints = (world.sim.scene.json as unknown as {
          joints: { q_start: number[]; qd_start: number[] };
        }).joints;
        const qIndexForDof = (dof: number): number | undefined => {
          for (let joint = 0; joint + 1 < joints.qd_start.length; joint++) {
            const low = joints.qd_start[joint], high = joints.qd_start[joint + 1];
            if (dof >= low && dof < high) {
              return joints.q_start[joint] + dof - low;
            }
          }
          return undefined;
        };
        const report: { name: string; dof: number; qIndex: number | undefined;
          q: number | undefined; qd: number | undefined }[] = [];
        for (const [name, dof] of robot.dofs) {
          const qIndex = qIndexForDof(dof);
          const q = qIndex === undefined ? undefined : state.jointQ[qIndex];
          const qd = state.jointQd[dof];
          report.push({ name, dof, qIndex, q, qd });
          if (q !== undefined && Number.isFinite(q) && Number.isFinite(qd))
            readings.current.set(name, { q, qd });
        }
        if (window.location.search.includes('debugPhysics=1')) {
          (window as Window & { __p37PhysicsDebug?: unknown }).__p37PhysicsDebug = {
            time: world.sim.time, robot: body, joints: report,
            actions: [...readings.current.entries()],
          };
        }
        if (world.sim.time - lastReport >= .5) {
          const left = readings.current.get(body === 'panda' ? 'finger_joint1' : 'left_finger_slide');
          const right = readings.current.get(body === 'panda' ? 'finger_joint2' : 'right_finger_slide');
          if (left && right) {
            onGripSample({ left: left.q, right: right.q, time: world.sim.time });
            lastReport = world.sim.time;
          }
        }
      } catch (error) {
        // Leave telemetry unavailable on WebGPU loss; never invent joint data.
        console.warn('Steel joint state readback unavailable', error);
      } finally {
        busy = false;
      }
    }, 100);
    return () => { active = false; clearInterval(timer); readings.current.clear(); };
  }, [world, refRobot, body, onGripSample]);

  useBeforeStep((sim) => {
    const robot = refRobot.current;
    if (!robot) return;
    if (body === 'panda') {
      // Manufacturer-derived Panda geometry (Apache-2.0, MuJoCo Menagerie).
      // Seven servo position commands, not a learned P37 policy.
      const pandaHome = [0, -.23, 0, -1.58, 0, 1.52, -.79];
      const names = ['joint1','joint2','joint3','joint4','joint5','joint6','joint7'];
      names.forEach((name, index) => {
        if (robot.dofs.has(name)) robot.setJointTarget(name, pandaHome[index]);
      });
      const jaw = Math.max(0, Math.min(.035, gripper));
      for (const name of ['finger_joint1','finger_joint2'])
        if (robot.dofs.has(name)) robot.setJointTarget(name, jaw);
      return;
    }
    // Original reference URDFs: a force-limited PD servo on each Newton joint.
    // Steel's URDF parser currently sets damping only, not Kp, so a plain
    // setJointTarget() would leave these bodies motionless. The PD force below
    // uses GPU-measured q and qd. No object attachment/teleport is performed.
    const drive = (name: string, commanded: number, kp: number, kd: number, forceMax: number) => {
      if (!robot.dofs.has(name)) return;
      robot.setJointTarget(name, commanded);
      const actual = readings.current.get(name);
      if (!actual) return;
      const force = Math.max(-forceMax, Math.min(forceMax,
        kp * (commanded - actual.q) - kd * actual.qd));
      robot.setJointForce(name, force);
    };
    const phase = sim.time % 8.5;
    const fraction = !baseline ? 0 :
      phase < .5 ? 0 :
      phase < 3.2 ? smooth((phase - .5) / 2.7) :
      phase < 5 ? 1 :
      phase < 7.8 ? 1 - smooth((phase - 5) / 2.8) : 0;
    drive('shoulder', target * (1 - fraction) + goal[0] * fraction, 155, 18, 100);
    drive('elbow', -.64 * (1 - fraction) + goal[1] * fraction, 180, 18, 75);
    drive('wrist', .52 * (1 - fraction) + goal[2] * fraction, 100, 12, 42);
    const opening = Math.max(0, Math.min(.035, gripper));
    drive('left_finger_slide', opening, 440, 24, 40);
    drive('right_finger_slide', opening, 440, 24, 40);
  });
  return null;
}
function StatsFeed({ onSample }: { onSample: (s: SimStatsSample | null) => void }) {
  const stats = useSimStats({ hz: 2 });
  useEffect(() => onSample(stats), [stats, onSample]);
  return null;
}
export function Workcell({ preset, robot, items, pose, baseline = true, gripper,
  onStats, onMotion, onGripSample, sourceFrames, sourcePlaying }: {
  preset: Preset; robot: RobotType; items: LooseItem[];
  pose: number; baseline?: boolean; gripper: number;
  onStats: (s: SimStatsSample | null) => void;
  onMotion: (sample: ItemMotionSample) => void;
  onGripSample: (sample: GripStateSample) => void;
  sourceFrames: SourceFrame[]; sourcePlaying: boolean;
}) {
  const robotRef = useRef<RobotHandle>(null);
  return <>
    <FurnitureColliders preset={preset}/>
    {items.map(item => <LooseObject key={item.id} item={item} onMotion={onMotion}/>)}
    {robot === 'panda' ?
      <MJCF src={import.meta.env.BASE_URL + 'vendor/panda/panda-steel.xml'} ref={robotRef}
        xform={[-.63,.05,.814,0,0,0,1]}/> :
      <URDF src={import.meta.env.BASE_URL + 'robots/' + robot + '.urdf'} ref={robotRef}
        xform={[-.63,.05,.805,0,0,0,1]}/>
    }
    <ReferenceRobotControl refRobot={robotRef} target={pose} body={robot} baseline={baseline} gripper={gripper} onGripSample={onGripSample}/>
    <IndustrialSet preset={preset}/>
    {sourceFrames.length >= 2 && <SourceTrajectory frames={sourceFrames} playing={sourcePlaying}/>}
    <StatsFeed onSample={onStats}/>
  </>;
}
export type { SceneHandle };
