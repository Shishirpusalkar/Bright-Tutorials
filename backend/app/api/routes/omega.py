import hashlib
import json
import logging
import re
import shutil
import uuid
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import fitz
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from sqlmodel import Session, select

from app.api.deps import CurrentUser
from app.core.ai import (
    AIQuestion,
    generate_questions_from_pdf,
    get_batch_settings,
    normalize_question_type,
)
from app.core.db import engine
from app.core.email_service import send_test_scheduled_alert
from app.core.jobs import (
    create_job,
    get_job,
    get_job_question_cache,
    set_job_question_cache,
    update_job,
)
from app.models import (
    Question,
    Test,
    TestGenerationConfig,
    User,
)

logger = logging.getLogger(__name__)

router = APIRouter()


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "find",
    "for",
    "from",
    "if",
    "in",
    "into",
    "is",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "what",
    "which",
    "with",
}


@dataclass
class CachedGeneratedQuestion:
    question_text: str
    options: dict | None
    correct_option: str | None
    solution_text: str | None
    solution_bbox: dict | None
    subject: str
    section: str
    question_type: str
    question_number: int | None
    marks: float
    negative_marks: float
    content_hash: str
    duplicate_guard_hash: str
    confidence_score: float
    word_similarity_anchor: str
    intent_signature: str
    organic_metadata: dict | None
    has_visual: bool
    visual_tag: str | None
    page_number: int | None
    visual_bbox: dict | None
    image_url: str | None
    standard: str | None
    category: str | None

    def to_public_dict(self) -> dict:
        return {
            "question_text": self.question_text,
            "options": self.options,
            "correct_option": self.correct_option,
            "solution_text": self.solution_text,
            "solution_bbox": self.solution_bbox,
            "subject": self.subject,
            "section": self.section,
            "question_type": self.question_type,
            "question_number": self.question_number,
            "marks": self.marks,
            "negative_marks": self.negative_marks,
            "content_hash": self.content_hash,
            "duplicate_guard_hash": self.duplicate_guard_hash,
            "confidence_score": self.confidence_score,
            "word_similarity_anchor": self.word_similarity_anchor,
            "intent_signature": self.intent_signature,
            "organic_metadata": self.organic_metadata,
            "has_visual": self.has_visual,
            "visual_tag": self.visual_tag,
            "page_number": self.page_number,
            "visual_bbox": self.visual_bbox,
            "image_url": self.image_url,
            "standard": self.standard,
            "category": self.category,
        }


class QuestionSimilarityComparator:
    @staticmethod
    def tokenize(text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", (text or "").lower())

    @classmethod
    def normalized_anchor(cls, question_text: str, options: dict | None) -> str:
        option_text = " ".join(str(v) for v in (options or {}).values() if v)
        tokens = cls.tokenize(f"{question_text} {option_text}")
        return " ".join(tokens)

    @classmethod
    def intent_signature(cls, question_text: str, subject: str, question_type: str) -> str:
        tokens = [
            token
            for token in cls.tokenize(question_text)
            if token not in STOPWORDS and not token.isdigit()
        ]
        core = " ".join(tokens[:8])
        return f"{(subject or '').lower()}|{(question_type or '').lower()}|{core}"

    @classmethod
    def confidence_score(
        cls,
        question_text: str,
        options: dict | None,
        subject: str,
        section: str,
        question_number: int | None,
        has_visual: bool,
        visual_bbox: dict | None,
    ) -> float:
        score = 0.35
        if len((question_text or "").strip()) >= 40:
            score += 0.2
        if subject and section:
            score += 0.1
        if question_number is not None:
            score += 0.1
        if options and len(options) >= 2:
            score += 0.1
        if has_visual:
            score += 0.05
        if visual_bbox:
            score += 0.1
        return min(1.0, round(score, 3))

    @classmethod
    def word_similarity(cls, left: str, right: str) -> float:
        left_tokens = set(cls.tokenize(left))
        right_tokens = set(cls.tokenize(right))
        if not left_tokens or not right_tokens:
            return 0.0
        overlap = len(left_tokens & right_tokens)
        union = len(left_tokens | right_tokens)
        return overlap / union if union else 0.0

    @classmethod
    def are_same_question(
        cls, left: CachedGeneratedQuestion, right: CachedGeneratedQuestion
    ) -> bool:
        if left.content_hash and left.content_hash == right.content_hash:
            return True
        if (
            left.duplicate_guard_hash
            and left.duplicate_guard_hash == right.duplicate_guard_hash
        ):
            return True
        similarity = cls.word_similarity(
            left.word_similarity_anchor, right.word_similarity_anchor
        )
        confidence_close = abs(left.confidence_score - right.confidence_score) <= 0.08
        same_intent = left.intent_signature == right.intent_signature
        return same_intent and confidence_close and similarity >= 0.9


@router.get("/progress/{job_id}")
def get_parsing_progress(job_id: str):
    """
    Get the real-time progress of a PDF parsing job.
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/cache/{job_id}")
def get_cached_generated_questions(job_id: str, current_user: CurrentUser):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required")

    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job_id,
        "cache_count": len(get_job_question_cache(job_id)),
        "questions": get_job_question_cache(job_id),
    }


def get_file_hash(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def get_content_hash(text: str, options: dict | None = None) -> str:
    """
    Generate a stable "Signature Hash" for a question.
    Considers normalized text and normalized/sorted options.
    """
    if not text:
        return ""

    # 1. Normalize Question Text
    # Lowercase, remove non-alphanumeric, collapse whitespace
    clean_text = "".join(filter(str.isalnum, text.lower()))

    # 2. Normalize Options
    # Sort by key (A, B, C, D) to ensure order-independence if Gemini shifts them
    # but more importantly, sort the normalized VALUES to catch shuffled options.
    opt_str = ""
    if options and isinstance(options, dict):
        # Extract values, normalize them, and sort alphabetially
        clean_opts = []
        for v in options.values():
            if v:
                clean_opts.append("".join(filter(str.isalnum, str(v).lower())))
        clean_opts.sort()
        opt_str = "|".join(clean_opts)

    # 3. Combine and Hash
    combined = f"{clean_text}#{opt_str}"
    return hashlib.sha256(combined.encode()).hexdigest()


def get_duplicate_guard_hash(text: str, options: dict | None = None) -> str:
    """
    Looser in-paper dedup signature to catch near-identical repeats.
    Ignores punctuation/case and option labels, and collapses the prompt body
    so small OCR/formatting differences do not create duplicate questions.
    """
    if not text:
        return ""

    clean_text = re.sub(r"\s+", " ", str(text).strip().lower())
    clean_text = re.sub(r"^[\(\[]?\d+[\)\.\]]\s*", "", clean_text)
    clean_text = re.sub(r"[^a-z0-9]+", "", clean_text)

    option_tokens = []
    if options and isinstance(options, dict):
        for value in options.values():
            if not value:
                continue
            clean_value = re.sub(r"\s+", " ", str(value).strip().lower())
            clean_value = re.sub(r"^[\(\[]?[a-z][\)\.\]]\s*", "", clean_value)
            clean_value = re.sub(r"[^a-z0-9]+", "", clean_value)
            if clean_value:
                option_tokens.append(clean_value)

    option_tokens.sort()
    combined = f"{clean_text}#{'|'.join(option_tokens)}"
    return hashlib.sha256(combined.encode()).hexdigest()


def extract_potential_questions(file_path: str) -> list[str]:
    """Extract raw text blocks that look like questions from a searchable PDF."""
    questions = []
    try:
        with fitz.open(file_path) as doc:
            full_text = ""
            for page in doc:
                full_text += page.get_text()

            # Simple regex-based splitting by "Q1.", "1.", etc.
            # This is a fallback to avoid Gemini if we have exact text matches.
            blocks = re.split(r"\n(?=\d+[\.\)])", full_text)
            for block in blocks:
                clean = block.strip()
                if clean and len(clean) > 20:  # Minimum length for a question
                    questions.append(clean)
    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
    return questions


def detect_visual_bbox(pdf_path: str, page_number: int) -> dict | None:
    """Detect the largest drawing or image on a specific page and return its bbox."""
    try:
        with fitz.open(pdf_path) as doc:
            if page_number < 1 or page_number > len(doc):
                return None
            page = doc[page_number - 1]

            # Find largest image or drawing
            largest_area = 0
            best_bbox = None

            # Check Images
            for img in page.get_images(full=True):
                # get_image_info is better for bboxes
                pass  # get_images doesn't give bbox directly easily here

            # Alternative: use get_image_info() or search for image blocks
            for block in page.get_text("dict")["blocks"]:
                if block["type"] == 1:  # Image
                    bbox = block["bbox"]  # (x0, y0, x1, y1)
                    area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                    if area > largest_area:
                        largest_area = area
                        best_bbox = bbox

            # Check Drawings (Vector graphics)
            for d in page.get_drawings():
                bbox = d["rect"]  # Rect object
                area = bbox.width * bbox.height
                if area > largest_area:
                    largest_area = area
                    best_bbox = (bbox.x0, bbox.y0, bbox.x1, bbox.y1)

            if best_bbox:
                return {
                    "x0": best_bbox[0],
                    "y0": best_bbox[1],
                    "x1": best_bbox[2],
                    "y1": best_bbox[3],
                }
    except Exception as e:
        logger.error(f"Visual detection failed on page {page_number}: {e}")
    return None


def normalize_bbox_payload(bbox: dict | list | tuple | None) -> dict | None:
    """Normalize AI/pdf bbox payloads to {x0, y0, x1, y1}."""
    if not bbox:
        return None

    if isinstance(bbox, dict):
        if all(key in bbox for key in ("x0", "y0", "x1", "y1")):
            try:
                return {
                    "x0": float(bbox["x0"]),
                    "y0": float(bbox["y0"]),
                    "x1": float(bbox["x1"]),
                    "y1": float(bbox["y1"]),
                }
            except (TypeError, ValueError):
                return None
        inner_bbox = bbox.get("bbox")
        if inner_bbox is not None:
            return normalize_bbox_payload(inner_bbox)

    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        try:
            return {
                "x0": float(bbox[0]),
                "y0": float(bbox[1]),
                "x1": float(bbox[2]),
                "y1": float(bbox[3]),
            }
        except (TypeError, ValueError):
            return None

    return None


def expand_bbox_for_display(
    pdf_path: str,
    page_number: int | None,
    bbox: dict | list | tuple | None,
    padding_ratio: float = 0.14,
    min_padding: float = 18.0,
) -> dict | None:
    normalized = normalize_bbox_payload(bbox)
    if not normalized or page_number is None:
        return normalized

    try:
        with fitz.open(pdf_path) as doc:
            if page_number < 1 or page_number > len(doc):
                return normalized
            page_rect = doc[page_number - 1].rect
    except Exception:
        return normalized

    width = max(1.0, normalized["x1"] - normalized["x0"])
    height = max(1.0, normalized["y1"] - normalized["y0"])
    pad_x = max(min_padding, width * padding_ratio)
    pad_y = max(min_padding, height * padding_ratio)

    return {
        "x0": max(page_rect.x0, normalized["x0"] - pad_x),
        "y0": max(page_rect.y0, normalized["y0"] - pad_y),
        "x1": min(page_rect.x1, normalized["x1"] + pad_x),
        "y1": min(page_rect.y1, normalized["y1"] + pad_y),
    }


def extract_question_image(
    pdf_path: str, page_number: int | None, bbox: dict | None, job_id: str
) -> str | None:
    bbox = expand_bbox_for_display(pdf_path, page_number, bbox)
    if not bbox or page_number is None:
        return None

    try:
        with fitz.open(pdf_path) as doc:
            if page_number < 1 or page_number > len(doc):
                return None
            page = doc[page_number - 1]
            clip = fitz.Rect(
                bbox["x0"],
                bbox["y0"],
                bbox["x1"],
                bbox["y1"],
            )
            if clip.is_empty or clip.width <= 0 or clip.height <= 0:
                return None

            snippets_dir = Path("static/uploads/question_snippets") / job_id
            snippets_dir.mkdir(parents=True, exist_ok=True)
            file_name = f"{uuid.uuid4()}.png"
            file_path = snippets_dir / file_name

            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip, alpha=False)
            pix.save(file_path)
            return f"/static/uploads/question_snippets/{job_id}/{file_name}"
    except Exception as e:
        logger.error(f"Failed to extract question image snippet: {e}")
        return None


@router.get("/health")
def health_check():
    """
    Simple health check for keep-alive.
    """
    return {"status": "ok", "timestamp": datetime.now(timezone.utc)}


@router.post("/upload")
def omega_upload(
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    config: str = Form(...),  # JSON string
):
    """
    Omega Go Workflow (Refactored for Progress Bar):
    1. Upload PDF & Config
    2. Create Job ID
    3. Start Background AI Parsing
    4. Return Job ID immediately
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    try:
        config_data = json.loads(config)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON config")

    # 1. Save PDF Temporarily
    temp_path = f"static/uploads/temp/{uuid.uuid4()}.pdf"
    Path("static/uploads/temp").mkdir(parents=True, exist_ok=True)

    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 2. Create Job
    job_id = create_job()

    # 3. Start Background Processing
    print(f">>> DEBUG: OMEGA UPLOAD - Initiating background task for Job: {job_id}")
    background_tasks.add_task(
        process_pdf_background, job_id, temp_path, config_data, current_user.id
    )

    return {
        "status": "processing",
        "job_id": job_id,
        "message": "Upload successful, processing started.",
    }


def process_pdf_background(
    job_id: str, temp_path: str, config_data: dict, user_id: UUID
):
    """
    Background worker for PDF processing.
    """
    print(f"\n>>> DEBUG: BACKGROUND TASK STARTED for Job: {job_id}")
    print(f">>> DEBUG: PDF Path: {temp_path}")
    final_path = None

    def normalize_subject_key(value: str | None) -> str:
        return (value or "General").strip().title()

    def normalize_section_key(value: str | None) -> str:
        return (value or "Section A").strip().lower()

    def build_question_cache(
        teacher_blueprint: list[dict],
        questions: list[AIQuestion],
    ) -> list[CachedGeneratedQuestion]:
        blueprint_limits = {}
        blueprint_metadata = {}
        for item in teacher_blueprint:
            key = (
                normalize_subject_key(item.get("subject")),
                normalize_section_key(item.get("section_name")),
            )
            blueprint_limits[key] = int(item.get("q_count", 0))
            blueprint_metadata[key] = item

        stage_counts = {}
        cached_questions: list[CachedGeneratedQuestion] = []

        for q in questions:
            subj = normalize_subject_key(q.subject)
            sect = q.section_name or "Section A"
            sect_key = normalize_section_key(sect)
            key = (subj, sect_key)
            limit = blueprint_limits.get(key)
            if limit is None:
                logger.info("Skipping staging row outside blueprint: %s / %s", subj, sect)
                continue
            blueprint_item = blueprint_metadata.get(key, {})

            content_hash = get_content_hash(q.question_text, q.options)
            duplicate_guard_hash = get_duplicate_guard_hash(q.question_text, q.options)
            if stage_counts.get(key, 0) >= limit:
                continue

            visual_bbox = normalize_bbox_payload(q.figure_bbox)
            if q.has_visual and not visual_bbox and q.page_number is not None:
                visual_bbox = detect_visual_bbox(temp_path, q.page_number)
            visual_bbox = expand_bbox_for_display(
                temp_path,
                q.page_number,
                visual_bbox,
            )

            image_url = None
            if q.has_visual:
                image_url = extract_question_image(
                    temp_path, q.page_number, visual_bbox, job_id
                )

            resolved_type = (
                normalize_question_type(blueprint_item.get("question_type"))
                or normalize_question_type(getattr(q, "question_type", None))
                or ("SCQ" if q.options else "NUMERIC")
            )

            cache_entry = CachedGeneratedQuestion(
                question_text=q.question_text,
                options=q.options,
                correct_option=q.correct_answer,
                solution_text=q.solution_text,
                solution_bbox=normalize_bbox_payload(q.solution_bbox),
                subject=subj,
                section=sect,
                question_type=resolved_type,
                question_number=q.question_number,
                marks=q.pos_mark,
                negative_marks=q.neg_mark,
                content_hash=content_hash or "",
                duplicate_guard_hash=duplicate_guard_hash or "",
                confidence_score=QuestionSimilarityComparator.confidence_score(
                    question_text=q.question_text,
                    options=q.options,
                    subject=subj,
                    section=sect,
                    question_number=q.question_number,
                    has_visual=q.has_visual,
                    visual_bbox=visual_bbox,
                ),
                word_similarity_anchor=QuestionSimilarityComparator.normalized_anchor(
                    q.question_text, q.options
                ),
                intent_signature=QuestionSimilarityComparator.intent_signature(
                    q.question_text,
                    subj,
                    resolved_type,
                ),
                organic_metadata={"smiles": q.smiles_code} if q.smiles_code else None,
                has_visual=q.has_visual,
                visual_tag=q.visual_tag,
                page_number=q.page_number,
                visual_bbox=visual_bbox,
                image_url=image_url,
                standard=config_data.get("standard"),
                category=config_data.get("category"),
            )

            if any(
                QuestionSimilarityComparator.are_same_question(cache_entry, existing)
                for existing in cached_questions
            ):
                logger.info(
                    "Skipping cache duplicate for %s / %s Q%s",
                    subj,
                    sect,
                    q.question_number,
                )
                continue

            cached_questions.append(cache_entry)
            stage_counts[key] = stage_counts.get(key, 0) + 1
        set_job_question_cache(
            job_id,
            [cached_question.to_public_dict() for cached_question in cached_questions],
        )

        print(
            f">>> DEBUG: Cached {len(cached_questions)} unique questions in memory for Job {job_id} before final save."
        )
        return cached_questions

    try:
        with Session(engine) as session:
            # 1. Fresh-run mode: do not reuse cached parses or previous DB-generated papers.
            print(f">>> DEBUG: [STEP 1] Generating file hash for Job: {job_id}")
            pdf_hash = get_file_hash(temp_path)
            print(
                f">>> DEBUG: [STEP 2] Hash generated: {pdf_hash}. Fresh conversion mode enabled."
            )

            raw_questions = []
            found_global_questions = []
            existing_subject_counts = {}
            test = None

            update_job(
                job_id,
                progress=10,
                message="Starting fresh AI conversion...",
            )

            # Construct Teacher Blueprint and filter out completed subjects
            teacher_blueprint = []
            subjects_to_parse = []
            for subj_name, subj_conf in config_data.get("subjects", {}).items():
                print(
                    f">>> DEBUG: Subject {subj_name} | Target generated dynamically via start_q and end_q range. Found globally: {existing_subject_counts.get(subj_name, 0)}. FORCING GENERATION."
                )

                subjects_to_parse.append(subj_name)
                # Normalize subject name for comparison and storage
                norm_subj = subj_name.strip().title()
                for sect_name, sect_conf in subj_conf.get("sections", {}).items():
                    start_q = max(1, int(sect_conf.get("start_q", 1)))
                    end_q = max(start_q, int(sect_conf.get("end_q", 20)))
                    q_count = end_q - start_q + 1

                    if q_count <= 0:
                        continue

                    # If we partially found some questions globally, adjust the count
                    # but for Gemini to understand context, we usually send the full list
                    # of what's REMAINING. However, generate_questions_from_pdf treats
                    # q_count as the total it should return for that section.
                    # Simplest fix: Just parse the missing subjects entirely.
                    teacher_blueprint.append(
                        {
                            "section_name": sect_name,
                            "subject": norm_subj,
                            "start_q": start_q,
                            "end_q": end_q,
                            "q_count": q_count,
                            "question_type": normalize_question_type(
                                sect_conf.get("type")
                            ),
                            "pos_mark": float(sect_conf.get("marks", 4.0)),
                            "neg_mark": float(sect_conf.get("negative_marks", -1.0)),
                        }
                    )

            def trim_questions_to_blueprint(
                questions: list[AIQuestion],
            ) -> list[AIQuestion]:
                blueprint_by_subject = {}
                for item in teacher_blueprint:
                    subj_key = normalize_subject_key(item.get("subject"))
                    blueprint_by_subject.setdefault(subj_key, []).append(item)

                for items in blueprint_by_subject.values():
                    items.sort(
                        key=lambda item: (
                            int(item.get("start_q", 0)),
                            int(item.get("end_q", 0)),
                        )
                    )

                section_counts = {}
                seen_content_hashes = set()
                seen_duplicate_hashes = set()
                trimmed = []

                sorted_questions = sorted(
                    questions,
                    key=lambda q: (
                        getattr(q, "page_number", 0) or 0,
                        getattr(q, "question_number", 0) or 0,
                    ),
                )

                for q in sorted_questions:
                    subj_key = normalize_subject_key(q.subject)
                    q_no = int(getattr(q, "question_number", 0) or 0)
                    section_items = blueprint_by_subject.get(subj_key, [])
                    matched_item = None

                    # Strongest match: question number inside configured range
                    for item in section_items:
                        if int(item.get("start_q", 0)) <= q_no <= int(
                            item.get("end_q", 0)
                        ):
                            matched_item = item
                            break

                    # Fallback: exact section-name match if question number is unreliable
                    if not matched_item:
                        for item in section_items:
                            if normalize_section_key(q.section_name) == normalize_section_key(
                                item.get("section_name")
                            ):
                                matched_item = item
                                break

                    if not matched_item:
                        logger.info(
                            "Dropping question outside configured ranges: %s Q%s",
                            subj_key,
                            q_no,
                        )
                        continue

                    content_hash = get_content_hash(q.question_text, q.options)
                    duplicate_guard_hash = get_duplicate_guard_hash(
                        q.question_text, q.options
                    )
                    if content_hash and content_hash in seen_content_hashes:
                        continue
                    if (
                        duplicate_guard_hash
                        and duplicate_guard_hash in seen_duplicate_hashes
                    ):
                        continue

                    key = (
                        normalize_subject_key(matched_item.get("subject")),
                        normalize_section_key(matched_item.get("section_name")),
                    )
                    limit = int(matched_item.get("q_count", 0))
                    current = section_counts.get(key, 0)
                    if current >= limit:
                        logger.info(
                            "Trimming excess question for %s / %s at Q%s (%s/%s)",
                            key[0],
                            matched_item.get("section_name"),
                            q_no,
                            current,
                            limit,
                        )
                        continue

                    q.subject = str(matched_item.get("subject"))
                    q.section_name = str(matched_item.get("section_name"))
                    q.question_type = normalize_question_type(
                        matched_item.get("question_type")
                    ) or normalize_question_type(getattr(q, "question_type", None))
                    q.pos_mark = float(matched_item.get("pos_mark", q.pos_mark))
                    q.neg_mark = float(matched_item.get("neg_mark", q.neg_mark))

                    trimmed.append(q)
                    section_counts[key] = current + 1
                    if content_hash:
                        seen_content_hashes.add(content_hash)
                    if duplicate_guard_hash:
                        seen_duplicate_hashes.add(duplicate_guard_hash)

                print(
                    f">>> DEBUG: Trimmed raw question pool from {len(questions)} to {len(trimmed)} using blueprint ranges."
                )
                return trimmed

            # 1.6 Generate missing content
            api_calls = 0
            if teacher_blueprint:
                update_job(
                    job_id,
                    progress=15,
                    message=f"Parsing remaining subjects: {', '.join(subjects_to_parse)}...",
                )
                try:
                    print(
                        f">>> DEBUG: [STEP 6] Calling AI to parse PDF for missing subjects: {subjects_to_parse}"
                    )
                    newLY_generated = generate_questions_from_pdf(
                        temp_path, teacher_blueprint, job_id=job_id
                    )
                    print(
                        f">>> DEBUG: [STEP 7] AI Returned {len(newLY_generated)} questions."
                    )
                    raw_questions.extend(newLY_generated)
                except Exception as e:
                    raise e

                # Correct API call count (number of batches processed)
                try:
                    with fitz.open(temp_path) as doc:
                        batch_size, _, _ = get_batch_settings(len(doc))
                        api_calls = (len(doc) + batch_size - 1) // batch_size
                except Exception:
                    api_calls = 1

                raw_questions = trim_questions_to_blueprint(raw_questions)

            else:
                if not raw_questions:
                    update_job(
                        job_id,
                        progress=100,
                        status="completed",
                        message="Test already fully generated!",
                    )
                    return

            # 2. Create or Reuse Test Record
            update_job(job_id, progress=91, message="Saving test record...")

            scheduled_at = None
            if config_data.get("scheduledAt"):
                try:
                    scheduled_at = datetime.fromisoformat(config_data["scheduledAt"])
                except ValueError:
                    pass

            # Save PDF permanently
            perm_id = uuid.uuid4()
            perm_name = f"{perm_id}.pdf"
            perm_dir = Path("static/uploads/tests")
            perm_dir.mkdir(parents=True, exist_ok=True)
            final_path = str(perm_dir / perm_name)
            shutil.copy2(temp_path, final_path)
            question_paper_url = f"/static/uploads/tests/{perm_name}"

            test = Test(
                title=config_data.get("title", "Omega Test"),
                description="Generated via Omega Go",
                duration_minutes=int(config_data.get("duration", 180)),
                created_by=user_id,
                total_marks=0,
                is_published=True,
                standard=config_data.get("standard"),
                category=config_data.get("category"),
                scheduled_at=scheduled_at,
                question_paper_url=question_paper_url,
            )
            session.add(test)
            session.commit()
            session.refresh(test)

            # Email Alert: Test Scheduled via Omega Go
            teacher = session.get(User, user_id)
            teacher_email = str(teacher.email) if teacher else ""
            subjects_list = list(config_data.get("subjects", {}).keys())
            send_test_scheduled_alert(
                teacher_email=teacher_email,
                test_title=config_data.get("title", "Omega Test"),
                scheduled_at=str(scheduled_at) if scheduled_at else None,
                subjects=subjects_list,
                total_questions=0,
                marking_scheme="Per Blueprint",
            )

            # 3. Filter & Save Questions
            total_marks = 0
            subject_stats = {}
            blueprint_section_targets = {}
            blueprint_subject_targets = {}

            for item in teacher_blueprint:
                subj_key = normalize_subject_key(item.get("subject"))
                sect_key = normalize_section_key(item.get("section_name"))
                q_count = int(item.get("q_count", 0))
                blueprint_section_targets[(subj_key, sect_key)] = q_count
                blueprint_subject_targets[subj_key] = (
                    blueprint_subject_targets.get(subj_key, 0) + q_count
                )

            def get_section_count(subj_key: str, sect_key: str) -> int:
                return (
                    subject_stats.get(subj_key, {})
                    .get("sections", {})
                    .get(sect_key, {})
                    .get("count", 0)
                )

            def can_add_question(subj_key: str, sect_key: str) -> tuple[bool, str | None]:
                target = blueprint_section_targets.get((subj_key, sect_key))
                if target is None:
                    return (
                        False,
                        f"Question outside blueprint skipped: {subj_key} / {sect_key}",
                    )

                current = get_section_count(subj_key, sect_key)
                if current >= target:
                    return (
                        False,
                        f"Section quota reached for {subj_key} / {sect_key} ({current}/{target})",
                    )

                return True, None

            def record_stats(subj_key: str, sect_key: str, marks: float) -> None:
                if subj_key not in subject_stats:
                    subject_stats[subj_key] = {"count": 0, "marks": 0, "sections": {}}
                subject_stats[subj_key]["count"] += 1
                subject_stats[subj_key]["marks"] += marks
                if sect_key not in subject_stats[subj_key]["sections"]:
                    subject_stats[subj_key]["sections"][sect_key] = {
                        "count": 0,
                        "marks": 0,
                    }
                subject_stats[subj_key]["sections"][sect_key]["count"] += 1
                subject_stats[subj_key]["sections"][sect_key]["marks"] += marks

            cached_questions = build_question_cache(
                teacher_blueprint=teacher_blueprint,
                questions=raw_questions,
            )
            if not cached_questions:
                raise Exception("AI EXTRACTION FAILED: no valid unique questions cached")

            for cached_question in cached_questions:
                db_question = Question(
                    test_id=test.id,
                    question_text=cached_question.question_text,
                    image_url=cached_question.image_url,
                    options=cached_question.options,
                    correct_option=cached_question.correct_option,
                    solution_text=cached_question.solution_text,
                    solution_bbox=cached_question.solution_bbox,
                    subject=cached_question.subject,
                    section=cached_question.section,
                    question_type=cached_question.question_type,
                    marks=cached_question.marks,
                    negative_marks=cached_question.negative_marks,
                    question_number=cached_question.question_number,
                    organic_metadata=cached_question.organic_metadata,
                    has_visual=cached_question.has_visual,
                    visual_tag=cached_question.visual_tag,
                    content_hash=cached_question.content_hash,
                    standard=cached_question.standard,
                    category=cached_question.category,
                    page_number=cached_question.page_number,
                    visual_bbox=cached_question.visual_bbox,
                )
                print(
                    f">>> DEBUG: PROMOTING CACHED QUESTION to Final DB for Test: {test.id} | Hash: {(cached_question.content_hash or '')[:8]}"
                )
                session.add(db_question)
                total_marks += cached_question.marks
                record_stats(
                    normalize_subject_key(cached_question.subject),
                    normalize_section_key(cached_question.section),
                    cached_question.marks,
                )

            test.total_marks = int(total_marks)
            session.add(test)

            # API calls tracked during generation

            # Subject Counts for Validation
            subject_counts = {
                subj: stats["count"] for subj, stats in subject_stats.items()
            }

            # Strict Blueprint & Symmetry Validation
            errors = []
            is_symmetrical = True

            # 1. Section Count Accuracy
            for (subj, sect_key), expected in blueprint_section_targets.items():
                actual = get_section_count(subj, sect_key)
                sect_label = next(
                    (
                        b.get("section_name")
                        for b in teacher_blueprint
                        if normalize_subject_key(b.get("subject")) == subj
                        and normalize_section_key(b.get("section_name")) == sect_key
                    ),
                    sect_key,
                )

                if actual < expected:
                    is_symmetrical = False
                    errors.append(
                        f"{subj} / {sect_label}: Under-extracted ({actual}/{expected})"
                    )
                elif actual > expected:
                    is_symmetrical = False
                    errors.append(
                        f"{subj} / {sect_label}: Over-extracted ({actual}/{expected})"
                    )

            # 2. Subject Totals Accuracy
            for subj, expected in blueprint_subject_targets.items():
                actual = subject_counts.get(subj, 0)

                if actual < expected:
                    is_symmetrical = False
                    errors.append(f"{subj}: Under-extracted ({actual}/{expected})")
                elif actual > expected:
                    is_symmetrical = False
                    errors.append(f"{subj}: Over-extracted ({actual}/{expected})")

            # 3. Section Symmetry (P/C/B match each other if present)
            p_count = subject_counts.get("Physics", 0)
            c_count = subject_counts.get("Chemistry", 0)
            b_count = subject_counts.get("Biology", 0)

            expected_subjects = {b.get("subject") for b in teacher_blueprint}

            if "Physics" in expected_subjects and "Chemistry" in expected_subjects:
                if p_count != c_count:
                    is_symmetrical = False
                    if not any("Physics" in e or "Chemistry" in e for e in errors):
                        errors.append(
                            f"Imbalance: Physics({p_count}) != Chemistry({c_count})"
                        )

            if "Biology" in expected_subjects and (
                "Physics" in expected_subjects or "Chemistry" in expected_subjects
            ):
                ref_count = p_count if "Physics" in expected_subjects else c_count
                if b_count != ref_count:
                    is_symmetrical = False
                    if not any("Biology" in e for e in errors):
                        errors.append(f"Imbalance: Biology({b_count}) != {ref_count}")

            symmetry_message = "Success" if is_symmetrical else " | ".join(errors)

            # SAVE SYMMETRY TO TEST RECORD
            test.is_symmetrical = is_symmetrical
            test.symmetry_message = symmetry_message

            if not is_symmetrical:
                logger.warning(
                    f"Blueprint Validation failed for test {test.id}: {symmetry_message}"
                )

            print(f">>> DEBUG: SESSION COMMIT (Questions) for Job: {job_id}")
            session.commit()

            parsing_report = {
                "total_extracted": len(raw_questions),
                "total_saved": len(cached_questions),
                "cached_questions": len(cached_questions),
                "subject_counts": subject_counts,
                "is_symmetrical": is_symmetrical,
                "symmetry_message": symmetry_message,
                "api_calls": api_calls,
                "recovery_mode": False,
                "balance_checkpoint": {
                    "status": "Balanced" if is_symmetrical else "Invalid",
                    "details": symmetry_message,
                    "counts": subject_counts,
                },
            }

            omega_conf = TestGenerationConfig(
                test_id=test.id,
                config_data=config_data,
                parsing_report=parsing_report,
                pdf_hash=pdf_hash,
            )
            session.add(omega_conf)

            print(f">>> DEBUG: SESSION COMMIT (Config/Report) for Job: {job_id}")
            session.commit()

            # Add results to job so frontend can redirect
            job = get_job(job_id)
            if job:
                job["result"] = {
                    "test_id": str(test.id),
                    "report": parsing_report,
                    "cache_questions": get_job_question_cache(job_id),
                }
            else:
                logger.warning(
                    f"Job {job_id} not found in memory during result assignment."
                )

            # 4. Final Update (Set status LAST to avoid race condition)
            update_job(
                job_id,
                progress=100,
                status="completed",
                message="Test successfully generated!",
            )
            print(
                f">>>> DEBUG: [STEP 100] Background PDF processing COMPLETED for Job {job_id}"
            )
            print(
                f">>>> DEBUG: [STEP 100] Background PDF processing COMPLETED for Job {job_id}"
            )

    except Exception as e:
        error_trace = traceback.format_exc()
        print(f">>> DEBUG: Background PDF processing FAILED for Job {job_id}: {e}")
        print(error_trace)
        logger.error(f"Background PDF processing failed: {e}")
        logger.error(error_trace)
        update_job(job_id, status="failed", message=str(e))
    finally:
        # Only cleanup if we didn't move it permanently or for the temp file
        if "temp_path" in locals() and temp_path and Path(temp_path).exists():
            Path(temp_path).unlink(missing_ok=True)
