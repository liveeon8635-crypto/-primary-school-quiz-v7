"""Context-aware product assistant and feedback channel for Changying V1.

The assistant is available only after an authenticated account has selected an
identity. Product questions are answered with product-only context; feedback is
recorded through the existing audit log so no new schema is required.
"""

from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timedelta
from types import ModuleType

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from changying.web import v1 as v1_module
from changying.web import v1_classic_gzip_embed as classic_embed_module


V1_PRODUCT_ASSISTANT_MARKER = "changying_v1_product_assistant_v1"
QUERY_PATH = "/v1/product-assistant/query"
FEEDBACK_PATH = "/v1/product-feedback"
FEEDBACK_PROOF_PREFIX = "/v1/product-feedback/proof"
FREEMAN_FEEDBACK_IMPORT_URL = "https://freeman-agent.onrender.com/api/project-feedback/import"
FEEDBACK_PROOF_TTL_MINUTES = 15


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


class ProductFeedbackBody(BaseModel):
    category: str = Field(default="其他反馈", max_length=60)
    message: str = Field(min_length=1, max_length=1200)
    page: str = Field(default="", max_length=240)
    identity: str = Field(default="", max_length=160)
    tutorial_step: str = Field(default="", max_length=200)
    attachment_name: str = Field(default="", max_length=240)
    attachment_type: str = Field(default="", max_length=120)
    attachment_size: int = Field(default=0, ge=0, le=8_000_000)
    attachment_data: str = Field(default="", max_length=12_000_000)


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
11. 当前产品助手没有图片/拍照上传入口。不要要求用户“拍照发来”“上传图片”或使用并不存在的控件；学生在答题页时优先使用已经关联到的当前题目和题目图示可见文字。

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
            "正确答案",
            "标准答案",
            "抄答案",
            "代做",
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

def install_v1_product_assistant_routes(implementation: ModuleType) -> None:
    app = implementation.app
    if getattr(app.state, "v1_product_assistant_routes_installed", False):
        return

    router = APIRouter()

    @router.post(QUERY_PATH, include_in_schema=False)
    def product_assistant_query(
        body: ProductAssistantBody,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        question = body.question.strip()
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
        )
        try:
            reply = implementation._ai_call(
                db,
                user,
                "product_assistant",
                prompt,
                timeout=45,
            )
            return {
                "ok": True,
                "reply": _clean_assistant_reply(reply)[:5000],
                "source": "ai",
                "degraded": False,
            }
        except HTTPException:
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
        except Exception:
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
        proof_token = secrets.token_urlsafe(24)
        payload = {
            "category": body.category.strip() or "其他反馈",
            "message": body.message.strip(),
            "page": body.page.strip(),
            "identity": body.identity.strip(),
            "tutorialStep": body.tutorial_step.strip(),
            "transferToken": proof_token,
        }
        implementation.audit(
            db,
            user,
            "product.feedback",
            json.dumps(payload, ensure_ascii=False)[:1800],
        )
        db.commit()

        synced = False
        try:
            response = requests.post(
                FREEMAN_FEEDBACK_IMPORT_URL,
                json={"projectId": "longying", "proofToken": proof_token},
                timeout=4,
            )
            synced = bool(response.ok)
        except requests.RequestException:
            synced = False
        return {"ok": True, "received": True, "freemanSynced": synced}

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
        if datetime.utcnow() - created_at > timedelta(minutes=FEEDBACK_PROOF_TTL_MINUTES):
            raise HTTPException(410, "反馈凭证已过期")
        try:
            payload = json.loads(row.detail or "{}")
        except Exception:
            raise HTTPException(404, "反馈凭证无效")
        if payload.get("transferToken") != token:
            raise HTTPException(404, "反馈凭证无效")
        return {
            "ok": True,
            "projectId": "longying",
            "feedback": {
                "sourceId": row.id,
                "category": str(payload.get("category") or "其他反馈")[:60],
                "message": str(payload.get("message") or "")[:1200],
                "page": str(payload.get("page") or "")[:240],
                "identity": str(payload.get("identity") or "")[:160],
                "tutorialStep": str(payload.get("tutorialStep") or "")[:200],
                "createdAt": created_at.isoformat() + "Z",
            },
        }

    app.include_router(router)
    app.state.v1_product_assistant_routes_installed = True


_ASSISTANT_SNIPPET = r'''
<style id="changying_v1_product_assistant_v1-css">
  #cy-product-assistant-fab{position:fixed;right:14px;bottom:calc(84px + env(safe-area-inset-bottom));z-index:125;border:0;border-radius:999px;background:#173a78;color:#fff;width:48px;height:48px;padding:0;font-weight:900;box-shadow:0 10px 28px rgba(23,58,120,.24);display:grid;place-items:center;font-size:20px}#cy-product-assistant-fab .cy-pa-fab-label{display:none}
  #cy-product-assistant-fab[hidden],#cy-product-assistant-panel[hidden]{display:none!important}
  #cy-product-assistant-panel{position:fixed;right:14px;bottom:calc(142px + env(safe-area-inset-bottom));z-index:126;width:min(390px,calc(100vw - 28px));max-height:min(620px,70dvh);background:#fff;border:1px solid #dbe4f1;border-radius:20px;box-shadow:0 22px 70px rgba(17,34,64,.28);overflow:hidden;display:flex;flex-direction:column}
  .cy-pa-head{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:11px 12px;border-bottom:1px solid #e2e8f1}.cy-pa-head b{display:block}.cy-pa-head small{display:block;max-width:240px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--muted);line-height:1.35}.cy-pa-head-actions{display:flex;gap:6px}.cy-pa-head-actions .btn{min-height:36px;padding:7px 10px}
  .cy-pa-tabs{display:grid;grid-template-columns:1fr 1fr;padding:9px;gap:7px;background:#f7f9fc}.cy-pa-tab{border:1px solid #dbe4f1;background:#fff;border-radius:11px;padding:9px;font-weight:750}.cy-pa-tab.active{background:#eaf1ff;border-color:#bfd2f4;color:#173a78}
  .cy-pa-body{padding:10px 11px;overflow:auto}.cy-pa-quick{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}.cy-pa-quick button{border:1px solid #dbe4f1;background:#fff;border-radius:999px;padding:6px 8px;font-size:11px}
  .cy-pa-chat{display:grid;gap:9px;margin-bottom:10px}.cy-pa-msg{max-width:92%;padding:10px 11px;border-radius:13px;line-height:1.55;font-size:13px;white-space:pre-wrap}.cy-pa-msg.user{justify-self:end;background:#173a78;color:#fff}.cy-pa-msg.assistant{justify-self:start;background:#f1f5fb;color:#1c2940}
  .cy-pa-learning-visual{justify-self:start;width:min(92%,330px);border:1px solid #dbe5f3;background:#fff;border-radius:14px;padding:10px;display:grid;gap:8px}.cy-pa-learning-visual b{font-size:12px;color:#173a78}.cy-pa-learning-visual small{font-size:10px;color:var(--muted);line-height:1.45}.cy-pa-fraction-grid{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:3px;height:42px}.cy-pa-fraction-cell{border:1px solid #9fb6da;border-radius:5px;background:#f5f8fd}.cy-pa-fraction-cell.is-given{background:#dbe8ff}.cy-pa-bar-model{display:grid;gap:5px}.cy-pa-bar-track{display:grid;grid-template-columns:1.15fr .85fr;height:42px;border:1px solid #9fb6da;border-radius:8px;overflow:hidden}.cy-pa-bar-known,.cy-pa-bar-unknown{display:grid;place-items:center;font-size:10px}.cy-pa-bar-known{background:#dbe8ff}.cy-pa-bar-unknown{background:#f7f9fc;border-left:1px dashed #9fb6da}.cy-pa-shape-box{height:86px;display:grid;place-items:center}.cy-pa-shape{border:2px solid #6c88b4;display:grid;place-items:center;color:#52647f;font-size:11px}.cy-pa-shape.rectangle{width:150px;height:68px}.cy-pa-shape.square{width:74px;height:74px}.cy-pa-shape.circle{width:74px;height:74px;border-radius:50%}.cy-pa-shape.triangle{width:0;height:0;border-left:48px solid transparent;border-right:48px solid transparent;border-bottom:78px solid #dbe8ff;border-top:0;position:relative}.cy-pa-numberline{position:relative;height:54px;margin:2px 8px}.cy-pa-numberline-line{position:absolute;left:0;right:0;top:24px;border-top:2px solid #6c88b4}.cy-pa-numberline-tick{position:absolute;top:17px;transform:translateX(-50%);font-size:9px;color:#52647f}.cy-pa-numberline-tick:before{content:'';display:block;width:1px;height:15px;background:#6c88b4;margin:0 auto 2px}
  .cy-pa-compose{display:grid;grid-template-columns:1fr auto;gap:7px}.cy-pa-compose textarea{min-height:58px;resize:none}.cy-pa-compose .btn{align-self:end}
  .cy-pa-feedback{display:grid;gap:8px}.cy-pa-feedback textarea{min-height:76px;resize:none}.cy-pa-feedback-cats{display:flex;gap:6px;flex-wrap:wrap}.cy-pa-feedback-cats button{border:1px solid #dbe4f1;background:#fff;border-radius:999px;padding:6px 9px;font-size:11px}.cy-pa-feedback-cats button.active{background:#eaf1ff;border-color:#bfd2f4;color:#173a78;font-weight:800}.cy-pa-note{font-size:10px;color:var(--muted);line-height:1.45}.cy-pa-guide{border:1px solid #dbe5f3;background:#f8fbff;border-radius:14px;padding:9px}.cy-pa-guide-title{font-size:12px;font-weight:850;color:#173a78;margin-bottom:7px}.cy-pa-guide-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.cy-pa-guide-card{display:grid;gap:5px;text-decoration:none;color:#182238;background:#fff;border:1px solid #dbe5f3;border-radius:11px;overflow:hidden}.cy-pa-guide-visual{height:74px;background:#edf3ff;padding:8px;display:grid;grid-template-rows:12px 1fr;gap:7px}.cy-pa-guide-bar{border-radius:6px;background:#d5e2f6}.cy-pa-guide-page{display:grid;grid-template-columns:38px 1fr;gap:8px;align-items:center}.cy-pa-guide-icon{height:38px;border-radius:9px;background:#fff;display:grid;place-items:center;font-size:20px;color:#244c91}.cy-pa-guide-lines{display:grid;gap:5px}.cy-pa-guide-lines i{display:block;height:6px;border-radius:3px;background:#fff}.cy-pa-guide-lines i:last-child{width:66%}.cy-pa-guide-copy{padding:0 7px 7px;display:grid;gap:2px}.cy-pa-guide-copy b{font-size:11px}.cy-pa-guide-copy small{font-size:9px;color:var(--muted);line-height:1.35}
  @media(max-width:640px){#cy-product-assistant-fab{right:12px;bottom:calc(78px + env(safe-area-inset-bottom));width:44px;height:44px;font-size:18px}#cy-product-assistant-panel{left:10px;right:10px;bottom:calc(128px + env(safe-area-inset-bottom));width:auto;max-height:62dvh}}
</style>
<button id="cy-product-assistant-fab" hidden aria-label="打开产品助手" title="产品助手">✦<span class="cy-pa-fab-label">产品助手</span></button>
<section id="cy-product-assistant-panel" hidden aria-label="长缨产品助手">
  <header class="cy-pa-head"><div><b>长缨产品助手</b><small id="cy-pa-context">读取当前身份与页面…</small></div><div class="cy-pa-head-actions"><button class="btn" id="cy-pa-collapse" aria-label="收起">−</button></div></header>
  <div class="cy-pa-tabs"><button class="cy-pa-tab active" id="cy-pa-ask-tab" data-pa-tab="ask">问产品</button><button class="cy-pa-tab" data-pa-tab="feedback">提反馈</button></div>
  <div class="cy-pa-body" id="cy-pa-ask">
    <div class="cy-pa-quick"><button id="cy-pa-quick-1" data-pa-question="我现在该做什么？">下一步做什么</button><button id="cy-pa-quick-2" data-pa-question="这个页面是干什么的？">页面用途</button><button id="cy-pa-quick-3" data-pa-question="这一步为什么排在这里？">为什么这样走</button></div>
    <div class="cy-pa-guide" id="cy-pa-guide">
      <div class="cy-pa-guide-title">页面示意 · 点卡片直达</div>
      <div class="cy-pa-guide-grid" id="cy-pa-guide-grid"></div>
      <div class="cy-pa-note">页面示意直接随助手生成，不依赖额外图片下载；点击即可进入对应功能页。</div>
    </div>
    <div class="cy-pa-chat" id="cy-pa-chat"><div class="cy-pa-msg assistant" id="cy-pa-welcome">我会结合你当前登录身份、所在页面和新手教学步骤回答长缨怎么用；也会用页面示意卡标出相关入口。</div></div>
    <div class="cy-pa-compose"><textarea id="cy-pa-input" placeholder="例如：这个页面应该先做什么？"></textarea><button class="btn primary" id="cy-pa-send">发送</button></div>
  </div>
  <div class="cy-pa-body" id="cy-pa-feedback" hidden>
    <div class="cy-pa-feedback"><input type="hidden" id="cy-pa-category" value="这里不好懂"><div class="cy-pa-feedback-cats"><button class="active" data-pa-category="这里不好懂">不好懂</button><button data-pa-category="没找到入口">找不到</button><button data-pa-category="流程不直观">流程不顺</button><button data-pa-category="功能与预期不符">不符合预期</button><button data-pa-category="希望增加功能">想加功能</button><button data-pa-category="其他反馈">其他</button></div><textarea id="cy-pa-feedback-text" placeholder="一句话描述问题或建议（不要填写密码、API Key 等敏感信息）"></textarea><button class="btn primary" id="cy-pa-submit-feedback">提交</button><div class="cy-pa-note">会自动附带当前页面、当前身份和正在进行的新手步骤。</div></div>
  </div>
</section>
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
  const addMessage=(kind,text)=>{const el=document.createElement('div');el.className='cy-pa-msg '+kind;el.textContent=kind==='assistant'?cleanReplyText(text):text;chat.appendChild(el);chat.scrollTop=chat.scrollHeight};
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
  const guideCandidates=text=>{
    const c=context(),role=guideRole(c.identity),pool=GUIDE_SETS[role]||GUIDE_SETS.teacher;
    const ranked=pool.map((g,order)=>({g,order,score:guideScore(g,text,c.page)})).sort((a,b)=>b.score-a.score||a.order-b.order);
    const picked=ranked.filter(x=>x.score>0).slice(0,3).map(x=>x.g);
    return picked.length?picked:pool.slice(0,3);
  };
  const renderGuideGrid=text=>{
    const grid=document.getElementById('cy-pa-guide-grid');if(!grid)return;
    grid.innerHTML=guideCandidates(text).map(g=>'<a class="cy-pa-guide-card" href="'+escapeHtml(g.href)+'" data-pa-guide="'+escapeHtml(g.id)+'"><span class="cy-pa-guide-visual" role="img" aria-label="'+escapeHtml(g.title)+'页面示意图"><span class="cy-pa-guide-bar"></span><span class="cy-pa-guide-page"><span class="cy-pa-guide-icon">'+escapeHtml(g.icon)+'</span><span class="cy-pa-guide-lines"><i></i><i></i></span></span></span><span class="cy-pa-guide-copy"><b>'+escapeHtml(g.title)+'</b><small>'+escapeHtml(g.hint)+'</small></span></a>').join('');
  };

  async function postJson(path,body){
    const token=readToken();if(!token)throw new Error('登录状态已失效，请重新登录');
    const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},body:JSON.stringify(body)});
    let data={};try{data=await r.json()}catch{}
    if(!r.ok)throw new Error(data.detail||'请求失败');
    return data;
  }

  async function ask(question){
    const text=String(question||'').trim();if(!text)return;
    const askContext=context();
    addMessage('user',text);input.value='';send.disabled=true;send.textContent='回答中…';
    try{
      const data=await postJson('/v1/product-assistant/query',{question:text,...askContext});
      const reply=data.reply||'暂时没有可用回答。';
      addMessage('assistant',reply);maybeAddLearningVisual(text,askContext);renderGuideGrid(text+' '+reply);
    }catch(err){addMessage('assistant','产品助手暂时无法回答：'+err.message)}
    finally{send.disabled=false;send.textContent='发送'}
  }

  function setTab(name){
    document.querySelectorAll('.cy-pa-tab').forEach(x=>x.classList.toggle('active',x.dataset.paTab===name));
    document.getElementById('cy-pa-ask').hidden=name!=='ask';
    document.getElementById('cy-pa-feedback').hidden=name!=='feedback';
    updateContext();
  }

  const closePanel=()=>{panel.hidden=true;fab.hidden=!identityReady();fab.setAttribute('aria-label','打开产品助手')};
  const openPanel=()=>{if(!identityReady())return;panel.hidden=false;fab.hidden=true;fab.setAttribute('aria-label','收起产品助手');updateContext();applyRoleCopy();renderGuideGrid()};
  fab.onclick=()=>panel.hidden?openPanel():closePanel();
  document.getElementById('cy-pa-collapse').onclick=closePanel;
  document.querySelectorAll('[data-pa-category]').forEach(btn=>btn.onclick=()=>{
    document.querySelectorAll('[data-pa-category]').forEach(x=>x.classList.toggle('active',x===btn));
    document.getElementById('cy-pa-category').value=btn.dataset.paCategory;
  });
  document.querySelectorAll('.cy-pa-tab').forEach(x=>x.onclick=()=>setTab(x.dataset.paTab));
  document.querySelectorAll('[data-pa-question]').forEach(x=>x.onclick=()=>ask(x.dataset.paQuestion));
  send.onclick=()=>ask(input.value);
  input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();ask(input.value)}});

  document.getElementById('cy-pa-submit-feedback').onclick=async()=>{
    const message=document.getElementById('cy-pa-feedback-text').value.trim();
    if(!message)return;
    const btn=document.getElementById('cy-pa-submit-feedback');btn.disabled=true;btn.textContent='提交中…';
    try{
      const result=await postJson('/v1/product-feedback',{category:document.getElementById('cy-pa-category').value,message,...context()});
      document.getElementById('cy-pa-feedback-text').value='';
      btn.textContent=result.freemanSynced?'已同步到 Freeman ✓':'反馈已收到 · Freeman 同步待确认';
      setTimeout(()=>{btn.textContent='提交反馈';btn.disabled=false},2200);
    }catch(err){btn.textContent='提交失败，重试';btn.disabled=false}
  };

  const observedIdentityNodes=new WeakSet();
  const identityObserver=new MutationObserver(()=>queueMicrotask(sync));
  const observeIdentityNodes=()=>{
    const button=getIdentityButton(),chip=getIdentityChip();
    if(button&&!observedIdentityNodes.has(button)){identityObserver.observe(button,{attributes:true,attributeFilter:['hidden']});observedIdentityNodes.add(button)}
    if(chip&&!observedIdentityNodes.has(chip)){identityObserver.observe(chip,{childList:true,characterData:true,subtree:true});observedIdentityNodes.add(chip)}
  };
  const sync=()=>{observeIdentityNodes();const ready=identityReady();if(!ready){fab.hidden=true;panel.hidden=true;return}fab.hidden=!panel.hidden;updateContext();applyRoleCopy();if(!panel.hidden)renderGuideGrid()};
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
    if V1_PRODUCT_ASSISTANT_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V1 product assistant: closing body marker not found")
    return html.replace(
        "</body>",
        _ASSISTANT_SNIPPET + f"\n<!-- {V1_PRODUCT_ASSISTANT_MARKER} -->\n</body>",
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


__all__ = [
    "FEEDBACK_PATH",
    "FEEDBACK_PROOF_PREFIX",
    "QUERY_PATH",
    "V1_PRODUCT_ASSISTANT_MARKER",
    "install_v1_product_assistant_patch",
    "install_v1_product_assistant_routes",
    "patch_v1_product_assistant",
]
