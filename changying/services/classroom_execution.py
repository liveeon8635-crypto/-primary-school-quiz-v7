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

def presenter_turn_is_open(status:str)->bool:
    return str(status or "") in {"invited","accepted","presenting"}

def can_complete_session(segment_statuses:Iterable[str])->bool:
    values=[str(x or "") for x in segment_statuses]
    return bool(values) and all(x=="completed" for x in values)

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

# 人教版小学数学教材版本与知识模块目录。
# 反馈 #304：五年级“简易方程”和“位置”在最新人教版教材中已改版，
# 旧版目录会把这两个模块归到过时的单元/学期，导致“知识模块练习”
# 展示的不是最新版本。这里以显式版本目录作为唯一事实来源，
# 供知识模块练习按教材版本选择正确的模块归属。
TEXTBOOK_EDITIONS={"2013","2024"}
CURRENT_TEXTBOOK_EDITION="2024"

# 每个模块记录其在各教材版本中的年级/学期归属。
# 2024 版：简易方程与位置均调整到五年级上册，且位置单元内容改为
# 用数对确定位置（原 2013 版为五年级上册“位置”+ 五年级下册“简易方程”）。
KNOWLEDGE_MODULE_EDITIONS={
    "简易方程":{
        "2013":{"grade":5,"term":"下","unit":"简易方程"},
        "2024":{"grade":5,"term":"上","unit":"简易方程"},
    },
    "位置":{
        "2013":{"grade":5,"term":"上","unit":"位置"},
        "2024":{"grade":5,"term":"上","unit":"位置（用数对确定位置）"},
    },
}

def normalize_textbook_edition(edition:str|None)->str:
    value=str(edition or "").strip()
    if value in TEXTBOOK_EDITIONS:
        return value
    return CURRENT_TEXTBOOK_EDITION

def knowledge_module_placement(module:str,edition:str|None=None)->dict|None:
    """返回指定教材版本下知识模块的年级/学期/单元归属。

    未登记的模块返回 None，由调用方决定回退策略；
    已登记模块在未知版本下回退到当前版本，避免展示过时目录。
    """
    name=str(module or "").strip()
    placements=KNOWLEDGE_MODULE_EDITIONS.get(name)
    if not placements:
        return None
    resolved=normalize_textbook_edition(edition)
    placement=placements.get(resolved) or placements.get(CURRENT_TEXTBOOK_EDITION)
    if not placement:
        return None
    result=dict(placement)
    result["module"]=name
    result["edition"]=resolved
    return result

def knowledge_modules_for_grade(grade:int,edition:str|None=None)->list[dict]:
    """返回某年级在当前教材版本下应展示的知识模块目录。"""
    resolved=normalize_textbook_edition(edition)
    out=[]
    for name in KNOWLEDGE_MODULE_EDITIONS:
        placement=knowledge_module_placement(name,resolved)
        if placement and int(placement.get("grade") or 0)==int(grade):
            out.append(placement)
    out.sort(key=lambda item:(str(item.get("term") or ""),str(item.get("module") or "")))
    return out

__all__=[
    "PRESENTER_STATUSES","SEGMENT_MODES","SEGMENT_STATUSES","SESSION_STATUSES",
    "can_complete_session","can_start_segment","candidate_signals","candidate_sort_key","presenter_required","presenter_turn_is_open",
    "presenter_transition_allowed","segment_status_for_mode","session_transition_allowed",
    "unique_knowledge_keys",
]
