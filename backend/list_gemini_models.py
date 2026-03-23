import os
import requests
from app.core.config import settings


def list_models():
    if not settings.GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not set")
        return

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={settings.GEMINI_API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        models = response.json().get("models", [])
        print("Available Models:")
        for m in models:
            print(f"- {m['name']}")
    except Exception as e:
        print(f"Error listing models: {e}")
        if "response" in locals() and response.content:
            print(response.text)


if __name__ == "__main__":
    list_models()
