import { useEffect, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import {
  BoxCollider, CylinderCollider, Ground, RigidBody,
  SphereCollider, URDF, useBeforeStep, useSimStats, useWorld,
  type RigidBodyHandle, type RobotHandle, type SceneHandle, type SimStatsSample,
} from '@skild-ai/steel-webgpu/react';
import type { Vec3 } from '@skild-ai/steel-webgpu';
import { Group } from 'three';
import { IndustrialSet, ProductDetail } from './IndustrialSet';
import { SourceTrajectory, type SourceFrame } from './SourceTrajectory';

export type Preset = 'workcell' | 'packing' | 'inspection';
export type RobotType = 'compact' | 'extended';
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
function ReferenceRobotControl({ refRobot, target, body, baseline, gripper }: {
  refRobot: React.RefObject<RobotHandle | null>;
  target: number;
  body: RobotType;
  baseline: boolean;
  gripper: number;
}) {
  const goal = referenceReachPose(body);
  useBeforeStep((sim) => {
    const robot = refRobot.current;
    if (!robot) return;
    const phase = sim.time % 8.5;
    const fraction = !baseline ? 0 :
      phase < .5 ? 0 :
      phase < 3.2 ? smooth((phase - .5) / 2.7) :
      phase < 5 ? 1 :
      phase < 7.8 ? 1 - smooth((phase - 5) / 2.8) : 0;
    const shoulder = target * (1 - fraction) + goal[0] * fraction;
    const elbow = -.64 * (1 - fraction) + goal[1] * fraction;
    const wrist = .52 * (1 - fraction) + goal[2] * fraction;
    if (robot.dofs.has('shoulder')) robot.setJointTarget('shoulder', shoulder);
    if (robot.dofs.has('elbow')) robot.setJointTarget('elbow', elbow);
    if (robot.dofs.has('wrist')) robot.setJointTarget('wrist', wrist);
    // Actuated prismatic jaws. The solver decides whether finite-mass objects
    // actually move; we never teleport an object or mark a grasp successful.
    const opening = Math.max(0, Math.min(.035, gripper));
    if (robot.dofs.has('left_finger_slide')) robot.setJointTarget('left_finger_slide', opening);
    if (robot.dofs.has('right_finger_slide')) robot.setJointTarget('right_finger_slide', opening);
  });
  return null;
}
function GripperTelemetry({ robotRef, onSample }: {
  robotRef: React.RefObject<RobotHandle | null>;
  onSample: (sample: GripStateSample) => void;
}) {
  const world = useWorld();
  useEffect(() => {
    if (!world) return;
    let active = true;
    let busy = false;
    const timer = setInterval(async () => {
      const robot = robotRef.current;
      const left = robot?.dofs.get('left_finger_slide');
      const right = robot?.dofs.get('right_finger_slide');
      if (left === undefined || right === undefined || busy) return;
      busy = true;
      try {
        // Read the two actual Newton joint coordinates from GPU memory;
        // commanded gripper opening is NEVER substituted for measurement.
        const state = await world.sim.state();
        if (active && Number.isFinite(state.jointQ[left]) && Number.isFinite(state.jointQ[right])) {
          onSample({
            left: state.jointQ[left],
            right: state.jointQ[right],
            time: world.sim.time,
          });
        }
      } catch (error) {
        // GPU loss and transient readback failures are handled by the Scene
        // error boundary. Keep telemetry marked unavailable until valid.
        console.warn('Steel gripper state readback unavailable', error);
      } finally {
        busy = false;
      }
    }, 850);
    return () => { active = false; clearInterval(timer); };
  }, [world, robotRef, onSample]);
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
    <URDF src={import.meta.env.BASE_URL + 'robots/' + robot + '.urdf'} ref={robotRef}
      xform={[-.63,.05,.805,0,0,0,1]}/>
    <ReferenceRobotControl refRobot={robotRef} target={pose} body={robot} baseline={baseline} gripper={gripper}/>
    <GripperTelemetry robotRef={robotRef} onSample={onGripSample}/>
    <IndustrialSet preset={preset}/>
    {sourceFrames.length >= 2 && <SourceTrajectory frames={sourceFrames} playing={sourcePlaying}/>}
    <StatsFeed onSample={onStats}/>
  </>;
}
export type { SceneHandle };
