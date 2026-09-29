"""
PDF parsing service using pypdf (formerly PyPDF2).

Implements step 2 of docs/process_flow.md (DeepSeek branch):
"The system uses libraries such as PyPDF2 to parse the document content."

Falls back to raw bytes extraction when the text layer is absent or minimal,
signalling to the caller that OCR is required.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Minimum characters per page to consider the text layer usable.
_MIN_TEXT_CHARS_PER_PAGE = 20


@dataclass
class ParsedPDFResult:
    """Result of a PDF parse operation."""

    # Extracted text per page (empty string means page has no text layer).
    pages: list[str] = field(default_factory=list)
    # Metadata extracted from the PDF document info dictionary.
    metadata: dict[str, str] = field(default_factory=dict)
    # True when text was successfully extracted from at least one page.
    has_text_layer: bool = False
    # Pages that need OCR (0-indexed).
    ocr_required_pages: list[int] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n".join(page for page in self.pages if page)


def parse_pdf(pdf_path: str | Path) -> ParsedPDFResult:
    """
    Parse a PDF file and extract its text content and metadata.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        ParsedPDFResult with per-page text, metadata, and OCR hint flags.

    Raises:
        FileNotFoundError: If the PDF does not exist.
        ValueError: If the file is not a valid PDF.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ImportError(
            "pypdf is required for PDF parsing. Install it with: pip install pypdf"
        ) from exc

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    logger.info("Parsing PDF: %s", pdf_path)

    try:
        reader = PdfReader(str(pdf_path))
    except Exception as exc:
        raise ValueError(f"Failed to open PDF '{pdf_path}': {exc}") from exc

    # Extract metadata
    raw_meta = reader.metadata or {}
    metadata: dict[str, str] = {}
    for key, value in raw_meta.items():
        # Keys like '/Author', '/Title' → strip leading slash
        clean_key = key.lstrip("/") if isinstance(key, str) else str(key)
        metadata[clean_key] = str(value) if value is not None else ""

    pages: list[str] = []
    ocr_required_pages: list[int] = []

    for page_idx, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            logger.warning("Failed to extract text from page %d: %s", page_idx, exc)
            text = ""

        pages.append(text.strip())

        if len(text.strip()) < _MIN_TEXT_CHARS_PER_PAGE:
            ocr_required_pages.append(page_idx)
            logger.debug(
                "Page %d has sparse text (%d chars) — OCR required",
                page_idx,
                len(text.strip()),
            )

    has_text_layer = len(ocr_required_pages) < len(pages)

    logger.info(
        "Parsed %d pages; text layer: %s; OCR required pages: %s",
        len(pages),
        has_text_layer,
        ocr_required_pages,
    )

    return ParsedPDFResult(
        pages=pages,
        metadata=metadata,
        has_text_layer=has_text_layer,
        ocr_required_pages=ocr_required_pages,
    )
