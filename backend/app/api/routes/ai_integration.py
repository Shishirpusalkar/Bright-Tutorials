import hashlib
import json
import logging
import shutil
import uuid
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlmodel import Session, select

from app.core.db import engine
from app.core.redis_cache import get_cached_extraction, set_cached_extraction
from app.models import ParsedPaperCache
from app.services.ai import generate_questions_from_pdf

logger = logging.getLogger(__name__)

router = APIRouter()

UPLOAD_DIR = Path("static/uploads/temp")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _compute_pdf_hash(file_path: Path) -> str:
    """Return SHA-256 hex digest of a PDF file for cache keying."""
    sha256 = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _questions_to_xml(questions: list[dict[str, Any]]) -> bytes:
    """Serialize questions list to an XML byte string.

    xml.etree.ElementTree automatically escapes special XML characters
    (<, >, &, ", ') when assigning to Element.text, so all question
    content is safely serialized regardless of its contents.
    """
    root = Element("extraction")
    for q in questions:
        q_el = SubElement(root, "question")
        for key, value in q.items():
            child = SubElement(q_el, key)
            child.text = str(value) if value is not None else ""
    return tostring(root, encoding="utf-8", xml_declaration=True)


@router.post("/upload-pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    response_format: str = Query(
        default="json", description="Response format: 'json' or 'xml'"
    ),
) -> Any:
    """
    Upload a PDF and extract questions using Gemini AI.

    Process flow (from docs/pdf_extraction_enhancement.md):
    1. File is stored temporarily in a secure location.
    2. SHA-256 hash computed for cache keying.
    3. Redis cache checked first (fast retrieval).
    4. DB cache checked on Redis miss.
    5. AI extraction performed on full cache miss.
    6. Results stored in Redis (TTL) and DB.
    7. Response returned as JSON or XML.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    if response_format not in ("json", "xml"):
        raise HTTPException(
            status_code=400, detail="response_format must be 'json' or 'xml'"
        )

    # 1. Store file temporarily
    file_id = uuid.uuid4()
    file_path = UPLOAD_DIR / f"{file_id}.pdf"

    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. Compute PDF hash for caching
        pdf_hash = _compute_pdf_hash(file_path)
        logger.info("Processing PDF hash=%s filename=%s", pdf_hash, file.filename)

        # 3. Redis cache check
        cached = get_cached_extraction(pdf_hash)
        if cached is not None:
            logger.info("Returning Redis-cached result for hash=%s", pdf_hash)
            questions_response = cached["questions"]
        else:
            # 4. DB cache check
            with Session(engine) as session:
                db_record = session.exec(
                    select(ParsedPaperCache).where(
                        ParsedPaperCache.pdf_hash == pdf_hash
                    )
                ).first()

            if db_record is not None:
                logger.info("Returning DB-cached result for hash=%s", pdf_hash)
                questions_response = db_record.data.get("questions", [])
                # Warm Redis cache from DB
                set_cached_extraction(pdf_hash, {"questions": questions_response})
            else:
                # 5. Full AI extraction
                logger.info("Running AI extraction for hash=%s", pdf_hash)
                ai_questions = generate_questions_from_pdf(str(file_path))

                questions_response = []
                for q in ai_questions:
                    questions_response.append(
                        {
                            "id": str(uuid.uuid4()),
                            "question_text": q.question_text,
                            "options": q.options,
                            "correct_option": q.correct_option
                            if not isinstance(q.correct_option, list)
                            else (q.correct_option[0] if q.correct_option else None),
                            "solution_text": q.solution_text,
                            "question_type": q.question_type,
                            "subject": q.subject,
                            "section": q.section,
                            "marks": q.marks or 4,
                            "negative_marks": q.negative_marks or -1.0,
                        }
                    )

                payload = {"questions": questions_response}

                # 6a. Store in Redis with TTL
                set_cached_extraction(pdf_hash, payload)

                # 6b. Persist in DB
                with Session(engine) as session:
                    existing = session.exec(
                        select(ParsedPaperCache).where(
                            ParsedPaperCache.pdf_hash == pdf_hash
                        )
                    ).first()
                    if existing is None:
                        session.add(
                            ParsedPaperCache(pdf_hash=pdf_hash, data=payload)
                        )
                        session.commit()

        # 7. Return formatted response
        if response_format == "xml":
            xml_bytes = _questions_to_xml(questions_response)
            return Response(content=xml_bytes, media_type="application/xml")

        return {"success": True, "pdf_hash": pdf_hash, "questions": questions_response}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("PDF extraction failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")
    finally:
        # Cleanup temp file
        if file_path.exists():
            file_path.unlink()


@router.get("/retrieve-pdf/{pdf_hash}")
async def retrieve_pdf_extraction(
    pdf_hash: str,
    response_format: str = Query(default="json", description="'json' or 'xml'"),
) -> Any:
    """
    Retrieve previously extracted data for a PDF by its SHA-256 hash.

    Checks Redis first, then the database.
    """
    if response_format not in ("json", "xml"):
        raise HTTPException(
            status_code=400, detail="response_format must be 'json' or 'xml'"
        )

    # Redis fast path
    cached = get_cached_extraction(pdf_hash)
    if cached is not None:
        questions_response = cached["questions"]
    else:
        with Session(engine) as session:
            db_record = session.exec(
                select(ParsedPaperCache).where(
                    ParsedPaperCache.pdf_hash == pdf_hash
                )
            ).first()
        if db_record is None:
            raise HTTPException(
                status_code=404,
                detail="No extraction found for the given PDF hash",
            )
        questions_response = db_record.data.get("questions", [])
        set_cached_extraction(pdf_hash, {"questions": questions_response})

    if response_format == "xml":
        xml_bytes = _questions_to_xml(questions_response)
        return Response(content=xml_bytes, media_type="application/xml")

    return {
        "success": True,
        "pdf_hash": pdf_hash,
        "questions": questions_response,
    }


@router.delete("/retrieve-pdf/{pdf_hash}")
async def invalidate_pdf_cache(pdf_hash: str) -> Any:
    """
    Invalidate the cached extraction for the given PDF hash (Redis + DB).
    """
    from app.core.redis_cache import invalidate_extraction

    redis_deleted = invalidate_extraction(pdf_hash)

    with Session(engine) as session:
        record = session.exec(
            select(ParsedPaperCache).where(ParsedPaperCache.pdf_hash == pdf_hash)
        ).first()
        db_deleted = False
        if record is not None:
            session.delete(record)
            session.commit()
            db_deleted = True

    if not redis_deleted and not db_deleted:
        raise HTTPException(
            status_code=404, detail="No cache entry found for the given PDF hash"
        )

    return {
        "success": True,
        "pdf_hash": pdf_hash,
        "redis_invalidated": redis_deleted,
        "db_invalidated": db_deleted,
    }

