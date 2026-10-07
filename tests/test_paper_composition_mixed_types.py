"""Feedback 刘麦迪 (2026-10-05): "题目全都是一个题型，能不能十个题目十个题型".

Assignment papers were composed in the browser with ``options.length >= 2``,
which dropped every fill-blank / calculation / short-answer question. Papers are
now composed server-side (POST /teacher/papers/compose) and spread across all
online auto-graded question types.
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from changying.services.paper_composition import (
    AUTO_GRADED_TYPES,
    compose_question_ids,
    distribution_text,
    online_question_type,
    type_distribution,
)

ROOT = Path(__file__).resolve().parents[1]


def _rows(per_type: int) -> list[tuple[int, str]]:
    rows, qid = [], 1
    for qtype in AUTO_GRADED_TYPES:
        for _ in range(per_type):
            rows.append((qid, qtype))
            qid += 1
    return rows


def test_ten_questions_are_spread_across_all_five_types():
    rows = _rows(6)
    ids = compose_question_ids(rows, 10, rng=random.Random(7))
    assert len(ids) == len(set(ids)) == 10
    dist = type_distribution(dict(rows), ids)
    assert dist == {t: 2 for t in AUTO_GRADED_TYPES}
    assert distribution_text(dist) == "单选2 · 判断2 · 填空2 · 计算2 · 简答2"


def test_uneven_banks_still_use_every_available_type_before_repeating():
    rows = [(1, "single_choice"), (2, "single_choice"), (3, "single_choice"), (4, "single_choice"), (5, "fill_blank"), (6, "true_false")]
    ids = compose_question_ids(rows, 4, rng=random.Random(1))
    assert set(type_distribution(dict(rows), ids)) == {"single_choice", "fill_blank", "true_false"}
    assert len(compose_question_ids(rows, 50, rng=random.Random(1))) == 6


def test_choice_mode_and_required_questions():
    rows = _rows(3)
    ids = compose_question_ids(rows, 6, mix="choice", rng=random.Random(3))
    assert set(type_distribution(dict(rows), ids)) == {"single_choice", "true_false"}
    led = compose_question_ids(rows, 5, rng=random.Random(3), required_first=[99])
    assert led[0] == 99 and len(led) == 5 and led.count(99) == 1


def test_only_online_gradable_questions_are_eligible():
    meta = lambda row: {"answer": row.answer}
    qtype_of = lambda row: row.qtype
    q = lambda **kw: SimpleNamespace(**{"options_json": "[]", "correct_index": -1, "answer": "", **kw})
    assert online_question_type(q(qtype="single_choice", options_json='["A","B","C","D"]', correct_index=2), question_type_of=qtype_of, answer_meta=meta) == "single_choice"
    assert online_question_type(q(qtype="single_choice", options_json='["A"]', correct_index=0), question_type_of=qtype_of, answer_meta=meta) is None
    assert online_question_type(q(qtype="true_false", options_json='["正确","错误"]', correct_index=5), question_type_of=qtype_of, answer_meta=meta) is None
    assert online_question_type(q(qtype="fill_blank", answer="12"), question_type_of=qtype_of, answer_meta=meta) == "fill_blank"
    assert online_question_type(q(qtype="calculation", answer=" "), question_type_of=qtype_of, answer_meta=meta) is None
    assert online_question_type(q(qtype="non_choice", answer="参考"), question_type_of=qtype_of, answer_meta=meta) is None


def test_both_assignment_forms_compose_on_the_server():
    from changying.web.classic_ui import inject_classic_ui
    import app_v924 as legacy

    html = inject_classic_ui(legacy.INDEX_HTML)
    form = html[html.find("function assignmentForm(classes){"):html.find("async function fetchHomeworkMediaBlob")]
    assert "changying_mixed_question_types_v1" in form
    assert '"/teacher/papers/compose"' in form
    assert 'id="homeworkTypeMix"' in html
    assert "(q.options||[]).length>=2" not in form
    assert '作业已布置（"+composedTypeSummary+"）' in form

    from changying.web.v1_teaching_actions import _TEACHING_ACTIONS_SNIPPET as v1

    assert "'/teacher/papers/compose'" in v1
    assert 'id="cy-amix"' in v1
    assert "q.options.length>=2" not in v1
    assert "qs.slice(0,count)" not in v1


RUNTIME = r"""
import json
from fastapi.testclient import TestClient
import app_v924 as legacy
from app import app


def headers_for(db, username):
    user = db.scalar(legacy.select(legacy.User).where(legacy.User.username == username))
    sec = legacy.security_for(db, user)
    sec.must_change_password = False
    db.commit()
    return {"Authorization": "Bearer " + legacy.make_token(user, sec, False)}


SUBJECT, TEXTBOOK, UNIT = "数学", "人教版", "多题型单元"

with TestClient(app) as client:
    with legacy.SessionLocal() as db:
        th = headers_for(db, "teacher1")
        sh = headers_for(db, "student1")
        teacher = db.scalar(legacy.select(legacy.User).where(legacy.User.username == "teacher1"))
        student = db.scalar(legacy.select(legacy.User).where(legacy.User.username == "student1"))
        cls = db.scalar(legacy.select(legacy.SchoolClass).join(legacy.ClassStudent, legacy.ClassStudent.class_id == legacy.SchoolClass.id).where(
            legacy.SchoolClass.teacher_id == teacher.id, legacy.ClassStudent.student_id == student.id))
        assert cls is not None, "demo seed must put student1 in a class of teacher1"
        answers = {}

        def add(qtype, n, options=None, correct=-1, answer=""):
            q = legacy.Question(school_id=teacher.school_id, grade=cls.grade, subject=SUBJECT, textbook=TEXTBOOK, semester="上册", unit=UNIT,
                                knowledge="多题型", text=f"{qtype} 第{n}题", options_json=json.dumps(options or [], ensure_ascii=False),
                                correct_index=correct, explanation="", question_type=qtype,
                                answer_json=json.dumps({"answer": answer, "accepted": []}, ensure_ascii=False), figure_json="{}", creator_id=teacher.id)
            db.add(q); db.flush(); return q

        for n in range(3):
            answers[add("single_choice", n, ["1", "2", "3", "4"], 1).id] = {"selected_index": 1}
            answers[add("true_false", n, ["正确", "错误"], 0).id] = {"selected_index": 0}
            answers[add("fill_blank", n, answer="12").id] = {"text_answer": "12"}
            answers[add("calculation", n, answer="3.5").id] = {"text_answer": "3.50"}
            answers[add("short_answer", n, answer="24厘米").id] = {"text_answer": "24 厘米"}
        broken = add("fill_blank", 99, answer="").id          # no standard answer: not gradable
        opened = add("non_choice", 98, answer="参考").id       # teacher-reviewed only
        db.commit()
        grade, class_id, student_id = cls.grade, cls.id, student.id

    body = {"title": "多题型作业", "grade": grade, "subject": SUBJECT, "textbook": TEXTBOOK, "unit": UNIT, "count": 10}
    r = client.post("/teacher/papers/compose", headers=th, json=body)
    assert r.status_code == 200, r.text
    paper = r.json()
    assert paper["typeDistribution"] == {"single_choice": 2, "true_false": 2, "fill_blank": 2, "calculation": 2, "short_answer": 2}, paper
    assert paper["typeSummary"] == "单选2 · 判断2 · 填空2 · 计算2 · 简答2"
    assert broken not in paper["questionIDs"] and opened not in paper["questionIDs"]
    assert paper["availableCount"] == 15

    choice = client.post("/teacher/papers/compose", headers=th, json={**body, "mix": "choice", "count": 6}).json()
    assert set(choice["typeDistribution"]) == {"single_choice", "true_false"}

    missing = client.post("/teacher/papers/compose", headers=th, json={**body, "unit": "没有题的单元"})
    assert missing.status_code == 400 and "本单元暂无" in missing.json()["detail"]
    broad = client.post("/teacher/papers/compose", headers=th, json={**body, "unit": "没有题的单元", "broaden_unit": True})
    assert broad.status_code == 200 and broad.json()["broadenedUnit"] is True

    assert client.post("/teacher/papers/compose", headers=th, json={**body, "required_question_ids": [10**9]}).status_code == 400
    assert client.post("/teacher/papers/compose", headers=sh, json=body).status_code == 403

    a = client.post("/teacher/assignments", headers=th, json={"title": "多题型作业", "class_id": class_id, "paper_id": paper["id"], "due_date": "2030-01-01"})
    assert a.status_code == 200, a.text
    aid = a.json()["id"]
    qs = client.get(f"/papers/{paper['id']}/questions", headers=sh)
    assert qs.status_code == 200, qs.text
    assert {q["questionType"] for q in qs.json()} == {"single_choice", "true_false", "fill_blank", "calculation", "short_answer"}
    submitted = [{"question_id": q["id"], **answers[q["id"]]} for q in qs.json()]
    s = client.post(f"/student/assignments/{aid}/submit", headers=sh, json={"answers": submitted})
    assert s.status_code == 200, s.text
    assert s.json()["score"] == 100, s.json()

    subs = client.get(f"/teacher/assignments/{aid}/submissions", headers=th).json()
    row = next(x for x in subs if x["studentID"] == student_id)
    assert row["score"] == 100 and row["correct"] == 10 and row["total"] == 10
    export = client.get(f"/teacher/assignments/{aid}/export.xlsx", headers=th)
    assert export.status_code == 200 and export.content[:2] == b"PK"
print("MIXED_TYPE_ASSIGNMENT_OK")
"""


def test_runtime_mixed_type_paper_assign_submit_and_report(tmp_path):
    env = os.environ.copy()
    env.update({"DATABASE_URL": f"sqlite:///{tmp_path / 'mixed.sqlite3'}", "ENABLE_DEMO_SEED": "1", "PYTHONPATH": str(ROOT)})
    result = subprocess.run([sys.executable, "-c", RUNTIME], cwd=ROOT, env=env, capture_output=True, text=True, timeout=240, check=False)
    assert result.returncode == 0 and "MIXED_TYPE_ASSIGNMENT_OK" in result.stdout, (
        f"mixed-type runtime failed\nstdout:\n{result.stdout[-4000:]}\nstderr:\n{result.stderr[-6000:]}"
    )
