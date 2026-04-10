/**
 * StructuralElement — 3D mesh component
 * ======================================
 * Renders a single structural element as a Three.js BoxGeometry mesh.
 *
 * Health color:
 *   The element's SHI status is fetched lazily on mount and used to
 *   tint the material's emissive channel, giving a "glowing" health 
 *   indicator effect in the dark scene.
 *
 * Interactivity:
 *   - onPointerOver: camera-hint cursor + subtle scale
 *   - onPointerOut:  resets scale
 *   - onClick:       selects element → triggers InfoPanel
 */

import { useRef, useState } from "react";
import { useFrame }          from "@react-three/fiber";
import { Text }              from "@react-three/drei";
import * as THREE            from "three";

import { type SceneElement }                    from "../../hooks/useElements";
import { useElementDetail, statusToColor }      from "../../hooks/useElementHealth";

interface Props {
  element:    SceneElement;
  isSelected: boolean;
  onClick:    (id: string) => void;
}

export function StructuralElement({ element, isSelected, onClick }: Props) {
  const meshRef  = useRef<THREE.Mesh>(null!);
  const [hovered, setHovered] = useState(false);

  // Lazily fetch the latest SHI for this element (only runs once per element)
  const { data: detail } = useElementDetail(element.element_id);
  const latestSHI = detail?.latest_shi;
  const shiColor  = statusToColor(latestSHI?.status);
  const shiScore  = latestSHI?.shi_score;

  // Subtle breathe animation for critical elements
  useFrame(({ clock }) => {
    if (!meshRef.current) return;
    const isCritical = latestSHI?.status === "CRITICAL";

    if (isCritical) {
      // Pulsing emissive brightness for critical elements
      const pulse = 0.3 + 0.2 * Math.sin(clock.getElapsedTime() * 3);
      (meshRef.current.material as THREE.MeshStandardMaterial).emissiveIntensity = pulse;
    }

    // Scale feedback on hover / selection
    const targetScale = isSelected ? 1.08 : hovered ? 1.04 : 1.0;
    meshRef.current.scale.lerp(
      new THREE.Vector3(targetScale, targetScale, targetScale),
      0.12
    );
  });

  const emissiveColor = new THREE.Color(shiColor);

  return (
    <group position={element.position}>
      {/* Main structural mesh */}
      <mesh
        ref={meshRef}
        castShadow
        receiveShadow
        onClick={(e) => { e.stopPropagation(); onClick(element.element_id); }}
        onPointerOver={(e) => { e.stopPropagation(); setHovered(true); document.body.style.cursor = "pointer"; }}
        onPointerOut={() => { setHovered(false); document.body.style.cursor = "default"; }}
      >
        <boxGeometry args={element.size} />
        <meshStandardMaterial
          color={hovered || isSelected ? "#FFFFFF" : "#1e293b"}
          emissive={emissiveColor}
          emissiveIntensity={isSelected ? 0.6 : 0.25}
          roughness={0.4}
          metalness={0.6}
        />
      </mesh>

      {/* SHI score badge floating above element */}
      {shiScore !== undefined && (
        <Text
          position={[0, element.size[1] / 2 + 0.5, 0]}
          fontSize={0.35}
          color={shiColor}
          anchorX="center"
          anchorY="middle"
          fontWeight="bold"
        >
          {`${shiScore.toFixed(0)}`}
        </Text>
      )}
    </group>
  );
}
