import os
import json
import requests
import sys

# Add the backend directory to sys.path to import settings
sys.path.append(os.getcwd())

try:
    from app.core.config import settings
    from app.core.ai import generate_attempt_analysis
except ImportError:
    print(
        "Error: Could not import app.core.ai/config. Make sure you are in the backend directory."
    )
    sys.exit(1)


def verify_gemini():
    print(f"--- Gemini Final Verification ---")

    if not settings.GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY is not set in .env")
        return

    test_raw_question = """
    (15) The value of log10(100) is 
    (A) 1
    (B) 2
    (C) 3
    (D) 4
    Solution: log10(10^2) = 2 log10(10) = 2.
    """

    print("\nTesting generate_attempt_analysis logic...")
    try:
        result = generate_attempt_analysis(
            student_name="Test Student",
            test_title="Unit Test",
            total_score=80,
            max_marks=100,
            attempts_details=[
                {"question_text": "Sample?", "is_correct": True, "marks_obtained": 4}
            ],
        )
        print("\nSuccess! AI Analysis Output:")
        print(result)

        if result and len(result) > 10:
            print("\nValidation PASSED.")
        else:
            print("\nValidation FAILED: Output too short or empty.")

    except Exception as e:
        print(f"\nError during AI Analysis call: {str(e)}")


if __name__ == "__main__":
    verify_gemini()
