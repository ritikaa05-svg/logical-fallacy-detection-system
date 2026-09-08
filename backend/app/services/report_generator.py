"""
Report Generator Service — Phase 6, Deliverable C2.
Generates PDF (via WeasyPrint + Jinja2) and JSON reports for document analysis results.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape

from backend.app.schemas.document import DocumentAnalysisResult

logger = logging.getLogger(__name__)

# Template directory relative to this file: ../../templates
_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")


class ReportGenerator:
    """
    Generates downloadable reports in PDF and JSON formats.

    PDF reports are rendered via WeasyPrint from an HTML Jinja2 template.
    JSON reports are structured dicts containing all analysis data.
    """

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(_TEMPLATE_DIR),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def generate_json_report(self, document_result: DocumentAnalysisResult) -> dict:
        """
        Build a structured JSON report from a DocumentAnalysisResult.

        Args:
            document_result: The complete analysis result from the document endpoint.

        Returns:
            Dict ready for JSONResponse serialization.
        """
        generated_at = datetime.now(UTC).isoformat()

        overall_dict = document_result.overall.model_dump(mode="json")

        per_page_list = [
            {
                "page_number": pp.page_number,
                "result": pp.result.model_dump(mode="json"),
            }
            for pp in document_result.per_page
        ]

        contradictions_dict = None
        if document_result.overall.cross_segment_contradictions:
            contradictions_dict = document_result.overall.cross_segment_contradictions.model_dump(mode="json")  # type: ignore[attr-defined]

        return {
            "report_version": "1.0",
            "generated_at": generated_at,
            "document": document_result.document.model_dump(mode="json"),
            "overall_analysis": overall_dict,
            "per_page_analysis": per_page_list,
            "cross_segment_contradictions": contradictions_dict,
            "summary": {
                "logic_score": document_result.overall.logic_score,
                "total_fallacies": len(document_result.overall.fallacies),
                "coarse_category": document_result.overall.coarse_category,
                "z3_status": document_result.overall.z3_status,
                "pages_analyzed": len(document_result.per_page),
                "contradictions_found": (len(contradictions_dict["contradictions"]) if contradictions_dict else 0),
            },
        }

    def generate_pdf_report(self, document_result: DocumentAnalysisResult) -> bytes:
        """
        Render an HTML report template and convert it to PDF bytes via WeasyPrint.

        Args:
            document_result: The complete analysis result from the document endpoint.

        Returns:
            Raw PDF bytes suitable for a streaming response.

        Raises:
            ImportError: If WeasyPrint is not installed.
            RuntimeError: If PDF generation fails.
        """
        try:
            from weasyprint import HTML
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "WeasyPrint is required for PDF generation. Install it with: pip install weasyprint>=61.0.0"
            ) from exc

        generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

        try:
            template = self._env.get_template("report.html")
        except Exception as exc:  # pragma: no cover
            logger.error(f"Failed to load report template: {exc}", exc_info=True)
            raise RuntimeError(f"Report template error: {exc}") from exc

        html_content = template.render(
            document=document_result.document,
            overall=document_result.overall,
            per_page=document_result.per_page,
            generated_at=generated_at,
        )

        try:
            pdf_bytes: bytes = HTML(string=html_content).write_pdf()
        except Exception as exc:
            logger.error(f"WeasyPrint PDF generation failed: {exc}", exc_info=True)
            raise RuntimeError(f"PDF generation failed: {exc}") from exc

        logger.info(f"PDF report generated for {document_result.document.filename}: {len(pdf_bytes)} bytes")
        return pdf_bytes


# Module-level singleton
report_generator = ReportGenerator()
