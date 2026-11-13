"""Group fragmented imports and split long text into complete screen-sized pages."""
from __future__ import annotations
import json
import re
from typing import Any

PAGE_CHARS=360
PAGE_PARAGRAPHS=5


def literal_numbered_questions(source: str) -> list[str]:
    """Recover individual exercise pages from revised student/teacher handouts.

    Supports plain headings and level/score/type metadata, while treating
    teacher solutions as private. Ambiguous duplicate numbering fails closed.
    """
    heading = re.compile(
        r'(?m)^[^\S\n]*第[^\S\n]*(\d{1,2})[^\S\n]*题'
        r'(?:[^\S\n]*[（(【\[][^\S\n]*(?:基础|进阶|提升)[^\S\n]*[）)】\]])?'
        r'(?:[^\S\n]*[（(]?[^\S\n]*\d+(?:\.\d+)?[^\S\n]*分[^\S\n]*[）)]?)?'
        r'(?:[^\S\n]*[·•｜|—－-][^\n]{1,60})?[^\S\n]*$'
    )
    body = source or ''
    marks = list(heading.finditer(body))
    numbers = [int(m.group(1)) for m in marks]
    if len(marks) >= 2 and len(set(numbers)) != len(numbers):
        # A DOCX source-correspondence table can repeat each real question
        # number. Start at the first actual teaching section, not the table.
        # Without an unambiguous boundary do not guess which copy is genuine.
        section = re.search(
            r'(?m)^[^\S\n]*(?:第[一二三四五六七八九十]+部分[^\n]{0,60}'
            r'|[一二三四五六七八九十]+[、.．][^\n]{2,60})$',
            body,
        )
        if section:
            body = body[section.start():]
            # Printed appendices can repeat question numbers: they are not
            # worked-example pages and must be excluded before de-duplicating.
            end_of_paper = re.search(
                r'(?m)^[^\S\n]*(?:课堂小结与板书|课堂小结|课后作业|作答检查'
                r'|自检表|附录[AB一二三四五六]|验收表)(?:[^\S\n]|[｜：:]|$)',
                body,
            )
            if end_of_paper:
                body = body[:end_of_paper.start()]
            marks = list(heading.finditer(body))
            numbers = [int(m.group(1)) for m in marks]
    if len(marks) < 2 or len(set(numbers)) != len(numbers):
        return []
    # Keep the student task, never teacher-only answers, reasoning, scoring,
    # staged reveal instructions, appendices or a following homework section.
    private_line = re.compile(
        r'(?m)^[^\S\n]*(?:考点提醒|答案|解析|参考答案|评分要点|评分标准'
        r'|【(?:参考答案|解析与错因|分步赋分|课件分镜|教师[^】]*|评分[^】]*|讲解[^】]*)】'
        r'|课堂小结与板书|课堂小结|课后作业|作答检查|附录[AB一二三四五六]'
        r'|自检表|验收表|阶段反馈)[^\n]*$'
    )
    out = []
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        chunk = body[mark.start():end]
        stop = private_line.search(chunk)
        if stop:
            chunk = chunk[:stop.start()]
        chunk = chunk.strip()
        if '\n' not in chunk or re.search(
            r'(?:答案|解析|评分要点)\s*[：:]|【(?:参考答案|解析与错因|分步赋分)',
            chunk,
        ):
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
            before, after = joined.split('学生随堂试卷', 1)
            # Revised handouts put explicit worked examples before the pupil
            # paper. Older imports may contain only stale headings before it
            # and the useful reading example after it, so preserve that
            # established layout unless the pre-paper section is recognisably
            # an example deck. A paper-only import fails closed.
            if not before.strip() or re.search(r'例题|讲解', before):
                joined = before
            else:
                joined = after
            joined = re.split(
                r'(?m)^.*(?:教师参考答案|教师用答案|教师专用答案|参考答案与采分点|参考答案及评分).*$',
                joined,
                maxsplit=1,
            )[0]
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
            # One reviewed exercise maps to exactly one interaction slot,
            # even when its full stem exceeds the generic slide text limit.
            # Splitting a long stem moves later question/page indices and
            # mismatches attached diagrams and approved courseware.
            return originals
    return presentation_pages(raw, preserve_pages=stage_no == 2 and source.startswith("第1页："),
                              source=source if stage_no == 2 else "", example_mode=stage_no == 3)


