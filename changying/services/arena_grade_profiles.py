"""3～6 年级年龄段交互配置（Age-Tier UX Adaptation）与跨年级定位/切换工具.

分学段交互策略：
- G3 启蒙辅助型（8~9 岁，g3_guided）：
  - 题干语音伴读（默认突出展示 🔊 读题按钮，0.9x 慢速清晰朗读）；
  - 少打字/大触控：数学填空与计算题自动展开内嵌大号数字/分数软键盘；
  - 英语/语文拼写与默写题附带首字母提示及候选字母/汉字托盘点选辅助；
  - 语文微写话 40~60 字并配开头句式支架；
  - 单题限时放宽 +25%（20s -> 25s），听力限播 3 遍。
- G4 进阶过渡型（9~10 岁，g4_bridge）：
  - 可选题干伴读；数学配备紧凑快捷符号条；
  - 英语/语文采用拼块 + 首字母/关键词轻键盘混合过渡；
  - 语文微写作 60~80 字并配好词锦囊胶囊；
  - 单题限时 22s，听力限播 2 遍。
- G5–G6 高阶冲刺型（10~12 岁，g56_mastery）：
  - 全键盘精准输入（严判单复数/时态/古诗字形/假分数与小数）；
  - 语文微写作 80~120 字严判立意与修辞；
  - 标准应试限时 20s，听力限播 2 遍。
"""
from __future__ import annotations

from typing import Any

SUPPORTED_GRADES: tuple[int, ...] = (3, 4, 5, 6)
DEFAULT_ARENA_GRADE: int = 5

GRADE_LABELS: dict[int, str] = {
    3: "三年级",
    4: "四年级",
    5: "五年级",
    6: "六年级",
}

GRADE_THEMES: dict[int, dict[str, str]] = {
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


def clamp_arena_grade(raw: Any, fallback: int = DEFAULT_ARENA_GRADE) -> int:
    """将任意年级输入规范化至 3..6 年级."""
    try:
        g = int(raw)
    except (TypeError, ValueError):
        return fallback
    if g in SUPPORTED_GRADES:
        return g
    if g in (1, 2):
        return 3
    if g > 6:
        return 6
    return fallback


def detect_user_grade(implementation: Any, db: Any, user: Any) -> int:
    """从学生档案或所属班级自动检测学生本人年级（规范化到 3..6，默认 5）."""
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
) -> int:
    """优先使用显式请求的 grade，未传时回落至学生本人年级."""
    base = clamp_arena_grade(student_grade, DEFAULT_ARENA_GRADE)
    if requested_grade is None or str(requested_grade).strip() == "":
        return base
    return clamp_arena_grade(requested_grade, base)


def grade_relation(target_grade: int, student_grade: int) -> tuple[str, str]:
    """返回目标年级相对于学生本人年级的关系编码与中文标签."""
    tg = clamp_arena_grade(target_grade)
    sg = clamp_arena_grade(student_grade)
    if tg == sg:
        return "current", "本年级"
    if tg < sg:
        return "review", "查漏补缺"
    return "advance", "超前探索"


def build_available_grades(active_grade: int, student_grade: int) -> list[dict[str, Any]]:
    """构建顶栏 3/4/5/6 年级切换胶囊元数据."""
    ag = clamp_arena_grade(active_grade)
    sg = clamp_arena_grade(student_grade)
    out: list[dict[str, Any]] = []
    for g in SUPPORTED_GRADES:
        rel_code, rel_label = grade_relation(g, sg)
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
    """根据年级返回差异化交互配置，驱动前端渲染与后端计时/判分适配."""
    g = clamp_arena_grade(grade)
    if g == 3:
        return {
            "grade": 3,
            "gradeLabel": "三年级",
            "tier": "g3_guided",
            "tierLabel": "三年级·启蒙辅助型（语音读题 + 数字键盘/字块托盘 + 宽松限时）",
            "tierShortLabel": "启蒙辅助模式",
            "stemReadAloud": True,
            "stemReadAloudDefault": True,
            "speechRate": 0.88,
            "mathKeypad": "full",
            "spellAssist": "tile_or_first_letter",
            "chineseAssistTiles": True,
            "writingScaffold": True,
            "writingTargetChars": "40～60字",
            "writingMinChars": 35,
            "perQuestionSec": 25,
            "perQuestionSecMultiplier": 1.25,
            "maxPlays": 3,
            "maxPlaysBonus": 1,
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
            "speechRate": 0.94,
            "mathKeypad": "compact",
            "spellAssist": "first_letter_hint",
            "chineseAssistTiles": False,
            "writingScaffold": True,
            "writingTargetChars": "60～80字",
            "writingMinChars": 50,
            "perQuestionSec": 22,
            "perQuestionSecMultiplier": 1.1,
            "maxPlays": 2,
            "maxPlaysBonus": 0,
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
            "speechRate": 1.0,
            "mathKeypad": "none",
            "spellAssist": "strict_keyboard",
            "chineseAssistTiles": False,
            "writingScaffold": False,
            "writingTargetChars": "80～100字",
            "writingMinChars": 70,
            "perQuestionSec": 20,
            "perQuestionSecMultiplier": 1.0,
            "maxPlays": 2,
            "maxPlaysBonus": 0,
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
        "speechRate": 1.0,
        "mathKeypad": "none",
        "spellAssist": "strict_keyboard",
        "chineseAssistTiles": False,
        "writingScaffold": False,
        "writingTargetChars": "100～120字",
        "writingMinChars": 85,
        "perQuestionSec": 20,
        "perQuestionSecMultiplier": 1.0,
        "maxPlays": 2,
        "maxPlaysBonus": 0,
        "largeTouchUi": False,
        "helperTone": "graduation",
    }


def infer_grade_from_node_key(node_key: str, default_grade: int = DEFAULT_ARENA_GRADE) -> int:
    """从节点编码（如 G3-M1-1、G4-E2-3、G6-C1-2 或五年级 M1-1/E1-1/C1-1）推断所属年级."""
    k = str(node_key or "").strip().upper()
    if k.startswith("G3-"):
        return 3
    if k.startswith("G4-"):
        return 4
    if k.startswith("G6-"):
        return 6
    if k.startswith("G5-"):
        return 5
    return clamp_arena_grade(default_grade)


def infer_grade_from_sprint_slug(slug: str, default_grade: int = DEFAULT_ARENA_GRADE) -> int:
    """从专项 slug（如 g3-listening-sprint、g4-math-calc、g6-chinese-poetry）推断所属年级."""
    s = str(slug or "").strip().lower()
    if s.startswith("g3-"):
        return 3
    if s.startswith("g4-"):
        return 4
    if s.startswith("g6-"):
        return 6
    if s.startswith("g5-"):
        return 5
    return clamp_arena_grade(default_grade)


__all__ = [
    "DEFAULT_ARENA_GRADE",
    "GRADE_LABELS",
    "GRADE_THEMES",
    "SUPPORTED_GRADES",
    "build_available_grades",
    "clamp_arena_grade",
    "detect_user_grade",
    "get_age_interaction_profile",
    "grade_relation",
    "infer_grade_from_node_key",
    "infer_grade_from_sprint_slug",
    "resolve_arena_grade",
]
