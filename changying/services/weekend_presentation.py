"""Group fragmented imports and split long text into complete screen-sized pages."""
from __future__ import annotations
import json
import re
from typing import Any

PAGE_CHARS=360
PAGE_PARAGRAPHS=5


def literal_numbered_questions(source: str) -> list[str]:
    """Extract question text only where explicit, unique question headings exist."""
    # Accept reviewed headings such as "第1题 [基础] 2分 · 操作", as well
    # as the older standalone "第1题 2分". Avoid matching prose mentioning a
    # question number by requiring a score when the heading has other content.
    heading = re.compile(r'(?m)^[^\S\n]*第[^\S\n]*(\d{1,2})[^\S\n]*题(?P<suffix>[^\n]{0,85})$')

    def headings(text: str) -> list[re.Match[str]]:
        return [m for m in heading.finditer(text)
                if not m.group("suffix").strip() or "分" in m.group("suffix")]

    body = source or ''
    marks = headings(body)
    numbers = [int(m.group(1)) for m in marks]
    if len(marks) >= 2 and len(set(numbers)) != len(numbers):
        # A printed teacher lesson can first contain a two-column question
        # provenance table ("第1题" / "第1课时·...") and then the actual
        # numbered exercises. Never use the table as screen content.
        # Limit this recovery to clearly labelled multi-part lesson bodies;
        # unstructured repeated headings continue to fail closed.
        part = re.search(r'(?m)^[^\S\n]*第一部分(?:[^\S\n：:、]|[：:、]|$)', body)
        if part:
            body = body[part.start():]
            stop = re.search(r'(?m)^[^\S\n]*(?:课堂小结与板书|课后作业|自检表)(?:[^\S\n]|$)', body)
            if stop:
                body = body[:stop.start()]
            marks = headings(body)
            numbers = [int(m.group(1)) for m in marks]
    if len(marks) < 2 or len(set(numbers)) != len(numbers):
        return []
    out = []
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        chunk = body[mark.start():end]
        # Bracketed teacher answer/marking sections must not enter the big screen.
        stop = re.search(
            r'(?m)^[^\S\n]*(?:【[^\n】]{0,24}】|'
            r'(?:考点提醒|答案|解析|参考答案|评分要点|分步赋分)[^\n：:]{0,8}[：:])',
            chunk,
        )
        if stop:
            chunk = chunk[:stop.start()]
        chunk = chunk.strip()
        if '\n' not in chunk or re.search(r'(?:答案|解析|评分要点)\s*[：:]', chunk):
            return []
        out.append(chunk)
    return out


def _screen_chunks(text: str) -> list[str]:
    """Split at a paragraph/sentence boundary, retaining every character."""
    chunks=[]
    while len(text)>PAGE_CHARS:
        candidates=[text.rfind(mark,PAGE_CHARS//2,PAGE_CHARS) for mark in ('\n','。','！','？','；')]
        cut=max(candidates)
        cut=cut+1 if cut>=0 else PAGE_CHARS
        chunks.append(text[:cut]);text=text[cut:]
    if text:chunks.append(text)
    return chunks


def presentation_pages(raw: Any, *, preserve_pages: bool = False, source: str = "", example_mode: bool = False) -> list[str]:
    if isinstance(raw,str):
        try:raw=json.loads(raw or '[]')
        except (ValueError,TypeError):return []
    if not isinstance(raw,list):return []
    pages=[]
    for item in raw:
        if isinstance(item,dict):
            parts=[str(item.get(k) or '').strip() for k in ('title','question','stem','text') if item.get(k)]
            answer=str(item.get('answer') or '').strip()
            if answer:
                # Labelled, so the big screen can keep it covered until the teacher shows it.
                parts.append(answer if re.match(r'^(参考答案|答案|解答|解析)[：:]',answer) else '答案：'+answer)
            text='\n'.join(parts)
        else:text=str(item or '').strip()
        if text:pages.append(text)
    line_deck=not preserve_pages and len(pages)>=10 and sum(len(p)<120 and '\n' not in p for p in pages)>=len(pages)*.7
    if line_deck and example_mode:
        joined='\n'.join(pages)
        if '学生随堂试卷' in joined:
            joined=joined.split('学生随堂试卷',1)[1]
            joined=re.split(r'(?m)^.*(?:教师参考答案|教师用答案|教师专用答案|参考答案与采分点|参考答案及评分).*$' ,joined,maxsplit=1)[0]
            pages=[p.strip() for p in joined.splitlines() if p.strip()]
    if line_deck and '单元高频考点讲解' in source and '学生随堂试卷' in source:
        lecture=source.split('学生随堂试卷',1)[0]
        lecture=re.split(r'参考答案|评分细则|教师专用|教师用答案',lecture,maxsplit=1)[0]
        paragraphs=[p.strip() for p in lecture.splitlines() if p.strip()]
        if paragraphs:pages=paragraphs
    # Only merge fragmented line imports. Explicit/PPT pages retain their
    # boundaries, while an overlong page gets continuation screens.
    if not line_deck:
        return [chunk for page in pages for chunk in _screen_chunks(page)]
    grouped=[];current=[];size=0
    for text in pages:
        if current and (size+len(text)+2>PAGE_CHARS or len(current)>=PAGE_PARAGRAPHS):
            grouped.append('\n\n'.join(current));current=[];size=0
        current.append(text);size+=len(text)+2
    if current:grouped.append('\n\n'.join(current))
    return [chunk for page in grouped for chunk in _screen_chunks(page)]


def lesson_deck(lesson: dict[str, Any], stage_no: int) -> list[str]:
    """Pages the teacher pages through on the big screen: their own slides (stage 2) or worked examples (stage 3)."""
    if stage_no not in (2, 3):
        return []
    raw = lesson.get("ppt_json") if stage_no == 2 else lesson.get("examples_json")
    source = str(lesson.get("reading_plan") or "")
    if stage_no == 3:
        originals = literal_numbered_questions(source)
        if originals:
            return presentation_pages(originals, preserve_pages=True)
    return presentation_pages(raw, preserve_pages=stage_no == 2 and source.startswith("第1页："),
                              source=source if stage_no == 2 else "", example_mode=stage_no == 3)


