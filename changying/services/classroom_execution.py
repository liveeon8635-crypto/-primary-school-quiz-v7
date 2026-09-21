"""State machine and candidate policy for live classroom execution."""

from __future__ import annotations

from typing import Iterable

SESSION_STATUSES={"planned","active","paused","completed","cancelled"}
SEGMENT_MODES={"teacher","student","co_teach","discussion","skipped"}
SEGMENT_STATUSES={"planned","selecting_presenter","explaining","checking","reviewed","completed"}
PRESENTER_STATUSES={"invited","accepted","declined","withdrawn","presenting","completed"}

_SESSION_TRANSITIONS={
    "planned":{"active","cancelled"},
    "active":{"paused","completed","cancelled"},
    "paused":{"active","completed","cancelled"},
    "completed":set(),
    "cancelled":set(),
}
_PRESENTER_TRANSITIONS={
    "invited":{"accepted","declined","withdrawn"},
    "accepted":{"presenting","withdrawn"},
    "declined":set(),
    "withdrawn":set(),
    "presenting":{"completed"},
    "completed":set(),
}

def session_transition_allowed(current:str,target:str)->bool:
    return target in _SESSION_TRANSITIONS.get(str(current or ""),set())

def presenter_transition_allowed(current:str,target:str)->bool:
    return target in _PRESENTER_TRANSITIONS.get(str(current or ""),set())

def segment_status_for_mode(mode:str)->str:
    mode=str(mode or "")
    if mode in {"student","co_teach"}: return "selecting_presenter"
    if mode=="skipped": return "completed"
    if mode in {"teacher","discussion"}: return "planned"
    raise ValueError("invalid segment mode")

def presenter_required(mode:str)->bool:
    return str(mode or "") in {"student","co_teach"}

def can_start_segment(*,session_status:str,segment_status:str,mode:str,presenter_status:str|None)->tuple[bool,str]:
    if session_status!="active": return False,"课堂尚未处于进行中"
    if segment_status not in {"planned","selecting_presenter"}: return False,"当前知识点状态不能开始讲解"
    if mode=="skipped": return False,"已跳过的知识点不能开始讲解"
    if presenter_required(mode) and presenter_status!="accepted":
        return False,"学生讲解必须先由学生本人确认"
    return True,""

def candidate_sort_key(candidate:dict)->tuple:
    return (
        -int(bool(candidate.get("sourceExerciseCorrect"))),
        -int(candidate.get("priorSuccessEvidence") or 0),
        int(candidate.get("priorPresentationCount") or 0),
        str(candidate.get("name") or ""),
        int(candidate.get("id") or 0),
    )

def candidate_signals(*,source_exercise_correct:bool,prior_success_evidence:int,prior_presentation_count:int)->list[str]:
    signals=[]
    if source_exercise_correct: signals.append("本次练习该知识点有正确作答")
    if prior_success_evidence>0: signals.append(f"已有 {prior_success_evidence} 条相关成功学习证据")
    if prior_presentation_count==0: signals.append("暂无已完成的同知识点讲解记录")
    else: signals.append(f"已完成 {prior_presentation_count} 次同知识点讲解")
    if not signals: signals.append("由教师结合课堂情况判断是否邀请")
    return signals

def unique_knowledge_keys(values:Iterable[str])->list[str]:
    seen=set();out=[]
    for raw in values:
        value=str(raw or "").strip()
        if value and value not in seen:
            seen.add(value);out.append(value)
    return out

__all__=[
    "PRESENTER_STATUSES","SEGMENT_MODES","SEGMENT_STATUSES","SESSION_STATUSES",
    "can_start_segment","candidate_signals","candidate_sort_key","presenter_required",
    "presenter_transition_allowed","segment_status_for_mode","session_transition_allowed",
    "unique_knowledge_keys",
]
