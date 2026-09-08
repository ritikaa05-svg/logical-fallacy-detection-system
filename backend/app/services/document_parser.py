"""
Document Parser Service — Phase 6, Deliverable A2.
Extracts text from PDF, DOCX, and TXT files with per-page metadata.
"""

import logging
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class PageResult:
    """Per-page extraction result with character offset information."""

    page_number: int
    text: str
    start_offset: int
    end_offset: int


@dataclass
class DocumentParseResult:
    """Complete result from parsing a document file."""

    filename: str
    mime_type: str
    page_count: int
    pages: list[PageResult]
    full_text: str
    latency_ms: float


class DocumentParser:
    """
    Service for parsing PDF, DOCX, and TXT documents into structured text.

    Usage:
        result = document_parser.parse("/path/to/file.pdf", "application/pdf")
    """

    def parse_pdf(self, path: str) -> DocumentParseResult:
        """
        Extract text from a PDF file page by page using PyMuPDF (fitz).

        Args:
            path: Absolute filesystem path to the PDF file.

        Returns:
            DocumentParseResult with per-page text and full document text.
        """
        import fitz  # PyMuPDF

        t0 = time.perf_counter()
        filename = Path(path).name
        pages: list[PageResult] = []
        text_parts: list[str] = []
        cursor = 0

        try:
            doc = fitz.open(path)
            for page_num, page in enumerate(doc, start=1):
                page_text = page.get_text()
                start = cursor
                text_parts.append(page_text)
                cursor += len(page_text)
                pages.append(
                    PageResult(
                        page_number=page_num,
                        text=page_text,
                        start_offset=start,
                        end_offset=cursor,
                    )
                )
            doc.close()
        except Exception as exc:
            logger.error(f"PDF parse error for {filename}: {exc}", exc_info=True)
            raise

        full_text = "".join(text_parts)
        latency_ms = (time.perf_counter() - t0) * 1000
        logger.info(f"PDF parsed: {filename}, {len(pages)} pages, {len(full_text)} chars, {latency_ms:.1f}ms")
        return DocumentParseResult(
            filename=filename,
            mime_type="application/pdf",
            page_count=len(pages),
            pages=pages,
            full_text=full_text,
            latency_ms=latency_ms,
        )

    def parse_docx(self, path: str) -> DocumentParseResult:
        """
        Extract text from a DOCX file paragraph by paragraph.
        Each paragraph is treated as a logical 'page' chunk.

        Args:
            path: Absolute filesystem path to the DOCX file.

        Returns:
            DocumentParseResult with paragraph-chunked pages.
        """
        import docx  # python-docx

        t0 = time.perf_counter()
        filename = Path(path).name
        pages: list[PageResult] = []
        text_parts: list[str] = []
        cursor = 0

        try:
            document = docx.Document(path)
            paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
        except Exception as exc:
            logger.error(f"DOCX parse error for {filename}: {exc}", exc_info=True)
            raise

        # Group paragraphs into page-like chunks (~500 chars each)
        chunk_size = 500
        current_chunk: list[str] = []
        current_len = 0
        page_num = 1

        def _flush_chunk(chunk_texts: list[str], p_num: int, cur: int) -> tuple[PageResult, int]:
            chunk_text = "\n".join(chunk_texts) + "\n"
            end = cur + len(chunk_text)
            page = PageResult(
                page_number=p_num,
                text=chunk_text,
                start_offset=cur,
                end_offset=end,
            )
            return page, end

        for para in paragraphs:
            current_chunk.append(para)
            current_len += len(para)
            text_parts.append(para + "\n")
            if current_len >= chunk_size:
                page_result, cursor = _flush_chunk(current_chunk, page_num, cursor)
                pages.append(page_result)
                page_num += 1
                current_chunk = []
                current_len = 0

        # Flush remaining paragraphs
        if current_chunk:
            page_result, cursor = _flush_chunk(current_chunk, page_num, cursor)
            pages.append(page_result)

        if not pages:
            # Empty document — create a single empty page
            pages.append(PageResult(page_number=1, text="", start_offset=0, end_offset=0))

        full_text = "".join(text_parts)
        latency_ms = (time.perf_counter() - t0) * 1000
        logger.info(f"DOCX parsed: {filename}, {len(pages)} chunks, {len(full_text)} chars, {latency_ms:.1f}ms")
        return DocumentParseResult(
            filename=filename,
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            page_count=len(pages),
            pages=pages,
            full_text=full_text,
            latency_ms=latency_ms,
        )

    def parse_txt(self, path: str) -> DocumentParseResult:
        """
        Extract text from a plain-text file.
        Chunks the text into 500-char page-like sections.

        Args:
            path: Absolute filesystem path to the TXT file.

        Returns:
            DocumentParseResult with chunked pages.
        """
        t0 = time.perf_counter()
        filename = Path(path).name

        try:
            raw = Path(path).read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            logger.error(f"TXT parse error for {filename}: {exc}", exc_info=True)
            raise

        chunk_size = 500
        pages: list[PageResult] = []
        cursor = 0
        page_num = 1

        while cursor < len(raw):
            end = min(cursor + chunk_size, len(raw))
            chunk_text = raw[cursor:end]
            pages.append(
                PageResult(
                    page_number=page_num,
                    text=chunk_text,
                    start_offset=cursor,
                    end_offset=end,
                )
            )
            cursor = end
            page_num += 1

        if not pages:
            pages.append(PageResult(page_number=1, text="", start_offset=0, end_offset=0))

        latency_ms = (time.perf_counter() - t0) * 1000
        logger.info(f"TXT parsed: {filename}, {len(pages)} chunks, {len(raw)} chars, {latency_ms:.1f}ms")
        return DocumentParseResult(
            filename=filename,
            mime_type="text/plain",
            page_count=len(pages),
            pages=pages,
            full_text=raw,
            latency_ms=latency_ms,
        )

    def parse(self, file_path: str, mime_type: str) -> DocumentParseResult:
        """
        Dispatcher: route to the appropriate parser based on MIME type or extension.

        Args:
            file_path: Absolute filesystem path to the uploaded file.
            mime_type: MIME type string (e.g. "application/pdf").

        Returns:
            DocumentParseResult from the appropriate parser.

        Raises:
            ValueError: If the MIME type / extension is unsupported.
        """
        ext = Path(file_path).suffix.lower()

        if mime_type == "application/pdf" or ext == ".pdf":
            return self.parse_pdf(file_path)
        elif (
            mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or mime_type == "application/msword"
            or ext == ".docx"
        ):
            return self.parse_docx(file_path)
        elif mime_type == "text/plain" or ext == ".txt":
            return self.parse_txt(file_path)
        else:
            raise ValueError(
                f"Unsupported document format: mime_type={mime_type!r}, ext={ext!r}. "
                "Supported formats: .pdf, .docx, .txt"
            )


# Module-level singleton
document_parser = DocumentParser()
