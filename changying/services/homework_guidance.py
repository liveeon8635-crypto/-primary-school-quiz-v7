"""晚托作业助手的引导式讲解：从学生已经会的知识出发，一步步让他自己做出来。

The model writes the whole guide in one call: every step first asks the pupil a small question, then explains.
The page runs the guide without further calls. When the school has published a knowledge map for the pupil's
grade, the prompt carries the map with the pupil's own mastery (keys, names and 已会/薄弱/未测 only, never a name),
so the guide can start from what he already knows; afterwards the system, not the model, adds the concrete
anchors: the point on his map, the prerequisites he has / has not mastered, a question of that point he once got
right, the exam it counts for, and a link to the point's 3—5 question quick check (whose first answers count).

Number steps are only asked when the program can check their arithmetic; anything else is shown, not asked, so
the page never tells a pupil he is wrong on the strength of an unchecked model answer. Nothing here scores:
the guide only decides when to show a hint, and mastery still comes from first answers to reviewed questions.
"""
from __future__ import annotations

from datetime import date
from fractions import Fraction
from typing import Any

from changying.services.homework_knowledge import match_knowledge
from changying.services.homework_math_check import OK, check_solution, parse_answer
from changying.services.knowledge_maps import MASTERY_LABELS, assessed

MAX_MAP_NODES = 80
SOLVED_CHARS = 120


def _state(node_m: dict[str, Any], key: str) -> str:
    level = (node_m.get(key) or {}).get("level")
    return level or ""


def map_lines(m: dict[str, Any], node_m: dict[str, Any]) -> str:
    """The map as the prompt shows it: ``编号 名称｜先学：…｜已会/薄弱/未测``, one point per line."""
    words = {"pass": "已会", "fluent": "已会", "weak": "薄弱"}
    lines = []
    for n in m["nodes"]:
        if n["kind"] == "display":
            continue
        before = "、".join(n["prereqs"]) or "无"
        lines.append(f"{n['key']} {n['name'][:30]}｜先学：{before}｜{words.get(_state(node_m, n['key']), '未测')}")
        if len(lines) >= MAX_MAP_NODES:
            break
    return "\n".join(lines)


def pick_node(m: dict[str, Any], node_key: str, knowledge_point: str) -> dict[str, Any] | None:
    """The map point of the question: the key the model chose, else the point whose name fits its phrase."""
    nodes = [n for n in m["nodes"] if n["kind"] != "display"]
    found = next((n for n in nodes if n["key"] == str(node_key or "").strip()), None)
    if found is None and knowledge_point:
        hit = match_knowledge(knowledge_point, [(n["key"], n["name"]) for n in nodes])
        found = next((n for n in nodes if hit and n["key"] == hit[0]), None)
    return found


def _check(answer: str) -> dict[str, float] | None:
    """What the page compares the pupil's number with: the value and the rounding the answer allows."""
    try:
        value, decimals = parse_answer(answer)
    except Exception:  # noqa: BLE001 - an answer the program cannot read is simply not asked
        return None
    tol = Fraction(1, 2 * 10**decimals) if decimals else abs(value) / 10**9
    return {"value": float(value), "tol": float(tol) + 1e-12}


def check_steps(solution: dict[str, Any], final_ok: bool) -> dict[str, Any]:
    """Keep a number question only when its arithmetic checks out; give the page what it compares with."""
    steps = []
    for step in solution["steps"]:
        step = dict(step)
        if step.get("kind") == "number":
            ok = check_solution(step.get("expression"), step.get("answer"))["status"] == OK
            target = _check(step.get("answer", "")) if ok else None
            if target is None:
                step["kind"] = "read"
                step["text"] = step["text"] or step.get("ask", "")
            else:
                step["check"] = target
        steps.append(step)
    out = dict(solution, steps=steps)
    target = _check(solution["answer"]) if final_ok else None
    if target is not None:
        out["finalCheck"] = target
    return out


def solved_question(m: dict[str, Any], node: dict[str, Any], first: dict[int, bool], texts: dict[int, str]) -> dict[str, str] | None:
    """A question of this point (else of a prerequisite) the pupil got right the first time: his own experience."""
    names = {n["key"]: n for n in m["nodes"]}
    for key in [node["key"], *node["prereqs"]]:
        point = names.get(key)
        if point is None:
            continue
        for qid in sorted(int(q) for q in point["levels"]):
            if first.get(qid) is True and texts.get(qid):
                return {"text": texts[qid][:SOLVED_CHARS], "from": f"{point['key']} {point['name']}"}
    return None


def exam_line(title: str, exam_date: str, today: date) -> str:
    try:
        days = (date.fromisoformat(exam_date) - today).days
    except ValueError:
        return ""
    if days < 0:
        return ""
    return f"这个知识点在「{title}」的考试范围里" + ("，今天就考试。" if days == 0 else f"，离考试还有 {days} 天。")


def guide_layer(m: dict[str, Any], node: dict[str, Any], node_m: dict[str, Any], first: dict[int, bool],
                texts: dict[int, str], exam: str) -> dict[str, Any]:
    """Where the question sits on the pupil's map, built by the system from his own record."""
    names = {n["key"]: n for n in m["nodes"]}
    known, weak = [], []
    for key in node["prereqs"]:
        point = names.get(key)
        if point is None:
            continue
        state = _state(node_m, key)
        if state in ("pass", "fluent"):
            known.append(f"{key} {point['name']}")
        elif state == "weak":
            weak.append(f"{key} {point['name']}")
    state = _state(node_m, node["key"])
    return {
        "node": {"key": node["key"], "name": node["name"], "state": state, "stateText": MASTERY_LABELS.get(state, "还没测")},
        "known": known,
        "weak": weak,
        "solved": solved_question(m, node, first, texts),
        "exam": exam,
        "quiz": assessed(m, node),
    }


__all__ = ["check_steps", "exam_line", "guide_layer", "map_lines", "pick_node", "solved_question"]
