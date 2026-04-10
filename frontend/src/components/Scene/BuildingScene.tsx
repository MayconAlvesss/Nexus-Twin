/**
 * BuildingScene — React Three Fiber scene root
 * =============================================
 * Assembles the full 3D structural scene:
 *   - Background gradient environment
 *   - Directional + ambient lighting
 *   - Ground plane mesh
 *   - Grid of structural element meshes (from the API)
 *   - Animated hotspot markers for Warning/Critical elements
 *   - OrbitControls for camera pan/zoom/rotate
 *
 * All element data comes from the useElements() hook which polls the
 * NexusTwin API, so the scene stays live without a page refresh.
 */

import { Suspense }                           from "react";
import { Canvas }                             from "@react-three/fiber";
import { OrbitControls, Environment, Grid }  from "@react-three/drei";

import { useElements }      from "../../hooks/useElements";
import { useElementDetail } from "../../hooks/useElementHealth";
import { StructuralElement } from "../Element/StructuralElement";
import { Hotspot }           from "../Element/Hotspot";

interface Props {
  selectedId:  string | null;
  onSelect:    (id: string) => void;
}

// ── Hotspot wrapper — fetches element health to decide if marker needed ───────

function HotspotLayer({
  elementId,
  position,
  onSelect,
}: {
  elementId: string;
  position:  [number, number, number];
  onSelect:  (id: string) => void;
}) {
  const { data: detail } = useElementDetail(elementId);
  const status = detail?.latest_shi?.status;

  if (status !== "WARNING" && status !== "CRITICAL") return null;

  return (
    <Hotspot
      position={position}
      status={status}
      onClick={() => onSelect(elementId)}
    />
  );
}

// ── Scene content (inside Suspense) ─────────────────────────────────────────

function SceneContent({ selectedId, onSelect }: Props) {
  const { data: elements = [], isLoading } = useElements();

  if (isLoading) return null;

  return (
    <>
      {/* Structural elements */}
      {elements.map((el) => (
        <StructuralElement
          key={el.element_id}
          element={el}
          isSelected={selectedId === el.element_id}
          onClick={onSelect}
        />
      ))}

      {/* Hotspot markers on top of each element */}
      {elements.map((el) => (
        <HotspotLayer
          key={`hotspot-${el.element_id}`}
          elementId={el.element_id}
          position={el.position}
          onSelect={onSelect}
        />
      ))}
    </>
  );
}

// ── Export ───────────────────────────────────────────────────────────────────

export function BuildingScene({ selectedId, onSelect }: Props) {
  return (
    <Canvas
      shadows
      camera={{ position: [12, 10, 18], fov: 52 }}
      style={{ background: "transparent" }}
      gl={{ antialias: true }}
    >
      {/* Lighting */}
      <ambientLight intensity={0.4} />
      <directionalLight
        position={[10, 20, 10]}
        intensity={1.2}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
      />
      <pointLight position={[-8, 8, -8]} intensity={0.5} color="#4F97FF" />

      {/* Environment preset for realistic reflections */}
      <Environment preset="city" />

      {/* Ground grid */}
      <Grid
        renderOrder={-1}
        args={[30, 30]}
        position={[0, -0.52, 0]}
        cellColor="#334155"
        sectionColor="#1e40af"
        sectionThickness={0.8}
        fadeDistance={40}
      />

      {/* Scene objects */}
      <Suspense fallback={null}>
        <SceneContent selectedId={selectedId} onSelect={onSelect} />
      </Suspense>

      {/* Camera controls */}
      <OrbitControls
        makeDefault
        enableDamping
        dampingFactor={0.06}
        minDistance={4}
        maxDistance={50}
        maxPolarAngle={Math.PI / 2.1}
      />
    </Canvas>
  );
}
