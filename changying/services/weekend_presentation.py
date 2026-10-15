"""Group fragmented imports and split long text into complete screen-sized pages."""
from __future__ import annotations
import json
import re
from typing import Any

PAGE_CHARS=360
PAGE_PARAGRAPHS=5


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
            text='\n'.join(str(item.get(k) or '').strip() for k in ('title','question','stem','text','answer') if item.get(k))
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
