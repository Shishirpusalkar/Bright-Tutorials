"""
Script to identify intra-test duplicate questions based on content hash.
"""

import hashlib

from sqlmodel import Session, select

from app.core.db import engine
from app.models.question import Question


def get_content_hash(text: str, options: dict | None = None) -> str:
    """
    Generate a stable SHA-256 hash for normalized question text and options.
    Matches the logic in omega.py.
    """
    if not text:
        return ""
    clean_text = "".join(filter(str.isalnum, text.lower()))

    opt_str = ""
    if options and isinstance(options, dict):
        clean_opts = []
        for v in options.values():
            if v:
                clean_opts.append("".join(filter(str.isalnum, str(v).lower())))
        clean_opts.sort()
        opt_str = "|".join(clean_opts)

    combined = f"{clean_text}#{opt_str}"
    return hashlib.sha256(combined.encode()).hexdigest()


def check_duplicates() -> None:
    """
    Scan all tests and identify questions with identical text within the same test.
    """
    with Session(engine) as session:
        # Get all unique test_ids
        test_ids = session.exec(select(Question.test_id).distinct()).all()
        print(f"Checking {len(test_ids)} tests for intra-test duplicates...")  # noqa: T201

        total_dups = 0
        for t_id in test_ids:
            questions = session.exec(
                select(Question).where(Question.test_id == t_id)
            ).all()

            seen_hashes = {}
            for q in questions:
                h = get_content_hash(q.question_text, q.options)
                if h in seen_hashes:
                    print(  # noqa: T201
                        f"INTRA-TEST DUP in Test {t_id}: Q ID {q.id} matches "
                        f"{seen_hashes[h].id}"
                    )
                    print(f"    Text: {q.question_text[:50]}...")  # noqa: T201
                    total_dups += 1
                else:
                    seen_hashes[h] = q

        print(f"Total intra-test duplicates found: {total_dups}")  # noqa: T201


if __name__ == "__main__":
    check_duplicates()
