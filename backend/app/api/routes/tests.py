import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sqlmodel import col, select

from app.core.email_service import send_test_scheduled_alert

from app.api.deps import CurrentUser, SessionDep
from app.core import ai
from app.models import (
    Attempt,
    Question,
    QuestionPublic,
    Test,
    TestGenerationConfig,
    TestPublic,
    UserRole,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tests", tags=["tests"])

UPLOAD_DIR = Path("static/uploads/tests")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/", response_model=Test)
def create_test(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    title: str = Form(...),
    description: str = Form(None),
    duration_minutes: int = Form(...),
    scheduled_at: str | None = Form(None),
    standard: str = Form(None),
    category: str = Form(None),
    positive_marks: int = Form(4),
    negative_marks: float = Form(-1.0),
    file: UploadFile = File(...),
) -> Any:
    """
    Create a new test with a PDF question paper.
    """
    if current_user.role != UserRole.TEACHER and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough privileges")

    # Check monetization limit: Max 3 tests for non-premium teachers
    # Teachers are now exempt from this limit (free of cost)
    if (
        current_user.role != UserRole.TEACHER
        and not current_user.is_premium
        and not current_user.is_superuser
    ):
        statement = select(Test).where(Test.created_by == current_user.id)
        test_count = len(session.exec(statement).all())
        if test_count >= 3:
            raise HTTPException(
                status_code=402,
                detail="Free tier limit reached. You can only create 3 tests on the plan. Please upgrade to unlock more!",
            )

    # Save the file
    file_id = uuid.uuid4()
    file_extension = Path(file.filename or "test.pdf").suffix
    file_name = f"{file_id}{file_extension}"
    file_path = UPLOAD_DIR / file_name

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Relative path for the URL
    question_paper_url = f"/static/uploads/tests/{file_name}"

    # Parse scheduling
    parsed_schedule = None
    if scheduled_at:
        try:
            # Expecting ISO format from frontend (e.g., 2023-10-27T10:30)
            parsed_schedule = datetime.fromisoformat(scheduled_at).replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            logger.warning(f"Failed to parse scheduled_at: {scheduled_at}")

    db_obj = Test(
        title=title,
        description=description,
        duration_minutes=duration_minutes,
        question_paper_url=question_paper_url,
        scheduled_at=parsed_schedule,
        standard=standard,
        category=category,
        positive_marks=positive_marks,
        negative_marks=negative_marks,
        created_by=current_user.id,
        is_published=True,  # Publishing immediately for now
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)

    # Email Alert: Test Scheduled
    send_test_scheduled_alert(
        teacher_email=str(current_user.email),
        test_title=title,
        scheduled_at=str(parsed_schedule) if parsed_schedule else None,
        subjects=[category] if category else [],
        total_questions=0,
        marking_scheme=f"+{positive_marks} / {negative_marks}",
    )

    # 3. AI Parsing & Storage (Additive)
    try:
        logger.info(f"Starting AI parsing for test: {db_obj.id}")
        # Run Gemini once per paper
        # Provide a default blueprint for legacy route
        default_blueprint = [
            {
                "section_name": "Section A",
                "subject": category or "General",
                "q_count": 50,  # Catch-all
                "pos_mark": float(positive_marks),
                "neg_mark": float(negative_marks),
            }
        ]
        ai_questions = ai.generate_questions_from_pdf(str(file_path), default_blueprint)

        # Handle backward compatibility (list return)
        if isinstance(ai_questions, tuple):
            ai_questions = ai_questions[0]

        for ai_q in ai_questions:
            from .omega import detect_visual_bbox, normalize_bbox_payload

            # Map AIQuestion to Question model
            q_options = ai_q.options or {}
            db_q = Question(
                test_id=db_obj.id,
                question_text=ai_q.question_text,
                option_a=q_options.get("A"),
                option_b=q_options.get("B"),
                option_c=q_options.get("C"),
                option_d=q_options.get("D"),
                options=ai_q.options,
                correct_option=ai_q.correct_option,
                marks=positive_marks,  # Default to test-level marking
                negative_marks=negative_marks,
                subject=ai_q.subject,
                section=ai_q.section,
                question_type=ai_q.question_type or "MCQ",
                solution_text=ai_q.solution_text,
                page_number=ai_q.page_number,
                has_visual=ai_q.has_visual,
                visual_tag=ai_q.visual_tag,
            )
            # detect_visual_bbox could be added here too if needed,
            # but usually tests.py is legacy. Adding it for consistency.
            if ai_q.has_visual:
                db_q.visual_bbox = normalize_bbox_payload(ai_q.figure_bbox)
                if not db_q.visual_bbox:
                    db_q.visual_bbox = detect_visual_bbox(
                        str(file_path), ai_q.page_number
                    )
            db_q.solution_bbox = getattr(ai_q, "solution_bbox", None)
            db_q.solution_bbox = normalize_bbox_payload(db_q.solution_bbox)

            session.add(db_q)

        session.commit()
        logger.info(
            f"Successfully stored {len(ai_questions)} questions for test {db_obj.id}"
        )
    except Exception as e:
        logger.error(f"AI Parsing failed but test was created: {str(e)}")
        # We don't fail the whole request if AI fails, but log it.
        # Teacher can manually add questions or retry later.

    return db_obj


@router.get("/", response_model=list[TestPublic])
def read_tests(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 1000,
) -> Any:
    """
    Retrieve tests.
    """
    # Students can see published tests, teachers can see all creators.
    # Role-based visibility
    if current_user.is_superuser or current_user.role == UserRole.ADMIN:
        # Superusers and Admins see everything
        statement = select(Test)
    elif current_user.role == UserRole.TEACHER:
        # Teachers see their own tests
        statement = select(Test).where(Test.created_by == current_user.id)
    else:
        # Student visibility logic
        now = datetime.now(timezone.utc)
        is_expired = (
            current_user.premium_expiry is not None
            and now > current_user.premium_expiry
        )

        # Start with published tests
        statement = select(Test).where(Test.is_published)

        # If expired, ONLY show tests already attempted
        if is_expired:
            statement = (
                statement.join(Attempt)
                .where(Attempt.student_id == current_user.id)
                .distinct()
            )

        # Filter by Standard (Class 11/12)
        if current_user.standard:
            # STRICT match standard exactly (e.g., "12th")
            statement = statement.where(Test.standard == current_user.standard)
        else:
            # If student has no standard set, they see nothing (safety)
            statement = statement.where(
                Test.standard == "NON_EXISTENT_STANDARD_FALLBACK"
            )

        # Filter by Stream (Engineering/Medical)
        if current_user.stream:
            stream = current_user.stream.lower()
            if stream == "engineering":
                # STRICT Engineering: JEE, JEE Mains, or JEE Advanced
                statement = statement.where(
                    col(Test.category).in_(["JEE", "JEE Mains", "JEE Advanced"])
                )
            elif stream == "medical":
                # STRICT Medical: NEET or Medical or NEET (Medical)
                statement = statement.where(
                    col(Test.category).in_(["NEET", "Medical", "NEET (Medical)"])
                )
            elif stream == "foundation":
                # STRICT Foundation
                statement = statement.where(Test.category == "Foundation")
            else:
                # Unknown stream, see nothing
                statement = statement.where(
                    Test.category == "NON_EXISTENT_STREAM_FALLBACK"
                )
        else:
            # If student has no stream set, they see nothing (safety)
            statement = statement.where(Test.category == "NON_EXISTENT_STREAM_FALLBACK")

    # Global pagination and ordering
    statement = statement.offset(skip).limit(limit)
    tests = session.exec(statement.order_by(col(Test.created_at).desc())).all()

    # Enrich with analytics for teachers/superusers
    results = []
    for test in tests:
        test_public = TestPublic.model_validate(test)

        # Calculate stats
        attempts_stmt = select(Attempt).where(Attempt.test_id == test.id)
        attempts = session.exec(attempts_stmt).all()

        test_public.submission_count = len(attempts)
        if attempts:
            test_public.average_score = sum(a.score or 0 for a in attempts) / len(
                attempts
            )

        # Fetch symmetry info from TestGenerationConfig
        config_stmt = select(TestGenerationConfig).where(
            TestGenerationConfig.test_id == test.id
        )
        config = session.exec(config_stmt).first()
        if config and config.parsing_report:
            test_public.is_symmetrical = config.parsing_report.get("is_symmetrical")
            test_public.symmetry_message = config.parsing_report.get("symmetry_message")

        results.append(test_public)

    return results


@router.get("/{id}", response_model=TestPublic)
def read_test(*, session: SessionDep, id: uuid.UUID) -> Any:
    """
    Get test by ID.
    """
    test = session.get(Test, id)
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    # Explicitly load questions to ensure they are included in TestPublic
    # SQLModel relationships might not load automatically during Pydantic serialization
    statement = (
        select(Question)
        .where(Question.test_id == id)
        .order_by(col(Question.question_number))
    )
    questions = session.exec(statement).all()

    # Create the public model and populate questions
    test_public = TestPublic.model_validate(test)

    # Runtime Deduplication by content_hash
    unique_questions = []
    seen_hashes = set()
    for q in questions:
        c_hash = q.content_hash
        if c_hash and c_hash in seen_hashes:
            logger.info(
                f"Runtime Deduplication: Skipping duplicate {q.id} (hash: {c_hash})"
            )
            continue
        if c_hash:
            seen_hashes.add(c_hash)
        unique_questions.append(QuestionPublic.model_validate(q))

    test_public.questions = unique_questions

    # Analytics for single test
    attempts_stmt = select(Attempt).where(Attempt.test_id == id)
    attempts = session.exec(attempts_stmt).all()
    test_public.submission_count = len(attempts)
    if attempts:
        test_public.average_score = sum(a.score for a in attempts) / len(attempts)

    return test_public


@router.post("/{id}/generate-questions", response_model=list[QuestionPublic])
def generate_questions(
    *, session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Any:
    """
    Generate questions from an existing test's PDF.
    """
    if current_user.role != UserRole.TEACHER and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough privileges")

    test = session.get(Test, id)
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    if not test.question_paper_url:
        raise HTTPException(status_code=400, detail="Test has no PDF question paper")

    # Extract text and generate
    file_path = Path(str(test.question_paper_url).lstrip("/"))
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found on disk")

    # Clear existing questions before generating new ones
    existing_questions = session.exec(
        select(Question).where(Question.test_id == id)
    ).all()
    for q in existing_questions:
        session.delete(q)
    session.commit()

    try:
        logger.info(f"Generating questions for test {id} from {file_path}")
        # Provide a default blueprint for legacy route
        default_blueprint = [
            {
                "section_name": "Section A",
                "subject": test.category or "General",
                "q_count": 50,  # Catch-all
                "pos_mark": float(test.positive_marks),
                "neg_mark": float(test.negative_marks),
            }
        ]
        ai_questions = ai.generate_questions_from_pdf(str(file_path), default_blueprint)
        logger.info(f"Successfully generated {len(ai_questions)} questions")
    except Exception as e:
        logger.error(f"AI Generation failed for test {id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Generation error: {str(e)}")

    db_questions = []
    for ai_q in ai_questions:
        from .omega import detect_visual_bbox, normalize_bbox_payload

        options = ai_q.options or {}

        db_q = Question(
            test_id=test.id,
            question_text=ai_q.question_text,
            option_a=options.get("A"),
            option_b=options.get("B"),
            option_c=options.get("C"),
            option_d=options.get("D"),
            options=ai_q.options,
            correct_option=ai_q.correct_option,
            marks=test.positive_marks,
            negative_marks=test.negative_marks,
            subject=ai_q.subject,
            section=ai_q.section,
            question_type=ai_q.question_type or "MCQ",
            solution_text=ai_q.solution_text,
            page_number=ai_q.page_number,
            has_visual=ai_q.has_visual,
            visual_tag=ai_q.visual_tag,
        )
        if ai_q.has_visual:
            db_q.visual_bbox = normalize_bbox_payload(ai_q.figure_bbox)
            if not db_q.visual_bbox:
                db_q.visual_bbox = detect_visual_bbox(str(file_path), ai_q.page_number)
        db_q.solution_bbox = getattr(ai_q, "solution_bbox", None)
        db_q.solution_bbox = normalize_bbox_payload(db_q.solution_bbox)

        session.add(db_q)
        db_questions.append(db_q)

    session.commit()

    # Update total_marks for the test
    test.total_marks = sum(q.marks for q in db_questions)
    session.add(test)
    session.commit()

    for q in db_questions:
        session.refresh(q)

    logger.info(
        f"Successfully saved {len(db_questions)} questions to database for test {id}"
    )
    return db_questions


@router.delete("/{id}")
def delete_test(
    *, session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Any:
    """
    Delete a test.
    """
    test = session.get(Test, id)
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    # Check permissions: Creator (if teacher) or Admin
    if (
        current_user.role != UserRole.ADMIN
        and not current_user.is_superuser
        and test.created_by != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Not enough privileges")

    # 1. Delete associated Omega configs manually (they don't cascade automatically)
    configs_stmt = select(TestGenerationConfig).where(
        TestGenerationConfig.test_id == id
    )
    configs = session.exec(configs_stmt).all()
    for config in configs:
        session.delete(config)

    # 2. Delete PDF file from disk
    if test.question_paper_url:
        # Strip leading slash if present
        relative_path = test.question_paper_url.lstrip("/")
        file_path = Path(relative_path)
        if file_path.exists() and file_path.is_file():
            try:
                file_path.unlink()
                logger.info(f"Deleted PDF file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to delete PDF file {file_path}: {e}")

    # 3. Delete the test record
    # Note: Questions and Attempts will be deleted via cascade_delete=True in Relationship
    session.delete(test)
    session.commit()

    return {"status": "success", "message": "Test deleted successfully"}
