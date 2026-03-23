from datetime import datetime, timezone
from io import BytesIO
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from fpdf import FPDF
from sqlmodel import col, func, select

from app.api.deps import SessionDep, get_current_active_superuser
from app.models import Question, QuestionPublic

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/questions", tags=["questions"])


@router.get("/", response_model=list[QuestionPublic])
def read_questions(
    session: SessionDep,
    superuser: Any = Depends(get_current_active_superuser),
    skip: int = 0,
    limit: int = 100,
    subject: str | None = Query(None),
    standard: str | None = Query(None),
    category: str | None = Query(None),
    search: str | None = Query(None),
) -> Any:
    """
    Retrieve questions for superusers with filtering and search.
    """
    _ = superuser  # Mark as used
    statement = select(Question)

    if subject:
        statement = statement.where(Question.subject == subject)
    if standard:
        statement = statement.where(Question.standard == standard)
    if category:
        statement = statement.where(Question.category == category)
    if search:
        statement = statement.where(col(Question.question_text).contains(search))

    statement = statement.offset(skip).limit(limit).order_by(col(Question.id))
    questions = session.exec(statement).all()
    return questions


@router.get("/stats")
def get_question_stats(
    session: SessionDep,
    superuser: Any = Depends(get_current_active_superuser),
) -> Any:
    """
    Get global question bank statistics.
    """
    _ = superuser
    total = session.exec(select(func.count(col(Question.id)))).one()

    # Subject breakdown
    subjects = session.exec(
        select(Question.subject, func.count(col(Question.id))).group_by(
            Question.subject
        )
    ).all()

    return {"total_questions": total, "subjects": {s: c for s, c in subjects if s}}


@router.get("/{id}", response_model=QuestionPublic)
def read_question(
    *,
    session: SessionDep,
    superuser: Any = Depends(get_current_active_superuser),
    id: UUID,
) -> Any:
    """
    Get question by ID.
    """
    _ = superuser
    question = session.get(Question, id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return question


@router.post("/export-pdf")
def export_questions_pdf(
    *,
    session: SessionDep,
    superuser: Any = Depends(get_current_active_superuser),
    question_ids: list[UUID],
) -> Any:
    """
    Export selected questions to a PDF file.
    """
    _ = superuser
    statement = select(Question).where(col(Question.id).in_(question_ids))
    questions = session.exec(statement).all()

    if not questions:
        raise HTTPException(status_code=404, detail="No questions found to export")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, "Global Question Bank Export", ln=True, align="C")
    pdf.set_font("helvetica", "", 10)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    pdf.cell(0, 10, f"Generated on: {now_str}", ln=True, align="R")
    pdf.ln(10)

    for i, q in enumerate(questions, 1):
        pdf.set_font("helvetica", "B", 12)
        pdf.multi_cell(0, 10, f"Q{i}. [{q.subject or 'General'}] {q.question_text}")

        pdf.set_font("helvetica", "", 11)
        if q.options:
            for opt, text in q.options.items():
                pdf.cell(0, 8, f"   ({opt}) {text}", ln=True)

        pdf.set_font("helvetica", "I", 9)
        pdf.cell(
            0,
            8,
            f"Marks: {q.marks} | Neg: {q.negative_marks} | Type: {q.question_type}",
            ln=True,
        )

        if q.solution_text:
            pdf.set_font("helvetica", "B", 10)
            pdf.cell(0, 8, "Solution:", ln=True)
            pdf.set_font("helvetica", "", 10)
            pdf.multi_cell(0, 8, q.solution_text)

        pdf.ln(5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

    output = BytesIO()
    pdf_bytes = pdf.output()
    output.write(pdf_bytes)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=extracted_questions.pdf"},
    )
