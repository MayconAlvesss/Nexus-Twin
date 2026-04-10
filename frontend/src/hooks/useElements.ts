/**
 * useElements hook
 * ================
 * Fetches the full element list from the NexusTwin API and provides
 * enriched element objects ready for the 3D scene.
 *
 * We derive a 3D position for each element based on its type and a
 * simple grid layout so the scene makes structural sense without
 * needing a real IFC model.
 */

import { useQuery } from "@tanstack/react-query";
import { fetchAllElements, type RawElement } from "../api/client";

export interface SceneElement extends RawElement {
  /** World-space position for the Three.js mesh */
  position: [number, number, number];
  /** Geometry dimensions [w, h, d] */
  size:     [number, number, number];
  /** Pre-computed hex colour string from the SHI status */
  color:    string;
}

// ── Deterministic layout engine ──────────────────────────────────────────────
// Position elements in a 4×4 structural grid based on element type.
// This is a simple approximation — a real app would parse IFC geometry.

const GRID_SPACING = 6;   // metres between grid nodes

function derivePosition(el: RawElement, index: number): [number, number, number] {
  const col  = index % 4;
  const row  = Math.floor(index / 4);
  const x    = col * GRID_SPACING - 9;
  const z    = row * GRID_SPACING - 6;

  const typeUpper = el.element_type.toUpperCase();
  if (typeUpper === "SLAB" || typeUpper === "FOUNDATION") {
    return [x, -0.15, z];
  }
  if (typeUpper === "BEAM") {
    return [x, 3.5, z];
  }
  // COLUMN / WALL / default
  return [x, 1.75, z];
}

function deriveSize(el: RawElement): [number, number, number] {
  const typeUpper = el.element_type.toUpperCase();
  if (typeUpper === "COLUMN")     return [0.5, 3.5, 0.5];
  if (typeUpper === "BEAM")       return [5.0, 0.4, 0.4];
  if (typeUpper === "SLAB")       return [5.5, 0.3, 5.5];
  if (typeUpper === "WALL")       return [5.0, 3.5, 0.3];
  if (typeUpper === "FOUNDATION") return [5.5, 0.5, 5.5];
  return [1, 1, 1];
}

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useElements() {
  return useQuery({
    queryKey: ["elements"],
    queryFn:  fetchAllElements,
    refetchInterval: 30_000,  // refresh every 30 s for near-real-time updates
    select: (data) =>
      data.elements.map((el, i): SceneElement => ({
        ...el,
        position: derivePosition(el, i),
        size:     deriveSize(el),
        color:    "#64748b",  // neutral grey until SHI data loads per-element
      })),
  });
}
