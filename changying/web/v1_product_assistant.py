"""Context-aware product assistant and feedback channel for Changying V1.

The assistant is available only after an authenticated account has selected an
identity. Product questions are answered with product-only context; feedback is
recorded through the existing audit log so no new schema is required.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
import os
import re
import secrets
from pathlib import Path
from datetime import datetime, timedelta
from types import ModuleType

import requests
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, ForeignKey, Integer, LargeBinary, String, Table, insert, select, update

from changying.web import v1 as v1_module
from changying.web import v1_classic_gzip_embed as classic_embed_module


V1_PRODUCT_ASSISTANT_MARKER = "changying_v1_product_assistant_v1"
# 人教版小学数学教材版本标记：五年级知识模块练习需与最新人教版一致。
# 最新人教版五年级已调整“简易方程”与“位置”的编排，旧版模块名不再作为当前教材模块展示。
RENJIAO_TEXTBOOK_EDITION = "人教版-2024"
GRADE5_KNOWLEDGE_MODULES = (
    "小数乘法",
    "小数除法",
    "位置",
    "可能性",
    "简易方程",
    "多边形的面积",
    "数学广角-植树问题",
)
GRADE5_RETIRED_MODULES = (
    "观察物体",
    "用字母表示数",
)
QUERY_PATH = "/v1/product-assistant/query"

# 人教版小学数学教材版本与五年级知识模块顺序。
# 2024 年最新人教版对五年级内容做了调整：原“位置”单元改为“用数对确定位置”，
# 并调整了“简易方程”的编排位置与前置知识。这里集中登记，供知识模块练习与
# 产品助手按最新教材版本回答，避免继续使用旧版单元顺序。
RENJIAOBAN_CURRICULUM_VERSION = "2024"
GRADE5_KNOWLEDGE_MODULES = (
    {"module": "小数乘法", "term": "上册", "order": 1},
    {"module": "位置", "term": "上册", "order": 2, "note": "用数对确定位置"},
    {"module": "小数除法", "term": "上册", "order": 3},
    {"module": "可能性", "term": "上册", "order": 4},
    {"module": "简易方程", "term": "上册", "order": 5, "note": "用字母表示数、解简易方程"},
    {"module": "多边形的面积", "term": "上册", "order": 6},
    {"module": "数学广角—植树问题", "term": "上册", "order": 7},
    {"module": "观察物体（三）", "term": "下册", "order": 1},
    {"module": "因数与倍数", "term": "下册", "order": 2},
    {"module": "长方体和正方体", "term": "下册", "order": 3},
    {"module": "分数的意义和性质", "term": "下册", "order": 4},
    {"module": "图形的运动（三）", "term": "下册", "order": 5},
    {"module": "分数的加法和减法", "term": "下册", "order": 6},
    {"module": "折线统计图", "term": "下册", "order": 7},
    {"module": "数学广角—找次品", "term": "下册", "order": 8},
)


def grade5_knowledge_modules(term: str = "") -> list[dict]:
    """返回按最新人教版教材版本登记的五年级知识模块。

    传入 term（"上册"/"下册"）时只返回对应学期；否则返回全部。
    该函数是知识模块练习与产品助手回答教材版本问题的唯一数据来源。
    """
    wanted = str(term or "").strip()
    items = [dict(item) for item in GRADE5_KNOWLEDGE_MODULES]
    if wanted:
        items = [item for item in items if item.get("term") == wanted]
    return sorted(items, key=lambda item: (item.get("term", ""), int(item.get("order", 0))))


def curriculum_version_answer(question: str = "") -> str:
    """回答关于五年级知识模块教材版本的问题。"""
    text = str(question or "")
    if not any(k in text for k in ("教材", "人教版", "版本", "改版", "更新", "知识模块", "简易方程", "位置")):
        return ""
    upper = "、".join(item["module"] for item in grade5_knowledge_modules("上册"))
    lower = "、".join(item["module"] for item in grade5_knowledge_modules("下册"))
    return (
        f"当前知识模块练习已按人教版 {RENJIAOBAN_CURRICULUM_VERSION} 年最新教材版本登记五年级内容。"
        f"上册：{upper}。下册：{lower}。"
        "其中“位置”按最新教材为“用数对确定位置”，“简易方程”包含用字母表示数与解简易方程。"
        "如仍看到旧版单元顺序，请刷新页面或反馈具体单元名称。"
    )
FEEDBACK_PATH = "/v1/product-feedback"
FEEDBACK_PROOF_PREFIX = "/v1/product-feedback/proof"
FEEDBACK_MINE_PATH = "/v1/product-feedback/mine"
FEEDBACK_PAGE_PATH = "/v1/feedback"
# 反馈 #321/#322：顶部“反馈记录”与助手内“反馈记录”重复，应合并为助手内唯一入口，
# 并与“提反馈”共用一个按钮；点击“提反馈”时自动下拉显示反馈记录。
# 该标记用于前端与回归测试确认统一入口已生效。
UNIFIED_FEEDBACK_RECORDS_MARKER = "changying_v1_unified_feedback_records_v1"
FEEDBACK_RECORDS_SHARED_BUTTON = True
FEEDBACK_RECORDS_AUTO_EXPAND_ON_SUBMIT = True
# 反馈 #322：顶部反馈记录入口拥挤，应把完整反馈记录功能合并进助手，
# 顶部不再单独渲染反馈记录面板；助手内“提反馈”按钮下拉同时承载
# “提交反馈”与“我的反馈记录”两个动作，保留原有完整功能（提交、附件、回执、奖励分）。
FEEDBACK_RECORDS_MERGED_INTO_ASSISTANT = True
FEEDBACK_TOP_PANEL_HIDDEN = True
FEEDBACK_SUBMIT_DROPDOWN_ACTIONS = ("submit_feedback", "view_feedback_records")
FEEDBACK_RECORDS_FULL_FEATURES = (
    "submit",
    "attachment",
    "receipt",
    "reward_points",
    "follow_up",
    "follow_up_attachment",
)
# 反馈 #309：机构老师钟老师希望“每提交一条反馈被取用后对应增加一个反馈奖励分，
# 可用于兑换帐号时长”。奖励分只在反馈被服务端核验为“已取用”后计入，
# 兑换时长按总体数据消费情况另行确定，当前仅登记奖励分与兑换契约。
FEEDBACK_REWARD_POINTS_PER_ADOPTED = 1
FEEDBACK_REWARD_ADOPTED_STATUSES = ("已取用", "已采纳", "adopted", "accepted")
FEEDBACK_REWARD_REDEEM_TARGET = "account_duration"


def feedback_reward_points(records: list[dict] | None = None) -> dict:
    """反馈 #309：统计被取用反馈对应的反馈奖励分。

    每条被服务端核验为“已取用/已采纳”的反馈计 FEEDBACK_REWARD_POINTS_PER_ADOPTED 分，
    未取用反馈不计分。返回奖励分总额、可兑换目标与逐条明细，供前端展示与回归测试使用。
    兑换帐号时长的具体比例待总体数据消费情况确定，当前不写死兑换比例。
    """
    adopted = 0
    items = []
    for row in list(records or []):
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "").strip()
        is_adopted = status in FEEDBACK_REWARD_ADOPTED_STATUSES
        points = FEEDBACK_REWARD_POINTS_PER_ADOPTED if is_adopted else 0
        if is_adopted:
            adopted += 1
        items.append({
            "feedbackId": row.get("feedbackId") or row.get("id"),
            "status": status,
            "adopted": is_adopted,
            "rewardPoints": points,
        })
    return {
        "marker": "changying_v1_feedback_reward_points_v1",
        "pointsPerAdopted": FEEDBACK_REWARD_POINTS_PER_ADOPTED,
        "adoptedCount": adopted,
        "totalRewardPoints": adopted * FEEDBACK_REWARD_POINTS_PER_ADOPTED,
        "redeemTarget": FEEDBACK_REWARD_REDEEM_TARGET,
        "redeemRate": None,
        "items": items,
    }


def feedback_records_dropdown_payload(records: list[dict] | None = None) -> dict:
    """反馈 #320 追加反馈 #1：助手内“我要反馈”下拉直接展示反馈记录。

    返回下拉所需的记录列表与状态字段（取用/回执/奖励分），并声明追加反馈
    支持图片上传。该函数是前端下拉与回归测试的唯一契约来源。
    """
    items = []
    for row in list(records or []):
        if not isinstance(row, dict):
            continue
        items.append({
            "feedbackId": row.get("feedbackId") or row.get("id"),
            "message": str(row.get("message") or "")[:200],
            "status": str(row.get("status") or "已提交"),
            "receipt": str(row.get("receipt") or ""),
            "rewardPoints": int(row.get("rewardPoints") or 0),
            "followUpCount": int(row.get("followUpCount") or 0),
            "followUpEndpoint": FEEDBACK_PATH + "/{feedback_id}/follow-up",
            "followUpAttachmentField": "attachment_data",
            "followUpAttachmentTypes": ("image/jpeg", "image/png", "image/webp"),
            "followUpAttachmentMaxBytes": FEEDBACK_ATTACHMENT_MAX_BYTES,
        })
    return {
        "marker": UNIFIED_FEEDBACK_RECORDS_MARKER,
        "recordsEndpoint": FEEDBACK_MINE_PATH,
        "recordsListedInDropdown": True,
        "recordsShowStatus": ("取用", "回执", "奖励分"),
        "followUpImageUpload": True,
        "items": items,
    }


def unified_feedback_records_contract() -> dict:
    """反馈 #321/#322：助手内唯一反馈记录入口的对外契约。

    顶部“反馈记录”面板不再单独渲染，其全部功能（提交、附件、回执、奖励分、
    追加反馈）合并进助手内“提反馈”按钮的下拉；点击“提反馈”时自动下拉显示
    反馈记录，追加反馈同样支持发送图片附件。
    """
    return {
        "marker": UNIFIED_FEEDBACK_RECORDS_MARKER,
        "mergedIntoAssistant": FEEDBACK_RECORDS_MERGED_INTO_ASSISTANT,
        "topPanelHidden": FEEDBACK_TOP_PANEL_HIDDEN,
        "sharedButton": FEEDBACK_RECORDS_SHARED_BUTTON,
        "autoExpandOnSubmit": FEEDBACK_RECORDS_AUTO_EXPAND_ON_SUBMIT,
        "dropdownActions": list(FEEDBACK_SUBMIT_DROPDOWN_ACTIONS),
        "fullFeatures": list(FEEDBACK_RECORDS_FULL_FEATURES),
        "followUpAttachmentSupported": True,
        # 反馈 #320 追加反馈 #1：进入助手点击“我要反馈”时，下拉应直接展示
        # 反馈记录列表（取用/回执/奖励分），并允许对单条记录追加反馈且支持上传图片。
        "recordsListedInDropdown": True,
        "recordsShowStatus": ("取用", "回执", "奖励分"),
        "followUpImageUpload": True,
        "followUpEndpoint": FEEDBACK_PATH + "/{feedback_id}/follow-up",
        # 反馈 #320 追加反馈 #1：助手内“我要反馈”下拉必须直接列出反馈记录，
        # 每条记录可查看取用/回执/奖励分状态，并可对单条记录追加反馈（含图片上传）。
        "recordsDropdownEndpoint": FEEDBACK_MINE_PATH,
        "followUpAttachmentField": "attachment_data",
        "followUpAttachmentMaxBytes": FEEDBACK_ATTACHMENT_MAX_BYTES,
        "followUpAttachmentTypes": ("image/jpeg", "image/png", "image/webp"),
        "recordsListedOnSubmitClick": True,
    }
FREEMAN_FEEDBACK_IMPORT_URL = "https://freeman-agent.onrender.com/api/project-feedback/import"
FREEMAN_FEEDBACK_STATUS_URL = "https://freeman-agent.onrender.com/api/project-feedback/status"
FEEDBACK_PROOF_TTL_MINUTES = 15
FEEDBACK_ATTACHMENT_MAX_BYTES = 1_000_000
FEEDBACK_GITHUB_REPO = "liveeon8635-crypto/-primary-school-quiz-v7"
FEEDBACK_GITHUB_TOKEN_ENV = "CHANGYING_FEEDBACK_GITHUB_TOKEN"
_logger = logging.getLogger(__name__)


def _post_feedback_import(proof_token: str, feedback_id: int | None = None) -> bool:
    last_status = None
    for attempt in range(1, 4):
        try:
            response = requests.post(FREEMAN_FEEDBACK_IMPORT_URL, json={"projectId": "longying", "proofToken": proof_token}, timeout=8)
            last_status = response.status_code
            if response.ok:
                _logger.info("freeman_feedback_sync_ok feedback_id=%s attempt=%s status=%s", feedback_id, attempt, last_status)
                return True
        except requests.RequestException as exc:
            _logger.warning("freeman_feedback_sync_retry feedback_id=%s attempt=%s error=%s", feedback_id, attempt, type(exc).__name__)
    _logger.error("freeman_feedback_sync_failed feedback_id=%s status=%s", feedback_id, last_status)
    return False

def _freeman_feedback_status(refs: list[dict]) -> dict[str, dict]:
    safe_refs=[]
    for ref in refs[:100]:
        source_id=str(ref.get("sourceId") or "").strip()
        token=str(ref.get("statusToken") or "").strip()
        if source_id.isdigit() and 24 <= len(token) <= 96:
            safe_refs.append({"sourceId": source_id, "statusToken": token})
    if not safe_refs:
        return {}
    try:
        response=requests.post(FREEMAN_FEEDBACK_STATUS_URL,json={"projectId":"longying","refs":safe_refs},timeout=4)
        if response.status_code != 200:
            return {}
        payload=response.json()
        return {str(item.get("sourceId")):item for item in list(payload.get("items") or []) if item.get("sourceId")}
    except Exception:
        return {}



def reconcile_persisted_feedback_handoff(implementation: ModuleType, feedback_id: int) -> bool:
    """Re-issue proof and replay one persisted feedback revision through normal Freeman verification."""
    SessionLocal = getattr(implementation, "SessionLocal", None)
    if SessionLocal is None:
        raise RuntimeError("production implementation does not expose SessionLocal")
    with SessionLocal() as db:
        row = db.scalar(
            select(implementation.AuditLog).where(
                implementation.AuditLog.id == feedback_id,
                implementation.AuditLog.action.in_(("product.feedback", "product_feedback")),
            )
        )
        if not row:
            return False
        try:
            detail = json.loads(row.detail or "{}")
        except (ValueError, TypeError):
            return False
        if not list(detail.get("followUps") or []):
            return False
        proof_token = secrets.token_urlsafe(24)
        detail["transferToken"] = proof_token
        detail["transferTokenAt"] = datetime.utcnow().isoformat() + "Z"
        row.detail = json.dumps(detail, ensure_ascii=False)
        db.commit()
        synced = _post_feedback_import(proof_token, int(row.id))
        _logger.info("freeman_feedback_production_reconcile feedback_id=%s revision=%s synced=%s", row.id, detail.get("revision"), synced)
        return synced


def _sync_feedback_github_issue(audit_row, payload: dict) -> dict | None:
    """Best-effort whiteboard sync. Feedback persistence never depends on GitHub."""
    token = os.getenv(FEEDBACK_GITHUB_TOKEN_ENV, "").strip()
    repo = os.getenv("CHANGYING_FEEDBACK_GITHUB_REPO", FEEDBACK_GITHUB_REPO).strip() or FEEDBACK_GITHUB_REPO
    if not token or not audit_row:
        _logger.warning("feedback_issue_sync_skipped reason=missing_token_or_audit feedback_id=%s", getattr(audit_row, "id", None))
        return None
    message = str(payload.get("message") or "").strip()
    summary = " ".join(message.split())[:30] or "用户反馈"
    created = getattr(audit_row, "created_at", None) or datetime.utcnow()
    source_page = str(payload.get("page") or "").strip() or "/v1/feedback"
    issue_payload = {
        "title": f"[User Feedback] {summary}",
        "body": (
            "## 用户反馈\n" + message
            + "\n\n## 提交信息\n"
            + f"- 提交时间: {created.isoformat()}Z\n"
            + f"- 来源页面: {source_page}\n"
            + f"- 关联反馈 ID: {int(audit_row.id)}\n"
        ),
        "labels": ["user-feedback", "need-freeman-agent"],
    }
    try:
        response = requests.post(
            f"https://api.github.com/repos/{repo}/issues",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json=issue_payload,
            timeout=4,
        )
        response.raise_for_status()
        result = response.json()
        return {"issue_number": int(result["number"]), "issue_url": str(result["html_url"])}
    except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
        _logger.warning("feedback_issue_sync_failed feedback_id=%s error=%s", getattr(audit_row, "id", None), type(exc).__name__)
        return None



class ProductAssistantBody(BaseModel):
    question: str = Field(min_length=1, max_length=1600)
    page: str = Field(default="", max_length=240)
    identity: str = Field(default="", max_length=160)
    tutorial_step: str = Field(default="", max_length=200)
    child_id: int | None = None
    active_assessment: bool = False
    active_question_text: str = Field(default="", max_length=1600)
    active_question_options: list[str] = Field(default_factory=list, max_length=8)
    active_question_meta: str = Field(default="", max_length=500)
    active_question_figure: str = Field(default="", max_length=900)
    active_question_position: str = Field(default="", max_length=80)
    active_question_response: str = Field(default="", max_length=600)
    image_name: str = Field(default="", max_length=240)
    image_type: str = Field(default="", max_length=120)
    image_size: int = Field(default=0, ge=0, le=FEEDBACK_ATTACHMENT_MAX_BYTES)
    image_data: str = Field(default="", max_length=1_400_000)


def _image_failure_reason(exc: Exception) -> str:
    if not isinstance(exc, HTTPException):
        return "internal_error"
    detail = str(exc.detail or "").lower()
    if exc.status_code == 429:
        return "hourly_limit"
    if exc.status_code == 504:
        return "provider_timeout"
    if exc.status_code == 503:
        return "ai_not_configured"
    if any(term in detail for term in ("insufficient_quota", "quota", "credits", "余额", "额度")):
        return "provider_quota"
    if any(term in detail for term in ("invalid_api_key", "authentication", "unauthorized", "api key")):
        return "provider_auth"
    if any(term in detail for term in ("vision", "image", "multimodal", "unsupported", "看图", "图片")):
        return "vision_model_unsupported"
    return "provider_error"


class ProductFeedbackBody(BaseModel):
    category: str = Field(default="其他反馈", max_length=60)
    message: str = Field(min_length=1, max_length=1200)
    page: str = Field(default="", max_length=240)
    identity: str = Field(default="", max_length=160)
    tutorial_step: str = Field(default="", max_length=200)
    attachment_name: str = Field(default="", max_length=240)
    attachment_type: str = Field(default="", max_length=120)
    attachment_size: int = Field(default=0, ge=0, le=FEEDBACK_ATTACHMENT_MAX_BYTES)
    attachment_data: str = Field(default="", max_length=1_400_000)


class ProductFeedbackFollowUpBody(BaseModel):
    message: str = Field(min_length=1, max_length=1200)
    attachment_name: str = Field(default="", max_length=240)
    attachment_type: str = Field(default="", max_length=120)
    attachment_size: int = Field(default=0, ge=0, le=FEEDBACK_ATTACHMENT_MAX_BYTES)
    attachment_data: str = Field(default="", max_length=1_400_000)


_PRODUCT_CONTEXT = """你是“长缨辅学”的站内学习与产品助手。你既帮助用户理解长缨怎么用，也要根据账号身份采用不同的沟通方式。

共同原则：
1. 学生始终是一份连续档案；换班、换教师、换学期、升年级不应重新创建学生。
2. 当前教学负责正在发生的教学；历史教学负责只读回看；升年级/升学用衔接记录表达阶段变化。
3. 教师主线：当前教学→学生连续档案→综合/模块测试或练习→教师审核布置→学生提交→分数/知识点/错题/积分回流→AI针对性练习→课堂复盘讲义→互动课堂/随堂检测→历史/升年级衔接。
4. 学生主线：课堂→作业→逐题作答→提交结果→针对性练习→学情→积分/错题/历史。
5. 家长主线：孩子课程→孩子作业→孩子学情→课堂表现/积分→连续档案与历史。
6. 管理员主线：平台总览→账号→班级与教学归属→积分规则→审计→系统设置→历史连续性。
7. 教师审核是重要边界；AI 可以生成建议或草稿，但不应自动替教师发布、评分确认或推进课堂。
8. 只能使用当前账号有权看到、并明确提供在“角色内学习数据”中的事实；不要编造学生、班级、成绩、按钮或已经发生的操作。
9. 用户问“我现在该做什么”时，根据身份、页面和新手步骤给 1-3 个明确动作；用户描述产品问题时，先解释当前功能，再指出应去哪个入口。
10. 回答简洁、友好、可执行，不贴标签、不羞辱、不用同伴比较刺激用户。
11. 产品反馈页可附一张照片或一个小文件；产品助手对话也可附图提问。学生在答题页时优先使用已经关联的当前题目和图示可见文字，不要求为解题上传照片。
12. 知识模块练习与教材版本：默认对齐最新人教版（2024 修订）小学教材。五年级数学知识模块以最新人教版为准，例如“简易方程”属于五年级下册，“位置”属于五年级上册（用数对确定位置）；旧版教材中“简易方程/位置”的年级或册次安排如与最新人教版不一致，一律以最新人教版为准，不得沿用旧版编排。回答知识模块、年级或册次问题时，先说明所依据的是最新人教版，再给出模块与册次对应关系；若不确定具体册次，明确说明不确定，不要编造。

学生模式：
- 除了介绍长缨功能，也允许学生问学科知识、错题思路和“为什么”。优先把问题拆成小步骤，连接到生活例子、已有知识或一个小挑战，帮助学生产生兴趣。
- 对学习问题采用“先判断卡点→给一条有用提示/类比→让学生完成下一小步→再继续”的方式；不要只反问，也不要一次把完整解题过程全部倒给学生。
- 如果学生在作业、练习、测验场景索要最终答案、正确选项、标准答案或要求代做，不直接给答案。可以解释概念、指出题目条件、给相似例子、提供检查方法，并邀请学生先完成下一步。
- 学生做完或暴露薄弱点后，优先引导到“我的错题 / 自主练习 / 我的学情 / 同步课堂”等对应功能继续巩固，而不是把对话变成脱离长缨的通用聊天。
- 如果只是问一个独立知识概念，可以正常解释，但尽量附带一个引导思考的小问题或小例子。

家长模式：
- 优先使用当前绑定孩子的真实学习数据回答“最近怎么样”等问题：先说一个具体事实或进步，再说一个值得关注的点，最后给 1-2 个可在家庭执行的小建议。
- 家庭建议以鼓励、作息、复述思路、短时巩固、让孩子自己讲明白为主；不要鼓励家长代做作业或直接给答案。
- 不给孩子下能力、性格或心理标签，不把一次成绩当作长期结论，不拿孩子和其他学生比较。
- 需要深入时，引导家长去“孩子学情 / 孩子作业 / 课堂表现 / 孩子课程”查看对应证据。

教师和管理员模式：
- 保持产品与工作流导向，优先解释功能、数据来源、操作边界和下一步入口。
"""

# 人教版小学数学教材版本对齐表（2024 年秋季最新版）。
# 反馈 #304：五年级“知识模块练习”中的“简易方程”和“位置”在最新人教版教材中已改版，
# 旧版把“简易方程”放在五年级上册、“位置”放在五年级上册用数对确定位置；
# 最新人教版把“简易方程”调整到五年级上册并强化等式性质与解方程步骤，
# “位置”调整为五年级上册“用数对确定位置”并新增“在方格纸上用数对确定位置”的进阶要求。
# 该表用于让产品助手与知识模块练习按最新教材版本回答和呈现，避免继续使用旧版目录。
PEOPLE_EDUCATION_TEXTBOOK_ALIGNMENT = {
    "version": "人教版（2024 年秋季最新版）",
    "grade": "五年级",
    "modules": {
        "简易方程": {
            "textbook": "人教版五年级上册 第五单元",
            "status": "updated",
            "notes": "最新版强化等式性质与解方程的一般步骤，先学用字母表示数，再学方程意义与解法。",
        },
        "位置": {
            "textbook": "人教版五年级上册 第二单元",
            "status": "updated",
            "notes": "最新版为“用数对确定位置”，并新增在方格纸上用数对确定位置的进阶要求。",
        },
    },
}


def knowledge_module_textbook_alignment(module_name: str) -> dict | None:
    """返回指定知识模块在最新人教版教材中的对齐信息；未知模块返回 None。"""
    key = str(module_name or "").strip()
    return PEOPLE_EDUCATION_TEXTBOOK_ALIGNMENT["modules"].get(key)


def _clean_assistant_reply(value: str) -> str:
    text = str(value or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u200b", "").replace("\ufeff", "").replace("\ufffd", "")
    text = re.sub(r"```[A-Za-z0-9_-]*\s*", "", text)
    text = text.replace("```", "")
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    text = text.replace("`", "")
    text = re.sub(r"(?m)^\s*[-*+]\s+", "• ", text)
    text = re.sub(r"(?m)^\s*(?:[-_=*#]){3,}\s*$", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"([!?！？。])\1{2,}", r"\1", text)
    return text.strip()

def _student_direct_answer_request(
    question: str,
    page: str = "",
    active_assessment: bool = False,
) -> bool:
    text = (question or "").strip().lower()
    if any(
        k in text
        for k in (
            "直接告诉我答案",
            "直接给我答案",
            "把答案给我",
            "答案是什么",
            "答案是",
            "正确答案",
            "标准答案",
            "抄答案",
            "代做",
            "帮我选",
            "给我选",
            "直接说",
        )
    ):
        return True
    in_assessment = bool(active_assessment) or any(k in (page or "") for k in ("assignments", "practice", "quiz", "assessment", "test"))
    academic_hint = in_assessment or any(k in text for k in ("这题", "题目", "作业", "练习", "测验", "考试", "选择题"))
    if academic_hint and any(k in text for k in ("选哪个", "应该选哪个", "第几项")):
        return True
    return in_assessment and any(k in text for k in ("答案", "直接算出", "直接做完", "告诉我结果"))


def _active_question_context(body: ProductAssistantBody) -> str:
    if not body.active_question_text.strip():
        return "当前没有检测到正在作答的题目。"
    options = [
        str(item).strip()
        for item in body.active_question_options[:8]
        if str(item).strip()
    ]
    option_text = "；".join(options) if options else "无可见选项"
    response = body.active_question_response.strip() or "学生尚未填写/选择"
    position = body.active_question_position.strip() or "当前题"
    meta = body.active_question_meta.strip() or "无额外题目信息"
    return (
        "当前正在作答上下文（只包含学生屏幕当前可见信息，不含正确答案或解析）："
        f"位置={position}；题干={body.active_question_text.strip()}；"
        f"可见选项={option_text}；题目信息={meta}；"
        f"题目图示可见文字={body.active_question_figure.strip() or '无'}；"
        f"学生当前输入/选择={response}。"
        "如果仍在提交前，不得确认、暗示或排除某个选项是否正确，也不得给出最终数值结果。"
        "可以帮助识别已知条件、解释概念、指出第一步、给相似例子或检查方法。"
        "如果学生只说“这题不会/帮我看看”，直接基于这道当前题帮助，不要要求他重新粘贴题目。"
    )


def _assignment_counts(implementation: ModuleType, db, student_id: int, school_id: int) -> tuple[int, int]:
    try:
        recipient = implementation.AssignmentRecipient
        assignment = implementation.Assignment
        rows = db.scalars(
            select(recipient)
            .where(recipient.school_id == school_id, recipient.student_id == student_id)
            .order_by(recipient.assignment_id.desc())
            .limit(80)
        ).all()
        pending = overdue = 0
        for row in rows:
            item = db.scalar(
                select(assignment).where(
                    assignment.id == row.assignment_id,
                    assignment.school_id == school_id,
                )
            )
            if not item:
                continue
            status = implementation.assignment_effective_status(db, item, student_id)
            if not status.get("completed"):
                pending += 1
            if status.get("overdue"):
                overdue += 1
        return pending, overdue
    except Exception:
        return 0, 0


def _knowledge_summary(progress: dict) -> tuple[str, str]:
    items = [x for x in (progress.get("knowledge") or []) if int(x.get("answered") or 0) > 0]
    weakest = items[:3]
    strongest = sorted(items, key=lambda x: (int(x.get("accuracy") or 0), str(x.get("knowledge") or "")), reverse=True)[:2]
    weak_text = "、".join(f"{x.get('knowledge')} {x.get('accuracy')}%" for x in weakest) or "暂无足够数据"
    strong_text = "、".join(f"{x.get('knowledge')} {x.get('accuracy')}%" for x in strongest) or "暂无足够数据"
    return strong_text, weak_text


def _student_learning_context(implementation: ModuleType, db, user) -> str:
    try:
        progress = implementation.progress_for(db, user.id, user.school_id)
        current_class = implementation.current_class_for(db, user.id, user.school_id)
        pending, overdue = _assignment_counts(implementation, db, user.id, user.school_id)
        strong, weak = _knowledge_summary(progress)
        latest = progress.get("latestSubmission") or {}
        points = implementation.point_summary(db, user.id, user.school_id)
        weekly = implementation.student_period_points(db, user.id, user.school_id, 7)
        badges = implementation.student_growth_badges(db, user.id, user.school_id) or []
        badge_text = "、".join(str(x.get("name") or "") for x in badges[:3] if x.get("name")) or "暂无"
        latest_text = (
            f"{latest.get('subject') or '未标科目'}《{latest.get('title') or '最近练习'}》"
            f"{latest.get('score', 0)}分，{latest.get('submittedAt') or '时间未记录'}"
            if latest
            else "暂无提交记录"
        )
        return (
            "当前学生可见学习摘要："
            f"年级={getattr(user, 'grade', '') or '未设置'}；班级={getattr(current_class, 'name', '') or '未分班'}；"
            f"长期平均分={progress.get('avgScore', 0)}；累计练习={progress.get('submissions', 0)}；累计答题={progress.get('totalAnswered', 0)}；"
            f"最近一次={latest_text}；待完成作业={pending}；逾期={overdue}；"
            f"掌握较好={strong}；当前宜巩固={weak}；"
            f"当前可用积分={points.get('available', 0)}；近7天净表现={weekly.get('net', 0)}；成长徽章={badge_text}。"
            "这些数据只用于帮助学生理解自己的学习与选择长缨功能，不包含任何题目标准答案。"
        )
    except Exception:
        return "当前学生学习摘要暂时不可用；只能依据当前页面和学生自己提供的信息进行引导。"


def _parent_learning_context(
    implementation: ModuleType,
    db,
    user,
    child_id: int | None,
    question: str,
) -> str:
    try:
        child = implementation.User
        link = implementation.ParentStudent
        children = db.scalars(
            select(child)
            .join(link, link.student_id == child.id)
            .where(
                link.parent_id == user.id,
                child.school_id == user.school_id,
                child.role == "student",
            )
            .order_by(child.id)
        ).all()
        if not children:
            return "当前家长账号尚未绑定学生。"

        target = next((x for x in children if child_id and x.id == child_id), None)
        if target is None:
            named = [x for x in children if x.name and x.name in (question or "")]
            target = named[0] if named else children[0]

        progress = implementation.progress_for(db, target.id, user.school_id)
        current_class = implementation.current_class_for(db, target.id, user.school_id)
        pending, overdue = _assignment_counts(implementation, db, target.id, user.school_id)
        strong, weak = _knowledge_summary(progress)
        latest = progress.get("latestSubmission") or {}
        points = implementation.point_summary(db, target.id, user.school_id)
        weekly = implementation.student_period_points(db, target.id, user.school_id, 7)
        advice = implementation.student_growth_advice(db, target.id, user.school_id) or []
        advice_text = "；".join(str(x) for x in advice[:2]) or "暂无系统成长建议"
        latest_text = (
            f"{latest.get('subject') or '未标科目'}《{latest.get('title') or '最近练习'}》"
            f"{latest.get('score', 0)}分，{latest.get('submittedAt') or '时间未记录'}"
            if latest
            else "暂无提交记录"
        )
        return (
            f"当前家长已绑定{len(children)}名学生；本次默认/选中孩子={target.name}。"
            f"年级={target.grade or '未设置'}；班级={getattr(current_class, 'name', '') or '未分班'}；"
            f"长期平均分={progress.get('avgScore', 0)}；累计练习={progress.get('submissions', 0)}；累计答题={progress.get('totalAnswered', 0)}；"
            f"最近一次={latest_text}；待完成作业={pending}；逾期={overdue}；"
            f"掌握较好={strong}；当前宜巩固={weak}；"
            f"当前可用积分={points.get('available', 0)}；近7天净表现={weekly.get('net', 0)}；"
            f"系统成长建议={advice_text}。"
            "回答家长时只围绕这些已授权事实，不推断孩子未记录的状态。"
        )
    except Exception:
        return "当前孩子学习摘要暂时不可用；只能依据当前页面和家长自己提供的信息进行建议。"


def _role_learning_context(
    implementation: ModuleType,
    db,
    user,
    child_id: int | None,
    question: str,
) -> str:
    role = str(getattr(user, "role", "") or "")
    if role == "student":
        return _student_learning_context(implementation, db, user)
    if role == "parent":
        return _parent_learning_context(implementation, db, user, child_id, question)
    return "当前角色不注入学生个人学习数据；按产品功能与当前页面回答。"


_GUIDANCE_CARDS = (
    {
        "key": "paper_import_saved",
        "title": "导入试卷保存在哪里",
        "description": "导入的试卷保存在「组卷与作业」，题目同时进入教材题库（按你填写的单元）。",
        "path": "/v1/tool?page=papers",
        "keywords": ("导入试卷", "导入的试卷", "保存到哪", "试卷保存", "找不到导入", "导入后"),
    },
    {
        "key": "catalog_questions",
        "title": "教材题库（查看导入的题目）",
        "description": "导入的题目都在教材题库，最新的在最前；可按年级、科目、教材、单元筛选或搜索。",
        "path": "/v1/tool?page=catalog",
        "keywords": ("教材题库", "导入的题目", "上传的题目", "查题目", "查看题目", "题库在哪", "导入试卷", "导入的试卷", "保存到哪"),
    },
    {
        "key": "homework_create",
        "title": "组卷作业",
        "description": "进入组卷与作业工具，新建题目后布置给当前班级或课程。",
        "path": "/v1/tool?page=papers",
        "keywords": ("布置作业", "新建作业", "发布作业", "作业在哪里", "组卷作业", "组卷"),
    },
    {
        "key": "current_teaching",
        "title": "当前教学",
        "description": "查看正在进行的班级、作业与课堂，从这里开始今天的教学。",
        "path": "/v1/teaching",
        "keywords": ("当前教学", "今天", "上课", "布置", "作业", "班级"),
    },
    {
        "key": "student_profile",
        "title": "学生连续档案",
        "description": "同一学生的成绩、错题、知识点、积分与课堂表现长期累积。",
        "path": "/v1/student",
        "keywords": ("学生", "档案", "学情", "成绩", "错题", "知识点", "积分"),
    },
    {
        "key": "targeted_practice",
        "title": "AI 针对性练习",
        "description": "基于最近测试与错题生成练习，教师审核后再布置。",
        "path": "/v1/practice",
        "keywords": ("针对性", "ai练习", "ai 练习", "练习", "巩固"),
    },
    {
        "key": "classroom_review",
        "title": "课堂复盘与互动课堂",
        "description": "汇总班级练习数据，生成复盘讲义并开放随堂检测。",
        "path": "/v1/classroom",
        "keywords": ("课堂", "复盘", "讲义", "互动", "随堂", "检测"),
    },
    {
        "key": "history_transition",
        "title": "历史与升年级衔接",
        "description": "换班或升年级不会重建学生，历史与衔接继续引用同一学生 ID。",
        "path": "/v1/history",
        "keywords": ("历史", "升年级", "升学", "衔接", "换班"),
    },
    {
        "key": "product_assistant",
        "title": "产品助手",
        "description": "打开产品助手，询问产品功能并通过关联卡片直达对应页面。",
        "path": "/v1/workspace?tab=ask",
        "keywords": ("产品助手", "助手", "产品引导", "关联卡片", "导航卡片", "功能卡片", "问产品", "产品功能"),
    },
    {
        "key": "feedback",
        "title": "提交产品反馈",
        "description": "遇到问题或希望增加功能，可直接提交反馈并附一张照片或文件。",
        "path": "/v1/workspace",
        "keywords": ("反馈", "建议", "问题", "功能", "增加"),
    },
    {
        "key": "feedback_records",
        "title": "我的反馈记录",
        "description": "查看我提交过的每条反馈、处理回执与反馈奖励分状态。",
        "path": FEEDBACK_PAGE_PATH,
        "keywords": (
            "反馈记录", "我的反馈", "提过什么反馈", "回执", "反馈奖励", "反馈状态", "查反馈",
            "历史记录", "处理状况", "追加反馈", "奖励明细",
        ),
    },
)


def _feedback_acceptance_path(detail: dict) -> str:
    """Choose the product surface the user should actually inspect.

    Feedback is commonly submitted from the assistant workspace, so using the
    raw submission page would send every acceptance check back to the generic
    workspace/new-user flow. Keep a concrete non-workspace source page, but
    resolve workspace-origin feedback by the feedback text to a specific
    product surface. When no specific surface can be inferred, return to the
    feedback records rather than the tutorial.
    """
    source_page = str(detail.get("page") or "").strip()

    text_parts = [str(detail.get("message") or "")]
    for followup in list(detail.get("followUps") or []):
        if isinstance(followup, dict):
            text_parts.append(str(followup.get("message") or ""))
    text = " ".join(text_parts).lower()

    # High-specificity product concepts override the raw source page. A user
    # can submit assistant/navigation feedback while physically viewing a
    # student page; acceptance must validate the feature being discussed, not
    # merely the page that happened to be open when the report was filed.
    if any(term in text for term in (
        "反馈记录", "追加反馈", "反馈回执", "反馈中心",
        "反馈奖励", "奖励分", "兑换账号时长", "兑换帐号时长", "账号时长", "帐号时长",
    )):
        return FEEDBACK_PAGE_PATH
    if any(term in text for term in (
        "产品助手", "助手", "关联卡片", "导航卡片", "功能卡片",
        "产品引导", "问产品", "智能助手",
    )):
        return "/v1/workspace?tab=ask"

    if source_page.startswith("/") and not source_page.startswith("/v1/workspace"):
        return source_page[:240]

    candidates = []
    for index, card in enumerate(_GUIDANCE_CARDS):
        if card["key"] in ("feedback", "current_teaching"):
            continue
        score = sum(1 for kw in card["keywords"] if kw.lower() in text)
        if score:
            longest = max((len(kw) for kw in card["keywords"] if kw.lower() in text), default=0)
            candidates.append((score, longest, -index, card["path"]))
    if candidates:
        candidates.sort(reverse=True)
        return str(candidates[0][3])

    return FEEDBACK_PAGE_PATH


# 反馈 #314：功能咨询应返回可点击的精准导航卡片；不是把所有功能卡片堆给用户。
FEATURE_NAVIGATION_CARD_MARKER = "changying_v1_precise_feature_navigation_card_v1"


def _guidance_cards(question: str, page: str = "", limit: int = 3) -> list[dict]:
    text = f"{question or ''} {page or ''}".lower()
    scored: list[tuple[int, int, dict]] = []
    for index, card in enumerate(_GUIDANCE_CARDS):
        score = sum(1 for kw in card["keywords"] if kw.lower() in text)
        if score:
            scored.append((score, index, card))
    scored.sort(key=lambda item: (-item[0], item[1]))
    if scored:
        best_score = scored[0][0]
        # Specific multi-word intents must win over generic cards on score ties.
        max_keyword_len = max(
            max((len(kw) for kw in card["keywords"] if kw.lower() in text), default=0)
            for score, _, card in scored if score == best_score
        )
        chosen = [
            card for score, _, card in scored
            if score == best_score
            and max((len(kw) for kw in card["keywords"] if kw.lower() in text), default=0) == max_keyword_len
        ][:limit]
    else:
        chosen = [card for card in _GUIDANCE_CARDS if card["key"] in ("current_teaching", "student_profile", "feedback")]
    return [
        {"key": c["key"], "title": c["title"], "description": c["description"], "path": c["path"]}
        for c in chosen
    ]

def _local_answer(
    question: str,
    identity: str,
    page: str,
    tutorial_step: str,
    role: str = "",
    learning_context: str = "",
) -> str:
    text = question.strip()
    context = f"当前身份：{identity or '已登录身份'}；当前页面：{page or 'V1'}"
    if tutorial_step:
        context += f"；新手步骤：{tutorial_step}"

    if role == "student" and _student_direct_answer_request(text, page):
        return (
            "我不直接替你提取作业或练习的最终答案，但可以陪你把题拆开。"
            "先把题目里“已知什么、要求什么”各说一句；如果你卡住，我会先帮你标出关键条件，再给一条提示。"
            "做完后可以去“我的错题”或“自主练习”再用一道相似题检查自己是不是真的会了。"
        )
    if role == "student" and any(k in text for k in ("不会", "怎么做", "为什么", "知识点", "这题", "题目")):
        return (
            "可以问我学习问题。我们不急着拿答案：先说你卡在哪一步，我会把它拆成一个小目标，"
            "给你一条提示或生活里的例子，再让你试下一步。完成后还可以用“我的错题 / 自主练习 / 我的学情”继续巩固。"
        )
    if role == "parent" and any(k in text for k in ("最近", "怎么样", "学情", "学习情况", "进步", "在家", "配合", "鼓励")):
        base = learning_context if learning_context else "当前孩子学习摘要暂时不可用。"
        return (
            f"{base} 家庭配合上建议先肯定一个具体进步，再只选一个薄弱点做10分钟左右的短巩固；"
            "让孩子先讲思路，家长主要追问“你为什么这么想”，尽量不要直接代做。"
            "需要证据时可打开“孩子学情”“孩子作业”或“课堂表现”。"
        )

    if any(k in text for k in ("上传的题目", "导入的题目", "查题目", "查看题目", "题库在哪", "教材题库")):
        return (
            "导入的题目都在「教材题库」：最新导入的排在最前面，可以按年级、科目、教材、单元筛选，也可以搜索题干。"
            "如果找不到，先确认导入时选的年级、学科和填写的单元，再按这个单元筛选。"
        )
    if any(k in text for k in ("导入试卷", "导入的试卷", "保存到哪", "试卷保存", "找不到导入")):
        return (
            "导入试卷保存后，试卷在「组卷与作业」页；这些题同时进入「教材题库」，单元就是导入时填写的单元。"
            "保存成功时页面会弹出提示说明保存位置。找不到时，先确认当时填写的单元和学科，再到教材题库按这个单元查看。"
        )
    if any(k in text for k in ("现在该做", "下一步", "从哪里开始")):
        return (
            f"{context}。建议先按右上角“新手教学”的当前步骤继续，不要跳到其他功能。"
            "如果已经退出教学：教师从“当前教学”开始，学生从“作业/课堂”开始，家长从“孩子课程”开始，管理员从“平台总览”开始。"
        )
    if any(k in text for k in ("学生档案", "连续档案")):
        return "学生连续档案是长缨的主线：成绩、作业、错题、知识点、积分、课堂表现、家长关系和阶段变化都围绕同一个学生 ID 累积。"
    if any(k in text for k in ("针对性", "AI练习", "ai练习")):
        return "AI 针对性练习应基于最近测试、知识点正确率和具体错题生成；教师审核后再布置，学生提交后结果继续回流同一学生档案。"
    if any(k in text for k in ("课堂复盘", "讲义", "互动课堂", "随堂检测")):
        return "课堂链条是：班级练习数据汇总→教师决定生成复盘讲义→确认发布版本→选择讲解方式→需要时邀请学生→开放随堂检测→教师查看反馈并收口。系统不应自动发布或自动推进课堂。"
    if any(k in text for k in ("升年级", "升学", "历史")):
        return "升年级或换班不会重新建学生。当前教学关系发生变化，旧班级和旧学期进入历史；衔接计划继续引用同一个学生 ID。"
    return (
        f"{context}。我可以解释这个页面的用途、告诉你下一步怎么操作，或帮你定位当前身份对应功能。"
        "学生也可以问知识点和不会的题，家长可以问孩子最近的学习情况与家庭配合方式。"
        "如果你是在反馈产品问题，也可以切到“反馈”直接提交当前页面问题。"
    )

def _decode_feedback_attachment(body: ProductFeedbackBody) -> tuple[bytes, str, str] | None:
    if not body.attachment_data:
        if body.attachment_name or body.attachment_type or body.attachment_size:
            raise HTTPException(422, "附件内容缺失")
        return None
    name = re.sub(r"[\\/\x00-\x1f\x7f]", "_", body.attachment_name).strip(" .")
    mime = body.attachment_type.strip().lower()
    if not name or not mime or not body.attachment_size:
        raise HTTPException(422, "附件信息不完整")
    if not re.fullmatch(r"[A-Za-z0-9._\-\u4e00-\u9fff ]{1,120}", name):
        raise HTTPException(422, "附件名称无效")
    try:
        raw = base64.b64decode(body.attachment_data, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(422, "附件编码无效")
    if not raw or len(raw) != body.attachment_size or len(raw) > FEEDBACK_ATTACHMENT_MAX_BYTES:
        raise HTTPException(422, "附件大小无效或超过 1 MB")
    signatures = {
        "image/jpeg": raw.startswith(b"\xff\xd8\xff") and name.lower().endswith((".jpg", ".jpeg")),
        "image/png": raw.startswith(b"\x89PNG\r\n\x1a\n") and name.lower().endswith(".png"),
        "image/webp": raw.startswith(b"RIFF") and raw[8:12] == b"WEBP" and name.lower().endswith(".webp"),
        "application/pdf": raw.startswith(b"%PDF-") and name.lower().endswith(".pdf"),
        "text/plain": name.lower().endswith(".txt") and b"\x00" not in raw,
    }
    if mime == "text/plain":
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            signatures[mime] = False
    if not signatures.get(mime, False):
        raise HTTPException(422, "仅支持 JPG、PNG、WebP、PDF 或 UTF-8 TXT 文件")
    return raw, name, mime


def _decode_assistant_image(body: ProductAssistantBody) -> str | None:
    if not body.image_data and not (body.image_name or body.image_type or body.image_size):
        return None
    if body.image_type.strip().lower() not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(422, "对话图片仅支持 JPG、PNG 或 WebP")
    attachment = _decode_feedback_attachment(ProductFeedbackBody(
        message="图片提问", attachment_name=body.image_name,
        attachment_type=body.image_type, attachment_size=body.image_size,
        attachment_data=body.image_data,
    ))
    if not attachment:
        raise HTTPException(422, "图片内容缺失")
    raw, _, mime = attachment
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def install_v1_product_assistant_routes(implementation: ModuleType) -> None:
    app = implementation.app
    if getattr(app.state, "v1_product_assistant_routes_installed", False):
        return

    router = APIRouter()
    attachment_table = Table(
        "product_feedback_attachments", implementation.Base.metadata,
        Column("id", Integer, primary_key=True),
        Column("audit_id", Integer, ForeignKey("audit_logs.id"), unique=True, nullable=False),
        Column("school_id", Integer, ForeignKey("schools.id"), nullable=False),
        Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
        Column("file_name", String(120), nullable=False),
        Column("mime_type", String(120), nullable=False),
        Column("size_bytes", Integer, nullable=False),
        Column("sha256", String(64), nullable=False),
        Column("file_data", LargeBinary, nullable=False),
        Column("created_at", DateTime, default=datetime.utcnow, nullable=False),
    )
    followup_attachment_table = Table(
        "product_feedback_followup_attachments", implementation.Base.metadata,
        Column("id", Integer, primary_key=True),
        Column("audit_id", Integer, ForeignKey("audit_logs.id"), nullable=False),
        Column("follow_up_id", String(80), unique=True, nullable=False),
        Column("school_id", Integer, ForeignKey("schools.id"), nullable=False),
        Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
        Column("file_name", String(120), nullable=False),
        Column("mime_type", String(120), nullable=False),
        Column("size_bytes", Integer, nullable=False),
        Column("sha256", String(64), nullable=False),
        Column("file_data", LargeBinary, nullable=False),
        Column("created_at", DateTime, default=datetime.utcnow, nullable=False),
    )
    reward_table = Table(
        "product_feedback_rewards", implementation.Base.metadata,
        Column("id", Integer, primary_key=True),
        Column("audit_id", Integer, ForeignKey("audit_logs.id"), unique=True, nullable=False),
        Column("school_id", Integer, ForeignKey("schools.id"), nullable=False),
        Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
        Column("points", Integer, nullable=False, default=1),
        Column("status", String(20), nullable=False, default="pending"),
        Column("created_at", DateTime, default=datetime.utcnow, nullable=False),
    )
    # These extracted tables are registered after the legacy application's initial
    # metadata bootstrap. Create only these tables idempotently before routes use them.
    bind = implementation.engine
    attachment_table.create(bind=bind, checkfirst=True)
    followup_attachment_table.create(bind=bind, checkfirst=True)
    reward_table.create(bind=bind, checkfirst=True)

    @router.get(FEEDBACK_PAGE_PATH, response_class=HTMLResponse, include_in_schema=False)
    def product_feedback_page():
        """独立反馈记录页：可直达查看回执、奖励分、追加反馈与验收。"""
        feedback_center = Path(__file__).with_name("feedback_center.js").read_text(encoding="utf-8")
        html = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>我的反馈记录 · 长缨辅学</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f4f7fb;color:#172033;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
.cy-feedback-page{max-width:960px;margin:0 auto;padding:18px 14px 40px}
.cy-feedback-page-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}
.cy-feedback-page-head h1{margin:0;font-size:24px}.cy-feedback-page-head p{margin:4px 0 0;color:#667085;font-size:13px}
.cy-feedback-page-back{display:inline-flex;text-decoration:none;border:1px solid #d5deeb;background:#fff;color:#173a78;border-radius:10px;padding:9px 12px;font-weight:800;font-size:13px}
#cy-feedback-center-backdrop{position:static!important;display:block!important;background:transparent!important;padding:0!important}
#cy-feedback-center-modal{width:100%!important;max-height:none!important;border-radius:16px!important}
#cy-fc-close{display:none!important}
@media(max-width:640px){.cy-feedback-page{padding:10px 8px 28px}.cy-feedback-page-head h1{font-size:20px}}
</style>
</head>
<body data-feedback-page="standalone">
<main class="cy-feedback-page">
  <div class="cy-feedback-page-head">
    <div><h1>我的反馈记录</h1><p>查看取用状态、处理回执、反馈奖励分，并完成验收或追加反馈。</p></div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end">
      <a id="cy-feedback-back-records" class="cy-feedback-page-back" href="/v1/workspace?tab=feedback-records&from=feedback">返回助手反馈记录</a>
      <a id="cy-feedback-back-workspace" class="cy-feedback-page-back" href="/v1/workspace?from=feedback">返回工作台</a>
    </div>
  </div>
</main>
<script>""" + feedback_center + """</script>
<script>
if(window.ChangyingFeedbackCenter){window.ChangyingFeedbackCenter.open()}
const cyFeedbackParams=new URLSearchParams(location.search);
const cyFeedbackId=cyFeedbackParams.get('cy_feedback_review')||cyFeedbackParams.get('reviewed')||cyFeedbackParams.get('focus');
const cyFeedbackBack=document.getElementById('cy-feedback-back-records');
const cyFeedbackWorkspace=document.getElementById('cy-feedback-back-workspace');
if(cyFeedbackBack&&cyFeedbackId){
  cyFeedbackBack.href='/v1/workspace?tab=feedback-records&from=feedback&reviewed='+encodeURIComponent(cyFeedbackId)+'&focus='+encodeURIComponent(cyFeedbackId);
}
if(cyFeedbackWorkspace){
  cyFeedbackWorkspace.href='/v1/workspace?from=feedback'+(cyFeedbackId?'&reviewed='+encodeURIComponent(cyFeedbackId)+'&focus='+encodeURIComponent(cyFeedbackId):'');
}
</script>
</body>
</html>"""
        return HTMLResponse(
            html,
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )


    FEEDBACK_REWARD_GRANTED_REMOTE_STATUSES = {
        "selected", "processing", "needs_attention", "awaiting_acceptance", "resolved"
    }

    def _sync_feedback_reward_grants(db, rows, freeman_status: dict) -> bool:
        """Persist one reward point when Freeman has actually taken the feedback.

        New/unselected feedback remains pending. Once Freeman moves a feedback out
        of new into a taken/processing state, the pending row is promoted once to
        granted. audit_id uniqueness plus pending-only update makes this idempotent.
        """
        changed = False
        for row in rows:
            remote = freeman_status.get(str(int(row.id)), {})
            remote_status = str(remote.get("status") or "")
            if remote_status not in FEEDBACK_REWARD_GRANTED_REMOTE_STATUSES:
                continue
            result = db.execute(
                update(reward_table)
                .where(
                    reward_table.c.audit_id == int(row.id),
                    reward_table.c.status == "pending",
                )
                .values(status="granted")
            )
            if int(result.rowcount or 0) > 0:
                changed = True
        if changed:
            db.commit()
        return changed

    def _feedback_reward_summary(db, user) -> dict:
        reward_query = select(reward_table.c.points, reward_table.c.status).where(reward_table.c.school_id == user.school_id)
        if getattr(user, "role", "") != "admin":
            reward_query = reward_query.where(reward_table.c.user_id == user.id)
        rows = db.execute(reward_query).all()
        granted_rows = [r for r in rows if str(r[1]) == "granted"]
        pending_rows = [r for r in rows if str(r[1]) == "pending"]
        earned = sum(int(r[0] or 0) for r in granted_rows)
        pending = sum(int(r[0] or 0) for r in pending_rows)
        return {
            "earnedPoints": earned,
            "pendingPoints": pending,
            "totalPoints": earned + pending,
            "redeemable": earned,
            "adoptedFeedbackCount": len(granted_rows),
            "receivedFeedbackCount": len(granted_rows) + len(pending_rows),
            "statusHint": "每条反馈都有回执：已采纳的反馈显示奖励分，未采纳的反馈显示待处理回执。",
            "rule": "每条被采纳的产品反馈获得 1 个反馈奖励分；奖励分可用于兑换账号时长，兑换比例将根据总体数据消费情况确定。",
        }

    @router.get(FEEDBACK_MINE_PATH, include_in_schema=False)
    def product_feedback_mine(
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        """反馈记录：返回当前用户提交过的反馈、回执状态与反馈奖励分。"""
        audit = implementation.AuditLog
        audit_query = select(audit).where(
            audit.school_id == user.school_id,
            audit.action.in_(("product.feedback", "product_feedback")),
        )
        reward_query = select(reward_table.c.audit_id, reward_table.c.points, reward_table.c.status).where(
            reward_table.c.school_id == user.school_id
        )
        if getattr(user, "role", "") != "admin":
            audit_query = audit_query.where(audit.user_id == user.id)
            reward_query = reward_query.where(reward_table.c.user_id == user.id)
        rows = db.scalars(audit_query.order_by(audit.id.desc()).limit(100)).all()
        reward_rows = db.execute(reward_query).all()
        reward_by_audit = {int(r[0]): (int(r[1] or 0), str(r[2])) for r in reward_rows}
        status_refs = []
        for row in rows:
            try:
                status_detail = json.loads(row.detail or "{}")
            except (ValueError, TypeError):
                status_detail = {}
            status_refs.append({"sourceId": int(row.id), "statusToken": str(status_detail.get("transferToken") or "")})
        freeman_status = _freeman_feedback_status(status_refs)
        # Backfill pre-status-loop feedback cards lazily. Existing cards imported
        # before Freeman learned status-token hashes would otherwise return no
        # operator reply even though Freeman had already replied to the user.
        missing_ids = [int(row.id) for row in rows if str(int(row.id)) not in freeman_status]
        if missing_ids:
            refreshed_refs = []
            now = datetime.utcnow()
            for row in rows:
                if int(row.id) not in missing_ids:
                    continue
                try:
                    status_detail = json.loads(row.detail or "{}")
                except (ValueError, TypeError):
                    status_detail = {}
                proof_token = secrets.token_urlsafe(24)
                status_detail["transferToken"] = proof_token
                status_detail["transferTokenAt"] = now.isoformat() + "Z"
                row.detail = json.dumps(status_detail, ensure_ascii=False)
                refreshed_refs.append({"sourceId": int(row.id), "statusToken": proof_token})
            if refreshed_refs:
                db.commit()
                for ref in refreshed_refs:
                    _post_feedback_import(ref["statusToken"], int(ref["sourceId"]))
                freeman_status.update(_freeman_feedback_status(refreshed_refs))
        if _sync_feedback_reward_grants(db, rows, freeman_status):
            reward_rows = db.execute(reward_query).all()
            reward_by_audit = {
                int(r[0]): (int(r[1] or 0), str(r[2])) for r in reward_rows
            }
        records = []
        for row in rows:
            detail = {}
            try:
                detail = json.loads(row.detail or "{}")
            except (ValueError, TypeError):
                detail = {}
            points, reward_status = reward_by_audit.get(int(row.id), (0, "pending"))
            acknowledged = bool(detail.get("acknowledged"))
            remote = freeman_status.get(str(int(row.id)), {})
            remote_status = str(remote.get("status") or "")
            operator_reply = str(remote.get("operatorReply") or "")
            terminal_accepted = remote_status == "resolved"
            waiting_confirmation = remote_status == "awaiting_acceptance"
            status_label = (
                "已验收" if terminal_accepted else
                ("已处理 · 待你确认" if waiting_confirmation else
                 ("处理中" if remote_status in ("selected", "processing", "needs_attention") else
                  ("待处理" if remote_status == "new" else
                   ("已取用" if reward_status == "granted" else ("待处理" if reward_status == "pending" else "已收到")))))
            )
            receipt = operator_reply or str(detail.get("receipt") or "")
            if not receipt:
                receipt = "反馈已验收；如有新问题请提交新反馈" if terminal_accepted else ("反馈已处理，请确认是否达到预期" if waiting_confirmation else "已收到，等待处理回执")
            submitted_user = db.get(implementation.User, row.user_id) if getattr(row, "user_id", None) else None
            own = int(getattr(row, "user_id", 0) or 0) == int(user.id)
            records.append({
                "id": int(row.id),
                "submittedBy": str(getattr(submitted_user, "name", "") or getattr(submitted_user, "username", "") or ""),
                "canFollowUp": own and not terminal_accepted,
                "canConfirm": own and waiting_confirmation and str((remote.get("userDecision") or {}).get("status") or "") != "confirmed",
                "terminalAccepted": terminal_accepted,
                "freemanStatus": remote_status,
                "operatorReply": operator_reply,
                "userDecision": remote.get("userDecision"),
                "category": str(detail.get("category") or "其他反馈"),
                "message": str(detail.get("message") or ""),
                "page": str(detail.get("page") or ""),
                "acceptanceUrl": _feedback_acceptance_path(detail),
                "createdAt": row.created_at.isoformat() if getattr(row, "created_at", None) else "",
                "receipt": receipt,
                "rewardPoints": points,
                "rewardStatus": reward_status,
                "statusLabel": status_label,
                "acknowledged": acknowledged,
                "followUps": list(detail.get("followUps") or []),
                "issueNumber": detail.get("issue_number"),
                "issueUrl": str(detail.get("issue_url") or ""),
            })
        return {
            "ok": True,
            "records": records,
            "rewardSummary": _feedback_reward_summary(db, user),
        }

    def _owned_feedback(db, user, feedback_id: int):
        audit = implementation.AuditLog
        row = db.scalar(
            select(audit).where(
                audit.id == feedback_id,
                audit.school_id == user.school_id,
                audit.user_id == user.id,
                audit.action.in_(("product.feedback", "product_feedback")),
            )
        )
        if not row:
            raise HTTPException(404, "反馈记录不存在")
        return row

    @router.post(FEEDBACK_MINE_PATH + "/{feedback_id}/follow-up", include_in_schema=False)
    def product_feedback_follow_up(
        feedback_id: int,
        body: ProductFeedbackFollowUpBody,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        """向当前用户自己的已有反馈追加说明。"""
        row = _owned_feedback(db, user, feedback_id)
        try:
            detail = json.loads(row.detail or "{}")
        except (ValueError, TypeError):
            detail = {}
        remote = _freeman_feedback_status([{"sourceId": feedback_id, "statusToken": str(detail.get("transferToken") or "")}]).get(str(feedback_id), {})
        if str(remote.get("status") or "") == "resolved":
            raise HTTPException(409, "反馈已验收，请提交新反馈")
        follow_ups = list(detail.get("followUps") or [])
        now = datetime.utcnow()
        follow_up = {
            "id": f"{int(row.id)}-{int(detail.get('revision') or 1) + 1}",
            "message": body.message.strip(),
            "at": now.isoformat() + "Z",
        }
        attachment = _decode_feedback_attachment(ProductFeedbackBody(
            message=body.message,
            attachment_name=body.attachment_name,
            attachment_type=body.attachment_type,
            attachment_size=body.attachment_size,
            attachment_data=body.attachment_data,
        ))
        if attachment:
            raw, name, mime = attachment
            follow_up["attachment"] = {
                "name": name, "type": mime, "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
            db.execute(insert(followup_attachment_table).values(
                audit_id=row.id, follow_up_id=follow_up["id"], school_id=user.school_id, user_id=user.id,
                file_name=name, mime_type=mime, size_bytes=len(raw),
                sha256=follow_up["attachment"]["sha256"], file_data=raw,
            ))
        follow_ups.append(follow_up)
        proof_token = secrets.token_urlsafe(24)
        detail["followUps"] = follow_ups
        detail["revision"] = int(detail.get("revision") or 1) + 1
        detail["updatedAt"] = now.isoformat() + "Z"
        # Rotate the short-lived transfer token for this revision. Freeman never
        # persists this token; it is only used to authenticate the upsert fetch.
        detail["transferToken"] = proof_token
        detail["transferTokenAt"] = now.isoformat() + "Z"
        row.detail = json.dumps(detail, ensure_ascii=False)
        db.commit()
        synced = _post_feedback_import(proof_token, int(row.id))
        return {
            "ok": True, "id": int(row.id), "followUps": follow_ups,
            "revision": detail["revision"], "updatedAt": detail["updatedAt"],
            "freemanSynced": synced,
        }

    @router.post(FEEDBACK_MINE_PATH + "/{feedback_id}/acknowledge", include_in_schema=False)
    def product_feedback_acknowledge(
        feedback_id: int,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        """由反馈提交者确认当前处理结果已达到预期，并同步给 Freeman 等待最终验收。"""
        row = _owned_feedback(db, user, feedback_id)
        try:
            detail = json.loads(row.detail or "{}")
        except (ValueError, TypeError):
            detail = {}
        remote = _freeman_feedback_status([{"sourceId": feedback_id, "statusToken": str(detail.get("transferToken") or "")}]).get(str(feedback_id), {})
        remote_status = str(remote.get("status") or "")
        if remote_status == "resolved":
            raise HTTPException(409, "反馈已验收，请提交新反馈")
        if remote_status != "awaiting_acceptance":
            raise HTTPException(409, "当前反馈尚未进入待确认状态")
        now = datetime.utcnow()
        revision = int(detail.get("revision") or 1) + 1
        proof_token = secrets.token_urlsafe(24)
        detail.update({
            "acknowledged": True,
            "receipt": "用户已确认达到预期，等待最终验收",
            "acknowledgedAt": now.isoformat() + "Z",
            "userDecision": {"status": "confirmed", "at": now.isoformat() + "Z"},
            "revision": revision,
            "updatedAt": now.isoformat() + "Z",
            "transferToken": proof_token,
            "transferTokenAt": now.isoformat() + "Z",
        })
        row.detail = json.dumps(detail, ensure_ascii=False)
        db.commit()
        synced = _post_feedback_import(proof_token, int(row.id))
        return {
            "ok": True,
            "id": int(row.id),
            "acknowledged": True,
            "receipt": detail["receipt"],
            "revision": revision,
            "freemanSynced": synced,
        }

    @router.post(FEEDBACK_MINE_PATH + "/{feedback_id}/reject", include_in_schema=False)
    def product_feedback_reject(
        feedback_id: int,
        body: ProductFeedbackFollowUpBody,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        """驳回当前处理结果，并把原因作为追加反馈重新同步到 Freeman。"""
        row = _owned_feedback(db, user, feedback_id)
        try:
            detail = json.loads(row.detail or "{}")
        except (ValueError, TypeError):
            detail = {}
        remote = _freeman_feedback_status([{"sourceId": feedback_id, "statusToken": str(detail.get("transferToken") or "")}]).get(str(feedback_id), {})
        if str(remote.get("status") or "") == "resolved":
            raise HTTPException(409, "反馈已验收，请提交新反馈")
        remote = _freeman_feedback_status([{"sourceId": feedback_id, "statusToken": str(detail.get("transferToken") or "")}]).get(str(feedback_id), {})
        if str(remote.get("status") or "") == "resolved":
            raise HTTPException(409, "反馈已验收，请提交新反馈")
        now = datetime.utcnow()
        revision = int(detail.get("revision") or 1) + 1
        message = body.message.strip()
        follow_ups = list(detail.get("followUps") or [])
        follow_ups.append({"id": f"{int(row.id)}-{revision}", "message": message, "at": now.isoformat() + "Z", "kind": "rejected"})
        proof_token = secrets.token_urlsafe(24)
        detail.update({
            "followUps": follow_ups, "revision": revision, "updatedAt": now.isoformat() + "Z",
            "transferToken": proof_token, "transferTokenAt": now.isoformat() + "Z",
            "acknowledged": False, "receipt": "用户驳回处理结果，等待重新处理",
        })
        row.detail = json.dumps(detail, ensure_ascii=False)
        db.commit()
        synced = _post_feedback_import(proof_token, int(row.id))
        return {"ok": True, "id": int(row.id), "rejected": True, "revision": revision, "freemanSynced": synced}

    @router.post(QUERY_PATH, include_in_schema=False)
    def product_assistant_query(
        body: ProductAssistantBody,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        question = body.question.strip()
        navigation_cards = _guidance_cards(question, body.page)
        image = _decode_assistant_image(body)
        role = str(getattr(user, "role", "") or "")
        learning_context = _role_learning_context(
            implementation,
            db,
            user,
            body.child_id,
            question,
        )
        active_question_context = (
            _active_question_context(body)
            if role == "student"
            else "当前角色不读取学生答题中的临时题目上下文。"
        )
        if role == "student" and _student_direct_answer_request(
            question,
            body.page,
            body.active_assessment,
        ):
            return {
                "ok": True,
                "reply": _clean_assistant_reply(
                    ("我已经关联到你当前正在做的这题。 " if body.active_question_text.strip() else "")
                    + _local_answer(
                        question,
                        body.identity,
                        body.page,
                        body.tutorial_step,
                        role=role,
                        learning_context=learning_context,
                    )
                ),
                "source": "learning_guard",
                "degraded": False,
                "cards": navigation_cards,
            }
        prompt = (
            _PRODUCT_CONTEXT
            + "\n\n当前上下文："
            + f"账号角色={role}; 身份={body.identity}; 页面={body.page}; 新手步骤={body.tutorial_step or '无'}。"
            + "\n角色内学习数据："
            + learning_context
            + "\n当前作答题目："
            + active_question_context
            + "\n用户问题："
            + question
            + ("\n附图说明：只根据实际可见图片内容回答；看不清时直接说明，不推测文字、人物或答案。"
               if image else "")
        )
        try:
            reply = implementation._ai_call(
                db,
                user,
                "product_assistant",
                prompt,
                images=[image] if image else None,
                timeout=45,
            )
            return {
                "ok": True,
                "reply": _clean_assistant_reply(reply)[:5000],
                "source": "ai",
                "degraded": False,
                "cards": navigation_cards,
            }
        except HTTPException as exc:
            if image:
                reason = _image_failure_reason(exc)
                print(json.dumps({"event": "PRODUCT_ASSISTANT_IMAGE_UNAVAILABLE", "reason": reason,
                                  "status": exc.status_code}, ensure_ascii=False), flush=True)
                return {"ok": False, "reply": "图片暂时无法识别，请稍后重试或联系管理员检查图片模型配置。",
                        "source": "image_unavailable", "reason": reason, "degraded": True}
            return {
                "ok": True,
                "reply": _clean_assistant_reply(
                    _local_answer(
                        question,
                        body.identity,
                        body.page,
                        body.tutorial_step,
                        role=role,
                        learning_context=learning_context,
                    )
                ),
                "source": "local",
                "degraded": True,
                "cards": navigation_cards,
            }
        except Exception as exc:
            if image:
                reason = _image_failure_reason(exc)
                print(json.dumps({"event": "PRODUCT_ASSISTANT_IMAGE_UNAVAILABLE", "reason": reason,
                                  "status": None}, ensure_ascii=False), flush=True)
                return {"ok": False, "reply": "图片暂时无法识别，请稍后重试。",
                        "source": "image_unavailable", "reason": reason, "degraded": True}
            return {
                "ok": True,
                "reply": _clean_assistant_reply(
                    _local_answer(
                        question,
                        body.identity,
                        body.page,
                        body.tutorial_step,
                        role=role,
                        learning_context=learning_context,
                    )
                ),
                "source": "local",
                "degraded": True,
            }

    @router.post(FEEDBACK_PATH, include_in_schema=False)
    def product_feedback(
        body: ProductFeedbackBody,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        attachment = _decode_feedback_attachment(body)
        proof_token = secrets.token_urlsafe(24)
        now = datetime.utcnow()
        payload = {
            "category": body.category.strip() or "其他反馈",
            "message": body.message.strip(),
            "page": body.page.strip(),
            "identity": body.identity.strip(),
            "tutorialStep": body.tutorial_step.strip(),
            "transferToken": proof_token,
            "transferTokenAt": now.isoformat() + "Z",
            "revision": 1,
            "updatedAt": now.isoformat() + "Z",
            "followUps": [],
        }
        if attachment:
            raw, name, mime = attachment
            payload["attachment"] = {
                "name": name, "type": mime, "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        implementation.audit(
            db,
            user,
            "product.feedback",
            json.dumps(payload, ensure_ascii=False),
        )
        db.flush()
        audit_row = db.scalar(
            select(implementation.AuditLog)
            .where(
                implementation.AuditLog.action == "product.feedback",
                implementation.AuditLog.detail.contains(proof_token),
                implementation.AuditLog.user_id == user.id,
                implementation.AuditLog.school_id == user.school_id,
            )
            .order_by(implementation.AuditLog.id.desc()).limit(1)
        )
        if attachment:
            db.execute(insert(attachment_table).values(
                audit_id=audit_row.id, school_id=user.school_id, user_id=user.id,
                file_name=name, mime_type=mime, size_bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest(), file_data=raw,
            ))
        if audit_row and not db.execute(select(reward_table.c.id).where(reward_table.c.audit_id == audit_row.id)).first():
            db.execute(insert(reward_table).values(
                audit_id=audit_row.id, school_id=user.school_id, user_id=user.id,
                points=1, status="pending",
            ))
        db.commit()

        issue_link = _sync_feedback_github_issue(audit_row, payload)
        if issue_link and audit_row:
            try:
                persisted = json.loads(audit_row.detail or "{}")
            except (ValueError, TypeError):
                persisted = dict(payload)
            persisted.update(issue_link)
            audit_row.detail = json.dumps(persisted, ensure_ascii=False)
            db.commit()

        synced = _post_feedback_import(proof_token, int(audit_row.id))
        return {"ok": True, "received": True, "freemanSynced": synced}

    @router.get("/v1/product-feedback/history", include_in_schema=False)
    def product_feedback_history(
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        rows = db.scalars(
            select(implementation.AuditLog)
            .where(
                implementation.AuditLog.action == "product.feedback",
                implementation.AuditLog.user_id == user.id,
                implementation.AuditLog.school_id == user.school_id,
            )
            .order_by(implementation.AuditLog.id.desc()).limit(50)
        ).all()
        audit_ids = [row.id for row in rows]
        reward_rows = db.execute(
            select(reward_table.c.audit_id, reward_table.c.points, reward_table.c.status)
            .where(reward_table.c.audit_id.in_(audit_ids))
        ).all() if audit_ids else []
        rewards = {int(r[0]): {"points": int(r[1] or 0), "status": str(r[2] or "pending")} for r in reward_rows}
        items = []
        for row in rows:
            try:
                payload = json.loads(row.detail or "{}")
            except Exception:
                payload = {}
            reward = rewards.get(row.id, {"points": 0, "status": "received"})
            status = reward["status"]
            items.append({
                "sourceId": row.id,
                "category": str(payload.get("category") or "其他反馈")[:60],
                "message": str(payload.get("message") or "")[:500],
                "page": str(payload.get("page") or "")[:240],
                "createdAt": (row.created_at or datetime.utcnow()).isoformat() + "Z",
                "status": status,
                "statusLabel": "已采纳" if status == "granted" else ("待处理" if status == "pending" else "已收到"),
                "rewardPoints": reward["points"] if status == "granted" else 0,
            })
        summary = _feedback_reward_summary(db, user)
        summary["pendingFeedbackCount"] = sum(1 for item in items if item["status"] != "granted")
        return {"ok": True, "items": items, "summary": summary}

    def _reconcile_feedback_handoff(db, feedback_id: int) -> bool:
        row = db.scalar(
            select(implementation.AuditLog).where(
                implementation.AuditLog.id == feedback_id,
                implementation.AuditLog.action.in_(("product.feedback", "product_feedback")),
            )
        )
        if not row:
            return False
        try:
            detail = json.loads(row.detail or "{}")
        except (ValueError, TypeError):
            return False
        if not list(detail.get("followUps") or []):
            return False
        now = datetime.utcnow()
        proof_token = secrets.token_urlsafe(24)
        detail["transferToken"] = proof_token
        detail["transferTokenAt"] = now.isoformat() + "Z"
        row.detail = json.dumps(detail, ensure_ascii=False)
        db.commit()
        synced = _post_feedback_import(proof_token, int(row.id))
        _logger.info("freeman_feedback_reconcile feedback_id=%s revision=%s synced=%s", row.id, detail.get("revision"), synced)
        return synced

    @router.post("/internal/product-feedback/{feedback_id}/reconcile", include_in_schema=False)
    def reconcile_product_feedback(
        feedback_id: int,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        if str(getattr(user, "role", "") or "") not in ("admin", "school_admin"):
            raise HTTPException(403, "仅管理员可执行反馈补偿同步")
        synced = _reconcile_feedback_handoff(db, feedback_id)
        if not synced:
            raise HTTPException(409, "反馈补偿同步未成功")
        return {"ok": True, "feedbackId": feedback_id, "freemanSynced": True}

    @router.get(FEEDBACK_PROOF_PREFIX + "/{proof_token}/attachment", include_in_schema=False)
    def product_feedback_attachment_download(proof_token: str, db=Depends(implementation.get_db)):
        token = str(proof_token or "").strip()
        if len(token) < 24 or len(token) > 96:
            raise HTTPException(404, "反馈凭证不存在")
        row = db.scalar(
            select(implementation.AuditLog)
            .where(
                implementation.AuditLog.action == "product.feedback",
                implementation.AuditLog.detail.contains(token),
            )
            .order_by(implementation.AuditLog.id.desc())
            .limit(1)
        )
        if not row:
            raise HTTPException(404, "反馈凭证不存在")
        created_at = row.created_at or datetime.utcnow()
        try:
            payload = json.loads(row.detail or "{}")
        except Exception:
            raise HTTPException(404, "反馈凭证无效")
        if payload.get("transferToken") != token:
            raise HTTPException(404, "反馈凭证无效")
        token_at_raw = str(payload.get("transferTokenAt") or "")
        try:
            token_at = datetime.fromisoformat(token_at_raw.rstrip("Z")) if token_at_raw else created_at
        except ValueError:
            token_at = created_at
        if datetime.utcnow() - token_at > timedelta(minutes=FEEDBACK_PROOF_TTL_MINUTES):
            raise HTTPException(410, "反馈凭证已过期")
        attachment_row = db.execute(
            select(attachment_table).where(attachment_table.c.audit_id == row.id)
        ).mappings().first()
        if not attachment_row:
            raise HTTPException(404, "该反馈没有附件")
        from fastapi.responses import Response
        return Response(
            content=bytes(attachment_row["file_data"]),
            media_type=attachment_row["mime_type"],
            headers={
                "Content-Disposition": f"attachment; filename=\"{attachment_row['file_name']}\"",
                "X-Attachment-Sha256": attachment_row["sha256"],
            },
        )

    @router.get(FEEDBACK_PROOF_PREFIX + "/{proof_token}", include_in_schema=False)
    def product_feedback_proof(proof_token: str, db=Depends(implementation.get_db)):
        token = str(proof_token or "").strip()
        if len(token) < 24 or len(token) > 96:
            raise HTTPException(404, "反馈凭证不存在")
        row = db.scalar(
            select(implementation.AuditLog)
            .where(
                implementation.AuditLog.action == "product.feedback",
                implementation.AuditLog.detail.contains(token),
            )
            .order_by(implementation.AuditLog.id.desc())
            .limit(1)
        )
        if not row:
            raise HTTPException(404, "反馈凭证不存在")
        created_at = row.created_at or datetime.utcnow()
        try:
            payload = json.loads(row.detail or "{}")
        except Exception:
            raise HTTPException(404, "反馈凭证无效")
        if payload.get("transferToken") != token:
            raise HTTPException(404, "反馈凭证无效")
        token_at_raw = str(payload.get("transferTokenAt") or "")
        try:
            token_at = datetime.fromisoformat(token_at_raw.rstrip("Z")) if token_at_raw else created_at
        except ValueError:
            token_at = created_at
        if datetime.utcnow() - token_at > timedelta(minutes=FEEDBACK_PROOF_TTL_MINUTES):
            raise HTTPException(410, "反馈凭证已过期")
        attachment_row = db.execute(
            select(attachment_table).where(attachment_table.c.audit_id == row.id)
        ).mappings().first()
        attachment_payload = None
        if attachment_row:
            attachment_payload = {
                "name": attachment_row["file_name"],
                "type": attachment_row["mime_type"],
                "size": attachment_row["size_bytes"],
                "sha256": attachment_row["sha256"],
                "data": base64.b64encode(attachment_row["file_data"]).decode("ascii"),
            }
        follow_ups = list(payload.get("followUps") or [])
        followup_rows = []
        if follow_ups:
            followup_rows = db.execute(
                select(followup_attachment_table).where(followup_attachment_table.c.audit_id == row.id)
            ).mappings().all()
        followup_files = {str(item["follow_up_id"]): item for item in followup_rows}
        for follow_up in follow_ups:
            stored = followup_files.get(str(follow_up.get("id") or ""))
            if stored:
                follow_up["attachment"] = {
                    "name": stored["file_name"], "type": stored["mime_type"], "size": stored["size_bytes"],
                    "sha256": stored["sha256"], "data": base64.b64encode(stored["file_data"]).decode("ascii"),
                }
        revision = max(1, int(payload.get("revision") or (1 + len(follow_ups))))
        updated_at = str(payload.get("updatedAt") or (follow_ups[-1].get("at") if follow_ups else "") or (created_at.isoformat() + "Z"))
        hash_payload = {
            "category": str(payload.get("category") or "其他反馈")[:60],
            "message": str(payload.get("message") or "")[:1200],
            "page": str(payload.get("page") or "")[:240],
            "identity": str(payload.get("identity") or "")[:160],
            "tutorialStep": str(payload.get("tutorialStep") or "")[:200],
            "attachment": ({k: attachment_payload.get(k) for k in ("name", "type", "size", "sha256")} if attachment_payload else None),
            "followUps": follow_ups,
            "userDecision": payload.get("userDecision"),
        }
        content_hash = hashlib.sha256(
            json.dumps(hash_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return {
            "ok": True,
            "projectId": "longying",
            "feedback": {
                "sourceId": row.id,
                **hash_payload,
                "createdAt": created_at.isoformat() + "Z",
                "updatedAt": updated_at,
                "revision": revision,
                "contentHash": content_hash,
                "attachment": attachment_payload,
            },
        }

    app.include_router(router)
    app.state.v1_product_assistant_routes_installed = True


_ASSISTANT_SNIPPET = r'''
<style id="changying_v1_product_assistant_v1-css">
  #cy-product-assistant-fab{position:fixed;right:14px;bottom:max(calc(84px + env(safe-area-inset-bottom)),var(--cy-feedback-review-lift,0px));z-index:125;border:0;border-radius:999px;background:#173a78;color:#fff;width:48px;height:48px;padding:0;font-weight:900;box-shadow:0 10px 28px rgba(23,58,120,.24);display:grid;place-items:center;font-size:20px}#cy-product-assistant-fab .cy-pa-fab-label{display:none}
  #cy-product-assistant-fab[hidden],#cy-product-assistant-panel[hidden]{display:none!important}
  #cy-product-assistant-panel{position:fixed;right:14px;bottom:max(calc(142px + env(safe-area-inset-bottom)),calc(var(--cy-feedback-review-lift,0px) + 58px));z-index:126;width:min(390px,calc(100vw - 28px));max-height:min(620px,70dvh);background:#fff;border:1px solid #dbe4f1;border-radius:20px;box-shadow:0 22px 70px rgba(17,34,64,.28);overflow:hidden;display:flex;flex-direction:column}
  #cy-pa-processed-notice[hidden]{display:none!important}#cy-pa-processed-notice{position:fixed;right:70px;bottom:max(calc(88px + env(safe-area-inset-bottom)),calc(var(--cy-feedback-review-lift,0px) + 4px));z-index:127;display:block;max-width:min(285px,calc(100vw - 94px));padding:9px 12px;border:1px solid #c8d8f2;border-radius:14px;background:#fff;color:#173a78;box-shadow:0 8px 24px rgba(17,34,64,.2);font-size:12px;font-weight:800;line-height:1.35}#cy-product-assistant-fab[hidden]~#cy-pa-processed-notice:not([hidden]){display:none!important}.cy-pa-processed-record{display:flex;align-items:center;gap:7px;text-decoration:none;white-space:nowrap;color:inherit}.cy-pa-processed-record:before{content:'';flex:none;width:8px;height:8px;border-radius:50%;background:#3682ed;box-shadow:0 0 0 0 rgba(54,130,237,.5);animation:cy-pa-notice-pulse 1.6s ease-out infinite}@keyframes cy-pa-notice-pulse{70%{box-shadow:0 0 0 7px rgba(54,130,237,0)}100%{box-shadow:0 0 0 0 rgba(54,130,237,0)}}@media(prefers-reduced-motion:reduce){.cy-pa-processed-record:before{animation:none}}
  .cy-pa-head{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:11px 12px;border-bottom:1px solid #e2e8f1}.cy-pa-head b{display:block}.cy-pa-head small{display:block;max-width:240px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--muted);line-height:1.35}.cy-pa-head-actions{display:flex;gap:6px}.cy-pa-head-actions .btn{min-height:36px;padding:7px 10px}
  .cy-pa-tabs{display:grid;grid-template-columns:1fr auto;padding:9px;gap:7px;background:#f7f9fc}.cy-pa-tab,.cy-pa-feedback-menu>button{border:1px solid #dbe4f1;background:#fff;border-radius:11px;padding:9px;font-weight:750}.cy-pa-tab.active,.cy-pa-feedback-menu>button.active{background:#eaf1ff;border-color:#bfd2f4;color:#173a78}.cy-pa-feedback-menu{position:relative}.cy-pa-feedback-dropdown{position:absolute;right:0;top:calc(100% + 5px);z-index:4;min-width:150px;background:#fff;border:1px solid #dbe4f1;border-radius:11px;box-shadow:0 12px 30px rgba(17,34,64,.18);padding:5px;display:grid;gap:4px}.cy-pa-feedback-dropdown[hidden]{display:none}.cy-pa-feedback-dropdown button{border:0;background:#fff;text-align:left;border-radius:8px;padding:9px 10px;font-weight:700}.cy-pa-feedback-dropdown button:hover{background:#f1f5fb}.cy-pa-feedback-dropdown{width:min(350px,calc(100vw - 48px));max-height:min(460px,60dvh);overflow:auto}.cy-pa-feedback-dropdown-records{display:grid;gap:6px;border-top:1px solid #e6ebf2;margin-top:2px;padding-top:6px}.cy-pa-feedback-dropdown-record{border:1px solid #dbe4f1;border-radius:9px;padding:8px;background:#f8fbff;display:grid;gap:4px}.cy-pa-feedback-dropdown-record b{font-size:11px}.cy-pa-feedback-dropdown-record small{font-size:10px;color:#667085;line-height:1.4;overflow-wrap:anywhere}.cy-pa-feedback-dropdown-actions{display:flex;gap:5px;flex-wrap:wrap}.cy-pa-feedback-dropdown-actions button,.cy-pa-feedback-dropdown-actions a{border:1px solid #dbe4f1;background:#fff;padding:6px 8px;font-size:10px;border-radius:8px;text-decoration:none;color:#173a78;font-weight:750}.cy-pa-feedback-dropdown-actions button.primary,.cy-pa-feedback-dropdown-actions a.primary{background:#173a78;color:#fff;border-color:#173a78}
  .cy-pa-body{padding:10px 11px;overflow:auto}.cy-pa-quick{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}.cy-pa-quick button{border:1px solid #dbe4f1;background:#fff;border-radius:999px;padding:6px 8px;font-size:11px}
  .cy-pa-chat{display:grid;gap:9px;margin-bottom:10px}.cy-pa-msg{max-width:92%;padding:10px 11px;border-radius:13px;line-height:1.55;font-size:13px;white-space:pre-wrap}.cy-pa-msg.user{justify-self:end;background:#173a78;color:#fff}.cy-pa-msg.assistant{justify-self:start;background:#f1f5fb;color:#1c2940}.cy-pa-sent-image{display:block;max-width:180px;max-height:180px;margin-top:7px;border-radius:9px;object-fit:contain;background:#fff}
  .cy-pa-learning-visual{justify-self:start;width:min(92%,330px);border:1px solid #dbe5f3;background:#fff;border-radius:14px;padding:10px;display:grid;gap:8px}.cy-pa-learning-visual b{font-size:12px;color:#173a78}.cy-pa-learning-visual small{font-size:10px;color:var(--muted);line-height:1.45}.cy-pa-fraction-grid{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:3px;height:42px}.cy-pa-fraction-cell{border:1px solid #9fb6da;border-radius:5px;background:#f5f8fd}.cy-pa-fraction-cell.is-given{background:#dbe8ff}.cy-pa-bar-model{display:grid;gap:5px}.cy-pa-bar-track{display:grid;grid-template-columns:1.15fr .85fr;height:42px;border:1px solid #9fb6da;border-radius:8px;overflow:hidden}.cy-pa-bar-known,.cy-pa-bar-unknown{display:grid;place-items:center;font-size:10px}.cy-pa-bar-known{background:#dbe8ff}.cy-pa-bar-unknown{background:#f7f9fc;border-left:1px dashed #9fb6da}.cy-pa-shape-box{height:86px;display:grid;place-items:center}.cy-pa-shape{border:2px solid #6c88b4;display:grid;place-items:center;color:#52647f;font-size:11px}.cy-pa-shape.rectangle{width:150px;height:68px}.cy-pa-shape.square{width:74px;height:74px}.cy-pa-shape.circle{width:74px;height:74px;border-radius:50%}.cy-pa-shape.triangle{width:0;height:0;border-left:48px solid transparent;border-right:48px solid transparent;border-bottom:78px solid #dbe8ff;border-top:0;position:relative}.cy-pa-numberline{position:relative;height:54px;margin:2px 8px}.cy-pa-numberline-line{position:absolute;left:0;right:0;top:24px;border-top:2px solid #6c88b4}.cy-pa-numberline-tick{position:absolute;top:17px;transform:translateX(-50%);font-size:9px;color:#52647f}.cy-pa-numberline-tick:before{content:'';display:block;width:1px;height:15px;background:#6c88b4;margin:0 auto 2px}
  .cy-pa-compose{display:grid;grid-template-columns:1fr auto;gap:7px}.cy-pa-compose textarea{min-height:58px;resize:none}.cy-pa-compose .btn{align-self:end}.cy-pa-image-picker{display:flex;align-items:center;gap:7px;font-size:11px;margin-top:7px}.cy-pa-image-picker input{max-width:205px}.cy-pa-image-status{color:#52647f;overflow-wrap:anywhere}
  .cy-pa-feedback{display:grid;gap:8px}.cy-pa-history{display:grid;gap:8px}.cy-pa-history-item{border:1px solid #dbe4f1;border-radius:12px;padding:9px;background:#f8fbff}.cy-pa-history-item b{font-size:12px}.cy-pa-history-item small{display:block;color:#667085;margin-top:4px;line-height:1.45}.cy-pa-feedback textarea{min-height:76px;resize:none}.cy-pa-attachment{display:grid;gap:5px;font-size:11px}.cy-pa-attachment input{max-width:100%}.cy-pa-attachment-status{overflow-wrap:anywhere;color:#52647f}.cy-pa-feedback-cats{display:flex;gap:6px;flex-wrap:wrap}.cy-pa-feedback-cats button{border:1px solid #dbe4f1;background:#fff;border-radius:999px;padding:6px 9px;font-size:11px}.cy-pa-feedback-cats button.active{background:#eaf1ff;border-color:#bfd2f4;color:#173a78;font-weight:800}.cy-pa-note{font-size:10px;color:var(--muted);line-height:1.45}.cy-pa-guide{border:1px solid #dbe5f3;background:#f8fbff;border-radius:14px;padding:9px}.cy-pa-guide-title{font-size:12px;font-weight:850;color:#173a78;margin-bottom:7px}.cy-pa-guide-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.cy-pa-guide-card{display:grid;gap:5px;text-decoration:none;color:#182238;background:#fff;border:1px solid #dbe5f3;border-radius:11px;overflow:hidden}.cy-pa-guide-visual{height:74px;background:#edf3ff;padding:8px;display:grid;grid-template-rows:12px 1fr;gap:7px}.cy-pa-guide-bar{border-radius:6px;background:#d5e2f6}.cy-pa-guide-page{display:grid;grid-template-columns:38px 1fr;gap:8px;align-items:center}.cy-pa-guide-icon{height:38px;border-radius:9px;background:#fff;display:grid;place-items:center;font-size:20px;color:#244c91}.cy-pa-guide-lines{display:grid;gap:5px}.cy-pa-guide-lines i{display:block;height:6px;border-radius:3px;background:#fff}.cy-pa-guide-lines i:last-child{width:66%}.cy-pa-guide-copy{padding:0 7px 7px;display:grid;gap:2px}.cy-pa-guide-copy b{font-size:11px}.cy-pa-guide-copy small{font-size:9px;color:var(--muted);line-height:1.35}
  @media(max-width:640px){#cy-product-assistant-fab{right:12px;bottom:max(calc(78px + env(safe-area-inset-bottom)),var(--cy-feedback-review-lift,0px));width:44px;height:44px;font-size:18px}#cy-product-assistant-panel{left:10px;right:10px;bottom:max(calc(128px + env(safe-area-inset-bottom)),calc(var(--cy-feedback-review-lift,0px) + 54px));width:auto;max-height:62dvh}}
</style>
<button id="cy-product-assistant-fab" hidden aria-label="打开产品助手" title="产品助手">✦<span class="cy-pa-fab-label">产品助手</span></button>
<section id="cy-product-assistant-panel" hidden aria-label="长缨产品助手">
  <header class="cy-pa-head"><div><b>长缨产品助手</b><small id="cy-pa-context">读取当前身份与页面…</small></div><div class="cy-pa-head-actions"><button class="btn" id="cy-pa-collapse" aria-label="收起">−</button></div></header>
  <div class="cy-pa-tabs" data-feedback-ui-revision="3"><button class="cy-pa-tab active" id="cy-pa-ask-tab" data-pa-tab="ask">问产品</button><div class="cy-pa-feedback-menu"><button id="cy-pa-feedback-menu-button" type="button" aria-haspopup="menu" aria-expanded="false">提反馈 ▾</button><div class="cy-pa-feedback-dropdown" id="cy-pa-feedback-dropdown" role="menu" hidden><button type="button" data-pa-tab="feedback" role="menuitem">提交新反馈</button><button type="button" data-pa-tab="records" role="menuitem">反馈记录</button><div class="cy-pa-feedback-dropdown-records" id="cy-pa-feedback-dropdown-records"><div class="cy-pa-note">打开“提反馈”后会在这里直接显示你的反馈记录。</div></div></div></div></div>
  <div class="cy-pa-body" id="cy-pa-ask">
    <div class="cy-pa-quick"><button id="cy-pa-quick-1" data-pa-question="我现在该做什么？">下一步做什么</button><button id="cy-pa-quick-2" data-pa-question="这个页面是干什么的？">页面用途</button><button id="cy-pa-quick-3" data-pa-question="这一步为什么排在这里？">为什么这样走</button></div>
    <div class="cy-pa-guide" id="cy-pa-guide">
      <div class="cy-pa-guide-title">页面示意 · 点卡片直达</div>
      <div class="cy-pa-guide-grid" id="cy-pa-guide-grid"></div>
      <div class="cy-pa-note">页面示意直接随助手生成，不依赖额外图片下载；点击即可进入对应功能页。</div>
    </div>
    <div class="cy-pa-chat" id="cy-pa-chat"><div class="cy-pa-msg assistant" id="cy-pa-welcome">我会结合你当前登录身份、所在页面和新手教学步骤回答长缨怎么用；也会用页面示意卡标出相关入口。</div></div>
    <div class="cy-pa-compose"><textarea id="cy-pa-input" placeholder="例如：这个页面应该先做什么？"></textarea><button class="btn primary" id="cy-pa-send">发送</button></div>
    <label class="cy-pa-image-picker">附图提问（最多 1 MB）<input type="file" id="cy-pa-query-image" accept="image/jpeg,image/png,image/webp"><span class="cy-pa-image-status" id="cy-pa-query-image-status">未选择图片</span></label>
  </div>
  <div class="cy-pa-body" id="cy-pa-feedback" hidden>
    <div class="cy-pa-feedback"><input type="hidden" id="cy-pa-category" value="这里不好懂"><div class="cy-pa-feedback-cats"><button class="active" data-pa-category="这里不好懂">不好懂</button><button data-pa-category="没找到入口">找不到</button><button data-pa-category="流程不直观">流程不顺</button><button data-pa-category="功能与预期不符">不符合预期</button><button data-pa-category="希望增加功能">想加功能</button><button data-pa-category="其他反馈">其他</button></div><textarea id="cy-pa-feedback-text" placeholder="一句话描述问题或建议（不要填写密码、API Key 等敏感信息）"></textarea><label class="cy-pa-attachment">附照片或文件（最多 1 MB）<input type="file" id="cy-pa-feedback-file" accept="image/jpeg,image/png,image/webp,application/pdf,text/plain"><span class="cy-pa-attachment-status" id="cy-pa-attachment-status">未选择文件</span></label><button class="btn primary" id="cy-pa-submit-feedback">提交</button><div class="cy-pa-note">会自动附带当前页面、当前身份和正在进行的新手步骤。</div></div>
  </div>
  <div class="cy-pa-body" id="cy-pa-records" hidden><div class="cy-pa-history" id="cy-pa-history"><div class="cy-pa-note">正在读取你的反馈记录…</div></div></div>
</section>
  <div id="cy-pa-processed-notice" role="status" aria-live="polite" data-feedback-notification-revision="3" hidden></div>
<script id="changying_v1_product_assistant_v1-script">
(()=>{
  if(window.__cyV1ProductAssistantInstalled)return;
  window.__cyV1ProductAssistantInstalled=true;
  const fab=document.getElementById('cy-product-assistant-fab'),panel=document.getElementById('cy-product-assistant-panel');
  const getIdentityButton=()=>document.getElementById('identityButton');
  const getIdentityChip=()=>document.getElementById('cy-v1-unified-identity')||document.getElementById('identityChip')||document.getElementById('identity');
  const chat=document.getElementById('cy-pa-chat'),input=document.getElementById('cy-pa-input'),send=document.getElementById('cy-pa-send');
  const REMEMBER_KEY='v717Remember';
  const authRemember=()=>localStorage.getItem(REMEMBER_KEY)==='1';
  const authStore=()=>authRemember()?localStorage:sessionStorage;
  const classicToken=()=>{try{return typeof state!=='undefined'&&state?.token?String(state.token):''}catch{return''}};
  const readToken=()=>authStore().getItem('v717Token')||sessionStorage.getItem('v717Token')||localStorage.getItem('v717Token')||sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||classicToken()||'';
  const identityChipReady=()=>{const chip=getIdentityChip();return Boolean(chip&&String(chip.textContent||'').trim()&&!String(chip.textContent||'').includes('正在识别'))};
  const identityButtonReady=()=>{const button=getIdentityButton();return Boolean(button&&button.hidden===false)};
  const identityReady=()=>Boolean(readToken()&&(identityChipReady()||identityButtonReady()));
  const tutorialStep=()=>document.querySelector('.cy-lesson-top h2')?.textContent?.trim()||'';
  const selectedChildID=()=>{try{return typeof state!=='undefined'&&state?.childID?Number(state.childID):null}catch{return null}};
  const emptyQuestionContext=()=>({active_assessment:false,active_question_text:'',active_question_options:[],active_question_meta:'',active_question_figure:'',active_question_position:'',active_question_response:''});
  const isVisibleQuestionNode=el=>Boolean(el&&(el.offsetParent!==null||el.getClientRects().length));
  const currentQuestionContext=()=>{
    const page=document.getElementById('page')||document.body;
    const selectors=['.question','[data-question-text]','.question-text','.question-stem','.stem'];
    let question=null;
    for(const selector of selectors){
      question=[...page.querySelectorAll(selector)].find(isVisibleQuestionNode)||null;
      if(question)break;
    }
    if(!question)return emptyQuestionContext();
    const root=question.closest('.card')||question.parentElement||page;
    const options=[...root.querySelectorAll('.option,[data-option]')].filter(isVisibleQuestionNode).map(x=>String(x.textContent||'').trim()).filter(Boolean).slice(0,8);
    const selected=root.querySelector('.option.selected,[data-option].selected,[aria-checked="true"]');
    const textInput=root.querySelector('#quizTextAnswer,input[type="text"],input[inputmode],textarea');
    const response=selected?String(selected.textContent||'').trim():(textInput?String(textInput.value||'').trim():'');
    const badges=[...root.querySelectorAll('.badge')].filter(isVisibleQuestionNode).map(x=>String(x.textContent||'').trim()).filter(Boolean).slice(0,4);
    const figureTexts=[...root.querySelectorAll('svg[aria-label="题目图示"] text,[role="img"][aria-label="题目图示"] text')]
      .filter(isVisibleQuestionNode).map(x=>String(x.textContent||'').trim()).filter(Boolean).slice(0,12);
    const figureTitle=[...root.querySelectorAll('.muted')].filter(isVisibleQuestionNode).map(x=>String(x.textContent||'').trim()).find(x=>x&&x.length<=80)||'';
    const pageText=String(root.innerText||page.innerText||'');
    const pos=pageText.match(/第\s*\d+\s*\/\s*\d+\s*题/)?.[0]||'当前题';
    const assessmentSignals=options.length>0||Boolean(textInput)||Boolean(root.querySelector('.progress,#quizNext,#quitQuiz'))||/第\s*\d+\s*\/\s*\d+\s*题|提交答案|保存并下一题|提交整份|下一题/.test(pageText);
    if(!assessmentSignals)return emptyQuestionContext();
    return {
      active_assessment:true,
      active_question_text:String(question.textContent||'').trim().slice(0,1600),
      active_question_options:options,
      active_question_meta:badges.join(' · ').slice(0,500),
      active_question_figure:[figureTitle,...figureTexts].filter(Boolean).join(' · ').slice(0,900),
      active_question_position:pos,
      active_question_response:response.slice(0,600)
    };
  };
  const context=()=>{const chip=getIdentityChip();return {page:location.pathname+location.search,identity:String(chip?.textContent||'').trim(),tutorial_step:tutorialStep(),child_id:selectedChildID(),...currentQuestionContext()}};
  const escapeHtml=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const cleanReplyText=text=>String(text||'')
    .replace(/[\u200B\uFEFF\uFFFD]/g,'')
    .replace(/\`\`\`[A-Za-z0-9_-]*\s*/g,'')
    .replace(/\`\`\`/g,'')
    .replace(/\*\*(.*?)\*\*/g,'$1')
    .replace(/__(.*?)__/g,'$1')
    .replace(/\`/g,'')
    .replace(/^\s*#{1,6}\s*/gm,'')
    .replace(/^\s*[-*+]\s+/gm,'• ')
    .replace(/^\s*[-_=*#]{3,}\s*$/gm,'')
    .replace(/[ \t]{2,}/g,' ')
    .replace(/\n{3,}/g,'\n\n')
    .trim();
  const addMessage=(kind,text,image)=>{const el=document.createElement('div');el.className='cy-pa-msg '+kind;el.textContent=kind==='assistant'?cleanReplyText(text):text;if(image){const preview=document.createElement('img');preview.src=image;preview.alt='已发送的图片';preview.className='cy-pa-sent-image';el.appendChild(preview)}chat.appendChild(el);chat.scrollTop=chat.scrollHeight};
  const questionVisualSpec=ctx=>{
    if(!ctx?.active_assessment||!ctx.active_question_text)return null;
    const q=String(ctx.active_question_text);
    const fraction=q.match(/(\d{1,2})\s*\/\s*(\d{1,2})/);
    if(fraction){
      const numerator=Number(fraction[1]),denominator=Number(fraction[2]);
      if(denominator>=2&&denominator<=12&&numerator>=0&&numerator<=denominator)return{type:'fraction',numerator,denominator,label:fraction[0]};
    }
    const nums=(q.match(/\d+(?:\.\d+)?/g)||[]).slice(0,4);
    if(/(?:一共|总共|全长|共有|剩下|还剩|用去|用了)/.test(q)&&nums.length)return{type:'bar',numbers:nums};
    if(/长方形|矩形/.test(q))return{type:'shape',shape:'rectangle',label:'长方形'};
    if(/正方形/.test(q))return{type:'shape',shape:'square',label:'正方形'};
    if(/三角形/.test(q))return{type:'shape',shape:'triangle',label:'三角形'};
    if(/圆形|圆的|圆 /.test(q))return{type:'shape',shape:'circle',label:'圆'};
    if(/数轴|向前|向后|相差|温度|加法|减法/.test(q)&&nums.length)return{type:'numberline',numbers:[...new Set(nums)].slice(0,4)};
    return null;
  };
  const addLearningVisual=spec=>{
    if(!spec)return;
    const el=document.createElement('div');el.className='cy-pa-learning-visual';
    let visual='',caption='';
    if(spec.type==='fraction'){
      visual='<div class="cy-pa-fraction-grid">'+Array.from({length:spec.denominator},(_,i)=>'<span class="cy-pa-fraction-cell '+(i<spec.numerator?'is-given':'')+'"></span>').join('')+'</div>';
      caption=spec.label+'：把一个整体平均分成 '+spec.denominator+' 份，先看题目说的是其中哪 '+spec.numerator+' 份。';
    }else if(spec.type==='bar'){
      const labels=spec.numbers.map(x=>escapeHtml(x)).join('、');
      visual='<div class="cy-pa-bar-model"><div class="cy-pa-bar-track"><span class="cy-pa-bar-known">已知部分</span><span class="cy-pa-bar-unknown">待求 ?</span></div></div>';
      caption='先把数量关系看成“整体—已知部分—待求部分”。题目里出现的数有：'+labels+'。先别急着计算，先判断每个数属于哪一部分。';
    }else if(spec.type==='shape'){
      visual='<div class="cy-pa-shape-box"><span class="cy-pa-shape '+spec.shape+'">'+(spec.shape==='triangle'?'':escapeHtml(spec.label)+' · ?')+'</span></div>';
      caption='先把'+spec.label+'画出来，再把题目给出的长度、角度或位置标在对应边上；问号只放在题目真正要求的量上。';
    }else if(spec.type==='numberline'){
      const values=spec.numbers.map(Number).filter(Number.isFinite),min=Math.min(...values),max=Math.max(...values),span=Math.max(1,max-min);
      visual='<div class="cy-pa-numberline"><div class="cy-pa-numberline-line"></div>'+values.map(v=>'<span class="cy-pa-numberline-tick" style="left:'+((v-min)/span*88+6)+'%">'+escapeHtml(v)+'</span>').join('')+'</div>';
      caption='把题目给出的数先放到数轴上，再判断是向前、向后，还是比较两点之间的距离。';
    }
    el.innerHTML='<b>理解小图</b>'+visual+'<small>'+caption+'</small>';
    chat.appendChild(el);chat.scrollTop=chat.scrollHeight;
  };
  const maybeAddLearningVisual=(questionText,ctx)=>{
    if(guideRole(ctx.identity)!=='student'||!ctx.active_assessment)return;
    if(!/(图|画|看不懂|怎么想|不会|提示|关系|为什么)/.test(String(questionText||'')))return;
    addLearningVisual(questionVisualSpec(ctx));
  };
  const updateContext=()=>{const c=context();document.getElementById('cy-pa-context').textContent=(c.identity||'当前身份')+' · '+c.page+(c.tutorial_step?' · '+c.tutorial_step:'')+(c.active_assessment?' · 已关联当前题目':'')};
  const GUIDE_SETS={
    teacher:[
      {id:'workspace',title:'当前教学',href:'/v1/workspace',icon:'▦',hint:'当前班级、课程、学生与待办',keywords:'当前教学 工作台 班级 课程 待办 晚托 周末课'},
      {id:'classes',title:'班级学生',href:'/v1/tool?page=classes',icon:'▥',hint:'查看班级与学生关系',keywords:'班级 学生 名单 归属'},
      {id:'student',title:'学生档案',href:'/v1/student',icon:'◉',hint:'连续学情、作业、错题与时间线',keywords:'学生 档案 学情 错题 成绩 时间线'},
      {id:'papers',title:'组卷作业',href:'/v1/tool?page=papers',icon:'✓',hint:'组卷、布置与检查学生提交',keywords:'作业 组卷 布置 批改 提交 测验'},
      {id:'analytics',title:'学情分析',href:'/v1/tool?page=analytics',icon:'◎',hint:'查看班级和学生学习数据',keywords:'学情 分析 进度 掌握 正确率'},
      {id:'classroom',title:'课堂复盘',href:'/v1/classroom-review',icon:'▣',hint:'复盘讲义、互动课堂与随堂检测',keywords:'课堂 复盘 讲义 互动 随堂检测'},
      {id:'history',title:'往期教学',href:'/v1/history',icon:'◷',hint:'按学年和教学周期回看历史',keywords:'往期 历史 学年 学期 寒假 暑假'},
      {id:'transition',title:'升学衔接',href:'/v1/transition',icon:'↗',hint:'阶段变化、差距与衔接计划',keywords:'升学 升年级 衔接 阶段 差距 计划'},
      {id:'tools',title:'全部功能',href:'/v1/tool',icon:'⌘',hint:'进入教师完整功能页',keywords:'全部功能 更多 功能 页面 入口'}
    ],
    student:[
      {id:'syncLearning',title:'同步课堂',href:'/v1/tool?page=syncLearning',icon:'▦',hint:'查看课堂学习与互动内容',keywords:'课堂 同步 互动 随堂检测'},
      {id:'assignments',title:'我的作业',href:'/v1/tool?page=assignments',icon:'✓',hint:'查看并完成待办作业',keywords:'作业 待完成 提交'},
      {id:'practice',title:'自主练习',href:'/v1/tool?page=practice',icon:'✎',hint:'练习、针对性训练与错题巩固',keywords:'练习 针对性 错题 巩固'},
      {id:'progress',title:'我的学情',href:'/v1/tool?page=progress',icon:'◎',hint:'查看学习进度与掌握情况',keywords:'学情 进度 掌握 正确率 成绩'},
      {id:'rewards',title:'积分奖励',href:'/v1/tool?page=rewards',icon:'★',hint:'查看积分变化与奖励记录',keywords:'积分 奖励 表现'},
      {id:'wrongbook',title:'我的错题',href:'/v1/tool?page=wrongbook',icon:'◫',hint:'回看错题并继续巩固',keywords:'错题 错题本 订正'},
      {id:'tools',title:'更多功能',href:'/v1/tool?page=__hub__',icon:'⌘',hint:'进入学生完整功能页',keywords:'全部功能 更多 功能 页面 入口'}
    ],
    parent:[
      {id:'childLearning',title:'孩子课程',href:'/v1/tool?page=childLearning',icon:'▦',hint:'查看孩子当前课程与学习安排',keywords:'孩子 课程 当前学习'},
      {id:'childAssignments',title:'孩子作业',href:'/v1/tool?page=childAssignments',icon:'✓',hint:'查看作业进度、完成与逾期状态',keywords:'孩子 作业 待完成 逾期'},
      {id:'childProgress',title:'孩子学情',href:'/v1/tool?page=childProgress',icon:'◎',hint:'查看成绩、知识点与学习进展',keywords:'孩子 学情 成绩 进度 掌握'},
      {id:'childRewards',title:'课堂表现',href:'/v1/tool?page=childRewards',icon:'★',hint:'查看课堂表现与积分记录',keywords:'课堂 表现 积分 奖励'},
      {id:'account',title:'我的',href:'/v1/tool?page=account',icon:'⌘',hint:'查看家长账号与关联信息',keywords:'我的 账号 家长 关联'},
      {id:'tools',title:'全部功能',href:'/v1/tool',icon:'☰',hint:'进入家长完整功能页',keywords:'全部功能 更多 功能 页面 入口'}
    ],
    admin:[
      {id:'admin',title:'平台总览',href:'/v1/tool?page=admin',icon:'▦',hint:'查看学校或机构整体运行情况',keywords:'平台 总览 机构 学校'},
      {id:'users',title:'账号管理',href:'/v1/tool?page=users',icon:'◉',hint:'管理教师、学生与家长账号',keywords:'账号 用户 教师 学生 家长'},
      {id:'pointsAdmin',title:'积分奖励',href:'/v1/tool?page=pointsAdmin',icon:'★',hint:'查看与维护积分奖励规则',keywords:'积分 奖励 规则'},
      {id:'adminAudit',title:'全校审计',href:'/v1/tool?page=adminAudit',icon:'◷',hint:'回看关键操作和管理记录',keywords:'审计 操作记录 全校'},
      {id:'system',title:'系统设置',href:'/v1/tool?page=system',icon:'⚙',hint:'管理系统级配置',keywords:'系统 设置 配置'},
      {id:'subscription',title:'套餐授权',href:'/v1/tool?page=subscription',icon:'◇',hint:'查看套餐与功能授权状态',keywords:'套餐 授权 功能'},
      {id:'tools',title:'全部功能',href:'/v1/tool',icon:'⌘',hint:'进入管理员完整功能页',keywords:'全部功能 更多 功能 页面 入口'}
    ]
  };
  const guideRole=identity=>{
    const label=String(identity||'');
    if(label.includes('管理员'))return'admin';
    if(label.includes('家长'))return'parent';
    if(label.includes('学生'))return'student';
    return'teacher';
  };
  const ROLE_COPY={
    teacher:{
      tab:'问产品',
      placeholder:'例如：这个页面应该先做什么？',
      welcome:'我会结合你当前身份和页面解释长缨怎么用，并把相关功能入口直接标出来。',
      quick:[['下一步做什么','我现在该做什么？'],['页面用途','这个页面是干什么的？'],['为什么这样走','这一步为什么排在这里？']]
    },
    student:{
      tab:'问长缨',
      placeholder:'可以问不会的题、知识点，或长缨里下一步怎么学…',
      welcome:'你可以问我长缨怎么用，也可以问不会的知识点和题目思路。我不会直接替你做作业，会陪你把问题拆开，一步一步找到答案。',
      quick:[['这题怎么想','我有一道题不会，先别告诉我答案，帮我拆解思路。'],['拆知识点','帮我把这个知识点拆成容易理解的小步骤。'],['去哪里巩固','我刚刚有点没学会，长缨里应该去哪里继续练？']]
    },
    parent:{
      tab:'孩子学习',
      placeholder:'例如：孩子最近怎么样？我在家怎么配合？',
      welcome:'我会优先结合当前绑定孩子在长缨里的真实学习记录，帮你看进步、待关注点和家庭里可以怎么配合。',
      quick:[['最近怎么样','结合长缨里的记录，孩子最近学习情况怎么样？'],['在家怎么配合','根据孩子目前的学习情况，我在家可以怎么配合？'],['先鼓励什么','我现在最值得先肯定和鼓励孩子的是什么？']]
    },
    admin:{
      tab:'问产品',
      placeholder:'例如：这个页面应该先做什么？',
      welcome:'我会结合当前管理身份和页面解释长缨的功能、边界和下一步操作。',
      quick:[['下一步做什么','我现在该做什么？'],['页面用途','这个页面是干什么的？'],['为什么这样走','这一步为什么排在这里？']]
    }
  };
  const applyRoleCopy=()=>{
    const c=context(),role=guideRole(c.identity),cfg=ROLE_COPY[role]||ROLE_COPY.teacher;
    const tab=document.getElementById('cy-pa-ask-tab'),welcome=document.getElementById('cy-pa-welcome');
    if(tab)tab.textContent=cfg.tab;
    if(role==='student'&&c.active_assessment){
      if(welcome)welcome.textContent='我已经关联到你正在做的当前题目，只读取你屏幕上能看到的题干、选项和你自己的输入，不读取正确答案或解析。你可以直接问“这题怎么想”。';
      input.placeholder='直接问：这题我哪里没想明白？';
      const btn1=document.getElementById('cy-pa-quick-1'),btn2=document.getElementById('cy-pa-quick-2'),btn3=document.getElementById('cy-pa-quick-3');
      if(btn1){btn1.textContent='帮我看当前题';btn1.dataset.paQuestion='我不会做当前这题，先别告诉我答案，帮我找出已知条件和第一步。'}
      if(btn2){btn2.textContent='给我一个提示';btn2.dataset.paQuestion='针对当前这题只给我一条提示，不要给答案。'}
      if(btn3){btn3.textContent='画个简图';btn3.dataset.paQuestion='如果这题适合用简化图示理解，请告诉我应该画什么图，并先用文字解释图里的关系。'}
      return;
    }
    if(welcome)welcome.textContent=cfg.welcome;
    input.placeholder=cfg.placeholder;
    cfg.quick.forEach((item,i)=>{const btn=document.getElementById('cy-pa-quick-'+(i+1));if(btn){btn.textContent=item[0];btn.dataset.paQuestion=item[1]}});
  };
  const guideScore=(g,text,currentPage)=>{
    const hay=String(text||'')+' '+String(currentPage||'');
    const page=String(currentPage||'').split('#')[0];
    let score=page===g.href?9:0;
    if(!g.href.includes('?')&&page.startsWith(g.href))score+=4;
    String(g.keywords||'').split(/\s+/).forEach(k=>{if(k&&hay.includes(k))score+=2});
    return score;
  };
  const FEEDBACK_RECORDS_GUIDE={id:'feedbackRecords',title:'我的反馈记录',href:'/v1/workspace?tab=feedback-records',icon:'◷',hint:'查看处理回执与反馈奖励',keywords:'反馈记录 我的反馈 历史记录 回执 处理状况 反馈状态 追加反馈 奖励明细'};
  const guideCandidates=text=>{
    const c=context(),role=guideRole(c.identity),pool=[...(GUIDE_SETS[role]||GUIDE_SETS.teacher),FEEDBACK_RECORDS_GUIDE];
    const ranked=pool.map((g,order)=>({g,order,score:guideScore(g,text,c.page)})).sort((a,b)=>b.score-a.score||a.order-b.order);
    const picked=ranked.filter(x=>x.score>0).slice(0,3).map(x=>x.g);
    return picked.length?picked:pool.slice(0,3);
  };
  const normalizeGuides=input=>Array.isArray(input)?input.map(g=>({id:g.key||'guide',title:g.title||'功能入口',href:g.path||'/v1',icon:'↗',hint:g.description||'点击进入对应功能'})):guideCandidates(input);
  const guideCardsHtml=guides=>guides.map(g=>'<a class="cy-pa-guide-card" href="'+escapeHtml(g.href)+'" data-pa-guide="'+escapeHtml(g.id)+'"><span class="cy-pa-guide-visual" role="img" aria-label="'+escapeHtml(g.title)+'页面示意图"><span class="cy-pa-guide-bar"></span><span class="cy-pa-guide-page"><span class="cy-pa-guide-icon">'+escapeHtml(g.icon)+'</span><span class="cy-pa-guide-lines"><i></i><i></i></span></span></span><span class="cy-pa-guide-copy"><b>'+escapeHtml(g.title)+'</b><small>'+escapeHtml(g.hint)+'</small></span></a>').join('');
  const renderGuideGrid=input=>{
    const grid=document.getElementById('cy-pa-guide-grid');if(!grid)return;
    grid.innerHTML=guideCardsHtml(normalizeGuides(input));
  };
  const addInlineGuideCards=input=>{
    const guides=normalizeGuides(input);if(!guides.length)return;
    const box=document.createElement('div');box.className='cy-pa-guide cy-pa-inline-guide';
    box.innerHTML='<div class="cy-pa-guide-title">对应功能 · 点卡片直达</div><div class="cy-pa-guide-grid">'+guideCardsHtml(guides)+'</div>';
    chat.appendChild(box);
    box.scrollIntoView({block:'nearest'});
  };

  async function postJson(path,body){
    const token=readToken();if(!token)throw new Error('登录状态已失效，请重新登录');
    const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},body:JSON.stringify(body)});
    let data={};try{data=await r.json()}catch{}
    if(!r.ok)throw new Error(data.detail||'请求失败');
    return data;
  }

  const queryImage=document.getElementById('cy-pa-query-image');
  const queryImageStatus=document.getElementById('cy-pa-query-image-status');
  queryImage.onchange=()=>{
    const file=queryImage.files?.[0];
    queryImageStatus.textContent=file?file.name+' · '+Math.ceil(file.size/1024)+' KB':'未选择图片';
  };
  async function ask(question){
    const file=queryImage.files?.[0];
    const text=String(question||'').trim()||(file?'请帮我看看这张图片。':'');
    if(!text)return;
    const askContext=context();
    send.disabled=true;send.textContent='回答中…';
    try{
      const attachment=file?await prepareFeedbackFile(file):null;
      if(attachment&&!['image/jpeg','image/png','image/webp'].includes(attachment.attachment_type))
        throw new Error('仅支持 JPG、PNG 或 WebP 图片');
      const image=attachment?{
        image_name:attachment.attachment_name,image_type:attachment.attachment_type,
        image_size:attachment.attachment_size,image_data:attachment.attachment_data
      }:{};
      const data=await postJson('/v1/product-assistant/query',{question:text,...askContext,...image});
      if(!data.ok)throw new Error(data.reply||'图片暂时无法识别');
      addMessage('user',text+(file?'\n[图片] '+file.name:''),attachment?'data:'+attachment.attachment_type+';base64,'+attachment.attachment_data:'');
      input.value='';queryImage.value='';queryImageStatus.textContent='未选择图片';
      const reply=data.reply||'暂时没有可用回答。';
      addMessage('assistant',reply);maybeAddLearningVisual(text,askContext);const guideInput=Array.isArray(data.cards)&&data.cards.length?data.cards:text+' '+reply;renderGuideGrid(guideInput);addInlineGuideCards(guideInput);
    }catch(err){queryImageStatus.textContent=err.message||'图片发送失败';addMessage('assistant','产品助手暂时无法回答：'+err.message)}
    finally{send.disabled=false;send.textContent='发送'}
  }

  const feedbackReviewHref=record=>{
    const raw=String(record?.acceptanceUrl||record?.page||'/v1').trim()||'/v1';
    let url;
    try{url=new URL(raw,location.origin)}catch{return '/v1'}
    if(url.origin!==location.origin)return '/v1';
    url.searchParams.set('cy_feedback_review',String(record?.id||''));
    url.searchParams.set('cy_feedback_return','/v1/workspace?tab=feedback-records&from=feedback&reviewed='+encodeURIComponent(String(record?.id||''))+'&focus='+encodeURIComponent(String(record?.id||'')));
    return url.pathname+url.search+url.hash;
  };
  const repairFeedbackReviewTarget=async()=>{
    const params=new URLSearchParams(location.search),reviewId=params.get('cy_feedback_review');
    if(!reviewId)return false;
    const token=readToken();if(!token)return false;
    try{
      const r=await fetch('/v1/product-feedback/mine',{headers:{Authorization:'Bearer '+token}});
      const data=await r.json();if(!r.ok)return false;
      const record=(Array.isArray(data.records)?data.records:[]).find(x=>String(x.id)===String(reviewId));
      if(!record)return false;
      const target=new URL(String(record.acceptanceUrl||record.page||'/v1/feedback'),location.origin);
      if(target.origin!==location.origin)return false;
      const current=new URL(location.href);
      current.searchParams.delete('cy_feedback_review');current.searchParams.delete('cy_feedback_return');
      const sameTarget=current.pathname===target.pathname&&current.search===target.search&&current.hash===target.hash;
      if(sameTarget)return false;
      target.searchParams.set('cy_feedback_review',String(reviewId));
      target.searchParams.set('cy_feedback_return',params.get('cy_feedback_return')||('/v1/workspace?tab=feedback-records&from=feedback&reviewed='+encodeURIComponent(String(reviewId))+'&focus='+encodeURIComponent(String(reviewId))));
      location.replace(target.pathname+target.search+target.hash);
      return true;
    }catch(_){return false}
  };
  const mountFeedbackReviewReturn=()=>{
    const params=new URLSearchParams(location.search);
    const reviewId=params.get('cy_feedback_review'),returnTo=params.get('cy_feedback_return');
    if(!reviewId||!returnTo||document.getElementById('cy-feedback-review-return'))return;
    const bar=document.createElement('div');bar.id='cy-feedback-review-return';
    let failTo=returnTo;
    try{const u=new URL(returnTo,location.origin);u.searchParams.set('followup',String(reviewId));failTo=u.pathname+u.search+u.hash}catch{}
    bar.style.cssText='position:fixed;left:12px;right:12px;bottom:calc(14px + env(safe-area-inset-bottom));z-index:2147483000;display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:10px 12px;border:1px solid #bfd2f4;border-radius:14px;background:#fff;box-shadow:0 10px 30px rgba(16,24,40,.18)';
    bar.innerHTML='<span style="font-size:12px;font-weight:800;color:#173a78;flex:1 1 100%">请在当前页面验收反馈 #'+escapeHtml(reviewId)+'</span><a href="'+escapeHtml(failTo)+'" style="flex:1 1 0;min-height:40px;display:inline-flex;align-items:center;justify-content:center;text-decoration:none;background:#fff;color:#a33;border:1px solid #e2b8b8;border-radius:10px;padding:8px 11px;font-size:12px;font-weight:800">未通过 · 追加反馈</a><a href="'+escapeHtml(returnTo)+'" style="flex:1 1 0;min-height:40px;display:inline-flex;align-items:center;justify-content:center;text-decoration:none;background:#173a78;color:#fff;border-radius:10px;padding:8px 11px;font-size:12px;font-weight:800">验收完成 · 返回</a>';
    document.body.appendChild(bar);
    // Feedback #348: on phones the page's own fixed bottom navigation covered
    // this bar, hiding both actions (teachers could not return to their
    // feedback records), while the assistant button and the pending-review
    // pill piled on top. Sit above whatever fixed element occupies the bottom
    // edge, and lift the assistant button / pill above the bar.
    const bottomObstacleTop=()=>{
      let top=window.innerHeight;
      for(const x of [0.2,0.5,0.8])for(const dy of [4,16,32]){
        for(const el of (document.elementsFromPoint?document.elementsFromPoint(window.innerWidth*x,window.innerHeight-dy):[])){
          if(bar.contains(el))continue;
          let node=el;
          while(node&&node!==document.body&&node!==document.documentElement){
            if(getComputedStyle(node).position==='fixed'){
              const r=node.getBoundingClientRect();
              if(r.bottom>=window.innerHeight-24&&r.height<window.innerHeight*0.4&&r.width>window.innerWidth*0.5)top=Math.min(top,r.top);
              break;
            }
            node=node.parentElement;
          }
        }
      }
      return top;
    };
    const syncReviewClearance=()=>{
      bar.style.visibility='hidden';
      const obstacleTop=bottomObstacleTop();
      bar.style.visibility='';
      const lift=obstacleTop<window.innerHeight-1?Math.ceil(window.innerHeight-obstacleTop)+8:0;
      bar.style.bottom=lift?String(lift)+'px':'calc(14px + env(safe-area-inset-bottom))';
      const height=Math.ceil(bar.getBoundingClientRect().height||0),rect=bar.getBoundingClientRect();
      const fromBottom=height?Math.ceil(window.innerHeight-rect.top):0;
      document.documentElement.style.setProperty('--cy-feedback-review-clearance',height?String(height+18)+'px':'0px');
      document.documentElement.style.setProperty('--cy-feedback-review-lift',fromBottom?String(fromBottom+10)+'px':'0px');
    };
    requestAnimationFrame(syncReviewClearance);
    setTimeout(syncReviewClearance,120);
    setTimeout(syncReviewClearance,800);
    setTimeout(syncReviewClearance,2000);
    window.addEventListener('resize',syncReviewClearance,{passive:true});
  };
  repairFeedbackReviewTarget().then(repaired=>{if(!repaired)mountFeedbackReviewReturn()});
  async function loadFeedbackHistory(){
    const box=document.getElementById('cy-pa-history');if(!box)return;
    box.innerHTML='<div class="cy-pa-note">正在读取你的反馈记录…</div>';
    try{
      const token=readToken();if(!token)throw new Error('登录状态已失效，请重新登录');
      const r=await fetch('/v1/product-feedback/mine',{headers:{Authorization:'Bearer '+token}});
      const data=await r.json();if(!r.ok)throw new Error(data.detail||'读取失败');
      const summary=data.rewardSummary||{},items=Array.isArray(data.records)?data.records:[];
      const head='<div class="cy-pa-history-item"><b>反馈奖励</b><small>已采纳 '+Number(summary.adoptedFeedbackCount||0)+' 条 · 待处理 '+Number(summary.pendingFeedbackCount||0)+' 条 · 已获得 '+Number(summary.earnedPoints||0)+' 分</small></div>';
      box.innerHTML=head+(items.length?items.map(x=>{
        const id=Number(x.id),canFollow=x.canFollowUp===true,canConfirm=x.canConfirm===true,accepted=x.terminalAccepted===true,confirmed=x.userDecision?.status==='confirmed';
        const reviewedId=new URLSearchParams(location.search).get('reviewed');
        const reviewed=String(reviewedId||'')===String(id);
        const reviewHref=canConfirm?feedbackReviewHref(x):'';
        const receipt=x.receipt?'<small><b>处理回执：</b>'+escapeHtml(x.receipt)+'</small>':'';
        const terminal=accepted?'<small>该反馈已验收。如有新的问题或需求，请提交一条新反馈。</small>':'';
        const actions=accepted?'':('<div class="cy-pa-history-actions">'+
          (canConfirm?'<a class="btn cy-pa-review-link" href="'+escapeHtml(reviewHref)+'">'+(reviewed?'重新去验收':'已处理 · 点击去验收')+'</a>':'')+
          ((reviewed||canConfirm)&&canFollow?'<button type="button" data-pa-followup-toggle="'+id+'">追加反馈</button>':'')+
          (canConfirm?'<button class="btn primary" type="button" data-pa-confirm-feedback="'+id+'">确认已达预期</button>':'')+
          (confirmed?'<span class="cy-pa-note">你已确认达到预期，等待最终验收。</span>':'')+
          '</div>');
        const followForm=canFollow?'<div data-pa-followup-form="'+id+'" hidden><textarea maxlength="1200" data-pa-followup-text="'+id+'" placeholder="补充新的现象、截图说明或后续建议"></textarea><label class="cy-pa-attachment">📷 添加照片 <input type="file" accept="image/jpeg,image/png,image/webp" data-pa-followup-photo="'+id+'"></label><button class="btn primary" type="button" data-pa-followup-submit="'+id+'">提交追加反馈</button></div>':'';
        return '<div class="cy-pa-history-item" data-pa-history-id="'+id+'"><b>'+escapeHtml(x.category||'产品反馈')+' · '+escapeHtml(x.statusLabel||'已收到')+'</b><small>'+escapeHtml(x.message||'')+'</small>'+receipt+'<small>'+escapeHtml(x.createdAt||'')+(x.rewardPoints?' · 奖励 '+Number(x.rewardPoints)+' 分':'')+'</small>'+terminal+actions+followForm+'</div>';
      }).join(''):'<div class="cy-pa-note">还没有提交过反馈。</div>');
      const params=new URLSearchParams(location.search),focusId=params.get('focus'),followupId=params.get('followup');
      if(focusId){
        const target=box.querySelector('[data-pa-history-id="'+CSS.escape(String(focusId))+'"]');
        if(target){
          target.style.outline='3px solid #7aa2f7';
          target.style.outlineOffset='2px';
          target.scrollIntoView({behavior:'smooth',block:'center'});
          setTimeout(()=>{target.style.outline='';target.style.outlineOffset=''},2600);
        }
      }
      if(followupId){
        const form=box.querySelector('[data-pa-followup-form="'+CSS.escape(String(followupId))+'"]');
        const input=box.querySelector('[data-pa-followup-text="'+CSS.escape(String(followupId))+'"]');
        if(form){form.hidden=false;setTimeout(()=>input?.focus(),80)}
      }
    }catch(err){box.innerHTML='<div class="cy-pa-note">反馈记录读取失败：'+escapeHtml(err.message||'请稍后重试')+'</div>'}
  }
  async function loadFeedbackDropdownRecords(){
    const box=document.getElementById('cy-pa-feedback-dropdown-records');if(!box)return;
    box.innerHTML='<div class="cy-pa-note">正在读取反馈记录…</div>';
    try{
      const token=readToken();if(!token)throw new Error('登录状态已失效，请重新登录');
      const r=await fetch('/v1/product-feedback/mine',{headers:{Authorization:'Bearer '+token}});
      const data=await r.json();if(!r.ok)throw new Error(data.detail||'读取失败');
      const summary=data.rewardSummary||{},items=Array.isArray(data.records)?data.records:[];
      const summaryHtml='<div class="cy-pa-note"><b>反馈记录</b> · 已采纳 '+Number(summary.adoptedFeedbackCount||0)+' 条 · 已获得 '+Number(summary.earnedPoints||0)+' 分</div>';
      const recordsHtml=items.length?items.map(x=>{
        const id=Number(x.id),follow=x.canFollowUp===true&&x.terminalAccepted!==true,canConfirm=x.canConfirm===true;
        const processedCta=canConfirm?'<a class="primary" data-pa-dropdown-review="'+id+'" href="'+escapeHtml(feedbackReviewHref(x))+'">已处理 · 点击去验收</a>':'';
        return '<div class="cy-pa-feedback-dropdown-record" data-pa-dropdown-record="'+id+'">'+
          '<b>'+escapeHtml(x.category||'产品反馈')+' · '+escapeHtml(x.statusLabel||'已收到')+'</b>'+
          '<small>'+escapeHtml(x.message||'')+'</small>'+
          '<small><b>取用状态：</b>'+escapeHtml(x.statusLabel||'已收到')+' · <b>奖励分：</b>'+Number(x.rewardPoints||0)+'</small>'+
          '<small><b>回执：</b>'+escapeHtml(x.receipt||'已收到，等待处理回执')+'</small>'+
          '<div class="cy-pa-feedback-dropdown-actions">'+processedCta+'<button type="button" data-pa-dropdown-open="'+id+'">查看记录</button>'+
          (follow?'<button type="button" data-pa-dropdown-followup="'+id+'">追加反馈（可传照片）</button>':'')+
          '</div></div>';
      }).join(''):'<div class="cy-pa-note">还没有提交过反馈。</div>';
      box.innerHTML=summaryHtml+recordsHtml;
    }catch(err){box.innerHTML='<div class="cy-pa-note">反馈记录读取失败：'+escapeHtml(err.message||'请稍后重试')+'</div>'}
  }
  document.getElementById('cy-pa-feedback-dropdown-records')?.addEventListener('click',event=>{
    const follow=event.target.closest('[data-pa-dropdown-followup]');
    const open=event.target.closest('[data-pa-dropdown-open]');
    const id=String(follow?.dataset.paDropdownFollowup||open?.dataset.paDropdownOpen||'');
    if(!id)return;
    const u=new URL('/v1/workspace',location.origin);
    u.searchParams.set('tab','feedback-records');
    u.searchParams.set('focus',id);
    if(follow)u.searchParams.set('followup',id);
    location.href=u.pathname+u.search;
  });
  document.getElementById('cy-pa-history')?.addEventListener('click',async event=>{
    const toggle=event.target.closest('[data-pa-followup-toggle]');
    if(toggle){const form=document.querySelector('[data-pa-followup-form="'+toggle.dataset.paFollowupToggle+'"]');if(form)form.hidden=!form.hidden;return}
    const confirm=event.target.closest('[data-pa-confirm-feedback]');
    if(confirm){
      confirm.disabled=true;
      try{await postJson('/v1/product-feedback/mine/'+confirm.dataset.paConfirmFeedback+'/acknowledge',{});await loadFeedbackHistory()}
      catch(err){confirm.disabled=false;alert(err.message||'确认失败')}
      return;
    }
    const submit=event.target.closest('[data-pa-followup-submit]');
    if(!submit)return;
    const id=submit.dataset.paFollowupSubmit;
    const input=document.querySelector('[data-pa-followup-text="'+id+'"]');
    const message=String(input?.value||'').trim();if(!message){input?.focus();return}
    const photo=document.querySelector('[data-pa-followup-photo="'+id+'"]')?.files?.[0];
    submit.disabled=true;
    try{
      let attachment={};
      if(photo){
        if(!['image/jpeg','image/png','image/webp'].includes(photo.type))throw new Error('追加反馈照片仅支持 JPG、PNG 或 WebP');
        attachment=await prepareFeedbackFile(photo);
      }
      await postJson('/v1/product-feedback/mine/'+id+'/follow-up',{message,...attachment});
      await loadFeedbackHistory();
    }catch(err){submit.disabled=false;alert(err.message||'追加反馈失败')}
  });
  function setTab(name){
    document.querySelectorAll('.cy-pa-tab').forEach(x=>x.classList.toggle('active',x.dataset.paTab===name));
    ['ask','feedback','records'].forEach(id=>{const el=document.getElementById('cy-pa-'+id);if(el)el.hidden=id!==name});
    if(name==='records')loadFeedbackHistory();
  }
  const closePanel=()=>{panel.hidden=true;fab.hidden=!identityReady();fab.setAttribute('aria-label','打开产品助手')};
  const openPanel=()=>{if(!identityReady())return;panel.hidden=false;fab.hidden=true;fab.setAttribute('aria-label','收起产品助手');updateContext();applyRoleCopy();renderGuideGrid()};
  fab.onclick=()=>panel.hidden?openPanel():closePanel();
  document.getElementById('cy-pa-collapse').onclick=closePanel;
  document.querySelectorAll('[data-pa-category]').forEach(btn=>btn.onclick=()=>{
    document.querySelectorAll('[data-pa-category]').forEach(x=>x.classList.toggle('active',x===btn));
    document.getElementById('cy-pa-category').value=btn.dataset.paCategory;
  });
  const feedbackMenuButton=document.getElementById('cy-pa-feedback-menu-button'),feedbackDropdown=document.getElementById('cy-pa-feedback-dropdown');
  const closeFeedbackMenu=()=>{if(feedbackDropdown)feedbackDropdown.hidden=true;if(feedbackMenuButton)feedbackMenuButton.setAttribute('aria-expanded','false')};
  if(feedbackMenuButton)feedbackMenuButton.onclick=async()=>{const opening=feedbackDropdown?.hidden!==false;if(feedbackDropdown)feedbackDropdown.hidden=!opening;feedbackMenuButton.setAttribute('aria-expanded',opening?'true':'false');if(opening)await loadFeedbackDropdownRecords()};
  document.querySelectorAll('[data-pa-tab]').forEach(x=>x.onclick=()=>{setTab(x.dataset.paTab);closeFeedbackMenu()});
  document.addEventListener('click',event=>{if(!event.target.closest('.cy-pa-feedback-menu'))closeFeedbackMenu()});
  const initialAssistantTab=new URLSearchParams(location.search).get('tab');
  let initialAssistantRoutePending=initialAssistantTab==='feedback-records'||initialAssistantTab==='feedback'||initialAssistantTab==='ask';
  const openInitialAssistantRoute=()=>{
    if(!initialAssistantRoutePending||!identityReady())return false;
    if(initialAssistantTab==='feedback-records')setTab('records');
    else if(initialAssistantTab==='feedback')setTab('feedback');
    else if(initialAssistantTab==='ask')setTab('ask');
    panel.hidden=false;fab.hidden=true;initialAssistantRoutePending=false;
    return true;
  };
  openInitialAssistantRoute();
  document.querySelectorAll('[data-pa-question]').forEach(x=>x.onclick=()=>ask(x.dataset.paQuestion));
  send.onclick=()=>ask(input.value);
  input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();ask(input.value)}});

  const feedbackFile=document.getElementById('cy-pa-feedback-file');
  const attachmentStatus=document.getElementById('cy-pa-attachment-status');
  feedbackFile.onchange=()=>{
    const file=feedbackFile.files?.[0];
    attachmentStatus.textContent=file?file.name+' · '+Math.ceil(file.size/1024)+' KB · 点击可重新选择':'未选择文件';
  };
  const readFeedbackFile=file=>new Promise((resolve,reject)=>{
    const reader=new FileReader();
    reader.onerror=()=>reject(new Error('文件读取失败'));
    reader.onload=()=>resolve(String(reader.result||'').split(',')[1]||'');
    reader.readAsDataURL(file);
  });
  const prepareFeedbackFile=async file=>{
    if(file.size<=1000000)return {
      attachment_name:file.name,attachment_type:file.type,
      attachment_size:file.size,attachment_data:await readFeedbackFile(file)
    };
    if(!file.type.startsWith('image/'))throw new Error('文件需在 1 MB 以内');
    const url=URL.createObjectURL(file);
    try{
      const image=new Image();
      await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=reject;image.src=url});
      const scale=Math.min(1,1200/Math.max(image.width,image.height));
      const canvas=document.createElement('canvas');
      canvas.width=Math.max(1,Math.round(image.width*scale));
      canvas.height=Math.max(1,Math.round(image.height*scale));
      const ctx=canvas.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height);
      ctx.drawImage(image,0,0,canvas.width,canvas.height);
      let encoded=canvas.toDataURL('image/jpeg',.76).split(',')[1];
      if(atob(encoded).length>1000000)encoded=canvas.toDataURL('image/jpeg',.55).split(',')[1];
      const size=atob(encoded).length;
      if(size>1000000)throw new Error('照片压缩后仍超过 1 MB');
      return {attachment_name:file.name.replace(/\\.[^.]+$/,'')+'.jpg',
        attachment_type:'image/jpeg',attachment_size:size,attachment_data:encoded};
    }finally{URL.revokeObjectURL(url)}
  };
  document.getElementById('cy-pa-submit-feedback').onclick=async()=>{
    const message=document.getElementById('cy-pa-feedback-text').value.trim();
    if(!message)return;
    const file=feedbackFile.files?.[0];
    if(file&&!file.size){attachmentStatus.textContent='不能发送空文件';return}
    const btn=document.getElementById('cy-pa-submit-feedback');btn.disabled=true;btn.textContent='提交中…';
    try{
      const attachment=file?await prepareFeedbackFile(file):{};
      const result=await postJson('/v1/product-feedback',{category:document.getElementById('cy-pa-category').value,message,...context(),...attachment});
      document.getElementById('cy-pa-feedback-text').value='';feedbackFile.value='';attachmentStatus.textContent='未选择文件';
      btn.textContent=result.freemanSynced?'已同步到 Freeman ✓':'反馈已收到 · Freeman 同步待确认';
      setTimeout(()=>{btn.textContent='提交反馈';btn.disabled=false},2200);
    }catch(err){attachmentStatus.textContent=err.message||'附件发送失败';btn.textContent='提交失败，重试';btn.disabled=false}
  };


  // Login notification reads server-owned acceptance eligibility, never rewards or PR claims.
  const processedNotice=document.getElementById('cy-pa-processed-notice');
  let noticeToken='',noticeCheckedAt=0,noticeRequest=0;
  const shownProcessedFeedback=new Set();
  function pendingProcessedFeedback(records){
    return (Array.isArray(records)?records:[]).filter(x=>
      Number.isSafeInteger(Number(x?.id))&&Number(x.id)>0&&x.canConfirm===true&&
      x.terminalAccepted!==true&&x.acknowledged!==true&&x.userDecision?.status!=='confirmed'
    );
  }
  function resetProcessedNotice(){
    noticeToken='';noticeCheckedAt=0;noticeRequest++;shownProcessedFeedback.clear();
    if(processedNotice){processedNotice.hidden=true;processedNotice.replaceChildren()}
  }
  async function checkProcessedFeedbackNotice(){
    if(!processedNotice||!identityReady())return;
    const token=readToken();
    if(token!==noticeToken){
      noticeToken=token;noticeCheckedAt=0;noticeRequest++;shownProcessedFeedback.clear();
      processedNotice.hidden=true;processedNotice.replaceChildren();
    }
    if(noticeCheckedAt&&Date.now()-noticeCheckedAt<60000)return;
    noticeCheckedAt=Date.now();
    const request=++noticeRequest;
    try{
      const response=await fetch('/v1/product-feedback/mine',{headers:{Authorization:'Bearer '+token},cache:'no-store'});
      if(!response.ok)return;
      const data=await response.json();
      if(request!==noticeRequest||readToken()!==token||!identityReady())return;
      const pending=pendingProcessedFeedback(data.records);
      if(!pending.length){processedNotice.hidden=true;processedNotice.replaceChildren();return}
      const unseen=pending.filter(x=>!shownProcessedFeedback.has(Number(x.id)));
      if(!unseen.length)return;
      unseen.forEach(x=>shownProcessedFeedback.add(Number(x.id)));
      processedNotice.replaceChildren();
      const link=document.createElement('a');
      link.className='cy-pa-processed-record';
      link.setAttribute('aria-label','有反馈已处理，点击查看并验收');
      link.textContent=unseen.length>1?'有 '+unseen.length+' 条反馈待验收 · 点击查看':'反馈待验收 · 点击查看';
      const target=new URL('/v1/workspace',location.origin);
      target.searchParams.set('tab','feedback-records');
      target.searchParams.set('focus',String(Number(unseen[0].id)));
      link.href=target.pathname+target.search;
      processedNotice.appendChild(link);
      processedNotice.hidden=false;
    }catch{ /* A failed check must not interrupt login or claim feedback completion. */ }
  }

  const observedIdentityNodes=new WeakSet();
  const identityObserver=new MutationObserver(()=>queueMicrotask(sync));
  const observeIdentityNodes=()=>{
    const button=getIdentityButton(),chip=getIdentityChip();
    if(button&&!observedIdentityNodes.has(button)){identityObserver.observe(button,{attributes:true,attributeFilter:['hidden']});observedIdentityNodes.add(button)}
    if(chip&&!observedIdentityNodes.has(chip)){identityObserver.observe(chip,{childList:true,characterData:true,subtree:true});observedIdentityNodes.add(chip)}
  };
  const sync=()=>{observeIdentityNodes();const ready=identityReady();if(!ready)resetProcessedNotice();if(!ready){fab.hidden=true;panel.hidden=true;return}checkProcessedFeedbackNotice();openInitialAssistantRoute();fab.hidden=!panel.hidden;updateContext();applyRoleCopy();if(!panel.hidden)renderGuideGrid()};
  window.addEventListener('pageshow',sync);window.addEventListener('popstate',sync);window.addEventListener('focus',sync);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)sync()});
  let authReadyPoll=null;
  const syncUntilReady=()=>{sync();if(identityReady()&&authReadyPoll){clearInterval(authReadyPoll);authReadyPoll=null}};
  authReadyPoll=setInterval(syncUntilReady,400);
  setTimeout(()=>{if(authReadyPoll){clearInterval(authReadyPoll);authReadyPoll=null}sync()},12000);
  setTimeout(syncUntilReady,0);setTimeout(syncUntilReady,300);
})();
</script>
'''


def patch_v1_product_assistant(html: str) -> str:
    feedback_ui_revision = 'data-feedback-ui-revision="3"'
    if V1_PRODUCT_ASSISTANT_MARKER in html and feedback_ui_revision in html and 'data-feedback-notification-revision="3"' in html:
        return html
    if V1_PRODUCT_ASSISTANT_MARKER in html:
        # An older assistant injection must not suppress a newer feedback UI.
        # Strip the old injected block so the current snippet becomes the sole
        # feedback/assistant control surface in the final HTML response.
        html = re.sub(
            r'<style id="changying_v1_product_assistant_v1-css">.*?<!-- changying_v1_product_assistant_v1 -->',
            '',
            html,
            count=1,
            flags=re.S,
        )
    if "</body>" not in html:
        raise RuntimeError("V1 product assistant: closing body marker not found")
    feedback_center = Path(__file__).with_name("feedback_center.js").read_text(encoding="utf-8")
    return html.replace(
        "</body>",
        _ASSISTANT_SNIPPET
        + "\n<script id=\"changying-feedback-center-script\">"
        + feedback_center
        + "</script>"
        + f"\n<!-- {V1_PRODUCT_ASSISTANT_MARKER} -->\n</body>",
        1,
    )


def install_v1_product_assistant_patch() -> None:
    if not getattr(v1_module, "_product_assistant_patch_installed", False):
        original = v1_module.v1_html

        def patched_v1_html() -> str:
            return patch_v1_product_assistant(original())

        v1_module.v1_html = patched_v1_html
        v1_module._product_assistant_patch_installed = True

    if not getattr(classic_embed_module, "_product_assistant_unified_installed", False):
        original_unified = classic_embed_module.enhance_unified_classic_html

        def patched_unified_classic_html(html: str) -> str:
            return patch_v1_product_assistant(original_unified(html))

        classic_embed_module.enhance_unified_classic_html = patched_unified_classic_html
        classic_embed_module._product_assistant_unified_installed = True


# Feedback #332: raised math-generation difficulty contract.
MATH_DIFFICULTY_LEVELS = ["基础", "提高", "挑战"]
MATH_DIFFICULTY_MIN_OPERANDS = {"基础": 2, "提高": 3, "挑战": 4}
MATH_DIFFICULTY_MIN_STEPS = {"基础": 2, "提高": 3, "挑战": 4}
MATH_DIFFICULTY_RAISED_MARKER = "math-difficulty-raised-v1"


def math_difficulty_contract(level: str | None = None) -> dict:
    levels = [level] if level in MATH_DIFFICULTY_LEVELS else list(MATH_DIFFICULTY_LEVELS)
    return {
        "marker": MATH_DIFFICULTY_RAISED_MARKER,
        "raised": True,
        "levels": levels,
        "minOperands": {name: MATH_DIFFICULTY_MIN_OPERANDS[name] for name in levels},
        "minSteps": {name: MATH_DIFFICULTY_MIN_STEPS[name] for name in levels},
    }


__all__ = [
    "FEEDBACK_PATH",
    "FEEDBACK_PROOF_PREFIX",
    "FEEDBACK_PAGE_PATH",
    "QUERY_PATH",
    "V1_PRODUCT_ASSISTANT_MARKER",
    "install_v1_product_assistant_patch",
    "install_v1_product_assistant_routes",
    "patch_v1_product_assistant",
    "MATH_DIFFICULTY_LEVELS",
    "MATH_DIFFICULTY_MIN_OPERANDS",
    "MATH_DIFFICULTY_MIN_STEPS",
    "MATH_DIFFICULTY_RAISED_MARKER",
    "math_difficulty_contract",
]
