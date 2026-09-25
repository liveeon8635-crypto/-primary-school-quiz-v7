"""Ephemeral role training sandbox for Changying V1.

The sandbox deliberately does not use the production database session. It
exercises real HTTP routes and workflow state transitions while keeping all
training objects in a bounded in-process store. Training sessions are isolated
by authenticated owner and expire automatically.
"""

from __future__ import annotations

import secrets
import threading
import time
from copy import deepcopy
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field


TRAINING_PREFIX = "/v1/training-sandbox"
TRAINING_TTL_SECONDS = 8 * 60 * 60
TRAINING_MAX_SESSIONS = 250

ROLE_MENU_PAGE_IDS: dict[str, list[str]] = {
    "teacher": ["teacher", "classes", "classPoints", "ai", "teaching", "resources", "catalog", "papers", "analytics", "audit", "leaderboard", "account"],
    "student": ["student", "syncLearning", "rewards", "assignments", "wrongbook", "practice", "progress", "leaderboard", "account"],
    "parent": ["parent", "childLearning", "childRewards", "childProgress", "childAssignments", "account"],
    "admin": ["admin", "subscription", "users", "pointsAdmin", "ai", "teaching", "resources", "imports", "catalog", "adminAudit", "system"],
}

ROLE_FLOW: dict[str, list[dict[str, str]]] = {
    "teacher": [
        {"id": "teacher_dashboard", "page": "/v1/tool?page=teacher", "title": "教师工作台与产品主线"},
        {"id": "create_class", "page": "/v1/tool?page=classes", "title": "建立班级"},
        {"id": "add_student", "page": "/v1/tool?page=classes", "title": "添加学生账号"},
        {"id": "student_profile", "page": "/v1/student", "title": "学生连续档案"},
        {"id": "paper", "page": "/v1/tool?page=papers", "title": "组卷 / AI 出题"},
        {"id": "review", "page": "/v1/tool?page=papers", "title": "审核题目与积分"},
        {"id": "assign", "page": "/v1/tool?page=papers", "title": "布置作业"},
        {"id": "student_submission", "page": "/v1/tool?page=papers", "title": "学生作答与完成情况"},
        {"id": "evidence", "page": "/v1/tool?page=analytics", "title": "结果与学习证据回流"},
        {"id": "targeted", "page": "/v1/tool?page=ai", "title": "AI 助手与针对性练习"},
        {"id": "class_review", "page": "/v1/tool?page=analytics", "title": "学情分析与课堂复盘"},
        {"id": "interactive", "page": "/v1/tool?page=teaching", "title": "定制教学与互动课堂"},
        {"id": "points", "page": "/v1/tool?page=classPoints", "title": "课堂积分与评价"},
        {"id": "teacher_resources", "page": "/v1/tool?page=resources", "title": "教材教案资料库"},
        {"id": "teacher_catalog", "page": "/v1/tool?page=catalog", "title": "教材题库"},
        {"id": "teacher_audit", "page": "/v1/tool?page=audit", "title": "教师操作记录"},
        {"id": "teacher_leaderboard", "page": "/v1/tool?page=leaderboard", "title": "班级排行榜"},
        {"id": "account", "page": "/v1/tool?page=account", "title": "我的账号与设备"},
        {"id": "history", "page": "/v1/history", "title": "往期教学"},
        {"id": "transition", "page": "/v1/transition", "title": "升年级与衔接"},
        {"id": "hub", "page": "/v1/tool", "title": "全部功能与关系"},
    ],
    "student": [
        {"id": "student_home", "page": "/v1/tool?page=student", "title": "学习首页"},
        {"id": "classroom", "page": "/v1/tool?page=syncLearning", "title": "同步课堂"},
        {"id": "assignments", "page": "/v1/tool?page=assignments", "title": "我的作业"},
        {"id": "answer", "page": "/v1/tool?page=assignments", "title": "逐题作答"},
        {"id": "result", "page": "/v1/student", "title": "提交结果"},
        {"id": "practice", "page": "/v1/tool?page=practice", "title": "自主 / 针对性练习"},
        {"id": "progress", "page": "/v1/tool?page=progress", "title": "我的学情"},
        {"id": "rewards", "page": "/v1/tool?page=rewards", "title": "积分奖励"},
        {"id": "wrongbook", "page": "/v1/tool?page=wrongbook", "title": "我的错题"},
        {"id": "student_leaderboard", "page": "/v1/tool?page=leaderboard", "title": "班级排行"},
        {"id": "account", "page": "/v1/tool?page=account", "title": "我的账号与更多"},
    ],
    "parent": [
        {"id": "parent_home", "page": "/v1/tool?page=parent", "title": "家长首页"},
        {"id": "learning", "page": "/v1/tool?page=childLearning", "title": "孩子课程"},
        {"id": "assignments", "page": "/v1/tool?page=childAssignments", "title": "孩子作业"},
        {"id": "progress", "page": "/v1/tool?page=childProgress", "title": "孩子学情"},
        {"id": "rewards", "page": "/v1/tool?page=childRewards", "title": "课堂表现与积分"},
        {"id": "history", "page": "/v1/history", "title": "连续档案与历史"},
        {"id": "account", "page": "/v1/tool?page=account", "title": "我的账号与关联孩子"},
    ],
    "admin": [
        {"id": "overview", "page": "/v1/tool?page=admin", "title": "平台总览"},
        {"id": "admin_subscription", "page": "/v1/tool?page=subscription", "title": "套餐授权"},
        {"id": "users", "page": "/v1/tool?page=users", "title": "账号管理"},
        {"id": "classes", "page": "/v1/tool?page=users", "title": "班级与教学归属"},
        {"id": "points", "page": "/v1/tool?page=pointsAdmin", "title": "积分奖励规则"},
        {"id": "admin_ai", "page": "/v1/tool?page=ai", "title": "AI 设置"},
        {"id": "admin_teaching", "page": "/v1/tool?page=teaching", "title": "定制教学"},
        {"id": "admin_resources", "page": "/v1/tool?page=resources", "title": "教材教案"},
        {"id": "admin_imports", "page": "/v1/tool?page=imports", "title": "批量导入"},
        {"id": "admin_catalog", "page": "/v1/tool?page=catalog", "title": "教材题库"},
        {"id": "audit", "page": "/v1/tool?page=adminAudit", "title": "全校审计"},
        {"id": "system", "page": "/v1/tool?page=system", "title": "系统设置"},
        {"id": "history", "page": "/v1/history", "title": "历史连续性"},
    ],
}

STEP_RELATIONSHIPS: dict[str, dict[str, str]] = {
    "teacher_dashboard": {"who": "教师", "creates": "无新增业务写入", "visible_to": "教师", "other_role_sees": "学生、家长只看到与自己有关的结果，不看到教师工作台", "communication_tip": "先从工作台确认今天要处理的班级、作业和课堂，再进入具体功能", "next": "班级学生"},
    "teacher_resources": {"who": "教师", "creates": "教材/教案资料引用关系", "visible_to": "教师；标记学生可见的资料按权限给学生", "other_role_sees": "学生只看到被允许的资料，不看到教师私有备课文件", "communication_tip": "上传资料前确认版权和学生可见范围", "next": "教材题库或 AI 助手"},
    "teacher_catalog": {"who": "教师", "creates": "题目筛选/选题上下文", "visible_to": "教师", "other_role_sees": "学生只看到最终被布置的题目", "communication_tip": "题库浏览不等于布置，发布前仍需教师审核", "next": "组卷作业"},
    "teacher_audit": {"who": "教师查看", "creates": "无新增业务事实", "visible_to": "教师本人授权范围", "other_role_sees": "其他角色不直接看到教师操作记录", "communication_tip": "出现争议时用操作记录确认时间、对象和动作", "next": "核对教学事实"},
    "teacher_leaderboard": {"who": "系统汇总/教师查看", "creates": "班级展示排序", "visible_to": "按班级权限", "other_role_sees": "学生只看到允许公开的班级排行信息", "communication_tip": "排行榜用于激励，不应替代学习诊断或给学生贴标签", "next": "积分与学习反馈"},
    "student_home": {"who": "学生", "creates": "无新增业务写入", "visible_to": "学生本人", "other_role_sees": "教师通过自己的工作台看任务状态，不看到学生首页本身", "communication_tip": "首页是任务入口，不等于已经完成作业或课堂", "next": "同步课堂/我的作业"},
    "student_leaderboard": {"who": "学生查看", "creates": "无新增业务写入", "visible_to": "同班授权学生", "other_role_sees": "教师维护积分和班级规则", "communication_tip": "排行是激励信息，不代表学业能力排名", "next": "回到学习主线"},
    "parent_home": {"who": "家长", "creates": "无新增业务写入", "visible_to": "已关联家长", "other_role_sees": "教师和学生使用各自入口；家长只看到授权摘要", "communication_tip": "先确认当前查看的是哪一个孩子，再解释作业、学情和积分", "next": "孩子课程/孩子作业"},
    "admin_subscription": {"who": "管理员", "creates": "套餐/功能授权状态", "visible_to": "管理员", "other_role_sees": "普通用户只感知功能是否可用，不看到后台套餐配置", "communication_tip": "套餐授权影响功能可用性，不应改写教学历史事实", "next": "账号与功能配置"},
    "admin_ai": {"who": "管理员", "creates": "AI 服务配置与授权边界", "visible_to": "管理员", "other_role_sees": "教师只看到可用 AI 功能和必要提示，不看到密钥", "communication_tip": "AI 配置与教师审核是两层边界；不能因为启用 AI 就自动发布内容", "next": "教师 AI 助手"},
    "admin_teaching": {"who": "管理员/授权教师", "creates": "教学计划和课时配置", "visible_to": "按角色授权", "other_role_sees": "学生只看到已发布的课堂/学习内容", "communication_tip": "配置课时与正式发布是不同动作", "next": "教材教案"},
    "admin_resources": {"who": "管理员/教师", "creates": "学校资料库元数据", "visible_to": "按资源权限", "other_role_sees": "学生只看到被标记为学生可见的资料", "communication_tip": "区分官方教材导航、学校自有资料和学生可见资料", "next": "教材题库/定制教学"},
    "admin_imports": {"who": "管理员", "creates": "批量账号/数据导入结果", "visible_to": "管理员", "other_role_sees": "导入成功后对应用户才看到自己的账号或归属", "communication_tip": "导入前检查字段、重复账号和班级归属，避免批量制造沟通错误", "next": "账号管理"},
    "admin_catalog": {"who": "管理员/教师", "creates": "教材题库配置", "visible_to": "按角色授权", "other_role_sees": "学生只看到最终教学内容", "communication_tip": "题库配置是上游资源，不是学生任务", "next": "组卷/AI 出题"},

    "create_class": {"who": "教师", "creates": "当前教学容器", "visible_to": "教师/管理员", "other_role_sees": "学生和家长此时还看不到任何作业", "communication_tip": "先确认班级名称、年级和教学周期，避免后续双方口径不一致", "next": "添加学生账号"},
    "add_student": {"who": "教师", "creates": "学生账号 + 连续档案起点", "visible_to": "教师/学生/授权家长", "other_role_sees": "学生得到自己的入口；家长只有关联后才看到该学生", "communication_tip": "告知学生使用哪个账号、家长能看到什么，避免把教师入口当成学生入口", "next": "组卷和布置"},
    "paper": {"who": "教师", "creates": "试卷草稿", "visible_to": "教师", "other_role_sees": "未发布前学生和家长都看不到", "communication_tip": "草稿不是作业，教师审核通过后才进入布置环节", "next": "审核后布置"},
    "assign": {"who": "教师", "creates": "学生待办", "visible_to": "教师/学生/家长状态页", "other_role_sees": "学生看到待完成作业；家长看到状态和截止信息，不代替学生作答", "communication_tip": "让教师明确告诉学生作业名称、截止时间和入口", "next": "学生作答"},
    "student_submission": {"who": "学生或沙盒模拟器", "creates": "提交结果", "visible_to": "学生/教师/家长摘要", "other_role_sees": "教师看到提交状态与结果；家长看到授权范围内的完成状态/摘要", "communication_tip": "提交与保存草稿要区分，避免教师误以为学生已交", "next": "教师查看证据"},
    "evidence": {"who": "系统汇总", "creates": "分数/逐题/知识点/错题/积分", "visible_to": "按角色授权可见", "other_role_sees": "学生看自己的结果；教师看教学证据；家长看适合家长理解的摘要", "communication_tip": "页面要解释同一结果在不同角色下为什么显示不同", "next": "针对性练习"},
    "targeted": {"who": "AI 草稿 + 教师审核", "creates": "针对性练习", "visible_to": "教师审核后给指定学生", "other_role_sees": "学生只看到教师确认发布后的练习", "communication_tip": "明确说明练习为什么被生成、依据哪次测试/哪些错题", "next": "继续练习并回流"},
    "class_review": {"who": "教师", "creates": "班级复盘讲义草稿", "visible_to": "教师确认后再发布", "other_role_sees": "草稿阶段学生不可见；发布后按课堂流程使用", "communication_tip": "区分“系统建议复盘”和“教师确认发布”", "next": "互动课堂"},
    "interactive": {"who": "教师主导/学生参与", "creates": "课堂事件与随堂反馈", "visible_to": "对应课堂参与者", "other_role_sees": "学生收到邀请/随堂检测；教师看汇总；家长只看适合家长端的结果摘要", "communication_tip": "邀请学生讲解不是系统评价，学生可以拒绝且不形成负面证据", "next": "积分/复盘/下一轮教学"},
    "points": {"who": "规则或教师", "creates": "可追溯积分动态", "visible_to": "教师/学生/家长摘要", "other_role_sees": "不同角色看到同一积分事实的不同解释层级", "communication_tip": "必须显示积分来源，避免用户把总分误解为学习成绩", "next": "长期激励与评价"},
    "history": {"who": "系统归档", "creates": "只读往期教学", "visible_to": "授权角色", "other_role_sees": "当前工作台减少旧内容，但学生连续档案仍保留历史", "communication_tip": "结束班级不等于删除学生或删除成绩", "next": "阶段衔接"},
    "transition": {"who": "教师/管理员", "creates": "同一学生的阶段变化计划", "visible_to": "授权角色", "other_role_sees": "学生/家长看到的是同一学生下一阶段的连续变化，而不是一个新账号", "communication_tip": "强调学生ID连续性，避免升年级重复建档", "next": "下一阶段继续同一档案"},
    "classroom": {"who": "学生参与", "creates": "课堂参与/随堂反馈", "visible_to": "学生本人/教师汇总", "other_role_sees": "教师看到参与结果；家长只看适合家长端的摘要", "communication_tip": "讲解邀请可拒绝，拒绝不形成负面证据", "next": "作业与随堂反馈"},
    "assignments": {"who": "教师布置、学生完成", "creates": "待办与完成状态", "visible_to": "学生/教师/家长状态页", "other_role_sees": "学生负责作答；家长看状态；教师看完成情况", "communication_tip": "保存过程不等于正式提交", "next": "逐题作答或查看状态"},
    "answer": {"who": "学生", "creates": "答题内容", "visible_to": "提交前仅学生本人", "other_role_sees": "教师只有提交后才获得结果", "communication_tip": "提交前不会显示正确答案，避免误把练习预览当正式提交", "next": "提交结果"},
    "result": {"who": "系统根据提交形成", "creates": "得分/知识点/错题/积分", "visible_to": "按角色授权显示", "other_role_sees": "教师看教学证据；家长看摘要", "communication_tip": "一次分数不等于长期掌握结论", "next": "针对性练习/学情"},
    "practice": {"who": "学生完成、教师可审核来源", "creates": "下一轮练习结果", "visible_to": "学生/教师", "other_role_sees": "教师可看到结果继续调整教学", "communication_tip": "告诉学生为什么收到这组题", "next": "继续回流学情"},
    "progress": {"who": "系统汇总", "creates": "长期趋势视图", "visible_to": "学生/教师/家长摘要", "other_role_sees": "各角色看到不同解释层级", "communication_tip": "重点解释趋势和证据来源，不只说一个总分", "next": "下一步学习"},
    "rewards": {"who": "规则/教师评价产生", "creates": "积分动态", "visible_to": "学生/教师/家长摘要", "other_role_sees": "积分来源一致，展示粒度不同", "communication_tip": "积分不是学业成绩", "next": "持续激励"},
    "wrongbook": {"who": "提交/教师确认形成", "creates": "错题记录", "visible_to": "学生/教师", "other_role_sees": "教师可用于针对练习", "communication_tip": "错题用于下一轮学习，不用于贴负面标签", "next": "针对性练习"},
    "learning": {"who": "家长查看", "creates": "无业务写入", "visible_to": "关联家长", "other_role_sees": "教师维护课程事实，学生参与课程", "communication_tip": "家长先确认孩子、班级和教师是否正确", "next": "孩子作业"},
    "overview": {"who": "管理员", "creates": "管理视图", "visible_to": "管理员", "other_role_sees": "教师/学生/家长不会看到后台管理总览", "communication_tip": "总览用于发现问题，不直接替教师完成教学", "next": "账号和班级关系"},
    "users": {"who": "管理员", "creates": "教师/家长账号", "visible_to": "管理员及对应账号本人", "other_role_sees": "新账号登录后只看到自身角色功能", "communication_tip": "创建账号时要明确角色和后续入口", "next": "班级与教学归属"},
    "classes": {"who": "管理员/教师", "creates": "教学归属关系", "visible_to": "按角色可见", "other_role_sees": "教师看到自己的班级；学生看到自己的归属；家长看到关联孩子信息", "communication_tip": "调班/换老师改变关系，不复制学生档案", "next": "教学开始"},
    "audit": {"who": "管理员查看", "creates": "无新增业务事实", "visible_to": "管理员", "other_role_sees": "普通用户只看到自身功能结果", "communication_tip": "审计用于追溯谁在什么时候做了什么", "next": "定位问题"},
    "system": {"who": "管理员", "creates": "系统级设置", "visible_to": "管理员", "other_role_sees": "设置会影响可用功能，但不应改写历史学习事实", "communication_tip": "系统设置和教学数据是两个边界", "next": "持续治理"},
    "account": {"who": "当前用户", "creates": "账号偏好/安全操作", "visible_to": "账号本人", "other_role_sees": "其他角色不应直接看到账号安全信息", "communication_tip": "身份切换和账号退出要区分", "next": "返回角色主线"},
}

SCENARIO_PRESETS: dict[str, dict[str, Any]] = {
    "empty": {"title": "从零开始", "description": "从建立班级开始完整练习。"},
    "assigned": {"title": "从已布置作业开始", "description": "自动准备班级、学生、试卷和已布置作业，直接练学生端/关联角色体验。"},
    "submitted": {"title": "从已提交结果开始", "description": "自动准备一次学生提交，直接练证据回流、针对性练习和学情沟通。"},
    "classroom": {"title": "从课堂复盘开始", "description": "自动准备班级结果与复盘草稿，直接练互动课堂、随堂检测和积分评价。"},
}


@dataclass
class SandboxSession:
    session_id: str
    owner_user_id: int
    primary_role: str
    current_role: str
    linked_mode: str = "choose"
    created_at: float = field(default_factory=time.time)
    touched_at: float = field(default_factory=time.time)
    next_id: int = 1
    progress: dict[str, str] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=lambda: {
        "classes": [],
        "students": [],
        "papers": [],
        "assignments": [],
        "submissions": [],
        "targeted_practices": [],
        "class_reviews": [],
        "classroom_events": [],
        "points": [],
        "history": [],
        "transitions": [],
        "accounts": [],
        "point_rules": [],
        "audit": [],
        "system_settings": {},
        "wrong_questions": [],
        "guardian_links": [],
    })
    events: list[dict[str, Any]] = field(default_factory=list)

    def new_id(self) -> int:
        value = self.next_id
        self.next_id += 1
        return value

    def touch(self) -> None:
        self.touched_at = time.time()



def _sample_questions(
    session: SandboxSession,
    knowledge: str = "小数乘法",
    count: int = 4,
    subject: str = "数学",
) -> list[dict[str, Any]]:
    subject = str(subject or "数学").strip()
    if subject == "语文":
        templates = [
            {"type": "单选", "prompt": "“僻静”的意思更接近哪一项？", "options": ["热闹嘈杂", "安静偏僻", "宽阔明亮", "整齐干净"], "correctIndex": 1},
            {"type": "判断", "prompt": "判断：“拟人”是把事物当作人来写的一种表达方式。", "options": ["正确", "错误"], "correctIndex": 0},
            {"type": "填空", "prompt": "填空：“白日依山尽”的下一句是____。", "correctAnswer": "黄河入海流"},
            {"type": "填空", "prompt": "“一丝不苟”中的“苟”在这个词里更接近____的意思。", "correctAnswer": "马虎"},
            {"type": "简短回答", "prompt": "写出“安静”的一个近义词。", "correctAnswer": "宁静", "acceptedAnswers": ["宁静", "寂静", "清静"]},
            {"type": "单选", "prompt": "下面哪一项属于比喻句？", "options": ["月亮像一只小船。", "我今天去学校。", "请把门关上。", "天气真好。"], "correctIndex": 0},
        ]
    elif subject == "英语":
        templates = [
            {"type": "单选", "prompt": "Choose the correct word: She ___ to school every day.", "options": ["go", "goes", "going", "gone"], "correctIndex": 1},
            {"type": "判断", "prompt": "判断：“I am happy.” 的意思是“我很开心”。", "options": ["正确", "错误"], "correctIndex": 0},
            {"type": "填空", "prompt": "Complete: I ___ a book every evening.", "correctAnswer": "read"},
            {"type": "单选", "prompt": "Choose the best word for “健康的”.", "options": ["healthy", "hungry", "heavy", "helpful"], "correctIndex": 0},
            {"type": "填空", "prompt": "Complete: We ___ friends.", "correctAnswer": "are"},
            {"type": "简短回答", "prompt": "Write the English word for “自然”.", "correctAnswer": "nature"},
        ]
    else:
        templates = [
            {"type": "单选", "prompt": "0.8 × 0.5 的结果是？", "options": ["0.4", "4", "0.04", "40"], "correctIndex": 0},
            {"type": "判断", "prompt": "判断：2.4 × 0.5 = 1.2。", "options": ["正确", "错误"], "correctIndex": 0},
            {"type": "填空", "prompt": "填空：1.25 × 4 = ____。", "correctAnswer": "5"},
            {"type": "计算", "prompt": "计算：3.6 × 2.5 = ____。", "correctAnswer": "9"},
            {"type": "简短应用题", "prompt": "每本练习册 2.5 元，买 4 本一共 ____。", "correctAnswer": "10元", "acceptedAnswers": ["10元", "10 元"], "placeholder": "例如：10元（含单位）"},
            {"type": "单选", "prompt": "0.06 × 10 的结果是？", "options": ["0.006", "0.06", "0.6", "6"], "correctIndex": 2},
            {"type": "填空", "prompt": "填空：7.2 × 0.1 = ____。", "correctAnswer": "0.72"},
            {"type": "简短应用题", "prompt": "一段路每千米用时 0.75 小时，8 千米共用时 ____。", "correctAnswer": "6小时", "acceptedAnswers": ["6小时", "6 小时"], "placeholder": "例如：6小时（含单位）"},
        ]

    questions: list[dict[str, Any]] = []
    for i in range(max(1, count)):
        template = deepcopy(templates[i % len(templates)])
        template["id"] = session.new_id()
        template["index"] = i + 1
        template["knowledge"] = knowledge
        template["answerKind"] = "choice" if "options" in template else "text"
        template.setdefault("placeholder", "输入答案")
        questions.append(template)
    return questions


def _answer_correct(question: dict[str, Any], value: Any) -> bool:
    if value is None:
        return False
    if question.get("answerKind") == "choice":
        try:
            return int(value) == int(question.get("correctIndex"))
        except (TypeError, ValueError):
            return False

    actual = "".join(str(value).strip().lower().split())
    accepted = [question.get("correctAnswer"), *(question.get("acceptedAnswers") or [])]
    return any(
        actual == "".join(str(candidate).strip().lower().split())
        for candidate in accepted
        if candidate is not None
    )

def _seed_role_context(session: SandboxSession) -> None:
    """Prepare only the upstream facts a role needs in order to practice."""
    if session.primary_role == "teacher":
        return

    if session.primary_role in {"student", "parent"}:
        cls = {"id": session.new_id(), "name": "五年级实操班", "grade": 5, "teacher": "周老师（虚拟）"}
        student = {
            "id": session.new_id(),
            "name": "小禾",
            "username": "xiaohe01",
            "classID": cls["id"],
            "className": cls["name"],
            "grade": 5,
        }
        questions = _sample_questions(session, count=6, subject="数学")
        paper = {
            "id": session.new_id(),
            "title": "小数乘法练习",
            "grade": 5,
            "subject": "数学",
            "textbook": "人教版",
            "knowledge": "小数乘法",
            "questions": questions,
            "reviewed": True,
        }
        assignment = {
            "id": session.new_id(),
            "title": "小数乘法练习",
            "classID": cls["id"],
            "paperID": paper["id"],
            "studentIDs": [student["id"]],
            "due": "本周五",
            "status": "open",
        }
        session.data["classes"].append(cls)
        session.data["students"].append(student)
        session.data["papers"].append(paper)
        session.data["assignments"].append(assignment)
        session.data["guardian_links"].append({"parent": "小禾家长", "studentID": student["id"]})

        if session.primary_role == "parent":
            total = len(questions)
            correct = max(1, round(total * 0.75))
            score = round(correct * 100 / total)
            session.data["submissions"].append({
                "id": session.new_id(),
                "assignmentID": assignment["id"],
                "studentID": student["id"],
                "studentName": student["name"],
                "score": score,
                "correct": correct,
                "total": total,
                "knowledge": paper["knowledge"],
                "accuracy": score,
                "wrongCount": total - correct,
                "source": "seeded_parent_view",
            })
            session.data["points"].append({"id": session.new_id(), "studentID": student["id"], "points": correct, "source": "练习完成"})
            session.data["history"].append({"id": session.new_id(), "classID": cls["id"], "className": "四年级实操班", "status": "read_only"})
        return

    if session.primary_role == "admin":
        teacher = {"id": session.new_id(), "name": "周老师", "username": "teacher_demo", "role": "teacher", "status": "正常"}
        student = {"id": session.new_id(), "name": "小禾", "username": "student_demo", "role": "student", "status": "在读"}
        parent = {"id": session.new_id(), "name": "小禾家长", "username": "parent_demo", "role": "parent", "status": "正常"}
        session.data["accounts"].extend([teacher, student, parent])
        session.data["classes"].append({"id": session.new_id(), "name": "五年级实操班", "grade": 5, "teacher": teacher["name"], "teacherID": teacher["id"]})
        session.data["point_rules"].append({"id": session.new_id(), "name": "练习完成", "points": 2, "active": True})
        session.data["audit"].append({"id": session.new_id(), "action": "账号示例", "detail": "演示环境初始化", "actor": "系统"})
        session.data["system_settings"] = {"loginSecurity": "开启", "teachingCycle": "当前学期", "featureFlags": "默认"}

class TrainingSandboxStore:
    def __init__(self, ttl_seconds: int = TRAINING_TTL_SECONDS, max_sessions: int = TRAINING_MAX_SESSIONS):
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self._items: dict[str, SandboxSession] = {}
        self._lock = threading.RLock()

    def _prune(self) -> None:
        now = time.time()
        expired = [sid for sid, item in self._items.items() if now - item.touched_at > self.ttl_seconds]
        for sid in expired:
            self._items.pop(sid, None)
        if len(self._items) <= self.max_sessions:
            return
        oldest = sorted(self._items.values(), key=lambda item: item.touched_at)
        for item in oldest[: len(self._items) - self.max_sessions]:
            self._items.pop(item.session_id, None)

    def create(self, owner_user_id: int, role: str, linked_mode: str = "choose") -> SandboxSession:
        with self._lock:
            self._prune()
            sid = secrets.token_urlsafe(18)
            item = SandboxSession(
                session_id=sid,
                owner_user_id=owner_user_id,
                primary_role=role,
                current_role=role,
                linked_mode=linked_mode,
            )
            _seed_role_context(item)
            self._items[sid] = item
            return item

    def get(self, session_id: str, owner_user_id: int) -> SandboxSession:
        with self._lock:
            self._prune()
            item = self._items.get(session_id)
            if not item or item.owner_user_id != owner_user_id:
                raise KeyError(session_id)
            item.touch()
            return item

    def reset(self, session_id: str, owner_user_id: int) -> SandboxSession:
        with self._lock:
            old = self.get(session_id, owner_user_id)
            fresh = SandboxSession(
                session_id=old.session_id,
                owner_user_id=old.owner_user_id,
                primary_role=old.primary_role,
                current_role=old.primary_role,
                linked_mode=old.linked_mode,
            )
            _seed_role_context(fresh)
            self._items[session_id] = fresh
            return fresh


STORE = TrainingSandboxStore()


class StartTrainingBody(BaseModel):
    linked_mode: str = Field(default="choose", pattern="^(choose|switch|simulate)$")


class TrainingActionBody(BaseModel):
    action: str = Field(min_length=1, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)


def _role(user: Any) -> str:
    role = str(getattr(user, "role", "") or "").strip().lower()
    if role not in ROLE_FLOW:
        raise HTTPException(403, "当前身份暂不支持实操沙盒")
    return role


def _payload(session: SandboxSession) -> dict[str, Any]:
    return {
        "ok": True,
        "training": True,
        "persistent": False,
        "sessionID": session.session_id,
        "primaryRole": session.primary_role,
        "currentRole": session.current_role,
        "linkedMode": session.linked_mode,
        "flow": ROLE_FLOW.get(session.primary_role, []),
        "relationships": STEP_RELATIONSHIPS,
        "scenarioPresets": SCENARIO_PRESETS,
        "progress": deepcopy(session.progress),
        "data": deepcopy(session.data),
        "events": deepcopy(session.events[-80:]),
        "notice": "这是临时实操沙盒；不会写入真实班级、学生、作业、积分或学习证据。",
    }


def _need(items: list[dict[str, Any]], label: str) -> dict[str, Any]:
    if not items:
        raise HTTPException(409, f"请先完成：{label}")
    return items[-1]


def _event(session: SandboxSession, action: str, detail: str) -> None:
    session.events.append({
        "id": session.new_id(),
        "action": action,
        "detail": detail,
        "role": session.current_role,
        "at": int(time.time()),
    })


def apply_training_action(session: SandboxSession, action: str, payload: dict[str, Any]) -> None:
    p = payload or {}
    session.touch()

    if action == "load_scenario":
        preset = str(p.get("preset", "empty")).strip()
        if preset not in SCENARIO_PRESETS:
            raise HTTPException(400, "未知练习场景")
        if preset == "empty":
            session.current_role = session.primary_role
            session.data = SandboxSession(
                session_id=session.session_id,
                owner_user_id=session.owner_user_id,
                primary_role=session.primary_role,
                current_role=session.primary_role,
                linked_mode=session.linked_mode,
            ).data
            session.progress = {}
            session.events = []
            session.next_id = 1
            _seed_role_context(session)
            _event(session, action, "preset=empty")
            return
        if session.primary_role != "teacher":
            raise HTTPException(400, "当前预置场景仅支持教师主线")
        # Presets are built through the same sandbox actions so page relationships
        # and downstream behavior stay identical to a user-driven training run.
        if not session.data["classes"]:
            apply_training_action(session, "create_class", {"name": "五年级实操班", "grade": 5})
        if not session.data["students"]:
            apply_training_action(session, "add_student", {"name": "小禾", "username": "xiaohe01"})
        if not session.data["papers"]:
            apply_training_action(session, "create_paper", {"subject": "数学", "textbook": "人教版", "knowledge": "小数乘法", "questionCount": 8})
            apply_training_action(session, "review_paper", {})
        if not session.data["assignments"]:
            apply_training_action(session, "assign", {"title": "小数乘法练习", "due": "本周五"})
        if preset in {"submitted", "classroom"} and not session.data["submissions"]:
            apply_training_action(session, "simulate_student_submission", {"correct": 6})
        if preset == "classroom" and not session.data["class_reviews"]:
            apply_training_action(session, "create_class_review", {})
        _event(session, action, f"preset={preset}")
        return

    if action == "rewind_step":
        step = str(p.get("step", "")).strip()
        flow = ROLE_FLOW.get(session.primary_role, [])
        ids = [x["id"] for x in flow]
        if step not in ids:
            raise HTTPException(400, "未知教学步骤")
        start = ids.index(step)
        for step_id in ids[start:]:
            session.progress.pop(step_id, None)
        session.current_role = session.primary_role
        if session.primary_role == "teacher":
            if step == "create_class":
                for key in ("classes", "students", "papers", "assignments", "submissions", "targeted_practices", "class_reviews", "classroom_events", "points", "history", "transitions"):
                    session.data[key].clear()
            elif step == "add_student":
                for key in ("students", "papers", "assignments", "submissions", "targeted_practices", "class_reviews", "classroom_events", "points", "history", "transitions"):
                    session.data[key].clear()
            elif step in {"paper", "review"}:
                if step == "paper":
                    session.data["papers"].clear()
                elif session.data["papers"]:
                    session.data["papers"][-1]["reviewed"] = False
                for key in ("assignments", "submissions", "targeted_practices", "class_reviews", "classroom_events", "points", "history", "transitions"):
                    session.data[key].clear()
            elif step == "assign":
                for key in ("assignments", "submissions", "targeted_practices", "class_reviews", "classroom_events", "points", "history", "transitions"):
                    session.data[key].clear()
            elif step == "student_submission":
                for key in ("submissions", "targeted_practices", "class_reviews", "classroom_events", "points", "history", "transitions"):
                    session.data[key].clear()
            elif step == "targeted":
                session.data["targeted_practices"].clear()
                for key in ("class_reviews", "classroom_events", "history", "transitions"):
                    session.data[key].clear()
            elif step == "class_review":
                session.data["class_reviews"].clear()
                session.data["classroom_events"].clear()
            elif step == "interactive":
                session.data["classroom_events"].clear()
            elif step == "history":
                session.data["history"].clear()
                session.data["transitions"].clear()
            elif step == "transition":
                session.data["transitions"].clear()
        elif session.primary_role == "student":
            if step == "answer":
                for key in ("submissions", "targeted_practices", "points", "wrong_questions"):
                    session.data[key].clear()
            elif step == "practice" and session.data["targeted_practices"]:
                session.data["targeted_practices"][-1]["status"] = "assigned"
        _event(session, action, f"step={step}")
        return

    if action == "set_linked_mode":
        mode = str(p.get("mode", "")).strip()
        if mode not in {"choose", "switch", "simulate"}:
            raise HTTPException(400, "关联角色体验方式无效")
        session.linked_mode = mode
        _event(session, action, f"linked_mode={mode}")
        return

    if action == "visit_step":
        step = str(p.get("step", "")).strip()
        valid = {x["id"] for x in ROLE_FLOW.get(session.primary_role, [])}
        if step not in valid:
            raise HTTPException(400, "未知教学步骤")
        session.progress[step] = str(p.get("status", "done"))
        _event(session, action, step)
        return

    if session.primary_role == "student" and action == "student_submit_self":
        assignment = _need(session.data["assignments"], "教师布置作业")
        student = _need(session.data["students"], "学生身份")
        paper = _need(session.data["papers"], "作业试卷")
        if session.data["submissions"]:
            raise HTTPException(409, "这份沙盒作业已经提交，可重置沙盒后重新练习")
        submitted_answers = p.get("answers") if isinstance(p.get("answers"), dict) else {}
        normalized = {str(key): value for key, value in submitted_answers.items()}
        total = len(paper["questions"])
        correct = sum(
            1
            for question in paper["questions"]
            if _answer_correct(question, normalized.get(str(question["id"])))
        )
        score = round(correct * 100 / max(1, total))
        sub = {
            "id": session.new_id(),
            "assignmentID": assignment["id"],
            "studentID": student["id"],
            "studentName": student["name"],
            "score": score,
            "correct": correct,
            "total": total,
            "knowledge": paper["knowledge"],
            "accuracy": score,
            "wrongCount": total - correct,
            "source": "student_training",
        }
        session.data["submissions"].append(sub)
        session.data["points"].append({"id": session.new_id(), "studentID": student["id"], "points": correct, "source": "练习完成"})
        for question in paper["questions"]:
            answer = normalized.get(str(question["id"]))
            if not _answer_correct(question, answer):
                session.data["wrong_questions"].append({"id": session.new_id(), "questionID": question["id"], "knowledge": question["knowledge"], "prompt": question["prompt"]})
        session.data["targeted_practices"].append({"id": session.new_id(), "studentID": student["id"], "knowledge": paper["knowledge"], "basedOnSubmissionID": sub["id"], "questionCount": 4, "status": "assigned"})
        session.progress["answer"] = "done"
        session.progress["result"] = "done"
        _event(session, action, f"submission={sub['id']}:score={score}")
        return

    if session.primary_role == "student" and action == "complete_student_practice":
        practice = _need(session.data["targeted_practices"], "提交一次作业后生成针对性练习")
        practice["status"] = "completed"
        session.progress["practice"] = "done"
        _event(session, action, f"practice={practice['id']}:completed")
        return

    if session.primary_role == "admin" and action == "admin_create_account":
        role = str(p.get("role", "teacher")).strip()
        if role not in {"teacher", "parent"}:
            raise HTTPException(400, "管理员练习只创建教师或家长账号")
        obj = {"id": session.new_id(), "name": str(p.get("name", "练习账号"))[:100], "username": str(p.get("username", f"demo{session.next_id}"))[:100], "role": role, "status": "正常"}
        session.data["accounts"].append(obj)
        session.data["audit"].append({"id": session.new_id(), "action": "账号创建", "detail": f"{role}:{obj['username']}", "actor": "当前沙盒管理员"})
        session.progress["users"] = "done"
        _event(session, action, f"account={obj['id']}:{role}")
        return

    if session.primary_role == "admin" and action == "admin_create_class":
        teachers = [x for x in session.data["accounts"] if x.get("role") == "teacher"]
        teacher = teachers[-1] if teachers else None
        if not teacher:
            raise HTTPException(409, "请先创建教师账号")
        obj = {"id": session.new_id(), "name": str(p.get("name", "五年级实操班"))[:120], "grade": int(p.get("grade", 5)), "teacher": teacher["name"], "teacherID": teacher["id"]}
        session.data["classes"].append(obj)
        session.data["audit"].append({"id": session.new_id(), "action": "班级创建", "detail": obj["name"], "actor": "当前沙盒管理员"})
        session.progress["classes"] = "done"
        _event(session, action, f"class={obj['id']}")
        return

    if session.primary_role == "admin" and action == "admin_set_point_rule":
        obj = {"id": session.new_id(), "name": str(p.get("name", "课堂参与"))[:80], "points": max(0, min(int(p.get("points", 2)), 100)), "active": True}
        session.data["point_rules"].append(obj)
        session.data["audit"].append({"id": session.new_id(), "action": "积分规则", "detail": f"{obj['name']}:+{obj['points']}", "actor": "当前沙盒管理员"})
        session.progress["points"] = "done"
        _event(session, action, f"point_rule={obj['id']}")
        return

    if session.primary_role == "admin" and action == "admin_set_system":
        key = str(p.get("key", "trainingFeature"))[:60]
        value = str(p.get("value", "开启"))[:120]
        session.data["system_settings"][key] = value
        session.data["audit"].append({"id": session.new_id(), "action": "系统设置", "detail": f"{key}={value}", "actor": "当前沙盒管理员"})
        session.progress["system"] = "done"
        _event(session, action, f"system={key}")
        return

    if session.primary_role != "teacher":
        raise HTTPException(400, "当前身份的这个步骤只读；请使用页面上的完成/跳过继续")

    if action == "create_class":
        name = str(p.get("name", "")).strip() or "五年级一班"
        grade = int(p.get("grade", 5))
        if not 1 <= grade <= 12:
            raise HTTPException(400, "年级无效")
        obj = {"id": session.new_id(), "name": name[:120], "grade": grade, "teacher": "当前沙盒教师"}
        session.data["classes"].append(obj)
        session.progress["create_class"] = "done"
        _event(session, action, f"class={obj['id']}:{obj['name']}")
        return

    if action == "add_student":
        cls = _need(session.data["classes"], "建立班级")
        name = str(p.get("name", "")).strip() or "小禾"
        username = str(p.get("username", "")).strip() or f"sandbox{session.new_id()}"
        obj = {
            "id": session.new_id(),
            "name": name[:100],
            "username": username[:100],
            "classID": cls["id"],
            "className": cls["name"],
            "grade": cls["grade"],
        }
        session.data["students"].append(obj)
        session.progress["add_student"] = "done"
        _event(session, action, f"student={obj['id']}:{obj['name']}")
        return

    if action == "create_paper":
        cls = _need(session.data["classes"], "建立班级")
        count = max(1, min(int(p.get("questionCount", 8)), 30))
        subject = str(p.get("subject", "数学"))[:30]
        knowledge = str(p.get("knowledge", "小数乘法"))[:120]
        textbook = str(p.get("textbook", "人教版"))[:80]
        questions = _sample_questions(session, knowledge=knowledge, count=count, subject=subject)
        obj = {
            "id": session.new_id(),
            "title": str(p.get("title", f"{subject}练习"))[:160],
            "grade": cls["grade"],
            "subject": subject,
            "textbook": textbook,
            "knowledge": knowledge,
            "questions": questions,
            "reviewed": False,
        }
        session.data["papers"].append(obj)
        session.progress["paper"] = "done"
        _event(session, action, f"paper={obj['id']}:questions={count}")
        return

    if action == "review_paper":
        paper = _need(session.data["papers"], "组卷")
        paper["reviewed"] = True
        paper["reviewNote"] = str(p.get("note", "题型、答案方式、难度和积分已检查"))[:300]
        session.progress["review"] = "done"
        _event(session, action, f"paper={paper['id']}:reviewed")
        return

    if action == "assign":
        cls = _need(session.data["classes"], "建立班级")
        paper = _need(session.data["papers"], "组卷")
        if not paper.get("reviewed"):
            raise HTTPException(409, "请先审核试卷")
        students = [x for x in session.data["students"] if x["classID"] == cls["id"]]
        if not students:
            raise HTTPException(409, "请先添加学生")
        obj = {
            "id": session.new_id(),
            "title": str(p.get("title", paper["title"]))[:160],
            "classID": cls["id"],
            "paperID": paper["id"],
            "studentIDs": [x["id"] for x in students],
            "due": str(p.get("due", "本周五"))[:40],
            "status": "open",
        }
        session.data["assignments"].append(obj)
        session.progress["assign"] = "done"
        _event(session, action, f"assignment={obj['id']}:students={len(students)}")
        return

    if action in {"switch_to_student", "simulate_student_submission", "student_submit"}:
        assignment = _need(session.data["assignments"], "布置作业")
        student = _need(session.data["students"], "添加学生")
        paper = _need(session.data["papers"], "组卷")
        if action == "switch_to_student":
            session.current_role = "student"
            session.linked_mode = "switch"
            _event(session, action, f"student={student['id']}")
            return
        if action == "student_submit" and session.current_role != "student":
            raise HTTPException(409, "请先切换到虚拟学生视角，或选择自动模拟")
        total = len(paper["questions"])
        submitted_answers = p.get("answers")
        if action == "student_submit" and isinstance(submitted_answers, dict):
            normalized = {str(key): value for key, value in submitted_answers.items()}
            correct = sum(
                1
                for question in paper["questions"]
                if _answer_correct(question, normalized.get(str(question["id"])))
            )
        else:
            correct = max(0, min(total, int(p.get("correct", max(1, round(total * 0.75))))))
        score = round(correct * 100 / max(1, total))
        existing = [x for x in session.data["submissions"] if x["assignmentID"] == assignment["id"] and x["studentID"] == student["id"]]
        if existing:
            raise HTTPException(409, "这份沙盒作业已经提交，可重置沙盒后重新练习")
        obj = {
            "id": session.new_id(),
            "assignmentID": assignment["id"],
            "studentID": student["id"],
            "studentName": student["name"],
            "score": score,
            "correct": correct,
            "total": total,
            "knowledge": paper["knowledge"],
            "accuracy": score,
            "wrongCount": total - correct,
            "source": "manual_virtual_student" if action == "student_submit" else "simulated_linked_role",
        }
        session.data["submissions"].append(obj)
        session.data["points"].append({
            "id": session.new_id(),
            "studentID": student["id"],
            "points": correct,
            "source": "练习完成",
        })
        session.progress["student_submission"] = "done"
        session.progress["evidence"] = "done"
        _event(session, action, f"submission={obj['id']}:score={score}")
        return

    if action == "return_primary_role":
        session.current_role = session.primary_role
        _event(session, action, "return_primary")
        return

    if action == "create_targeted_practice":
        submission = _need(session.data["submissions"], "学生提交或自动模拟提交")
        obj = {
            "id": session.new_id(),
            "studentID": submission["studentID"],
            "knowledge": submission["knowledge"],
            "basedOnSubmissionID": submission["id"],
            "questionCount": max(3, min(int(p.get("questionCount", 6)), 15)),
            "status": "draft",
        }
        session.data["targeted_practices"].append(obj)
        session.progress["targeted"] = "done"
        _event(session, action, f"targeted={obj['id']}")
        return

    if action == "create_class_review":
        submission = _need(session.data["submissions"], "至少一次学生提交")
        cls = _need(session.data["classes"], "建立班级")
        obj = {
            "id": session.new_id(),
            "classID": cls["id"],
            "knowledge": submission["knowledge"],
            "summary": f"围绕{submission['knowledge']}生成课堂复盘草稿",
            "status": "draft",
        }
        session.data["class_reviews"].append(obj)
        session.progress["class_review"] = "done"
        _event(session, action, f"class_review={obj['id']}")
        return

    if action == "run_interactive_classroom":
        review = _need(session.data["class_reviews"], "生成课堂复盘")
        obj = {
            "id": session.new_id(),
            "reviewID": review["id"],
            "mode": str(p.get("mode", "师生共讲"))[:30],
            "quickCheck": True,
            "studentResponse": str(p.get("studentResponse", "已完成"))[:30],
        }
        session.data["classroom_events"].append(obj)
        session.progress["interactive"] = "done"
        _event(session, action, f"classroom={obj['id']}")
        return

    if action == "archive_history":
        cls = _need(session.data["classes"], "建立班级")
        obj = {"id": session.new_id(), "classID": cls["id"], "className": cls["name"], "status": "read_only"}
        session.data["history"].append(obj)
        session.progress["history"] = "done"
        _event(session, action, f"history={obj['id']}")
        return

    if action == "create_transition":
        student = _need(session.data["students"], "添加学生")
        obj = {
            "id": session.new_id(),
            "studentID": student["id"],
            "from": str(p.get("from", f"{student['grade']}年级")),
            "to": str(p.get("to", f"{student['grade'] + 1}年级")),
            "status": "practice_plan",
        }
        session.data["transitions"].append(obj)
        session.progress["transition"] = "done"
        _event(session, action, f"transition={obj['id']}")
        return

    if action == "review_points":
        _need(session.data["points"], "学生提交")
        session.progress["points"] = "done"
        _event(session, action, "points_reviewed")
        return

    raise HTTPException(400, "未知沙盒操作")


def install_v1_training_sandbox_routes(implementation: ModuleType) -> None:
    app = implementation.app
    if getattr(app.state, "v1_training_sandbox_routes_installed", False):
        return

    router = APIRouter()

    @router.post(TRAINING_PREFIX + "/start", include_in_schema=False)
    def start_training(body: StartTrainingBody, user=Depends(implementation.current_user)):
        role = _role(user)
        item = STORE.create(int(user.id), role, body.linked_mode)
        return _payload(item)

    @router.get(TRAINING_PREFIX + "/{session_id}", include_in_schema=False)
    def read_training(session_id: str, user=Depends(implementation.current_user)):
        try:
            item = STORE.get(session_id, int(user.id))
        except KeyError:
            raise HTTPException(404, "实操沙盒不存在或已过期") from None
        return _payload(item)

    @router.post(TRAINING_PREFIX + "/{session_id}/action", include_in_schema=False)
    def training_action(session_id: str, body: TrainingActionBody, user=Depends(implementation.current_user)):
        try:
            item = STORE.get(session_id, int(user.id))
        except KeyError:
            raise HTTPException(404, "实操沙盒不存在或已过期") from None
        apply_training_action(item, body.action, body.payload)
        return _payload(item)

    @router.post(TRAINING_PREFIX + "/{session_id}/reset", include_in_schema=False)
    def reset_training(session_id: str, user=Depends(implementation.current_user)):
        try:
            item = STORE.reset(session_id, int(user.id))
        except KeyError:
            raise HTTPException(404, "实操沙盒不存在或已过期") from None
        return _payload(item)

    app.include_router(router)
    app.state.v1_training_sandbox_routes_installed = True


__all__ = [
    "ROLE_FLOW",
    "ROLE_MENU_PAGE_IDS",
    "SCENARIO_PRESETS",
    "STEP_RELATIONSHIPS",
    "STORE",
    "TRAINING_PREFIX",
    "TrainingSandboxStore",
    "apply_training_action",
    "install_v1_training_sandbox_routes",
]
