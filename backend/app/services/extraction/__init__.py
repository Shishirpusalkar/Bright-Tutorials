"""Layout-aware question extraction for two-column JEE/NEET style papers.

Usage:
    from app.services.extraction import build_transcriber, extract_paper

    result = extract_paper(
        "paper.pdf",
        asset_dir="static/uploads/papers/<id>",
        asset_url="/static/uploads/papers/<id>",
        solution_pdf_path=None,          # optional separate solutions PDF
        transcriber=build_transcriber(),  # None -> text layer + image fallback
    )
"""

from .models import ExtractedQuestion
from .pipeline import ExtractionResult, extract_paper
from .transcriber import Transcriber


def build_transcriber() -> Transcriber | None:
    """Transcriber configured from settings, or None when AI is disabled."""
    from app.core.config import settings

    if not settings.OPENAI_API_KEY:
        return None
    return Transcriber(
        api_key=settings.OPENAI_API_KEY,
        model=settings.OPENAI_EXTRACTION_MODEL,
        base_url=settings.OPENAI_BASE_URL,
        cache_dir=settings.EXTRACTION_CACHE_DIR,
        max_workers=settings.EXTRACTION_MAX_WORKERS,
        batch_size=settings.EXTRACTION_BATCH_SIZE,
    )


__all__ = [
    "ExtractedQuestion",
    "ExtractionResult",
    "Transcriber",
    "build_transcriber",
    "extract_paper",
]
