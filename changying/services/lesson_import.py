"""Plain-text extraction from a teacher's own lesson plan file (.docx / .pptx / .pdf / .txt / .md).

No XML parser is used on the (untrusted) Office files: the text runs are pulled out with regular expressions, so an
entity-expansion bomb has nothing to expand. The caller validates the zip container (size / entry limits) first.
"""

from __future__ import annotations

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


def _pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    if len(reader.pages) > MAX_PDF_PAGES:
        raise ValueError("PDF exceeds supported page count")
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _plain(data: bytes) -> str:
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "ignore")


def extract(ext: str, data: bytes) -> dict[str, Any]:
    """{"text": str, "slides": [str]} — slides only for .pptx (the teacher's own slides, in order)."""
    ext = ext.lower()
    slides: list[str] = []
    if ext == ".docx":
        text = _docx(data)
    elif ext == ".pptx":
        slides = _pptx(data)
        text = "\n".join(f"第{i}页：{s}" for i, s in enumerate(slides, start=1))
    elif ext == ".pdf":
        text = _pdf(data)
    elif ext in (".txt", ".md"):
        text = _plain(data)
    else:
        raise ValueError("unsupported")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError("教案文字超过20万字，请拆分文件后导入；未截断或保存任何内容")
    return {"text": text, "slides": slides}


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
