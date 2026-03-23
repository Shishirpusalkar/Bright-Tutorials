from uuid import UUID
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Attempt,
    AttemptAnswer,
    AttemptStatus,
    Test,
)
from typing import Any, cast
import cv2
import numpy as np
import base64
import requests
import json
from app.core.config import settings
from sqlmodel import col

router = APIRouter()


def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def four_point_transform(image, pts):
    rect = order_points(pts)
    (tl, tr, br, bl) = rect
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))
    dst = np.array(
        [[0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]],
        dtype="float32",
    )
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    return warped


def sort_contours(cnts: Any, method: str = "left-to-right"):
    reverse = False
    i = 0
    if method == "right-to-left" or method == "bottom-to-top":
        reverse = True
    if method == "top-to-bottom" or method == "bottom-to-top":
        i = 1

    boundingBoxes = [cv2.boundingRect(c) for c in cnts]
    # Use explicit list for sorting to satisfy type checkers
    zipped = list(zip(cnts, boundingBoxes, strict=False))
    zipped.sort(key=lambda b: b[1][i], reverse=reverse)

    cnts_sorted, boxes_sorted = zip(*zipped, strict=False)
    return (list(cnts_sorted), list(boxes_sorted))


def gemini_omr_fallback(image_bytes: bytes, num_questions: int) -> list[dict]:
    """
    Uses Gemini Vision to parse the OMR sheet as a fallback.
    """
    if not settings.GEMINI_API_KEY:
        return []

    try:
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        prompt = f"""
        This is a scanned OMR sheet for a test with {num_questions} questions.
        Each question has 4 options (A, B, C, D).
        Please identify which option (A, B, C, or D) is filled for each question from 1 to {num_questions}.
        Return ONLY a JSON list of objects: [{{"question_index": 0, "marked": "A"}}, ...]
        Use 0-based question_index.
        """

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": base64_image,
                            }
                        },
                    ]
                }
            ]
        }

        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        text = data["candidates"][0]["content"]["parts"][0]["text"]
        # Extract JSON from potential markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        return json.loads(text)
    except Exception as e:
        print(f"Gemini OMR Fallback Failed: {e}")
        return []


def process_omr_sheet_logic(image_bytes: bytes, num_questions: int = 5) -> list[dict]:
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None:
            return []

        gray = cv2.cvtColor(cast(np.ndarray, image), cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 75, 200)
        cnts_found = cv2.findContours(
            edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        cnts = cnts_found[0] if len(cnts_found) == 2 else cnts_found[1]
        docCnt = None
        if len(cnts) > 0:
            # Sort contours by area
            cnts_list = list(cnts)
            cnts_list.sort(key=cast(Any, cv2.contourArea), reverse=True)
            for c in cnts_list:
                peri = cv2.arcLength(c, True)
                approx = cv2.approxPolyDP(c, 0.02 * peri, True)
                if len(approx) == 4:
                    docCnt = approx
                    break
        if docCnt is None:
            warped = gray
            thresh = cv2.threshold(
                warped, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
            )[1]
        else:
            warped = four_point_transform(gray, docCnt.reshape(4, 2))
            thresh = cv2.threshold(
                warped, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
            )[1]
        cnts = cv2.findContours(
            thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        cnts = cnts[0] if len(cnts) == 2 else cnts[1]
        questionCnts = []
        for c in cnts:
            (x, y, w_b, h_b) = cv2.boundingRect(c)
            ar = w_b / float(h_b)
            if w_b >= 20 and h_b >= 20 and ar >= 0.9 and ar <= 1.1:
                questionCnts.append(c)
        if not questionCnts:
            # Fallback to Gemini AI for "AI to read OMR"
            return gemini_omr_fallback(image_bytes, num_questions)
        questionCnts = sort_contours(questionCnts, method="top-to-bottom")[0]
        answers = []
        options = ["A", "B", "C", "D"]
        for q, i in enumerate(range(0, len(questionCnts), 4)):
            if i + 3 >= len(questionCnts):
                break
            cnts = sort_contours(questionCnts[i : i + 4])[0]
            bubbled = None
            max_pixels = 0
            for j, c in enumerate(cnts):
                mask = np.zeros(thresh.shape, dtype="uint8")
                cv2.drawContours(mask, [c], -1, 255, -1)
                mask = cv2.bitwise_and(thresh, thresh, mask=mask)
                total = cv2.countNonZero(mask)
                if bubbled is None or total > max_pixels:
                    bubbled = (total, j)
                    max_pixels = total
            if bubbled:
                answers.append({"question_index": q, "marked": options[bubbled[1]]})
        return answers
    except Exception:
        return []


@router.post("/process", response_model=Attempt)
async def process_omr(
    current_user: CurrentUser,
    session: SessionDep,
    test_id: UUID = Form(...),
    file: UploadFile = File(...),
):
    # Verify Test exists
    test = session.get(Test, test_id)
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    # Read file
    content = await file.read()

    # Process OMR
    # Get total questions to help OMR logic (optional)
    num_questions = len(test.questions)

    try:
        results = process_omr_sheet_logic(content, num_questions=num_questions)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OMR Processing Failed: {str(e)}")

    if not results:
        raise HTTPException(
            status_code=400,
            detail="Could not detect any answers or OMR sheet validation failed.",
        )

    # Create Attempt
    attempt = Attempt(
        student_id=current_user.id,
        test_id=test.id,
        status=AttemptStatus.SUBMITTED,
        tab_switch_count=0,  # Offline test
    )
    session.add(attempt)
    session.commit()
    session.refresh(attempt)

    total_score = 0
    section_scores = {}  # subject -> {section -> score}

    # Sort questions by question_number to align with OMR sequence
    sorted_questions = sorted(test.questions, key=lambda x: x.question_number or 0)
    questions_map = {i: q for i, q in enumerate(sorted_questions)}

    for res in results:
        q_idx = res["question_index"]
        marked_opt = res["marked"]

        if q_idx not in questions_map:
            continue

        question = questions_map[q_idx]
        is_correct = False
        marks = 0

        # Initialize section tracking
        subject = question.subject or "General"
        section = question.section or "Section A"
        if subject not in section_scores:
            section_scores[subject] = {}
        if section not in section_scores[subject]:
            section_scores[subject][section] = 0

        if question.question_type in ["MCQ", "SCQ"] and question.correct_option:
            if marked_opt == question.correct_option:
                is_correct = True
                marks = question.marks
            else:
                # Apply negative marks if incorrect
                marks = question.negative_marks

        total_score += marks
        section_scores[subject][section] += marks

        answer_record = AttemptAnswer(
            attempt_id=attempt.id,
            question_id=question.id,
            selected_option=marked_opt,
            answer_text=None,
            is_correct=is_correct,
            marks_obtained=marks,
            time_spent_seconds=0,
        )
        session.add(answer_record)

    attempt.score = int(total_score)
    attempt.section_results = section_scores
    session.add(attempt)
    session.commit()
    session.refresh(attempt)

    return attempt
