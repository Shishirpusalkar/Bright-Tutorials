"""Turn question/solution crops into Markdown + LaTeX with an OpenAI vision model.

The layout engine has already isolated each question, so the model only has
to read one small image at a time: it never has to decide where a question
starts or which figure belongs where. Several crops share one request to
keep the fixed prompt cost low, results are cached on disk by content hash,
and requests run in parallel.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

PROMPT_VERSION = "2026-09-30.1"

SYSTEM_PROMPT = r"""You transcribe cropped images of Indian competitive-exam questions (JEE / NEET: physics, chemistry, mathematics, biology) into Markdown with LaTeX. You are a careful typist: never solve, never add, never drop words.

Every image shows exactly ONE item (a question, or the worked solution of one question). Transcribe only what is inside that image. Ignore watermarks, page borders, coloured highlighting and tick marks.

FORMAT
- Inline math in $...$, displayed equations in $$...$$. Use proper LaTeX: \frac, \sqrt, ^{}, _{}, \vec, \hat, \int, \sum, \lim, \theta, \mu, \Omega, \times, \cdot, \le, \ge, \ne, \pm, \infty, \circ for degrees.
- Units and chemistry in upright text: $\mathrm{kg\,m^{-2}}$, $\mathrm{H_2SO_4}$, $\mathrm{SO_4^{2-}}$, $\mathrm{[Fe(CN)_6]^{3-}}$. Reactions: $\mathrm{A \xrightarrow{H_2O} B}$, equilibria $\rightleftharpoons$.
- Tables, "Match the columns" and List-I/List-II become Markdown tables. Assertion/Reason and statement lists keep one statement per line.
- Keep blanks like "......" as they are.

FIGURE BOXES
- A blue box labelled like [[F1]] or [[S2]] marks a figure that is shown to the student separately. Write that token exactly once, at the place where the box appears in the reading order. Do not describe or transcribe anything inside the box.
- A blue box labelled OPTION FIGURE is a picture that belongs to an option; do not transcribe it. If an option is only a picture, its text is "".

FIELDS
- number: the printed question number, or null if none is visible.
- is_question: false only if the image is not an exam item at all (a page title, instructions, a blank strip).
- stem: the question text without its printed number and without the options.
- options: one entry per expected label, text without the "(A)" prefix. For items without options return [].
- solution: for solution images, the full worked solution without the "Solution:" / "Correct Answer" heading; otherwise "".
- answer: only if the image explicitly prints the final answer (e.g. "Correct Answer: C", "Ans. (B)", "➠ (D)", "Answer: 12"). Letters for options (comma-separated if several), the number for numeric answers. Never work it out yourself; otherwise "".
"""

RESPONSE_SCHEMA = {
    "name": "transcriptions",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "id",
                        "is_question",
                        "number",
                        "stem",
                        "options",
                        "solution",
                        "answer",
                    ],
                    "properties": {
                        "id": {"type": "string"},
                        "is_question": {"type": "boolean"},
                        "number": {"type": ["integer", "null"]},
                        "stem": {"type": "string"},
                        "options": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["label", "text"],
                                "properties": {
                                    "label": {"type": "string"},
                                    "text": {"type": "string"},
                                },
                            },
                        },
                        "solution": {"type": "string"},
                        "answer": {"type": "string"},
                    },
                },
            }
        },
    },
}


@dataclass
class Job:
    id: str
    kind: Literal["question", "solution"]
    png: bytes
    text_hint: str = ""
    option_labels: list[str] = field(default_factory=list)
    figure_tokens: list[str] = field(default_factory=list)
    # Scanned questions: option labels are unknown until the model reads them.
    detect_options: bool = False

    def cache_key(self, model: str) -> str:
        h = hashlib.sha256()
        for part in (
            PROMPT_VERSION,
            model,
            self.kind,
            "detect" if self.detect_options else ",".join(self.option_labels),
            ",".join(self.figure_tokens),
            self.text_hint,
        ):
            h.update(part.encode("utf-8"))
            h.update(b"\x00")
        h.update(self.png)
        return h.hexdigest()


@dataclass
class UsageStats:
    requests: int = 0
    cached: int = 0
    failed: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def as_dict(self) -> dict:
        return self.__dict__.copy()


class Transcriber:
    def __init__(
        self,
        api_key: str | None,
        model: str,
        base_url: str | None = None,
        cache_dir: str | Path | None = None,
        max_workers: int = 4,
        batch_size: int = 6,
        timeout: float = 120.0,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.max_workers = max(1, max_workers)
        self.batch_size = max(1, batch_size)
        self.timeout = timeout
        self.usage = UsageStats()
        self._lock = threading.Lock()
        self._client = None

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url or None,
                timeout=self.timeout,
                max_retries=3,
            )
        return self._client

    # -- cache -----------------------------------------------------------------

    def _cache_get(self, key: str) -> dict | None:
        if not self.cache_dir:
            return None
        path = self.cache_dir / key[:2] / f"{key}.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def _cache_put(self, key: str, value: dict) -> None:
        if not self.cache_dir:
            return
        path = self.cache_dir / key[:2] / f"{key}.json"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:  # pragma: no cover - disk full etc.
            logger.warning("Could not write transcription cache: %s", exc)

    # -- main ------------------------------------------------------------------

    def run(self, jobs: list[Job], progress=None) -> dict[str, dict]:
        """Transcribe jobs. Returns {job_id: item}. Failed jobs are absent."""
        results: dict[str, dict] = {}
        pending: list[tuple[Job, str]] = []
        for job in jobs:
            key = job.cache_key(self.model)
            hit = self._cache_get(key)
            if hit is not None:
                results[job.id] = hit
                self.usage.cached += 1
            else:
                pending.append((job, key))
        if not pending or not self.available:
            return results

        batches = [
            pending[i : i + self.batch_size]
            for i in range(0, len(pending), self.batch_size)
        ]
        done = 0

        def work(batch: list[tuple[Job, str]]) -> None:
            nonlocal done
            out = self._call(batch)
            with self._lock:
                for job, key in batch:
                    item = out.get(job.id)
                    if item is None:
                        self.usage.failed += 1
                        continue
                    results[job.id] = item
                    self._cache_put(key, item)
                done += 1
                if progress:
                    progress(done, len(batches))

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            list(pool.map(work, batches))
        return results

    def _call(self, batch: list[tuple[Job, str]]) -> dict[str, dict]:
        content: list[dict] = [
            {
                "type": "text",
                "text": (
                    f"Transcribe the {len(batch)} items below. Return exactly one entry per id, "
                    "in the same order."
                ),
            }
        ]
        for job, _ in batch:
            header = [f"ID: {job.id}", f"KIND: {job.kind}"]
            if job.kind == "question" and job.detect_options:
                header.append(
                    "EXPECTED OPTIONS: read them from the image; label them A, B, C, D in "
                    "printed order (also for (1)-(4) or (a)-(d)); [] if there are none"
                )
            elif job.kind == "question":
                header.append(
                    "EXPECTED OPTIONS: "
                    + (", ".join(job.option_labels) if job.option_labels else "none")
                )
            if job.figure_tokens:
                header.append(
                    "FIGURE TOKENS TO PLACE: "
                    + ", ".join(f"[[{t}]]" for t in job.figure_tokens)
                )
            if job.text_hint:
                header.append(
                    "Text layer of the same crop (reliable words, often garbled maths/ordering):\n"
                    + job.text_hint[:1800]
                )
            content.append({"type": "text", "text": "\n".join(header)})
            b64 = base64.b64encode(job.png).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{b64}",
                        "detail": "high",
                    },
                }
            )
        try:
            resp = self._get_client().chat.completions.create(
                model=self.model,
                temperature=0,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": content},
                ],
                response_format={"type": "json_schema", "json_schema": RESPONSE_SCHEMA},
            )
        except Exception as exc:
            logger.error("Transcription request failed (%s items): %s", len(batch), exc)
            return {}
        with self._lock:
            self.usage.requests += 1
            if getattr(resp, "usage", None):
                self.usage.input_tokens += resp.usage.prompt_tokens or 0
                self.usage.output_tokens += resp.usage.completion_tokens or 0
        try:
            data = json.loads(resp.choices[0].message.content or "{}")
        except json.JSONDecodeError:
            logger.error("Transcription response was not JSON")
            return {}
        out: dict[str, dict] = {}
        ids = [job.id for job, _ in batch]
        for idx, item in enumerate(data.get("items", [])):
            item_id = item.get("id")
            if item_id not in ids and idx < len(ids):
                item_id = ids[idx]  # tolerate a mangled id, rely on order
            if item_id in ids:
                out[item_id] = item
        return out
