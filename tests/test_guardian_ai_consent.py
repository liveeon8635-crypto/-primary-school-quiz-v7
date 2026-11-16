"""Security & adversarial tests for P0-2 guardian AI consent and default-deny AI egress guard."""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

COMMERCIAL_KEY = "guardian-consent-commercial-key-0123456789"
PASSWORD = "Teacher1234"
CHANGED = "Teacher5678"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("consent") / "app.sqlite3"
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path}")
    os.environ["ENABLE_DEMO_SEED"] = "0"
    os.environ.setdefault("JWT_SECRET", "guardian-consent-jwt-secret-0123456789abcdef")
    import app as app_module
    import app_v924 as legacy

    legacy.COMMERCIAL_ADMIN_KEY = COMMERCIAL_KEY
    with TestClient(app_module.app) as c:
        yield c


def _login_headers(client: TestClient, username: str, password: str) -> dict[str, str]:
    data = client.post("/login", json={"username": username, "password": password}).json()
    headers = {"Authorization": "Bearer " + data["token"]}
    if data.get("mustChangePassword"):
        assert client.post(
            "/change-password",
            json={"current_password": password, "new_password": CHANGED},
            headers=headers,
        ).status_code == 200
        data = client.post("/login", json={"username": username, "password": CHANGED}).json()
        headers = {"Authorization": "Bearer " + data["token"]}
    return headers


def _setup_personal_family(client: TestClient):
    tag = uuid.uuid4().hex[:8]
    t_code = f"t-{tag}"
    r = client.post(
        "/operator/schools/create",
        headers={"X-Commercial-Key": COMMERCIAL_KEY},
        json={
            "school_name": f"监护授权工作室{tag}",
            "school_code": t_code,
            "admin_name": "张老师",
            "admin_username": t_code,
            "admin_password": PASSWORD,
            "individual": True,
        },
    )
    assert r.status_code == 200, r.text[:300]
    t_headers = _login_headers(client, t_code, PASSWORD)

    s_user = f"stu-{tag}"
    sr = client.post(
        "/teacher/students",
        headers=t_headers,
        json={"name": "小宇", "username": s_user, "password": PASSWORD, "grade": 5},
    )
    assert sr.status_code == 200, sr.text[:300]
    student_id = sr.json()["id"]

    p_user = f"par-{tag}"
    pr = client.post(
        "/admin/users",
        headers=t_headers,
        json={"name": "宇妈妈", "username": p_user, "password": PASSWORD, "role": "parent"},
    )
    assert pr.status_code == 200, pr.text[:300]
    parent_id = pr.json()["id"]
    br = client.post(
        f"/teacher/students/{student_id}/parent",
        headers=t_headers,
        json={"parent_id": parent_id},
    )
    assert br.status_code == 200, br.text[:300]
    p_headers = _login_headers(client, p_user, PASSWORD)
    s_headers = _login_headers(client, s_user, PASSWORD)

    cfg = client.put(
        "/teacher/ai-config",
        headers=t_headers,
        json={
            "provider": "openai_compatible",
            "base_url": "https://api.example.com/v1",
            "model": "deepseek-chat",
            "api_key": "sk-test-secret-key-1234567890",
            "enabled": True,
            "allow_student_data": True,
        },
    )
    assert cfg.status_code == 200, cfg.text[:300]
    return t_headers, p_headers, s_headers, student_id


def test_compliance_gate_blocks_personal_egress_by_default(client, monkeypatch):
    monkeypatch.delenv("STUDENT_AI_COMPLIANCE_APPROVED", raising=False)
    t_headers, p_headers, _, sid = _setup_personal_family(client)
    tok = client.post(f"/teacher/students/{sid}/ai-consent/token", headers=t_headers, json={}).json()["token"]
    assert client.post("/parent/ai-consent/confirm", headers=p_headers, json={"token": tok}).status_code == 200

    import app_v924 as legacy
    from changying.services.guardian_consent import require_student_ai_authorized

    called = {"http": 0}
    monkeypatch.setattr(legacy.requests, "post", lambda *a, **kw: called.__setitem__("http", called["http"] + 1))
    monkeypatch.setattr(legacy, "_validate_ai_base_url", lambda base, runtime=False: base)

    with legacy.SessionLocal() as db:
        stu = db.get(legacy.User, sid)
        with pytest.raises(Exception) as exc:
            legacy._ai_call(db, stu, "homework_help_guide", "hello", student_ids=[sid])
        assert getattr(exc.value, "status_code", None) == 403
        assert "合规" in str(getattr(exc.value, "detail", ""))
        with pytest.raises(Exception) as exc2:
            require_student_ai_authorized(db, legacy, school_id=stu.school_id, feature="weekend_report", student_ids=[sid])
        assert getattr(exc2.value, "status_code", None) == 403
    assert called["http"] == 0


def test_default_deny_unknown_feature_missing_student_ids_and_teacher_image_upload(client, monkeypatch):
    monkeypatch.setenv("STUDENT_AI_COMPLIANCE_APPROVED", "1")
    monkeypatch.setenv("HOMEWORK_VISION_PROVIDER", "openai_compatible")
    monkeypatch.setenv("HOMEWORK_VISION_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("HOMEWORK_VISION_MODEL", "vision-test-model")
    monkeypatch.setenv("HOMEWORK_VISION_API_KEY", "sk-vision-test-key-123456")

    t_headers, _, _, sid = _setup_personal_family(client)
    other_t_headers, _, _, other_sid = _setup_personal_family(client)

    # Cross-workspace isolation: Teacher B cannot view/create token/submit proof/revoke Teacher A's student
    assert client.get(f"/teacher/students/{sid}/ai-consent", headers=other_t_headers).status_code == 404
    assert client.post(f"/teacher/students/{sid}/ai-consent/token", headers=other_t_headers, json={}).status_code == 404
    assert client.post(f"/teacher/students/{sid}/ai-consent/revoke", headers=other_t_headers, json={}).status_code == 404

    import app_v924 as legacy
    from changying.services.homework_vision import recognize_image

    http_calls = {"count": 0}

    class _FakeResp:
        ok = True
        status_code = 200
        def json(self):
            return {"choices": [{"message": {"content": "连接成功"}}], "usage": {}}

    def _fake_post(*args, **kwargs):
        http_calls["count"] += 1
        return _FakeResp()

    monkeypatch.setattr(legacy.requests, "post", _fake_post)
    monkeypatch.setattr("changying.services.homework_vision.requests.post", _fake_post)
    monkeypatch.setattr(legacy, "_validate_ai_base_url", lambda base, runtime=False: base)

    with legacy.SessionLocal() as db:
        stu = db.get(legacy.User, sid)
        teacher = db.scalar(legacy.select(legacy.User).where(legacy.User.school_id == stu.school_id, legacy.User.role == "teacher"))

        # Teaching-only allowlisted feature (no student_ids, no images) is allowed
        out = legacy._ai_call(db, teacher, "connection_test", "ping")
        assert out == "连接成功"
        assert http_calls["count"] == 1

        # Unknown / unregistered feature is default-denied (0 HTTP calls)
        http_calls["count"] = 0
        with pytest.raises(Exception) as exc_unk:
            legacy._ai_call(db, teacher, "unknown_custom_feature", "hello")
        assert getattr(exc_unk.value, "status_code", None) == 403

        # Student-data feature with missing student_ids is default-denied (0 HTTP calls)
        with pytest.raises(Exception) as exc_missing:
            legacy._ai_call(db, teacher, "weekend_report", "report without student_ids")
        assert getattr(exc_missing.value, "status_code", None) == 403

        # Teacher uploading an image containing student info MUST NOT skip guardian consent
        tiny_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        with pytest.raises(Exception) as exc_img:
            recognize_image(legacy, db, teacher, tiny_png, feature="homework_parse_vision")
        assert getattr(exc_img.value, "status_code", None) == 403
    assert http_calls["count"] == 0


def test_proof_consent_requires_controlled_verification_before_becoming_active(client, monkeypatch):
    monkeypatch.setenv("STUDENT_AI_COMPLIANCE_APPROVED", "1")
    t_headers, p_headers, _, sid = _setup_personal_family(client)
    _, other_p_headers, _, _ = _setup_personal_family(client)

    proof = client.post(
        f"/teacher/students/{sid}/ai-consent/proof",
        headers=t_headers,
        json={"verificationMethod": "written_proof", "proofDigest": "SIGNED-2026-001", "scope": "student_ai_all"},
    )
    assert proof.status_code == 200
    body = proof.json()
    assert body["status"] == "pending_verification"
    cid = body["consentId"]

    import app_v924 as legacy

    http_calls = {"count": 0}
    monkeypatch.setattr(legacy.requests, "post", lambda *a, **kw: http_calls.__setitem__("count", http_calls["count"] + 1))
    monkeypatch.setattr(legacy, "_validate_ai_base_url", lambda base, runtime=False: base)

    # Pending proof MUST NOT allow AI egress
    with legacy.SessionLocal() as db:
        stu = db.get(legacy.User, sid)
        with pytest.raises(Exception) as exc:
            legacy._ai_call(db, stu, "homework_help_guide", "hello", student_ids=[sid])
        assert getattr(exc.value, "status_code", None) == 403
    assert http_calls["count"] == 0

    # Teacher cannot self-verify their own proof
    assert client.post(f"/guardian-consents/{cid}/verify", headers=t_headers, json={"approved": True}).status_code == 403
    # Unlinked parent cannot verify
    assert client.post(f"/guardian-consents/{cid}/verify", headers=other_p_headers, json={"approved": True}).status_code == 403
    # Linked parent verifies -> becomes active
    ok = client.post(f"/guardian-consents/{cid}/verify", headers=p_headers, json={"approved": True})
    assert ok.status_code == 200 and ok.json()["status"] == "active"


def test_token_security_replay_expiry_cross_student_and_unlinked_parent(client, monkeypatch):
    monkeypatch.setenv("STUDENT_AI_COMPLIANCE_APPROVED", "1")
    t_headers, p_headers, s_headers, sid = _setup_personal_family(client)
    _, other_p_headers, _, other_sid = _setup_personal_family(client)

    res = client.post(
        f"/teacher/students/{sid}/ai-consent/token",
        headers=t_headers,
        json={"scope": "homework_help", "policyVersion": "v1.2", "validDays": 90},
    )
    assert res.status_code == 200
    raw_token = res.json()["token"]

    import app_v924 as legacy
    with legacy.SessionLocal() as db:
        rows = db.execute(text("SELECT token_hash FROM guardian_consent_tokens")).fetchall()
        assert all(raw_token not in str(r[0]) for r in rows)

    assert client.post("/parent/ai-consent/confirm", headers=s_headers, json={"token": raw_token}).status_code == 403
    assert client.post("/parent/ai-consent/confirm", headers=other_p_headers, json={"token": raw_token}).status_code == 403
    assert client.post(
        "/parent/ai-consent/confirm",
        headers=p_headers,
        json={"token": raw_token, "studentId": other_sid},
    ).status_code == 403

    ok = client.post("/parent/ai-consent/confirm", headers=p_headers, json={"token": raw_token, "studentId": sid})
    assert ok.status_code == 200
    body = ok.json()
    assert body["status"] == "active"
    assert body["validUntil"] != body["retentionUntil"]

    assert client.post("/parent/ai-consent/confirm", headers=p_headers, json={"token": raw_token}).status_code == 409

    exp_tok = client.post(f"/teacher/students/{sid}/ai-consent/token", headers=t_headers, json={}).json()["token"]
    with legacy.SessionLocal() as db:
        db.execute(
            text("UPDATE guardian_consent_tokens SET expires_at = :past"),
            {"past": datetime.utcnow() - timedelta(hours=1)},
        )
        db.commit()
    assert client.post("/parent/ai-consent/confirm", headers=p_headers, json={"token": exp_tok}).status_code == 409


def test_revocation_blocks_all_four_modules_and_queued_retries_with_zero_http(client, monkeypatch):
    monkeypatch.setenv("STUDENT_AI_COMPLIANCE_APPROVED", "1")
    monkeypatch.setenv("HOMEWORK_VISION_PROVIDER", "openai_compatible")
    monkeypatch.setenv("HOMEWORK_VISION_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("HOMEWORK_VISION_MODEL", "vision-test-model")
    monkeypatch.setenv("HOMEWORK_VISION_API_KEY", "sk-vision-test-key-123456")
    t_headers, p_headers, _, sid = _setup_personal_family(client)

    tok = client.post(f"/teacher/students/{sid}/ai-consent/token", headers=t_headers, json={}).json()["token"]
    assert client.post("/parent/ai-consent/confirm", headers=p_headers, json={"token": tok}).status_code == 200

    import app_v924 as legacy
    from changying.services.homework_vision import recognize_image

    http_calls = {"count": 0}

    class _FakeResp:
        ok = True
        status_code = 200
        def json(self):
            return {"choices": [{"message": {"content": '{"text": "1+1=2", "confidence": 0.9}'}}], "usage": {}}

    def _fake_post(*args, **kwargs):
        http_calls["count"] += 1
        return _FakeResp()

    monkeypatch.setattr(legacy.requests, "post", _fake_post)
    monkeypatch.setattr("changying.services.homework_vision.requests.post", _fake_post)
    monkeypatch.setattr(legacy, "_validate_ai_base_url", lambda base, runtime=False: base)

    with legacy.SessionLocal() as db:
        stu = db.get(legacy.User, sid)
        for feat in ("homework_help_guide", "weekend_report", "knowledge_map_student_ai", "exam_prep_student_ai"):
            legacy._ai_call(db, stu, feat, "prompt", student_ids=[sid])
        tiny_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        recognize_image(legacy, db, stu, tiny_png, feature="homework_help_vision")
    assert http_calls["count"] == 5

    rev = client.post(f"/parent/children/{sid}/ai-consent/revoke", headers=p_headers, json={"reason": "parent_stop"})
    assert rev.status_code == 200

    http_calls["count"] = 0
    with legacy.SessionLocal() as db:
        stu = db.get(legacy.User, sid)
        for feat in ("homework_help_guide", "weekend_report", "knowledge_map_student_ai", "exam_prep_student_ai"):
            with pytest.raises(Exception) as exc:
                legacy._ai_call(db, stu, feat, "queued-retry-prompt", student_ids=[sid])
            assert getattr(exc.value, "status_code", None) == 403
        with pytest.raises(Exception) as exc_v:
            recognize_image(legacy, db, stu, b"\x89PNG\r\n\x1a\n" + b"\x00" * 32, feature="homework_help_vision")
        assert getattr(exc_v.value, "status_code", None) == 403
    assert http_calls["count"] == 0

    info = client.get(f"/teacher/students/{sid}/ai-consent", headers=t_headers).json()
    actions = [a["action"] for a in info["audits"]]
    assert "consent.grant" in actions
    assert "consent.revoke" in actions
    assert "egress.blocked" in actions
    serialized = str(info)
    assert "sk-test-secret-key" not in serialized
    assert "sk-vision-test-key" not in serialized


def test_migration_tables_exist_and_isolated_rollback_preserves_legacy_tables(client, tmp_path):
    import app_v924 as legacy
    from changying.services.guardian_consent import CONSENT_METADATA, register_guardian_consent_tables

    insp = inspect(legacy.engine)
    names = set(insp.get_table_names())
    new_tables = ("guardian_ai_consents", "guardian_consent_tokens", "guardian_consent_audit_logs")
    assert set(new_tables).issubset(names)
    assert {"users", "parent_students", "point_ledger"}.issubset(names)
    # Must NOT pollute Base.metadata so prelaunch_data_cleanup remains untouched
    assert not set(new_tables).intersection(set(legacy.Base.metadata.tables))

    iso_engine = create_engine(f"sqlite:///{tmp_path / 'rollback.sqlite3'}")
    legacy.Base.metadata.create_all(bind=iso_engine)
    tables = register_guardian_consent_tables()
    CONSENT_METADATA.create_all(bind=iso_engine)
    assert set(new_tables).issubset(set(inspect(iso_engine).get_table_names()))
    for tname in ("audits", "tokens", "consents"):
        tables[tname].drop(bind=iso_engine, checkfirst=True)
    remaining = set(inspect(iso_engine).get_table_names())
    assert not set(new_tables).intersection(remaining)
    assert {"users", "parent_students", "point_ledger"}.issubset(remaining)


def test_product_assistant_v3_consent_and_image_boundaries(client, monkeypatch):
    import base64
    from types import SimpleNamespace
    import app_v924 as legacy

    t_headers, p_headers, s_headers, student_id = _setup_personal_family(client)
    http_calls = []

    def fake_post(url, *args, **kwargs):
        http_calls.append(url)
        return SimpleNamespace(
            ok=True,
            status_code=200,
            json=lambda: {"choices": [{"message": {"content": "AI回复内容"}}]},
        )

    monkeypatch.setattr(legacy.requests, "post", fake_post)
    monkeypatch.setattr(legacy, "_validate_ai_base_url", lambda base, runtime=False: base)
    monkeypatch.delenv("STUDENT_AI_COMPLIANCE_APPROVED", raising=False)

    # 1. Student unauthorized & compliance closed -> 0 HTTP calls
    r1 = client.post("/v1/product-assistant/query", headers=s_headers, json={"question": "这道分数题怎么理解？"})
    assert r1.status_code == 200
    assert len(http_calls) == 0

    # 2. Teacher pure product guidance (no image, no child_id) -> allowed even without student consent
    r_guide = client.post("/v1/product-assistant/query", headers=t_headers, json={"question": "怎么创建班级？"})
    assert r_guide.status_code == 200
    assert len(http_calls) == 1

    # 3. Teacher with image and no child_id -> default-denied (0 new HTTP calls)
    raw_png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"img").decode("ascii")
    img_payload = {
        "question": "帮我看这张图",
        "image_name": "shot.png",
        "image_type": "image/png",
        "image_size": len(b"\x89PNG\r\n\x1a\n" + b"img"),
        "image_data": raw_png,
    }
    r_t_img = client.post("/v1/product-assistant/query", headers=t_headers, json=img_payload)
    assert r_t_img.status_code == 200
    assert r_t_img.json()["ok"] is False
    assert len(http_calls) == 1

    # 4. Parent with wrong/unlinked child_id -> 403, 0 new HTTP calls
    r_p_bad = client.post(
        "/v1/product-assistant/query",
        headers=p_headers,
        json={"question": "孩子最近学得怎么样？", "child_id": 999999},
    )
    assert r_p_bad.status_code == 403
    assert len(http_calls) == 1

    # 5. Parent unauthorized (consent not yet active) -> 0 new HTTP calls
    monkeypatch.setenv("STUDENT_AI_COMPLIANCE_APPROVED", "1")
    r_p_unauth = client.post(
        "/v1/product-assistant/query",
        headers=p_headers,
        json={"question": "孩子最近学得怎么样？", "child_id": student_id},
    )
    assert r_p_unauth.status_code == 200
    assert len(http_calls) == 1

    # 6. Activate parent consent -> student text + student image both succeed
    tok = client.post(f"/teacher/students/{student_id}/ai-consent/token", headers=t_headers, json={}).json()["token"]
    assert client.post("/parent/ai-consent/confirm", headers=p_headers, json={"token": tok, "student_id": student_id}).status_code == 200

    r_s_auth = client.post("/v1/product-assistant/query", headers=s_headers, json={"question": "这道分数题怎么理解？"})
    assert r_s_auth.status_code == 200
    assert len(http_calls) == 2

    r_s_img = client.post("/v1/product-assistant/query", headers=s_headers, json=img_payload)
    assert r_s_img.status_code == 200
    assert len(http_calls) == 3


def test_institutional_allow_student_data_false_blocks_all_features_and_images(client, monkeypatch):
    from types import SimpleNamespace
    from fastapi import HTTPException
    import app_v924 as legacy

    tag = uuid.uuid4().hex[:8]
    t_code = f"inst-{tag}"
    assert client.post(
        "/operator/schools/create",
        headers={"X-Commercial-Key": COMMERCIAL_KEY},
        json={
            "school_name": f"机构学校{tag}",
            "school_code": t_code,
            "admin_name": "王老师",
            "admin_username": t_code,
            "admin_password": PASSWORD,
            "individual": False,
        },
    ).status_code == 200
    t_headers = _login_headers(client, t_code, PASSWORD)
    tr = client.post(
        "/admin/users",
        headers=t_headers,
        json={"name": "机构教师", "username": f"it-{tag}", "password": PASSWORD, "role": "teacher"},
    )
    assert tr.status_code == 200, tr.text[:300]
    teach_id = tr.json()["id"]
    with legacy.SessionLocal() as db:
        t_user = db.get(legacy.User, teach_id)
        cls = legacy.SchoolClass(school_id=t_user.school_id, name="四年级1班", grade=4, teacher_id=teach_id)
        db.add(cls)
        db.commit()
        cls_id = cls.id
    teach_headers = _login_headers(client, f"it-{tag}", PASSWORD)
    sr = client.post(
        "/teacher/students",
        headers=teach_headers,
        json={"name": "机构学生", "username": f"is-{tag}", "password": PASSWORD, "grade": 4, "class_id": cls_id},
    )
    assert sr.status_code == 200, sr.text[:300]
    sid = sr.json()["id"]
    pr = client.post(
        "/admin/users",
        headers=t_headers,
        json={"name": "机构家长", "username": f"ip-{tag}", "password": PASSWORD, "role": "parent"},
    )
    assert pr.status_code == 200, pr.text[:300]
    pid = pr.json()["id"]
    assert client.post(f"/teacher/students/{sid}/parent", headers=teach_headers, json={"parent_id": pid}).status_code == 200
    p_headers = _login_headers(client, f"ip-{tag}", PASSWORD)

    # Activate guardian consent, but keep allow_student_data=False
    tok = client.post(f"/teacher/students/{sid}/ai-consent/token", headers=teach_headers, json={}).json()["token"]
    assert client.post("/parent/ai-consent/confirm", headers=p_headers, json={"token": tok, "student_id": sid}).status_code == 200

    http_calls = []
    monkeypatch.setattr(
        legacy.requests,
        "post",
        lambda url, *a, **kw: http_calls.append(url) or SimpleNamespace(ok=True, status_code=200, json=lambda: {"choices": [{"message": {"content": "ok"}}]}),
    )

    with legacy.SessionLocal() as db:
        teacher = db.query(legacy.User).filter(legacy.User.username == f"it-{tag}").first()
        cfg = legacy.ai_config_for(db, teacher.school_id, True)
        cfg.enabled = True
        cfg.allow_student_data = False
        cfg.provider = "openai_compatible"
        cfg.base_url = "https://api.deepseek.com/v1"
        cfg.model = "deepseek-chat"
        db.commit()
        for feat in (
            "weekend_report",
            "weekend_practice",
            "homework_help_guide",
            "exam_prep",
            "knowledge_map",
            "homework_practice_generate",
            "unknown_feature",
        ):
            with pytest.raises(HTTPException) as exc:
                legacy._ai_call(db, teacher, feat, "prompt", student_ids=(sid,))
            assert exc.value.status_code == 403
        with pytest.raises(HTTPException) as exc_img:
            legacy._ai_call(db, teacher, "homework_help_solve", "prompt", images=["data:image/png;base64,AAAA"], student_ids=(sid,))
        assert exc_img.value.status_code == 403
    assert len(http_calls) == 0


def test_personal_homework_practice_and_weekend_report_require_student_consent(client, monkeypatch):
    from types import SimpleNamespace
    from fastapi import HTTPException
    import app_v924 as legacy

    t_headers, p_headers, _s_headers, student_id = _setup_personal_family(client)
    monkeypatch.setenv("STUDENT_AI_COMPLIANCE_APPROVED", "1")
    monkeypatch.setattr(legacy, "_validate_ai_base_url", lambda base, runtime=False: base)
    http_calls = []
    monkeypatch.setattr(
        legacy.requests,
        "post",
        lambda url, *a, **kw: http_calls.append(url) or SimpleNamespace(ok=True, status_code=200, json=lambda: {"choices": [{"message": {"content": "ok"}}]}),
    )

    with legacy.SessionLocal() as db:
        student = db.get(legacy.User, student_id)
        teacher = db.query(legacy.User).filter(legacy.User.school_id == student.school_id, legacy.User.role == "teacher").first()
        for feat in ("homework_practice_generate", "weekend_report", "weekend_practice"):
            with pytest.raises(HTTPException) as exc:
                legacy._ai_call(db, teacher, feat, "prompt", student_ids=(student_id,))
            assert exc.value.status_code == 403
    assert len(http_calls) == 0

    tok = client.post(f"/teacher/students/{student_id}/ai-consent/token", headers=t_headers, json={}).json()["token"]
    assert client.post("/parent/ai-consent/confirm", headers=p_headers, json={"token": tok, "student_id": student_id}).status_code == 200

    with legacy.SessionLocal() as db:
        student = db.get(legacy.User, student_id)
        teacher = db.query(legacy.User).filter(legacy.User.school_id == student.school_id, legacy.User.role == "teacher").first()
        for feat in ("homework_practice_generate", "weekend_report", "weekend_practice"):
            assert legacy._ai_call(db, teacher, feat, "prompt", student_ids=(student_id,)) == "ok"
    assert len(http_calls) == 3
