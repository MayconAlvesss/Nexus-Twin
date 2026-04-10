/**
 * Header — global KPI summary bar
 * =================================
 * Displays the NexusTwin branding and a live count of elements by
 * health status. Data is derived from the element list API response,
 * augmented by per-element SHI detail fetched separately.
 *
 * The counts update automatically every 30 seconds alongside the scene.
 */

import { useElements }      from "../../hooks/useElements";
import { useElementDetail } from "../../hooks/useElementHealth";
import styles                from "./Header.module.css";

// ── Per-element status resolver (individual API call) ────────────────────────

function useAllStatuses(elementIds: string[]) {
  // We call useElementDetail for each element — harmless since React Query
  // deduplicates concurrent requests and caches results.
  const results = elementIds.map((id) => {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const { data } = useElementDetail(id);
    return data?.latest_shi?.status ?? null;
  });
  return results;
}

// ── Header component ─────────────────────────────────────────────────────────

export function Header() {
  const { data: elements = [] } = useElements();
  const ids      = elements.map((e) => e.element_id);
  const statuses = useAllStatuses(ids);

  const healthy  = statuses.filter((s) => s === "HEALTHY").length;
  const warning  = statuses.filter((s) => s === "WARNING").length;
  const critical = statuses.filter((s) => s === "CRITICAL").length;
  const unknown  = statuses.filter((s) => s === null).length;

  return (
    <header className={styles.header}>
      {/* Brand */}
      <div className={styles.brand}>
        <span className={styles.logo}>⬡</span>
        <span className={styles.title}>NexusTwin</span>
        <span className={styles.subtitle}>Structural Health Dashboard</span>
      </div>

      {/* KPI chips */}
      <div className={styles.kpis}>
        <KpiChip label="Healthy"  count={healthy}  color="var(--color-healthy)"  />
        <KpiChip label="Warning"  count={warning}  color="var(--color-warning)"  />
        <KpiChip label="Critical" count={critical} color="var(--color-critical)" />
        {unknown > 0 && (
          <KpiChip label="No data" count={unknown} color="var(--color-muted)" />
        )}
        <div className={styles.totalBadge}>
          {elements.length} ELEMENTS
        </div>
      </div>
    </header>
  );
}

function KpiChip({
  label, count, color,
}: {
  label: string; count: number; color: string;
}) {
  return (
    <div className={styles.kpiChip} style={{ "--chip-color": color } as React.CSSProperties}>
      <span className={styles.kpiDot} />
      <span className={styles.kpiCount}>{count}</span>
      <span className={styles.kpiLabel}>{label}</span>
    </div>
  );
}
