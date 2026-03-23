import time
import logging
import requests
from requests.exceptions import HTTPError

logger = logging.getLogger(__name__)


def ai_post_with_retry(url, json, timeout=180, max_retries=3, initial_delay=2):
    """
    POST request to Gemini with Exponential Backoff.
    Retries on 500, 503, 504 and transient network errors.
    """
    delay = initial_delay
    last_exception = None

    for i in range(max_retries + 1):
        try:
            response = requests.post(url, json=json, timeout=timeout)

            # If 5xx error, retry
            if 500 <= response.status_code <= 504:
                logger.warning(
                    f"Gemini returned {response.status_code}. Retrying in {delay}s... (Attempt {i + 1}/{max_retries + 1})"
                )
                time.sleep(delay)
                delay *= 2
                continue

            # If 429 (Rate Limit), wait longer
            if response.status_code == 429:
                logger.warning(
                    f"Gemini Rate Limited (429). Retrying in {delay * 2}s..."
                )
                time.sleep(delay * 2)
                delay *= 2
                continue

            response.raise_for_status()
            return response

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_exception = e
            logger.warning(f"Network error: {e}. Retrying in {delay}s...")
            time.sleep(delay)
            delay *= 2
        except HTTPError as e:
            # 4xx errors (except 429) shouldn't be retried
            logger.error(f"HTTP Error: {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error calling Gemini: {e}")
            raise e

    if last_exception:
        raise last_exception

    # If we exhausted retries, surface the most useful failure explicitly.
    if response.status_code == 429:
        raise RuntimeError("Gemini rate limit exceeded (429) after retries")
    response.raise_for_status()
    return response
