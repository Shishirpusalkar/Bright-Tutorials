"""Split laid-out pages into questions, options, solutions and figures.

The key idea: every question owns a vertical band of a column, starting at
its number ("(12)", "12.", "Q12") and ending where the next question starts.
Content that runs past the bottom of a column continues the same question in
the next column/page. Items are assigned by geometry (their centre point),
never by reading order, so tightly packed questions and two-column
neighbours cannot bleed into each other.
"""

from __future__ import annotations

import logging
import re
import statistics
from dataclasses import dataclass

from .models import (
    Box,
    Figure,
    Item,
    Marker,
    OptionCell,
    PageLayout,
    QuestionDraft,
    Segment,
    box_expand,
    box_union,
    center_in,
)

logger = logging.getLogger(__name__)

ANCHOR_RE = re.compile(
    r"^\s*(?:Q(?:ue(?:s(?:tion)?)?)?\s*\.?\s*(?:no\.?\s*)?)?"
    r"(?:\((\d{1,3})\)|\[(\d{1,3})\]|(\d{1,3})(?:\.(?!\d)|\)|:(?!\d)))"
)
OPTION_RE = re.compile(r"^\s*(?:\(([A-Da-d])\)|\[([A-Da-d])\]|([A-D])[\.\)](?![\w.]))")
SOLUTION_RE = re.compile(
    r"^\s*(?:sol(?:ution|n)?|explanation|hint)\s*[\.:\-]|correct\s*answer\s*[:\-]?",
    re.I,
)
ANSWER_IN_TEXT_RE = re.compile(
    r"(?:correct\s*answer|ans(?:wer)?)\s*[:\-\.]?\s*\(?\s*"
    r"((?:[A-Da-d]\s*(?:,|and|&)\s*)*[A-Da-d](?![a-z])|[-+]?\d+(?:\.\d+)?)",
    re.I,
)
ARROW_ANSWER_RE = re.compile(
    r"^\s*(?:[➠⇒→►▶➔➜➤]|ans(?:wer)?\s*[:\.\-]?)\s*"
    r"\(?\s*((?:[A-Da-d]\s*,\s*)*[A-Da-d]|[-+]?\d+(?:\.\d+)?)\s*\)?\s*$",
    re.I,
)
GREEN_RE_TOL = 0.25


@dataclass
class _Anchor:
    item: Item
    number: int
    page: int
    col: int
    x0: float
    y: float


@dataclass
class _Cut:
    y: float
    owner: str | None  # question key, or None for "belongs to nobody"


def _anchor_number(it: Item) -> int | None:
    if it.kind != "text":
        return None
    m = ANCHOR_RE.match(it.text)
    if not m:
        return None
    num = next(g for g in m.groups() if g is not None)
    n = int(num)
    if n == 0:
        return None
    rest = it.text[m.end() :].strip()
    # "12. 5 cm" style decimals / "(1) = ..." equation labels are not questions.
    if rest[:1] in ("=", "%", "°"):
        return None
    return n


def _column_left(items: list[Item]) -> float:
    xs = sorted(it.x0 for it in items if it.kind in ("text", "raster_text"))
    if not xs:
        return 0.0
    return xs[min(len(xs) - 1, max(0, int(len(xs) * 0.03)))]


# ---------------------------------------------------------------------------
# Anchors
# ---------------------------------------------------------------------------


def find_anchors(
    layouts: list[PageLayout],
) -> tuple[list[_Anchor], dict[tuple[int, int], list[Marker]]]:
    """Accept question-number anchors in global reading order."""
    markers_by_col: dict[tuple[int, int], list[Marker]] = {}
    events: list[tuple[int, int, float, int, object]] = []
    # A scanned page in front of the first typed question page is a cover or
    # instructions page ("1. The test is of 3 hours ..."), not questions.
    first_typed = min(
        (
            lay.index
            for lay in layouts
            if not lay.is_scanned
            and any(_anchor_number(it) is not None for it in lay.items)
        ),
        default=None,
    )
    for lay in layouts:
        for col in lay.columns:
            col_items = [it for it in lay.items if it.col == col.index]
            left = _column_left(col_items)
            for it in col_items:
                n = _anchor_number(it)
                if n is None:
                    continue
                if it.x0 > left + 16:
                    continue
                events.append((lay.index, col.index, it.y0, 1, (n, it)))
            if lay.is_scanned and (first_typed is None or lay.index > first_typed):
                events.extend(_raster_anchor_events(lay, col.index, col_items))
            mk = [
                m for m in lay.markers if m.col == col.index or m.kind == "header_block"
            ]
            markers_by_col[(lay.index, col.index)] = [
                m for m in lay.markers if m.col == col.index
            ]
            for m in mk:
                if m.kind == "header_block" and col.index != 0:
                    continue
                events.append((lay.index, col.index, m.y, 0, m))
    events.sort(key=lambda e: (e[0], e[1], e[2], e[3]))
    candidates = [e for e in events if e[3] == 1]
    cand_index = {id(e): i for i, e in enumerate(candidates)}

    def starts_run(idx: int, n: int) -> bool:
        """n is followed by n+1 and n+2 (one gap allowed) among the next candidates."""
        want = n + 1
        hits = 0
        for e in candidates[idx + 1 : idx + 6]:
            m = e[4][0]
            if m is None:
                continue
            if m == want or m == want + 1:
                hits += 1
                want = m + 1
                if hits >= 2:
                    return True
        return False

    accepted: list[_Anchor] = []
    last: int | None = None
    reset: str | None = "start"
    anchor_x: dict[tuple[int, int], float] = {}
    for ev in events:
        page, col, y, kind, payload = ev
        if kind == 0:
            m = payload  # type: ignore[assignment]
            if m.kind in ("header_block", "section"):  # type: ignore[union-attr]
                reset = m.kind  # type: ignore[union-attr]
            continue
        n, it = payload  # type: ignore[misc]
        if n is None:  # scanned rows: number unknown, assume sequence
            n = (last or 0) + 1
        ok = False
        if last is None or n == last + 1:
            ok = True
        elif reset and n == 1:
            ok = True
        elif last + 1 < n <= last + 3:
            ref = anchor_x.get((page, col))
            ok = ref is None or abs(it.x0 - ref) < 5
        elif reset == "header_block":
            ok = True
        if not ok and starts_run(cand_index[id(ev)], n):
            ok = True  # numbering restarted/jumped and stays consistent
        if not ok:
            continue
        accepted.append(
            _Anchor(item=it, number=n, page=page, col=col, x0=it.x0, y=it.y0)
        )
        anchor_x.setdefault((page, col), it.x0)
        last = n
        reset = None
    return accepted, markers_by_col


def _raster_anchor_events(lay: PageLayout, col: int, rows: list[Item]):
    """Scanned pages: a question starts on a row printed at the hanging indent."""
    rows = sorted(rows, key=lambda r: r.y0)
    if not rows:
        return []
    left = _column_left(rows)
    heights = [r.height for r in rows] or [10.0]
    med_h = statistics.median(heights)
    events = []
    prev: Item | None = None
    for r in rows:
        at_margin = r.x0 <= left + 4
        prev_indented = (
            prev is None or prev.x0 > left + 6 or r.y0 - prev.y1 > 0.6 * med_h
        )
        if at_margin and prev_indented and r.height < 2.5 * med_h:
            events.append((lay.index, col, r.y0, 1, (None, r)))
        prev = r
    return events


# ---------------------------------------------------------------------------
# Cutting columns into question bands
# ---------------------------------------------------------------------------


def _starts_structure(it: Item) -> bool:
    return it.kind == "text" and bool(
        OPTION_RE.match(it.text)
        or ANCHOR_RE.match(it.text)
        or SOLUTION_RE.match(it.text)
    )


def _marker_right(it: Item, regex: re.Pattern[str]) -> float:
    """x where the printed marker ("(12)", "(B)") ends inside a text line."""
    if not it.spans:
        return it.x0 + 20
    s = it.spans[0]
    m = regex.match(s.text)
    if not m or not s.text:
        return s.bbox[2]
    frac = min(1.0, m.end() / max(1, len(s.text)))
    return s.bbox[0] + (s.bbox[2] - s.bbox[0]) * frac


def _best_cut(
    col_items: list[Item],
    anchor: Item,
    lower_bound: float,
    marker_re: re.Pattern[str] = ANCHOR_RE,
) -> float:
    """Boundary between the previous question and the one starting at `anchor`.

    Normally that is just above the question number. Stacked content on the
    number's row (chemical structures, tall fractions) can start a few points
    higher; such lines are pulled into the new question only when the gap
    above them is clearly larger than the gap to the number's row, which is
    how typesetters separate questions. Option rows are never pulled in.
    """
    number_right = _marker_right(anchor, marker_re)
    chain_top = anchor.y0
    accepted_top = anchor.y0
    for step in range(6):
        # The first stacked row must overlap the number's own line; a line
        # that merely ends just above it is the previous question's tail.
        reach = 0.5 if step == 0 else -3
        above = [
            it
            for it in col_items
            if it is not anchor
            and it.y0 < chain_top - 0.5
            and it.y1 > chain_top + reach
            and it.y1 < chain_top + max(anchor.height, 6)
        ]
        if not above:
            break
        row_top = min(it.y0 for it in above)
        row = [
            it
            for it in col_items
            if it.y0 < chain_top and it.y1 > row_top + 1 and it is not anchor
        ]
        stacked = all(it.kind == "text" and it.x0 > number_right + 2 for it in row)
        if not stacked or any(_starts_structure(it) for it in row):
            break
        if anchor.y0 - row_top > 34 or row_top - 0.5 <= lower_bound:
            break
        prev_bottom = max(
            (
                it.y1
                for it in col_items
                if it.y1 <= row_top + 1 and it not in row and it is not anchor
            ),
            default=lower_bound,
        )
        chain_top = row_top
        if row_top - prev_bottom >= 4.0:
            accepted_top = row_top
            break
    return max(lower_bound, accepted_top - 0.5)


def build_questions(layouts: list[PageLayout]) -> list[QuestionDraft]:
    anchors, markers_by_col = find_anchors(layouts)
    if not anchors:
        return []

    # Context (subject/section/type) from markers in reading order.
    drafts: dict[str, QuestionDraft] = {}
    anchor_by_uid: dict[tuple[int, int], _Anchor] = {
        (a.page, a.item.uid): a for a in anchors
    }

    run = 0
    ordinal = 0
    ctx_subject: str | None = None
    ctx_section: str | None = None
    ctx_type: str | None = None
    open_key: str | None = None
    seq = -1
    last_number: int | None = None
    prev_scanned = False

    ordered_keys: list[str] = []
    for lay in layouts:
        for col in lay.columns:
            col_items = [it for it in lay.items if it.col == col.index]
            col_markers = sorted(
                markers_by_col.get((lay.index, col.index), []), key=lambda m: m.y
            )
            if col.index == 0:
                if any(m.kind == "header_block" for m in lay.markers):
                    open_key = None
                    run += 1 if drafts else 0
                    last_number = None
                elif lay.is_scanned and not prev_scanned:
                    # A scanned page inserted after a typed one starts fresh;
                    # its title block must not leak into the previous question.
                    open_key = None
                prev_scanned = lay.is_scanned
            col_anchors = sorted(
                (
                    anchor_by_uid[(lay.index, it.uid)]
                    for it in col_items
                    if (lay.index, it.uid) in anchor_by_uid
                ),
                key=lambda a: a.y,
            )

            # Build cut list: (y, owner). Start with carry-over owner.
            cuts: list[_Cut] = [_Cut(y=-1e9, owner=open_key)]
            events: list[tuple[float, int, object]] = [
                (m.y, 0, m) for m in col_markers
            ] + [(a.y, 1, a) for a in col_anchors]
            events.sort(key=lambda e: (e[0], e[1]))
            prev_boundary = -1e9
            for y, kind, payload in events:
                if kind == 0:
                    m: Marker = payload  # type: ignore[assignment]
                    if m.subject:
                        ctx_subject = m.subject
                    if m.section:
                        ctx_section = m.section
                    if m.question_type:
                        ctx_type = m.question_type
                    elif m.kind == "section" and m.subject and not m.section:
                        ctx_type = None
                    cut_y = y - 0.5
                    cuts.append(_Cut(y=cut_y, owner=None))
                    open_key = None
                    prev_boundary = cut_y
                    continue
                a: _Anchor = payload  # type: ignore[assignment]
                if last_number is None or a.number <= last_number:
                    seq += (
                        1  # a new numbering sequence (paper, section, or solution copy)
                    )
                last_number = a.number
                key = f"r{run}-q{a.number}-{ordinal}"
                ordinal += 1
                drafts[key] = QuestionDraft(
                    key=key,
                    number=a.number,
                    run=run,
                    ordinal=ordinal,
                    block=seq,
                    subject=ctx_subject,
                    section=ctx_section,
                    type_hint=ctx_type,
                )
                ordered_keys.append(key)
                cut_y = _best_cut(col_items, a.item, prev_boundary)
                cuts.append(_Cut(y=cut_y, owner=key))
                open_key = key
                prev_boundary = cut_y

            # Assign items by centre y.
            for it in col_items:
                owner = None
                for c in cuts:
                    if it.cy >= c.y:
                        owner = c.owner
                    else:
                        break
                if owner is None:
                    continue
                d = drafts[owner]
                seg = d.segments[-1] if d.segments else None
                if seg is None or seg.page != lay.index or seg.col != col.index:
                    seg = Segment(page=lay.index, col=col.index, rect=col.rect)
                    d.segments.append(seg)
                seg.items.append(it)

    result: list[QuestionDraft] = []
    for key in ordered_keys:
        d = drafts[key]
        if not d.segments:
            continue
        for seg in d.segments:
            seg.items.sort(key=lambda it: (it.y0, it.x0))
            seg.rect = _segment_rect(seg)
        _split_parts(d)
        result.append(d)
    return result


def _segment_rect(seg: Segment) -> Box:
    b = box_union([it.bbox for it in seg.items])
    cx0, cy0, cx1, cy1 = seg.rect
    return (
        max(cx0, b[0] - 3),
        max(cy0, b[1] - 2),
        min(cx1, b[2] + 3),
        min(cy1, b[3] + 2),
    )


# ---------------------------------------------------------------------------
# Stem / options / solution
# ---------------------------------------------------------------------------


def _is_green(color: int) -> bool:
    r, g, b = (color >> 16) & 255, (color >> 8) & 255, color & 255
    return g > 90 and g > r + 40 and g > b + 25


def _split_parts(d: QuestionDraft) -> None:
    # 1. Solution marker: everything from it onwards is the solution.
    sol_pos: tuple[int, float] | None = None
    for si, seg in enumerate(d.segments):
        for it in seg.items:
            if it.kind != "text":
                continue
            if SOLUTION_RE.match(it.text) or ARROW_ANSWER_RE.match(it.text):
                sol_pos = (si, it.y0 - 0.5)
                ans = ANSWER_IN_TEXT_RE.search(it.text) or ARROW_ANSWER_RE.match(
                    it.text
                )
                if ans:
                    d.answer = _clean_answer(ans.group(1))
                    d.answer_source = "solution_marker"
                break
        if sol_pos:
            break

    q_items: list[tuple[int, Item]] = []
    for si, seg in enumerate(d.segments):
        for it in seg.items:
            if sol_pos and (
                si > sol_pos[0] or (si == sol_pos[0] and it.cy >= sol_pos[1])
            ):
                d.solution_items.append(it)
            else:
                q_items.append((si, it))

    # 2. Option labels (take the last run that starts with A).
    labels: list[tuple[int, Item, str]] = []
    for si, it in q_items:
        if it.kind != "text":
            continue
        m = OPTION_RE.match(it.text)
        if m:
            letter = next(g for g in m.groups() if g is not None).upper()
            labels.append((si, it, letter))
    # Order labels row by row (labels on one row can differ by a few points
    # vertically when the option content has tall math).
    labels.sort(key=lambda t: (t[0], t[1].y0))
    row_key: list[float] = []
    for i, (si, it, _) in enumerate(labels):
        if i and _same_option_row(labels[i - 1][1], it) and labels[i - 1][0] == si:
            row_key.append(row_key[-1])
        else:
            row_key.append(it.y0)
    labels = [
        lab
        for _, lab in sorted(
            zip(row_key, labels, strict=True), key=lambda z: (z[1][0], z[0], z[1][1].x0)
        )
    ]
    if d.type_hint == "SUBJECTIVE":
        labels = []  # (a)/(b) sub-parts of a descriptive question are not options
    # Options are the run starting at an "A" that covers the most letters;
    # later runs win ties (a match-the-column table above uses A-D too),
    # while a wrapped line that happens to start with "(A)" covers fewer.
    start = None
    best_cover = 2
    a_positions = [i for i, lab in enumerate(labels) if lab[2] == "A"]
    for pos_i, i in enumerate(a_positions):
        end = a_positions[pos_i + 1] if pos_i + 1 < len(a_positions) else len(labels)
        cover = len({lab[2] for lab in labels[i:end]})
        if cover >= best_cover:
            start, best_cover = i, cover
    chosen = labels[start:] if start is not None else []
    # Keep first occurrence of each letter, in order A, B, C, D...
    seen: set[str] = set()
    uniq: list[tuple[int, Item, str]] = []
    for lab in chosen:
        if lab[2] not in seen:
            seen.add(lab[2])
            uniq.append(lab)
    cells = _option_cells(d, uniq)

    # 3. Assign items to option cells or stem.
    label_uids = {lab[1].uid for lab in uniq}
    for si, it in q_items:
        placed = False
        for cell in cells:
            seg = d.segments[si]
            if (
                seg.page == cell.page
                and seg.col == cell.col
                and center_in(it.bbox, cell.region)
            ):
                cell.items.append(it)
                placed = True
                break
        if not placed:
            d.stem_items.append(it)
    d.options = cells

    # Answer from a highlighted (green) option label in a solution copy.
    for cell in cells:
        for it in cell.items:
            if it.uid in label_uids and it.spans and _is_green(it.spans[0].color):
                d.from_solution_copy = True
                if not d.answer:
                    d.answer = cell.label
                    d.answer_source = "highlighted_option"

    if any(it.kind == "raster_text" for _, it in q_items):
        raster = sum(it.height for _, it in q_items if it.kind == "raster_text")
        texty = sum(it.height for _, it in q_items if it.kind == "text")
        d.raster_heavy = raster > texty

    d.figures = _build_figures(d)


def _same_option_row(a: Item, b: Item) -> bool:
    """Labels share a grid row when they are side by side, not stacked.

    Side-by-side labels can drift a few points vertically when one option
    holds a tall picture, but stacked labels always share the same x.
    """
    return abs(a.y0 - b.y0) < 16 and abs(a.x0 - b.x0) > 40


def _clean_answer(raw: str) -> str:
    raw = raw.strip().upper()
    letters = re.findall(r"[A-D]", raw)
    if letters and not re.search(r"\d", raw):
        return ",".join(dict.fromkeys(letters))
    return raw


def _option_cells(
    d: QuestionDraft, labels: list[tuple[int, Item, str]]
) -> list[OptionCell]:
    cells: list[OptionCell] = []
    by_seg: dict[int, list[tuple[Item, str]]] = {}
    for si, it, letter in labels:
        by_seg.setdefault(si, []).append((it, letter))
    for si, labs in by_seg.items():
        seg = d.segments[si]
        col_x0, _, col_x1, _ = _column_bounds(d, si)
        seg_bottom = max(it.y1 for it in seg.items) + 1

        # Grid columns: labels printed at (nearly) the same x. A 2x2 layout
        # has two (A/C and B/D); stacked options have one; a single row of
        # four has four. Each grid column is cut into one band per label.
        xs: list[list[Item]] = []
        for it, _ in sorted(labs, key=lambda t: t[0].x0):
            if xs and it.x0 - xs[-1][0].x0 < 25:
                xs[-1].append(it)
            else:
                xs.append([it])
        col_starts = [min(i.x0 for i in grp) for grp in xs]
        letter_of = {id(it): letter for it, letter in labs}
        bounds: list[tuple[float, float]] = []
        top_of: dict[int, float] = {}
        lower_of: dict[int, float] = {}
        for gi, grp in enumerate(xs):
            gx0 = col_x0 if gi == 0 else col_starts[gi] - 2
            gx1 = col_starts[gi + 1] - 2 if gi + 1 < len(xs) else col_x1
            bounds.append((gx0, gx1))
            grid_items = [
                it
                for it in seg.items
                if gx0 <= it.x0 - 0.5 and it.x1 <= gx1 + 2 and it.kind == "text"
            ]
            grp.sort(key=lambda i: i.y0)
            for li, lab in enumerate(grp):
                lower = grp[li - 1].y1 if li > 0 else lab.y0 - 36
                lower_of[id(lab)] = lower
                if li == 0 and len(xs) == 1:
                    top_of[id(lab)] = lab.y0 - 1.5  # stacked list: nothing to pull up
                else:
                    top_of[id(lab)] = min(
                        lab.y0 - 1.5, _best_cut(grid_items, lab, lower, OPTION_RE)
                    )

        # Options side by side start together: if B's structure begins a line
        # above its label, so does A's — unless that line is stem text that
        # starts at the question's left margin.
        all_labs = [lab for grp in xs for lab in grp]
        for lab in all_labs:
            row = [o for o in all_labs if o is lab or _same_option_row(o, lab)]
            row_top = min(top_of[id(o)] for o in row)
            if row_top >= top_of[id(lab)] - 0.1 or row_top <= lower_of[id(lab)]:
                continue
            gi = next(i for i, grp in enumerate(xs) if lab in grp)
            gx0, gx1 = bounds[gi]
            label_right = _marker_right(lab, OPTION_RE)
            band = [
                it
                for it in seg.items
                if it.kind == "text"
                and row_top <= it.cy < top_of[id(lab)]
                and gx0 <= it.cx <= gx1
            ]
            if all(
                it.x0 > label_right + 2 and not _starts_structure(it) for it in band
            ):
                top_of[id(lab)] = row_top

        for gi, grp in enumerate(xs):
            gx0, gx1 = bounds[gi]
            for li, lab in enumerate(grp):
                bottom = top_of[id(grp[li + 1])] if li + 1 < len(grp) else seg_bottom
                cells.append(
                    OptionCell(
                        label=letter_of[id(lab)],
                        page=seg.page,
                        col=seg.col,
                        label_bbox=lab.bbox,
                        region=(gx0, top_of[id(lab)], gx1, bottom),
                    )
                )
    cells.sort(key=lambda c: c.label)
    return cells


def _column_bounds(d: QuestionDraft, si: int) -> Box:
    seg = d.segments[si]
    return seg.rect[0] - 4, seg.rect[1], seg.rect[2] + 4, seg.rect[3]


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------


def _group_visuals(
    visuals: list[Item], texts: list[Item]
) -> list[tuple[Box, list[Item], int, int]]:
    """Merge visuals on the same row / touching, then absorb their labels.

    Returns (bbox, absorbed_text_items, page, col) per figure.
    """

    def close(a: Box, b: Box) -> bool:
        v_overlap = min(a[3], b[3]) - max(a[1], b[1])
        same_row = v_overlap > 0.5 * min(a[3] - a[1], b[3] - b[1])
        h_gap = max(a[0], b[0]) - min(a[2], b[2])
        v_gap = max(a[1], b[1]) - min(a[3], b[3])
        h_overlap = min(a[2], b[2]) - max(a[0], b[0])
        return (same_row and h_gap < 45) or (v_gap < 6 and h_overlap > -10)

    groups: list[list[Item]] = [
        [v] for v in sorted(visuals, key=lambda v: (v.page, v.col, v.y0, v.x0))
    ]
    merged = True
    while merged:  # merge until stable so chains of neighbours end up together
        merged = False
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                gi, gj = groups[i], groups[j]
                if gi[0].page != gj[0].page or gi[0].col != gj[0].col:
                    continue
                if close(
                    box_union([x.bbox for x in gi]), box_union([x.bbox for x in gj])
                ):
                    gi.extend(gj)
                    del groups[j]
                    merged = True
                    break
            if merged:
                break

    result = []
    for g in groups:
        box = box_union([x.bbox for x in g])
        absorbed: list[Item] = []
        for _ in range(3):
            grown = False
            for t in texts:
                if t in absorbed or t.page != g[0].page or t.col != g[0].col:
                    continue
                if (
                    OPTION_RE.match(t.text)
                    or ANCHOR_RE.match(t.text)
                    or SOLUTION_RE.match(t.text)
                ):
                    # A label like "(i)" is fine, but option/question markers stay text.
                    if not re.match(r"^\s*\(?[ivx]{1,4}\)", t.text, re.I):
                        continue
                inside = center_in(t.bbox, box_expand(box, 2))
                near = False
                if not inside and len(t.text) <= 28:
                    v_gap = max(box[1] - t.y1, t.y0 - box[3])
                    h_gap = max(box[0] - t.x1, t.x0 - box[2])
                    within_x = t.x0 >= box[0] - 14 and t.x1 <= box[2] + 14
                    within_y = t.y0 >= box[1] - 6 and t.y1 <= box[3] + 6
                    # Beside the figure only short labels ("P", "+q", "(ii)")
                    # belong to it; running words like "is" stay in the text.
                    label_like = len(t.text) <= 6 and not re.fullmatch(
                        r"[a-z]{2,}[.,?:]?", t.text.strip()
                    )
                    near = (v_gap <= 8 and within_x) or (
                        h_gap <= 10 and within_y and label_like
                    )
                if inside or near:
                    absorbed.append(t)
                    box = box_union([box, t.bbox])
                    grown = True
            if not grown:
                break
        result.append((box, absorbed, g[0].page, g[0].col))
    return result


_BOND_RE = re.compile(r"^[\s|‖∥=≡]*[|‖∥][\s|‖∥=≡]*$")
_synthetic_uid = [-1]


def _text_art_visuals(texts: list[Item]) -> list[Item]:
    """Structural formulae typed with "|" / "||" bond lines, as figure items.

    Text like "CH3 − CH − C − NH" over "|  ||  |" over "CH3 O  Br" cannot be
    transcribed faithfully, so the whole stacked block is cropped as a figure.
    """
    bonds = [t for t in texts if _BOND_RE.match(t.text)]
    used: set[int] = set()
    out: list[Item] = []
    for b in bonds:
        if b.uid in used:
            continue
        box = b.bbox
        members = [b]
        for _ in range(6):
            grown = False
            for t in texts:
                if t in members or _starts_structure(t) or len(t.text) > 40:
                    continue
                v_gap = max(box[1] - t.y1, t.y0 - box[3])
                h_overlap = min(box[2] + 4, t.x1) - max(box[0] - 4, t.x0)
                if v_gap <= 4 and h_overlap > 0.3 * max(1.0, t.width):
                    members.append(t)
                    box = box_union([box, t.bbox])
                    grown = True
            if not grown:
                break
        if len(members) < 3:
            continue
        used.update(m.uid for m in members)
        _synthetic_uid[0] -= 1
        out.append(
            Item(
                uid=_synthetic_uid[0],
                page=b.page,
                kind="vector",
                bbox=box,
                col=b.col,
                is_figure=True,
            )
        )
    return out


def _build_figures(d: QuestionDraft) -> list[Figure]:
    figures: list[Figure] = []

    def make(
        part: str, items: list[Item], option: str | None, prefix: str
    ) -> list[Item]:
        texts = [it for it in items if it.kind == "text"]
        visuals = [
            it for it in items if it.is_visual and it.is_figure
        ] + _text_art_visuals(texts)
        if not visuals:
            return []
        absorbed_all: list[Item] = []
        for idx, (box, absorbed, page, _col) in enumerate(
            _group_visuals(visuals, texts), start=1
        ):
            fid = f"{prefix}{idx}"
            fig = Figure(id=fid, page=page, bbox=box, part=part, option=option)  # type: ignore[arg-type]
            row_text = [
                t
                for t in texts
                if t not in absorbed
                and t.page == page
                and min(t.y1, box[3]) - max(t.y0, box[1]) > 0.5 * t.height
                and (t.x1 < box[0] or t.x0 > box[2])
            ]
            if row_text and (box[3] - box[1]) < 90:
                fig.layout = "inline"
            figures.append(fig)
            absorbed_all.extend(absorbed)
        return absorbed_all

    absorbed = make("stem", d.stem_items, None, "F")
    d.stem_items = [it for it in d.stem_items if it not in absorbed]
    for cell in d.options:
        absorbed = make("option", cell.items, cell.label, f"{cell.label}")
        cell.items = [it for it in cell.items if it not in absorbed]
    absorbed = make("solution", d.solution_items, None, "S")
    d.solution_items = [it for it in d.solution_items if it not in absorbed]
    return figures
