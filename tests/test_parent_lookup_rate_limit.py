"""Exact parent lookup is limited per authenticated teacher, not only in the UI."""
from sqlalchemy import select

from tests.test_teacher_parent_scope import client, _class, _login, _school, _student, _suffix, _teacher, PASSWORD


def test_lookup_limit_scope_audit_and_authorization(client):
    import app_v924 as legacy

    admin = _school(client)
    teacher = _teacher(client, admin)
    other_teacher = _teacher(client, admin)
    no_class_teacher = _teacher(client, admin)
    _class(client, teacher, "教师本人班")
    cls = _class(client, other_teacher, "隔离班")
    student = _student(client, other_teacher, cls["id"], "测试学生")
    parent_account = "parent-" + _suffix()
    created = client.post("/admin/users", headers=admin, json={"name": "测试家长", "username": parent_account,
        "password": PASSWORD, "role": "parent"})
    assert created.status_code == 200
    parent = created.json()
    assert client.get("/teacher/parents", headers=no_class_teacher, params={"q": parent_account}).status_code == 403
    assert client.post("/teacher/parents/lookup", headers=no_class_teacher, json={"username": parent_account}).status_code == 403
    other_school = _school(client)
    other_parent_account = "other-parent-" + _suffix()
    assert client.post("/admin/users", headers=other_school, json={"name": "外校家长", "username": other_parent_account,
        "password": PASSWORD, "role": "parent"}).status_code == 200

    assert client.get("/teacher/parents", headers=teacher, params={"q": other_parent_account}).json() == []
    assert client.get("/teacher/parents", headers=teacher, params={"q": "not-a-real-parent"}).json() == []
    found = client.get("/teacher/parents", headers=teacher, params={"q": parent_account})
    assert found.status_code == 200 and [x["id"] for x in found.json()] == [parent["id"]]
    exact_post = client.post("/teacher/parents/lookup", headers=teacher, json={"username": parent_account})
    assert exact_post.status_code == 200 and [x["id"] for x in exact_post.json()] == [parent["id"]]
    for i in range(6):
        assert client.get("/teacher/parents", headers=teacher, params={"q": f"synthetic-guess-{i}"}).status_code == 200
    assert client.get("/teacher/parents", headers=teacher, params={"q": parent_account}).status_code == 429
    assert client.post("/teacher/parents/lookup", headers=teacher, json={"username": parent_account}).status_code == 429
    assert client.get("/teacher/parents", headers=teacher).status_code == 200
    # The other teacher's independent budget and legitimate binding still work.
    assert client.get("/teacher/parents", headers=other_teacher, params={"q": parent_account}).status_code == 200
    assert client.post(f"/teacher/students/{student['id']}/parent", headers=other_teacher,
                       json={"parent_id": parent["id"]}).status_code == 200
    assert client.post(f"/teacher/students/{student['id']}/parent", headers=teacher,
                       json={"parent_id": parent["id"]}).status_code == 403
    parent_headers = _login(client, parent_account)
    assert client.get("/teacher/parents", headers=parent_headers, params={"q": parent_account}).status_code == 403
    assert client.post("/teacher/parents/lookup", headers=parent_headers, json={"username": parent_account}).status_code == 403
    student_headers = _login(client, student["username"])
    assert client.get("/teacher/parents", headers=student_headers, params={"q": parent_account}).status_code == 403
    assert client.get("/teacher/parents", params={"q": parent_account}).status_code == 401
    assert client.post("/teacher/parents/lookup", headers=other_teacher, json={"username": "x" * 101}).status_code == 422
    assert client.get("/admin/users", headers=teacher).status_code == 403
    with legacy.SessionLocal() as db:
        logs = db.scalars(select(legacy.AuditLog).where(legacy.AuditLog.action.in_([
            "parent.lookup.attempt", "parent.lookup.limited"]))).all()
        assert sum(x.action == "parent.lookup.limited" for x in logs) == 1
        assert all(parent_account not in x.detail and other_parent_account not in x.detail for x in logs)


def test_expired_attempts_do_not_block_legitimate_lookup(client):
    from datetime import datetime, timedelta
    import app_v924 as legacy

    admin = _school(client)
    teacher = _teacher(client, admin)
    _class(client, teacher, "教师本人班")
    session = client.get("/session", headers=teacher).json()
    with legacy.SessionLocal() as db:
        user = db.get(legacy.User, session["userID"])
        db.add_all([legacy.AuditLog(school_id=user.school_id, user_id=user.id, action="parent.lookup.attempt",
                                  detail="exact account", created_at=datetime.utcnow() - timedelta(minutes=11)) for _ in range(10)])
        db.commit()
    assert client.get("/teacher/parents", headers=teacher, params={"q": "no-such-account"}).status_code == 200


def test_readonly_subscription_and_password_change_remain_enforced(client):
    import app_v924 as legacy

    admin = _school(client)
    teacher = _teacher(client, admin)
    _class(client, teacher, "教师本人班")
    session = client.get("/session", headers=teacher).json()
    with legacy.SessionLocal() as db:
        user = db.get(legacy.User, session["userID"])
        sub = db.scalar(select(legacy.SchoolSubscription).where(legacy.SchoolSubscription.school_id == user.school_id))
        sub.status = "expired"
        db.commit()
    assert client.get("/teacher/parents", headers=teacher, params={"q": "not-found"}).status_code == 200
    assert client.post("/teacher/parents/lookup", headers=teacher, json={"username": "not-found"}).status_code == 200
    assert client.post("/teacher/classes", headers=teacher, json={"name": "不应创建", "grade": 5}).status_code == 402
    with legacy.SessionLocal() as db:
        user = db.get(legacy.User, session["userID"])
        legacy.security_for(db, user).must_change_password = True
        db.commit()
    assert client.get("/teacher/parents", headers=teacher, params={"q": "not-found"}).status_code == 428
    assert client.post("/teacher/parents/lookup", headers=teacher, json={"username": "not-found"}).status_code == 428
