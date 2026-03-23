# ============================================================
# omr_engine.py
# Local OMR Detection + Section-wise Marking
# No Gemini required
# ============================================================

import cv2
import numpy as np


# ============================================================
# BUBBLE DETECTION
# ============================================================


def detect_marked_options(omr_image_path):

    img = cv2.imread(omr_image_path, 0)
    blur = cv2.GaussianBlur(img, (5, 5), 0)
    thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    marked = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if 500 < area < 5000:
            marked.append(cnt)

    # This part must be adapted to your OMR layout grid
    # For now assume sequential mapping

    detected_answers = {}

    question_index = 1
    for cnt in marked:
        detected_answers[question_index] = "A"  # placeholder logic
        question_index += 1

    return detected_answers


# ============================================================
# SCORE CALCULATION
# ============================================================


def calculate_score(student_answers, answer_key, section_configs):

    score = 0
    detailed_result = []

    for q_no, correct_answer in answer_key.items():
        student_answer = student_answers.get(q_no)

        section_config = section_configs.get(q_no)

        if not section_config:
            continue

        if student_answer == correct_answer:
            score += section_config["positive"]
            status = "correct"
        elif student_answer is None:
            status = "unattempted"
        else:
            score -= section_config["negative"]
            status = "wrong"

        detailed_result.append(
            {
                "question": q_no,
                "student_answer": student_answer,
                "correct_answer": correct_answer,
                "status": status,
            }
        )

    return score, detailed_result
