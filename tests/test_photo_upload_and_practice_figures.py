"""Tests for resilient student photo upload and automatic course-figure matching on targeted practice."""
from __future__ import annotations

import base64
import importlib.util
import io
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("photo_practice_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_normalize_practice_figure_converts_png_to_jpeg():
    from changying.web.weekend_report_views import _normalize_practice_figure

    buf = io.BytesIO()
    Image.new("RGB", (320, 180), (245, 250, 255)).save(buf, format="PNG")
    png_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    out = _normalize_practice_figure({"type": "uploaded_image", "data_url": png_url, "alt": "第21题原图"})
    assert out["type"] == "uploaded_image"
    assert out["data_url"].startswith("data:image/jpeg;base64,")
    assert len(out["data_url"]) <= 700_000


def test_student_photo_upload_handles_trailing_bytes_and_oversized_image(tmp_path):
    script = helpers.COMMON + r'''
import io
from datetime import datetime
from PIL import Image
from changying.web.weekend_views import register_weekend_tables
from changying.web.weekend_written import register_written_tables

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    md = "# 第12课：梯形面积\n## 本节目标\n掌握梯形面积。\n## 教学流程\n讲练结合。\n## 课后练习\n1. 求面积。\n"
    imp = client.post(
        "/teacher/weekend/lessons/import/markdown",
        headers=th,
        data={"subject": "数学"},
        files={"files": ("第12课.md", md.encode("utf-8"), "text/markdown")},
    )
    assert imp.status_code == 200, imp.text
    lid = imp.json()["items"][0]["lessonId"]
    with legacy.SessionLocal() as db:
        cls = db.query(legacy.SchoolClass).first()
        cid = cls.id
    opened = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": lid, "classId": cid, "requireReady": False})
    assert opened.status_code == 200, opened.text
    sess_id = opened.json().get("sessionId") or opened.json().get("id")
    qadd = client.post(
        f"/teacher/weekend/sessions/{sess_id}/written/questions",
        headers=th,
        json={"stem": "计算下图中阴影部分面积。", "reference": "120", "hints": []},
    )
    assert qadd.status_code == 200, qadd.text
    qid = qadd.json()["id"]
    started = client.post(f"/teacher/weekend/sessions/{sess_id}/start", headers=th)
    assert started.status_code == 200, started.text
    goto_res = client.post(f"/teacher/weekend/sessions/{sess_id}/goto", headers=th, json={"stage": 4})
    assert goto_res.status_code == 200, goto_res.text
    pq_res = client.post(f"/teacher/weekend/sessions/{sess_id}/practice-question", headers=th, json={"question": 1})
    assert pq_res.status_code == 200, pq_res.text

    # 1) JPEG with trailing EXIF/padding bytes after EOI (\xff\xd9)
    jbuf = io.BytesIO()
    Image.new("RGB", (600, 400), (255, 250, 240)).save(jbuf, format="JPEG")
    padded_jpg = jbuf.getvalue() + b"\x00\x00EXTRA_PADDING"
    r1 = client.post(
        f"/student/weekend/sessions/{sess_id}/written/{qid}",
        headers=sh,
        data={"text": "见附图", "revision": "0", "removePhoto": "false"},
        files={"photo": ("phone.jpg", padded_jpg, "image/jpeg")},
    )
    assert r1.status_code == 200, r1.text

    # 2) Oversized (>3MB, <8MB) valid PNG auto-compressed to <=3MB JPEG
    big_im = Image.effect_noise((1800, 1800), 64.0).convert("RGB")
    pbuf = io.BytesIO()
    big_im.save(pbuf, format="PNG")
    big_png = pbuf.getvalue()
    assert len(big_png) > 3 * 1024 * 1024
    r2 = client.post(
        f"/student/weekend/sessions/{sess_id}/written/{qid}",
        headers=sh,
        data={"text": "高清大图重提", "revision": "1", "removePhoto": "false"},
        files={"photo": ("big.png", big_png, "image/png")},
    )
    assert r2.status_code == 200, r2.text
    print("OK")
'''
    helpers.run_isolated(tmp_path, script)
