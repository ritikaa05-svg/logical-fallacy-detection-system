"""
Document upload, analysis, and report schemas — Phase 6, Deliverable A5.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.app.schemas.inference import InferenceResult


class PageInfo(BaseModel):
    """Metadata and preview for a single parsed page or chunk."""

    page_number: int = Field(description="1-based page/chunk number.")
    text_preview: str = Field(description="First 200 characters of the page text.")
    start_offset: int = Field(description="Character start offset into full_text.")
    end_offset: int = Field(description="Character end offset into full_text.")


class DocumentUploadResponse(BaseModel):
    """Response returned after a successful document upload."""

    document_id: str = Field(description="Short UUID identifying the uploaded document.")
    filename: str = Field(description="Original filename of the uploaded document.")
    mime_type: str = Field(description="Detected MIME type.")
    page_count: int = Field(description="Number of pages/chunks extracted.")
    char_count: int = Field(description="Total character count of extracted text.")
    text_preview: str = Field(description="First 500 characters of the full extracted text.")
    pages: list[PageInfo] = Field(default_factory=list, description="Per-page metadata.")


class DocumentAnalysisRequest(BaseModel):
    """Request body for the document analyze endpoint."""

    document_id: str = Field(description="ID returned from the upload endpoint.")
    skip_cache: bool = Field(default=False, description="Bypass Redis cache.")
    fast_track: bool = Field(
        default=False,
        description="Skip LLM-heavy stages for faster results.",
    )
    include_explanations: bool = Field(
        default=True,
        description="Generate token-level saliency explanations.",
    )


class PerPageResult(BaseModel):
    """Analysis result for a single page/chunk within a document."""

    page_number: int = Field(description="1-based page number.")
    result: InferenceResult = Field(description="Full pipeline result for this page.")


class DocumentAnalysisResult(BaseModel):
    """Full analysis result for an uploaded document."""

    document: DocumentUploadResponse = Field(description="Uploaded document metadata.")
    overall: InferenceResult = Field(description="Full pipeline result run on the complete document text.")
    per_page: list[PerPageResult] = Field(
        default_factory=list,
        description="Per-page pipeline results.",
    )
