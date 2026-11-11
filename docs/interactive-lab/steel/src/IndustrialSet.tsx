/**
 * Physical-workcell visual set. Units are meters in a Z-up Steel scene.
 *
 * The workbench/seat/monitor meshes mirror the static Steel colliders in Workcell.tsx.
 * Tiny labels, screw heads, seams, tool handles and distant room dressing are visual
 * detail only; they are not presented as interactable simulation objects.
 */
import { useEffect, useMemo } from 'react';
import { CanvasTexture, RepeatWrapping, SRGBColorSpace, type ColorRepresentation } from 'three';
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import type { Vec3 } from '@skild-ai/steel-webgpu';
import type { Preset } from './Workcell';

function RoundedSolid({
  size, position, color, roughness = .45, metalness = .12, radius = .007, clearcoat = 0,
}: {
  size: Vec3;
  position: Vec3;
  color: ColorRepresentation;
  roughness?: number;
  metalness?: number;
  radius?: number;
  clearcoat?: number;
}) {
  const geometry = useMemo(() =>
    new RoundedBoxGeometry(size[0], size[1], size[2], 3, radius),
    [size[0], size[1], size[2], radius],
  );
  useEffect(() => () => geometry.dispose(), [geometry]);
  return <mesh geometry={geometry} position={position} castShadow receiveShadow>
    <meshPhysicalMaterial color={color} roughness={roughness} metalness={metalness} clearcoat={clearcoat}/>
  </mesh>;
}

function grainTexture(): CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = 1536;
  canvas.height = 384;
  const g = canvas.getContext('2d');
  if (!g) throw new Error('Cannot render workbench material');
  g.fillStyle = '#a99279'; g.fillRect(0,0,1536,384);
  let seed = 27541;
  const rand = () => { seed=(seed*1664525+1013904223)>>>0;return seed/4294967296; };
  for (let n=0;n<3800;n++) {
    const y=rand()*384;
    g.strokeStyle = rand()>.52
      ? 'rgba(54,34,21,'+(rand()*.11).toFixed(3)+')'
      : 'rgba(255,236,204,'+(rand()*.12).toFixed(3)+')';
    g.lineWidth=.3+rand()*1.4;
    g.beginPath();g.moveTo(0,y);
    for(let x=0;x<=1536;x+=37)g.lineTo(x,y+Math.sin(x*.012+n)*2.3);
    g.stroke();
  }
  const t=new CanvasTexture(canvas);t.colorSpace=SRGBColorSpace;
  t.wrapS=RepeatWrapping;t.wrapT=RepeatWrapping;t.anisotropy=12;
  return t;
}

function materialLabel(title: string, subtitle: string): CanvasTexture {
  const canvas=document.createElement('canvas');
  canvas.width=512;canvas.height=256;
  const g=canvas.getContext('2d');
  if(!g)throw new Error('Cannot render product label');
  g.fillStyle='#edf0ea';g.fillRect(0,0,512,256);
  g.fillStyle='#202c2d';g.fillRect(0,0,512,38);
  g.fillStyle='#d2dfd9';g.font='600 18px Arial';g.fillText('ONTOS  /  RESEARCH WORKCELL',21,26);
  g.fillStyle='#202a29';g.font='bold 51px Arial';g.fillText(title,21,112);
  g.font='26px Arial';g.fillStyle='#516365';g.fillText(subtitle,22,161);
  g.fillStyle='#779288';
  for(let i=0;i<30;i++)g.fillRect(21+i*11,189,3+(i%4)*2,33);
  const texture=new CanvasTexture(canvas);texture.colorSpace=SRGBColorSpace;
  return texture;
}

function Workbench({ preset }: {preset:Preset}) {
  const oak=useMemo(grainTexture,[]);
  const label=useMemo(()=>materialLabel('P37 / LAB', 'WORKCELL 01  /  2026'),[]);
  useEffect(()=>()=>{oak.dispose();label.dispose()},[oak,label]);
  const steel = preset==='inspection';
  const edge=steel?'#838e95':'#393f40';
  const metal='#414d53';
  return <group>
    {/* Floor-to-worktop frame. Same extents as Steel's static tabletop and legs. */}
    <RoundedSolid size={[1.85,.98,.084]} position={[0,0,.76]} color={edge}
      radius={.012} roughness={.42} metalness={steel?.72:.40}/>
    <mesh position={[0,0,.803]} castShadow receiveShadow>
      <boxGeometry args={[1.81,.94,.007]}/>
      <meshPhysicalMaterial color={steel?'#a0a8ab':'#c0a48b'} map={steel?undefined:oak}
        metalness={steel?.54:.06} roughness={steel?.32:.52} clearcoat={.16}/>
    </mesh>
    {/* T-slot edge protection; metal braces and levelling feet. */}
    {[-.78,.78].flatMap(x=>[-.34,.34].map(y=>
      <group key={'leg'+x+y}>
        <RoundedSolid size={[.074,.074,.72]} position={[x,y,.390]} color={metal}
          metalness={.78} roughness={.32} radius={.007}/>
        <RoundedSolid size={[.117,.113,.03]} position={[x,y,.028]} color="#202729"
          metalness={.46} roughness={.64} radius={.008}/>
        <mesh position={[x,y,.062]}>
          <cylinderGeometry args={[.016,.016,.025,16]}/>
          <meshStandardMaterial color="#c6c8c1" metalness={.82} roughness={.33}/>
        </mesh>
      </group>
    ))}
    {[-.33,.33].map(y=>
      <RoundedSolid key={'apron-y'+y} size={[1.61,.032,.07]} position={[0,y,.68]}
        color="#444f54" metalness={.77} roughness={.32} radius={.005}/>
    )}
    {[-.77,.77].map(x=>
      <RoundedSolid key={'apron-x'+x} size={[.032,.70,.07]} position={[x,0,.68]}
        color="#434d52" metalness={.76} roughness={.34} radius={.005}/>
    )}
    <RoundedSolid size={[1.55,.65,.027]} position={[0,0,.23]}
      color="#41474b" metalness={.55} roughness={.56}/>
    {/* Laser-etched plate rests on the table without changing its collision mesh. */}
    <mesh position={[-.63,-.26,.808]}>
      <planeGeometry args={[.15,.075]}/>
      <meshBasicMaterial map={label} transparent/>
    </mesh>
    {/* Calibration rail aligned to the back edge. */}
    <RoundedSolid size={[1.7,.018,.027]} position={[0,.447,.823]}
      color="#566468" metalness={.72} roughness={.3} radius={.004}/>
  </group>;
}

function Chair() {
  const frame='#505b62';
  return <group>
    <RoundedSolid size={[.485,.487,.094]} position={[-1.18,.68,.462]}
      color="#364144" roughness={.82} radius={.042}/>
    <RoundedSolid size={[.083,.49,.57]} position={[-1.39,.68,.756]}
      color="#2d383e" roughness={.78} radius={.031}/>
    {/* Upholstery seam panels and exposed steel chair frame. */}
    <RoundedSolid size={[.37,.006,.47]} position={[-1.343,.68,.764]}
      color="#506066" roughness={.91} radius={.031}/>
    {[-.175,.175].map(y=>
      <group key={'chair-arm'+y}>
        <RoundedSolid size={[.30,.045,.037]} position={[-1.17,.68+y,.66]}
          color="#303c40" roughness={.66}/>
        <RoundedSolid size={[.027,.029,.18]} position={[-1.03,.68+y,.558]}
          color={frame} metalness={.77} roughness={.4}/>
      </group>
    )}
    {[-.18,.18].flatMap(x=>[-.18,.18].map(y=>
      <group key={'chair-leg'+x+y}>
        <RoundedSolid size={[.046,.046,.42]} position={[-1.18+x,.68+y,.227]}
          color={frame} metalness={.73} roughness={.43}/>
        <RoundedSolid size={[.069,.055,.038]} position={[-1.18+x,.68+y,.034]}
          color="#22292e" metalness={.28} roughness={.77}/>
      </group>
    ))}
  </group>;
}

function Monitor() {
  return <group>
    <RoundedSolid size={[.28,.18,.020]} position={[.66,.27,.815]}
      color="#263237" metalness={.64} roughness={.35} radius={.008}/>
    <RoundedSolid size={[.037,.036,.19]} position={[.66,.27,.916]}
      color="#6f7d82" metalness={.81} roughness={.3}/>
    <RoundedSolid size={[.48,.069,.32]} position={[.66,.294,1.157]}
      color="#29333a" metalness={.56} roughness={.4} radius={.018}/>
    <RoundedSolid size={[.442,.008,.273]} position={[.66,.253,1.156]}
      color="#081316" metalness={.31} roughness={.18} clearcoat={.72} radius={.008}/>
    <mesh position={[.66,.247,1.157]} rotation={[Math.PI/2,0,0]}>
      <planeGeometry args={[.405,.238]}/>
      <meshBasicMaterial color="#0f3435"/>
    </mesh>
    {/* A minimal instrument HUD. Not live policy telemetry. */}
    {[0,1,2].map(i=>
      <mesh key={i} position={[.57+i*.08,.244,1.16]} rotation={[Math.PI/2,0,0]}>
        <planeGeometry args={[.055,.003]}/>
        <meshBasicMaterial color={i===1?'#b2d6c5':'#5e8b86'}/>
      </mesh>
    )}
  </group>;
}

function Room() {
  return <group>
    <mesh receiveShadow position={[0,0,-.035]}>
      <boxGeometry args={[10,10,.11]}/>
      <meshStandardMaterial color="#b7beb9" roughness={.96} metalness={.025}/>
    </mesh>
    {/* Concrete panels and physical looking expansion joints. Backdrop only. */}
    <mesh receiveShadow position={[0,3.2,1.55]}>
      <boxGeometry args={[9,.06,3.1]}/>
      <meshStandardMaterial color="#929e9a" roughness={.91}/>
    </mesh>
    {[-3,-1.5,0,1.5,3].map(x=>
      <mesh key={'wall-'+x} position={[x,3.158,1.55]}>
        <boxGeometry args={[.006,.008,3.10]}/>
        <meshBasicMaterial color="#344047"/>
      </mesh>
    )}
    <RoundedSolid size={[4.75,.16,.14]} position={[0,3.1,.18]}
      color="#394346" metalness={.65} roughness={.44}/>
    {[.4,1.8].map(z=>
      <mesh key={'wall-strip'+z} position={[0,3.151,z]}>
        <boxGeometry args={[9,.008,.005]}/>
        <meshBasicMaterial color="#77807d"/>
      </mesh>
    )}
    <mesh position={[0,3.15,2.9]}>
      <boxGeometry args={[1.8,.055,.038]}/>
      <meshStandardMaterial color="#272f32" metalness={.54} roughness={.49}/>
    </mesh>
    <mesh position={[-1.6,3.113,1.53]}>
      <planeGeometry args={[.26,.25]}/>
      <meshBasicMaterial color="#d5bc8c" side={2}/>
    </mesh>
    {/* A constrained floor zone makes object dimensions readable. */}
    {[-1.3,1.3].map(x=>
      <mesh key={'floor-x'+x} position={[x,0,.026]}>
        <boxGeometry args={[.018,2.65,.004]}/>
        <meshBasicMaterial color="#a19a74"/>
      </mesh>
    )}
    {[-1.15,1.15].map(y=>
      <mesh key={'floor-y'+y} position={[0,y,.026]}>
        <boxGeometry args={[2.62,.018,.004]}/>
        <meshBasicMaterial color="#a19a74"/>
      </mesh>
    )}
  </group>;
}

function Lighting() {
  return <>
    <ambientLight intensity={.34} color="#d8e5e6"/>
    <hemisphereLight args={['#cfe0e2','#4e5a58',1.2]}/>
    <directionalLight position={[2.6,-3.4,5.3]} color="#fff5e9" intensity={2.7}
      castShadow shadow-mapSize={[2048,2048]}
      shadow-bias={-.00045} shadow-normalBias={.012}/>
    <spotLight position={[-2.3,-1.4,3.8]} color="#d6eeff" intensity={140}
      angle={.65} penumbra={.94} decay={2} castShadow={false}/>
    <spotLight position={[1.6,1.3,3.4]} color="#fff1d9" intensity={100}
      angle={.66} penumbra={1} decay={2}/>
  </>;
}

export function IndustrialSet({ preset }: {preset:Preset}) {
  return <>
    <Room/>
    <Workbench preset={preset}/>
    <Chair/>
    <Monitor/>
    <Lighting/>
  </>;
}

export function ProductDetail({ type }: {type:'parcel'|'canister'|'ball'|'bin'}) {
  const label=useMemo(()=>materialLabel(
    type==='parcel'?'PARTS / 04':type==='bin'?'BIN / 02':'QC / 01',
    type==='parcel'?'ORDER #P37-2026':type==='bin'?'MACHINE SHOP':'STEEL REFERENCE',
  ),[type]);
  useEffect(()=>()=>label.dispose(),[label]);
  if(type==='parcel')return <>
    <RoundedSolid size={[.23,.19,.16]} position={[0,0,0]}
      color="#b79870" roughness={.87} metalness={0} radius={.007}/>
    <RoundedSolid size={[.031,.189,.002]} position={[0,0,.082]}
      color="#d5be94" roughness={.77} metalness={0} radius={.001}/>
    <RoundedSolid size={[.003,.189,.039]} position={[.116,0,0]}
      color="#d8c39a" roughness={.81} metalness={0} radius={.001}/>
    <mesh position={[.1145,0,0]} rotation={[Math.PI/2,0,Math.PI/2]}>
      <planeGeometry args={[.095,.083]}/>
      <meshBasicMaterial map={label}/>
    </mesh>
  </>;
  if(type==='canister')return <>
    <mesh rotation={[Math.PI/2,0,0]} castShadow receiveShadow>
      <cylinderGeometry args={[.055,.051,.155,36]}/>
      <meshPhysicalMaterial color="#adbac0" metalness={.88} roughness={.22} clearcoat={.08}/>
    </mesh>
    {[-.071,.071].map(z=>
      <mesh key={z} position={[0,0,z]} rotation={[Math.PI/2,0,0]}>
        <torusGeometry args={[.054,.003,9,36]}/>
        <meshStandardMaterial color="#dae0e0" metalness={.88} roughness={.3}/>
      </mesh>
    )}
    <mesh position={[0,0,.079]}>
      <circleGeometry args={[.046,36]}/>
      <meshStandardMaterial color="#8d9b9d" metalness={.7} roughness={.3}/>
    </mesh>
  </>;
  if(type==='ball')return <mesh castShadow receiveShadow>
    <sphereGeometry args={[.064,40,32]}/>
    <meshPhysicalMaterial color="#d7dfd9" metalness={.07} roughness={.32} clearcoat={.55}/>
  </mesh>;
  return <group>
    {/* A physical five-piece tub; the inner floor and walls match Steel colliders. */}
    <RoundedSolid size={[.238,.192,.016]} position={[0,0,-.052]}
      color="#5d6e71" roughness={.63} metalness={.18}/>
    {[-.111,.111].map(x=>
      <RoundedSolid key={'bin-x'+x} size={[.012,.19,.13]} position={[x,0,.005]}
        color="#53696e" roughness={.58} metalness={.23}/>
    )}
    {[-.088,.088].map(y=>
      <RoundedSolid key={'bin-y'+y} size={[.238,.014,.13]} position={[0,y,.005]}
        color="#52686d" roughness={.58} metalness={.23}/>
    )}
    <RoundedSolid size={[.12,.004,.038]} position={[0,-.097,0]}
      color="#f0ede3" roughness={.84} metalness={0}/>
  </group>;
}
