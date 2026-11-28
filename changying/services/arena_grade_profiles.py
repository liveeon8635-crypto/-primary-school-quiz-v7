"""1～6 年级四阶年龄段交互配置（Age-Tier UX Adaptation）与分学科跨年级定位/切换工具.

四阶分学段交互策略：
- G1–G2 低段零打字启蒙型（6~8 岁，g12_playful）：
  - 题干与选项慢速语音伴读（默认突出展示 🔊 读题按钮，0.85x 亲切慢速朗读）；
  - 数学全系标配内嵌大号数字软键盘（0~9、退格、清空，免调系统输入法）；
  - 语文 100% 零打字点选：听音选拼音、看拼音写字词、古诗默写均提供大号汉字/拼音块点选托盘；
  - 语文看图/情境写话（G1 一句话 15~25 字 / G2 四要素 25~40 字）提供「句式积木拼句胶囊」，点击积木即可拼成完整句子；
  - 乐考闯关专项精简为 8 题，单题宽松限时 30s，音频限播 3 遍。
- G3 启蒙辅助型（8~9 岁，g3_guided）：
  - 题干语音伴读（0.88x 慢速清晰朗读）；
  - 数学内嵌大号数字/分数软键盘；英语/语文附带首字母提示及候选字母/汉字托盘；
  - 语文微写话 40~60 字并配开头句式支架；单题限时 25s，听力限播 3 遍。
- G4 进阶过渡型（9~10 岁，g4_bridge）：
  - 可选题干伴读；数学配备紧凑快捷符号条；英语/语文采用拼块 + 首字母轻键盘混合过渡；
  - 语文微写作 60~80 字并配好词锦囊胶囊；单题限时 22s，听力限播 2 遍。
- G5–G6 高阶冲刺型（10~12 岁，g56_mastery）：
  - 全键盘精准输入（严判单复数/时态/古诗字形/假分数与小数）；
  - 语文微写作 80~120 字严判立意与修辞；标准应试限时 20s，听力限播 2 遍。
"""
from __future__ import annotations

from typing import Any

SUPPORTED_GRADES: tuple[int, ...] = (1, 2, 3, 4, 5, 6)
ENGLISH_SUPPORTED_GRADES: tuple[int, ...] = (3, 4, 5, 6)
DEFAULT_ARENA_GRADE: int = 5

SUBJECT_SUPPORTED_GRADES: dict[str, tuple[int, ...]] = {
    "数学": SUPPORTED_GRADES,
    "语文": SUPPORTED_GRADES,
    "英语": ENGLISH_SUPPORTED_GRADES,
    "math": SUPPORTED_GRADES,
    "chinese": SUPPORTED_GRADES,
    "english": ENGLISH_SUPPORTED_GRADES,
}

GRADE_LABELS: dict[int, str] = {
    1: "一年级",
    2: "二年级",
    3: "三年级",
    4: "四年级",
    5: "五年级",
    6: "六年级",
}

GRADE_THEMES: dict[int, dict[str, str]] = {
    1: {
        "mathTitle": "小学数学通用知识地图（一年级·数感与图形乐考星图）",
        "englishTitle": "小学英语通用知识地图（三年级·自然拼读与启蒙交际）",
        "chineseTitle": "小学语文通用知识地图（一年级·拼音识字与童谣写话）",
    },
    2: {
        "mathTitle": "小学数学通用知识地图（二年级·口诀算理与思维星图）",
        "englishTitle": "小学英语通用知识地图（三年级·自然拼读与启蒙交际）",
        "chineseTitle": "小学语文通用知识地图（二年级·查字典词句与看图写话）",
    },
    3: {
        "mathTitle": "小学数学通用知识地图（三年级·启蒙算理星图）",
        "englishTitle": "小学英语通用知识地图（三年级·自然拼读与启蒙交际）",
        "chineseTitle": "小学语文通用知识地图（三年级·字词句段与童话诗文）",
    },
    4: {
        "mathTitle": "小学数学通用知识地图（四年级·进阶思维星图）",
        "englishTitle": "小学英语通用知识地图（四年级·核心语法与校园交际）",
        "chineseTitle": "小学语文通用知识地图（四年级·批注阅读与诗文积累）",
    },
    5: {
        "mathTitle": "小学数学通用知识地图（五年级·算理星图）",
        "englishTitle": "小学英语通用知识地图（五年级·听说读写星图）",
        "chineseTitle": "小学语文通用知识地图（五年级·国学与阅读星图）",
    },
    6: {
        "mathTitle": "小学数学通用知识地图（六年级·小升初综合星图）",
        "englishTitle": "小学英语通用知识地图（六年级·多时态与小升初语篇）",
        "chineseTitle": "小学语文通用知识地图（六年级·文言诗词与小升初读写）",
    },
}


def supported_grades_for_subject(subject: str | None = None) -> tuple[int, ...]:
    """返回指定学科支持的年级列表（数学/语文 1~6 年级，英语 3~6 年级）."""
    key = str(subject or "").strip().lower()
    if key in ("英语", "english"):
        return ENGLISH_SUPPORTED_GRADES
    return SUPPORTED_GRADES


def clamp_arena_grade(
    raw: Any,
    fallback: int = DEFAULT_ARENA_GRADE,
    *,
    subject: str | None = None,
) -> int:
    """将任意年级输入规范化至目标学科支持的年级范围（语/数 1..6，英语 3..6）."""
    allowed = supported_grades_for_subject(subject)
    min_g, max_g = allowed[0], allowed[-1]
    fb = fallback if fallback in allowed else max(min_g, min(max_g, int(fallback or DEFAULT_ARENA_GRADE)))
    try:
        g = int(raw)
    except (TypeError, ValueError):
        return fb
    if g < min_g:
        return min_g
    if g > max_g:
        return max_g
    return g


def detect_user_grade(implementation: Any, db: Any, user: Any) -> int:
    """从学生档案或所属班级自动检测学生本人真实年级（规范化到 1..6，默认 5）."""
    for attr in ("grade", "student_grade", "class_grade"):
        val = getattr(user, attr, None)
        if val:
            return clamp_arena_grade(val, DEFAULT_ARENA_GRADE)
    fn = getattr(implementation, "current_class_for", None)
    if callable(fn) and db is not None and user is not None:
        try:
            cls = fn(db, int(user.id), int(user.school_id))
            if cls is not None and getattr(cls, "grade", None):
                return clamp_arena_grade(cls.grade, DEFAULT_ARENA_GRADE)
        except Exception:
            pass
    return DEFAULT_ARENA_GRADE


def resolve_arena_grade(
    requested_grade: Any = None,
    student_grade: Any = None,
    *,
    subject: str | None = None,
) -> int:
    """优先使用显式请求的 grade，未传时回落至学生本人年级，并按学科支持的年级范围规范化."""
    base = clamp_arena_grade(student_grade, DEFAULT_ARENA_GRADE, subject=subject)
    if requested_grade is None or str(requested_grade).strip() == "":
        return base
    return clamp_arena_grade(requested_grade, base, subject=subject)


def grade_relation(target_grade: int, student_grade: int, *, subject: str | None = None) -> tuple[str, str]:
    """返回目标年级相对于学生本人年级的关系编码与中文标签."""
    tg = clamp_arena_grade(target_grade, subject=subject)
    sg = clamp_arena_grade(student_grade)
    if tg == sg:
        return "current", "本年级"
    if tg < sg:
        return "review", "查漏补缺"
    if sg in (1, 2) and tg == 3 and str(subject or "").strip().lower() in ("英语", "english"):
        return "advance", "超前启蒙"
    return "advance", "超前探索"


def build_available_grades(
    active_grade: int,
    student_grade: int,
    *,
    subject: str | None = None,
) -> list[dict[str, Any]]:
    """构建顶栏年级切换胶囊元数据（语/数 1~6 年级 6 胶囊，英语 3~6 年级 4 胶囊）."""
    allowed = supported_grades_for_subject(subject)
    ag = clamp_arena_grade(active_grade, subject=subject)
    sg = clamp_arena_grade(student_grade)
    out: list[dict[str, Any]] = []
    for g in allowed:
        rel_code, rel_label = grade_relation(g, sg, subject=subject)
        prof = get_age_interaction_profile(g)
        out.append({
            "grade": g,
            "label": GRADE_LABELS[g],
            "active": g == ag,
            "isCurrentGrade": g == sg,
            "relation": rel_code,
            "relationLabel": rel_label,
            "tier": prof["tier"],
            "tierShortLabel": prof["tierShortLabel"],
        })
    return out


def get_age_interaction_profile(grade: int) -> dict[str, Any]:
    """根据年级返回四阶差异化交互配置，驱动前端渲染与后端计时/判分适配."""
    g = clamp_arena_grade(grade)
    if g == 1:
        return {
            "grade": 1,
            "gradeLabel": "一年级",
            "tier": "g12_playful",
            "tierLabel": "一年级·零打字启蒙型（0.85x慢速语音读题 + 大号数字盘/拼音汉字块点选 + 积木拼句写话）",
            "tierShortLabel": "零打字启蒙模式",
            "stemReadAloud": True,
            "stemReadAloudDefault": True,
            "optionReadAloud": True,
            "speechRate": 0.85,
            "mathKeypad": "full",
            "spellAssist": "tile_or_first_letter",
            "chineseAssistTiles": True,
            "writingScaffold": True,
            "writingBlockBuilder": True,
            "writingTargetChars": "15～25字（一句话写话）",
            "writingMinChars": 12,
            "perQuestionSec": 30,
            "perQuestionSecMultiplier": 1.5,
            "maxPlays": 3,
            "maxPlaysBonus": 1,
            "sprintQuestionCount": 8,
            "largeTouchUi": True,
            "helperTone": "playful",
        }
    if g == 2:
        return {
            "grade": 2,
            "gradeLabel": "二年级",
            "tier": "g12_playful",
            "tierLabel": "二年级·零打字乐考型（0.85x慢速语音读题 + 大号数字盘/字块点选 + 四要素积木拼句写话）",
            "tierShortLabel": "零打字乐考模式",
            "stemReadAloud": True,
            "stemReadAloudDefault": True,
            "optionReadAloud": True,
            "speechRate": 0.85,
            "mathKeypad": "full",
            "spellAssist": "tile_or_first_letter",
            "chineseAssistTiles": True,
            "writingScaffold": True,
            "writingBlockBuilder": True,
            "writingTargetChars": "25～40字（四要素写话）",
            "writingMinChars": 20,
            "perQuestionSec": 30,
            "perQuestionSecMultiplier": 1.5,
            "maxPlays": 3,
            "maxPlaysBonus": 1,
            "sprintQuestionCount": 8,
            "largeTouchUi": True,
            "helperTone": "playful",
        }
    if g == 3:
        return {
            "grade": 3,
            "gradeLabel": "三年级",
            "tier": "g3_guided",
            "tierLabel": "三年级·启蒙辅助型（语音读题 + 数字键盘/字块托盘 + 宽松限时）",
            "tierShortLabel": "启蒙辅助模式",
            "stemReadAloud": True,
            "stemReadAloudDefault": True,
            "optionReadAloud": False,
            "speechRate": 0.88,
            "mathKeypad": "full",
            "spellAssist": "tile_or_first_letter",
            "chineseAssistTiles": True,
            "writingScaffold": True,
            "writingBlockBuilder": False,
            "writingTargetChars": "40～60字",
            "writingMinChars": 35,
            "perQuestionSec": 25,
            "perQuestionSecMultiplier": 1.25,
            "maxPlays": 3,
            "maxPlaysBonus": 1,
            "sprintQuestionCount": 10,
            "largeTouchUi": True,
            "helperTone": "guided",
        }
    if g == 4:
        return {
            "grade": 4,
            "gradeLabel": "四年级",
            "tier": "g4_bridge",
            "tierLabel": "四年级·进阶过渡型（可选读题 + 拼块/首字母轻输入 + 标准限时）",
            "tierShortLabel": "进阶过渡模式",
            "stemReadAloud": True,
            "stemReadAloudDefault": False,
            "optionReadAloud": False,
            "speechRate": 0.94,
            "mathKeypad": "compact",
            "spellAssist": "first_letter_hint",
            "chineseAssistTiles": False,
            "writingScaffold": True,
            "writingBlockBuilder": False,
            "writingTargetChars": "60～80字",
            "writingMinChars": 50,
            "perQuestionSec": 22,
            "perQuestionSecMultiplier": 1.1,
            "maxPlays": 2,
            "maxPlaysBonus": 0,
            "sprintQuestionCount": 10,
            "largeTouchUi": False,
            "helperTone": "bridge",
        }
    if g == 5:
        return {
            "grade": 5,
            "gradeLabel": "五年级",
            "tier": "g56_mastery",
            "tierLabel": "五年级·高阶冲刺型（全键盘精准输入 + 综合推理 + 应试限时）",
            "tierShortLabel": "高阶冲刺模式",
            "stemReadAloud": False,
            "stemReadAloudDefault": False,
            "optionReadAloud": False,
            "speechRate": 1.0,
            "mathKeypad": "none",
            "spellAssist": "strict_keyboard",
            "chineseAssistTiles": False,
            "writingScaffold": False,
            "writingBlockBuilder": False,
            "writingTargetChars": "80～100字",
            "writingMinChars": 70,
            "perQuestionSec": 20,
            "perQuestionSecMultiplier": 1.0,
            "maxPlays": 2,
            "maxPlaysBonus": 0,
            "sprintQuestionCount": 10,
            "largeTouchUi": False,
            "helperTone": "mastery",
        }
    return {
        "grade": 6,
        "gradeLabel": "六年级",
        "tier": "g56_mastery",
        "tierLabel": "六年级·小升初毕业冲刺型（全键盘严判 + 跨时态/文言/几何压轴限时）",
        "tierShortLabel": "小升初冲刺模式",
        "stemReadAloud": False,
        "stemReadAloudDefault": False,
        "optionReadAloud": False,
        "speechRate": 1.0,
        "mathKeypad": "none",
        "spellAssist": "strict_keyboard",
        "chineseAssistTiles": False,
        "writingScaffold": False,
        "writingBlockBuilder": False,
        "writingTargetChars": "100～120字",
        "writingMinChars": 85,
        "perQuestionSec": 20,
        "perQuestionSecMultiplier": 1.0,
        "maxPlays": 2,
        "maxPlaysBonus": 0,
        "sprintQuestionCount": 10,
        "largeTouchUi": False,
        "helperTone": "graduation",
    }


def infer_grade_from_node_key(node_key: str, default_grade: int = DEFAULT_ARENA_GRADE) -> int:
    """从节点编码（如 G1-M1-1、G2-C1-1、G3-M1-1、G4-E2-3、G6-C1-2 或五年级 M1-1/E1-1/C1-1）推断所属年级."""
    k = str(node_key or "").strip().upper()
    for g in SUPPORTED_GRADES:
        if k.startswith(f"G{g}-"):
            return g
    return clamp_arena_grade(default_grade)


def infer_grade_from_sprint_slug(slug: str, default_grade: int = DEFAULT_ARENA_GRADE) -> int:
    """从专项 slug（如 g1-math-add-sprint、g2-chinese-foundation-sprint、g3-listening-sprint）推断所属年级."""
    s = str(slug or "").strip().lower()
    for g in SUPPORTED_GRADES:
        if s.startswith(f"g{g}-"):
            return g
    return clamp_arena_grade(default_grade)


__all__ = [
    "DEFAULT_ARENA_GRADE",
    "ENGLISH_SUPPORTED_GRADES",
    "GRADE_LABELS",
    "GRADE_THEMES",
    "SUBJECT_SUPPORTED_GRADES",
    "SUPPORTED_GRADES",
    "build_available_grades",
    "clamp_arena_grade",
    "detect_user_grade",
    "get_age_interaction_profile",
    "grade_relation",
    "infer_grade_from_node_key",
    "infer_grade_from_sprint_slug",
    "resolve_arena_grade",
    "supported_grades_for_subject",
]
