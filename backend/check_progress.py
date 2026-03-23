from sqlmodel import Session, select
from app.core.db import engine
from app.models import Test, TestGenerationConfig
import json


def check_progress():
    with Session(engine) as session:
        # Check last 5 tests
        tests = session.exec(
            select(Test).order_by(Test.created_at.desc()).limit(5)
        ).all()
        print(f"--- RECENT TESTS ({len(tests)}) ---")
        for t in tests:
            print(
                f"ID: {t.id} | Title: {t.title} | Published: {t.is_published} | Symmetry: {t.is_symmetrical}"
            )

        # Check last 5 configs
        configs = session.exec(
            select(TestGenerationConfig)
            .order_by(TestGenerationConfig.test_id.desc())
            .limit(5)
        ).all()
        print(f"\n--- RECENT CONFIGS ({len(configs)}) ---")
        for c in configs:
            report = c.parsing_report if isinstance(c.parsing_report, dict) else {}
            print(
                f"Test ID: {c.test_id} | Extracted: {report.get('total_extracted')} | Saved: {report.get('total_saved')}"
            )


if __name__ == "__main__":
    check_progress()
