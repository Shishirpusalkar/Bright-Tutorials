import base64
import json
import logging
import re
import time
import hashlib
from pathlib import Path

import fitz
from pydantic import BaseModel, field_validator, Field, AliasChoices

from app.core.ai_client import ai_post_with_retry
from app.core.config import settings
from app.core.jobs import update_job

logger = logging.getLogger(__name__)

GEMINI_MODEL = settings.GEMINI_MODEL
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
)

# ============================================================
# STRICT ANTI GRAVITY PROMPT
# ============================================================

ANTI_GRAVITY_PROMPT = """
You are a forensic-level PDF exam extractor.

MISSION:
Extract questions exactly as printed.

CRITICAL VISUAL POLICY:
If a question contains a biological diagram, electrical/physics circuit, graph, organic skeletal structure, labeled figure, reaction mechanism, image block, or a complex math expression/function that should be preserved visually:
1. Detect the bounding box coordinates of the source snippet as [x0, y0, x1, y1].
2. Set has_visual = true and provide the figure_bbox.
3. Set visual_tag to the best label among: "circuit", "math", "organic", "biology", "graph", "figure".
4. Insert the literal marker [[VISUAL_SNIPPET]] into question_text exactly where that source snippet belongs.
5. DO NOT describe, recreate, redraw, simplify, or approximate the visual snippet in plain text.

STRICT RULES:
41. Extract ONLY the questions visible on the provided pages (Pages {page_range}).
42. ONLY EXTRACT QUESTIONS WITHIN THE REQUESTED RANGES (start_q to end_q) indicated in the blueprint.
43. DO NOT skip any questions within the requested range.
44. DO NOT extract ANY questions outside the requested range (No subject leakage).
45. Ensure exact chronological generation of question numbers.
46. Extract the solution snippet for each question into "solution_text". If the solution contains complex math/diagrams that must stay visual, insert [[SOLUTION_SNIPPET]] at the same location and provide the bounding box [x0, y0, x1, y1] in "solution_bbox".
47. Preserve original formatting, math, and option order exactly.
48. The blueprint defines the FULL document targets: {blueprint_str}
49. For THIS batch, return only the questions that are actually visible on Pages {page_range}.
50. Do NOT treat it as an error if a subject's full blueprint count is split across later pages.
51. EVERY question object MUST contain: "subject", "section_name", "question_number", and "question_text".
52. EVERY question object MUST contain a "page_number" integer indicating which page the question text primarily resides on.
53. For MCQ/SCQ questions, you MUST include an "options" field as a JSON object mapping option labels to text. Include only the options that actually appear in the question (usually A–D, but some questions may have fewer). e.g. {{"A": "option text", "B": "option text", "C": "option text", "D": "option text"}}. Extract all options exactly as printed.
54. You MUST include a "correct_answer" field: for MCQ/SCQ use the letter (e.g. "A", "B", "C", or "D"); for INTEGER/NUMERIC use the numeric value as a string.
55. You MUST include a "question_type" field: use "SCQ" for single-correct MCQ, "MCQ" for multiple-correct, "INTEGER" for integer-type, "NUMERIC" for numerical-value type. For INTEGER/NUMERIC questions, omit the "options" field or set it to null.
56. LATEX FORMATTING: All mathematical expressions, equations, formulas, and symbols MUST be wrapped in LaTeX delimiters so the frontend can render them correctly with KaTeX:
    - Inline math (in the middle of a sentence): wrap with single dollar signs, e.g. $x^2 + y^2 = r^2$
    - Display/block math (on its own line): wrap with double dollar signs, e.g. $$\\frac{{d}}{{dx}}(x^n) = nx^{{n-1}}$$
    - This applies to question_text, all option values, and solution_text.
    - Examples of what must be LaTeX-wrapped: fractions, exponents, subscripts, integrals, summations, Greek letters (α, β, γ…), chemical formulas with subscripts, trigonometric functions, logarithms, vectors, matrices.
    - Plain text like "x squared" should be written as $x^2$; "CO2" should be written as $\\text{{CO}}_2$; "H2O" as $\\text{{H}}_2\\text{{O}}$.

Each returned object MUST follow this exact JSON structure:
{{
  "question_number": <integer>,
  "subject": "<subject name>",
  "section_name": "<section name>",
  "question_text": "<full question text with math in $...$ or $$...$$>",
  "options": {{"A": "<text with math in $...$>", "B": "<text>", "C": "<text>", "D": "<text>"}} or null for INTEGER/NUMERIC,
  "correct_answer": "<A/B/C/D or numeric value>",
  "question_type": "<SCQ|MCQ|INTEGER|NUMERIC>",
  "solution_text": "<solution text with math in $...$ or $$...$$>",
  "has_visual": <true|false>,
  "visual_tag": "<circuit|math|organic|biology|graph|figure|null>",
  "figure_bbox": [x0, y0, x1, y1] or null,
  "solution_bbox": [x0, y0, x1, y1] or null,
  "page_number": <integer>
}}

If the current batch contains visible numbered questions but you still cannot reconcile them safely, include:
"error": "QUESTION_COUNT_MISMATCH", "expected": X, "found": Y, "subject": "..."

Return JSON array of objects.
"""

SEARCHABLE_TEXT_RESCUE_PROMPT = """
SEARCHABLE TEXT SUPPORT:
- Raw text extracted directly from the same PDF pages may be supplied below.
- Use that searchable text to recover exact numbering, subject transitions, and question wording when the page images are hard to parse.
- The PAGE markers in the raw text are authoritative for page_number.
- If numbered questions are clearly present in the supplied page images or searchable text and they fall within the blueprint ranges, do NOT return an empty array.
"""

DEFAULT_BATCH_SIZE = 2
DEFAULT_BATCH_DELAY_SECONDS = 3


def normalize_question_type(question_type: str | None) -> str | None:
    if question_type is None:
        return None

    normalized = re.sub(r"[_-]+", " ", str(question_type)).strip().upper()
    if not normalized:
        return None

    if normalized in {"SCQ", "SINGLE", "SINGLE CHOICE", "SINGLE CORRECT"}:
        return "SCQ"
    if normalized in {
        "MCQ",
        "MCQS",
        "MSQ",
        "MULTIPLE CHOICE",
        "MULTIPLE CORRECT",
        "MULTIPLE SELECT",
    }:
        return "MCQ"
    if normalized in {"INTEGER", "INT", "NAT"}:
        return "INTEGER"
    if normalized in {"NUMERIC", "NUMERICAL", "NUM"}:
        return "NUMERIC"

    return normalized


def get_batch_settings(total_pages: int) -> tuple[int, int, int]:
    safe_total = max(int(total_pages or 0), 0)
    batch_size = DEFAULT_BATCH_SIZE if safe_total else 1
    batch_count = max(1, (safe_total + batch_size - 1) // batch_size)
    return batch_size, batch_count, DEFAULT_BATCH_DELAY_SECONDS

# ============================================================
# DATA MODEL
# ============================================================


class AIQuestion(BaseModel):
    question_number: int = Field(
        validation_alias=AliasChoices("question_number", "q_no", "no", "number")
    )
    section_name: str = Field(
        validation_alias=AliasChoices("section_name", "section", "sec")
    )
    subject: str = Field(validation_alias=AliasChoices("subject", "sub"))
    question_text: str = Field(
        validation_alias=AliasChoices("question_text", "text", "q_text")
    )
    options: dict | None = None
    solution_text: str | None = None
    correct_answer: str | None = Field(
        None,
        validation_alias=AliasChoices("correct_answer", "answer", "correct_option"),
    )
    question_type: str | None = Field(
        None,
        validation_alias=AliasChoices("question_type", "q_type", "type"),
    )
    pos_mark: float = 4.0
    neg_mark: float = 1.0
    smiles_code: str | None = None
    has_visual: bool = False
    visual_tag: str | None = None
    page_number: int | None = None
    figure_bbox: list[float] | None = None
    solution_bbox: list[float] | None = None

    @field_validator("options", mode="before")
    @classmethod
    def normalize_options(cls, v):
        if isinstance(v, list):
            normalized = {}
            for i, val in enumerate(v):
                letter = chr(65 + i)
                clean_val = re.sub(r"^\(?[A-Z]\)[\s.]*", "", str(val)).strip()
                normalized[letter] = clean_val
            return normalized
        return v

    @property
    def correct_option(self) -> str | None:
        return self.correct_answer

    @property
    def section(self) -> str:
        return self.section_name

    @property
    def marks(self) -> float:
        return self.pos_mark

    @property
    def negative_marks(self) -> float:
        return self.neg_mark


# ============================================================
# SAFE JSON
# ============================================================


def safe_json(text):
    if not text:
        return []

    text = text.strip()

    # Strategy 1: Look for an array
    match = re.search(r"\[\s*\{.*\}\s*\]", text, re.S)
    if match:
        target = match.group(0)
    else:
        # Strategy 2: Look for a single object
        match = re.search(r"\{\s*\".*\}\s*", text, re.S)
        if match:
            target = match.group(0)
        else:
            target = text

    # Clean up common JSON breaking characters
    target = re.sub(r'(?<!\\)\\(?![\\/bfnrtu"\'/])', r"\\\\", target)
    target = re.sub(r",\s*]", "]", target)
    target = re.sub(r",\s*}", "}", target)

    try:
        return json.loads(target)
    except Exception as e:
        logger.error(f"JSON parse failed: {e}")
        # Final attempt: try to close a truncated JSON
        if target.startswith("["):
            try:
                return json.loads(target + "]")
            except Exception:
                pass
        return []


def extract_candidate_text(data):
    candidates = data.get("candidates", [])
    if not candidates:
        return "[]"

    candidate = candidates[0]
    parts = candidate.get("content", {}).get("parts", [])
    text_parts = [
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and part.get("text")
    ]
    combined = "\n".join(text_parts).strip()
    return combined or "[]"


def clean_searchable_text(text: str) -> str:
    if not text:
        return ""

    cleaned = "".join(
        ch if (ch.isprintable() or ch in "\n\t") else " " for ch in str(text)
    )
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def build_searchable_text_for_batch(doc, start_page, end_page):
    page_text_blocks = []
    for page_index in range(start_page, end_page):
        page_text = clean_searchable_text(doc[page_index].get_text("text"))
        if not page_text:
            continue
        page_text_blocks.append(
            (
            f"--- PAGE {page_index + 1} SEARCHABLE TEXT START ---\n"
                f"{page_text[:12000]}\n"
                f"--- PAGE {page_index + 1} SEARCHABLE TEXT END ---"
            )
        )
    return "\n\n".join(page_text_blocks)


def has_numbered_questions(text: str) -> bool:
    if not text:
        return False
    return bool(re.search(r"(\(\d+\)|^\d+[\.\)])", text, re.M))


# ============================================================
# DEDUP HASH
# ============================================================


def generate_hash(question):
    # Safe field access with defaults to avoid KeyErrors
    subj = str(question.get("subject") or "General")
    sect = str(question.get("section_name") or "Main")
    text = str(question.get("question_text") or "")
    base = subj + sect + re.sub(r"\s+", "", text)
    return hashlib.sha256(base.encode()).hexdigest()


# ============================================================
# MAIN ENGINE
# ============================================================


def generate_questions_from_pdf(pdf_path, teacher_blueprint, job_id=None):
    print(f"\n>>> DEBUG: STARTING PDF EXTRACTION for: {pdf_path}")

    all_questions = []
    batch_errors = []
    seen_hashes = set()
    blueprint_str = json.dumps(teacher_blueprint)

    try:
        with fitz.open(pdf_path) as doc:
            total_pages = len(doc)
            print(f">>> DEBUG: Total pages in PDF: {total_pages}")

            batch_size, _, batch_delay_seconds = get_batch_settings(total_pages)
            for i in range(0, total_pages, batch_size):
                batch_end = min(i + batch_size, total_pages)

                if job_id:
                    update_job(
                        job_id,
                        progress=int((i / total_pages) * 100),
                        message=f"Parsing Pages {i + 1} - {batch_end}",
                    )

                parts = [
                    {
                        "text": ANTI_GRAVITY_PROMPT.format(
                            blueprint_str=blueprint_str,
                            page_range=f"{i + 1} to {batch_end}",
                        )
                    }
                ]

                for j in range(i, batch_end):
                    page = doc[j]
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    img_base64 = base64.b64encode(pix.tobytes("jpeg")).decode()
                    parts.append({"text": f"--- PAGE {j + 1} ---"})
                    parts.append(
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": img_base64,
                            }
                        }
                    )

                batch_searchable_text = build_searchable_text_for_batch(doc, i, batch_end)

                payload = {
                    "contents": [{"parts": parts}],
                    "generationConfig": {
                        "temperature": 0.1,
                        "response_mime_type": "application/json",
                        "response_schema": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "question_number": {"type": "INTEGER"},
                                    "subject": {"type": "STRING"},
                                    "section_name": {"type": "STRING"},
                                    "question_text": {"type": "STRING"},
                                    "options": {
                                        "type": "OBJECT",
                                        "properties": {
                                            "A": {"type": "STRING"},
                                            "B": {"type": "STRING"},
                                            "C": {"type": "STRING"},
                                            "D": {"type": "STRING"},
                                        },
                                    },
                                    "correct_answer": {"type": "STRING"},
                                    "question_type": {"type": "STRING"},
                                    "solution_text": {"type": "STRING"},
                                    "has_visual": {"type": "BOOLEAN"},
                                    "visual_tag": {"type": "STRING"},
                                    "figure_bbox": {
                                        "type": "ARRAY",
                                        "items": {"type": "NUMBER"},
                                    },
                                    "solution_bbox": {
                                        "type": "ARRAY",
                                        "items": {"type": "NUMBER"},
                                    },
                                    "page_number": {"type": "INTEGER"},
                                },
                                "required": [
                                    "question_number",
                                    "subject",
                                    "section_name",
                                    "question_text",
                                    "question_type",
                                    "correct_answer",
                                    "page_number",
                                ],
                            },
                        },
                    },
                }

                if batch_searchable_text:
                    parts.append(
                        {
                            "text": (
                                SEARCHABLE_TEXT_RESCUE_PROMPT
                                + "\n\n"
                                + batch_searchable_text
                            )
                        }
                    )

                print(f">>> DEBUG: Sending request for Pages {i + 1}-{batch_end}...")
                try:
                    result = ai_post_with_retry(GEMINI_URL, json=payload, timeout=180)
                    result.raise_for_status()
                    data = result.json()
                    text_out = extract_candidate_text(data)

                    print(
                        f">>> DEBUG: Pages {i + 1}-{batch_end} RAW RESPONSE (first 200 chars): {text_out[:200]}..."
                    )

                    page_questions = safe_json(text_out)
                    print(
                        f">>> DEBUG: Pages {i + 1}-{batch_end} PARSED JSON type: {type(page_questions)}"
                    )

                    if (
                        not page_questions
                        and batch_searchable_text
                        and has_numbered_questions(batch_searchable_text)
                    ):
                        print(
                            f">>> DEBUG: Triggering searchable-text retry for Pages {i + 1}-{batch_end}"
                        )
                        retry_payload = {
                            "contents": [
                                {
                                    "parts": [
                                        {
                                            "text": (
                                                ANTI_GRAVITY_PROMPT.format(
                                                    blueprint_str=blueprint_str,
                                                    page_range=f"{i + 1} to {batch_end}",
                                                )
                                                + "\n\n"
                                                + SEARCHABLE_TEXT_RESCUE_PROMPT
                                                + "\n\n"
                                                + batch_searchable_text
                                            )
                                        }
                                    ]
                                }
                            ],
                            "generationConfig": {
                                "temperature": 0.1,
                                "response_mime_type": "application/json",
                                "response_schema": payload["generationConfig"]["response_schema"],
                            },
                        }
                        retry_result = ai_post_with_retry(
                            GEMINI_URL, json=retry_payload, timeout=180
                        )
                        retry_result.raise_for_status()
                        retry_data = retry_result.json()
                        retry_text_out = extract_candidate_text(retry_data)
                        print(
                            f">>> DEBUG: Pages {i + 1}-{batch_end} RETRY RESPONSE (first 200 chars): {retry_text_out[:200]}..."
                        )
                        retry_questions = safe_json(retry_text_out)
                        if retry_questions:
                            text_out = retry_text_out
                            page_questions = retry_questions

                    # Robust extraction if AI wraps the list in an object (e.g., {"questions": [...]})
                    if isinstance(page_questions, dict):
                        if "questions" in page_questions:
                            page_questions = page_questions["questions"]
                            print(
                                f">>> DEBUG: Unwrapped 'questions' list on Pages {i + 1}-{batch_end}"
                            )
                        elif "data" in page_questions:
                            page_questions = page_questions["data"]
                            print(
                                f">>> DEBUG: Unwrapped 'data' list on Pages {i + 1}-{batch_end}"
                            )
                        else:
                            page_questions = [page_questions]
                            print(
                                f">>> DEBUG: Wrapped single object into list on Pages {i + 1}-{batch_end}"
                            )

                    if not page_questions and text_out.strip() not in ["[]", "{}"]:
                        print(
                            f">>> DEBUG: PARSING FAILURE ON PAGES {i + 1}-{batch_end}! Raw output was: {text_out}"
                        )
                        logger.warning(
                            f"Likely parsing failure on Pages {i + 1}-{batch_end}. Logging raw response."
                        )
                        try:
                            Path("static/uploads").mkdir(parents=True, exist_ok=True)
                            with open(
                                "static/uploads/ai_debug.txt", "a", encoding="utf-8"
                            ) as f:
                                f.write(f"\n--- PAGES {i + 1}-{batch_end} START ---\n")
                                f.write(text_out)
                                f.write(f"\n--- PAGES {i + 1}-{batch_end} END ---\n")
                        except Exception as le:
                            logger.error(f"Failed to write debug log: {le}")

                    print(
                        f">>> DEBUG: Pages {i + 1}-{batch_end} returned {len(page_questions)} question candidates"
                    )

                    for q in page_questions:
                        if (
                            isinstance(q, dict)
                            and q.get("error") == "QUESTION_COUNT_MISMATCH"
                        ):
                            logger.warning(
                                "Ignoring batch-level count mismatch for pages %s-%s: %s expected %s found %s",
                                i + 1,
                                batch_end,
                                q.get("subject"),
                                q.get("expected"),
                                q.get("found"),
                            )
                            print(
                                f">>> DEBUG: Ignoring batch-level count mismatch on Pages {i + 1}-{batch_end} for {q.get('subject')}: expected {q.get('expected')}, found {q.get('found')}"
                            )
                            continue

                        try:
                            # Pre-processing AI response: Inject missing fields / normalize
                            if not isinstance(q, dict):
                                continue

                            # 1. Alias normalization
                            if "section" in q and "section_name" not in q:
                                q["section_name"] = q["section"]
                            if "sub" in q and "subject" not in q:
                                q["subject"] = q["sub"]
                            if "text" in q and "question_text" not in q:
                                q["question_text"] = q["text"]

                            # 2. Smart Field Injection from Blueprint
                            # If blueprint has only one subject/section, auto-fill it
                            unique_subjects = list(
                                set(b.get("subject") for b in teacher_blueprint)
                            )
                            if not q.get("subject") and len(unique_subjects) == 1:
                                q["subject"] = unique_subjects[0]

                            unique_sections = list(
                                set(b.get("section_name") for b in teacher_blueprint)
                            )
                            if not q.get("section_name") and len(unique_sections) == 1:
                                q["section_name"] = unique_sections[0]

                            # Final defaults
                            if not q.get("subject"):
                                q["subject"] = "General"
                            if not q.get("section_name"):
                                q["section_name"] = "Main"

                            # Robustly extract integer page_number
                            raw_page = q.get("page_number")
                            if raw_page is not None:
                                try:
                                    if isinstance(raw_page, str):
                                        digits = re.search(r"\d+", raw_page)
                                        q["page_number"] = (
                                            int(digits.group()) if digits else (i + 1)
                                        )
                                    else:
                                        q["page_number"] = int(raw_page)
                                except Exception:
                                    q["page_number"] = i + 1
                            else:
                                q["page_number"] = i + 1
                            q_hash = generate_hash(q)

                            if q_hash in seen_hashes:
                                print(
                                    f">>> DEBUG: Duplicate detected Q{q.get('question_number')} pages {i + 1}-{batch_end}"
                                )
                                continue

                            seen_hashes.add(q_hash)
                            print(
                                f">>> DEBUG: Validated Q{q.get('question_number')} from Pages {i + 1}-{batch_end}"
                            )
                            all_questions.append(AIQuestion(**q))
                        except Exception as ve:
                            print(
                                f">>> DEBUG: VALIDATION FAILED for Q in Pages {i + 1}-{batch_end}: {ve}"
                            )
                            logger.error(
                                f"VALIDATION FAILED for question: {q} | Reason: {ve}"
                            )
                            continue

                except Exception as e:
                    print(f">>> DEBUG: Error processing Pages {i + 1}-{batch_end}: {e}")
                    logger.error(f"Error parsing pages {i + 1}-{batch_end}: {e}")
                    batch_errors.append(f"Pages {i + 1}-{batch_end}: {e}")
                    if "AI Error" in str(e):
                        raise e
                    continue

                time.sleep(batch_delay_seconds)  # RPM safety

    except Exception as doc_error:
        print(f">>> DEBUG: CRITICAL PDF ERROR: {doc_error}")
        raise doc_error

    if not all_questions and batch_errors:
        raise Exception(f"AI EXTRACTION FAILED: {batch_errors[0]}")

    # ============================================================
    # STRICT COUNT VALIDATION & FILTERING
    # ============================================================

    def normalize_subject(s):
        if not s:
            return ""
        s = str(s).strip().upper()
        if s in ["PHY", "PHYY", "PH"]:
            return "PHYSICS"
        if s in ["CHEM", "CHM", "CH"]:
            return "CHEMISTRY"
        if s in ["MATH", "MATHS", "MAT", "MA"]:
            return "MATHEMATICS"
        if s in ["BIO", "BIOL", "BI"]:
            return "BIOLOGY"
        return s

    filtered_questions = []
    print(
        f">>> DEBUG: Total questions collected BEFORE filtering: {len(all_questions)}"
    )
    for q in all_questions:
        q_subj_norm = normalize_subject(q.subject)
        q_sec_norm = str(q.section_name).strip().upper()

        matched = False
        for section in teacher_blueprint:
            bp_subj_norm = normalize_subject(section["subject"])
            bp_sec_norm = str(section["section_name"]).strip().upper()

            # Loose Match: Same subject, and either section name contains the other
            if q_subj_norm == bp_subj_norm:
                if bp_sec_norm in q_sec_norm or q_sec_norm in bp_sec_norm:
                    # Update config to match blueprint exactly so downstream processing works
                    q.subject = section["subject"]
                    q.section_name = section["section_name"]
                    matched = True
                    break

        if matched:
            filtered_questions.append(q)
        else:
            print(
                f">>> DEBUG: Filtering OUT Q{q.question_number} from Page {q.page_number} - Subject '{q_subj_norm}' or Section '{q_sec_norm}' did not loosely match any blueprint definition."
            )

    all_questions = filtered_questions
    print(f">>> DEBUG: Total questions AFTER filtering: {len(all_questions)}")

    grouped = {}
    for q in all_questions:
        key = (normalize_subject(q.subject), str(q.section_name).strip().upper())
        grouped.setdefault(key, []).append(q)

    for section in teacher_blueprint:
        key = (
            normalize_subject(section["subject"]),
            str(section["section_name"]).strip().upper(),
        )
        expected = section["q_count"]
        actual = len(grouped.get(key, []))

        print(f">>> DEBUG: Section {key} | Expected: {expected} | Actual: {actual}")

        if actual < expected:
            raise Exception(
                f"MISSING QUESTIONS: {key} expected {expected} but got {actual}"
            )
        elif actual > expected:
            grouped[key] = grouped[key][:expected]
            print(f">>> DEBUG: Truncated {key} to {expected}")

    all_questions.sort(key=lambda x: (x.page_number, x.question_number))
    return all_questions
