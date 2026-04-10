/**
 * Hotspot — animated warning marker
 * ====================================
 * A small animated sphere that floats above Warning/Critical elements.
 * It "breathes" using a sine-wave scale animation driven by useFrame.
 *
 * Only rendered when the element's SHI status is WARNING or CRITICAL,
 * keeping the scene clean for healthy elements.
 */

import { useRef }   from "react";
import { useFrame } from "@react-three/fiber";
import { Sphere }   from "@react-three/drei";
import * as THREE   from "three";

interface Props {
  position:  [number, number, number];
  status:    "WARNING" | "CRITICAL";
  onClick:   () => void;
}

const STATUS_COLOR = {
  WARNING:  "#F59E0B",
  CRITICAL: "#EF4444",
} as const;

export function Hotspot({ position, status, onClick }: Props) {
  const ref = useRef<THREE.Mesh>(null!);

  // Breathing / pulsing scale animation
  useFrame(({ clock }) => {
    if (!ref.current) return;
    const t     = clock.getElapsedTime();
    const speed = status === "CRITICAL" ? 4 : 2;
    const s     = 1 + 0.25 * Math.sin(t * speed);
    ref.current.scale.setScalar(s);
  });

  const color = STATUS_COLOR[status];

  // Hotspot floats above the element's top face
  const floatY = 1.2;

  return (
    <Sphere
      ref={ref}
      args={[0.18, 12, 12]}
      position={[position[0], position[1] + floatY, position[2]]}
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      castShadow
    >
      <meshStandardMaterial
        color={color}
        emissive={new THREE.Color(color)}
        emissiveIntensity={1.2}
        transparent
        opacity={0.9}
      />
    </Sphere>
  );
}
