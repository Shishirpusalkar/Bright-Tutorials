import logging
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.ai import generate_questions_from_pdf

logger = logging.getLogger(__name__)

router = APIRouter()

UPLOAD_DIR = Path("static/uploads/temp")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload-pdf")
async def upload_pdf(
    file: UploadFile = File(...),
) -> Any:
    """
    Upload a PDF and extract questions directly.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Save the file temporarily
    file_id = uuid.uuid4()
    file_path = UPLOAD_DIR / f"{file_id}.pdf"

    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        logger.info(f"Processing PDF for direct extraction: {file_path}")
        ai_questions = generate_questions_from_pdf(str(file_path))

        # Format response as requested
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

        return {"success": True, "questions": questions_response}
    except Exception as e:
        logger.error(f"PDF extraction failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")
    finally:
        # Cleanup temp file
        if file_path.exists():
            file_path.unlink()
