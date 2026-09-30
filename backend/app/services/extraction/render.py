"""Render crops of questions, options, solutions and figures to PNG."""

from __future__ import annotations

import io
import logging
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .models import (
    Box,
    Figure,
    Item,
    PageLayout,
    box_expand,
    box_intersection,
    box_union,
)

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    import fitz  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

DISPLAY_ZOOM = 3.0  # 216 dpi: sharp on phones and projectors
LLM_ZOOM = 2.0  # 144 dpi: legible subscripts at a modest token cost

# q <rotated cm> <grey fill/stroke> BT ... ET Q  -> diagonal text watermark.
_WATERMARK_BLOCK = re.compile(
    rb"q\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+-?[\d.]+\s+-?[\d.]+\s+cm\s+"
    rb"((?:(?:-?[\d.]+\s+){1,4}(?:g|G|rg|RG|k|K|sc|SC|scn|SCN)\s+|/\w+\s+(?:cs|CS|gs)\s+)*)"
    rb"BT\b.*?\bET\s+Q",
    re.S,
)


def _is_watermark(match: re.Match[bytes]) -> bool:
    a, b, c, d = (float(x) for x in match.groups()[:4])
    if abs(b) < 0.05 or abs(c) < 0.05:
        return False  # not rotated
    colours = [float(v) for v in re.findall(rb"(-?[\d.]+)\s+[gG]\b", match.group(5))]
    return any(0.45 <= v <= 0.97 for v in colours)


def open_for_render(pdf_path: str | Path):
    """Open a copy of the PDF with diagonal text watermarks removed."""
    doc = fitz.open(pdf_path)
    removed = 0
    for page in doc:
        try:
            page.clean_contents()
            xrefs = list(page.get_contents())
            xrefs += [x[0] for x in page.get_xobjects()]
        except Exception:  # pragma: no cover
            continue
        for xref in xrefs:
            try:
                stream = doc.xref_stream(xref)
            except Exception:
                continue
            if not stream or b"BT" not in stream:
                continue
            new = _WATERMARK_BLOCK.sub(
                lambda m: b"" if _is_watermark(m) else m.group(0), stream
            )
            if new != stream:
                doc.update_stream(xref, new)
                removed += 1
    if removed:
        logger.info("Removed %s watermark block(s) before rendering", removed)
    return doc


def render_region(
    doc,
    page_index: int,
    rect: Box,
    zoom: float,
    erase: list[Box] | None = None,
    masks: list[tuple[Box, str]] | None = None,
    grayscale: bool = False,
) -> Image.Image:
    """Render `rect`, whiting out `erase` boxes and drawing labelled `masks`."""
    page = doc[page_index]
    clip = fitz.Rect(rect) & page.rect
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, alpha=False)
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    draw = ImageDraw.Draw(img)

    def to_px(b: Box) -> tuple[float, float, float, float]:
        return (
            (b[0] - clip.x0) * zoom,
            (b[1] - clip.y0) * zoom,
            (b[2] - clip.x0) * zoom,
            (b[3] - clip.y0) * zoom,
        )

    for b in erase or []:
        draw.rectangle(to_px(b), fill="white")
    for b, label in masks or []:
        box = to_px(b)
        draw.rectangle(
            box, fill=(238, 242, 255), outline=(37, 99, 235), width=max(1, int(zoom))
        )
        font = _font(int(9 * zoom))
        tw = draw.textlength(label, font=font)
        cx = (box[0] + box[2]) / 2 - tw / 2
        cy = (box[1] + box[3]) / 2 - 6 * zoom
        draw.text(
            (max(box[0] + 2, cx), max(box[1] + 1, cy)),
            label,
            fill=(30, 64, 175),
            font=font,
        )
    if grayscale:
        img = ImageOps.grayscale(img).convert("RGB")
    return img


_FONT_CACHE: dict[int, ImageFont.ImageFont] = {}


def _font(size: int):
    if size not in _FONT_CACHE:
        font = None
        for name in (
            "DejaVuSans-Bold.ttf",
            "arialbd.ttf",
            "Arial Bold.ttf",
            "LiberationSans-Bold.ttf",
        ):
            try:
                font = ImageFont.truetype(name, size)
                break
            except OSError:
                continue
        _FONT_CACHE[size] = font or ImageFont.load_default()
    return _FONT_CACHE[size]


def stack(images: list[Image.Image], gap: int = 12) -> Image.Image:
    if len(images) == 1:
        return images[0]
    width = max(i.width for i in images)
    height = sum(i.height for i in images) + gap * (len(images) - 1)
    out = Image.new("RGB", (width, height), "white")
    y = 0
    for i in images:
        out.paste(i, (0, y))
        y += i.height + gap
    return out


def trim_whitespace(img: Image.Image, pad: int = 6) -> Image.Image:
    gray = ImageOps.grayscale(img)
    bbox = ImageOps.invert(gray).point(lambda v: 255 if v > 24 else 0).getbbox()
    if not bbox:
        return img
    x0, y0, x1, y1 = bbox
    return img.crop(
        (
            max(0, x0 - pad),
            max(0, y0 - pad),
            min(img.width, x1 + pad),
            min(img.height, y1 + pad),
        )
    )


def to_png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def part_regions(
    items: list[Item], layouts: list[PageLayout], pad: float = 3.0
) -> list[tuple[int, int, Box]]:
    """Group items by (page, column) in reading order; one rect per group."""
    groups: dict[tuple[int, int], list[Item]] = {}
    order: list[tuple[int, int]] = []
    for it in items:
        key = (it.page, it.col)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(it)
    regions: list[tuple[int, int, Box]] = []
    for key in sorted(order):
        page, col = key
        lay = layouts[page]
        col_rect = next((c.rect for c in lay.columns if c.index == col), lay.rect)
        b = box_union([it.bbox for it in groups[key]])
        b = (
            max(col_rect[0] + 0.5, b[0] - pad),
            max(col_rect[1], b[1] - pad),
            min(col_rect[2] - 0.5, b[2] + pad),
            min(col_rect[3], b[3] + pad),
        )
        regions.append((page, col, b))
    return regions


def foreign_boxes(layout: PageLayout, rect: Box, owned: set[int]) -> list[Box]:
    """Boxes of other questions' content that intrude into `rect`."""
    out: list[Box] = []
    owned_boxes = [it.bbox for it in layout.items if it.uid in owned]
    for it in layout.items:
        if it.uid in owned:
            continue
        if box_intersection(it.bbox, rect) <= 0:
            continue
        # Never erase something that sits on top of our own content.
        if any(
            box_intersection(it.bbox, ob)
            > 0.5 * max(1.0, (it.x1 - it.x0) * (it.y1 - it.y0))
            for ob in owned_boxes
        ):
            continue
        out.append(box_expand(it.bbox, 0.6))
    return out


def render_figure(
    doc, layouts: list[PageLayout], fig: Figure, owned: set[int], grayscale: bool
) -> Image.Image:
    lay = layouts[fig.page]
    rect = box_expand(fig.bbox, 2.5)
    img = render_region(
        doc,
        fig.page,
        rect,
        DISPLAY_ZOOM,
        erase=foreign_boxes(lay, rect, owned),
        grayscale=grayscale,
    )
    return trim_whitespace(img, pad=8)
