"""语数英自主练习共享核心：记忆保鲜（星光褪色/待温习）+ 教师考点私房题."""
from __future__ import annotations

from datetime import datetime, timedelta
import json
import re
import threading
from typing import Any

from sqlalchemy import Column, DateTime, Integer, String, Table, Text, desc, select

CUSTOM_QUESTION_PREFIX = "cq_"

CUSTOM_TYPE_LABELS = {
    "single_choice": "老师加题·单选",
    "true_false": "老师加题·判断",
    "fill_blank": "老师加题·填空",
}

TRUE_TOKENS = {"正确", "对", "true", "t", "yes", "y", "√", "1", "a"}
FALSE_TOKENS = {"错误", "错", "false", "f", "no", "n", "×", "0", "b"}


def _to_naive_utc(dt: Any) -> datetime | None:
    if dt is None:
        return None
    if isinstance(dt, str):
        s = dt.strip()
        if not s:
            return None
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(dt, datetime):
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(tz=None).replace(tzinfo=None)
    return dt


def compute_review_meta(
    row: Any | None,
    now: datetime | None = None,
    *,
    stars: int | None = None,
    needs_repair: bool | None = None,
) -> dict[str, Any]:
    """计算知识节点的记忆保鲜 / 待温习元数据.

    规则：
    - stars in (1, 2) 且 updated_at 距今超过 14 天 -> reviewDue = True
    - stars >= 3 且 updated_at 距今超过 30 天 -> reviewDue = True
    - 其余情况（含未点亮 stars == 0 或 needs_repair）-> reviewDue = False
    """
    if row is None:
        return {"reviewDue": False, "daysSincePractice": 0, "reviewCycleDays": 14}

    if isinstance(row, dict):
        eff_stars = int(stars if stars is not None else row.get("stars", 0) or 0)
        eff_repair = bool(
            needs_repair
            if needs_repair is not None
            else (row.get("needs_repair") if "needs_repair" in row else row.get("needsRepair", False))
        )
        raw_updated = row.get("updated_at") if "updated_at" in row else row.get("updatedAt")
    else:
        eff_stars = int(stars if stars is not None else getattr(row, "stars", 0) or 0)
        eff_repair = bool(
            needs_repair
            if needs_repair is not None
            else getattr(row, "needs_repair", getattr(row, "needsRepair", False))
        )
        raw_updated = getattr(row, "updated_at", getattr(row, "updatedAt", None))

    cycle_days = 30 if eff_stars >= 3 else 14
    updated_dt = _to_naive_utc(raw_updated)
    now_dt = _to_naive_utc(now) if now is not None else datetime.utcnow()
    if updated_dt is None or now_dt is None:
        return {"reviewDue": False, "daysSincePractice": 0, "reviewCycleDays": cycle_days}

    delta = now_dt - updated_dt
    days_since = max(0, int(delta.total_seconds() // 86400))

    if eff_repair or eff_stars <= 0:
        return {"reviewDue": False, "daysSincePractice": days_since, "reviewCycleDays": cycle_days}

    review_due = delta > timedelta(days=cycle_days)
    return {
        "reviewDue": bool(review_due),
        "daysSincePractice": days_since,
        "reviewCycleDays": cycle_days,
    }


_DDL_LOCK = threading.Lock()


def ensure_tables_on_session(db: Any, *tables: Table) -> None:
    """在同一 Session 已占用的连接上按 Engine 幂等建表，避免 db.get_bind() 额外抢占连接池导致 8 并发死锁."""
    if not tables:
        return
    bind = db.get_bind()
    ensured: set[str] | None = getattr(bind, "_cy_ensured_tables", None)
    if ensured is not None and all(t.name in ensured for t in tables):
        return
    with _DDL_LOCK:
        ensured = getattr(bind, "_cy_ensured_tables", None)
        if ensured is None:
            ensured = set()
            try:
                setattr(bind, "_cy_ensured_tables", ensured)
            except Exception:
                pass
        pending = [t for t in tables if t.name not in ensured]
        if not pending:
            return
        conn = db.connection()
        for tbl in pending:
            tbl.create(bind=conn, checkfirst=True)
            ensured.add(tbl.name)


def register_arena_custom_questions_table(implementation: Any) -> Table:
    """将 arena_custom_questions 注册到 Base.metadata（支持 checkfirst 建表）."""
    md = implementation.Base.metadata
    if "arena_custom_questions" not in md.tables:
        Table(
            "arena_custom_questions",
            md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("subject", String(16), nullable=False, index=True),
            Column("node_key", String(32), nullable=False, index=True),
            Column("question_type", String(24), nullable=False),  # single_choice | fill_blank | true_false
            Column("stem", Text, nullable=False),
            Column("options_json", Text, nullable=False, default="[]"),
            Column("answer", Text, nullable=False),
            Column("explanation", Text, nullable=False, default=""),
            Column("created_by", Integer, nullable=False),
            Column("active", Integer, nullable=False, default=1),
            Column("created_at", DateTime, nullable=False),
        )
    return md.tables["arena_custom_questions"]


def parse_options_json(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    try:
        parsed = json.loads(raw or "[]")
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        pass
    return []


def resolve_choice_correct_index(options: list[str], answer: str) -> int:
    """将单选答案（支持选项文本或 A/B/C/D 或 0-based 数字）解析为正确选项索引."""
    ans = str(answer or "").strip()
    if not options:
        return 0
    for idx, opt in enumerate(options):
        if opt.strip().lower() == ans.lower():
            return idx
    upper = ans.upper()
    if len(upper) == 1 and "A" <= upper <= "Z":
        idx = ord(upper) - ord("A")
        if 0 <= idx < len(options):
            return idx
    if ans.isdigit():
        idx = int(ans)
        if 0 <= idx < len(options):
            return idx
    return 0


def resolve_tf_is_true(answer: str) -> bool:
    tok = str(answer or "").strip().lower()
    if tok in FALSE_TOKENS:
        return False
    return True


def serialize_custom_question_row(row: Any) -> dict[str, Any]:
    """序列化教师端/预览接口用的私房题对象."""
    qtype = str(row.question_type)
    opts = parse_options_json(row.options_json)
    if qtype == "true_false" and not opts:
        opts = ["正确", "错误"]
    return {
        "id": int(row.id),
        "questionId": f"{CUSTOM_QUESTION_PREFIX}{int(row.id)}",
        "subject": str(row.subject),
        "nodeKey": str(row.node_key),
        "questionType": qtype,
        "typeLabel": CUSTOM_TYPE_LABELS.get(qtype, "老师加题"),
        "stem": str(row.stem),
        "text": str(row.stem),
        "options": opts,
        "answer": str(row.answer),
        "explanation": str(row.explanation or ""),
        "createdBy": int(row.created_by),
        "createdAt": row.created_at.strftime("%Y-%m-%d %H:%M") if getattr(row, "created_at", None) else "",
        "isCustom": True,
    }


def _display_qtype_for_subject(subject: str, raw_qtype: str) -> str:
    """适配三科地图前端的客观题渲染类型，同时保留 customQuestionType 供判卷与展示使用."""
    if raw_qtype in ("single_choice", "true_false"):
        if subject == "英语":
            return "reading_choice"
        if subject == "语文":
            return "basic_choice"
    return raw_qtype


def fetch_custom_quiz_questions(
    implementation: Any,
    db: Any,
    *,
    school_id: int,
    subject: str,
    node_key: str,
    limit: int = 3,
    seed: int = 0,
) -> list[dict[str, Any]]:
    """抽取本校该考点的有效老师私房题（最多 limit 题），构造成与微测兼容的题目字典."""
    tbl = register_arena_custom_questions_table(implementation)
    ensure_tables_on_session(db, tbl)
    rows = db.execute(
        select(tbl)
        .where(
            tbl.c.school_id == int(school_id),
            tbl.c.subject == subject,
            tbl.c.node_key == node_key,
            tbl.c.active == 1,
        )
        .order_by(desc(tbl.c.id))
    ).all()
    if not rows:
        return []
    n = len(rows)
    if n > limit:
        shift = abs(int(seed)) % n
        ordered = list(rows[shift:]) + list(rows[:shift])
        picked = ordered[:limit]
    else:
        picked = list(rows)

    out: list[dict[str, Any]] = []
    for r in picked:
        raw_qtype = str(r.question_type)
        opts = parse_options_json(r.options_json)
        if raw_qtype == "true_false":
            if not opts:
                opts = ["正确", "错误"]
            is_true = resolve_tf_is_true(str(r.answer))
            cidx = 0 if is_true else 1
            canonical_ans = opts[cidx] if cidx < len(opts) else ("正确" if is_true else "错误")
        elif raw_qtype == "single_choice":
            cidx = resolve_choice_correct_index(opts, str(r.answer))
            canonical_ans = opts[cidx] if 0 <= cidx < len(opts) else str(r.answer)
        else:
            cidx = None
            canonical_ans = str(r.answer).strip()

        item: dict[str, Any] = {
            "id": f"{CUSTOM_QUESTION_PREFIX}{int(r.id)}",
            "customId": int(r.id),
            "isCustom": True,
            "nodeKey": str(r.node_key),
            "questionType": _display_qtype_for_subject(subject, raw_qtype),
            "customQuestionType": raw_qtype,
            "typeLabel": CUSTOM_TYPE_LABELS.get(raw_qtype, "老师加题"),
            "level": "medium",
            "levelLabel": "老师加题",
            "marks": 2,
            "text": str(r.stem),
            "options": opts,
            "answer": canonical_ans,
            "acceptableAnswers": [canonical_ans, str(r.answer).strip()],
            "explanation": str(r.explanation or ""),
            "figure": None,
        }
        if cidx is not None:
            item["correctIndex"] = cidx
        out.append(item)
    return out


def is_custom_question_id(qid: Any) -> bool:
    return isinstance(qid, str) and qid.startswith(CUSTOM_QUESTION_PREFIX)


def _norm_fill(s: Any) -> str:
    txt = str(s or "").strip().lower()
    txt = re.sub(r"\s+", " ", txt)
    return txt


def grade_custom_question(
    implementation: Any,
    db: Any,
    question: dict[str, Any],
    *,
    selected_index: int | None = None,
    text_answer: str = "",
) -> tuple[bool, str, str]:
    """判分老师私房题，返回 (correct, standard_answer, explanation).

    优先从 arena_custom_questions 表读取最新标准答案和解析，若记录不存在则回退使用题目快照。
    """
    qid_str = str(question.get("id") or "")
    raw_qtype = str(question.get("customQuestionType") or question.get("questionType") or "fill_blank")
    opts = list(question.get("options") or [])
    answer = str(question.get("answer") or "")
    explanation = str(question.get("explanation") or "")

    if qid_str.startswith(CUSTOM_QUESTION_PREFIX):
        try:
            cid = int(qid_str[len(CUSTOM_QUESTION_PREFIX):])
            tbl = register_arena_custom_questions_table(implementation)
            ensure_tables_on_session(db, tbl)
            row = db.execute(select(tbl).where(tbl.c.id == cid)).first()
            if row is not None:
                raw_qtype = str(row.question_type)
                opts = parse_options_json(row.options_json)
                if raw_qtype == "true_false" and not opts:
                    opts = ["正确", "错误"]
                answer = str(row.answer)
                explanation = str(row.explanation or "")
        except Exception:
            pass

    if raw_qtype == "single_choice":
        cidx = resolve_choice_correct_index(opts, answer)
        canonical_ans = opts[cidx] if 0 <= cidx < len(opts) else answer
        if selected_index is not None:
            return int(selected_index) == cidx, canonical_ans, explanation
        txt = str(text_answer or "").strip()
        if not txt:
            return False, canonical_ans, explanation
        if _norm_fill(txt) == _norm_fill(canonical_ans) or _norm_fill(txt) == _norm_fill(answer):
            return True, canonical_ans, explanation
        if resolve_choice_correct_index(opts, txt) == cidx and (txt.upper() in ("A", "B", "C", "D", "E", "F") or txt.isdigit()):
            return True, canonical_ans, explanation
        return False, canonical_ans, explanation

    if raw_qtype == "true_false":
        if not opts:
            opts = ["正确", "错误"]
        is_true = resolve_tf_is_true(answer)
        cidx = 0 if is_true else 1
        canonical_ans = opts[cidx] if cidx < len(opts) else ("正确" if is_true else "错误")
        if selected_index is not None:
            return int(selected_index) == cidx, canonical_ans, explanation
        tok = str(text_answer or "").strip().lower()
        if not tok:
            return False, canonical_ans, explanation
        if is_true and tok in TRUE_TOKENS:
            return True, canonical_ans, explanation
        if (not is_true) and tok in FALSE_TOKENS:
            return True, canonical_ans, explanation
        return False, canonical_ans, explanation

    # fill_blank
    got = _norm_fill(text_answer)
    if not got:
        return False, answer.strip(), explanation
    expected_norm = _norm_fill(answer)
    if got == expected_norm:
        return True, answer.strip(), explanation
    # 兼容无空格比对（如中文或数学表达式去空格）
    if got.replace(" ", "") == expected_norm.replace(" ", ""):
        return True, answer.strip(), explanation
    return False, answer.strip(), explanation


__all__ = [
    "CUSTOM_QUESTION_PREFIX",
    "CUSTOM_TYPE_LABELS",
    "compute_review_meta",
    "ensure_tables_on_session",
    "fetch_custom_quiz_questions",
    "grade_custom_question",
    "is_custom_question_id",
    "parse_options_json",
    "register_arena_custom_questions_table",
    "resolve_choice_correct_index",
    "resolve_tf_is_true",
    "serialize_custom_question_row",
]
