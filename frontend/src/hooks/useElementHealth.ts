/**
 * useElementHealth hook
 * =====================
 * Fetches the latest SHI snapshot and full SHI history for a specific
 * element. Designed to be called lazily — only when an element is
 * selected or hovered — to avoid unnecessary API calls at startup.
 */

import { useQuery } from "@tanstack/react-query";
import { fetchElement, fetchSHIHistory, fetchAnomalyLog } from "../api/client";

export function useElementDetail(elementId: string | null) {
  return useQuery({
    queryKey: ["element-detail", elementId],
    queryFn:  () => fetchElement(elementId!),
    enabled:  !!elementId,
    staleTime: 15_000,
  });
}

export function useSHIHistory(elementId: string | null) {
  return useQuery({
    queryKey: ["shi-history", elementId],
    queryFn:  () => fetchSHIHistory(elementId!, 30),
    enabled:  !!elementId,
    staleTime: 15_000,
  });
}

export function useAnomalyLog(elementId: string | null) {
  return useQuery({
    queryKey: ["anomaly-log", elementId],
    queryFn:  () => fetchAnomalyLog(elementId!, 10),
    enabled:  !!elementId,
    staleTime: 15_000,
  });
}

// ── Derived helpers ───────────────────────────────────────────────────────────

/** Maps a SHI status string to a CSS hex colour. */
export function statusToColor(status?: string): string {
  switch (status?.toUpperCase()) {
    case "HEALTHY":  return "#10B981";  // emerald
    case "WARNING":  return "#F59E0B";  // amber
    case "CRITICAL": return "#EF4444";  // red
    default:         return "#64748b";  // slate
  }
}

/** Maps a SHI score (0–100) to a friendly label. */
export function shiLabel(score?: number): string {
  if (score === undefined || score === null) return "No data";
  if (score >= 75) return "Healthy";
  if (score >= 40) return "Warning";
  return "Critical";
}
