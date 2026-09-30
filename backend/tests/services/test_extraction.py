"""Geometry tests for the layout-aware extraction engine on synthetic PDFs.

Pages are drawn with PyMuPDF so every rule is exercised deterministically:
two columns, tightly packed questions, options in a 2x2 grid with pictures,
questions continuing into the next column, a solution copy, answer keys.
"""

from pathlib import Path

import pytest

from app.services.extraction import extract_paper
from app.services.extraction.layout import analyze_document
from app.services.extraction.segmenter import build_questions
from app.services.extraction.transcriber import Job, Transcriber

fitz = pytest.importorskip("pymupdf")

W, H = 595, 842
LEFT_X, RIGHT_X = 22, 312  # question number x per column
LINE = 13


class Pen:
    """Writes lines down a column the way a question-paper generator does."""

    def __init__(self, page, x: float, y: float = 60):
        self.page = page
        self.x = x
        self.y = y

    def line(self, text: str, indent: float = 0, size: float = 10) -> None:
        self.page.insert_text((self.x + indent, self.y), text, fontsize=size)
        self.y += LINE

    def options_grid(self, a: str, b: str, c: str, d: str) -> None:
        for left, right in ((("(A)", a), ("(B)", b)), (("(C)", c), ("(D)", d))):
            self.page.insert_text(
                (self.x + 16, self.y), f"{left[0]} {left[1]}", fontsize=10
            )
            self.page.insert_text(
                (self.x + 140, self.y), f"{right[0]} {right[1]}", fontsize=10
            )
            self.y += LINE

    def box_figure(
        self, dx: float, w: float, h: float
    ) -> tuple[float, float, float, float]:
        """A small vector diagram (a circle in a frame with a diagonal)."""
        r = fitz.Rect(self.x + dx, self.y - 8, self.x + dx + w, self.y - 8 + h)
        shape = self.page.new_shape()
        shape.draw_circle((r.tl + r.br) / 2, min(w, h) / 3)
        shape.draw_line(r.tl, r.br)
        shape.draw_rect(r)
        shape.finish(color=(0, 0, 0), width=0.8)
        shape.commit()
        self.y += h + 4
        return (r.x0, r.y0, r.x1, r.y1)


def _divider(page) -> None:
    shape = page.new_shape()
    shape.draw_line((W / 2, 40), (W / 2, H - 40))
    shape.finish(color=(0, 0, 0), width=0.5)
    shape.commit()


def _watermark(page) -> None:
    origin = fitz.Point(150, 500)
    page.insert_text(
        origin,
        "Bright Tuition class",
        fontsize=40,
        color=(0.75, 0.75, 0.75),
        morph=(origin, fitz.Matrix(-45)),
    )


def _header(page) -> None:
    page.insert_text((200, 30), "Bright Tuition class", fontsize=20)
    page.insert_text((20, 50), "Subject : Physics", fontsize=11)
    page.insert_text((20, 64), "Standard : 11", fontsize=11)
    page.insert_text((20, 78), "Total Mark : 40", fontsize=11)
    page.insert_text((420, 50), "Date : 01-01-2026", fontsize=11)


def _paper(path: Path, with_solutions: bool = True) -> Path:
    doc = fitz.open()

    # ---- question paper -------------------------------------------------
    page = doc.new_page(width=W, height=H)
    _header(page)
    _divider(page)
    _watermark(page)
    left = Pen(page, LEFT_X, 110)
    left.line("Physics - Section A (MCQ)", indent=40)
    left.line("(1) A block of mass M × g is suspended by a wire.")
    left.line("The elastic energy stored is", indent=16)
    left.options_grid("Mgl", "MgL", "Mgl/2", "MgL/2")
    # Tightly packed: next number directly under the options row.
    left.line("(2) Which graph shows velocity against distance?")
    left.y += 4
    page.insert_text((left.x + 16, left.y), "(A)", fontsize=10)
    page.insert_text((left.x + 140, left.y), "(B)", fontsize=10)
    left.y += 6
    left.box_figure(30, 70, 50)
    left.y -= 54
    left.box_figure(154, 70, 50)
    page.insert_text((left.x + 16, left.y), "(C)", fontsize=10)
    page.insert_text((left.x + 140, left.y), "(D)", fontsize=10)
    left.y += 6
    left.box_figure(30, 70, 50)
    left.y -= 54
    left.box_figure(154, 70, 50)
    left.line("(3) The electric flux through the surface")
    left.box_figure(40, 150, 60)
    left.options_grid("largest", "least", "same", "zero")
    # Question 4 starts at the bottom of the left column ...
    left.y = H - 90
    left.line("(4) A wire of length L and cross section A is stretched so")
    left.line("that its length changes by l. The Young's modulus", indent=16)
    # ... and continues at the top of the right column.
    right = Pen(page, RIGHT_X, 110)
    right.line("of the wire is given by", indent=16)
    right.line("(A) MgL/Al (B) Mgl/AL", indent=16)
    right.line("(C) Ml/gAL (D) AL/Mgl", indent=16)
    right.line("Physics - Section B (NUMERIC)", indent=40)
    right.line("(5) A ball falls from 9 cm into water. Find its depth in cm.")

    if with_solutions:
        # ---- solution copy -----------------------------------------------
        page = doc.new_page(width=W, height=H)
        _header(page)
        _divider(page)
        pen = Pen(page, LEFT_X, 110)
        pen.line("(1) A block of mass M × g is suspended by a wire.")
        pen.line("The elastic energy stored is", indent=16)
        pen.options_grid("Mgl", "MgL", "Mgl/2", "MgL/2")
        pen.line("Solution:(Correct Answer:C)", indent=16)
        pen.line("Energy = (1/2) x stress x strain x volume.", indent=16)
        pen.line("(2) Which graph shows velocity against distance?")
        pen.line("Solution:(Correct Answer:A)", indent=16)
        pen.line("(3) The electric flux through the surface")
        pen.line("Solution:(Correct Answer:D)", indent=16)
        pen.line("(4) A wire of length L and cross section A is stretched so")
        pen.line("Solution:(Correct Answer:B)", indent=16)
        pen.line("(5) A ball falls from 9 cm into water. Find its depth in cm.")
        pen.line("Solution:(Correct Answer:6)", indent=16)
        pen.line("Using energy balance the depth is 6 cm.", indent=16)
    doc.save(path)
    return path


@pytest.fixture()
def paper(tmp_path: Path) -> Path:
    return _paper(tmp_path / "paper.pdf")


def _questions(path: Path):
    with fitz.open(path) as doc:
        layouts = analyze_document(doc)
    return layouts, build_questions(layouts)


def test_columns_watermark_and_header_are_handled(paper: Path) -> None:
    layouts, _ = _questions(paper)
    first = layouts[0]
    assert len(first.columns) == 2
    texts = " ".join(it.text for it in first.items)
    assert "Total Mark" not in texts  # title block dropped
    assert first.has_header_block
    # The rotated watermark never becomes a text item.
    assert all("Bright Tuition" not in it.text for it in first.items)


def test_questions_are_found_in_order_with_sections(paper: Path) -> None:
    _, drafts = _questions(paper)
    paper_copy = [d for d in drafts if d.block == drafts[0].block]
    assert [d.number for d in paper_copy] == [1, 2, 3, 4, 5]
    assert paper_copy[0].subject == "Physics"
    assert paper_copy[0].type_hint == "SCQ"
    assert paper_copy[4].type_hint == "NUMERIC"


def test_tightly_packed_options_stay_with_their_question(paper: Path) -> None:
    _, drafts = _questions(paper)
    q1, q2 = drafts[0], drafts[1]
    assert [c.label for c in q1.options] == ["A", "B", "C", "D"]
    stem2 = " ".join(it.text for it in q2.stem_items)
    assert "(C)" not in stem2 and "Mgl" not in stem2


def test_pictures_belong_to_their_option_cell(paper: Path) -> None:
    _, drafts = _questions(paper)
    q2 = drafts[1]
    assert [c.label for c in q2.options] == ["A", "B", "C", "D"]
    option_figs = {f.option for f in q2.figures if f.part == "option"}
    assert option_figs == {"A", "B", "C", "D"}
    assert not [f for f in q2.figures if f.part == "stem"]


def test_stem_figure_and_continuation_across_columns(paper: Path) -> None:
    _, drafts = _questions(paper)
    q3, q4 = drafts[2], drafts[3]
    assert [f.part for f in q3.figures] == ["stem"]
    assert [(s.page, s.col) for s in q4.segments] == [(0, 0), (0, 1)]
    assert [c.label for c in q4.options] == [
        "A",
        "B",
        "C",
        "D",
    ]  # "(A) x (B) y" lines split


def test_solution_copy_supplies_answers_and_solutions(
    paper: Path, tmp_path: Path
) -> None:
    res = extract_paper(
        paper, asset_dir=tmp_path / "assets", asset_url="/a", transcriber=None
    )
    by_num = {q.number: q for q in res.questions}
    assert sorted(by_num) == [1, 2, 3, 4, 5]
    assert by_num[1].correct_answer == "C"
    assert by_num[2].correct_answer == "A"
    assert by_num[5].correct_answer == "6"
    assert by_num[5].question_type == "NUMERIC"
    assert "stress" in (by_num[1].solution_text or "")
    # Every figure file exists and is referenced from the content.
    q2 = by_num[2].content
    assert {o["label"]: o["figures"] for o in q2["options"]} == {
        "A": ["A1"],
        "B": ["B1"],
        "C": ["C1"],
        "D": ["D1"],
    }
    for fig in q2["figures"].values():
        assert (tmp_path / "assets" / Path(fig["url"]).name).exists()
    assert "[[F1]]" in by_num[3].question_text
    assert res.report["with_answer"] == 5


def test_answer_key_table_is_used_and_not_read_as_questions(tmp_path: Path) -> None:
    path = _paper(tmp_path / "p.pdf", with_solutions=False)
    doc = fitz.open(path)
    page = doc.new_page(width=W, height=H)
    y = 60
    for n, ans in zip(range(1, 11), "CADBACBDAC", strict=True):
        page.insert_text((60, y), f"{n}.", fontsize=10)
        page.insert_text((110, y), ans, fontsize=10)
        page.insert_text((160, y), "Full Syllabus", fontsize=10)
        y += 18
    doc.save(tmp_path / "keyed.pdf")
    res = extract_paper(
        tmp_path / "keyed.pdf", asset_dir=tmp_path / "a", asset_url="/a"
    )
    by_num = {q.number: q for q in res.questions}
    assert sorted(by_num) == [1, 2, 3, 4, 5]
    assert by_num[1].correct_answer == "C"
    assert by_num[4].answer_source == "answer_key"


def test_transcriber_output_is_used_and_cached(
    paper: Path, tmp_path: Path, monkeypatch
) -> None:
    calls: list[list[str]] = []

    def fake_call(_self, batch):
        calls.append([job.id for job, _ in batch])
        return {
            job.id: {
                "id": job.id,
                "is_question": True,
                "number": None,
                "stem": "Transcribed $x^2$ "
                + " ".join(f"[[{t}]]" for t in job.figure_tokens),
                "options": [
                    {"label": lab, "text": f"$\\frac{{{lab}}}{{2}}$"}
                    for lab in job.option_labels
                ],
                "solution": "Worked $E=mc^2$",
                "answer": "",
            }
            for job, _ in batch
        }

    monkeypatch.setattr(Transcriber, "_call", fake_call)
    tr = Transcriber(api_key="test", model="gpt-4.1-mini", cache_dir=tmp_path / "cache")
    res = extract_paper(paper, asset_dir=tmp_path / "a", asset_url="/a", transcriber=tr)
    assert calls, "question 1 contains maths symbols, so it must be transcribed"
    transcribed = [
        q for q in res.questions if q.content["source"]["transcribed_by"] == "ai"
    ]
    assert transcribed
    for q in transcribed:
        assert q.question_text.startswith("Transcribed")
    # Second run is served entirely from the disk cache.
    calls.clear()
    tr2 = Transcriber(
        api_key="test", model="gpt-4.1-mini", cache_dir=tmp_path / "cache"
    )
    extract_paper(paper, asset_dir=tmp_path / "b", asset_url="/b", transcriber=tr2)
    assert calls == []
    assert tr2.usage.cached > 0


def test_job_cache_key_depends_on_image_and_prompt() -> None:
    a = Job(id="1", kind="question", png=b"one")
    b = Job(id="2", kind="question", png=b"two")
    assert a.cache_key("m") != b.cache_key("m")
    assert a.cache_key("m") != a.cache_key("other-model")
