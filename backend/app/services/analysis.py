import logging
import requests
from app.core.config import settings
from app.core.ai_client import ai_post_with_retry

logger = logging.getLogger(__name__)

GEMINI_MODEL = settings.GEMINI_MODEL
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
)


def generate_attempt_analysis(
    student_name: str,
    test_title: str,
    total_score: int,
    max_marks: int,
    attempts_details: list[dict],
):
    """
    Generate a personalized AI analysis for a student's test attempt.
    """

    # Summarize performance by subject
    subjects = {}
    for detail in attempts_details:
        sub = detail.get("subject", "General")
        if sub not in subjects:
            subjects[sub] = {"correct": 0, "total": 0}
        subjects[sub]["total"] += 1
        if detail.get("is_correct"):
            subjects[sub]["correct"] += 1

    subject_summary = ""
    for sub, stats in subjects.items():
        subject_summary += f"- {sub}: {stats['correct']}/{stats['total']} correct\n"

    prompt = f"""
You are an AI Education Mentor. Analyze the following test performance for {student_name}.

Test Title: {test_title}
Score: {total_score} / {max_marks}

Subject-wise Breakdown:
{subject_summary}

STRICT RULES:
1. Provide a concise, encouraging, and actionable summary (max 150 words).
2. Identify strengths based on high-performing subjects.
3. Identify areas of improvement based on low-performing subjects.
4. Suggest a specific study strategy (e.g., focus on concepts, practice more numerics).
5. Use a friendly, mentor-like tone.

Return the analysis in plain text. Do not use Markdown headers, only bold text if needed.
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 500},
    }

    try:
        response = ai_post_with_retry(GEMINI_URL, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        logger.error(f"AI Analysis failed: {e}")
        return f"Hey {student_name}, you scored {total_score}/{max_marks} in {test_title}. Keep practicing and focus on the areas where you missed marks. You're doing great!"
