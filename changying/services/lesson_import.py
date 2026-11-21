"""Plain-text extraction from a teacher's own lesson plan file (.docx / .pptx / .pdf / .txt / .md).

No XML parser is used on the (untrusted) Office files: the text runs are pulled out with regular expressions, so an
entity-expansion bomb has nothing to expand. The caller validates the zip container (size / entry limits) first.
"""

from __future__ import annotations

import base64
import html
import hashlib
import io
import re
import zipfile
from typing import Any

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TEXT_CHARS = 200000
MAX_PDF_PAGES = 60
MAX_SLIDES = 60
SUPPORTED = (".docx", ".pptx", ".pdf", ".txt", ".md")
# Figures travel to the model and then into a question's figure field, which caps a
# single data URL at 700k chars; keep a margin and a total budget per lesson.
MAX_FIGURES = 12
MAX_FIGURE_CHARS = 650_000
MAX_TOTAL_FIGURE_CHARS = 3_000_000


_RUN = re.compile(r"<(?:w|a):t(?:\s[^>]*)?>(.*?)</(?:w|a):t>", re.S)
_SLIDE_NO = re.compile(r"ppt/slides/slide(\d+)\.xml$")


def _runs(xml: str) -> list[str]:
    return [html.unescape(m).strip() for m in _RUN.findall(xml) if m.strip()]


def _docx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    paragraphs = [" ".join(_runs(p)) for p in xml.split("</w:p>")]
    return "\n".join(p for p in paragraphs if p)


def _pptx(data: bytes) -> list[str]:
    slides: list[tuple[int, str]] = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            m = _SLIDE_NO.search(name)
            if m:
                text = " ".join(_runs(z.read(name).decode("utf-8", "ignore")))
                if text:
                    slides.append((int(m.group(1)), text))
    if len(slides) > MAX_SLIDES:
        raise ValueError("PPT exceeds supported page count")
    return [t for _, t in sorted(slides)]


def _pdf(data: bytes) -> tuple[str, list[dict[str, Any]]]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    if len(reader.pages) > MAX_PDF_PAGES:
        raise ValueError("PDF exceeds supported page count")
    texts, figures = [], []
    for number, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        texts.append(page_text)
        # A page number alone is not enough when one page contains several questions.
        # Map an image only when its rendered position falls inside one unique numbered
        # question region. Unknown layouts deliberately keep question_no=None.
        regions = _pdf_question_regions(page, page_text)
        figures.extend(_pdf_page_figures(page, number, regions))
    return "\n".join(texts), figures


_PDF_QUESTION_HEADING = re.compile(r"第\s*(\d{1,3})\s*题")


def _pdf_question_regions(page: Any, page_text: str) -> list[dict[str, Any]]:
    """Return numbered question text blocks with their top-origin page coordinates."""
    if int(page.get("/Rotate") or 0) % 360:
        return []  # rotated-page coordinates need a separate transform
    lines: list[tuple[float, str]] = []
    try:
        chunks: list[tuple[float, float, str]] = []

        def collect(text: str, _cm: Any, tm: Any, _font: Any, _size: Any) -> None:
            if text and text.strip():
                chunks.append((float(tm[5]), float(tm[4]), text))

        page.extract_text(visitor_text=collect)
        # pypdf emits separate text runs for glyphs and style changes. Rejoin runs on
        # the same baseline before looking for a heading such as “第 7 题”.
        for y, x, value in sorted(chunks, key=lambda row: (row[0], row[1])):
            match = next((i for i, (line_y, _) in enumerate(lines) if abs(line_y - y) <= 2.0), None)
            if match is None:
                lines.append((y, value))
            else:
                line_y, current = lines[match]
                lines[match] = ((line_y + y) / 2, current + " " + value)
        lines.sort(key=lambda row: row[0])
    except Exception:  # noqa: BLE001 - unsupported text geometry means no automatic match
        return []

    headings: list[tuple[int, float]] = []
    for y, line in lines:
        for found in _PDF_QUESTION_HEADING.finditer(line):
            try:
                headings.append((int(found.group(1)), y))
            except ValueError:
                continue
    # A repeated heading number on one page makes the page ambiguous.
    if not headings or len({n for n, _ in headings}) != len(headings):
        return []

    text_matches = list(_PDF_QUESTION_HEADING.finditer(page_text))
    by_number: dict[int, str] = {}
    if len(text_matches) == len(headings):
        for i, (number, _) in enumerate(headings):
            start = text_matches[i].start()
            end = text_matches[i + 1].start() if i + 1 < len(text_matches) else len(page_text)
            by_number[number] = page_text[start:end].strip()

    page_height = float(page.mediabox.height)
    return [
        {"question_no": number, "top": y, "bottom": headings[i + 1][1] if i + 1 < len(headings) else page_height,
         "source_text": by_number.get(number, "")}
        for i, (number, y) in enumerate(headings)
    ]


def _pdf_page_figures(page: Any, page_number: int, regions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract each placed JPEG with a question number only when geometry proves one."""
    try:
        xobjects = (page.get("/Resources") or {}).get("/XObject") or {}
    except Exception:  # noqa: BLE001 - a malformed page must not fail the whole import
        return []

    placed: list[dict[str, Any]] = []

    def record(operator: bytes, operands: Any, cm: Any, _tm: Any) -> None:
        if operator != b"Do" or not operands:
            return
        name = str(operands[0])
        ref = xobjects.get(name)
        if ref is None:
            return
        try:
            obj = ref.get_object()
        except Exception:  # noqa: BLE001
            return
        if str(obj.get("/Subtype") or "") != "/Image":
            return
        filt = obj.get("/Filter")
        filters = [str(f) for f in (filt if isinstance(filt, list) else [filt])]
        if "/DCTDecode" not in filters and "/JPXDecode" not in filters:
            return
        try:
            url = _data_url(obj.get_data())
        except Exception:  # noqa: BLE001
            return
        if not url:
            return

        # The image paints the unit square through the current PDF matrix [a b c d e f].
        # Use its full transformed bounds so rotation/skew cannot silently select another row.
        try:
            a, b, c, d, e, f = (float(cm[i]) for i in range(6))
            corners = [(e, f), (a + e, b + f), (c + e, d + f), (a + c + e, b + d + f)]
            top = float(page.mediabox.height) - max(y for _, y in corners)
            bottom = float(page.mediabox.height) - min(y for _, y in corners)
            center = (top + bottom) / 2
        except Exception:  # noqa: BLE001
            top = bottom = center = -1

        matches = [r for r in regions if top >= r["top"] and bottom <= r["bottom"] and r["top"] <= center < r["bottom"]]
        region = matches[0] if len(matches) == 1 else None
        placed.append({"page": page_number, "data_url": url,
                       "question_no": region["question_no"] if region else None,
                       "question_source_text": region["source_text"] if region else ""})

    try:
        page.extract_text(visitor_operand_before=record)
    except Exception:  # noqa: BLE001
        return []

    # Two pictures placed in one question are ambiguous for the single-picture field.
    counts: dict[int, int] = {}
    for item in placed:
        no = item["question_no"]
        if no is not None:
            counts[no] = counts.get(no, 0) + 1
    for item in placed:
        if item["question_no"] is not None and counts[item["question_no"]] != 1:
            item["question_no"] = None
            item["question_source_text"] = ""
    return placed


def _docx_figures(data: bytes) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in sorted(z.namelist()):
                if not name.startswith("word/media/") or name.endswith("/"):
                    continue
                if not name.lower().endswith((".jpg", ".jpeg", ".png")):
                    out.append({"data_url": "", "source_name": name.rsplit("/", 1)[-1],
                                "source_format": name.rsplit(".", 1)[-1].lower() if "." in name else "unknown"})
                    continue
                try:
                    raw = z.read(name)
                except Exception:  # noqa: BLE001
                    continue
                source_hash = hashlib.sha256(raw).hexdigest()
                try:
                    preview = _image_preview(raw)
                    url = _data_url(preview)
                except Exception:  # noqa: BLE001
                    # Keep an omission marker so the teacher receives an honest
                    # count even when the embedded bytes are corrupt or unsupported.
                    out.append({"data_url": "", "source_name": name.rsplit("/", 1)[-1],
                                "source_sha256": source_hash,
                                "source_format": "png" if name.lower().endswith(".png") else "jpeg"})
                    continue
                if url:
                    out.append({"data_url": url, "source_name": name.rsplit("/", 1)[-1],
                                "source_sha256": source_hash, "source_format": "png" if raw.startswith(b"\x89PNG") else "jpeg"})
                else:
                    out.append({"data_url": "", "source_name": name.rsplit("/", 1)[-1],
                                "source_sha256": source_hash, "source_format": "unknown"})
    except Exception:  # noqa: BLE001
        return out
    return out


def _image_preview(raw: bytes, *, max_side: int = 2200) -> bytes:
    """Return a review-sized JPEG while leaving the uploaded office file untouched."""
    if len(raw) <= 450_000:
        return raw
    from PIL import Image

    with Image.open(io.BytesIO(raw)) as image:
        width, height = image.size
        if width <= 0 or height <= 0 or width * height > 50_000_000:
            raise ValueError("embedded image dimensions exceed the safe preview limit")
        image = image.convert("RGB")
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        image.save(out, format="JPEG", quality=78, optimize=True)
        return out.getvalue()


def _data_url(raw: bytes) -> str:
    if raw.startswith(b"\xff\xd8\xff"):
        return "data:image/jpeg;base64," + base64.b64encode(raw).decode()
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "data:image/png;base64," + base64.b64encode(raw).decode()
    return ""



def _plain(data: bytes) -> str:
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "ignore")


def extract(ext: str, data: bytes) -> dict[str, Any]:
    """{"text": str, "slides": [str], "images": [{"page": int, "data_url": str}]}.

    slides only for .pptx (the teacher's own slides, in order); images are the pictures
    embedded in the original file, in document order, so imported questions can keep them.
    """
    ext = ext.lower()
    slides: list[str] = []
    figures: list[dict[str, Any]] = []
    source_figure_count = 0
    if ext == ".docx":
        text = _docx(data)
        source_figures = _docx_figures(data)
        source_figure_count = len(source_figures)
        figures = [{"page": 0, **item} for item in source_figures]
    elif ext == ".pptx":
        slides = _pptx(data)
        text = "\n".join(f"第{i}页：{s}" for i, s in enumerate(slides, start=1))
    elif ext == ".pdf":
        text, figures = _pdf(data)
    elif ext in (".txt", ".md"):
        text = _plain(data)
    else:
        raise ValueError("unsupported")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError("教案文字超过20万字，请拆分文件后导入；未截断或保存任何内容")
    images = _budget_figures(figures)
    return {"text": text, "slides": slides, "images": images,
            "omittedImages": max(0, source_figure_count - len(images))}


def _budget_figures(figures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep figures that fit the per-image and per-lesson request budget."""
    kept: list[dict[str, Any]] = []
    total = 0
    for item in figures:
        url = str(item.get("data_url") or "")
        if not url or len(url) > MAX_FIGURE_CHARS:
            continue
        if len(kept) >= MAX_FIGURES or total + len(url) > MAX_TOTAL_FIGURE_CHARS:
            break
        kept_item = {"page": int(item.get("page") or 0), "data_url": url,
                     "question_no": item.get("question_no") if isinstance(item.get("question_no"), int) else None,
                     "question_source_text": str(item.get("question_source_text") or "")[:MAX_TEXT_CHARS]}
        for key in ("source_name", "source_sha256", "source_format"):
            if item.get(key):
                kept_item[key] = str(item[key])[:160]
        kept.append(kept_item)
        total += len(url)
    return kept



_LESSON_NO_PATTERNS = (
    re.compile(r"第\s*(\d{1,2})\s*课"),
    re.compile(r"lesson[\s_-]*(\d{1,2})", re.IGNORECASE),
    re.compile(r"课次[\s_-]*(\d{1,2})"),
    re.compile(r"^\s*(\d{1,2})\s*[-_.、\s]"),
)


def detect_lesson_no(filename: str, *, max_lesson: int = 18) -> int | None:
    """The 课次 a teacher wrote in the file name: 第03课 / lesson-03 / 03-教案.docx.

    A bare number is only read at the start of the name, so a date such as
    2026-10-26 can never be mistaken for a lesson number. None when it cannot be told.
    """
    name = str(filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    stem = name.rsplit(".", 1)[0] if "." in name else name
    for pattern in _LESSON_NO_PATTERNS:
        match = pattern.search(stem)
        if not match:
            continue
        try:
            value = int(match.group(1))
        except (TypeError, ValueError):
            continue
        if 1 <= value <= max_lesson:
            return value
    return None


__all__ = ["MAX_FILE_BYTES", "MAX_TEXT_CHARS", "SUPPORTED", "extract", "detect_lesson_no"]
