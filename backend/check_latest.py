from sqlmodel import Session, select, func
from app.core.db import engine
from app.models import Test, Question, TestGenerationConfig
import json


def check_latest_activity():
    with Session(engine) as session:
        print("--- LATEST TESTS & QUESTION COUNTS ---")
        tests = session.exec(
            select(Test).order_by(Test.created_at.desc()).limit(5)
        ).all()
        for t in tests:
            q_count = session.exec(
                select(func.count(Question.id)).where(Question.test_id == t.id)
            ).one()
            print(
                f"Test: {t.title} | ID: {t.id} | Qs: {q_count} | Symmetrical: {t.is_symmetrical}"
            )

        print("\n--- LATEST CONFIGS ---")
        configs = session.exec(
            select(TestGenerationConfig)
            .order_by(TestGenerationConfig.id.desc())
            .limit(3)
        ).all()
        for c in configs:
            print(
                f"Test ID: {c.test_id} | Report: {json.dumps(c.parsing_report, indent=2) if c.parsing_report else 'None'}"
            )


if __name__ == "__main__":
    check_latest_activity()
