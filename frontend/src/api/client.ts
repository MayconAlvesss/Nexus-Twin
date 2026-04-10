/**
 * NexusTwin API Client
 * ====================
 * Typed fetch wrapper that authenticates all requests to the FastAPI
 * backend with the X-NexusTwin-API-Key header.
 *
 * Base URL and API key are read from Vite environment variables so the
 * client works in development (localhost) and in any deployed environment
 * by swapping the .env values without touching source code.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const API_KEY  = import.meta.env.VITE_API_KEY ?? "";

// ── Shared fetch helper ──────────────────────────────────────────────────────

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-NexusTwin-API-Key": API_KEY,
      ...(options.headers ?? {}),
    },
  });

  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText} (${path})`);
  }

  return res.json() as Promise<T>;
}

// ── Public API functions ─────────────────────────────────────────────────────

/** Returns the full list of registered elements from the element registry. */
export async function fetchAllElements(): Promise<ElementListResponse> {
  return apiFetch<ElementListResponse>("/api/v1/elements");
}

/** Returns a single element's detail and its most recent SHI snapshot. */
export async function fetchElement(elementId: string): Promise<ElementDetailResponse> {
  return apiFetch<ElementDetailResponse>(`/api/v1/elements/${elementId}`);
}

/** Returns the SHI history for an element (newest-first). */
export async function fetchSHIHistory(
  elementId: string,
  limit = 30
): Promise<SHIHistoryResponse> {
  return apiFetch<SHIHistoryResponse>(
    `/api/v1/health/${elementId}/history?limit=${limit}`
  );
}

/** Returns the anomaly log for an element. */
export async function fetchAnomalyLog(
  elementId: string,
  limit = 20
): Promise<AnomalyLogResponse> {
  return apiFetch<AnomalyLogResponse>(
    `/api/v1/anomaly/${elementId}/log?limit=${limit}`
  );
}

/** Triggers a PDF report download for an element. Returns a blob URL. */
export async function fetchReportUrl(elementId: string): Promise<string> {
  const res = await fetch(`${BASE_URL}/api/v1/report/${elementId}`, {
    headers: { "X-NexusTwin-API-Key": API_KEY },
  });
  if (!res.ok) throw new Error(`Report fetch failed: ${res.status}`);
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

// ── API Response Types ───────────────────────────────────────────────────────

export interface RawElement {
  element_id:     string;
  name:           string;
  element_type:   string;  // "COLUMN" | "BEAM" | "SLAB" | "WALL" | "FOUNDATION"
  material_class: string;
  age_years:      number;
  floor_level:    string | null;
}

export interface SHISnapshot {
  shi_score:         number;
  strain_score:      number;
  vibration_score:   number;
  fatigue_score:     number;
  temperature_score: number;
  status:            "HEALTHY" | "WARNING" | "CRITICAL";
  recorded_at:       string;
}

export interface ElementListResponse {
  count:    number;
  elements: RawElement[];
}

export interface ElementDetailResponse {
  element:    RawElement;
  latest_shi: SHISnapshot | null;
}

export interface SHIHistoryResponse {
  element_id: string;
  count:      number;
  history:    SHISnapshot[];
}

export interface AnomalyEvent {
  id:          number;
  sensor_type: string;
  severity:    string;
  value:       number;
  description: string;
  detected_at: string;
}

export interface AnomalyLogResponse {
  element_id: string;
  count:      number;
  anomalies:  AnomalyEvent[];
}
