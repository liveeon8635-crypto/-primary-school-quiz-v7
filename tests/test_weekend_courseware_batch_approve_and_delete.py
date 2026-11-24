from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cw_batch_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_delete_lesson_clears_courseware_and_approve_all_batches_in_one_tx(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
from sqlalchemy import select
from changying.web.weekend_courseware import register_courseware_table

FRAME = {
    "type": "uploaded_image",
    "data_url": "data:image/jpeg;base64,/9j/2Q==",
    "alt": "分步图",
}


def make_bundle(lesson_no, stems):
    def page(stage, index, text, answer):
        return {
            "stageNo": stage,
            "page": index,
            "expectedPageText": text,
            "kind": "steps",
            "writtenTask": False,
            "params": {
                "title": "分步讲解",
                "problem": text,
                "steps": ["第一步观察条件", "第二步代入计算"],
                "answer": answer,
                "stepFigures": [FRAME, FRAME, FRAME],
            },
        }

    return {
        "schemaVersion": 1,
        "subject": "数学",
        "dryRun": False,
        "onConflict": "overwrite",
        "items": [{
            "lessonNo": lesson_no,
            "title": "第13课测试",
            "coreTarget": "测试批量审核与删课清课件",
            "teacherPlan": "测试教案",
            "ppt": ["知识点1：测试内容。"],
            "examples": ["例1 测试例题。\n【答案】10。"],
            "closureTraining": "订正错题。",
            "questions": [],
            "writtenQuestions": [
                {"type": "short_answer", "material": "", "stem": s, "reference": "答案", "hints": []}
                for s in stems
            ],
        }],
        "courseware": {
            "dryRun": False,
            "replaceExisting": True,
            "pages": [
                page(2, 0, "知识点1：测试内容。", "结论"),
                page(3, 0, "例1 测试例题。\n【答案】10。", "10"),
                *[page(4, idx, s, "答案") for idx, s in enumerate(stems)],
            ],
        },
    }


with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    url = "/teacher/weekend/lessons/import"

    # 1. Import Lesson 13 bundle with 2 practice questions + 4 courseware pages
    b1 = make_bundle(13, ["第1题 旧练习一。", "第2题 旧练习二。"])
    r1 = client.post(
        url, headers=th,
        data={"subject": "数学", "lessonNo": "13", "force": "0"},
        files={"file": ("l13_v1.json", json.dumps(b1, ensure_ascii=False).encode("utf8"), "application/json")},
    )
    assert r1.status_code == 200, r1.text
    lid = r1.json()["lessonId"]

    # Approve written questions first so Stage 4 courseware can be approved
    wq = client.get(f"/teacher/weekend/lessons/{lid}/written/questions", headers=th).json()
    apq = client.post(
        f"/teacher/weekend/lessons/{lid}/written/questions",
        headers=th,
        json={"approve": [q["id"] for q in wq["items"]]},
    )
    assert apq.status_code == 200, apq.text

    # 2. Batch approve Stage 2 & 3 first, then all remaining drafts in one call
    ap_stage2 = client.post(
        f"/teacher/weekend/lessons/{lid}/courseware/approve-all",
        headers=th,
        json={"stageNo": 2},
    )
    assert ap_stage2.status_code == 200, ap_stage2.text
    d2 = ap_stage2.json()
    assert d2["approvedCount"] == 1 and d2["totalDrafts"] == 1 and d2["failed"] == []

    ap_rest = client.post(
        f"/teacher/weekend/lessons/{lid}/courseware/approve-all",
        headers=th,
        json={},
    )
    assert ap_rest.status_code == 200, ap_rest.text
    dr = ap_rest.json()
    assert dr["approvedCount"] == 3 and dr["totalDrafts"] == 3 and dr["failed"] == []
    assert all(it["status"] == "approved" for it in dr["items"])

    # 3. Delete lesson -> weekend_courseware row MUST be deleted too
    dl = client.request(
        "DELETE", f"/teacher/weekend/lessons/{lid}",
        headers=th,
        json={"subject": "数学", "lessonNo": 13, "confirmed": True},
    )
    assert dl.status_code == 200, dl.text
    cw_table = register_courseware_table(legacy)
    with legacy.SessionLocal() as db:
        row = db.execute(select(cw_table).where(cw_table.c.lesson_id == lid)).first()
        assert row is None, "delete_lesson must remove leftover weekend_courseware row"

    # 4. Re-import Lesson 13 with DIFFERENT practice stems -> MUST succeed (no 409!)
    b2 = make_bundle(13, ["第1题 全新练习A。", "第2题 全新练习B。"])
    r2 = client.post(
        url, headers=th,
        data={"subject": "数学", "lessonNo": "13", "force": "0"},
        files={"file": ("l13_v2.json", json.dumps(b2, ensure_ascii=False).encode("utf8"), "application/json")},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["coursewarePagesFound"] == 4

    # 5. Frontend exposes /courseware/approve-all
    page_resp = client.get("/v1/weekend-plan", headers=th)
    assert page_resp.status_code == 200
    assert "/courseware/approve-all" in page_resp.text
    print("OK")
''')
