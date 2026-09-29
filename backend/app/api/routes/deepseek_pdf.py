"""
DeepSeek AI PDF extraction routes.

Implements docs/process_flow.md (DeepSeek branch):
1. PDF Upload    — POST /deepseek/upload-pdf
2. Doc Parsing   — PyPDF2 text extraction (services/pdf_parser.py)
3. OCR Processing — DeepSeek OCR for scanned pages (core/deepseek.py)
4. Data Storage  — Persist structured result in ParsedPaperCache
5. Redis Caching — Cache result for fast subsequent retrieval
6. User Retrieval — GET /deepseek/retrieve/{pdf_hash}
"""

import hashlib
import logging
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from sqlmodel import Session, select

from app.core.db import engine
from app.core.redis_cache import get_cached_extraction, set_cached_extraction
from app.models import ParsedPaperCache
from app.services.pdf_parser import parse_pdf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deepseek", tags=["deepseek-pdf"])

UPLOAD_DIR = Path("static/uploads/temp")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _compute_pdf_hash(file_path: Path) -> str:
    """Return SHA-256 hex digest of a PDF file."""
    sha256 = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


@router.post("/upload-pdf")
async def deepseek_upload_pdf(
    file: UploadFile = File(...),
    use_ocr: bool = True,
) -> Any:
    """
    Upload a PDF document and extract its text content.

    Process flow:
    1. PDF stored temporarily.
    2. SHA-256 hash computed.
    3. Redis + DB checked for prior extraction.
    4. PyPDF2 parses text layer.
    5. DeepSeek OCR fills gaps for scanned/image-only pages (if use_ocr=True).
    6. Structured result stored in DB and cached in Redis.
    7. Structured JSON response returned.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    file_id = uuid.uuid4()
    file_path = UPLOAD_DIR / f"{file_id}.pdf"

    try:
        # 1. Store temporarily
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. Compute hash
        pdf_hash = _compute_pdf_hash(file_path)
        logger.info(
            "DeepSeek upload: hash=%s filename=%s", pdf_hash, file.filename
        )

        # 3. Check Redis cache
        cached = get_cached_extraction(pdf_hash)
        if cached is not None:
            logger.info("Redis cache HIT for hash=%s", pdf_hash)
            return {"success": True, "pdf_hash": pdf_hash, **cached}

        # 3b. Check DB cache
        with Session(engine) as session:
            db_record = session.exec(
                select(ParsedPaperCache).where(
                    ParsedPaperCache.pdf_hash == pdf_hash
                )
            ).first()

        if db_record is not None:
            logger.info("DB cache HIT for hash=%s", pdf_hash)
            payload = db_record.data
            set_cached_extraction(pdf_hash, payload)
            return {"success": True, "pdf_hash": pdf_hash, **payload}

        # 4. PyPDF2 document parsing
        parsed = parse_pdf(file_path)
        logger.info(
            "Parsed %d pages; text layer=%s; OCR needed=%s",
            len(parsed.pages),
            parsed.has_text_layer,
            parsed.ocr_required_pages,
        )

        # Per-page text: start with PyPDF2 output
        pages_text: list[str] = list(parsed.pages)

        # 5. DeepSeek OCR for scanned pages
        if use_ocr and parsed.ocr_required_pages:
            try:
                from app.core.deepseek import ocr_pdf_pages

                ocr_results = ocr_pdf_pages(file_path, parsed.ocr_required_pages)
                for page_idx, ocr_text in ocr_results.items():
                    pages_text[page_idx] = ocr_text
                logger.info(
                    "DeepSeek OCR completed for %d pages", len(ocr_results)
                )
            except Exception as exc:
                # OCR is best-effort; log and continue with available text
                logger.warning(
                    "DeepSeek OCR failed (continuing with partial text from PyPDF2 only): %s",
                    exc,
                )

        # 4 & 5 combined result
        payload: dict[str, Any] = {
            "metadata": parsed.metadata,
            "page_count": len(pages_text),
            "has_text_layer": parsed.has_text_layer,
            "ocr_applied_pages": parsed.ocr_required_pages,
            "pages": [
                {"page_number": i + 1, "text": text}
                for i, text in enumerate(pages_text)
            ],
            "full_text": "\n".join(t for t in pages_text if t),
        }

        # 6a. Persist in DB
        with Session(engine) as session:
            existing = session.exec(
                select(ParsedPaperCache).where(
                    ParsedPaperCache.pdf_hash == pdf_hash
                )
            ).first()
            if existing is None:
                session.add(ParsedPaperCache(pdf_hash=pdf_hash, data=payload))
                session.commit()

        # 6b. Cache in Redis
        set_cached_extraction(pdf_hash, payload)

        # 7. Return structured response
        return {"success": True, "pdf_hash": pdf_hash, **payload}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("DeepSeek PDF extraction failed: %s", exc)
        raise HTTPException(
            status_code=500, detail=f"Extraction failed: {str(exc)}"
        )
    finally:
        if file_path.exists():
            file_path.unlink()


@router.get("/retrieve/{pdf_hash}")
async def deepseek_retrieve_extraction(pdf_hash: str) -> Any:
    """
    Retrieve previously extracted PDF data by its SHA-256 hash.

    Checks Redis first, then the database (step 6 of docs/process_flow.md).
    """
    # Redis fast path
    cached = get_cached_extraction(pdf_hash)
    if cached is not None:
        return {"success": True, "pdf_hash": pdf_hash, "source": "cache", **cached}

    # DB fallback
    with Session(engine) as session:
        db_record = session.exec(
            select(ParsedPaperCache).where(
                ParsedPaperCache.pdf_hash == pdf_hash
            )
        ).first()

    if db_record is None:
        raise HTTPException(
            status_code=404,
            detail="No extraction found for the given PDF hash. Upload the PDF first.",
        )

    payload = db_record.data
    set_cached_extraction(pdf_hash, payload)

    return {
        "success": True,
        "pdf_hash": pdf_hash,
        "source": "database",
        **payload,
    }
