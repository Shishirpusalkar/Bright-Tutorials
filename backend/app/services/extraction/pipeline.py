"""End-to-end extraction: PDF(s) in, display-ready questions out.

layout (PyMuPDF geometry, free)  ->  questions/options/solutions/figures
-> figure + crop PNGs            ->  OpenAI transcription of each crop
-> solution matching + answers   ->  ExtractedQuestion list + report
"""

from __future__ import annotations

import difflib
import logging
import re
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .layout import analyze_document, uses_math_fonts
from .models import ExtractedQuestion, Figure, Item, PageLayout, QuestionDraft
from .render import (
    DISPLAY_ZOOM,
    LLM_ZOOM,
    foreign_boxes,
    open_for_render,
    part_regions,
    render_figure,
    render_region,
    stack,
    to_png,
    trim_whitespace,
)
from .segmenter import ANCHOR_RE, OPTION_RE, _clean_answer, build_questions
from .transcriber import Job, Transcriber

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    import fitz  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

Progress = Callable[[int, str], None]

# Rough list prices (USD per 1M tokens) used only for the cost estimate shown
# to the teacher; unknown models simply show token counts.
_PRICES = {
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
}


@dataclass
class _Source:
    index: int
    path: str
    layouts: list[PageLayout]
    render_doc: object
    drafts: list[QuestionDraft]


@dataclass
class ExtractionResult:
    questions: list[ExtractedQuestion]
    report: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def _rows(items: list[Item]) -> list[list[Item]]:
    texts = sorted(
        (it for it in items if it.kind == "text"),
        key=lambda it: (it.page, it.col, it.cy, it.x0),
    )
    rows: list[list[Item]] = []
    for it in texts:
        if rows:
            last = rows[-1]
            ref = last[0]
            same_page = ref.page == it.page and ref.col == it.col
            overlap = min(max(r.y1 for r in last), it.y1) - max(
                min(r.y0 for r in last), it.y0
            )
            if same_page and overlap > 0.45 * min(it.height, ref.height):
                last.append(it)
                continue
        rows.append([it])
    for r in rows:
        r.sort(key=lambda it: it.x0)
    return rows


def _plain_text(items: list[Item], figures: list[Figure] | None = None) -> str:
    """Text-layer transcription with figure tokens placed by position."""
    rows = _rows(items)
    lines: list[tuple[int, int, float, str]] = []
    for r in rows:
        lines.append(
            (r[0].page, r[0].col, min(it.y0 for it in r), " ".join(it.text for it in r))
        )
    for f in figures or []:
        col = 0
        for it in items:
            if it.page == f.page:
                col = it.col
                break
        lines.append((f.page, col, f.bbox[1] + 0.1, f"[[{f.id}]]"))
    lines.sort(key=lambda t: (t[0], t[1], t[2]))
    return "\n".join(t[3] for t in lines).strip()


def _strip_number(text: str) -> str:
    return ANCHOR_RE.sub("", text, count=1).lstrip() if ANCHOR_RE.match(text) else text


def _strip_option_label(text: str) -> str:
    return OPTION_RE.sub("", text, count=1).lstrip() if OPTION_RE.match(text) else text


def _strip_solution_heading(text: str) -> str:
    text = re.sub(
        r"^\s*solution\s*[:.\-]?\s*\(?\s*correct\s*answer\s*[:\-]?\s*[^)\n]*\)?\s*",
        "",
        text,
        flags=re.I,
    )
    return re.sub(
        r"^\s*(?:sol(?:ution|n)?|explanation)\s*[.:\-]\s*", "", text, flags=re.I
    ).strip()


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _similarity(a: str, b: str) -> float:
    a, b = _norm(a)[:220], _norm(b)[:220]
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def _draft_text(d: QuestionDraft) -> str:
    items = list(d.stem_items)
    for c in d.options:
        items.extend(c.items)
    return _plain_text(items)


def _needs_llm(items: list[Item], figures: list[Figure]) -> bool:
    """Plain prose in a single text font can be taken from the text layer."""
    texts = [it for it in items if it.kind == "text"]
    if not texts or any(it.kind == "raster_text" for it in items):
        return True
    if any(f.layout == "inline" for f in figures):
        return True  # figure beside text: the model places [[F1]] in the sentence
    if uses_math_fonts(texts):
        return True
    sizes = [s.size for it in texts for s in it.spans if s.text.strip()]
    if not sizes:
        return True
    body = sorted(sizes)[len(sizes) // 2]
    if any(s < 0.82 * body for s in sizes):
        return True  # sub/superscripts (H2O, x2, 10-3) need proper markup
    joined = " ".join(it.text for it in texts)
    # Control/replacement characters (unmapped glyphs) or maths symbols.
    if re.search(r"[\u0000-\u0008�]|[−×÷√∫∑π∞≤≥≠±→⇌∆°]", joined):
        return True
    return False


# ---------------------------------------------------------------------------
# Solution matching
# ---------------------------------------------------------------------------


def _is_solution_seq(ds: list[QuestionDraft]) -> bool:
    marked = sum(
        1
        for d in ds
        if d.solution_items
        or d.answer_source in ("solution_marker", "highlighted_option")
    )
    return marked >= max(1, 0.3 * len(ds))


def _is_copy_of(later: list[QuestionDraft], earlier: list[QuestionDraft]) -> bool:
    """Is `later` a reprint of `earlier` (answer copy), not a new section?

    Numbering alone can't tell: many papers restart at 1 for every subject.
    Compare the text of same-numbered questions; image-only reprints (no
    text layer) count as copies when they mirror the numbering exactly.
    """
    by_num = {d.number: d for d in earlier}
    pairs = [(d, by_num[d.number]) for d in later if d.number in by_num]
    if len(pairs) < max(2, 0.6 * len(later)):
        return False

    def body(d: QuestionDraft) -> str:
        text = _strip_number(_draft_text(d))
        return text if len(_norm(text)) >= 12 else ""

    comparable = [(body(a), body(b)) for a, b in pairs]
    comparable = [(a, b) for a, b in comparable if a and b]
    if len(comparable) >= max(2, 0.5 * len(pairs)):
        sims = sorted(_similarity(a, b) for a, b in comparable)
        return sims[len(sims) // 2] >= 0.5
    if all(d.raster_heavy for d in later):
        return len(pairs) >= 0.8 * len(later) and abs(
            len(later) - len(earlier)
        ) <= 0.2 * len(earlier)
    return False


def _match(
    sources: list[_Source],
) -> tuple[list[QuestionDraft], dict[str, QuestionDraft], list[str]]:
    """Pick the student-facing copy of each question and its solution source."""
    warnings: list[str] = []
    seqs: dict[tuple[int, int], list[QuestionDraft]] = defaultdict(list)
    for src in sources:
        for d in src.drafts:
            seqs[(src.index, d.block)].append(d)
    order = sorted(seqs)
    papers: list[list[QuestionDraft]] = []
    secondary: list[list[QuestionDraft]] = []
    for key in order:
        ds = seqs[key]
        if _is_solution_seq(ds):
            secondary.append(ds)
            continue
        dup_of = next((p for p in papers if _is_copy_of(ds, p)), None)
        if dup_of is not None:
            secondary.append(ds)  # a second printed copy (e.g. with answers marked)
        else:
            papers.append(ds)

    solution_of: dict[str, QuestionDraft] = {}
    if not papers:
        # Only a solution copy was uploaded: it doubles as the question paper.
        primaries = [d for ds in secondary for d in ds]
        for d in primaries:
            d.from_solution_copy = True
            if d.solution_items:
                solution_of[d.key] = d
        if primaries:
            warnings.append(
                "No clean question copy found; questions were taken from the solution copy."
            )
        return primaries, solution_of, warnings

    primaries = [d for ds in papers for d in ds]
    by_number: dict[int, list[QuestionDraft]] = defaultdict(list)
    for d in primaries:
        by_number[d.number].append(d)
    texts = {d.key: _draft_text(d) for d in primaries}

    for ds in secondary:
        nums = {d.number for d in ds}
        target = max(papers, key=lambda p: len(nums & {d.number for d in p}))
        target_map = {d.number: d for d in target}
        for s in ds:
            cands = (
                [target_map[s.number]]
                if s.number in target_map
                else list(by_number.get(s.number, []))
            )
            if not cands:
                continue
            s_text = _draft_text(s)
            best = cands[0]
            if s_text:
                scored = sorted(
                    cands, key=lambda c: _similarity(s_text, texts[c.key]), reverse=True
                )
                best = scored[0]
                sim = _similarity(s_text, texts[best.key])
                if sim < 0.35 and texts[best.key]:
                    alt = max(
                        by_number.get(s.number, []),
                        key=lambda c: _similarity(s_text, texts[c.key]),
                        default=best,
                    )
                    if _similarity(s_text, texts[alt.key]) > sim:
                        best = alt
            if s.answer and not best.answer:
                best.answer, best.answer_source = s.answer, s.answer_source
            if best.key not in solution_of and (
                s.solution_items or s.raster_heavy or s.answer
            ):
                solution_of[best.key] = s
    return primaries, solution_of, warnings


def _apply_answer_keys(primaries: list[QuestionDraft], sources: list[_Source]) -> int:
    entries: list[tuple[int, int, str]] = []
    for src in sources:
        for lay in src.layouts:
            entries.extend(lay.answer_key)
    if not entries:
        return 0
    blocks: list[list[QuestionDraft]] = []
    seen: dict[tuple[int, int], int] = {}
    for d in primaries:
        k = (d.source, d.block)
        if k not in seen:
            seen[k] = len(blocks)
            blocks.append([])
        blocks[seen[k]].append(d)
    applied = 0
    by_section: dict[int, dict[int, str]] = defaultdict(dict)
    for sec, num, ans in entries:
        if ans != "-":
            by_section[sec].setdefault(num, ans)
    for sec, answers in by_section.items():
        block = blocks[sec] if sec < len(blocks) else None
        for num, ans in answers.items():
            target = None
            if block is not None:
                target = next((d for d in block if d.number == num), None)
            if target is None:
                same = [d for d in primaries if d.number == num]
                target = same[0] if len(same) == 1 else None
            if target is not None and not target.answer:
                target.answer, target.answer_source = _clean_answer(ans), "answer_key"
                applied += 1
    return applied


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def extract_paper(
    pdf_path: str | Path,
    *,
    asset_dir: str | Path,
    asset_url: str,
    solution_pdf_path: str | Path | None = None,
    transcriber: Transcriber | None = None,
    progress: Progress | None = None,
) -> ExtractionResult:
    t0 = time.time()
    asset_dir = Path(asset_dir)
    asset_dir.mkdir(parents=True, exist_ok=True)
    asset_url = asset_url.rstrip("/")

    def report(pct: int, msg: str) -> None:
        if progress:
            progress(pct, msg)

    report(5, "Reading page layout...")
    sources: list[_Source] = []
    for idx, path in enumerate(p for p in (pdf_path, solution_pdf_path) if p):
        with fitz.open(path) as doc:
            layouts = analyze_document(doc)
        drafts = build_questions(layouts)
        for d in drafts:
            d.source = idx
        sources.append(
            _Source(
                index=idx,
                path=str(path),
                layouts=layouts,
                render_doc=open_for_render(path),
                drafts=drafts,
            )
        )

    total_found = sum(len(s.drafts) for s in sources)
    report(20, f"Located {total_found} question blocks, matching solutions...")
    primaries, solution_of, warnings = _match(sources)
    key_answers = _apply_answer_keys(primaries, sources)

    report(28, "Cropping figures and questions...")
    plans = []
    jobs: list[Job] = []
    use_llm = transcriber is not None and transcriber.available
    for qi, d in enumerate(primaries, start=1):
        plan = _render_question(
            qi, d, solution_of.get(d.key), sources, asset_dir, asset_url, use_llm
        )
        plans.append(plan)
        jobs.extend(plan["jobs"])
        if qi % 20 == 0:
            report(
                28 + int(22 * qi / max(1, len(primaries))),
                f"Cropped {qi}/{len(primaries)} questions...",
            )

    results: dict[str, dict] = {}
    if jobs and use_llm:
        report(50, f"Transcribing {len(jobs)} crops with AI...")

        def llm_progress(done: int, total: int) -> None:
            report(
                50 + int(40 * done / max(1, total)),
                f"AI transcription {done}/{total} batches...",
            )

        assert transcriber is not None
        results = transcriber.run(jobs, progress=llm_progress)

    report(92, "Assembling questions...")
    questions: list[ExtractedQuestion] = []
    for plan in plans:
        q = _assemble(plan, results, use_llm)
        if q is not None:
            questions.append(q)

    for src in sources:
        try:
            src.render_doc.close()  # type: ignore[attr-defined]
        except Exception:
            pass

    usage = transcriber.usage.as_dict() if transcriber else {}
    cost = None
    if transcriber and transcriber.model in _PRICES and usage:
        pin, pout = _PRICES[transcriber.model]
        cost = round(
            usage["input_tokens"] / 1e6 * pin + usage["output_tokens"] / 1e6 * pout, 4
        )
    subjects: dict[str, int] = defaultdict(int)
    for q in questions:
        subjects[q.subject or "General"] += 1
    review = [
        {"number": q.number, "subject": q.subject, "reasons": q.review_reasons}
        for q in questions
        if q.needs_review
    ]
    rep = {
        "engine": "layout-v2",
        "questions": len(questions),
        "question_blocks_found": total_found,
        "with_answer": sum(1 for q in questions if q.correct_answer),
        "with_solution": sum(1 for q in questions if q.solution_content),
        "answers_from_answer_key": key_answers,
        "figures": sum(len(q.content.get("figures", {})) for q in questions),
        "subjects": dict(subjects),
        "needs_review": review,
        "warnings": warnings,
        "ai": {
            "enabled": use_llm,
            "model": transcriber.model if transcriber else None,
            "crops": len(jobs),
            **usage,
            "estimated_cost_usd": cost,
        },
        "seconds": round(time.time() - t0, 1),
    }
    return ExtractionResult(questions=questions, report=rep)


def _save(img, asset_dir: Path, asset_url: str, name: str) -> tuple[str, int, int]:
    path = asset_dir / name
    img.save(path, format="PNG", optimize=True)
    return f"{asset_url}/{name}", img.width, img.height


def _render_question(
    qi: int,
    d: QuestionDraft,
    sol: QuestionDraft | None,
    sources: list[_Source],
    asset_dir: Path,
    asset_url: str,
    use_llm: bool,
) -> dict:
    src = sources[d.source]
    lay = src.layouts
    doc = src.render_doc
    owned = {it.uid for seg in d.segments for it in seg.items}
    gray = d.from_solution_copy
    prefix = f"q{qi:03d}"

    # Question part = everything except solution items.
    sol_ids = {it.uid for it in d.solution_items}
    q_items = [it for seg in d.segments for it in seg.items if it.uid not in sol_ids]
    q_figs = [f for f in d.figures if f.part != "solution"]
    figures: dict[str, dict] = {}
    for f in q_figs:
        img = render_figure(doc, lay, f, owned, grayscale=False)
        url, w, h = _save(img, asset_dir, asset_url, f"{prefix}_{f.id}.png")
        figures[f.id] = {
            "url": url,
            "w": w,
            "h": h,
            "layout": f.layout,
            "part": f.part,
            "option": f.option,
        }

    regions = part_regions(q_items, lay) if q_items else []
    crop_url = None
    llm_png = None
    if regions:
        crops = [
            render_region(
                doc,
                p,
                r,
                DISPLAY_ZOOM,
                erase=foreign_boxes(lay[p], r, owned),
                grayscale=gray,
            )
            for p, _, r in regions
        ]
        crop = trim_whitespace(stack(crops))
        crop_url, _, _ = _save(crop, asset_dir, asset_url, f"{prefix}_crop.png")
        if use_llm:
            masks = [
                (f.bbox, f"[[{f.id}]]" if f.part == "stem" else "OPTION FIGURE")
                for f in q_figs
            ]
            llm_imgs = []
            for p, _, r in regions:
                page_masks = [
                    (b, lab)
                    for (b, lab), f in zip(masks, q_figs, strict=True)
                    if f.page == p
                ]
                llm_imgs.append(
                    render_region(
                        doc,
                        p,
                        r,
                        LLM_ZOOM,
                        erase=foreign_boxes(lay[p], r, owned),
                        masks=page_masks,
                    )
                )
            llm_png = to_png(trim_whitespace(stack(llm_imgs)))

    option_items = {c.label: c.items for c in d.options}
    stem_figs = [f for f in q_figs if f.part == "stem"]
    q_needs_llm = (
        _needs_llm(d.stem_items + [it for c in d.options for it in c.items], stem_figs)
        or d.raster_heavy
    )

    jobs: list[Job] = []
    qjob_id = f"{prefix}_q"
    if use_llm and llm_png and q_needs_llm:
        jobs.append(
            Job(
                id=qjob_id,
                kind="question",
                png=llm_png,
                text_hint=_plain_text(q_items),
                option_labels=[c.label for c in d.options],
                figure_tokens=[f.id for f in stem_figs],
                detect_options=not d.options and d.raster_heavy,
            )
        )

    # --- solution -----------------------------------------------------------
    sol_block = None
    if sol is not None:
        ssrc = sources[sol.source]
        s_owned = {it.uid for seg in sol.segments for it in seg.items}
        s_items = sol.solution_items or (
            [it for seg in sol.segments for it in seg.items] if sol.raster_heavy else []
        )
        s_figs = [f for f in sol.figures if f.part == "solution"]
        s_figures: dict[str, dict] = {}
        for f in s_figs:
            img = render_figure(
                ssrc.render_doc, ssrc.layouts, f, s_owned, grayscale=False
            )
            url, w, h = _save(img, asset_dir, asset_url, f"{prefix}_{f.id}.png")
            s_figures[f.id] = {
                "url": url,
                "w": w,
                "h": h,
                "layout": f.layout,
                "part": "solution",
                "option": None,
            }
        s_regions = part_regions(s_items, ssrc.layouts) if s_items else []
        s_crop_url = None
        s_png = None
        if s_regions:
            s_crops = [
                render_region(
                    ssrc.render_doc,
                    p,
                    r,
                    DISPLAY_ZOOM,
                    erase=foreign_boxes(ssrc.layouts[p], r, s_owned),
                )
                for p, _, r in s_regions
            ]
            s_crop_url, _, _ = _save(
                trim_whitespace(stack(s_crops)),
                asset_dir,
                asset_url,
                f"{prefix}_solution.png",
            )
            if use_llm:
                s_masks_all = [(f.bbox, f"[[{f.id}]]", f.page) for f in s_figs]
                imgs = []
                for p, _, r in s_regions:
                    imgs.append(
                        render_region(
                            ssrc.render_doc,
                            p,
                            r,
                            LLM_ZOOM,
                            erase=foreign_boxes(ssrc.layouts[p], r, s_owned),
                            masks=[(b, lab) for b, lab, pg in s_masks_all if pg == p],
                        )
                    )
                s_png = to_png(trim_whitespace(stack(imgs)))
        s_text_items = [it for it in sol.solution_items if it.kind == "text"]
        sjob_id = f"{prefix}_s"
        if (
            use_llm
            and s_png
            and (_needs_llm(sol.solution_items, s_figs) or sol.raster_heavy)
        ):
            jobs.append(
                Job(
                    id=sjob_id,
                    kind="solution",
                    png=s_png,
                    text_hint=_plain_text(sol.solution_items),
                    figure_tokens=[f.id for f in s_figs],
                )
            )
        fallback = (
            _strip_solution_heading(_plain_text(s_text_items, s_figs))
            if s_text_items
            else ""
        )
        sol_block = {
            "job": sjob_id,
            "figures": s_figures,
            "crop": s_crop_url,
            "fallback": fallback,
            "math": uses_math_fonts(s_text_items),
        }

    stem_fallback = _strip_number(_plain_text(d.stem_items, stem_figs))
    option_fallback = {
        label: _strip_option_label(_plain_text(items))
        for label, items in option_items.items()
    }
    return {
        "draft": d,
        "prefix": prefix,
        "figures": figures,
        "crop": crop_url,
        "jobs": jobs,
        "qjob": qjob_id,
        "stem_fallback": stem_fallback,
        "option_fallback": option_fallback,
        "math": q_needs_llm,
        "solution": sol_block,
    }


def _ensure_tokens(text: str, tokens: list[str]) -> str:
    for t in tokens:
        if f"[[{t}]]" not in text:
            text = (text + f"\n\n[[{t}]]").strip()
    return text


def _assemble(
    plan: dict, results: dict[str, dict], use_llm: bool
) -> ExtractedQuestion | None:
    d: QuestionDraft = plan["draft"]
    reasons: list[str] = []
    stem_tokens = [fid for fid, f in plan["figures"].items() if f["part"] == "stem"]
    qres = results.get(plan["qjob"])

    if qres is not None and not qres.get("is_question", True) and d.raster_heavy:
        return None  # a title strip on a scanned page, not a question

    number = d.number
    if qres is not None and qres.get("number") and qres["number"] != d.number:
        if d.raster_heavy:
            number = int(qres["number"])
        else:
            reasons.append(f"printed number read as {qres['number']}")

    stem_image = None
    option_labels = [c.label for c in d.options]
    if qres is not None:
        stem = qres.get("stem", "").strip()
        llm_opts = {
            re.sub(r"[^A-E]", "", o.get("label", "").strip().upper())[:1]: o.get(
                "text", ""
            ).strip()
            for o in qres.get("options", [])
        }
        llm_opts.pop("", None)
        if not option_labels and d.raster_heavy:
            option_labels = sorted(llm_opts)  # scanned: labels come from the model
        options = {
            lab: llm_opts.get(lab, plan["option_fallback"].get(lab, ""))
            for lab in option_labels
        }
        source = "ai"
    else:
        stem = plan["stem_fallback"]
        if (
            not option_labels
            and d.raster_heavy
            and d.type_hint not in ("NUMERIC", "INTEGER", "SUBJECTIVE")
        ):
            # Scanned MCQ without AI: the student reads the options from the
            # original image and answers with A-D buttons.
            option_labels = ["A", "B", "C", "D"]
        options = {lab: plan["option_fallback"].get(lab, "") for lab in option_labels}
        source = "text-layer"
        if plan["math"]:
            # No AI transcription for a maths-heavy/scanned question: show the
            # original crop so nothing is garbled.
            stem_image = plan["crop"]
            if use_llm:
                reasons.append("AI transcription failed; showing original image")
    stem = _ensure_tokens(stem, stem_tokens)

    # Answers ---------------------------------------------------------------
    answer = d.answer
    answer_source = d.answer_source
    sol_block = plan["solution"]
    sres = results.get(sol_block["job"]) if sol_block else None
    for res in (sres, qres):
        if not answer and res and res.get("answer"):
            answer = _clean_answer(res["answer"])
            answer_source = "solution_text"
    if answer and options and re.fullmatch(r"[A-D](,[A-D])*", answer or "") is None:
        reasons.append(f"answer '{answer}' does not match option labels")
    if not answer:
        reasons.append("no answer found")

    # Type --------------------------------------------------------------------
    qtype = d.type_hint
    if len(options) >= 2:
        if qtype not in ("SCQ", "MCQ"):
            qtype = "SCQ"
        if answer and "," in answer:
            qtype = "MCQ"
    elif qtype == "SUBJECTIVE":
        reasons = [r for r in reasons if r != "no answer found"]
        reasons.append("descriptive question (cannot be auto-graded)")
    elif qtype not in ("NUMERIC", "INTEGER"):
        qtype = "NUMERIC"
    if qtype in ("SCQ", "MCQ") and len(options) not in (4, 5):
        reasons.append(f"found {len(options)} options")
    if d.raster_heavy:
        reasons.append("scanned/image-only question")

    # Solution ------------------------------------------------------------------
    solution_text = None
    solution_content = None
    if sol_block:
        s_tokens = list(sol_block["figures"].keys())
        s_image = None
        if sres is not None:
            solution_text = _strip_solution_heading(sres.get("solution", "").strip())
        else:
            solution_text = sol_block["fallback"]
            if sol_block["math"] or not solution_text:
                s_image = sol_block["crop"]
        solution_text = (
            _ensure_tokens(solution_text or "", s_tokens)
            if (solution_text or s_tokens)
            else ""
        )
        if solution_text or s_image or sol_block["crop"]:
            solution_content = {
                "text": solution_text,
                "image": s_image,
                "crop": sol_block["crop"],
                "figures": sol_block["figures"],
            }

    content = {
        "v": 2,
        "stem": {"text": stem, "image": stem_image},
        "options": [
            {
                "label": lab,
                "text": options.get(lab, ""),
                "figures": [
                    fid for fid, f in plan["figures"].items() if f["option"] == lab
                ],
            }
            for lab in option_labels
        ],
        "figures": plan["figures"],
        "crop": plan["crop"],
        "source": {"page": d.page + 1, "number": number, "transcribed_by": source},
    }
    return ExtractedQuestion(
        number=number,
        ordinal=d.ordinal,
        subject=d.subject,
        section=d.section,
        question_type=qtype or "SCQ",
        question_text=stem,
        options=options or None,
        correct_answer=answer,
        answer_source=answer_source,
        solution_text=solution_text or None,
        page_number=d.page + 1,
        content=content,
        solution_content=solution_content,
        needs_review=bool(reasons),
        review_reasons=reasons,
    )
