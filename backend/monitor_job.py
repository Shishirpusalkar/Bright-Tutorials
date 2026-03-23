from sqlmodel import Session, select
from app.core.db import engine
from app.models import Test, TestGenerationConfig
import json
from uuid import UUID


def monitor_job(job_id_str):
    try:
        job_id = UUID(job_id_str)
    except:
        job_id = None

    with Session(engine) as session:
        print(f"--- MONITORING JOB: {job_id_str} ---")

        # Check for matching config
        configs = session.exec(select(TestGenerationConfig)).all()
        found_config = None
        for c in configs:
            if str(c.test_id) == job_id_str or (
                c.parsing_report
                and isinstance(c.parsing_report, dict)
                and c.parsing_report.get("job_id") == job_id_str
            ):
                found_config = c
                break

        if found_config:
            print(f"Found Config for Test ID: {found_config.test_id}")
            print(
                f"Parsing Report: {json.dumps(found_config.parsing_report, indent=2)}"
            )
        else:
            print("No matching config found yet.")

        # Check last 3 tests to see if any new record exists
        tests = session.exec(
            select(Test).order_by(Test.created_at.desc()).limit(3)
        ).all()
        print("\n--- LATEST TESTS ---")
        for t in tests:
            print(f"ID: {t.id} | Title: {t.title} | Symmetry: {t.is_symmetrical}")


if __name__ == "__main__":
    monitor_job("366411d7-a0e1-4fc4-afdd-0d7a864f62c2")
