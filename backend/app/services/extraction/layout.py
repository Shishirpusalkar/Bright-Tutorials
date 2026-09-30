"""Page layout analysis: columns, text lines, figures and page chrome.

Everything here is deterministic geometry from the PDF itself, so it costs
nothing and never hallucinates. The output is a list of PageLayout objects
whose items are already assigned to a column and stripped of watermarks,
running headers/footers, page numbers and title blocks.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict

from .models import (
    Box,
    Column,
    Item,
    Marker,
    PageLayout,
    Span,
    box_area,
    box_intersection,
    box_union,
)

try:  # PyMuPDF >= 1.24 exposes the "pymupdf" name; older builds only "fitz".
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    import fitz  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

SUBJECT_ALIASES = {
    "physics": "Physics",
    "chemistry": "Chemistry",
    "mathematics": "Mathematics",
    "maths": "Mathematics",
    "math": "Mathematics",
    "biology": "Biology",
    "botany": "Biology",
    "zoology": "Biology",
}
_SUBJECT_WORD = r"(physics|chemistry|mathematics|maths?|biology|botany|zoology)"
SUBJECT_RE = re.compile(rf"\b{_SUBJECT_WORD}\b", re.I)
SECTION_RE = re.compile(r"\bsection\s*[-:]?\s*[\[\(]?\s*([A-Z])\b(?!\w)", re.I)
TYPE_RE = re.compile(
    r"\(\s*(MCQ|SCQ|MSQ|NUMERIC(?:AL)?|INTEGER|NAT|ASSERTION[\s\-]*REASON(?:ING)?)\s*\)",
    re.I,
)
HEADER_KEY_RE = re.compile(
    r"^\s*(subject|standard|std\b|total\s*marks?|paper\s*set|date|time|chapters?|"
    r"max(?:imum)?\s*marks?|duration|roll\s*no|name\s*of)",
    re.I,
)
INSTRUCTION_RE = re.compile(
    r"\[\s*each\s+carr(?:y|ies)|each\s+(?:question\s+)?carr(?:y|ies)\s+\d+\s*marks?",
    re.I,
)
PAGE_NUMBER_RE = re.compile(
    r"^\s*(?:page\s*)?\d{1,3}(?:\s*(?:of|/)\s*\d{1,3})?\s*$", re.I
)

MATH_FONT_RE = re.compile(
    r"(^|\+)(CM(MI|SY|EX|BSY|MIB)|MSAM|MSBM|Symbol|MT-?Extra|MTSY|Math|STIX|Euclid|"
    r"Mathematical|Cambria.?Math|LatinModernMath|Asana)",
    re.I,
)


def luminance(color: int | tuple | list | None) -> float:
    if color is None:
        return 0.0
    if isinstance(color, int):
        r = ((color >> 16) & 255) / 255
        g = ((color >> 8) & 255) / 255
        b = (color & 255) / 255
    else:
        vals = list(color)
        if len(vals) == 1:
            return float(vals[0])
        if len(vals) == 4:  # CMYK
            c, m, y, k = vals
            r, g, b = (1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k)
        else:
            r, g, b = vals[:3]
    return 0.299 * r + 0.587 * g + 0.114 * b


def normalize_subject(value: str | None) -> str | None:
    if not value:
        return None
    return SUBJECT_ALIASES.get(value.strip().lower(), value.strip().title())


def _norm_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _in_chrome_zone(bbox: Box, page_height: float) -> bool:
    """Top/bottom strip where running headers, footers and page numbers live."""
    return bbox[3] < 0.075 * page_height or bbox[1] > 0.925 * page_height


# ---------------------------------------------------------------------------
# Raw extraction
# ---------------------------------------------------------------------------


def _raw_spans(page) -> list[tuple[Box, list[Span]]]:
    """Horizontal, non-watermark text lines as (bbox, spans)."""
    flags = fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES
    data = page.get_text("dict", flags=flags)
    page_rect = page.rect
    lines: list[tuple[Box, list[Span]]] = []
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            dx, dy = line.get("dir", (1, 0))
            if dx < 0.99 or abs(dy) > 0.02:
                continue  # rotated text: diagonal watermarks, vertical labels
            spans: list[Span] = []
            for s in line.get("spans", []):
                text = s.get("text", "")
                if not text.strip():
                    continue
                size = float(s.get("size", 0))
                color = int(s.get("color", 0))
                if size >= 20 and luminance(color) > 0.6:
                    continue  # large light-grey text = watermark
                x0, y0, x1, y1 = s["bbox"]
                if x1 <= page_rect.x0 or x0 >= page_rect.x1:
                    continue
                if y1 <= page_rect.y0 or y0 >= page_rect.y1:
                    continue
                spans.append(
                    Span(
                        text=text,
                        bbox=(x0, y0, x1, y1),
                        font=str(s.get("font", "")),
                        size=size,
                        color=color,
                    )
                )
            if spans:
                lines.append((box_union([s.bbox for s in spans]), spans))
    return lines


_LEAD_OPTION_RE = re.compile(r"^\s*\(([A-Da-d])\)")
_INLINE_OPTION_RE = re.compile(r"(?<=\s)\(([B-Db-d])\)(?=\s)")


def _split_inline_options(spans: list[Span]) -> list[list[Span]]:
    """Split "(C) foo (D) bar" printed as one line into one line per option.

    Only splits when the line itself starts with an option label, the next
    label is the following letter, and the part before it has content.
    """
    text = "".join(s.text for s in spans)
    lead = _LEAD_OPTION_RE.match(text)
    if not lead:
        return [spans]
    # Labels printed as their own spans: split at span boundaries.
    expected = chr(ord(lead.group(1).upper()) + 1)
    groups: list[list[Span]] = [[spans[0]]]
    for s in spans[1:]:
        m = _LEAD_OPTION_RE.match(s.text)
        before = "".join(x.text for x in groups[-1])
        has_content = bool(_LEAD_OPTION_RE.sub("", before, count=1).strip())
        if (
            m
            and m.group(1).upper() == expected
            and has_content
            and s.bbox[0] - groups[-1][-1].bbox[2] > 2
        ):
            groups.append([s])
            expected = chr(ord(expected) + 1)
        else:
            groups[-1].append(s)
    if len(groups) > 1:
        return groups
    # Flatten to characters with estimated x positions.
    chars: list[tuple[str, Span, float, float]] = []
    for s in spans:
        n = max(1, len(s.text))
        w = (s.bbox[2] - s.bbox[0]) / n
        for i, ch in enumerate(s.text):
            chars.append((ch, s, s.bbox[0] + i * w, s.bbox[0] + (i + 1) * w))
    flat = "".join(c[0] for c in chars)
    cuts: list[int] = []
    expected = chr(ord(lead.group(1).upper()) + 1)
    last_cut = lead.end()
    for m in _INLINE_OPTION_RE.finditer(flat):
        if m.group(1).upper() != expected or not flat[last_cut : m.start()].strip():
            continue
        cuts.append(m.start())
        last_cut = m.end()
        expected = chr(ord(expected) + 1)
    if not cuts:
        return [spans]
    pieces: list[list[Span]] = []
    bounds = [0] + cuts + [len(chars)]
    for a, b in zip(bounds, bounds[1:], strict=False):
        seg = chars[a:b]
        seg_text = "".join(c[0] for c in seg).strip()
        if not seg_text:
            continue
        ref = seg[0][1]
        pieces.append(
            [
                Span(
                    text=seg_text,
                    bbox=(seg[0][2], ref.bbox[1], seg[-1][3], ref.bbox[3]),
                    font=ref.font,
                    size=ref.size,
                    color=ref.color,
                )
            ]
        )
    return pieces


def _line_text(spans: list[Span]) -> str:
    out = ""
    prev: Span | None = None
    for s in spans:
        if (
            prev is not None
            and s.bbox[0] - prev.bbox[2] > 1.5
            and not out.endswith(" ")
        ):
            out += " "
        out += s.text
        prev = s
    return re.sub(r"\s+", " ", out).strip()


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------


def _detect_split(
    page, text_boxes: list[Box], drawings: list[dict]
) -> tuple[float | None, float]:
    """Return (split_x, divider_top). split_x is None for single-column pages."""
    W, H = page.rect.width, page.rect.height
    best = None
    for d in drawings:
        r = d["rect"]
        if r.width < 3 and r.height > 0.35 * H and 0.3 * W < r.x0 < 0.7 * W:
            if best is None or r.height > best.height:
                best = r
    if best is not None:
        return (best.x0 + best.x1) / 2, best.y0

    body = [b for b in text_boxes if b[1] > 0.15 * H and b[3] < 0.93 * H]
    if len(body) < 12:
        return None, 0.0
    best_x, best_cross = None, None
    for x in range(int(0.35 * W), int(0.65 * W), 2):
        cross = sum(1 for b in body if b[0] < x - 1 and b[2] > x + 1)
        if best_cross is None or cross < best_cross:
            best_x, best_cross = x, cross
    assert best_x is not None and best_cross is not None
    left = sum(1 for b in body if b[2] <= best_x)
    right = sum(1 for b in body if b[0] >= best_x)
    if left >= 6 and right >= 6 and best_cross <= max(1, 0.03 * len(body)):
        # Centre the split in the empty gutter.
        lo = max((b[2] for b in body if b[2] <= best_x), default=best_x)
        hi = min((b[0] for b in body if b[0] >= best_x), default=best_x)
        return (lo + hi) / 2, 0.0
    return None, 0.0


# ---------------------------------------------------------------------------
# Vector figures
# ---------------------------------------------------------------------------


def _drawing_color_lum(d: dict) -> float:
    col = d.get("color") if d.get("color") is not None else d.get("fill")
    return luminance(col)


def _is_structural(d: dict, page_rect, split_x: float | None) -> bool:
    r = d["rect"]
    W, H = page_rect.width, page_rect.height
    if r.is_empty and (r.width == 0 and r.height == 0):
        return True
    if r.width > 0.4 * W and r.height > 0.4 * H:
        return True  # page frame / full-page watermark
    if r.width < 3 and r.height > 0.35 * H:
        return True  # column divider
    col_w = (W / 2) if split_x else W
    if r.height < 2.5 and r.width > 0.75 * col_w:
        return True  # horizontal rule across the column
    fill = d.get("fill")
    stroke = d.get("color")
    if fill is not None and stroke is None and luminance(fill) > 0.85:
        return True  # light background shading / white masks
    if (
        len(d.get("items", [])) > 60
        and box_area(tuple(r)) > 0.04 * W * H
        and 0.35 < _drawing_color_lum(d) < 0.95
    ):
        return True  # vector-outlined grey watermark
    return False


def _segment_kinds(d: dict) -> tuple[bool, bool, int]:
    """(has_curve, has_diagonal, n_segments)."""
    has_curve = False
    has_diag = False
    n = 0
    for it in d.get("items", []):
        op = it[0]
        n += 1
        if op == "c":
            has_curve = True
        elif op == "l":
            p1, p2 = it[1], it[2]
            if abs(p1.x - p2.x) > 1.0 and abs(p1.y - p2.y) > 1.0:
                has_diag = True
        elif op == "qu":
            has_diag = True
    return has_curve, has_diag, n


class _DSU:
    def __init__(self, n: int):
        self.p = list(range(n))

    def find(self, a: int) -> int:
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def _vector_clusters(
    drawings: list[dict], page_rect, split_x: float | None, text_boxes: list[Box]
) -> list[tuple[Box, bool]]:
    """Cluster drawings into candidate figures. Returns (bbox, is_figure)."""
    kept: list[tuple[Box, bool, bool, int]] = []
    for d in drawings:
        if _is_structural(d, page_rect, split_x):
            continue
        r = d["rect"] & page_rect
        if r.is_empty and r.width == 0 and r.height == 0:
            continue
        curve, diag, n = _segment_kinds(d)
        kept.append(((r.x0, r.y0, r.x1, r.y1), curve, diag, n))
    if not kept:
        return []

    tol = 3.0
    dsu = _DSU(len(kept))
    order = sorted(range(len(kept)), key=lambda i: kept[i][0][1])
    for oi, i in enumerate(order):
        bi = kept[i][0]
        for j in order[oi + 1 :]:
            bj = kept[j][0]
            if bj[1] > bi[3] + tol:
                break
            same_side = split_x is None or (
                ((bi[0] + bi[2]) / 2 < split_x) == ((bj[0] + bj[2]) / 2 < split_x)
            )
            if (
                same_side
                and bj[0] <= bi[2] + tol
                and bi[0] <= bj[2] + tol
                and bj[1] <= bi[3] + tol
                and bi[1] <= bj[3] + tol
            ):
                dsu.union(i, j)

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(len(kept)):
        groups[dsu.find(i)].append(i)

    clusters: list[tuple[Box, bool]] = []
    for members in groups.values():
        bbox = box_union([kept[i][0] for i in members])
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if w < 12 or h < 8 or w * h < 220:
            continue
        curve = any(kept[i][1] for i in members)
        diag = any(kept[i][2] for i in members)
        nseg = sum(kept[i][3] for i in members)
        area = max(1.0, w * h)
        text_cov = sum(box_intersection(bbox, tb) for tb in text_boxes) / area
        if curve or diag:
            is_fig = text_cov < 0.45 and nseg >= 2
        else:
            # Axis-aligned only: circuits/graph axes vs. tables/boxes around text.
            is_fig = text_cov < 0.12 and nseg >= 4
        clusters.append((bbox, is_fig))
    return clusters


# ---------------------------------------------------------------------------
# Scanned pages (no text layer)
# ---------------------------------------------------------------------------


def _raster_items(page, split_hint: float | None) -> tuple[list[Item], float | None]:
    """Detect text rows on a scanned page with projection profiles."""
    import numpy as np

    scale = 1.5
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csGRAY)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    ink = img < 140
    Hpx, Wpx = ink.shape

    # Page frames and column dividers put ink on every row; remove long
    # vertical/horizontal rules before taking projection profiles.
    col_frac = ink.mean(axis=0)
    rule_cols = np.where(col_frac > 0.35)[0]
    split_px = None
    if split_hint is not None:
        split_px = int(split_hint * scale)
    else:
        central = [c for c in rule_cols if 0.3 * Wpx < c < 0.7 * Wpx]
        if central:
            split_px = int(np.median(central))
    ink = ink.copy()
    for c in rule_cols:
        ink[:, max(0, c - 2) : c + 3] = False
    row_frac = ink.mean(axis=1)
    rule_rows = np.where(row_frac > 0.5)[0]
    ink[row_frac > 0.5, :] = False
    # A full-width rule in the top third closes the title block
    # (Subject / Standard / Paper Set ...): ignore everything above it.
    header_rules = [r for r in rule_rows if r < 0.35 * Hpx]
    content_top_px = int(max(header_rules)) + 2 if header_rules else 0
    ink[:content_top_px, :] = False
    if split_px is None:
        col_ink = ink[int(0.12 * Hpx) : int(0.95 * Hpx)].mean(axis=0)
        lo, hi = int(0.35 * Wpx), int(0.65 * Wpx)
        window = col_ink[lo:hi]
        if len(window) and window.min() < 0.002:
            # Widest empty gutter near the centre.
            empty = window < 0.002
            best, best_len, i = None, 0, 0
            while i < len(empty):
                if empty[i]:
                    j = i
                    while j < len(empty) and empty[j]:
                        j += 1
                    if j - i > best_len:
                        best, best_len = (i + j) // 2, j - i
                    i = j
                else:
                    i += 1
            if best is not None and best_len >= 6:
                split_px = lo + best

    cols = [(0, split_px), (split_px, Wpx)] if split_px else [(0, Wpx)]
    items: list[Item] = []
    uid = 0
    for ci, (cx0, cx1) in enumerate(cols):
        band = ink[:, cx0 + 3 : cx1 - 3] if split_px else ink[:, cx0:cx1]
        rows = band.mean(axis=1) > 0.003
        y = 0
        runs: list[tuple[int, int]] = []
        while y < Hpx:
            if rows[y]:
                start = y
                while y < Hpx and rows[y]:
                    y += 1
                runs.append((start, y))
            y += 1
        merged: list[list[int]] = []
        for a, b in runs:
            if merged and a - merged[-1][1] <= 2:
                merged[-1][1] = b
            else:
                merged.append([a, b])
        for a, b in merged:
            if b - a < 4:
                continue
            row = band[a:b]
            xs = np.where(row.any(axis=0))[0]
            if not len(xs):
                continue
            off = cx0 + 3 if split_px else cx0
            bbox = (
                (off + xs[0]) / scale,
                a / scale,
                (off + xs[-1] + 1) / scale,
                b / scale,
            )
            items.append(
                Item(uid=uid, page=page.number, kind="raster_text", bbox=bbox, col=ci)
            )
            uid += 1
    return items, (split_px / scale if split_px else None)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_document(doc) -> list[PageLayout]:
    n_pages = len(doc)
    raw: list[list[tuple[Box, list[Span]]]] = []
    for page in doc:
        try:
            raw.append(_raw_spans(page))
        except Exception as exc:  # pragma: no cover - corrupt page
            logger.warning(
                "Text extraction failed on page %s: %s", page.number + 1, exc
            )
            raw.append([])

    # Running headers/footers: same text near the top/bottom on many pages.
    repeat_pages: dict[str, set[int]] = defaultdict(set)
    for pi, lines in enumerate(raw):
        H = doc[pi].rect.height
        for bbox, spans in lines:
            if _in_chrome_zone(bbox, H):
                key = _norm_key(_line_text(spans))
                # Short keys ("a" from "(A)", "1") are content, not headers.
                if len(key) >= 4 and not key.isdigit():
                    repeat_pages[key].add(pi)
    repeat_threshold = max(3, int(0.3 * n_pages))
    running = {k for k, v in repeat_pages.items() if len(v) >= repeat_threshold}

    # Logos: the same image placed at the same spot on several pages.
    image_spots: dict[tuple, set[int]] = defaultdict(set)
    page_images: list[list[dict]] = []
    for page in doc:
        try:
            infos = page.get_image_info(xrefs=True)
        except Exception:  # pragma: no cover
            infos = []
        page_images.append(infos)
        for info in infos:
            b = info["bbox"]
            image_spots[(round(b[0]), round(b[1]), round(b[2]), round(b[3]))].add(
                page.number
            )

    layouts: list[PageLayout] = []
    for page in doc:
        layouts.append(
            _analyze_page(
                page, raw[page.number], running, page_images[page.number], image_spots
            )
        )
    return layouts


def _analyze_page(
    page, raw_lines, running: set[str], images: list[dict], image_spots
) -> PageLayout:
    pi = page.number
    prect = page.rect
    W, H = prect.width, prect.height
    try:
        drawings = page.get_drawings()
    except Exception:  # pragma: no cover
        drawings = []

    text_chars = sum(len(s.text.strip()) for _, spans in raw_lines for s in spans)
    big_images = [i for i in images if box_area(tuple(i["bbox"])) > 0.45 * W * H]
    is_scanned = bool(big_images) and text_chars < 60

    split_x, divider_top = _detect_split(page, [b for b, _ in raw_lines], drawings)
    if is_scanned:
        items, split_x = _raster_items(page, split_x)
        columns = _columns(pi, prect, split_x)
        return PageLayout(
            index=pi,
            rect=(prect.x0, prect.y0, prect.x1, prect.y1),
            columns=columns,
            items=items,
            markers=[],
            content_top=0.04 * H,
            content_bottom=0.97 * H,
            is_scanned=True,
        )

    columns = _columns(pi, prect, split_x)

    def col_of(b: Box) -> int:
        if split_x is None:
            return 0
        return 0 if (b[0] + b[2]) / 2 < split_x else 1

    # --- text lines, split per column --------------------------------------
    uid = 0
    items: list[Item] = []
    markers: list[Marker] = []
    header_lines: list[Box] = []
    spanning: list[Box] = []
    for bbox, spans in raw_lines:
        groups: dict[int, list[Span]] = defaultdict(list)
        crosses = (
            split_x is not None and bbox[0] < split_x - 6 and bbox[2] > split_x + 6
        )
        if crosses and any(
            s.bbox[0] < split_x - 6 and s.bbox[2] > split_x + 6 for s in spans
        ):
            spanning.append(bbox)
            groups[-1] = spans
        else:
            for s in spans:
                groups[col_of(s.bbox)].append(s)
        pieces_by_col = [
            (col, piece)
            for col, gsp in groups.items()
            for piece in _split_inline_options(gsp)
        ]
        for col, gspans in pieces_by_col:
            text = _line_text(gspans)
            if not text:
                continue
            gbox = box_union([s.bbox for s in gspans])
            key = _norm_key(text)
            if key in running and _in_chrome_zone(gbox, H):
                continue
            if PAGE_NUMBER_RE.match(text) and (gbox[1] > 0.9 * H or gbox[3] < 0.08 * H):
                continue
            if HEADER_KEY_RE.match(text) and gbox[3] < 0.3 * H:
                header_lines.append(gbox)
            items.append(
                Item(
                    uid=uid,
                    page=pi,
                    kind="text",
                    bbox=gbox,
                    col=max(col, 0),
                    text=text,
                    spans=gspans,
                )
            )
            if col == -1:
                items[-1].col = col_of(gbox)
            uid += 1

    # --- page title block (Subject / Standard / Date / Time ...) -----------
    content_top = prect.y0
    has_header_block = len(header_lines) >= 3
    if has_header_block:
        block_bottom = max(b[3] for b in header_lines)
        content_top = block_bottom + 1
        # Full-width title lines just below the key/value block belong to it.
        for b in spanning:
            if b[1] <= block_bottom + 25:
                content_top = max(content_top, b[3] + 1)
    if split_x is not None and divider_top > 0.08 * H:
        # Columns start where the divider starts; above it is page chrome.
        content_top = max(content_top, divider_top - 18)

    kept: list[Item] = []
    for it in items:
        if it.y1 <= content_top + 0.5:
            continue
        kept.append(it)
    items = kept

    # --- structural markers --------------------------------------------------
    body: list[Item] = []
    for it in items:
        marker = _classify_marker(it)
        if marker is not None:
            markers.append(marker)
            continue
        body.append(it)
    items = body
    if has_header_block:
        markers.append(Marker(kind="header_block", page=pi, col=0, y=content_top))

    text_boxes = [it.bbox for it in items]

    # --- images ----------------------------------------------------------------
    col_width = (split_x - prect.x0) if split_x else W

    def is_strip(b) -> bool:
        w, h = b[2] - b[0], b[3] - b[1]
        return w >= 0.8 * col_width and h <= 45 and w / max(h, 1) >= 6

    # Pages that store each line of text as a picture have many such strips;
    # a single wide, short picture elsewhere is a real figure (a reaction).
    # Pages that are mostly pictures with almost no text layer are treated
    # the same way: their "images" are the question text itself.
    image_area = sum(box_area(tuple(i["bbox"])) for i in images)
    strip_page = sum(1 for info in images if is_strip(tuple(info["bbox"]))) >= 4 or (
        len(images) >= 4 and text_chars < 400 and image_area > 0.25 * W * H
    )
    if strip_page and text_chars < 400 and image_area > 0.25 * W * H:
        is_strip = lambda b: True  # noqa: E731
    for info in images:
        b = tuple(info["bbox"])
        b = (
            max(b[0], prect.x0),
            max(b[1], prect.y0),
            min(b[2], prect.x1),
            min(b[3], prect.y1),
        )
        w, h = b[2] - b[0], b[3] - b[1]
        if w < 4 or h < 4:
            continue
        spot = (
            round(info["bbox"][0]),
            round(info["bbox"][1]),
            round(info["bbox"][2]),
            round(info["bbox"][3]),
        )
        if len(image_spots.get(spot, ())) >= 3 and (b[3] < 0.15 * H or b[1] > 0.88 * H):
            continue  # repeated logo
        if b[3] <= content_top + 0.5:
            continue
        kind = "image"
        if (strip_page and is_strip(b)) or h < 12:
            kind = "raster_text"  # a line of text stored as a picture
        items.append(
            Item(
                uid=uid,
                page=pi,
                kind=kind,
                bbox=b,
                col=col_of(b),
                is_figure=kind == "image",
            )
        )
        uid += 1

    # --- vector drawings -----------------------------------------------------
    for bbox, is_fig in _vector_clusters(drawings, prect, split_x, text_boxes):
        if bbox[3] <= content_top + 0.5 or not is_fig:
            continue
        items.append(
            Item(
                uid=uid,
                page=pi,
                kind="vector",
                bbox=bbox,
                col=col_of(bbox),
                is_figure=True,
            )
        )
        uid += 1

    items.sort(key=lambda it: (it.col, it.y0, it.x0))
    answer_key = parse_answer_key(items)
    if answer_key:
        # A key/table page: its "12." cells must not become questions.
        items = []
    return PageLayout(
        index=pi,
        rect=(prect.x0, prect.y0, prect.x1, prect.y1),
        columns=columns,
        items=items,
        markers=markers,
        content_top=content_top,
        content_bottom=prect.y1,
        is_scanned=False,
        has_header_block=has_header_block,
        answer_key=answer_key,
    )


_KEY_NUM_RE = re.compile(r"^\(?(\d{1,3})\s*[\.\)\-:]?\)?$")
_KEY_ANS_RE = re.compile(r"^\(?([A-Da-d](?:\s*,\s*[A-Da-d])*|[-+]?\d+(?:\.\d+)?|-)\)?$")
_KEY_INLINE_RE = re.compile(
    r"(?<![\w.])(\d{1,3})\s*[\.\):\-]\s*\(?([A-Da-d](?:\s*,\s*[A-Da-d])*)\)?(?![\w])"
)
_KEY_SECTION_RE = re.compile(r"section\s*[\[\(]?\s*([A-Z])\b", re.I)


def parse_answer_key(items: list[Item]) -> list[tuple[int, int, str]]:
    """Detect an answer-key page and return (section_index, number, answer).

    Handles tables ("33. | B | ...") and inline keys ("1. (B) 2. (C) ...").
    A page counts as a key only if most of its rows are number/answer pairs.
    """
    texts = sorted(
        (it for it in items if it.kind == "text"), key=lambda it: (it.cy, it.x0)
    )
    if len(texts) < 16:
        return []
    rows: list[list[Item]] = []
    for it in texts:
        if rows and abs(rows[-1][0].cy - it.cy) < 3:
            rows[-1].append(it)
        else:
            rows.append([it])
    pairs: list[tuple[int, int, str]] = []
    section = 0
    pair_rows = 0
    for row in rows:
        row.sort(key=lambda it: it.x0)
        joined = " ".join(it.text for it in row)
        if _KEY_SECTION_RE.search(joined) and not _KEY_NUM_RE.match(row[0].text):
            section += 1 if pairs else 0
            continue
        found = False
        for a, b in zip(row, row[1:], strict=False):
            m1, m2 = (
                _KEY_NUM_RE.match(a.text.strip()),
                _KEY_ANS_RE.match(b.text.strip()),
            )
            if m1 and m2 and b.x0 - a.x1 < 120:
                pairs.append((section, int(m1.group(1)), m2.group(1).upper()))
                found = True
                break
        if not found:
            inline = _KEY_INLINE_RE.findall(joined)
            if len(inline) >= 2:
                for num, ans in inline:
                    pairs.append((section, int(num), ans.upper()))
                found = True
        if found:
            pair_rows += 1
    if pair_rows >= 8 and pair_rows >= 0.5 * len(rows):
        return pairs  # "-" entries (no key for that question) are skipped later
    return []


def _columns(pi: int, prect, split_x: float | None) -> list[Column]:
    if split_x is None:
        return [Column(page=pi, index=0, rect=(prect.x0, prect.y0, prect.x1, prect.y1))]
    return [
        Column(page=pi, index=0, rect=(prect.x0, prect.y0, split_x, prect.y1)),
        Column(page=pi, index=1, rect=(split_x, prect.y0, prect.x1, prect.y1)),
    ]


def _classify_marker(it: Item) -> Marker | None:
    text = it.text
    if len(text) > 110:
        return None
    if INSTRUCTION_RE.search(text):
        qtype = None
        if re.search(
            r"write\s+the\s+answer|answer\s+the\s+following|short\s+answer|long\s+answer|descriptive",
            text,
            re.I,
        ):
            qtype = "SUBJECTIVE"
        elif re.search(
            r"choose|correct\s+(?:answer|option)|multiple\s+choice", text, re.I
        ):
            qtype = "SCQ"
        return Marker(
            kind="instruction", page=it.page, col=it.col, y=it.y0, question_type=qtype
        )
    stripped = text.strip(" .:-_=*|\t")
    subj = SUBJECT_RE.search(stripped)
    sec = SECTION_RE.search(stripped)
    qtype = TYPE_RE.search(stripped)
    words = re.findall(r"[A-Za-z]+", stripped)
    if sec and (subj or qtype or len(words) <= 4):
        return Marker(
            kind="section",
            page=it.page,
            col=it.col,
            y=it.y0,
            subject=normalize_subject(subj.group(1)) if subj else None,
            section=f"Section {sec.group(1).upper()}",
            question_type=_normalize_type(qtype.group(1)) if qtype else None,
        )
    if subj and len(words) <= 3 and stripped.upper() == stripped and len(stripped) >= 4:
        # "PHYSICS", "PART A - CHEMISTRY"
        return Marker(
            kind="section",
            page=it.page,
            col=it.col,
            y=it.y0,
            subject=normalize_subject(subj.group(1)),
        )
    return None


def _normalize_type(value: str) -> str:
    v = value.upper()
    if v.startswith("NUMERIC") or v in ("NAT",):
        return "NUMERIC"
    if v == "INTEGER":
        return "INTEGER"
    if v == "MSQ":
        return "MCQ"
    if v.startswith("ASSERTION"):
        return "SCQ"
    return "SCQ" if v in ("MCQ", "SCQ") else v


def uses_math_fonts(items: list[Item]) -> bool:
    for it in items:
        for s in it.spans:
            if MATH_FONT_RE.search(s.font):
                return True
    return False
