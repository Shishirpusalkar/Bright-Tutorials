import os
import sys
import logging
import json
from app.core import ai
from app.core.config import settings
from sqlmodel import Session, create_engine, select
from app.models import Test

# Add root to sys path
sys.path.append(os.getcwd())

logging.basicConfig(level=logging.INFO)

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


def test_ai_flow():
    with Session(engine) as session:
        test = session.exec(select(Test)).first()
        if not test:
            print("No tests found.")
            return

        print(f"Testing for Test: {test.title}")
        print(f"PDF URL: {test.question_paper_url}")

        file_path = test.question_paper_url.lstrip("/")
        if not os.path.exists(file_path):
            print(f"File NOT found at {file_path}")
            # Try with absolute path if needed
            return

        print("--- Testing OMEGA GO Pipeline ---")
        try:
            questions = ai.generate_questions_from_pdf(file_path)
            print(f"Generated {len(questions)} questions.")
            for i, q in enumerate(questions[:5]):
                print(f"  {i + 1}. {q.question_text[:50]}...")
        except Exception as e:
            print(f"AI Generation Failed: {e}")


if __name__ == "__main__":
    test_ai_flow()
