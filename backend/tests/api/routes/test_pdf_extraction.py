"""
Unit and integration tests for the PDF extraction pipeline.

Covers the testing strategy from docs/pdf_extraction_enhancement.md:
- Unit Tests: each component (text extraction, caching) in isolation.
- Integration Tests: full workflow from PDF upload to data retrieval.
"""

import hashlib
import io
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_pdf_bytes() -> bytes:
    """Return the bytes of a minimal valid PDF for testing."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f \n"
        b"0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"
    )


def _pdf_hash(pdf_bytes: bytes) -> str:
    return hashlib.sha256(pdf_bytes).hexdigest()


# ---------------------------------------------------------------------------
# Unit Tests — Redis cache
# ---------------------------------------------------------------------------

class TestRedisCacheUnit:
    """Unit tests for the Redis caching service."""

    def test_cache_miss_returns_none_when_redis_unavailable(self) -> None:
        from app.core import redis_cache

        with patch.object(redis_cache, "_redis_client", None):
            with patch("redis.from_url", side_effect=ConnectionRefusedError):
                result = redis_cache.get_cached_extraction("nonexistent_hash")
        assert result is None

    def test_set_and_get_roundtrip(self) -> None:
        from app.core import redis_cache

        mock_client = MagicMock()
        stored: dict[str, Any] = {}

        def _set(key: str, value: str, ex: int | None = None) -> None:
            stored[key] = value

        def _get(key: str) -> str | None:
            return stored.get(key)

        mock_client.set.side_effect = _set
        mock_client.get.side_effect = _get
        mock_client.ping.return_value = True

        with patch.object(redis_cache, "_redis_client", mock_client):
            pdf_hash = "abc123"
            data = {"questions": [{"id": "1", "question_text": "What is 2+2?"}]}
            redis_cache.set_cached_extraction(pdf_hash, data, ttl=60)
            result = redis_cache.get_cached_extraction(pdf_hash)

        assert result == data

    def test_invalidate_calls_delete(self) -> None:
        from app.core import redis_cache

        mock_client = MagicMock()
        mock_client.delete.return_value = 1

        with patch.object(redis_cache, "_redis_client", mock_client):
            success = redis_cache.invalidate_extraction("some_hash")

        assert success is True
        mock_client.delete.assert_called_once_with("pdf_extraction:some_hash")

    def test_set_returns_false_on_redis_error(self) -> None:
        from app.core import redis_cache

        mock_client = MagicMock()
        mock_client.set.side_effect = RuntimeError("connection lost")

        with patch.object(redis_cache, "_redis_client", mock_client):
            success = redis_cache.set_cached_extraction("hash", {"questions": []})

        assert success is False

    def test_ttl_uses_settings_default(self) -> None:
        from app.core import redis_cache

        mock_client = MagicMock()
        with patch.object(redis_cache, "_redis_client", mock_client):
            redis_cache.set_cached_extraction("hash_ttl", {"questions": []})
            call_kwargs = mock_client.set.call_args
            # ex kwarg should equal settings.PDF_CACHE_TTL_SECONDS
            assert call_kwargs[1]["ex"] == settings.PDF_CACHE_TTL_SECONDS


# ---------------------------------------------------------------------------
# Unit Tests — PDF parser (PyPDF2 / pypdf)
# ---------------------------------------------------------------------------

class TestPdfParserUnit:
    """Unit tests for the PyPDF2-based PDF parser."""

    def test_parse_returns_result_object(self, tmp_path: Path) -> None:
        from app.services.pdf_parser import parse_pdf

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(_make_minimal_pdf_bytes())
        result = parse_pdf(pdf_file)
        assert result is not None
        assert isinstance(result.pages, list)
        assert isinstance(result.metadata, dict)

    def test_parse_raises_for_missing_file(self, tmp_path: Path) -> None:
        from app.services.pdf_parser import parse_pdf

        with pytest.raises(FileNotFoundError):
            parse_pdf(tmp_path / "nonexistent.pdf")

    def test_empty_pdf_marks_all_pages_for_ocr(self, tmp_path: Path) -> None:
        from app.services.pdf_parser import parse_pdf

        pdf_file = tmp_path / "empty.pdf"
        pdf_file.write_bytes(_make_minimal_pdf_bytes())
        result = parse_pdf(pdf_file)
        # Minimal PDF has no real text, so every page should need OCR
        assert len(result.ocr_required_pages) == len(result.pages)
        assert result.has_text_layer is False

    def test_full_text_property(self, tmp_path: Path) -> None:
        from app.services.pdf_parser import ParsedPDFResult

        result = ParsedPDFResult(pages=["Hello", "", "World"])
        assert "Hello" in result.full_text
        assert "World" in result.full_text


# ---------------------------------------------------------------------------
# Unit Tests — ai_integration route helpers
# ---------------------------------------------------------------------------

class TestAiIntegrationHelpers:
    """Unit tests for helper functions in the Gemini AI route."""

    def test_compute_pdf_hash_is_deterministic(self, tmp_path: Path) -> None:
        from app.api.routes.ai_integration import _compute_pdf_hash

        pdf_bytes = _make_minimal_pdf_bytes()
        f = tmp_path / "a.pdf"
        f.write_bytes(pdf_bytes)
        hash1 = _compute_pdf_hash(f)
        hash2 = _compute_pdf_hash(f)
        assert hash1 == hash2
        assert hash1 == _pdf_hash(pdf_bytes)

    def test_compute_pdf_hash_differs_for_different_files(
        self, tmp_path: Path
    ) -> None:
        from app.api.routes.ai_integration import _compute_pdf_hash

        f1 = tmp_path / "a.pdf"
        f2 = tmp_path / "b.pdf"
        f1.write_bytes(_make_minimal_pdf_bytes())
        f2.write_bytes(_make_minimal_pdf_bytes() + b"\x00")
        assert _compute_pdf_hash(f1) != _compute_pdf_hash(f2)

    def test_questions_to_xml_structure(self) -> None:
        from app.api.routes.ai_integration import _questions_to_xml

        questions = [{"id": "1", "question_text": "Q1", "options": None}]
        xml_bytes = _questions_to_xml(questions)
        assert b"<extraction>" in xml_bytes
        assert b"<question>" in xml_bytes
        assert b"Q1" in xml_bytes

    def test_questions_to_xml_escapes_special_chars(self) -> None:
        from app.api.routes.ai_integration import _questions_to_xml

        questions = [{"question_text": "a < b & c > d \"quote\""}]
        xml_bytes = _questions_to_xml(questions)
        # Must be parseable XML (would raise if unescaped)
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_bytes)
        q_text = root.find("question/question_text")
        assert q_text is not None
        assert "a < b & c > d" in (q_text.text or "")


# ---------------------------------------------------------------------------
# Integration Tests — full upload → retrieve flow
# ---------------------------------------------------------------------------

class TestPdfExtractionIntegration:
    """
    Integration tests for the Gemini PDF extraction endpoint.

    AI calls are mocked so no real API key is required.
    """

    @pytest.fixture
    def client(self) -> TestClient:
        from app.main import app

        return TestClient(app)

    @pytest.fixture
    def pdf_bytes(self) -> bytes:
        return _make_minimal_pdf_bytes()

    def _mock_ai_questions(self) -> list[Any]:
        q = MagicMock()
        q.question_text = "What is 1+1?"
        q.options = {"A": "1", "B": "2", "C": "3", "D": "4"}
        q.correct_option = "B"
        q.solution_text = "Simple addition."
        q.question_type = "SCQ"
        q.subject = "Math"
        q.section = "Arithmetic"
        q.marks = 4
        q.negative_marks = -1.0
        return [q]

    def test_upload_pdf_returns_success(
        self, client: TestClient, pdf_bytes: bytes
    ) -> None:
        with patch(
            "app.api.routes.ai_integration.generate_questions_from_pdf",
            return_value=self._mock_ai_questions(),
        ), patch("app.core.redis_cache.get_redis", return_value=None):
            resp = client.post(
                f"{settings.API_V1_STR}/upload-pdf",
                files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "questions" in body
        assert len(body["questions"]) == 1
        assert body["questions"][0]["question_text"] == "What is 1+1?"

    def test_upload_pdf_rejects_non_pdf(self, client: TestClient) -> None:
        resp = client.post(
            f"{settings.API_V1_STR}/upload-pdf",
            files={"file": ("doc.txt", io.BytesIO(b"hello"), "text/plain")},
        )
        assert resp.status_code == 400

    def test_upload_pdf_returns_pdf_hash(
        self, client: TestClient, pdf_bytes: bytes
    ) -> None:
        with patch(
            "app.api.routes.ai_integration.generate_questions_from_pdf",
            return_value=self._mock_ai_questions(),
        ), patch("app.core.redis_cache.get_redis", return_value=None):
            resp = client.post(
                f"{settings.API_V1_STR}/upload-pdf",
                files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            )
        body = resp.json()
        assert "pdf_hash" in body
        assert body["pdf_hash"] == _pdf_hash(pdf_bytes)

    def test_upload_pdf_xml_format(
        self, client: TestClient, pdf_bytes: bytes
    ) -> None:
        with patch(
            "app.api.routes.ai_integration.generate_questions_from_pdf",
            return_value=self._mock_ai_questions(),
        ), patch("app.core.redis_cache.get_redis", return_value=None):
            resp = client.post(
                f"{settings.API_V1_STR}/upload-pdf?response_format=xml",
                files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            )
        assert resp.status_code == 200
        assert "xml" in resp.headers["content-type"]
        assert b"<extraction>" in resp.content

    def test_upload_pdf_invalid_format_rejected(
        self, client: TestClient, pdf_bytes: bytes
    ) -> None:
        with patch(
            "app.api.routes.ai_integration.generate_questions_from_pdf",
            return_value=self._mock_ai_questions(),
        ), patch("app.core.redis_cache.get_redis", return_value=None):
            resp = client.post(
                f"{settings.API_V1_STR}/upload-pdf?response_format=csv",
                files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            )
        assert resp.status_code == 400

    def test_retrieve_returns_404_for_unknown_hash(
        self, client: TestClient
    ) -> None:
        with patch("app.core.redis_cache.get_redis", return_value=None):
            resp = client.get(
                f"{settings.API_V1_STR}/retrieve-pdf/unknownhash123"
            )
        assert resp.status_code == 404

    def test_redis_cache_hit_skips_ai(
        self, client: TestClient, pdf_bytes: bytes
    ) -> None:
        cached_payload = {
            "questions": [
                {
                    "id": "cached-id",
                    "question_text": "Cached question",
                    "options": {},
                    "correct_option": "A",
                    "solution_text": "",
                    "question_type": "SCQ",
                    "subject": "Physics",
                    "section": "Mechanics",
                    "marks": 4,
                    "negative_marks": -1.0,
                }
            ]
        }
        with patch(
            "app.api.routes.ai_integration.get_cached_extraction",
            return_value=cached_payload,
        ) as mock_cache, patch(
            "app.api.routes.ai_integration.generate_questions_from_pdf"
        ) as mock_ai:
            resp = client.post(
                f"{settings.API_V1_STR}/upload-pdf",
                files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            )
        assert resp.status_code == 200
        mock_ai.assert_not_called()
        body = resp.json()
        assert body["questions"][0]["question_text"] == "Cached question"
