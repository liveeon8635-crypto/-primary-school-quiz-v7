from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import app
from changying.web.v1_product_assistant import FEEDBACK_MINE_PATH, FEEDBACK_PATH


def test_feedback_center_is_mounted_as_real_frontend_with_visible_entry_and_actions():
    response = TestClient(app).get("/v1")
    assert response.status_code == 200
    html = response.text

    assert 'id="changying-feedback-center-script"' in html
    assert "window.__cyFeedbackCenterInstalled=true" in html
    assert "feedbackCenterButton" in html
    assert "我的反馈记录" in html
    assert 'id="cy-feedback-center-modal"' in html
    assert "/v1/product-feedback/mine" in html
    assert "取用状态：" in html
    assert "处理回执" in html
    assert "奖励分：" in html
    assert "追加反馈" in html
    assert "查收（满意）" in html
    assert "/follow-up" in html
    assert "/acknowledge" in html


def test_feedback_center_backend_round_trip(monkeypatch):
    import app_v924 as implementation
    from changying.web import v1_product_assistant as assistant

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    attachment_table = implementation.Base.metadata.tables["product_feedback_attachments"]
    reward_table = implementation.Base.metadata.tables["product_feedback_rewards"]
    implementation.Base.metadata.create_all(
        engine,
        tables=[implementation.AuditLog.__table__, attachment_table, reward_table],
    )
    session_factory = sessionmaker(bind=engine)
    user = SimpleNamespace(id=51, school_id=9, role="teacher")

    def db_override():
        with session_factory() as db:
            yield db

    app.dependency_overrides[implementation.current_user] = lambda: user
    app.dependency_overrides[implementation.get_db] = db_override
    monkeypatch.setattr(assistant.requests, "post", lambda *args, **kwargs: Mock(ok=True))

    try:
        client = TestClient(app)
        submitted = client.post(
            FEEDBACK_PATH,
            json={
                "category": "希望增加功能",
                "message": "希望可以直接看到反馈处理回执",
                "page": "/v1/workspace",
                "identity": "机构老师",
            },
        )
        assert submitted.status_code == 200

        mine = client.get(FEEDBACK_MINE_PATH)
        assert mine.status_code == 200
        records = mine.json()["records"]
        assert len(records) == 1
        record = records[0]
        assert record["message"] == "希望可以直接看到反馈处理回执"
        assert record["statusLabel"] == "待处理"
        assert record["receipt"] == "已收到，等待处理回执"
        assert record["acknowledged"] is False

        with session_factory() as db:
            reward = db.execute(select(reward_table)).mappings().one()
            db.execute(
                update(reward_table)
                .where(reward_table.c.id == reward["id"])
                .values(status="granted")
            )
            db.commit()

        follow_up = client.post(
            f"{FEEDBACK_MINE_PATH}/{record['id']}/follow-up",
            json={"message": "补充：希望手机端也能直接进入"},
        )
        assert follow_up.status_code == 200
        assert follow_up.json()["followUps"][-1]["message"] == "补充：希望手机端也能直接进入"

        acknowledged = client.post(
            f"{FEEDBACK_MINE_PATH}/{record['id']}/acknowledge",
        )
        assert acknowledged.status_code == 200
        assert acknowledged.json()["acknowledged"] is True
        assert "确认满意" in acknowledged.json()["receipt"]

        refreshed = client.get(FEEDBACK_MINE_PATH)
        assert refreshed.status_code == 200
        item = refreshed.json()["records"][0]
        assert item["statusLabel"] == "已取用"
        assert item["rewardPoints"] == 1
        assert item["acknowledged"] is True
        assert "确认满意" in item["receipt"]
        assert item["followUps"][-1]["message"] == "补充：希望手机端也能直接进入"
    finally:
        app.dependency_overrides.pop(implementation.current_user, None)
        app.dependency_overrides.pop(implementation.get_db, None)
        engine.dispose()
