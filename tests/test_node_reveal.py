"""测试块四：node_reveal_states 服务层与 /v1/classroom/<session_id>/... Web 接口。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base, sessionmaker

from changying.services.node_identity import stable_node_id
from changying.services.node_reveal import (
    list_node_reveal,
    register_node_reveal_states_table,
    retract_node,
    reveal_node,
)

spec = importlib.util.spec_from_file_location("node_reveal_test_helpers", Path(__file__).with_name("test_homework_solve.py"))
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def _make_implementation():
    Base = declarative_base()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    impl = SimpleNamespace(Base=Base, engine=engine, SessionLocal=SessionLocal)
    register_node_reveal_states_table(impl)
    Base.metadata.create_all(engine)
    return impl


def test_service_reveal_retract_and_rereveal_preserves_single_row_and_unique_constraint():
    impl = _make_implementation()
    table = register_node_reveal_states_table(impl)
    cols = {c.name for c in table.columns}
    assert cols == {
        "id",
        "school_id",
        "classroom_session_id",
        "lesson_id",
        "class_id",
        "node_id",
        "reveal_level",
        "revealed_by",
        "revealed_at",
        "revoked_at",
        "revoke_reason",
    }

    nid = stable_node_id("hint", "q1", "提示一：注意中心句")
    s1 = reveal_node(
        501,
        nid,
        "hint",
        revealed_by=9,
        school_id=1,
        lesson_id=12,
        class_id=3,
        implementation=impl,
    )
    assert s1["classroom_session_id"] == 501
    assert s1["node_id"] == nid
    assert s1["reveal_level"] == "hint"
    assert s1["revoked_at"] is None
    assert s1["revoke_reason"] is None

    retracted = retract_node(501, nid, "先收回提示让学生独立思考", implementation=impl)
    assert retracted["id"] == s1["id"]
    assert retracted["revoked_at"] is not None
    assert retracted["revoke_reason"] == "先收回提示让学生独立思考"

    # 再次开放同一 (session, node)：revoked_at 置回 None，reveal_level 更新，不新增第二行
    rerevealed = reveal_node(501, nid, "answer", revealed_by=9, implementation=impl)
    assert rerevealed["id"] == s1["id"]
    assert rerevealed["reveal_level"] == "answer"
    assert rerevealed["revoked_at"] is None
    assert rerevealed["revoke_reason"] is None

    items = list_node_reveal(501, implementation=impl)
    assert len(items) == 1
    assert items[0]["id"] == s1["id"]
    assert items[0]["reveal_level"] == "answer"

    # UniqueConstraint(classroom_session_id, node_id)
    with impl.SessionLocal() as db:
        with pytest.raises(IntegrityError):
            db.execute(
                table.insert().values(
                    school_id=1,
                    classroom_session_id=501,
                    lesson_id=12,
                    class_id=3,
                    node_id=nid,
                    reveal_level="analysis",
                    revealed_by=9,
                )
            )
            db.commit()

    with pytest.raises(ValueError, match="开放层级不合法"):
        reveal_node(501, nid, "invalid_level", implementation=impl)

    with pytest.raises(LookupError, match="未找到该节点的开放记录"):
        retract_node(501, "missing_node", "撤回不存在记录", implementation=impl)


def test_web_node_reveal_retract_list_and_404_400_boundaries(tmp_path):
    helpers.run_isolated(
        tmp_path,
        helpers.COMMON
        + r"""
from changying.services.node_identity import stable_node_id

with TestClient(app) as client:
    th, sh, student_id, school_id = setup(client)
    sessions_tbl = legacy.Base.metadata.tables["classroom_sessions"]
    with legacy.SessionLocal() as db:
        teacher = db.scalar(select(legacy.User).where(legacy.User.username == "teacher1"))
        cls = db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id == school_id))
        lesson = db.scalar(select(legacy.TeachingLesson).where(legacy.TeachingLesson.school_id == school_id))
        sid = int(
            db.execute(
                sessions_tbl.insert()
                .values(
                    school_id=school_id,
                    class_id=cls.id if cls else 1,
                    teacher_id=teacher.id,
                    lesson_id=lesson.id if lesson else 1,
                    subject="语文",
                    title="语文第12课课堂",
                    status="active",
                )
                .returning(sessions_tbl.c.id)
            ).scalar_one()
        )
        db.commit()

    nid = stable_node_id("stem", "q1", "阅读短文并回答问题")

    # 1. session 不存在 -> 404
    r_missing_reveal = client.post(f"/v1/classroom/999999/nodes/{nid}/reveal", headers=th, json={"level": "hint"})
    assert r_missing_reveal.status_code == 404, r_missing_reveal.text
    r_missing_retract = client.post(f"/v1/classroom/999999/nodes/{nid}/retract", headers=th, json={"reason": "误触"})
    assert r_missing_retract.status_code == 404, r_missing_retract.text
    r_missing_list = client.get("/v1/classroom/999999/node-reveals", headers=th)
    assert r_missing_list.status_code == 404, r_missing_list.text

    # 2. level 非法 -> 400
    r_bad_level = client.post(f"/v1/classroom/{sid}/nodes/{nid}/reveal", headers=th, json={"level": "wrong_level"})
    assert r_bad_level.status_code == 400, r_bad_level.text
    r_empty_level = client.post(f"/v1/classroom/{sid}/nodes/{nid}/reveal", headers=th, json={})
    assert r_empty_level.status_code == 400, r_empty_level.text

    # 3. 学生无权调用教师课堂控制接口 -> 403
    r_student = client.post(f"/v1/classroom/{sid}/nodes/{nid}/reveal", headers=sh, json={"level": "hint"})
    assert r_student.status_code == 403, r_student.text

    # 4. reveal -> retract -> re-reveal 全链路与列表查询
    r_reveal1 = client.post(f"/v1/classroom/{sid}/nodes/{nid}/reveal", headers=th, json={"level": "hint"})
    assert r_reveal1.status_code == 200, r_reveal1.text
    d1 = r_reveal1.json()
    assert d1["classroom_session_id"] == sid
    assert d1["node_id"] == nid
    assert d1["reveal_level"] == "hint"
    assert d1["revoked_at"] is None

    r_retract = client.post(f"/v1/classroom/{sid}/nodes/{nid}/retract", headers=th, json={"reason": "撤回重讲"})
    assert r_retract.status_code == 200, r_retract.text
    d_ret = r_retract.json()
    assert d_ret["id"] == d1["id"]
    assert d_ret["revoked_at"] is not None
    assert d_ret["revoke_reason"] == "撤回重讲"

    r_reveal2 = client.post(f"/v1/classroom/{sid}/nodes/{nid}/reveal", headers=th, json={"level": "analysis"})
    assert r_reveal2.status_code == 200, r_reveal2.text
    d2 = r_reveal2.json()
    assert d2["id"] == d1["id"]
    assert d2["reveal_level"] == "analysis"
    assert d2["revoked_at"] is None
    assert d2["revoke_reason"] is None

    r_list = client.get(f"/v1/classroom/{sid}/node-reveals", headers=th)
    assert r_list.status_code == 200, r_list.text
    payload = r_list.json()
    assert payload["classroom_session_id"] == sid
    assert len(payload["items"]) == 1
    assert payload["items"][0]["node_id"] == nid
    assert payload["items"][0]["reveal_level"] == "analysis"
    assert payload["items"][0]["revoked_at"] is None
    print("OK")
""",
    )
