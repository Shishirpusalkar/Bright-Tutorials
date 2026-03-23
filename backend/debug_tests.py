from sqlmodel import Session, select
from app.core.db import engine
from app.models import Test
import uuid


def check_tests(user_id_str):
    uid = uuid.UUID(user_id_str)
    with Session(engine) as session:
        statement = select(Test).where(Test.created_by == uid)
        tests = session.exec(statement).all()
        print(f"Total tests for user {user_id_str}: {len(tests)}")
        for t in tests:
            print(
                f"ID: {t.id} | Title: {t.title} | Published: {t.is_published} | Questions: {len(t.questions)}"
            )


if __name__ == "__main__":
    # This is a template, I'll need to know the teacher's ID to run it effectively
    # But I can't easily get it from the prompt metadata without a query
    pass
