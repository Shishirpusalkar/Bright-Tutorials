import csv
import io
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import col, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Attempt,
    AttemptAnswer,
    AttemptAnswerPublic,
    AttemptPublic,
    AttemptStatus,
    Question,
    Test,
    User,
)
from app.core.email_service import send_attempt_started_alert
from app.services.analysis import generate_attempt_analysis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/attempts", tags=["attempts"])


class SubmitQuestionResponse(BaseModel):
    question_id: UUID
    selected_option: str | None = None
    answer_text: str | None = None
    time_spent_seconds: int = 0


class SubmitTestRequest(BaseModel):
    test_id: UUID
    responses: list[SubmitQuestionResponse]
    tab_switch_count: int = 0


@router.post("/submit", response_model=Attempt)
def submit_test(
    request: SubmitTestRequest,
    current_user: CurrentUser,
    session: SessionDep,
):
    # Check Limit for Free Users
    if not current_user.is_premium and not current_user.is_superuser:
        # Count existing attempts
        statement = select(func.count(Attempt.id)).where(
            Attempt.student_id == current_user.id
        )
        count = session.exec(statement).one()
        if count >= 3:
            raise HTTPException(
                status_code=403,
                detail="Free plan limit reached (3 tests). Upgrade to Premium.",
            )

    # Verify Test exists
    test = session.get(Test, request.test_id)
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    # Create Attempt
    attempt = Attempt(
        student_id=current_user.id,
        test_id=test.id,
        status=AttemptStatus.SUBMITTED,
        tab_switch_count=request.tab_switch_count,
    )
    session.add(attempt)
    session.commit()
    session.refresh(attempt)

    # Email Alert: Student Attempt Started (first attempt only per student+test)
    prior_count = session.exec(
        select(func.count(Attempt.id)).where(
            Attempt.student_id == current_user.id,
            Attempt.test_id == test.id,
        )
    ).one()
    if prior_count <= 1:
        teacher = session.get(User, test.created_by)
        teacher_email = str(teacher.email) if teacher else ""
        send_attempt_started_alert(
            teacher_email=teacher_email,
            student_name=current_user.full_name or str(current_user.email),
            student_email=str(current_user.email),
            test_title=test.title,
            login_time=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        )

    total_score = 0
    questions_map = {q.id: q for q in test.questions}

    try:
        for resp in request.responses:
            question = questions_map.get(resp.question_id)
            if not question:
                continue

            is_correct = False
            marks = 0

            if question.question_type in ["MCQ", "SCQ"]:
                if (
                    resp.selected_option
                    and question.correct_option
                    and resp.selected_option.upper().strip()
                    == question.correct_option.upper().strip()
                ):
                    is_correct = True
                    marks = question.marks
            elif question.question_type in ["NUMERIC", "INTEGER"]:
                if resp.answer_text and question.correct_option:
                    user_ans = resp.answer_text.strip()
                    correct_ans = question.correct_option.strip()
                    if user_ans == correct_ans:
                        is_correct = True
                    else:
                        # Try float comparison
                        try:
                            if float(user_ans) == float(correct_ans):
                                is_correct = True
                        except ValueError:
                            pass

                    if is_correct:
                        marks = question.marks

            if is_correct:
                total_score += marks
            else:
                # Deduct negative marks if student provided an answer
                is_attempted = (resp.selected_option is not None) or (
                    resp.answer_text is not None
                )
                if is_attempted:
                    # Use test.negative_marks (e.g. -1.0)
                    neg_val = getattr(test, "negative_marks", -1.0) or -1.0
                    total_score += neg_val  # Adding a negative value
                    marks = int(neg_val)

            answer_record = AttemptAnswer(
                attempt_id=attempt.id,
                question_id=question.id,
                selected_option=resp.selected_option,
                answer_text=resp.answer_text,
                is_correct=is_correct,
                marks_obtained=marks,
                time_spent_seconds=resp.time_spent_seconds,
            )
            session.add(answer_record)

        # Flush to ensure answers are in the DB before relationships are accessed
        session.flush()
        attempt.score = int(total_score)

        # Trigger AI Performance Analysis
        try:
            # Prepare summary for AI
            summary_details = []
            for ans in attempt.answers:
                q = questions_map.get(ans.question_id)
                summary_details.append(
                    {
                        "question_text": q.question_text if q else "N/A",
                        "is_correct": ans.is_correct,
                        "marks_obtained": ans.marks_obtained,
                        "subject": q.subject if q else "General",
                    }
                )

            analysis = generate_attempt_analysis(
                student_name=current_user.full_name or "Student",
                test_title=test.title,
                total_score=int(total_score),
                max_marks=test.total_marks,
                attempts_details=summary_details,
            )
            attempt.ai_analysis = analysis
        except Exception as ai_err:
            logger.error(f"AI Analysis generation failed: {str(ai_err)}")
            attempt.ai_analysis = "AI Analysis is currently unavailable. Great job on completing the test!"

        session.add(attempt)
        session.commit()
        session.refresh(attempt)
    except Exception as e:
        logger.error(
            f"Error during test submission for user {current_user.id}, test {request.test_id}: {str(e)}"
        )
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

    return attempt


@router.get("/my", response_model=list[AttemptPublic])
def read_user_attempts(
    current_user: CurrentUser,
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
):
    """
    Retrieve attempts for the current user.
    """
    statement = (
        select(Attempt)
        .where(Attempt.student_id == current_user.id)
        .offset(skip)
        .limit(limit)
    )
    attempts = session.exec(statement).all()

    # Ensure answers are loaded if needed for public model
    for attempt in attempts:
        _ = attempt.answers

    return attempts


@router.get("/stats/me", response_model=dict)
def get_attempt_stats(
    current_user: CurrentUser,
    session: SessionDep,
):
    statement = select(func.count(Attempt.id)).where(
        Attempt.student_id == current_user.id
    )
    count = session.exec(statement).one()
    return {"attempt_count": count, "is_premium": current_user.is_premium}


@router.get("/{id}", response_model=AttemptPublic)
def read_attempt(
    id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
):
    # Eager load answers
    # Using SQLModel select is better
    statement = select(Attempt).where(Attempt.id == id)
    attempt = session.exec(statement).first()

    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt.student_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Not authorized to view this attempt"
        )

    # Convert to public model and enrich answers
    result = AttemptPublic.model_validate(attempt)

    # Fetch all questions for this test to ensure even unattempted ones are shown
    questions_statement = (
        select(Question)
        .where(Question.test_id == attempt.test_id)
        .order_by(col(Question.question_number))
    )
    all_questions = session.exec(questions_statement).all()

    # Map existing answers by question_id
    answers_map = {ans.question_id: ans for ans in attempt.answers}

    enriched_answers = []
    for question in all_questions:
        ans = answers_map.get(question.id)
        if ans:
            # Convert DB answer to public model
            ans_public = AttemptAnswerPublic.model_validate(ans)
        else:
            # Create a placeholder for unattempted questions
            ans_public = AttemptAnswerPublic(
                id=uuid4(),
                question_id=question.id,
                is_correct=False,
                marks_obtained=0,
                time_spent_seconds=0,
                selected_option=None,
                answer_text=None,
            )

        # Enrich with question details
        ans_public.question_text = question.question_text
        ans_public.solution_text = question.solution_text
        ans_public.correct_option = question.correct_option
        # For numeric/integer, the correct_option field stores the actual value
        if question.question_type in ["NUMERIC", "INTEGER"]:
            ans_public.correct_answer_text = question.correct_option

        # Additional enrichment for detailed solutions
        ans_public.marks = question.marks
        ans_public.organic_metadata = question.organic_metadata
        ans_public.diagram_description = question.diagram_description
        ans_public.has_visual = question.has_visual
        ans_public.visual_tag = question.visual_tag
        ans_public.question_type = question.question_type
        ans_public.page_number = question.page_number
        ans_public.visual_bbox = question.visual_bbox
        ans_public.solution_bbox = question.solution_bbox
        ans_public.image_url = question.image_url
        ans_public.question_paper_url = test.question_paper_url

        enriched_answers.append(ans_public)

    result.answers = enriched_answers
    return result


@router.get("/export/{test_id}")
def export_attempts(
    test_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
):
    # Verify Test exists and user is owner
    test = session.get(Test, test_id)
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    if test.created_by != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Not authorized to export results for this test"
        )

    # Fetch attempts
    statement = select(Attempt).where(Attempt.test_id == test_id)
    attempts = session.exec(statement).all()

    # Identify Subjects
    subjects = sorted({q.subject or "General" for q in test.questions})

    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    header = [
        "Student Name",
        "Email",
        "Status",
        "Total Score",
        "Max Marks",
        "Percentage",
        "Time Taken (min)",
        "Tab Switches",
        "Submission Date",
    ]
    # Add Subject Columns
    for sub in subjects:
        header.append(f"{sub} Score")

    writer.writerow(header)

    for attempt in attempts:
        student = session.get(User, attempt.student_id)
        student_name = student.full_name if student else "Unknown"
        student_email = student.email if student else "Unknown"

        max_marks = test.total_marks if test.total_marks > 0 else 0

        percentage = 0
        if max_marks > 0:
            percentage = round((attempt.score / max_marks) * 100, 2)

        duration = 0
        if attempt.submitted_at and attempt.started_at:
            duration = round(
                (attempt.submitted_at - attempt.started_at).total_seconds() / 60, 2
            )

        # Calculate Subject Scores
        subject_scores = dict.fromkeys(subjects, 0)
        # We need to access answers. Ideally eager load, but lazy load works in sync
        for ans in attempt.answers:
            # We need the question to know the subject
            # ans.question might be lazy loaded.
            question = next(
                (q for q in test.questions if q.id == ans.question_id), None
            )
            if question:
                sub = question.subject or "General"
                # Accumulate the net marks (positive or negative)
                subject_scores[sub] += ans.marks_obtained

        row = [
            student_name,
            student_email,
            attempt.status,
            attempt.score,
            max_marks,
            f"{percentage}%",
            duration,
            attempt.tab_switch_count,
            attempt.submitted_at.strftime("%Y-%m-%d %H:%M:%S")
            if attempt.submitted_at
            else "Not Submitted",
        ]

        for sub in subjects:
            row.append(subject_scores.get(sub, 0))

        writer.writerow(row)

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=results_{test_id}.csv"},
    )
