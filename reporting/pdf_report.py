"""
NexusTwin — PDF Report Generator
==================================
Generates a professional multi-page PDF health report for a single
structural element. The output is a bytes object (in-memory) — no
temporary files are written to disk.

Report structure:
  Page 1 — Cover + KPI summary (SHI score, status, anomaly count)
  Page 2 — SHI trend chart (matplotlib embedded as PNG)
  Page 3 — Sub-score breakdown table
  Page 4 — Anomaly event log table
  Page 5 — Recommendations section

Technology:
  ReportLab for layout and tables (same as EcoBIM's PDF engine).
  Matplotlib for charts — figures are rendered to BytesIO buffers and
  embedded as images, avoiding any disk I/O.

References:
  - ReportLab User Guide v3.6
  - EcoBIM lab/reports/run_wlca_report.py (architecture reference)
"""

import io
import logging
from datetime import datetime, timezone
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # non-interactive backend (no display required)
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from reportlab.lib         import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units   import mm
from reportlab.lib.styles  import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums   import TA_CENTER, TA_LEFT
from reportlab.platypus    import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Colour palette (follows the NexusTwin brand: dark teal + amber accents)
# ---------------------------------------------------------------------------
COLOUR_PRIMARY    = colors.HexColor("#0D3B4E")   # dark teal / header bg
COLOUR_ACCENT     = colors.HexColor("#F59E0B")   # amber — alert / highlight
COLOUR_HEALTHY    = colors.HexColor("#10B981")   # green
COLOUR_WARNING    = colors.HexColor("#F59E0B")   # amber
COLOUR_CRITICAL   = colors.HexColor("#EF4444")   # red
COLOUR_BG_LIGHT   = colors.HexColor("#F0F4F8")   # table alt row
COLOUR_WHITE      = colors.white

STATUS_COLOUR_MAP = {
    "HEALTHY":  COLOUR_HEALTHY,
    "WARNING":  COLOUR_WARNING,
    "CRITICAL": COLOUR_CRITICAL,
}


def _status_colour(status: str) -> colors.Color:
    return STATUS_COLOUR_MAP.get(status.upper(), colors.grey)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_element_report(
    element:    dict,
    history:    list[dict],
    anomalies:  list[dict],
    latest_shi: Optional[dict],
) -> bytes:
    """
    Build the complete PDF report and return it as raw bytes.

    Parameters:
        element    — element dict from TwinDBManager.get_element()
        history    — SHI history list (newest-first from DB)
        anomalies  — anomaly log entries (newest-first from DB)
        latest_shi — the most recent SHI snapshot (or None)

    Returns:
        bytes — the complete PDF file content
    """
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=20*mm,
        bottomMargin=20*mm,
        title=f"NexusTwin Health Report — {element['element_id']}",
        author="NexusTwin Structural Monitoring System",
    )

    styles = getSampleStyleSheet()
    story  = []

    # ------------------------------------------------------------------
    # Cover / KPI section
    # ------------------------------------------------------------------
    story += _build_cover(element, latest_shi, len(anomalies), styles)

    # ------------------------------------------------------------------
    # SHI trend chart
    # ------------------------------------------------------------------
    chart_image = _build_trend_chart(history, element["element_id"])
    if chart_image:
        story.append(Paragraph("SHI Trend (last 100 snapshots)", _heading2(styles)))
        story.append(Spacer(1, 4*mm))
        story.append(chart_image)
        story.append(Spacer(1, 8*mm))

    # ------------------------------------------------------------------
    # Sub-score breakdown table (from most recent snapshot)
    # ------------------------------------------------------------------
    if latest_shi:
        story.append(Paragraph("Latest Sub-Score Breakdown", _heading2(styles)))
        story.append(Spacer(1, 4*mm))
        story.append(_build_subscores_table(latest_shi, styles))
        story.append(Spacer(1, 8*mm))

    # ------------------------------------------------------------------
    # Anomaly event log
    # ------------------------------------------------------------------
    story.append(Paragraph("Anomaly Event Log", _heading2(styles)))
    story.append(Spacer(1, 4*mm))
    story.append(_build_anomaly_table(anomalies, styles))
    story.append(Spacer(1, 8*mm))

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------
    story.append(Paragraph("Recommendations", _heading2(styles)))
    story.append(Spacer(1, 4*mm))
    story += _build_recommendations(latest_shi, len(anomalies), styles)

    # ------------------------------------------------------------------
    # Footer disclaimer
    # ------------------------------------------------------------------
    story.append(Spacer(1, 12*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        "This report was generated automatically by NexusTwin v1.0.0. "
        "Results are based on sensor data and computational models. "
        "A qualified structural engineer should review findings before "
        "any remediation action is taken.",
        ParagraphStyle("Disclaimer", parent=styles["Normal"], fontSize=7, textColor=colors.grey),
    ))

    doc.build(story)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Private section builders
# ---------------------------------------------------------------------------

def _heading2(styles) -> ParagraphStyle:
    return ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        textColor=COLOUR_PRIMARY,
        spaceBefore=6,
    )


def _build_cover(
    element: dict,
    latest_shi: Optional[dict],
    anomaly_count: int,
    styles,
) -> list:
    """Build the report header / KPI summary block."""
    story = []

    # Title bar
    story.append(Paragraph(
        "NexusTwin — Structural Health Report",
        ParagraphStyle(
            "Cover",
            parent=styles["Title"],
            textColor=COLOUR_PRIMARY,
            fontSize=22,
            alignment=TA_CENTER,
        ),
    ))
    story.append(Spacer(1, 2*mm))
    story.append(HRFlowable(width="100%", thickness=2, color=COLOUR_ACCENT))
    story.append(Spacer(1, 6*mm))

    # Element metadata table
    meta_data = [
        ["Element ID",     element.get("element_id", "--")],
        ["Name",           element.get("name", "--")],
        ["Type",           element.get("element_type", "--")],
        ["Material Class", element.get("material_class", "--").capitalize()],
        ["Age",            f"{element.get('age_years', 0.0):.1f} years"],
        ["Floor Level",    element.get("floor_level") or "N/A"],
        ["Report Date",    datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")],
    ]
    meta_table = Table(meta_data, colWidths=[50*mm, 110*mm])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (0, -1), COLOUR_PRIMARY),
        ("TEXTCOLOR",    (0, 0), (0, -1), COLOUR_WHITE),
        ("FONTNAME",     (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE",     (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (1, 0), (1, -1), [COLOUR_WHITE, COLOUR_BG_LIGHT]),
        ("GRID",         (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 8*mm))

    # KPI highlight row
    shi_score = latest_shi["shi_score"] if latest_shi else "N/A"
    shi_status = latest_shi["status"] if latest_shi else "UNKNOWN"
    kpi_data = [
        [
            Paragraph(f"<b>{shi_score}</b><br/>SHI Score", _kpi_style(styles, shi_status)),
            Paragraph(f"<b>{shi_status}</b><br/>Status",   _kpi_style(styles, shi_status)),
            Paragraph(f"<b>{anomaly_count}</b><br/>Anomalies", _kpi_style(styles, "HEALTHY")),
        ]
    ]
    kpi_table = Table(kpi_data, colWidths=[55*mm, 55*mm, 55*mm])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), COLOUR_PRIMARY),
        ("TEXTCOLOR",    (0, 0), (-1, -1), COLOUR_WHITE),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE",     (0, 0), (-1, -1), 14),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ("BOX",          (0, 0), (-1, -1), 1, COLOUR_ACCENT),
        ("LINEBEFORE",   (1, 0), (2, 0), 0.5, COLOUR_ACCENT),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 10*mm))
    return story


def _kpi_style(styles, status: str) -> ParagraphStyle:
    return ParagraphStyle(
        f"KPI_{status}",
        parent=styles["Normal"],
        textColor=COLOUR_WHITE,
        fontSize=13,
        alignment=TA_CENTER,
    )


def _build_trend_chart(history: list[dict], element_id: str) -> Optional[Image]:
    """
    Render the SHI trend line chart using matplotlib and return a
    ReportLab Image object (embedded as PNG in the PDF).
    """
    if not history:
        return None

    # history is newest-first from DB — reverse for chronological plot
    records = list(reversed(history[:100]))
    scores  = [r["shi_score"] for r in records]
    labels  = list(range(len(scores)))

    fig, ax = plt.subplots(figsize=(10, 3.5), dpi=120)
    ax.set_facecolor("#F8FAFC")
    fig.patch.set_facecolor("#F8FAFC")

    # Shade danger zones
    ax.axhspan(0,  40,  alpha=0.12, color="red",    label=None)
    ax.axhspan(40, 65,  alpha=0.08, color="orange",  label=None)
    ax.axhspan(65, 100, alpha=0.05, color="green",   label=None)

    ax.plot(labels, scores, color="#0D3B4E", linewidth=2, marker="o", markersize=3)
    ax.axhline(65, color="orange", linestyle="--", linewidth=1, label="Warning (65)")
    ax.axhline(40, color="red",    linestyle="--", linewidth=1, label="Critical (40)")

    ax.set_ylim(0, 105)
    ax.set_xlabel("Snapshot index (chronological)", fontsize=9, color="#555")
    ax.set_ylabel("SHI Score",                      fontsize=9, color="#555")
    ax.set_title(f"SHI Trend — {element_id}",       fontsize=11, color="#0D3B4E", fontweight="bold")
    ax.legend(fontsize=8, loc="lower right")
    ax.tick_params(labelsize=8)
    ax.grid(axis="y", alpha=0.3)

    img_buf = io.BytesIO()
    fig.savefig(img_buf, format="png", bbox_inches="tight")
    plt.close(fig)
    img_buf.seek(0)

    return Image(img_buf, width=170*mm, height=60*mm)


def _build_subscores_table(latest_shi: dict, styles) -> Table:
    """Render the sub-score breakdown as a formatted table."""
    headers = ["Channel", "Sub-Score (/100)", "Weight"]
    rows = [
        ["Strain",      f"{latest_shi.get('strain_score', '--'):.1f}",      "35%"],
        ["Vibration",   f"{latest_shi.get('vibration_score', '--'):.1f}",   "25%"],
        ["Fatigue",     f"{latest_shi.get('fatigue_score', '--'):.1f}",     "25%"],
        ["Temperature", f"{latest_shi.get('temperature_score', '--'):.1f}", "15%"],
        ["Overall SHI", f"{latest_shi.get('shi_score', '--'):.2f}",         "100%"],
    ]
    data = [headers] + rows
    t = Table(data, colWidths=[60*mm, 60*mm, 45*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), COLOUR_PRIMARY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), COLOUR_WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS",(0, 1), (-1, -2), [COLOUR_WHITE, COLOUR_BG_LIGHT]),
        ("BACKGROUND",    (0, -1), (-1, -1), colors.HexColor("#E0EAF0")),
        ("FONTNAME",      (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN",         (1, 0), (-1, -1), "CENTER"),
        ("GRID",          (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _build_anomaly_table(anomalies: list[dict], styles) -> Table:
    """Render the anomaly log as a table with severity colour coding."""
    if not anomalies:
        return Table([["No anomalies have been recorded for this element."]])

    headers = ["Timestamp", "Sensor", "Severity", "Value", "Description"]
    rows = []
    for a in anomalies[:20]:  # cap at 20 rows to keep the PDF readable
        rows.append([
            str(a.get("detected_at", "--"))[:19],
            str(a.get("sensor_type", "--")),
            str(a.get("severity", "--")),
            str(a.get("value", "--")),
            str(a.get("description", "--"))[:80],
        ])

    data = [headers] + rows
    col_widths = [38*mm, 22*mm, 22*mm, 18*mm, 65*mm]
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style_commands = [
        ("BACKGROUND",    (0, 0), (-1, 0), COLOUR_PRIMARY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), COLOUR_WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [COLOUR_WHITE, COLOUR_BG_LIGHT]),
        ("GRID",          (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("WORDWRAP",      (4, 1), (4, -1), True),
    ]
    # Colour-code severity column
    severity_col = 2
    for i, row in enumerate(rows, start=1):
        sev = row[severity_col].upper()
        if sev in STATUS_COLOUR_MAP:
            style_commands.append(
                ("TEXTCOLOR", (severity_col, i), (severity_col, i), _status_colour(sev))
            )
            style_commands.append(
                ("FONTNAME", (severity_col, i), (severity_col, i), "Helvetica-Bold")
            )
    t.setStyle(TableStyle(style_commands))
    return t


def _build_recommendations(
    latest_shi: Optional[dict],
    anomaly_count: int,
    styles,
) -> list:
    """Generate context-aware textual recommendations."""
    items = []
    shi   = latest_shi["shi_score"] if latest_shi else 100.0
    status = latest_shi["status"] if latest_shi else "UNKNOWN"

    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"], fontSize=10, leading=16
    )

    if shi >= 80:
        items.append("✅ Structure is operating within normal parameters. Continue routine monitoring at the scheduled interval.")
    elif shi >= 65:
        items.append("🟡 Minor deviations detected. Increase sensor polling frequency to every 30 minutes until conditions stabilise.")
    elif shi >= 40:
        items.append("🟠 Elevated stress levels detected. Schedule a physical inspection within 30 days.")
        items.append("   — Pay particular attention to the sub-channels with the lowest sub-scores.")
    else:
        items.append("🔴 CRITICAL: Multiple channels are outside safe operating limits.")
        items.append("   — Notify the responsible structural engineer immediately.")
        items.append("   — Consider temporary load reduction or access restriction.")

    if anomaly_count > 0:
        items.append(f"⚠️ {anomaly_count} anomaly event(s) have been logged. Review the anomaly table and investigate any CRITICAL or HIGH severity events.")

    return [Paragraph(item, body_style) for item in items]
