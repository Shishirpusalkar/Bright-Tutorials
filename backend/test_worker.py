import json
import uuid
from pathlib import Path
from app.api.routes.omega import process_pdf_background
from app.models import User
from sqlmodel import Session, select
from app.core.db import engine


def test_local_processing():
    # Use one of the existing PDFs in temp if any
    temp_dir = Path("static/uploads/temp")
    pdfs = list(temp_dir.glob("*.pdf"))
    if not pdfs:
        print("No PDFs found in temp dir to test.")
        return

    pdf_path = str(pdfs[0])
    job_id = str(uuid.uuid4())

    with Session(engine) as session:
        user = session.exec(select(User)).first()
        if not user:
            print("No user found in DB to associate with test.")
            return
        user_id = user.id

    config_data = {
        "title": "Test Local Paper",
        "duration": 180,
        "standard": "11th",
        "category": "JEE Mains",
        "subjects": {
            "Physics": {
                "sections": {
                    "Section A": {"marks": 4, "negative_marks": -1, "q_count": 1}
                }
            }
        },
    }

    print(f"--- TESTING LOCAL PROCESSING ---")
    print(f"File: {pdf_path}")
    print(f"Job ID: {job_id}")

    try:
        process_pdf_background(job_id, pdf_path, config_data, user_id)
        print("--- LOCAL SUCCESS ---")
    except Exception as e:
        print(f"--- LOCAL FAILURE: {e} ---")


if __name__ == "__main__":
    test_local_processing()
