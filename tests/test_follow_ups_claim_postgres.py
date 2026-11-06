"""PostgreSQL 并发 claim 测试骨架（可选）。

背景与设计说明：
1. 为什么需要此测试骨架？
   在晚托作业助手的待跟进功能中（/teacher/homework/follow-ups/claim），
   服务端在进入名额分配逻辑前执行：
       select(User.id).where(User.id == u.id).with_for_update()
   通过在事务内对教师行加排他行级锁（FOR UPDATE），确保多设备或并发请求按序排队，
   后执行的请求能够读取到先执行者已落库的 AuditLog 名额记录，防止并发竞态导致超额放行。
2. CI 为什么默认跳过？
   CI 流程运行于 SQLite 内存/临时文件库上。SQLite 的锁机制与 PostgreSQL 不同
   （SQLAlchemy 中 SQLite 的 with_for_update() 为 no-op），无法在多连接环境下
   真实检验行级锁排队效果。
3. 如何在独立环境中执行？
   - 准备专用的隔离 PostgreSQL 数据库（例如本地 Docker 或隔离的本地开发库）。
   - 设置环境变量：
     export TEST_POSTGRES_URL="postgresql://user:pass@localhost:5432/changying_test"
     export HOMEWORK_ASSISTANT="1"
   - 执行测试：
     pytest tests/test_follow_ups_claim_postgres.py
4. 安全红线（严格遵守 AGENTS.md §2 与 §6）：
   - 严禁配置或连接 Render/生产环境的 PostgreSQL 数据库！
   - 测试运行前会自动检测连接字符串特征并进行防呆拦截。
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import threading
from datetime import datetime, timedelta
from typing import Any

import pytest

# 读取测试连接配置
_RAW_URL = os.environ.get("TEST_POSTGRES_URL", "").strip()
if not (_RAW_URL.startswith("postgres://") or _RAW_URL.startswith("postgresql://")):
    # 仅当 DATABASE_URL 明确不是 conftest 注入的 sqlite 时才回退检测
    _DB_ENV = os.environ.get("DATABASE_URL", "").strip()
    if _DB_ENV.startswith("postgres://") or _DB_ENV.startswith("postgresql://"):
        _RAW_URL = _DB_ENV

_HAS_POSTGRES = _RAW_URL.startswith("postgres://") or _RAW_URL.startswith("postgresql://")

# 安全防呆拦截：禁止任何包含云端/生产标识的数据库连接
if _HAS_POSTGRES:
    _LOWER_URL = _RAW_URL.lower()
    _PROD_MARKERS = ("render.com", "oregon-postgres", "frankfurt-postgres", "dpg-", "prod")
    if any(m in _LOWER_URL for m in _PROD_MARKERS):
        raise RuntimeError("【安全拦截】检测到潜在生产 PostgreSQL 连接特征，测试已紧急终止！")


def _login_and_change(client: Any, username: str, old_pw: str, new_pw: str) -> str:
    login = client.post("/login", json={"username": username, "password": old_pw, "remember": False})
    assert login.status_code == 200, login.text
    token = login.json()["token"]
    changed = client.post(
        "/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": old_pw, "new_password": new_pw, "remember": False},
    )
    assert changed.status_code == 200, changed.text
    return changed.json()["token"]


@pytest.mark.skipif(
    not _HAS_POSTGRES,
    reason=(
        "CI 默认使用 SQLite（with_for_update 为 no-op）；"
        "真实验证行级锁并发需提供隔离的 PostgreSQL 测试库（设置 TEST_POSTGRES_URL）。"
        "严禁连接生产数据库！"
    ),
)
def test_concurrent_follow_ups_claim_postgres():
    """验证两个并发客户端同时请求 claim 时，同班名额严格受限且幂等。"""
    os.environ["DATABASE_URL"] = _RAW_URL
    os.environ["HOMEWORK_ASSISTANT"] = "1"

    import app_v924 as legacy
    from app import app
    from fastapi.testclient import TestClient
    from sqlalchemy import insert, select

    with TestClient(app) as client:
        # 获取教师账号 token
        token1 = _login_and_change(client, "teacher1", "123456", "Teacher1234")
        token2 = client.post("/login", json={"username": "teacher1", "password": "Teacher1234", "remember": False}).json()["token"]
        th1 = {"Authorization": f"Bearer {token1}"}
        th2 = {"Authorization": f"Bearer {token2}"}

        teacher_id = client.get("/session", headers=th1).json()["userID"]

        with legacy.SessionLocal() as db:
            teacher_user = db.get(legacy.User, teacher_id)
            school_id = teacher_user.school_id
            # 找到或建立测试班级
            cls = db.scalar(
                select(legacy.SchoolClass).where(legacy.SchoolClass.teacher_id == teacher_id).limit(1)
            )
            if not cls:
                cls = legacy.SchoolClass(school_id=school_id, name="并发测试班", grade=3, teacher_id=teacher_id)
                db.add(cls)
                db.flush()
            class_id = cls.id
            db.commit()

        # 在测试班中添加 6 名学生
        helps_tbl = legacy.Base.metadata.tables["help_requests"]
        base_time = datetime.utcnow()
        student_ids: list[int] = []

        with legacy.SessionLocal() as db:
            for i in range(6):
                name = f"pg_conc_pupil_{i}_{int(base_time.timestamp())}"
                pupil = legacy.User(
                    school_id=school_id,
                    username=name,
                    password_hash=legacy.hash_password("123456"),
                    name=name,
                    role="student",
                    grade=3,
                )
                db.add(pupil)
                db.flush()
                db.add(legacy.ClassStudent(class_id=class_id, student_id=pupil.id))
                student_ids.append(int(pupil.id))
            db.commit()

        # 为每个学生各生成一条待跟进求助记录（escalated 状态）
        with legacy.SessionLocal() as db:
            for idx, sid in enumerate(student_ids):
                db.execute(
                    insert(helps_tbl).values(
                        school_id=school_id,
                        student_id=sid,
                        grade=3,
                        question_text=f"并发测试题_{idx}",
                        state="escalated",
                        escalate_reason="student_request",
                        escalated_at=base_time + timedelta(minutes=idx * 5),
                    )
                )
            db.commit()

        # 两个并发客户端同时触发 claim
        barrier = threading.Barrier(2)

        def _do_claim(headers: dict[str, str]):
            # 建立独立的 TestClient 模拟并发 HTTP 连接
            with TestClient(app) as c:
                barrier.wait(timeout=10)
                return c.post("/teacher/homework/follow-ups/claim", headers=headers)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(_do_claim, th1)
            f2 = executor.submit(_do_claim, th2)
            resp1 = f1.result()
            resp2 = f2.result()

        assert resp1.status_code == 200, resp1.text
        assert resp2.status_code == 200, resp2.text

        data1 = resp1.json()
        data2 = resp2.json()

        class_set = set(student_ids)
        admitted1 = {x["studentID"] for x in data1.get("items", []) if x["studentID"] in class_set}
        admitted2 = {x["studentID"] for x in data2.get("items", []) if x["studentID"] in class_set}

        # 核心断言 1：同班获准学生去重后的并集不得超过 5 人（FOLLOW_UP_DAILY_LIMIT）
        union_admitted = admitted1 | admitted2
        assert len(union_admitted) <= 5, f"并发 claim 突破了单班 5 条上限: {union_admitted}"
        assert student_ids[5] not in union_admitted, "第 6 名学生不应被并发漏出"

        # 核心断言 2：第二次 claim 不新增名额（recorded 为空）
        resp_after = client.post("/teacher/homework/follow-ups/claim", headers=th1)
        assert resp_after.status_code == 200
        data_after = resp_after.json()
        assert data_after.get("recorded") == [], "第二次 claim 不应再新增占用名额"

        # 核心断言 3：重复 claim 幂等（返回的学生集合与已获准一致）
        after_admitted = {x["studentID"] for x in data_after.get("items", []) if x["studentID"] in class_set}
        assert after_admitted == union_admitted, "重复 claim 结果应保持一致与幂等"
