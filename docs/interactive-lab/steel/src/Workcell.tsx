import { useEffect, useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import {
  BoxCollider, CylinderCollider, Ground, RigidBody, Scene,
  SphereCollider, URDF, useBeforeStep, useSimStats,
  type RigidBodyHandle, type RobotHandle, type SceneHandle, type SimStatsSample,
} from '@skild-ai/steel-webgpu/react';
import type { Vec3 } from '@skild-ai/steel-webgpu';
import { CanvasTexture, Group, RepeatWrapping, SRGBColorSpace } from 'three';

export type Preset = 'workcell' | 'packing' | 'inspection';
export type RobotType = 'compact' | 'extended';
export type ObjectType = 'parcel' | 'canister' | 'ball' | 'bin';
export type LooseItem = { id: number; type: ObjectType; position: Vec3 };
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
function woodTexture(): CanvasTexture {
  const c = document.createElement('canvas'); c.width = 1024; c.height = 256;
  const ctx = c.getContext('2d');
  if (!ctx) throw new Error('Canvas unavailable for procedural wood texture');
  ctx.fillStyle = '#a48262'; ctx.fillRect(0, 0, c.width, c.height);
  let seed = 11457;
  const random = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  for (let i = 0; i < 1700; i++) {
    const y = random() * 256, v = random() * .13;
    ctx.strokeStyle = random() > .48 ? 'rgba(55,30,18,' + v + ')' : 'rgba(255,226,185,' + v + ')';
    ctx.lineWidth = .25 + random() * 2.3; ctx.beginPath(); ctx.moveTo(0,y);
    for (let x = 0; x <= 1024; x += 45) ctx.lineTo(x, y + Math.sin(x*.016+i)*(1.0+random()*2));
    ctx.stroke();
  }
  const t = new CanvasTexture(c);
  t.wrapS = RepeatWrapping; t.wrapT = RepeatWrapping; t.colorSpace = SRGBColorSpace;
  return t;
}
function FurnitureColliders({ preset }: { preset: Preset }) {
  const top: Vec3 = preset === 'inspection' ? [.36,.39,.41] : [.53,.38,.26];
  return <>
    <Ground />
    <RigidBody name="fixed-workbench" position={[0,0,.76]} kinematic>
      <BoxCollider hx={.91} hy={.48} hz={.042} color={top} />
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
    <RigidBody name="fixed-monitor" position={[.92,.53,1.05]} kinematic>
      <BoxCollider hx={.14} hy={.038} hz={.28} color={[.20,.23,.25]}/>
    </RigidBody>
  </>;
}
function FurnitureVisuals({ preset }: { preset: Preset }) {
  const oak = useMemo(woodTexture, []);
  useEffect(() => () => oak.dispose(), [oak]);
  const metal = '#3c474c';
  return <>
    <mesh receiveShadow position={[0,0,-.045]}>
      <boxGeometry args={[12,12,.09]}/><meshStandardMaterial color="#30383b" roughness={.94}/>
    </mesh>
    <mesh castShadow receiveShadow position={[0,0,.762]}>
      <boxGeometry args={[1.85,.98,.088]}/>
      <meshPhysicalMaterial color={preset === 'inspection' ? '#899096' : '#b38a6a'}
        map={preset === 'inspection' ? undefined : oak}
        metalness={preset === 'inspection' ? .67 : .04}
        roughness={preset === 'inspection' ? .35 : .47} clearcoat={.18}/>
    </mesh>
    {[-.78,.78].flatMap(x => [-.34,.34].map(y =>
      <mesh key={'leg'+x+y} castShadow position={[x,y,.39]}>
        <boxGeometry args={[.08,.08,.73]}/>
        <meshStandardMaterial color={metal} roughness={.32} metalness={.82}/>
      </mesh>,
    ))}
    <mesh castShadow receiveShadow position={[-1.18,.68,.462]}>
      <boxGeometry args={[.49,.49,.097]}/>
      <meshPhysicalMaterial color="#6b5447" roughness={.79}/>
    </mesh>
    <mesh castShadow receiveShadow position={[-1.39,.68,.76]}>
      <boxGeometry args={[.091,.49,.57]}/>
      <meshPhysicalMaterial color="#334047" roughness={.84}/>
    </mesh>
    {[-.18,.18].flatMap(x => [-.18,.18].map(y =>
      <mesh key={'chair'+x+y} castShadow position={[-1.18+x,.68+y,.23]}>
        <cylinderGeometry args={[.025,.025,.43,12]}/>
        <meshStandardMaterial color="#6b7478" roughness={.39} metalness={.78}/>
      </mesh>,
    ))}
    <mesh castShadow position={[.92,.53,1.06]}>
      <boxGeometry args={[.29,.09,.57]}/>
      <meshStandardMaterial color="#434e55" roughness={.54} metalness={.65}/>
    </mesh>
    <mesh position={[.923,.477,1.11]}>
      <boxGeometry args={[.19,.012,.24]}/><meshPhysicalMaterial color="#0e2830" roughness={.29}/>
    </mesh>
    <ambientLight intensity={.36}/>
    <directionalLight position={[3,-3,6]} intensity={1.8} castShadow shadow-mapSize={[2048,2048]}/>
    <spotLight position={[-2,-1.3,4.2]} intensity={230} angle={.55} penumbra={.8} castShadow color="#faf6ef"/>
  </>;
}
function FollowPbr({ type, body, initial }: {
  type: ObjectType; body: React.RefObject<RigidBodyHandle | null>; initial: Vec3
}) {
  const group = useRef<Group>(null);
  useFrame(() => {
    const pose = body.current && body.current.index >= 0 ? body.current.pose : null;
    if (group.current && pose) {
      group.current.position.copy(pose.position);
      group.current.quaternion.copy(pose.quaternion);
    }
  });
  return <group ref={group} position={initial}>
    {type === 'parcel' && <>
      <mesh castShadow receiveShadow><boxGeometry args={[.232,.193,.162]}/>
        <meshStandardMaterial color="#b58c66" roughness={.84}/></mesh>
      <mesh position={[0,0,.083]}><boxGeometry args={[.037,.195,.003]}/>
        <meshStandardMaterial color="#d5be9b" roughness={.7}/></mesh>
      <mesh position={[.117,0,0]}><boxGeometry args={[.003,.195,.04]}/>
        <meshStandardMaterial color="#d9c39f" roughness={.68}/></mesh>
    </>}
    {type === 'canister' && <mesh castShadow receiveShadow>
      <cylinderGeometry args={[.057,.053,.155,32]}/>
      <meshPhysicalMaterial color="#c1cccf" metalness={.67} roughness={.19}/>
    </mesh>}
    {type === 'ball' && <mesh castShadow><sphereGeometry args={[.066,32,24]}/>
      <meshPhysicalMaterial color="#cfdbd1" roughness={.27} metalness={.08} clearcoat={.42}/>
    </mesh>}
    {type === 'bin' && <>
      <mesh castShadow><boxGeometry args={[.247,.203,.128]}/>
        <meshStandardMaterial color="#52626b" metalness={.34} roughness={.54}/></mesh>
      <mesh position={[0,0,.069]}><boxGeometry args={[.23,.18,.008]}/>
        <meshStandardMaterial color="#73858a" metalness={.48} roughness={.42}/></mesh>
    </>}
  </group>;
}
function LooseObject({ item }: { item: LooseItem }) {
  const ref = useRef<RigidBodyHandle>(null);
  return <>
    <RigidBody ref={ref} name={'item-'+item.id} position={item.position} mass={item.type === 'parcel' ? .25 : .18}>
      {item.type === 'ball' && <SphereCollider radius={.062} restitution={.45} color={[.67,.78,.73]}/>}
      {item.type === 'canister' && <CylinderCollider radius={.053} halfHeight={.076} color={[.66,.73,.77]} friction={.63}/>}
      {item.type === 'parcel' && <BoxCollider hx={.113} hy={.094} hz={.078} color={[.57,.42,.29]} friction={.72}/>}
      {item.type === 'bin' && <BoxCollider hx={.121} hy={.098} hz={.062} color={[.36,.45,.5]} friction={.8}/>}
    </RigidBody>
    <FollowPbr type={item.type} body={ref} initial={item.position}/>
  </>;
}
function ReferenceRobotControl({ refRobot, target }: {
  refRobot: React.RefObject<RobotHandle | null>; target: number
}) {
  useBeforeStep(() => {
    const robot = refRobot.current;
    if (!robot) return;
    if (robot.dofs.has('shoulder')) robot.setJointTarget('shoulder', target);
    if (robot.dofs.has('elbow')) robot.setJointTarget('elbow', -.64);
    if (robot.dofs.has('wrist')) robot.setJointTarget('wrist', .52);
  });
  return null;
}
function StatsFeed({ onSample }: { onSample: (s: SimStatsSample | null) => void }) {
  const stats = useSimStats({ hz: 2 });
  useEffect(() => onSample(stats), [stats, onSample]);
  return null;
}
export function Workcell({ preset, robot, items, pose, onStats }: {
  preset: Preset; robot: RobotType; items: LooseItem[];
  pose: number; onStats: (s: SimStatsSample | null) => void;
}) {
  const robotRef = useRef<RobotHandle>(null);
  return <>
    <FurnitureColliders preset={preset}/>
    {items.map(item => <LooseObject key={item.id} item={item}/>)}
    <URDF src={import.meta.env.BASE_URL + 'robots/' + robot + '.urdf'} ref={robotRef}
      xform={[-.63,.05,.805,0,0,0,1]}/>
    <ReferenceRobotControl refRobot={robotRef} target={pose}/>
    <FurnitureVisuals preset={preset}/>
    <StatsFeed onSample={onStats}/>
  </>;
}
export type { SceneHandle };
