from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cw_dedup_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_courseware_media_dedup_slim_response_and_restore(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
import base64
from sqlalchemy import select
from changying.web.weekend_courseware import items_of, register_courseware_table, stage_pages

MD = """# 第12课：梯形面积
## 本节目标
认识梯形面积和对应的高。
## 教学流程
先拼合，再计算。
## 例题
1. 上底5厘米、下底7厘米、高5厘米，求梯形面积。
【答案】30平方厘米。
"""

BIG_IMG_1 = "data:image/jpeg;base64," + ("A" * 4000)
BIG_IMG_2 = "data:image/jpeg;base64," + ("B" * 4000)
BIG_IMG_3 = "data:image/jpeg;base64," + ("C" * 4000)

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    imported = client.post(
        "/teacher/weekend/lessons/import/markdown",
        headers=th,
        data={"subject": "数学"},
        files={"files": ("第12课-梯形面积.md", MD.encode("utf8"), "text/markdown")},
    )
    assert imported.status_code == 200 and imported.json()["imported"] == 1, imported.text
    lid = imported.json()["items"][0]["lessonId"]
    with legacy.SessionLocal() as db:
        lesson = db.get(legacy.TeachingLesson, lid)
        page_texts = stage_pages(lesson, 3)
    assert len(page_texts) == 1

    base_params = {
        "title": "例1",
        "problem": page_texts[0].split("\n【答案】")[0],
        "steps": ["第一步找底和高", "第二步代入公式"],
        "answer": "30平方厘米",
        "stepFigures": [
            {"type": "uploaded_image", "data_url": BIG_IMG_1, "alt": "图0"},
            {"type": "uploaded_image", "data_url": BIG_IMG_2, "alt": "图1"},
            {"type": "uploaded_image", "data_url": BIG_IMG_3, "alt": "图2"},
        ],
    }

    # 1. Prepared import + approve
    imp = client.post(
        f"/teacher/weekend/lessons/{lid}/courseware/prepared-import",
        headers=th,
        json={
            "dryRun": False,
            "replaceExisting": True,
            "pages": [{
                "stageNo": 3,
                "page": 0,
                "expectedPageText": page_texts[0],
                "kind": "steps",
                "writtenTask": False,
                "params": base_params,
            }],
        },
    )
    assert imp.status_code == 200, imp.text

    ap = client.post(
        f"/teacher/weekend/lessons/{lid}/courseware/approve",
        headers=th,
        json={"stageNo": 3, "page": 0},
    )
    assert ap.status_code == 200, ap.text
    ap_item = ap.json()["items"][0]
    assert ap_item["status"] == "approved"
    assert len(ap_item["params"]["stepFigures"]) == 3
    # Approved snapshot omits duplicate stepFigures in HTTP response while keeping metadata/answer
    assert ap_item["approved"]["answer"] == "30平方厘米"
    assert "stepFigures" not in ap_item["approved"]

    # 2. Save a text edit (same images -> previousDraft, approved, params all share 3 images in DB!)
    edited_params = {**base_params, "title": "例1（修订）"}
    sv = client.put(
        f"/teacher/weekend/lessons/{lid}/courseware",
        headers=th,
        json={"stageNo": 3, "page": 0, "kind": "steps", "params": edited_params, "writtenTask": False},
    )
    assert sv.status_code == 200, sv.text
    sv_item = sv.json()["items"][0]
    assert sv_item["previousDraft"]["hasPrevious"] is True
    assert "params" not in sv_item["previousDraft"]

    # Check raw DB storage: each 4000-char image must appear ONCE (not 3 times!)
    cw_table = register_courseware_table(legacy)
    with legacy.SessionLocal() as db:
        row = db.execute(select(cw_table).where(cw_table.c.lesson_id == lid)).first()
        assert row is not None
        raw = row.params_json
        assert raw.count("A" * 4000) == 1, "BIG_IMG_1 should be deduplicated in DB storage"
        assert raw.count("B" * 4000) == 1, "BIG_IMG_2 should be deduplicated in DB storage"
        assert raw.count("C" * 4000) == 1, "BIG_IMG_3 should be deduplicated in DB storage"
        hydrated = items_of(row)
        assert hydrated[0]["params"]["stepFigures"][0]["data_url"] == BIG_IMG_1
        assert hydrated[0]["approved"]["stepFigures"][0]["data_url"] == BIG_IMG_1
        assert hydrated[0]["previousDraft"]["params"]["stepFigures"][0]["data_url"] == BIG_IMG_1

    # 3. Restore previous still restores full images
    restored = client.post(
        f"/teacher/weekend/lessons/{lid}/courseware/restore-previous",
        headers=th,
        json={"stageNo": 3, "page": 0},
    )
    assert restored.status_code == 200, restored.text
    r_item = restored.json()["items"][0]
    assert r_item["params"]["title"] == "例1"
    assert r_item["params"]["stepFigures"][2]["data_url"] == BIG_IMG_3

    # 4. Frontend JS exposes pending/disabled guards for both save and approve
    page_resp = client.get("/v1/weekend-plan", headers=th)
    assert page_resp.status_code == 200
    assert "正在保存…" in page_resp.text
    assert "审核中…" in page_resp.text
    print("OK")
''')


def test_harden_postgres_engine_applies_keepalives_and_recycle():
    from changying.compat.legacy import _harden_postgres_engine

    calls: list[dict] = []
    disposed = []
    configured = []

    class FakeOldEngine:
        def dispose(self):
            disposed.append(True)

    class FakeSessionLocal:
        def configure(self, **kwargs):
            configured.append(kwargs)

    fake_new_engine = object()

    def fake_create_engine(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return fake_new_engine

    pg_impl = SimpleNamespace(
        raw_url="postgresql+psycopg://user:pass@host/db",
        engine=FakeOldEngine(),
        SessionLocal=FakeSessionLocal(),
        create_engine=fake_create_engine,
    )
    _harden_postgres_engine(pg_impl)
    assert len(calls) == 1
    assert calls[0]["pool_pre_ping"] is True
    assert calls[0]["pool_recycle"] == 240
    assert calls[0]["pool_size"] == 3
    assert calls[0]["max_overflow"] == 5
    assert calls[0]["connect_args"]["keepalives"] == 1
    assert pg_impl.engine is fake_new_engine
    assert configured == [{"bind": fake_new_engine}]
    assert disposed == [True]

    # SQLite must remain untouched
    sqlite_calls: list[dict] = []
    sqlite_impl = SimpleNamespace(
        raw_url="sqlite:///local.db",
        engine=FakeOldEngine(),
        SessionLocal=FakeSessionLocal(),
        create_engine=lambda url, **kw: sqlite_calls.append(kw),
    )
    _harden_postgres_engine(sqlite_impl)
    assert sqlite_calls == []
