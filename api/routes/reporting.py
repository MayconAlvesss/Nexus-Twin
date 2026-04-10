"""
NexusTwin — PDF Reporting Router
===================================
Triggers the generation of a professional PDF health report for a given
structural element based on its full SHI history.

Endpoints:
  GET /api/v1/report/{element_id}   — generate and stream the PDF report
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from api.dependencies import get_db, verified_api_key
from database.twin_db import TwinDBManager
from reporting.pdf_report import generate_element_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/report", tags=["PDF Reporting"])


@router.get(
    "/{element_id}",
    summary="Generate and download a PDF health report",
    response_class=StreamingResponse,
    dependencies=[Depends(verified_api_key)],
)
async def download_report(
    element_id: str,
    db: TwinDBManager = Depends(get_db),
) -> StreamingResponse:
    """
    Generates a professional multi-page PDF report for the element including:
      - Cover page with KPIs (current SHI, status, anomaly count)
      - SHI trend chart (matplotlib)
      - Latest sub-score breakdown
      - Anomaly event table
      - Recommendations section

    The report is streamed directly to the caller as a binary PDF response.
    No file is written to disk — everything is generated in-memory.
    """
    element = await db.get_element(element_id)
    if not element:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Element '{element_id}' not found.",
        )

    history  = await db.get_shi_history(element_id, limit=1000)
    anomalies = await db.get_anomalies(element_id=element_id, limit=50)
    latest_shi = await db.get_latest_shi(element_id)

    if not history:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"No SHI history for '{element_id}'. "
                "Compute at least one health score before requesting a report."
            ),
        )

    pdf_bytes = generate_element_report(
        element    = element,
        history    = history,
        anomalies  = anomalies,
        latest_shi = latest_shi,
    )

    filename = f"nexustwin_report_{element_id}.pdf"
    logger.info("PDF report generated for element %s (%d bytes).", element_id, len(pdf_bytes))

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
