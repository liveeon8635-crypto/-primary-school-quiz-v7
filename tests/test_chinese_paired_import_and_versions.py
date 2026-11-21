"""Tests for paired teacher+student import, bindings/errata, and versioned written annotations."""

from __future__ import annotations

import importlib.util
import io
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("paired_import_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = helpers
_spec.loader.exec_module(helpers)


def _make_docx(paragraphs: list[str], *, image_bytes: bytes | None = None) -> bytes:
    buf = io.BytesIO()
    body = "".join(
        f'<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:r><w:t>{p}</w:t></w:r></w:p>'
        for p in paragraphs
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", xml.encode("utf-8"))
        if image_bytes is not None:
            zf.writestr("word/media/image1.png", image_bytes)
    return buf.getvalue()


def test_real_lesson12_docx_inventory_if_present():
    from changying.services.weekend_paired_import import pair_teacher_and_student_docs, sha256_hex

    t_path = Path(r"C:\Users\14228\Desktop\语文12次.docx")
    s_path = Path(r"C:\Users\14228\Desktop\语文12次学生.docx")
    if not (t_path.exists() and s_path.exists()):
        return
    t_raw = t_path.read_bytes()
    s_raw = s_path.read_bytes()
    t_hash_before = sha256_hex(t_raw)
    s_hash_before = sha256_hex(s_raw)
    paired = pair_teacher_and_student_docs(t_raw, t_path.name, s_raw, s_path.name)
    assert paired["teacherMediaCount"] == 4
    assert paired["studentMediaCount"] == 4
    assert any("母亲的那盏灯" in (b["payload"].get("text") or "") for b in paired["bindings"])
    assert any("父亲的泥脚" in (b["payload"].get("text") or "") for b in paired["bindings"])
    assert sha256_hex(t_path.read_bytes()) == t_hash_before
    assert sha256_hex(s_path.read_bytes()) == s_hash_before


def test_paired_import_bindings_errata_and_versioned_annotations(tmp_path):
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 32 + b"IEND\xaeB`\x82"
    t_docx = _make_docx(
        [
            "第12课：阅读——舐犊情深",
            "《母亲的那盏灯》\n每当夜幕降临，我家客厅那盏暖黄的台灯总会准时亮起。她微驼着背，粗糙的手指捏着针线。",
            "1. 读文中画横线的句子，体会母亲怎样的情感？",
            "参考答案：写出了母亲对“我”无私而深沉的爱。",
        ],
        image_bytes=png,
    )
    s_docx = _make_docx(
        [
            "第12课：阅读——舐犊情深",
            "《母亲的那盏灯》\n每当夜幕降临，我家客厅那盏暖黄的台灯总会准时亮起。她微驼着背，粗糙的手指捏着针线。",
            "1. 读文中画横线的句子，体会母亲怎样的情感？",
        ],
        image_bytes=png,
    )
    s_docx_plain = _make_docx(["第12课：阅读——舐犊情深", "《母亲的那盏灯》\n每当夜幕降临，我家客厅那盏暖黄的台灯总会准时亮起。"])
    script = (
        helpers.COMMON
        + f"T_DOCX = {t_docx!r}\nS_DOCX = {s_docx!r}\nPLAIN_DOCX = {s_docx_plain!r}\nPNG = {png!r}\n"
        + r"""
with TestClient(app) as client:
    th, sh, student, school = setup(client)
    __import__("sys").path.insert(0, "tests")
    from test_chinese_readiness import prepare_reviewed_lesson
    with legacy.SessionLocal() as db:
        tid = db.scalar(select(legacy.User.id).where(legacy.User.username == "teacher1"))
        cls = db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id == school))
        cls.teacher_id = tid
        link = db.scalar(select(legacy.ClassStudent).where(legacy.ClassStudent.student_id == student))
        if link:
            link.class_id = cls.id
        else:
            db.add(legacy.ClassStudent(class_id=cls.id, student_id=student))
        cls1_id = cls.id
        cls2 = legacy.SchoolClass(school_id=school, name="二班", grade=5, teacher_id=tid)
        db.add(cls2)
        db.flush()
        cls2_id = cls2.id
        stu2 = legacy.User(school_id=school, username="student2", name="学生2", role="student", password_hash="x")
        db.add(stu2)
        db.flush()
        db.add(legacy.ClassStudent(class_id=cls2_id, student_id=stu2.id))
        db.commit()
    imp = client.post(
        "/teacher/weekend/lessons/import",
        headers=th,
        data={"subject": "语文", "lessonNo": "12", "courseType": "reading"},
        files={"file": ("reading.docx", PLAIN_DOCX, "application/octet-stream")},
    )
    assert imp.status_code == 200, imp.text
    lid = imp.json()["lessonId"]
    prepare_reviewed_lesson(client, th, legacy, lid)
    # 1. Paired import
    r = client.post(
        f"/teacher/weekend/lessons/{lid}/paired-import",
        headers=th,
        files={
            "teacherFile": ("teacher.docx", T_DOCX, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            "studentFile": ("student.docx", S_DOCX, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["pair"]["teacherMediaCount"] == 1
    assert data["pair"]["studentMediaCount"] == 1
    img_b = next(b for b in data["bindings"] if b["itemType"] == "image")
    q_b = next(b for b in data["bindings"] if b["itemType"] == "question")
    bad = client.put(
        f"/teacher/weekend/lessons/{lid}/bindings/{img_b['id']}",
        headers=th,
        json={"status": "confirmed", "expectedRevision": img_b["revision"]},
    )
    assert bad.status_code == 400, bad.text
    ok = client.put(
        f"/teacher/weekend/lessons/{lid}/bindings/{img_b['id']}",
        headers=th,
        json={"status": "confirmed", "targetKey": q_b["itemKey"], "expectedRevision": img_b["revision"]},
    )
    assert ok.status_code == 200 and ok.json()["binding"]["status"] == "confirmed", ok.text
    stale = client.put(
        f"/teacher/weekend/lessons/{lid}/bindings/{img_b['id']}",
        headers=th,
        json={"stageNo": 2, "expectedRevision": img_b["revision"]},
    )
    assert stale.status_code == 409, stale.text
    edit_q = client.put(
        f"/teacher/weekend/lessons/{lid}/bindings/{q_b['id']}",
        headers=th,
        json={"text": "1. 修订后的题干", "expectedRevision": q_b["revision"]},
    )
    assert edit_q.status_code == 200 and edit_q.json()["binding"]["status"] == "pending", edit_q.text
    errata = client.get(f"/teacher/weekend/lessons/{lid}/paired-import", headers=th).json()["errata"]
    assert len(errata) >= 2

    # 2. Dual-class frozen snapshot & independent sessions
    s1 = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": lid, "classId": cls1_id}).json()["id"]
    s2 = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": lid, "classId": cls2_id}).json()["id"]
    client.post(f"/teacher/weekend/sessions/{s1}/start", headers=th)
    client.post(f"/teacher/weekend/sessions/{s2}/start", headers=th)
    client.post(f"/teacher/weekend/sessions/{s1}/goto", headers=th, json={"stage": 5})
    assert client.get(f"/teacher/weekend/sessions/{s2}", headers=th).json()["currentStage"] == 1

    # 3. Versioned multi-photo student submission & teacher annotation isolation
    sid = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": lid, "classId": cls1_id}).json()["id"]
    wq = client.post(
        f"/teacher/weekend/sessions/{sid}/written/questions",
        headers=th,
        json={"stem": "1. 体会母亲怎样的情感？", "reference": "无私深沉的爱", "hints": ["找细节", "看动作", "悟情感"]},
    )
    assert wq.status_code == 200, wq.text
    wid = wq.json()["id"]
    client.post(f"/teacher/weekend/sessions/{sid}/start", headers=th)
    client.post(f"/teacher/weekend/sessions/{sid}/goto", headers=th, json={"stage": 5})
    from changying.services.weekend_answers import open_practice_question
    with legacy.SessionLocal() as db:
        s_row = db.execute(select(legacy.Base.metadata.tables["weekend_sessions"]).where(
            legacy.Base.metadata.tables["weekend_sessions"].c.id == sid
        )).first()
        open_practice_question(legacy, db, s_row, 1)
        db.commit()
    sub1 = client.post(
        f"/student/weekend/sessions/{sid}/written/{wid}",
        headers=sh,
        data={"text": "第一版答案", "revision": "0", "orientation": "6"},
        files=[("photos", ("p1.png", PNG, "image/png")), ("photos", ("p2.png", PNG, "image/png"))],
    )
    assert sub1.status_code == 200, sub1.text
    v1_id = sub1.json()["versionId"]
    ann = client.post(
        f"/teacher/weekend/sessions/{sid}/written/{wid}/students/{student}/annotate",
        headers=th,
        json={
            "submissionVersionId": v1_id,
            "verdict": "retake",
            "comment": "字迹模糊请重拍",
            "shapes": [{"kind": "circle", "x": 10, "y": 20, "w": 50, "h": 50, "text": "这里重写"}],
        },
    )
    assert ann.status_code == 200, ann.text
    sub2 = client.post(
        f"/student/weekend/sessions/{sid}/written/{wid}",
        headers=sh,
        data={"text": "第二版清晰答案", "revision": str(sub1.json()["revision"]), "orientation": "1"},
        files=[("photos", ("p3.png", PNG, "image/png"))],
    )
    assert sub2.status_code == 200, sub2.text
    vers = client.get(f"/student/weekend/sessions/{sid}/written/{wid}/versions", headers=sh).json()["versions"]
    assert len(vers) == 2
    assert len(vers[0]["photos"]) == 2 and len(vers[0]["annotations"]) == 1
    assert len(vers[1]["photos"]) == 1 and len(vers[1]["annotations"]) == 0
    print("OK")
"""
    )
    helpers.run_isolated(tmp_path, script)
