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
    monkeypatch.setenv("HOMEWORK_ASSISTANT", "1")
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
    monkeypatch.setenv("HOMEWORK_ASSISTANT", "1")
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

    # 2. Teacher pure product guidance & free-text containing student info (no image, no child_id)
    # Must NEVER send unreviewed teacher free-text to external AI (0 HTTP calls).
    r_guide = client.post("/v1/product-assistant/query", headers=t_headers, json={"question": "怎么创建班级？"})
    assert r_guide.status_code == 200
    assert r_guide.json()["source"] == "local"
    assert len(http_calls) == 0

    r_free_text = client.post(
        "/v1/product-assistant/query",
        headers=t_headers,
        json={"question": "张小明这次数学考了58分，错题很多，怎么辅导？"},
    )
    assert r_free_text.status_code == 200
    assert r_free_text.json()["source"] == "local"
    assert len(http_calls) == 0

    with legacy.SessionLocal() as db:
        student = db.get(legacy.User, student_id)
        teacher = db.query(legacy.User).filter(legacy.User.school_id == student.school_id, legacy.User.role == "teacher").first()
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_pa:
            legacy._ai_call(db, teacher, "product_assistant_guidance", "张小明这次数学考了58分")
        assert exc_pa.value.status_code == 403
    assert len(http_calls) == 0

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
    assert len(http_calls) == 0

    # 4. Parent with wrong/unlinked child_id -> 403, 0 new HTTP calls
    r_p_bad = client.post(
        "/v1/product-assistant/query",
        headers=p_headers,
        json={"question": "孩子最近学得怎么样？", "child_id": 999999},
    )
    assert r_p_bad.status_code == 403
    assert len(http_calls) == 0

    # 5. Parent unauthorized (consent not yet active) -> 0 new HTTP calls
    monkeypatch.setenv("STUDENT_AI_COMPLIANCE_APPROVED", "1")
    r_p_unauth = client.post(
        "/v1/product-assistant/query",
        headers=p_headers,
        json={"question": "孩子最近学得怎么样？", "child_id": student_id},
    )
    assert r_p_unauth.status_code == 200
    assert len(http_calls) == 0

    # 6. Activate parent consent -> student text + student image both succeed
    tok = client.post(f"/teacher/students/{student_id}/ai-consent/token", headers=t_headers, json={}).json()["token"]
    assert client.post("/parent/ai-consent/confirm", headers=p_headers, json={"token": tok, "student_id": student_id}).status_code == 200

    r_s_auth = client.post("/v1/product-assistant/query", headers=s_headers, json={"question": "这道分数题怎么理解？"})
    assert r_s_auth.status_code == 200
    assert len(http_calls) == 1

    r_s_img = client.post("/v1/product-assistant/query", headers=s_headers, json=img_payload)
    assert r_s_img.status_code == 200
    assert len(http_calls) == 2


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
        cfg.api_key_cipher = legacy._ai_encrypt_key("sk-inst-v6-test-key")
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


def test_personal_weekend_courseware_and_hint_boundaries(client, monkeypatch):
    import json
    from types import SimpleNamespace
    from fastapi import HTTPException
    import app_v924 as legacy

    t_headers, p_headers, _s_headers, student_id = _setup_personal_family(client)
    monkeypatch.delenv("STUDENT_AI_COMPLIANCE_APPROVED", raising=False)
    monkeypatch.setattr(legacy, "_validate_ai_base_url", lambda base, runtime=False: base)

    http_calls = []

    def fake_post(url, *args, **kwargs):
        http_calls.append(url)
        payload = kwargs.get("json") or {}
        text = json.dumps(payload, ensure_ascii=False)
        if "levels" in text:
            content = json.dumps({"levels": ["先看已知条件", "列出算式", "算出结果 15"]}, ensure_ascii=False)
        else:
            content = json.dumps({
                "template": "steps",
                "title": "分数应用题",
                "problem": "小明有12支铅笔，送出1/4，还剩多少支？",
                "steps": ["找单位1", "列式计算"],
                "answer": "9支",
            }, ensure_ascii=False)
        return SimpleNamespace(
            ok=True,
            status_code=200,
            json=lambda: {"choices": [{"message": {"content": content}}]},
        )

    monkeypatch.setattr(legacy.requests, "post", fake_post)

    with legacy.SessionLocal() as db:
        student = db.get(legacy.User, student_id)
        prog = legacy.TeachingProgram(
            school_id=student.school_id,
            title="五年级周末培优",
            grade=5,
        )
        db.add(prog)
        db.flush()
        lesson = legacy.TeachingLesson(
            school_id=student.school_id,
            program_id=prog.id,
            subject="数学",
            lesson_no=1,
            title="分数应用题精讲",
            core_target="掌握单位1",
            teacher_plan="第1页讲解分数的意义",
        )
        db.add(lesson)
        db.flush()
        tq = legacy.TeachingQuestion(
            school_id=student.school_id,
            program_id=prog.id,
            lesson_id=lesson.id,
            subject="数学",
            level=1,
            stem="小明有12支铅笔，送出1/4，还剩多少支？",
            options_json=json.dumps(["3支", "9支", "6支", "8支"], ensure_ascii=False),
            correct_index=1,
            knowledge="分数应用题",
        )
        db.add(tq)
        db.commit()
        lid, qid = lesson.id, tq.id

    # 1. Unverified teacher free-text courseware (weekend_courseware) is excluded from allowlist -> blocked (0 HTTP)
    r_cw = client.post(f"/teacher/weekend/lessons/{lid}/courseware/generate", headers=t_headers, json={"stageNo": 1})
    assert r_cw.status_code in (403, 502)
    assert len(http_calls) == 0

    # 2. Teacher weekend_hint carries unverified question stem/options -> blocked without consent (0 HTTP)
    r_hint = client.post("/teacher/weekend/hints/generate", headers=t_headers, json={"questionId": qid})
    assert r_hint.status_code in (403, 502)
    assert len(http_calls) == 0

    # 3. Student-scoped weekend_hint / weekend_report / weekend_practice without consent MUST be blocked (0 new HTTP calls)
    with legacy.SessionLocal() as db:
        student = db.get(legacy.User, student_id)
        for feat in ("weekend_hint", "weekend_report", "weekend_practice"):
            with pytest.raises(HTTPException) as exc:
                legacy._ai_call(db, student, feat, "prompt", student_ids=(student_id,))
            assert exc.value.status_code == 403
    assert len(http_calls) == 0

    # 4. After guardian consent + compliance approval, student weekend_hint succeeds; after revocation -> 403, 0 HTTP
    monkeypatch.setenv("STUDENT_AI_COMPLIANCE_APPROVED", "1")
    tok = client.post(f"/teacher/students/{student_id}/ai-consent/token", headers=t_headers, json={}).json()["token"]
    assert client.post("/parent/ai-consent/confirm", headers=p_headers, json={"token": tok, "student_id": student_id}).status_code == 200
    with legacy.SessionLocal() as db:
        student = db.get(legacy.User, student_id)
        assert legacy._ai_call(db, student, "weekend_hint", '{"levels": []}', student_ids=(student_id,))
    assert len(http_calls) == 1

    assert client.post(f"/parent/children/{student_id}/ai-consent/revoke", headers=p_headers, json={"reason": "revoke"}).status_code == 200
    with legacy.SessionLocal() as db:
        student = db.get(legacy.User, student_id)
        with pytest.raises(HTTPException) as exc_rev:
            legacy._ai_call(db, student, "weekend_hint", '{"levels": []}', student_ids=(student_id,))
        assert exc_rev.value.status_code == 403
    assert len(http_calls) == 1


def test_v4_independent_acceptance_matrix(client, monkeypatch):
    from types import SimpleNamespace
    from fastapi import HTTPException
    import app_v924 as legacy
    from changying.services.guardian_consent import (
        CONSENT_METADATA,
        register_guardian_consent_tables,
    )

    t_headers, p_headers, _s_headers, student_id = _setup_personal_family(client)
    monkeypatch.setattr(legacy, "_validate_ai_base_url", lambda base, runtime=False: base)
    http_calls = []
    monkeypatch.setattr(
        legacy.requests,
        "post",
        lambda url, *a, **kw: http_calls.append(url) or SimpleNamespace(ok=True, status_code=200, json=lambda: {"choices": [{"message": {"content": "ok"}}]}),
    )

    # 1. Pure-text paper_import containing student name & score without authorization -> 0 HTTP
    monkeypatch.delenv("STUDENT_AI_COMPLIANCE_APPROVED", raising=False)
    r_paper = client.post(
        "/teacher/papers/import/parse",
        headers=t_headers,
        json={"grade": 5, "subject": "数学", "text": "张小明 数学 58分\n1. 1+1=?"},
    )
    assert r_paper.status_code in (403, 502)
    assert len(http_calls) == 0

    # 2. Hardcoded connection_test (zero user input) succeeds; question_generation without consent is blocked
    with legacy.SessionLocal() as db:
        student = db.get(legacy.User, student_id)
        teacher = db.query(legacy.User).filter(legacy.User.school_id == student.school_id, legacy.User.role == "teacher").first()
        assert legacy._ai_call(db, teacher, "connection_test", "你是长缨辅学的AI连接测试。请只回复：连接成功") == "ok"
    assert len(http_calls) == 1

    # 3. Unregistered AI feature MUST return 403 and 0 HTTP even with student_ai_all consent & compliance open
    monkeypatch.setenv("STUDENT_AI_COMPLIANCE_APPROVED", "1")
    tok = client.post(f"/teacher/students/{student_id}/ai-consent/token", headers=t_headers, json={"scope": "student_ai_all"}).json()["token"]
    assert client.post("/parent/ai-consent/confirm", headers=p_headers, json={"token": tok, "student_id": student_id}).status_code == 200
    with legacy.SessionLocal() as db:
        student = db.get(legacy.User, student_id)
        teacher = db.query(legacy.User).filter(legacy.User.school_id == student.school_id, legacy.User.role == "teacher").first()
        with pytest.raises(HTTPException) as exc_unreg:
            legacy._ai_call(db, teacher, "brand_new_unregistered_feature", "hello", student_ids=(student_id,))
        assert exc_unreg.value.status_code == 403
    assert len(http_calls) == 1

    # 4. Institutional mode with allow_student_data=True but missing student_ids -> 403, 0 HTTP
    tag = uuid.uuid4().hex[:8]
    inst_code = f"inst-v4-{tag}"
    assert client.post(
        "/operator/schools/create",
        headers={"X-Commercial-Key": COMMERCIAL_KEY},
        json={
            "school_name": f"机构V4-{tag}",
            "school_code": inst_code,
            "admin_name": "刘老师",
            "admin_username": inst_code,
            "admin_password": PASSWORD,
            "individual": False,
        },
    ).status_code == 200
    with legacy.SessionLocal() as db:
        inst_admin = db.query(legacy.User).filter(legacy.User.username == inst_code).first()
        cfg = legacy.ai_config_for(db, inst_admin.school_id, True)
        cfg.enabled = True
        cfg.allow_student_data = True
        cfg.provider = "openai_compatible"
        cfg.base_url = "https://api.deepseek.com/v1"
        cfg.model = "deepseek-chat"
        cfg.api_key_cipher = legacy._ai_encrypt_key("sk-inst-v6-test-key")
        db.commit()
        with pytest.raises(HTTPException) as exc_inst:
            legacy._ai_call(db, inst_admin, "homework_help_solve", "missing student owner")
        assert exc_inst.value.status_code == 403
    assert len(http_calls) == 1

    # 5. Production non-SQLite DB does NOT auto-run create_all at startup unless migration is approved
    create_calls = []
    monkeypatch.setattr(CONSENT_METADATA, "create_all", lambda bind=None: create_calls.append(bind))
    monkeypatch.delenv("GUARDIAN_CONSENT_MIGRATION_APPROVED", raising=False)
    fake_pg_impl = SimpleNamespace(engine=SimpleNamespace(dialect=SimpleNamespace(name="postgresql")))
    register_guardian_consent_tables(fake_pg_impl)
    assert len(create_calls) == 0
    monkeypatch.setenv("GUARDIAN_CONSENT_MIGRATION_APPROVED", "1")
    register_guardian_consent_tables(fake_pg_impl)
    assert len(create_calls) == 1


def test_v5_reinforcement_and_question_gen_notes_isolation(client, monkeypatch):
    import json
    from concurrent.futures import ThreadPoolExecutor
    from types import SimpleNamespace
    from fastapi import HTTPException
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateIndex, CreateTable
    import app_v924 as legacy
    from changying.services.guardian_consent import CONSENT_METADATA

    t_headers, p_headers, _s_headers, student_id = _setup_personal_family(client)
    monkeypatch.setattr(legacy, "_validate_ai_base_url", lambda base, runtime=False: base)

    http_calls = []

    def fake_post(url, *args, **kwargs):
        http_calls.append(url)
        payload = kwargs.get("json") or {}
        text = json.dumps(payload, ensure_ascii=False)
        if "questions" in text:
            content = json.dumps({
                "questions": [{
                    "question_type": "single_choice",
                    "knowledge": "分数计算",
                    "text": "1/2 + 1/3 等于多少？",
                    "options": ["2/5", "5/6", "1/6", "3/5"],
                    "correct_index": 1,
                    "explanation": "通分后相加：3/6 + 2/6 = 5/6。",
                }]
            }, ensure_ascii=False)
        else:
            content = json.dumps({
                "items": [{
                    "question_type": "single_choice",
                    "grade": 5,
                    "subject": "数学",
                    "textbook": "人教版",
                    "semester": "上册",
                    "unit": "分数加法",
                    "knowledge": "分数计算",
                    "text": "1/4 + 1/2 等于多少？",
                    "options": ["1/6", "3/4", "2/6", "1/2"],
                    "correct_index": 1,
                    "explanation": "通分后相加：1/4 + 2/4 = 3/4。",
                }]
            }, ensure_ascii=False)
        return SimpleNamespace(
            ok=True,
            status_code=200,
            json=lambda: {"choices": [{"message": {"content": content}}]},
        )

    monkeypatch.setattr(legacy.requests, "post", fake_post)

    # Seed real WrongQuestionRecord for student_id
    with legacy.SessionLocal() as db:
        stu = db.get(legacy.User, student_id)
        db.add(legacy.WrongQuestionRecord(
            school_id=stu.school_id,
            student_id=student_id,
            subject="数学",
            knowledge="分数计算",
            problem_text="1/2 + 1/4 = ?",
            wrong_answer="2/6",
            correct_answer="3/4",
            analysis="先通分再相加",
            status="active",
        ))
        db.commit()

    # 1. reinforcement_generate: compliance closed (even with allow_student_data=True) -> 403, 0 HTTP
    monkeypatch.delenv("STUDENT_AI_COMPLIANCE_APPROVED", raising=False)
    r_closed = client.post(
        f"/teacher/students/{student_id}/reinforcement/generate",
        headers=t_headers,
        json={"count": 1},
    )
    assert r_closed.status_code == 403
    assert len(http_calls) == 0

    # 2. compliance open, NO guardian consent -> 403, 0 HTTP
    monkeypatch.setenv("STUDENT_AI_COMPLIANCE_APPROVED", "1")
    r_no_consent = client.post(
        f"/teacher/students/{student_id}/reinforcement/generate",
        headers=t_headers,
        json={"count": 1},
    )
    assert r_no_consent.status_code == 403
    assert len(http_calls) == 0

    # 3. Direct _ai_call("reinforcement_generate") without student_ids -> 403, 0 HTTP
    with legacy.SessionLocal() as db:
        stu = db.get(legacy.User, student_id)
        teacher = db.query(legacy.User).filter(legacy.User.school_id == stu.school_id, legacy.User.role == "teacher").first()
        with pytest.raises(HTTPException) as exc_direct:
            legacy._ai_call(db, teacher, "reinforcement_generate", "prompt")
        assert exc_direct.value.status_code == 403
    assert len(http_calls) == 0

    # 4. Activate guardian consent -> reinforcement_generate succeeds (1 HTTP)
    tok = client.post(f"/teacher/students/{student_id}/ai-consent/token", headers=t_headers, json={"scope": "exam_prep_ai"}).json()["token"]
    assert client.post("/parent/ai-consent/confirm", headers=p_headers, json={"token": tok, "student_id": student_id}).status_code == 200
    r_ok = client.post(
        f"/teacher/students/{student_id}/reinforcement/generate",
        headers=t_headers,
        json={"count": 1},
    )
    assert r_ok.status_code == 200, r_ok.text[:300]
    assert len(http_calls) == 1

    # 5. Revoke consent -> retry & concurrent calls for revoked student -> 403, 0 new HTTP
    assert client.post(f"/parent/children/{student_id}/ai-consent/revoke", headers=p_headers, json={"reason": "revoke"}).status_code == 200
    r_rev = client.post(
        f"/teacher/students/{student_id}/reinforcement/generate",
        headers=t_headers,
        json={"count": 1},
    )
    assert r_rev.status_code == 403
    assert len(http_calls) == 1

    def _retry_revoked():
        return client.post(
            f"/teacher/students/{student_id}/reinforcement/generate",
            headers=t_headers,
            json={"count": 1},
        ).status_code

    with ThreadPoolExecutor(max_workers=3) as pool:
        statuses = list(pool.map(lambda _: _retry_revoked(), range(3)))
    assert statuses == [403, 403, 403]
    assert len(http_calls) == 1

    # 6. question_generation & question_generation_repair with teacher notes containing student name & score -> 403, 0 new HTTP
    r_q_notes = client.post(
        "/ai/questions/generate",
        headers=t_headers,
        json={
            "grade": 5,
            "subject": "数学",
            "textbook": "人教版",
            "semester": "上册",
            "count": 1,
            "notes": "根据张小明最近数学考试58分、分数计算薄弱的情况，生成针对性练习",
        },
    )
    assert r_q_notes.status_code == 403
    assert len(http_calls) == 1

    with legacy.SessionLocal() as db:
        stu = db.get(legacy.User, student_id)
        teacher = db.query(legacy.User).filter(legacy.User.school_id == stu.school_id, legacy.User.role == "teacher").first()
        with pytest.raises(HTTPException) as exc_rep:
            legacy._ai_call(db, teacher, "question_generation_repair", "repair", unverified_free_text=True)
        assert exc_rep.value.status_code == 403
    assert len(http_calls) == 1

    # 7. question_generation without student_ids is ALSO blocked (403, 0 new HTTP) since all user fields can carry PII
    r_q_pure = client.post(
        "/ai/questions/generate",
        headers=t_headers,
        json={
            "grade": 5,
            "subject": "数学",
            "textbook": "人教版",
            "semester": "上册",
            "knowledge": "分数计算",
            "count": 1,
            "notes": "",
        },
    )
    assert r_q_pure.status_code == 403
    assert len(http_calls) == 1

    # 8. PostgreSQL DDL compilation check for all 3 tables & indexes
    pg_dialect = postgresql.dialect()
    ddls = []
    for tbl in CONSENT_METADATA.sorted_tables:
        ddls.append(str(CreateTable(tbl).compile(dialect=pg_dialect)))
        for idx in tbl.indexes:
            ddls.append(str(CreateIndex(idx).compile(dialect=pg_dialect)))
    joined_ddl = "\n".join(ddls)
    assert "CREATE TABLE guardian_ai_consents" in joined_ddl
    assert "CREATE TABLE guardian_consent_tokens" in joined_ddl
    assert "CREATE TABLE guardian_consent_audit_logs" in joined_ddl


def test_v6_round3_audit_fixes(client, monkeypatch, tmp_path):
    import json
    from types import SimpleNamespace
    from fastapi import HTTPException
    import app_v924 as legacy
    from changying.services.guardian_consent_ddl import (
        downgrade_consent_schema,
        main as migration_cli_main,
        upgrade_consent_schema,
        verify_consent_schema,
    )

    t_headers, _p_headers, _s_headers, student_id = _setup_personal_family(client)
    monkeypatch.setattr(legacy, "_validate_ai_base_url", lambda base, runtime=False: base)
    monkeypatch.setenv("HOMEWORK_ASSISTANT", "1")

    http_calls = []

    def fake_post(url, *args, **kwargs):
        http_calls.append(url)
        return SimpleNamespace(
            ok=True,
            status_code=200,
            json=lambda: {
                "choices": [{
                    "message": {
                        "content": json.dumps({
                            "questions": [{
                                "question_type": "single_choice",
                                "knowledge": "分数计算",
                                "text": "1/2 + 1/4 = ?",
                                "options": ["1/6", "3/4", "2/6", "1/2"],
                                "correct_index": 1,
                                "explanation": "通分相加",
                            }]
                        }, ensure_ascii=False)
                    }
                }]
            },
        )

    monkeypatch.setattr(legacy.requests, "post", fake_post)

    # 1. P0-1: question_generation with resource_ids containing student PII (even with notes="") MUST be blocked (0 HTTP)
    with legacy.SessionLocal() as db:
        stu = db.get(legacy.User, student_id)
        teacher = db.query(legacy.User).filter(legacy.User.school_id == stu.school_id, legacy.User.role == "teacher").first()
        raw_doc = "张小明 学号20260105 数学考试 58分".encode("utf-8")
        res = legacy.TeachingResource(
            school_id=stu.school_id,
            uploader_id=teacher.id,
            title="张小明数学测验记录.docx",
            subject="数学",
            grade=5,
            file_name="score.docx",
            file_ext="docx",
            size_bytes=len(raw_doc),
            sha256="a" * 64,
            file_data=raw_doc,
        )
        db.add(res)
        db.commit()
        rid = res.id

    r_res = client.post(
        "/ai/questions/generate",
        headers=t_headers,
        json={
            "grade": 5,
            "subject": "数学",
            "textbook": "人教版",
            "semester": "上册",
            "count": 1,
            "notes": "",
            "resource_ids": [rid],
        },
    )
    assert r_res.status_code == 403
    assert len(http_calls) == 0

    # question_generation without student_ids is strictly blocked (0 HTTP)
    r_pure = client.post(
        "/ai/questions/generate",
        headers=t_headers,
        json={
            "grade": 5,
            "subject": "数学",
            "textbook": "人教版",
            "semester": "上册",
            "knowledge": "分数计算",
            "count": 1,
            "notes": "",
            "resource_ids": [],
        },
    )
    assert r_pure.status_code == 403
    assert len(http_calls) == 0

    # 2. P0-3 & P1: Institutional homework_parse / homework_parse_vision without studentIds & invalid student ownership
    tag = uuid.uuid4().hex[:8]
    inst_code = f"inst-v6-{tag}"
    assert client.post(
        "/operator/schools/create",
        headers={"X-Commercial-Key": COMMERCIAL_KEY},
        json={
            "school_name": f"机构V6-{tag}",
            "school_code": inst_code,
            "admin_name": "赵老师",
            "admin_username": inst_code,
            "admin_password": PASSWORD,
            "individual": False,
        },
    ).status_code == 200
    inst_admin_h = _login_headers(client, inst_code, PASSWORD)
    tr = client.post(
        "/admin/users",
        headers=inst_admin_h,
        json={"name": "机构教师", "username": f"it6-{tag}", "password": PASSWORD, "role": "teacher"},
    )
    assert tr.status_code == 200
    teach_id = tr.json()["id"]
    with legacy.SessionLocal() as db:
        t_u = db.get(legacy.User, teach_id)
        cls = legacy.SchoolClass(school_id=t_u.school_id, name="五年级1班", grade=5, teacher_id=teach_id)
        db.add(cls)
        db.commit()
        cls_id = cls.id
        cfg = legacy.ai_config_for(db, t_u.school_id, True)
        cfg.enabled = True
        cfg.allow_student_data = True
        cfg.provider = "openai_compatible"
        cfg.base_url = "https://api.deepseek.com/v1"
        cfg.model = "deepseek-chat"
        cfg.api_key_cipher = legacy._ai_encrypt_key("sk-inst-v6-test-key")
        db.commit()
    inst_teach_h = _login_headers(client, f"it6-{tag}", PASSWORD)
    sr = client.post(
        "/teacher/students",
        headers=inst_teach_h,
        json={"name": "机构小敏", "username": f"is6-{tag}", "password": PASSWORD, "grade": 5, "class_id": cls_id},
    )
    assert sr.status_code == 200
    inst_sid = sr.json()["id"]

    # Missing studentIds on institutional homework_parse -> 403, 0 new HTTP
    r_hw_no_sid = client.post(
        "/teacher/homework/parse",
        headers=inst_teach_h,
        json={"text": "张小明 学号20260105 数学58分，请完成第5页练习"},
    )
    assert r_hw_no_sid.status_code == 403
    assert len(http_calls) == 0

    # Missing studentIds on institutional homework_parse_vision -> 403, 0 new HTTP
    r_hw_img_no_sid = client.post(
        "/teacher/homework/parse-image",
        headers={**inst_teach_h, "Content-Type": "image/png"},
        content=b"\x89PNG\r\n\x1a\n" + b"0" * 32,
    )
    assert r_hw_img_no_sid.status_code == 403
    assert len(http_calls) == 0

    # P1: Institutional DB student ownership validation
    with legacy.SessionLocal() as db:
        inst_teacher = db.get(legacy.User, teach_id)
        for bad_sid in (999999, teach_id, student_id):
            with pytest.raises(HTTPException) as exc_bad:
                legacy._ai_call(db, inst_teacher, "homework_help_solve", "hello", student_ids=(bad_sid,))
            assert exc_bad.value.status_code == 403
        assert len(http_calls) == 0
        assert legacy._ai_call(db, inst_teacher, "homework_help_solve", "hello", student_ids=(inst_sid,))
    assert len(http_calls) == 1

    # 3. P1: Executable migration & reverse-order rollback CLI drill on isolated DB
    mig_db_url = f"sqlite:///{tmp_path / 'mig_drill.sqlite3'}"
    mig_engine = create_engine(mig_db_url)
    legacy.Base.metadata.create_all(bind=mig_engine)
    assert migration_cli_main(["verify", "--database-url", mig_db_url]) == 1
    assert migration_cli_main(["upgrade", "--database-url", mig_db_url]) == 0
    assert migration_cli_main(["verify", "--database-url", mig_db_url]) == 0
    assert all(verify_consent_schema(mig_engine).values())
    assert migration_cli_main(["downgrade", "--database-url", mig_db_url]) == 2
    assert all(verify_consent_schema(mig_engine).values())
    assert migration_cli_main(["downgrade", "--database-url", mig_db_url, "--confirm-downgrade"]) == 0
    assert migration_cli_main(["verify", "--database-url", mig_db_url]) == 1
    assert not any(verify_consent_schema(mig_engine).values())
    assert {"users", "parent_students", "point_ledger"}.issubset(set(inspect(mig_engine).get_table_names()))
    assert upgrade_consent_schema(mig_engine)
    assert downgrade_consent_schema(mig_engine)
    mig_engine.dispose()


def test_v7_round4_audit_fixes(client, monkeypatch, tmp_path):
    import json
    import subprocess
    from types import SimpleNamespace
    from fastapi import HTTPException
    import app_v924 as legacy
    from changying.services.homework_prompts import scrub_notice_text

    t_headers, p_headers, _s_headers, student_id = _setup_personal_family(client)
    monkeypatch.setattr(legacy, "_validate_ai_base_url", lambda base, runtime=False: base)
    monkeypatch.setenv("HOMEWORK_ASSISTANT", "1")
    monkeypatch.setenv("STUDENT_AI_COMPLIANCE_APPROVED", "1")

    http_calls = []

    def fake_post(url, *args, **kwargs):
        http_calls.append(url)
        return SimpleNamespace(
            ok=True,
            status_code=200,
            json=lambda: {"choices": [{"message": {"content": json.dumps({"levels": ["提示1", "提示2", "提示3"]}, ensure_ascii=False)}}]},
        )

    monkeypatch.setattr(legacy.requests, "post", fake_post)

    # 1. P0: Every string field in AIQuestionGenerateBody injected with student PII + question_generation_repair -> 403, 0 HTTP
    pii = "张小明最近考试58分，数学薄弱"
    base_payload = {
        "grade": 5,
        "subject": "数学",
        "textbook": "人教版",
        "semester": "上册",
        "unit": "",
        "knowledge": "",
        "difficulty": "中等",
        "question_type": "mixed",
        "count": 1,
        "notes": "",
        "resource_ids": [],
    }
    for field in ("subject", "textbook", "semester", "unit", "knowledge", "difficulty", "question_type", "notes"):
        bad_payload = {**base_payload, field: pii}
        r_f = client.post("/ai/questions/generate", headers=t_headers, json=bad_payload)
        assert r_f.status_code in (400, 403), (field, r_f.status_code)
    with legacy.SessionLocal() as db:
        stu = db.get(legacy.User, student_id)
        teacher = db.query(legacy.User).filter(legacy.User.school_id == stu.school_id, legacy.User.role == "teacher").first()
        for feat in ("question_generation", "question_generation_repair"):
            with pytest.raises(HTTPException) as exc_q:
                legacy._ai_call(db, teacher, feat, pii)
            assert exc_q.value.status_code == 403
    assert len(http_calls) == 0

    # 2. P1: Same-school other-teacher class student MUST be rejected (teacher_class_ownership_denied)
    tag = uuid.uuid4().hex[:8]
    inst_code = f"inst-v7-{tag}"
    assert client.post(
        "/operator/schools/create",
        headers={"X-Commercial-Key": COMMERCIAL_KEY},
        json={
            "school_name": f"机构V7-{tag}",
            "school_code": inst_code,
            "admin_name": "校长",
            "admin_username": inst_code,
            "admin_password": PASSWORD,
            "individual": False,
        },
    ).status_code == 200
    admin_h = _login_headers(client, inst_code, PASSWORD)
    ta_id = client.post("/admin/users", headers=admin_h, json={"name": "甲老师", "username": f"ta-{tag}", "password": PASSWORD, "role": "teacher"}).json()["id"]
    with legacy.SessionLocal() as db:
        ta_u = db.get(legacy.User, ta_id)
        tb_u = legacy.User(
            school_id=ta_u.school_id,
            name="乙老师",
            username=f"tb-{tag}",
            password_hash=ta_u.password_hash,
            role="teacher",
            active=True,
        )
        db.add(tb_u)
        db.flush()
        tb_id = tb_u.id
        ca = legacy.SchoolClass(school_id=ta_u.school_id, name="甲班", grade=5, teacher_id=ta_id)
        cb = legacy.SchoolClass(school_id=ta_u.school_id, name="乙班", grade=5, teacher_id=tb_id)
        db.add_all([ca, cb])
        db.commit()
        ca_id, cb_id = ca.id, cb.id
        cfg = legacy.ai_config_for(db, ta_u.school_id, True)
        cfg.enabled = True
        cfg.allow_student_data = True
        cfg.provider = "openai_compatible"
        cfg.base_url = "https://api.deepseek.com/v1"
        cfg.model = "deepseek-chat"
        cfg.api_key_cipher = legacy._ai_encrypt_key("sk-inst-v7-key")
        db.commit()
    ta_h = _login_headers(client, f"ta-{tag}", PASSWORD)
    tb_h = _login_headers(client, f"tb-{tag}", PASSWORD)
    sa_id = client.post("/teacher/students", headers=ta_h, json={"name": "甲班生", "username": f"sa-{tag}", "password": PASSWORD, "grade": 5, "class_id": ca_id}).json()["id"]
    sb_id = client.post("/teacher/students", headers=tb_h, json={"name": "乙班生", "username": f"sb-{tag}", "password": PASSWORD, "grade": 5, "class_id": cb_id}).json()["id"]

    # Teacher A passing Teacher B's student sb_id in the SAME school -> 403, 0 HTTP
    r_cross_cls = client.post(
        "/teacher/homework/parse",
        headers=ta_h,
        json={"text": "明天作业第5页", "studentIds": [sb_id]},
    )
    assert r_cross_cls.status_code == 403
    assert len(http_calls) == 0

    # 3. P1: Teacher weekend hints with studentIds (and authorized) succeeds; without studentIds -> 403
    with legacy.SessionLocal() as db:
        ta_u = db.get(legacy.User, ta_id)
        prog = legacy.TeachingProgram(school_id=ta_u.school_id, title="五年级培优V7", grade=5)
        db.add(prog)
        db.flush()
        lesson = legacy.TeachingLesson(school_id=ta_u.school_id, program_id=prog.id, subject="数学", lesson_no=1, title="小数")
        db.add(lesson)
        db.flush()
        tq = legacy.TeachingQuestion(
            school_id=ta_u.school_id,
            program_id=prog.id,
            lesson_id=lesson.id,
            subject="数学",
            level=1,
            stem="0.5 + 0.25 = ?",
            options_json=json.dumps(["0.75", "0.3", "0.5", "1.0"]),
            correct_index=0,
        )
        db.add(tq)
        db.commit()
        qid = tq.id

    assert client.post("/teacher/weekend/hints/generate", headers=ta_h, json={"questionId": qid}).status_code == 403
    assert client.post("/teacher/weekend/hints/generate", headers=ta_h, json={"questionId": qid, "studentIds": [sb_id]}).status_code == 403
    assert len(http_calls) == 0
    r_hint_ok = client.post("/teacher/weekend/hints/generate", headers=ta_h, json={"questionId": qid, "studentIds": [sa_id]})
    assert r_hint_ok.status_code == 200
    assert len(http_calls) == 1

    # 4. P1: Frontend /v1/homework wires /teacher/homework/students and passes studentIds
    hw_html = client.get("/v1/homework").text
    assert "/teacher/homework/students" in hw_html
    assert "studentIds" in hw_html

    # 5. P1: scrub_notice_text redacts labelled PII & scores
    scrubbed = scrub_notice_text("学生姓名：张小明 家长：王女士 学号：20260105 成绩：58分 13812345678")
    for secret in ("张小明", "王女士", "20260105", "58分", "13812345678"):
        assert secret not in scrubbed

    # 6. P1: Real subprocess CLI execution of python -m changying.services.guardian_consent_ddl
    cli_db_url = f"sqlite:///{tmp_path / 'cli_subproc.sqlite3'}"
    cli_env = {**os.environ, "PYTHONPATH": str(ROOT)}
    assert subprocess.run([sys.executable, "-m", "changying.services.guardian_consent_ddl", "verify", "--database-url", cli_db_url], cwd=ROOT, env=cli_env).returncode == 1
    assert subprocess.run([sys.executable, "-m", "changying.services.guardian_consent_ddl", "upgrade", "--database-url", cli_db_url], cwd=ROOT, env=cli_env).returncode == 0
    assert subprocess.run([sys.executable, "-m", "changying.services.guardian_consent_ddl", "verify", "--database-url", cli_db_url], cwd=ROOT, env=cli_env).returncode == 0
    assert subprocess.run([sys.executable, "-m", "changying.services.guardian_consent_ddl", "downgrade", "--database-url", cli_db_url], cwd=ROOT, env=cli_env).returncode == 2
    assert subprocess.run([sys.executable, "-m", "changying.services.guardian_consent_ddl", "downgrade", "--database-url", cli_db_url, "--confirm-downgrade"], cwd=ROOT, env=cli_env).returncode == 0
    assert subprocess.run([sys.executable, "-m", "changying.services.guardian_consent_ddl", "verify", "--database-url", cli_db_url], cwd=ROOT, env=cli_env).returncode == 1

def test_denied_egress_never_commits_callers_pending_changes(client, monkeypatch):
    """A blocked AI egress must not commit (or lose) unrelated pending business changes."""
    from fastapi import HTTPException
    import app_v924 as legacy

    monkeypatch.setenv("STUDENT_AI_COMPLIANCE_APPROVED", "1")
    monkeypatch.setattr(legacy, "_validate_ai_base_url", lambda base, runtime=False: base)
    t_headers, _p_headers, _s_headers, student_id = _setup_personal_family(client)

    http_calls = {"count": 0}
    monkeypatch.setattr(legacy.requests, "post", lambda *a, **kw: http_calls.__setitem__("count", http_calls["count"] + 1))

    with legacy.SessionLocal() as db:
        stu = db.get(legacy.User, student_id)
        teacher = db.query(legacy.User).filter(legacy.User.school_id == stu.school_id, legacy.User.role == "teacher").first()
        teacher_id = int(teacher.id)
        unpaid_name = f"未保存草稿-{uuid.uuid4().hex[:6]}"
        teacher.name = unpaid_name

        with pytest.raises(HTTPException) as exc:
            legacy._ai_call(db, teacher, "pending_change_probe_feature", "hello")
        assert exc.value.status_code == 403

        # The denial audit is still persisted, in its own transaction.
        audit_row = db.execute(
            text(
                "SELECT action, detail FROM guardian_consent_audit_logs "
                "WHERE actor_user_id = :uid AND action = 'egress.blocked' ORDER BY id DESC LIMIT 1"
            ),
            {"uid": teacher_id},
        ).first()
        assert audit_row is not None
        assert "pending_change_probe_feature" in str(audit_row[1])

    # The staged rename must not have been committed by the denial path.
    with legacy.SessionLocal() as db:
        reloaded = db.get(legacy.User, teacher_id)
        assert reloaded.name != unpaid_name
        assert db.query(legacy.User).filter(legacy.User.name == unpaid_name).count() == 0

    # Caller's pending business modification must ALSO be preserved if caller commits later!
    kept_name = f"合法保存-{uuid.uuid4().hex[:6]}"
    with legacy.SessionLocal() as db:
        teacher = db.get(legacy.User, teacher_id)
        teacher.name = kept_name
        with pytest.raises(HTTPException) as exc:
            legacy._ai_call(db, teacher, "pending_change_preserve_probe", "hello")
        assert exc.value.status_code == 403
        # Before caller commits, kept_name is still pending in caller's Session and not yet committed.
        with legacy.SessionLocal() as probe_db:
            assert probe_db.get(legacy.User, teacher_id).name != kept_name
        # Now caller performs a legitimate save: kept_name MUST be preserved and persisted!
        db.commit()

    with legacy.SessionLocal() as db:
        assert db.get(legacy.User, teacher_id).name == kept_name
    assert http_calls["count"] == 0


def test_v8_p0_1_pure_teaching_question_generation_and_free_text_blocking(client, monkeypatch):
    """V8 P0-1: Structured pure-teaching generation works; free-text/PII/direct repair calls stay blocked."""
    import json
    from fastapi import HTTPException
    import app_v924 as legacy

    monkeypatch.delenv("STUDENT_AI_COMPLIANCE_APPROVED", raising=False)
    monkeypatch.setattr(legacy, "_validate_ai_base_url", lambda base, runtime=False: base)
    t_headers, _p_headers, _s_headers, student_id = _setup_personal_family(client)

    sent_prompts: list[str] = []

    class FakeAIResp:
        status_code = 200
        ok = True

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "questions": [
                                        {
                                            "question_type": "single_choice",
                                            "text": "计算 1/2 + 1/3 的结果是多少？",
                                            "options": ["2/5", "5/6", "1/6", "2/3"],
                                            "correct_index": 1,
                                            "knowledge": "分数加减法",
                                            "explanation": "通分后 3/6 + 2/6 = 5/6。",
                                            "steps": ["通分", "分子相加"],
                                            "expression": "1/2+1/3",
                                        }
                                    ]
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 30},
            }

    def fake_post(url, headers=None, json=None, timeout=None):
        sent_prompts.append(str(json))
        return FakeAIResp()

    monkeypatch.setattr(legacy.requests, "post", fake_post)

    # Ensure AI config is enabled but allow_student_data=False and compliance closed
    with legacy.SessionLocal() as db:
        stu = db.get(legacy.User, student_id)
        school_id = int(stu.school_id)
        teacher = db.query(legacy.User).filter(legacy.User.school_id == school_id, legacy.User.role == "teacher").first()
        teacher_id = int(teacher.id)
        cfg = legacy.ai_config_for(db, school_id, True)
        cfg.enabled = True
        cfg.allow_student_data = False
        cfg.provider = "openai_compatible"
        cfg.base_url = "https://api.deepseek.com/v1"
        cfg.model = "deepseek-chat"
        cfg.api_key_cipher = legacy._ai_encrypt_key("sk-v8-p01-test-key")
        # Plant a school DB question containing a student name to prove pure-teaching skips _bank_examples
        db.add(
            legacy.Question(
                school_id=school_id,
                grade=5,
                subject="数学",
                textbook="人教版",
                semester="上册",
                unit="第三单元",
                knowledge="分数加减法",
                text="张三同学考了95分，请问他比平均分高多少？",
                options_json=json.dumps(["1", "2", "3", "4"]),
                correct_index=0,
                explanation="示例",
            )
        )
        db.commit()

    # 1. Legitimate structured pure-teaching generation succeeds for Math, Chinese, Science
    for payload in [
        {"grade": 5, "subject": "数学", "textbook": "人教版", "semester": "上册", "unit": "第三单元", "knowledge": "分数加减法", "difficulty": "中等", "question_type": "single_choice", "count": 1, "notes": "", "resource_ids": []},
        {"grade": 5, "subject": "语文", "textbook": "统编版（人民教育出版社）", "semester": "上册", "unit": "综合", "knowledge": "阅读理解", "difficulty": "基础", "question_type": "single_choice", "count": 1, "notes": "", "resource_ids": []},
        {"grade": 5, "subject": "科学", "textbook": "教科版", "semester": "上册", "unit": "第一单元", "knowledge": "物质的变化", "difficulty": "基础", "question_type": "single_choice", "count": 1, "notes": "", "resource_ids": []},
    ]:
        before = len(sent_prompts)
        res = client.post("/ai/questions/generate", headers=t_headers, json=payload)
        assert res.status_code == 200, (payload, res.text)
        assert len(res.json().get("items") or []) >= 1
        assert len(sent_prompts) > before
        assert "张三" not in sent_prompts[-1]

    # 2. All free-text / PII / resource_ids / direct repair / unknown feature probes MUST return 403 and 0 HTTP
    http_before_blocks = len(sent_prompts)
    for bad_payload in [
        {"grade": 5, "subject": "数学", "textbook": "人教版", "semester": "上册", "unit": "综合", "knowledge": "张小明 分数加减法 58分", "difficulty": "中等", "question_type": "single_choice", "count": 1, "notes": "", "resource_ids": []},
        {"grade": 5, "subject": "数学", "textbook": "人教版", "semester": "上册", "unit": "第三单元 李小红", "knowledge": "分数加减法", "difficulty": "中等", "question_type": "single_choice", "count": 1, "notes": "", "resource_ids": []},
        {"grade": 5, "subject": "数学", "textbook": "人教版", "semester": "上册", "unit": "综合", "knowledge": "分数加减法", "difficulty": "中等", "question_type": "single_choice", "count": 1, "notes": "针对张小明85分出题", "resource_ids": []},
        {"grade": 5, "subject": "数学", "textbook": "人教版", "semester": "上册", "unit": "综合", "knowledge": "分数加减法", "difficulty": "中等", "question_type": "single_choice", "count": 1, "notes": "", "resource_ids": [1]},
    ]:
        blocked = client.post("/ai/questions/generate", headers=t_headers, json=bad_payload)
        assert blocked.status_code == 403, (bad_payload, blocked.status_code, blocked.text)
        assert len(sent_prompts) == http_before_blocks

    with legacy.SessionLocal() as db:
        teacher = db.get(legacy.User, teacher_id)
        for direct_feature in ("question_generation", "question_generation_repair", "unknown_probe_feature"):
            with pytest.raises(HTTPException) as exc:
                legacy._ai_call(db, teacher, direct_feature, "学生张三 90分")
            assert exc.value.status_code == 403
            assert len(sent_prompts) == http_before_blocks


def test_v8_p0_2_homework_notice_raw_screenshot_8_scenarios(client, monkeypatch):
    """V8 P0-2: Unverified raw screenshots never leave to external vision AI; manual & text flows work."""
    from fastapi import HTTPException
    import app_v924 as legacy
    from changying.services import homework_vision

    monkeypatch.setenv("STUDENT_AI_COMPLIANCE_APPROVED", "1")
    monkeypatch.setenv("HOMEWORK_ASSISTANT", "1")
    monkeypatch.setenv("HOMEWORK_VISION_PROVIDER", "openai_compatible")
    monkeypatch.setenv("HOMEWORK_VISION_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("HOMEWORK_VISION_MODEL", "vision-test-model")
    monkeypatch.setenv("HOMEWORK_VISION_API_KEY", "sk-vision-test-key")
    monkeypatch.setattr(legacy, "_validate_ai_base_url", lambda base, runtime=False: base)

    t_headers, p_headers, _s_headers, sid1 = _setup_personal_family(client)
    # Create a second student without guardian consent
    with legacy.SessionLocal() as db:
        stu1 = db.get(legacy.User, sid1)
        school_id = int(stu1.school_id)
        teacher = db.query(legacy.User).filter(legacy.User.school_id == school_id, legacy.User.role == "teacher").first()
        cls = db.query(legacy.SchoolClass).filter(legacy.SchoolClass.school_id == school_id).first()
        cls_id = int(cls.id)
        teacher_id = int(teacher.id)
        cfg = legacy.ai_config_for(db, school_id, True)
        cfg.enabled = True
        cfg.allow_student_data = True
        cfg.provider = "openai_compatible"
        cfg.base_url = "https://api.deepseek.com/v1"
        cfg.model = "deepseek-chat"
        cfg.api_key_cipher = legacy._ai_encrypt_key("sk-hw-v8-key")
        db.commit()

    # Grant guardian consent ONLY for sid1
    tok_res = client.post(
        f"/teacher/students/{sid1}/ai-consent/token",
        headers=t_headers,
        json={"scope": "student_ai_all", "valid_days": 30},
    )
    assert tok_res.status_code == 200, tok_res.text
    conf_res = client.post(
        "/parent/ai-consent/confirm",
        headers=p_headers,
        json={"token": tok_res.json()["token"], "guardian_relation": "家长", "confirm_method": "parent_confirm"},
    )
    assert conf_res.status_code == 200, conf_res.text

    res2 = client.post(
        "/teacher/students",
        headers=t_headers,
        json={"name": "未授权同学", "username": f"unauth-{uuid.uuid4().hex[:6]}", "password": "Password123!", "grade": 5, "class_id": cls_id},
    )
    assert res2.status_code == 200
    sid2 = int(res2.json()["id"])

    http_calls: list[dict] = []
    monkeypatch.setattr(homework_vision.requests, "post", lambda *a, **kw: http_calls.append({"url": a, "kw": kw}))
    monkeypatch.setattr(legacy.requests, "post", lambda *a, **kw: http_calls.append({"url": a, "kw": kw}))

    jpeg = b"\xff\xd8\xff\xe0" + b"RAW-SCREENSHOT-BYTES" * 10

    # Scenarios 1-6: Raw screenshot upload via /teacher/homework/parse-image MUST be blocked with 0 external HTTP
    for url in (
        "/teacher/homework/parse-image",                         # 1. teaching-only raw screenshot (no studentIds)
        f"/teacher/homework/parse-image?studentIds={sid1}",      # 2 & 5 & 6. authorized / sensitive / partial studentIds
        f"/teacher/homework/parse-image?studentIds={sid2}",      # 3. unauthorized student
        f"/teacher/homework/parse-image?studentIds={sid1},{sid2}",  # 4. multiple students & parents
    ):
        r = client.post(url, headers={**t_headers, "Content-Type": "image/jpeg"}, content=jpeg)
        assert r.status_code == 403, (url, r.status_code, r.text)
        assert len(http_calls) == 0

    # Scenario 7: Direct service call with unverified raw notice features MUST also fail with 0 external HTTP
    with legacy.SessionLocal() as db:
        t_user = db.get(legacy.User, teacher_id)
        for feat in ("homework_parse_vision", "homework_notice_vision"):
            with pytest.raises(HTTPException) as exc:
                homework_vision.recognize_image(legacy, db, t_user, jpeg, feature=feat, student_ids=(sid1,))
            assert exc.value.status_code == 403
            assert len(http_calls) == 0

    # Scenario 8: With external AI disabled, teacher manual entry, edit, and publish still work (0 external HTTP)
    with legacy.SessionLocal() as db:
        cfg = legacy.ai_config_for(db, school_id, True)
        cfg.enabled = False
        db.commit()

    created = client.post(
        "/teacher/homework/notices",
        headers=t_headers,
        json={
            "groupLabel": "五(1)班",
            "items": [{"seq": 1, "subject": "数学", "content": "口算第5页", "page": "P5", "requirement": "独立完成"}],
        },
    )
    assert created.status_code == 200, created.text
    nid = created.json()["id"]
    edited = client.put(
        f"/teacher/homework/notices/{nid}",
        headers=t_headers,
        json={
            "groupLabel": "五(1)班",
            "items": [{"seq": 1, "subject": "数学", "content": "口算第5-6页", "page": "P5-6", "requirement": "家长核对"}],
        },
    )
    assert edited.status_code == 200, edited.text
    published = client.post(
        f"/teacher/homework/notices/{nid}/publish",
        headers=t_headers,
        json={"studentIDs": [sid1]},
    )
    assert published.status_code == 200, published.text
    assert len(http_calls) == 0
