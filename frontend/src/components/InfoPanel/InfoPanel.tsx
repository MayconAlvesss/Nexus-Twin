/**
 * InfoPanel — Element detail side panel
 * =======================================
 * Glassmorphism floating panel that slides in from the right when an
 * element is selected in the 3D scene.
 *
 * Displays:
 *   - Element metadata (ID, type, material, age, floor)
 *   - SHI score ring (CSS animated arc)
 *   - Sub-score breakdown table
 *   - SHI trend line chart (Recharts)
 *   - Recent anomaly event list
 *   - PDF report download button
 */

import { useState }   from "react";
import {
  LineChart, Line, CartesianGrid, XAxis, YAxis,
  Tooltip, ResponsiveContainer, ReferenceLine
} from "recharts";

import {
  useElementDetail,
  useSHIHistory,
  useAnomalyLog,
  statusToColor,
} from "../../hooks/useElementHealth";
import { fetchReportUrl } from "../../api/client";
import styles              from "./InfoPanel.module.css";

interface Props {
  elementId: string | null;
  onClose:   () => void;
}

export function InfoPanel({ elementId, onClose }: Props) {
  const { data: detail,   isLoading: loadingDetail }  = useElementDetail(elementId);
  const { data: history,  isLoading: loadingHistory } = useSHIHistory(elementId);
  const { data: anomalog, isLoading: loadingAnomaly } = useAnomalyLog(elementId);
  const [downloading, setDownloading] = useState(false);

  if (!elementId) return null;

  const el     = detail?.element;
  const shi    = detail?.latest_shi;
  const events = anomalog?.anomalies ?? [];

  // Chart data — reverse history so it's chronological (oldest left)
  const chartData = (history?.history ?? [])
    .slice()
    .reverse()
    .map((h, i) => ({ t: i + 1, shi: Number(h.shi_score.toFixed(1)) }));

  const statusColor = statusToColor(shi?.status);

  async function handleDownloadPDF() {
    try {
      setDownloading(true);
      const url = await fetchReportUrl(elementId!);
      const a   = document.createElement("a");
      a.href     = url;
      a.download = `NexusTwin_Report_${elementId}.pdf`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    } catch (err) {
      console.error("PDF download failed:", err);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <aside className={styles.panel}>
      {/* Close button */}
      <button className={styles.closeBtn} onClick={onClose} aria-label="Close panel">✕</button>

      {/* ── Title ── */}
      <div className={styles.titleRow}>
        <span className={styles.dot} style={{ background: statusColor, boxShadow: `0 0 8px ${statusColor}` }} />
        <div>
          <h2 className={styles.elementId}>{elementId}</h2>
          {el && <p className={styles.elementName}>{el.name}</p>}
        </div>
      </div>

      {loadingDetail ? (
        <p className={styles.loading}>Loading health data…</p>
      ) : (
        <>
          {/* ── SHI Score ring ── */}
          {shi && (
            <div className={styles.shiRing} style={{ "--status-color": statusColor } as React.CSSProperties}>
              <svg viewBox="0 0 80 80" className={styles.ringsvg}>
                <circle cx="40" cy="40" r="32" stroke="#1e293b" strokeWidth="8" fill="none" />
                <circle
                  cx="40" cy="40" r="32"
                  stroke={statusColor}
                  strokeWidth="8"
                  fill="none"
                  strokeDasharray={`${(shi.shi_score / 100) * 201} 201`}
                  strokeLinecap="round"
                  transform="rotate(-90 40 40)"
                  style={{ filter: `drop-shadow(0 0 6px ${statusColor})` }}
                />
              </svg>
              <div className={styles.ringLabel}>
                <span className={styles.ringScore}>{shi.shi_score.toFixed(1)}</span>
                <span className={styles.ringStatus} style={{ color: statusColor }}>{shi.status}</span>
              </div>
            </div>
          )}

          {/* ── Metadata table ── */}
          {el && (
            <table className={styles.metaTable}>
              <tbody>
                <tr><td>Type</td><td>{el.element_type}</td></tr>
                <tr><td>Material</td><td>{el.material_class}</td></tr>
                <tr><td>Age</td><td>{el.age_years.toFixed(1)} yrs</td></tr>
                <tr><td>Floor</td><td>{el.floor_level ?? "N/A"}</td></tr>
              </tbody>
            </table>
          )}

          {/* ── Sub-score bars ── */}
          {shi && (
            <div className={styles.subscores}>
              <h3 className={styles.sectionTitle}>Sub-Scores</h3>
              {[
                { label: "Strain",      val: shi.strain_score,      weight: "35%" },
                { label: "Vibration",   val: shi.vibration_score,   weight: "25%" },
                { label: "Fatigue",     val: shi.fatigue_score,     weight: "25%" },
                { label: "Temperature", val: shi.temperature_score, weight: "15%" },
              ].map((s) => (
                <div key={s.label} className={styles.scoreRow}>
                  <span className={styles.scoreLabel}>{s.label}</span>
                  <div className={styles.scoreBar}>
                    <div
                      className={styles.scoreFill}
                      style={{
                        width: `${s.val}%`,
                        background: s.val >= 75 ? "#10B981" : s.val >= 40 ? "#F59E0B" : "#EF4444",
                      }}
                    />
                  </div>
                  <span className={styles.scoreVal}>{s.val.toFixed(0)}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* ── SHI Trend Chart ── */}
      <div className={styles.chartSection}>
        <h3 className={styles.sectionTitle}>SHI Trend</h3>
        {loadingHistory ? (
          <p className={styles.loading}>Loading chart…</p>
        ) : chartData.length > 1 ? (
          <ResponsiveContainer width="100%" height={130}>
            <LineChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
              <XAxis dataKey="t" tick={{ fontSize: 9, fill: "#64748b" }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 9, fill: "#64748b" }} />
              <Tooltip
                contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 6 }}
                labelStyle={{ color: "#94a3b8" }}
                itemStyle={{ color: "#60a5fa" }}
              />
              <ReferenceLine y={65} stroke="#F59E0B" strokeDasharray="4 4" />
              <ReferenceLine y={40} stroke="#EF4444" strokeDasharray="4 4" />
              <Line
                type="monotone"
                dataKey="shi"
                stroke="#60a5fa"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <p className={styles.loading}>No trend data yet. Run a simulation first.</p>
        )}
      </div>

      {/* ── Anomaly log ── */}
      <div className={styles.anomalySection}>
        <h3 className={styles.sectionTitle}>
          Recent Anomalies
          {events.length > 0 && <span className={styles.anomalyBadge}>{events.length}</span>}
        </h3>
        {loadingAnomaly ? (
          <p className={styles.loading}>Loading…</p>
        ) : events.length === 0 ? (
          <p className={styles.empty}>No anomalies recorded.</p>
        ) : (
          <div className={styles.anomalyList}>
            {events.map((ev) => (
              <div key={ev.id} className={styles.anomalyItem}>
                <span
                  className={styles.anomalySev}
                  style={{ color: ev.severity === "CRITICAL" ? "#EF4444" : ev.severity === "HIGH" ? "#F97316" : "#F59E0B" }}
                >
                  {ev.severity}
                </span>
                <span className={styles.anomalyDesc}>{ev.description}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── PDF Button ── */}
      <button
        className={styles.pdfBtn}
        onClick={handleDownloadPDF}
        disabled={downloading}
      >
        {downloading ? "Generating…" : "⬇ Download PDF Report"}
      </button>
    </aside>
  );
}
