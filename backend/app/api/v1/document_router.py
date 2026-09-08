"""
Document API Router — Phase 6, Deliverable A4.
Provides endpoints for document upload, analysis, metadata retrieval, and report download.
"""

from __future__ import annotations

import logging
import os
import tempfile
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse, Response

from backend.app.config import settings
from backend.app.core.security import rate_limit_middleware, sanitize_input
from backend.app.pipeline.orchestrator import pipeline_orchestrator
from backend.app.schemas.document import (
    DocumentAnalysisResult,
    DocumentUploadResponse,
    PageInfo,
    PerPageResult,
)
from backend.app.services.document_parser import DocumentParseResult, document_parser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

# In-memory document store: document_id -> DocumentParseResult
_document_store: dict[str, DocumentParseResult] = {}

# In-memory analysis cache: document_id -> DocumentAnalysisResult
_analysis_cache: dict[str, DocumentAnalysisResult] = {}

# MIME-type map from common extensions
_MIME_MAP: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}


def _parse_result_to_response(doc: DocumentParseResult, doc_id: str) -> DocumentUploadResponse:
    """Convert a DocumentParseResult to the HTTP response schema."""
    pages_info = [
        PageInfo(
            page_number=p.page_number,
            text_preview=p.text[:200],
            start_offset=p.start_offset,
            end_offset=p.end_offset,
        )
        for p in doc.pages
    ]
    return DocumentUploadResponse(
        document_id=doc_id,
        filename=doc.filename,
        mime_type=doc.mime_type,
        page_count=doc.page_count,
        char_count=len(doc.full_text),
        text_preview=doc.full_text[:500],
        pages=pages_info,
    )


# ──────────────────────────────────────────────────────────────────────────────
# POST /upload
# ──────────────────────────────────────────────────────────────────────────────
@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document for analysis",
    description=(
        "Upload a PDF, DOCX, or TXT document. "
        "The server extracts its text and returns page metadata. "
        f"Maximum file size: {settings.MAX_FILE_SIZE_MB} MB."
    ),
    dependencies=[Depends(rate_limit_middleware)],
)
async def upload_document(
    file: UploadFile,
    request: Request,  # noqa: ARG001  # required for rate_limit_middleware state
) -> DocumentUploadResponse:
    """
    Accept an uploaded file, validate format/size, parse it, and store metadata.
    """
    # Validate extension
    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in settings.SUPPORTED_DOCUMENT_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(f"Unsupported file format '{ext}'. Allowed: {', '.join(settings.SUPPORTED_DOCUMENT_FORMATS)}"),
        )

    # Read file content and enforce size limit
    content = await file.read()
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(f"File size {len(content) / 1_048_576:.1f} MB exceeds the {settings.MAX_FILE_SIZE_MB} MB limit."),
        )

    # Determine MIME type from extension
    mime_type = _MIME_MAP.get(ext, file.content_type or "application/octet-stream")

    # Write to a temporary file so parsers can read it
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        parse_result = document_parser.parse(tmp_path, mime_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error(f"Document parse failed for {filename}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse document: {exc}",
        ) from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    # Restore original filename (the parser uses the temp path's filename)
    parse_result.filename = filename

    # Assign a document ID and store
    doc_id = str(uuid.uuid4())[:8]
    _document_store[doc_id] = parse_result

    logger.info(
        f"Document uploaded: id={doc_id}, file={filename}, "
        f"pages={parse_result.page_count}, chars={len(parse_result.full_text)}"
    )
    return _parse_result_to_response(parse_result, doc_id)


# ──────────────────────────────────────────────────────────────────────────────
# GET /{document_id}
# ──────────────────────────────────────────────────────────────────────────────
@router.get(
    "/{document_id}",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve stored document metadata",
    dependencies=[Depends(rate_limit_middleware)],
)
async def get_document(
    document_id: str,
    request: Request,  # noqa: ARG001
) -> DocumentUploadResponse:
    """Return the metadata of a previously uploaded document."""
    doc = _document_store.get(document_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )
    return _parse_result_to_response(doc, document_id)


# ──────────────────────────────────────────────────────────────────────────────
# POST /{document_id}/analyze
# ──────────────────────────────────────────────────────────────────────────────
@router.post(
    "/{document_id}/analyze",
    response_model=DocumentAnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Analyze an uploaded document",
    description=("Run the 4-stage LogiScan pipeline on the full document text and independently on each page/chunk."),
    dependencies=[Depends(rate_limit_middleware)],
)
async def analyze_document(
    document_id: str,
    request: Request,  # noqa: ARG001
    skip_cache: bool = False,
    fast_track: bool = False,
    include_explanations: bool = True,
) -> DocumentAnalysisResult:
    """
    1. Retrieve the stored document by ID.
    2. Sanitize the full text.
    3. Run the pipeline on the full text (cached result).
    4. Run the pipeline independently on each page.
    5. Run cross-segment contradiction detection on page results.
    6. Return DocumentAnalysisResult.
    """
    doc = _document_store.get(document_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )

    # Return cached analysis if available and skip_cache is False
    if not skip_cache and document_id in _analysis_cache:
        logger.info(f"Returning cached analysis for document {document_id}")
        return _analysis_cache[document_id]

    # Sanitize full text (truncate injection patterns; don't raise on long docs)
    try:
        full_text = sanitize_input(doc.full_text[:8000])  # cap at 8000 chars for pipeline
    except HTTPException:
        full_text = doc.full_text[:8000]

    # --- Overall analysis on full text ---
    try:
        overall_result = await pipeline_orchestrator.analyze(
            text=full_text,
            skip_cache=skip_cache,
            include_explanations=include_explanations,
            fast_track=fast_track,
        )
    except Exception as exc:
        logger.error(f"Overall analysis failed for {document_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline analysis failed: {exc}",
        ) from exc

    # --- Per-page analysis ---
    per_page_results: list[PerPageResult] = []
    page_inference_results = []

    for page in doc.pages:
        page_text = page.text.strip()
        if not page_text or len(page_text) < 10:
            continue
        try:
            sanitized_page = sanitize_input(page_text[:4000])
        except HTTPException:
            sanitized_page = page_text[:4000]
        try:
            page_result = await pipeline_orchestrator.analyze(
                text=sanitized_page,
                skip_cache=skip_cache,
                include_explanations=False,
                fast_track=True,  # always fast-track per-page for performance
            )
            per_page_results.append(PerPageResult(page_number=page.page_number, result=page_result))
            page_inference_results.append((page.page_number, page_result))
        except Exception as exc:
            logger.warning(f"Per-page analysis failed for page {page.page_number}: {exc}")

    # --- Cross-segment contradiction detection ---
    if len(page_inference_results) > 1:
        from backend.app.services.contradiction_detector import (
            AnalysisSegment,
            contradiction_detector,
        )

        segments = []
        for page_num, r in page_inference_results:
            premises: list[str] = []
            conclusion = ""
            if r.argument_structure:
                premises = r.argument_structure.premises or []
                conclusion = r.argument_structure.conclusion or ""

            formal_types = {
                "affirming_consequent",
                "denying_antecedent",
                "undistributed_middle",
                "illicit_major",
                "illicit_minor",
                "exclusive_premises",
                "existential_fallacy",
            }
            has_formal = any(lbl in formal_types for lbl in r.fine_labels)

            # Build segment text from page text (use input_text from result)
            seg_text = r.input_text or ""

            segments.append(
                AnalysisSegment(
                    text=seg_text,
                    page_number=page_num,
                    premises=premises,
                    conclusion=conclusion,
                    has_formal_fallacy=has_formal,
                    fallacy_types=r.fine_labels,
                )
            )

        contradiction_result = contradiction_detector.detect(segments)
        # Attach contradictions to overall result
        overall_result = overall_result.model_copy(update={"cross_segment_contradictions": contradiction_result})

    doc_response = _parse_result_to_response(doc, document_id)
    analysis = DocumentAnalysisResult(
        document=doc_response,
        overall=overall_result,
        per_page=per_page_results,
    )

    # Cache the analysis result
    _analysis_cache[document_id] = analysis

    logger.info(
        f"Document analysis complete: id={document_id}, "
        f"pages={len(per_page_results)}, "
        f"fallacies={len(overall_result.fallacies)}"
    )
    return analysis


# ──────────────────────────────────────────────────────────────────────────────
# GET /{document_id}/report
# ──────────────────────────────────────────────────────────────────────────────
@router.get(
    "/{document_id}/report",
    status_code=status.HTTP_200_OK,
    summary="Download analysis report",
    description="Download the analysis report as PDF or JSON. Requires a prior /analyze call.",
    dependencies=[Depends(rate_limit_middleware)],
)
async def get_report(
    document_id: str,
    request: Request,  # noqa: ARG001
    format: str = "pdf",
) -> Response:
    """
    Generate and return a downloadable report for a previously analyzed document.

    Query params:
        format: "pdf" (default) or "json"
    """
    # Must have been analyzed first
    analysis = _analysis_cache.get(document_id)
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No analysis found for document '{document_id}'. Please call POST /{{document_id}}/analyze first."
            ),
        )

    from backend.app.services.report_generator import report_generator

    safe_filename = "".join(
        c if c.isalnum() or c in "-_." else "_" for c in analysis.document.filename.rsplit(".", 1)[0]
    )

    if format.lower() == "json":
        json_report = report_generator.generate_json_report(analysis)
        return JSONResponse(
            content=json_report,
            headers={"Content-Disposition": (f'attachment; filename="{safe_filename}_logic_report.json"')},
        )

    # Default: PDF
    try:
        pdf_bytes = report_generator.generate_pdf_report(analysis)
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": (f'attachment; filename="{safe_filename}_logic_report.pdf"')},
    )
