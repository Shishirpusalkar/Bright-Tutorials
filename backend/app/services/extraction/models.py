"""Data structures shared by the layout-aware extraction pipeline.

Coordinates are always PDF points in the page's own space (origin top-left),
as reported by PyMuPDF.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Box = tuple[float, float, float, float]

ItemKind = Literal["text", "image", "vector", "raster_text"]
Part = Literal["stem", "option", "solution"]


def box_union(boxes: list[Box]) -> Box:
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def box_area(b: Box) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def box_intersection(a: Box, b: Box) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def box_expand(b: Box, dx: float, dy: float | None = None) -> Box:
    dy = dx if dy is None else dy
    return (b[0] - dx, b[1] - dy, b[2] + dx, b[3] + dy)


def center_in(b: Box, region: Box) -> bool:
    cx = (b[0] + b[2]) / 2
    cy = (b[1] + b[3]) / 2
    return region[0] <= cx <= region[2] and region[1] <= cy <= region[3]


@dataclass
class Span:
    text: str
    bbox: Box
    font: str
    size: float
    color: int


@dataclass
class Item:
    """A positioned piece of page content: a text line or a visual."""

    uid: int
    page: int
    kind: ItemKind
    bbox: Box
    col: int = 0
    text: str = ""
    spans: list[Span] = field(default_factory=list)
    # Vector clusters only: whether the drawing looks like a real figure.
    # Tables/boxes that merely frame text are kept as content, not figures.
    is_figure: bool = False

    @property
    def x0(self) -> float:
        return self.bbox[0]

    @property
    def y0(self) -> float:
        return self.bbox[1]

    @property
    def x1(self) -> float:
        return self.bbox[2]

    @property
    def y1(self) -> float:
        return self.bbox[3]

    @property
    def cy(self) -> float:
        return (self.bbox[1] + self.bbox[3]) / 2

    @property
    def cx(self) -> float:
        return (self.bbox[0] + self.bbox[2]) / 2

    @property
    def height(self) -> float:
        return self.bbox[3] - self.bbox[1]

    @property
    def width(self) -> float:
        return self.bbox[2] - self.bbox[0]

    @property
    def is_visual(self) -> bool:
        return self.kind in ("image", "vector")


@dataclass
class Column:
    page: int
    index: int
    rect: Box


@dataclass
class Marker:
    """A structural line that is not question content."""

    kind: Literal["section", "instruction", "header_block"]
    page: int
    col: int
    y: float
    subject: str | None = None
    section: str | None = None
    question_type: str | None = None


@dataclass
class PageLayout:
    index: int
    rect: Box
    columns: list[Column]
    items: list[Item]
    markers: list[Marker]
    # Everything above this y is page chrome (title block, logo) and ignored.
    content_top: float = 0.0
    content_bottom: float = 1e9
    is_scanned: bool = False
    has_header_block: bool = False
    # (section_index, question_number, answer) parsed from an answer-key page.
    answer_key: list[tuple[int, int, str]] = field(default_factory=list)


@dataclass
class Figure:
    """A cropped visual that must be shown to the student as an image."""

    id: str
    page: int
    bbox: Box
    part: Part
    option: str | None = None
    url: str | None = None
    width: float = 0.0
    height: float = 0.0
    # "block": own line. "inline": sits beside text on the same row.
    layout: Literal["block", "inline"] = "block"


@dataclass
class Segment:
    """The part of a question that lies inside one column of one page."""

    page: int
    col: int
    rect: Box
    items: list[Item] = field(default_factory=list)


@dataclass
class OptionCell:
    label: str
    page: int
    col: int
    label_bbox: Box
    region: Box
    items: list[Item] = field(default_factory=list)


@dataclass
class QuestionDraft:
    """A question located on the page, before transcription."""

    key: str
    number: int
    run: int
    ordinal: int
    subject: str | None
    section: str | None
    type_hint: str | None
    # Index of the numbering sequence in the document. A new sequence starts
    # whenever numbering restarts (per-section numbering, a solution copy).
    block: int = 0
    segments: list[Segment] = field(default_factory=list)
    stem_items: list[Item] = field(default_factory=list)
    options: list[OptionCell] = field(default_factory=list)
    solution_items: list[Item] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)
    answer: str | None = None
    answer_source: str | None = None
    # Question body is mostly rasterised text (scans, image strips).
    raster_heavy: bool = False
    # Printed with the correct option highlighted (solution copy).
    from_solution_copy: bool = False
    # 0 = the uploaded paper, 1 = a separately uploaded solutions PDF.
    source: int = 0

    @property
    def page(self) -> int:
        return self.segments[0].page if self.segments else 0

    @property
    def has_solution(self) -> bool:
        return bool(self.solution_items)

    def all_items(self) -> list[Item]:
        items: list[Item] = []
        for seg in self.segments:
            items.extend(seg.items)
        return items


@dataclass
class ExtractedQuestion:
    """Final, display-ready question produced by the pipeline."""

    number: int
    ordinal: int
    subject: str | None
    section: str | None
    question_type: str
    question_text: str
    options: dict[str, str] | None
    correct_answer: str | None
    answer_source: str | None
    solution_text: str | None
    page_number: int
    content: dict
    solution_content: dict | None
    needs_review: bool = False
    review_reasons: list[str] = field(default_factory=list)
