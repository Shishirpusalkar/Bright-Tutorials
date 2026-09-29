"""
DeepSeek AI client for OCR-based text extraction from PDF page images.

Implements step 3 of docs/process_flow.md (DeepSeek branch):
"If the document is scanned, OCR processing is initiated using DeepSeek OCR
to extract text."

Uses the OpenAI-compatible DeepSeek API endpoint. Requires DEEPSEEK_API_KEY
to be set in the environment / .env file.
"""

import base64
import logging
import time
from io import BytesIO
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_INITIAL_DELAY = 2  # seconds


def _get_openai_client():  # type: ignore[return]
    """Return an OpenAI client configured for the DeepSeek endpoint."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError(
            "openai package is required. Install with: pip install openai"
        ) from exc

    if not settings.DEEPSEEK_API_KEY:
        raise RuntimeError(
            "DEEPSEEK_API_KEY is not configured. "
            "Set it in your .env file to enable DeepSeek OCR."
        )

    return OpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
    )


def _encode_image_to_base64(image_path: str | Path) -> str:
    """Return a Base-64 encoded JPEG/PNG string from an image file."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_text_from_image(image_path: str | Path, page_number: int = 0) -> str:
    """
    Call DeepSeek vision API to OCR a single page image.

    Args:
        image_path:  Path to the page image (JPEG or PNG).
        page_number: 0-indexed page number (used for logging only).

    Returns:
        Extracted text string from the image.
    """
    client = _get_openai_client()
    img_b64 = _encode_image_to_base64(image_path)

    # Determine MIME type from extension
    suffix = Path(image_path).suffix.lower()
    mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"

    prompt = (
        "You are an expert OCR assistant. "
        "Extract all text from this document page exactly as it appears. "
        "Preserve paragraph structure, numbered lists, and headings. "
        "Output only the extracted text without commentary."
    )

    delay = _INITIAL_DELAY
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime};base64,{img_b64}"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=4096,
            )
            text = response.choices[0].message.content or ""
            logger.debug(
                "DeepSeek OCR page %d: extracted %d chars", page_number, len(text)
            )
            return text
        except Exception as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if attempt < _MAX_RETRIES and (
                status in _RETRY_STATUS_CODES or status is None
            ):
                logger.warning(
                    "DeepSeek OCR attempt %d/%d failed (%s). Retrying in %ds…",
                    attempt + 1,
                    _MAX_RETRIES + 1,
                    exc,
                    delay,
                )
                time.sleep(delay)
                delay *= 2
            else:
                logger.error("DeepSeek OCR failed for page %d: %s", page_number, exc)
                raise


def ocr_pdf_pages(
    pdf_path: str | Path,
    page_indices: list[int],
    dpi: int = 200,
) -> dict[int, str]:
    """
    Convert specified PDF pages to images and OCR them with DeepSeek.

    Args:
        pdf_path:     Path to the source PDF.
        page_indices: 0-indexed list of pages that need OCR.
        dpi:          Rendering DPI for pdf2image (higher = more accurate, slower).

    Returns:
        Mapping of page_index → extracted text string.
    """
    try:
        from pdf2image import convert_from_path
    except ImportError as exc:
        raise ImportError(
            "pdf2image is required. Install with: pip install pdf2image"
        ) from exc

    if not page_indices:
        return {}

    results: dict[int, str] = {}
    pdf_path = Path(pdf_path)

    for page_idx in page_indices:
        # Convert 0-indexed page_idx to 1-indexed for the pdf2image API
        page_num_1indexed = page_idx + 1
        try:
            images = convert_from_path(
                str(pdf_path),
                dpi=dpi,
                first_page=page_num_1indexed,
                last_page=page_num_1indexed,
                poppler_path=settings.POPPLER_PATH,
            )
            if not images:
                logger.warning("No image rendered for page %d", page_idx)
                results[page_idx] = ""
                continue

            # Save to an in-memory buffer as PNG
            img_buf = BytesIO()
            images[0].save(img_buf, format="PNG")
            img_buf.seek(0)

            # Write to a temp file (DeepSeek client reads from disk)
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(img_buf.read())
                tmp_path = Path(tmp.name)

            try:
                text = extract_text_from_image(tmp_path, page_number=page_idx)
            finally:
                tmp_path.unlink(missing_ok=True)

            results[page_idx] = text

        except Exception as exc:
            logger.error("Failed to OCR page %d: %s", page_idx, exc)
            results[page_idx] = ""

    return results
