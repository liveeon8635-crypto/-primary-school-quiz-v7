"""Readable text slides; preserve all supplied text and original PPT page boundaries."""
from __future__ import annotations
import json
import re
from typing import Any


def presentation_pages(raw: Any, *, preserve_pages: bool = False, source: str = "") -> list[str]:
    if isinstance(raw,str):
        try:raw=json.loads(raw or '[]')
        except (ValueError,TypeError):return []
    if not isinstance(raw,list):return []
    pages=[]
    for item in raw:
        if isinstance(item,dict):
            text='\n'.join(str(item.get(k) or '').strip() for k in ('title','question','stem','text','answer') if item.get(k))
        else:text=str(item or '').strip()
        if text:pages.append(text)
    # Old Word imports and AI drafts stored a list of headings or individual
    # lines. Keep original PPT slides and authored multi-paragraph pages intact.
    line_deck=not preserve_pages and len(pages)>=10 and sum(len(p)<120 and '\n' not in p for p in pages)>=len(pages)*.7
    if line_deck and '单元高频考点讲解' in source and '学生随堂试卷' in source:
        # A recognisable teacher-authored lecture section is stronger evidence
        # than the old model-generated headings. Never project the raw full
        # original (which also contains private scoring/answer sections).
        lecture = source.split('学生随堂试卷', 1)[0]
        lecture = re.split(r'参考答案|评分细则|教师专用|教师用答案', lecture, maxsplit=1)[0]
        paragraphs = [p.strip() for p in lecture.splitlines() if p.strip()]
        if paragraphs:
            pages = paragraphs
    if not line_deck:return pages
    out=[];current=[];size=0
    for text in pages:
        if current and (size+len(text)>900 or len(current)>=6):
            out.append('\n\n'.join(current));current=[];size=0
        current.append(text);size+=len(text)+2
    if current:out.append('\n\n'.join(current))
    return out
