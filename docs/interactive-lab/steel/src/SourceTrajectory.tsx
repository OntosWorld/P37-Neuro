import { useEffect, useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { BufferGeometry, Line as ThreeLine, LineBasicMaterial, Mesh, Vector3 } from 'three';

export interface SourceFrame {
  t: number;
  state: Record<string, number>;
}

function position(frame: SourceFrame): [number, number, number] {
  return [
    frame.state.eef_position_0,
    frame.state.eef_position_1,
    frame.state.eef_position_2,
  ];
}

/**
 * Data-derived source end-effector path only. Never actuates the reference arm,
 * never asserts contact, and never infers a trained P37 policy result.
 */
export function SourceTrajectory({
  frames,
  playing,
}: {
  frames: SourceFrame[];
  playing: boolean;
}) {
  const marker = useRef<Mesh>(null);
  const elapsed = useRef(0);
  const line = useMemo(() => {
    const points = frames.map((frame) => new Vector3(...position(frame)));
    const geometry = new BufferGeometry().setFromPoints(points);
    const material = new LineBasicMaterial({ color: '#b4f4d1' });
    return new ThreeLine(geometry, material);
  }, [frames]);

  useEffect(() => {
    elapsed.current = 0;
    return () => {
      line.geometry.dispose();
      (line.material as LineBasicMaterial).dispose();
    };
  }, [line]);

  useFrame((_, delta) => {
    if (!marker.current || frames.length === 0) return;
    const total = frames[frames.length - 1].t;
    if (playing) elapsed.current = total > 0 ? (elapsed.current + Math.min(delta, 0.1)) % total : 0;
    let lo = 0;
    let hi = frames.length - 1;
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1;
      if (frames[mid].t <= elapsed.current) lo = mid;
      else hi = mid - 1;
    }
    const point = position(frames[lo]);
    marker.current.position.set(...point);
  });

  if (frames.length < 2) return null;
  return (
    <group>
      <primitive object={line} />
      <mesh ref={marker} position={position(frames[0])}>
        <sphereGeometry args={[0.026, 24, 16]} />
        <meshBasicMaterial color="#d3ffec" />
      </mesh>
      <mesh position={position(frames[0])}>
        <sphereGeometry args={[0.012, 12, 10]} />
        <meshBasicMaterial color="#85b5dd" />
      </mesh>
      <mesh position={position(frames[frames.length - 1])}>
        <sphereGeometry args={[0.012, 12, 10]} />
        <meshBasicMaterial color="#d9b784" />
      </mesh>
    </group>
  );
}
