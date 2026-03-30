"""
Performance tests for the PDF extraction pipeline.

Measures timing for various document sizes and types as described in
docs/pdf_extraction_enhancement.md:
"Performance Tests: Measure the time taken for various document sizes and types."

These tests are marked with @pytest.mark.performance so they can be run
selectively:
    pytest -m performance backend/tests/performance/
"""

import io
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_pdf_bytes(num_pages: int = 1, text_per_page: str = "") -> bytes:
    """Build a minimal multi-page PDF for performance benchmarking."""
    objects = []

    # Page objects (3 0 R onwards)
    page_refs = []
    for i in range(num_pages):
        obj_id = 3 + i * 2
        page_refs.append(f"{obj_id} 0 R")
        # Content stream with optional text
        stream = f"BT /F1 12 Tf 50 750 Td ({text_per_page[:100]}) Tj ET"
        content_obj = obj_id + 1
        objects.append((content_obj, f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream"))
        objects.append((obj_id, f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_obj} 0 R >>"))

    # Catalog and Pages dict
    kids = " ".join(page_refs)
    pages_dict = f"<< /Type /Pages /Kids [{kids}] /Count {num_pages} >>"

    header = b"%PDF-1.4\n"
    body_parts = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        f"2 0 obj\n{pages_dict}\nendobj\n".encode(),
    ]
    for obj_id, obj_body in sorted(objects):
        body_parts.append(f"{obj_id} 0 obj\n{obj_body}\nendobj\n".encode())

    body = b"".join(body_parts)
    xref_offset = len(header) + len(body)
    trailer = (
        f"\nxref\n0 1\n0000000000 65535 f \n"
        f"trailer\n<< /Size 1 /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF"
    ).encode()

    return header + body + trailer


def _mock_ai_questions(count: int = 5) -> list[Any]:
    """Return a list of mock AI question objects."""
    questions = []
    for i in range(count):
        q = MagicMock()
        q.question_text = f"Performance test question {i + 1}?"
        q.options = {"A": "opt1", "B": "opt2", "C": "opt3", "D": "opt4"}
        q.correct_option = "A"
        q.solution_text = "Test solution."
        q.question_type = "SCQ"
        q.subject = "Physics"
        q.section = "Mechanics"
        q.marks = 4
        q.negative_marks = -1.0
        questions.append(q)
    return questions


# ---------------------------------------------------------------------------
# Performance fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def perf_client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Performance Tests
# ---------------------------------------------------------------------------

@pytest.mark.performance
class TestPdfExtractionPerformance:
    """
    Measures end-to-end time for PDF extraction under varying document sizes.
    Each test asserts that processing completes within a reasonable time budget.
    """

    def _upload_pdf(self, client: Any, pdf_bytes: bytes, question_count: int) -> tuple[float, Any]:
        """Perform upload and return (elapsed_seconds, response_body)."""
        from app.core.config import settings

        with patch(
            "app.api.routes.ai_integration.generate_questions_from_pdf",
            return_value=_mock_ai_questions(question_count),
        ), patch("app.core.redis_cache.get_redis", return_value=None):
            start = time.perf_counter()
            resp = client.post(
                f"{settings.API_V1_STR}/upload-pdf",
                files={"file": ("perf.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            )
            elapsed = time.perf_counter() - start

        return elapsed, resp.json()

    def test_single_page_pdf_under_5s(self, perf_client: Any) -> None:
        """A 1-page PDF should be processed in under 5 seconds (mock AI)."""
        pdf_bytes = _build_pdf_bytes(num_pages=1, text_per_page="Hello World")
        elapsed, body = self._upload_pdf(perf_client, pdf_bytes, question_count=5)
        assert body.get("success") is True, f"Upload failed: {body}"
        assert elapsed < 5.0, f"Single page took {elapsed:.2f}s (expected <5s)"

    def test_ten_page_pdf_under_10s(self, perf_client: Any) -> None:
        """A 10-page PDF should be processed in under 10 seconds (mock AI)."""
        pdf_bytes = _build_pdf_bytes(num_pages=10, text_per_page="Sample text " * 5)
        elapsed, body = self._upload_pdf(perf_client, pdf_bytes, question_count=30)
        assert body.get("success") is True, f"Upload failed: {body}"
        assert elapsed < 10.0, f"10-page PDF took {elapsed:.2f}s (expected <10s)"

    def test_redis_cache_hit_under_1s(self, perf_client: Any) -> None:
        """A Redis cache hit should be served in under 1 second."""
        from app.core.config import settings

        cached_payload = {"questions": _mock_ai_questions(20)}
        pdf_bytes = _build_pdf_bytes(num_pages=5)

        with patch(
            "app.api.routes.ai_integration.get_cached_extraction",
            return_value=cached_payload,
        ):
            start = time.perf_counter()
            resp = perf_client.post(
                f"{settings.API_V1_STR}/upload-pdf",
                files={"file": ("cached.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            )
            elapsed = time.perf_counter() - start

        assert resp.status_code == 200
        assert elapsed < 1.0, f"Cache hit took {elapsed:.2f}s (expected <1s)"

    def test_pdf_hash_computation_is_fast(self, tmp_path: Path) -> None:
        """SHA-256 hash of a 1 MB file should complete in under 0.5 seconds."""
        from app.api.routes.ai_integration import _compute_pdf_hash

        large_pdf = tmp_path / "large.pdf"
        # Write 1 MB of data
        large_pdf.write_bytes(_build_pdf_bytes(num_pages=50, text_per_page="x" * 200))

        start = time.perf_counter()
        _compute_pdf_hash(large_pdf)
        elapsed = time.perf_counter() - start

        assert elapsed < 0.5, f"Hash computation took {elapsed:.3f}s (expected <0.5s)"

    def test_xml_serialization_under_2s(self) -> None:
        """Serialising 100 questions to XML should take under 2 seconds."""
        from app.api.routes.ai_integration import _questions_to_xml

        questions = [
            {
                "id": str(i),
                "question_text": f"Question {i}" * 5,
                "options": str({"A": "opt1", "B": "opt2"}),
                "correct_option": "A",
                "solution_text": "Solution.",
                "question_type": "SCQ",
                "subject": "Chemistry",
                "section": "Organic",
                "marks": "4",
                "negative_marks": "-1.0",
            }
            for i in range(100)
        ]

        start = time.perf_counter()
        xml_bytes = _questions_to_xml(questions)
        elapsed = time.perf_counter() - start

        assert len(xml_bytes) > 0
        assert elapsed < 2.0, f"XML serialisation took {elapsed:.3f}s (expected <2s)"
