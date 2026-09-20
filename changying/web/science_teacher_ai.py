"""Science teacher AI workflow guard and UI affordance.

Science is available only when the teacher names the school's actual textbook
line.  The workflow deliberately does not register a national/default science
textbook or enable a built-in science question pack.
"""

from __future__ import annotations

from functools import wraps
import re
from types import ModuleType
from typing import Any

from fastapi import HTTPException

from changying.services.textbook_registry import (
    TextbookRegistryError,
    require_textbook,
)


SCIENCE_TEACHER_AI_MARKER = "changying_science_teacher_ai_v1"
_AMBIGUOUS_SCIENCE_TEXTBOOKS = frozenset(
    {
        "",
        "人教版",
        "人教版（当前最新版）",
        "人教版（PEP·当前最新版）",
        "PEP·当前最新版",
        "统编版",
        "统编版（人民教育出版社）",
    }
)


def require_explicit_science_textbook(subject: str, textbook: str) -> str:
    """Require a science-specific school textbook label without guessing."""
    raw_subject = str(subject or "").strip()
    raw_textbook = str(textbook or "").strip()
    if "科学" not in raw_subject:
        return raw_textbook
    if raw_textbook in _AMBIGUOUS_SCIENCE_TEXTBOOKS:
        raise ValueError(
            "科学教材必须明确填写学校实际使用的出版社/版本；"
            "不要使用数学、语文或英语界面的通用默认教材名"
        )
    return raw_textbook


def normalize_teacher_ai_textbook(grade: int, subject: str, textbook: str) -> str:
    """Normalize verified Grade 5 curricula and keep science explicit."""
    raw_subject = str(subject or "").strip()
    raw_textbook = str(textbook or "").strip()
    if "科学" in raw_subject:
        return require_explicit_science_textbook(raw_subject, raw_textbook)
    try:
        return require_textbook(int(grade or 0), raw_subject, raw_textbook)
    except TextbookRegistryError as exc:
        raise ValueError(str(exc)) from exc


def augment_science_teacher_prompt(feature: str, prompt: str) -> str:
    """Add science-specific lesson constraints without altering other subjects."""
    if str(feature or "") not in {"lesson_plan", "lesson_practice"}:
        return prompt
    text = str(prompt or "")
    if not re.search(r"课程：\s*\d+年级\s*科学(?:；|;)", text):
        return text
    return (
        text
        + """

【科学教师工作流附加约束】
1. 教材出版社/版本、册次、单元和课题必须以教师输入为准；不得猜测或替换成其他科学教材版本。
2. 教学设计必须区分“观察事实/实验数据”“由证据支持的解释”“仍需验证的推测”，避免把推测写成既定事实。
3. 课堂活动优先体现观察、分类、比较、变量控制、证据解释、模型表达、预测与检验等科学实践。
4. 实验设计要写清材料、条件、变量、记录方式和安全边界；不得要求学生自行进行明火、强电、危险化学品或其他明显高风险操作。
5. 课堂练习可以包含客观题和教师审核型解释题，但参考答案必须说明判断依据；开放探究题不能伪装成唯一自动判分答案。
6. 若输入的教材、单元或课题信息不足，应在 teacher_notes / 设计目的中明确提示教师补充核对，不得虚构教材章节或课文内容。
"""
    )


def _route(implementation: ModuleType, path: str, method: str):
    for route in implementation.app.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route
    raise RuntimeError(f"route not found: {method} {path}")


def _body_from_call(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    body = kwargs.get("b")
    if body is not None:
        return body
    for value in args:
        if hasattr(value, "subject") and hasattr(value, "textbook"):
            return value
    return None


def patch_science_teacher_ai_html(html: str) -> str:
    """Expose science lesson planning and make the textbook requirement visible."""
    if SCIENCE_TEACHER_AI_MARKER in html:
        return html

    old_lesson_subject = (
        '<select id="alSubject"><option>数学</option><option>语文</option>'
        '<option>英语</option></select>'
    )
    new_lesson_subject = (
        '<select id="alSubject"><option>数学</option><option>语文</option>'
        '<option>英语</option><option>科学</option></select>'
    )
    if old_lesson_subject not in html:
        raise RuntimeError("science teacher AI patch: lesson subject selector not found")
    html = html.replace(old_lesson_subject, new_lesson_subject, 1)

    question_textbook = '<input id="aqTextbook" value="人教版">'
    question_textbook_new = (
        '<input id="aqTextbook" value="人教版">'
        '<small id="aqScienceTextbookHint" class="muted hidden">'
        '科学：请填写学校实际使用的出版社/版本，系统不会自动猜测教材。</small>'
    )
    if question_textbook not in html:
        raise RuntimeError("science teacher AI patch: question textbook input not found")
    html = html.replace(question_textbook, question_textbook_new, 1)

    lesson_textbook = '<input id="alTextbook" value="人教版">'
    lesson_textbook_new = (
        '<input id="alTextbook" value="人教版">'
        '<small id="alScienceTextbookHint" class="muted hidden">'
        '科学：请填写学校实际使用的出版社/版本，系统不会自动猜测教材。</small>'
    )
    if lesson_textbook not in html:
        raise RuntimeError("science teacher AI patch: lesson textbook input not found")
    html = html.replace(lesson_textbook, lesson_textbook_new, 1)

    snippet = r'''
<script id="changying_science_teacher_ai_v1-script">
(()=>{
  if(window.__cyScienceTeacherAIInstalled)return;
  window.__cyScienceTeacherAIInstalled=true;
  const ambiguous=new Set(['人教版','人教版（当前最新版）','人教版（PEP·当前最新版）','PEP·当前最新版','统编版','统编版（人民教育出版社）']);
  const registered={5:{'数学':'人教版','语文':'统编版（人民教育出版社）','英语':'人教版（PEP·当前最新版）'}};
  function sync(prefix){
    const subject=document.getElementById(prefix+'Subject');
    const grade=document.getElementById(prefix+'Grade');
    const textbook=document.getElementById(prefix+'Textbook');
    const hint=document.getElementById(prefix+'ScienceTextbookHint');
    if(!subject||!textbook)return;
    const subjectValue=String(subject.value||'').trim();
    const science=subjectValue.includes('科学');
    const gradeValue=Number(grade?.value||0);
    const canonical=(registered[gradeValue]||{})[subjectValue]||'';
    if(science){
      if(ambiguous.has(String(textbook.value||'').trim())) textbook.value='';
      textbook.placeholder='必填：学校实际科学教材出版社/版本';
      textbook.setAttribute('aria-required','true');
    }else if(canonical){
      textbook.value=canonical;
      textbook.placeholder='当前核定教材';
      textbook.setAttribute('aria-required','true');
    }else{
      textbook.placeholder='请输入学校实际教材版本';
      textbook.setAttribute('aria-required','false');
    }
    if(hint) hint.classList.toggle('hidden',!science);
  }
  document.addEventListener('change',event=>{
    if(event.target?.id==='aqSubject'||event.target?.id==='aqGrade')sync('aq');
    if(event.target?.id==='alSubject'||event.target?.id==='alGrade')sync('al');
  });
  const observer=new MutationObserver(()=>{sync('aq');sync('al')});
  observer.observe(document.documentElement,{subtree:true,childList:true});
  setTimeout(()=>{sync('aq');sync('al')},0);
})();
</script>
'''
    if "</body>" not in html:
        raise RuntimeError("science teacher AI patch: closing body marker not found")
    return html.replace(
        "</body>",
        snippet + f"\n<!-- {SCIENCE_TEACHER_AI_MARKER} --></body>",
        1,
    )


def install_science_teacher_ai_workflow(implementation: ModuleType) -> None:
    app = implementation.app
    if getattr(app.state, "science_teacher_ai_workflow_installed", False):
        return

    implementation.INDEX_HTML = patch_science_teacher_ai_html(implementation.INDEX_HTML)

    original_ai_call = implementation._ai_call

    def science_aware_ai_call(
        db: Any,
        user: Any,
        feature: str,
        prompt: str,
        images=None,
        timeout: int = 90,
    ):
        return original_ai_call(
            db,
            user,
            feature,
            augment_science_teacher_prompt(feature, prompt),
            images=images,
            timeout=timeout,
        )

    implementation._ai_call = science_aware_ai_call

    for path in ("/ai/questions/generate", "/ai/lesson-plan/generate", "/ai/lesson-plan/practice"):
        route = _route(implementation, path, "POST")
        original = route.dependant.call

        @wraps(original)
        def guarded(*args: Any, __original=original, **kwargs: Any):
            body = _body_from_call(args, kwargs)
            if body is not None:
                raw_textbook = str(getattr(body, "textbook", "") or "").strip()
                try:
                    canonical = normalize_teacher_ai_textbook(
                        int(getattr(body, "grade", 0) or 0),
                        str(getattr(body, "subject", "") or ""),
                        raw_textbook,
                    )
                except ValueError as exc:
                    raise HTTPException(400, str(exc)) from exc
                if canonical != raw_textbook:
                    setattr(body, "textbook", canonical)
            return __original(*args, **kwargs)

        route.dependant.call = guarded
        route.endpoint = guarded

    app.state.science_teacher_ai_workflow_installed = True


__all__ = [
    "SCIENCE_TEACHER_AI_MARKER",
    "augment_science_teacher_prompt",
    "install_science_teacher_ai_workflow",
    "normalize_teacher_ai_textbook",
    "patch_science_teacher_ai_html",
    "require_explicit_science_textbook",
]
