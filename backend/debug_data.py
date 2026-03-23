"""
Debug script to inspect recent database records.
"""

from sqlmodel import Session, select

from app.core.db import engine
from app.models.attempt import Attempt
from app.models.question import Question
from app.models.test import Test


def debug_data() -> None:
    """
    Fetch and print summaries of the most recent tests and attempts.
    """
    with Session(engine) as session:
        # 1. Inspect Recent Tests
        tests = session.exec(
            select(Test).order_by(Test.created_at.desc()).limit(5)
        ).all()
        print(f"--- RECENT TESTS ({len(tests)}) ---")  # noqa: T201

        for t in tests:
            questions = session.exec(
                select(Question).where(Question.test_id == t.id)
            ).all()

            print(f"Test ID: {t.id} | Title: {t.title} | Questions: {len(questions)}")  # noqa: T201
            if questions:
                first_q = questions[0]
                sol_preview = (
                    (first_q.solution_text[:50] + "...")
                    if first_q.solution_text
                    else "NONE"
                )
                print(f"  First Q Solution: {sol_preview}")  # noqa: T201
                print(f"  First Q Correct Option: {first_q.correct_option}")  # noqa: T201

        # 2. Inspect Recent Attempts
        attempts = session.exec(
            select(Attempt).order_by(Attempt.started_at.desc()).limit(5)
        ).all()
        print(f"\n--- RECENT ATTEMPTS ({len(attempts)}) ---")  # noqa: T201

        for a in attempts:
            # RELATIONSHIP CHECK: Ensure answers are counted correctly
            # Note: Relationship is accessed while session is active.
            ans_count = len(a.answers) if a.answers is not None else 0
            print(  # noqa: T201
                f"Attempt ID: {a.id} | Test ID: {a.test_id} | "
                f"Score: {a.score} | Answers: {ans_count}"
            )


if __name__ == "__main__":
    debug_data()
