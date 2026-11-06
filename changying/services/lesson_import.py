"""Plain-text extraction from a teacher's own lesson plan file (.docx / .pptx / .pdf / .txt / .md).

No XML parser is used on the (untrusted) Office files: the text runs are pulled out with regular expressions, so an
entity-expansion bomb has nothing to expand. The caller validates the zip container (size / entry limits) first.
"""

from __future__ import annotations

import base64
import html
import io
import re
import zipfile
from typing import Any

MAX_FILE_BYTES = 10 * 1024 * 1024
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
        texts.append(page.extract_text() or "")
        # The teacher's paper is exported with its question pictures as JPEG XObjects;
        # read those streams directly (no imaging library on the server).
        for url in _pdf_page_figures(page):
            figures.append({"page": number, "data_url": url})
    return "\n".join(texts), figures


def _pdf_page_figures(page: Any) -> list[str]:
    try:
        xobjects = (page.get("/Resources") or {}).get("/XObject") or {}
    except Exception:  # noqa: BLE001 - a malformed page must not fail the whole import
        return []
    out: list[str] = []
    for _, ref in xobjects.items():
        try:
            obj = ref.get_object()
        except Exception:  # noqa: BLE001
            continue
        if str(obj.get("/Subtype") or "") != "/Image":
            continue
        filt = obj.get("/Filter")
        filters = [str(f) for f in (filt if isinstance(filt, list) else [filt])]
        if "/DCTDecode" not in filters and "/JPXDecode" not in filters:
            continue
        try:
            url = _data_url(obj.get_data())
        except Exception:  # noqa: BLE001
            continue
        if url:
            out.append(url)
    return out


def _docx_figures(data: bytes) -> list[str]:
    out: list[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in sorted(z.namelist()):
                if not name.startswith("word/media/") or not name.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                try:
                    url = _data_url(z.read(name))
                except Exception:  # noqa: BLE001
                    continue
                if url:
                    out.append(url)
    except Exception:  # noqa: BLE001
        return out
    return out


def _data_url(raw: bytes) -> str:
    # JPEG only: the question figure field and its renderer accept data:image/jpeg.
    if raw.startswith(b"\xff\xd8\xff"):
        return "data:image/jpeg;base64," + base64.b64encode(raw).decode()
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
    if ext == ".docx":
        text = _docx(data)
        figures = [{"page": 0, "data_url": url} for url in _docx_figures(data)]
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
    return {"text": text, "slides": slides, "images": _budget_figures(figures)}


def _budget_figures(figures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the first figures that fit the count and size budget; drop the rest silently."""
    kept: list[dict[str, Any]] = []
    total = 0
    for item in figures:
        url = str(item.get("data_url") or "")
        if not url or len(url) > MAX_FIGURE_CHARS:
            continue
        if len(kept) >= MAX_FIGURES or total + len(url) > MAX_TOTAL_FIGURE_CHARS:
            break
        kept.append({"page": int(item.get("page") or 0), "data_url": url})
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
