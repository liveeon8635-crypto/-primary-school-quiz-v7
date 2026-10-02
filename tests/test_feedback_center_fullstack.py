from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import app
from changying.web.v1_product_assistant import FEEDBACK_MINE_PATH, FEEDBACK_PATH


def test_feedback_center_is_mounted_only_through_assistant_dropdown_with_actions():
    response = TestClient(app).get("/v1")
    assert response.status_code == 200
    html = response.text

    assert 'id="changying-feedback-center-script"' in html
    assert "window.__cyFeedbackCenterInstalled=true" in html
    assert "feedbackCenterButton" not in html
    assert 'data-feedback-ui-revision="2"' in html
    assert 'id="cy-pa-feedback-menu-button"' in html
    assert ">提反馈 ▾</button>" in html
    assert 'data-pa-tab="feedback"' in html
    assert 'data-pa-tab="records"' in html
    assert 'id="cy-feedback-center-modal"' in html
    assert "/v1/product-feedback/mine" in html
    assert "取用状态：" in html
    assert "处理回执" in html
    assert "奖励分：" in html
    assert "追加反馈" in html
    assert "验收通过" in html
    assert "驳回" in html
    assert "/follow-up" in html
    assert "/acknowledge" in html
    assert "/reject" in html


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
        tables=[implementation.User.__table__, implementation.AuditLog.__table__, attachment_table, reward_table],
    )
    session_factory = sessionmaker(bind=engine)
    user = SimpleNamespace(id=51, school_id=9, role="teacher")

    def db_override():
        with session_factory() as db:
            yield db

    app.dependency_overrides[implementation.current_user] = lambda: user
    app.dependency_overrides[implementation.get_db] = db_override
    freeman_state = {"status": "", "operatorReply": "", "userDecision": None}
    def fake_post(url, *args, **kwargs):
        if url == assistant.FREEMAN_FEEDBACK_STATUS_URL:
            refs = (kwargs.get("json") or {}).get("refs") or []
            items = []
            if freeman_state["status"] and refs:
                items = [{
                    "sourceId": str(refs[0]["sourceId"]),
                    "status": freeman_state["status"],
                    "operatorReply": freeman_state["operatorReply"],
                    "userDecision": freeman_state["userDecision"],
                }]
            return Mock(ok=True, status_code=200, json=lambda: {"items": items})
        return Mock(ok=True, status_code=201)
    monkeypatch.setattr(assistant.requests, "post", fake_post)

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

        freeman_state.update({
            "status": "awaiting_acceptance",
            "operatorReply": "反馈已处理，请确认是否达到预期。",
        })
        acknowledged = client.post(
            f"{FEEDBACK_MINE_PATH}/{record['id']}/acknowledge",
        )
        assert acknowledged.status_code == 200
        assert acknowledged.json()["acknowledged"] is True
        assert "达到预期" in acknowledged.json()["receipt"]
        freeman_state["userDecision"] = {"status": "confirmed", "at": "2026-10-02T15:00:00Z"}

        refreshed = client.get(FEEDBACK_MINE_PATH)
        assert refreshed.status_code == 200
        item = refreshed.json()["records"][0]
        assert item["statusLabel"] == "已处理 · 待你确认"
        assert item["rewardPoints"] == 1
        assert item["acknowledged"] is True
        assert item["operatorReply"] == "反馈已处理，请确认是否达到预期。"
        assert item["userDecision"]["status"] == "confirmed"
        assert item["followUps"][-1]["message"] == "补充：希望手机端也能直接进入"
    finally:
        app.dependency_overrides.pop(implementation.current_user, None)
        app.dependency_overrides.pop(implementation.get_db, None)
        engine.dispose()


def test_feedback_ui_revision_is_present_in_unified_classic_final_html():
    from changying.web.v1_product_assistant import patch_v1_product_assistant

    classic = '<html><body><header><button>切换身份</button></header><main>classic</main></body></html>'
    html = patch_v1_product_assistant(classic)
    assert 'data-feedback-ui-revision="2"' in html
    assert 'id="cy-pa-feedback-menu-button"' in html
    assert '>提反馈 ▾</button>' in html
    assert 'data-pa-tab="feedback"' in html
    assert 'data-pa-tab="records"' in html
    assert 'feedbackCenterButton' not in html


def test_feedback_center_preserves_reward_and_followup_detail_in_merged_view():
    from pathlib import Path

    script = Path("changying/web/feedback_center.js").read_text(encoding="utf-8")
    assert "rewardPoints" in script
    assert "rewardStatus" in script
    assert "rewardSummary" in script
    assert 'data-cy-fc-reward="' in script
    assert "followUps" in script
    assert 'data-cy-fc-followups="' in script
    assert "追加反馈（" in script
    assert 'data-cy-fc-followup-toggle="' in script
    assert 'data-cy-fc-followup-submit="' in script
    assert "/follow-up" in script


def test_admin_feedback_records_are_school_scoped_but_actions_remain_owner_only():
    from pathlib import Path

    backend = Path("changying/web/v1_product_assistant.py").read_text(encoding="utf-8")
    frontend = Path("changying/web/feedback_center.js").read_text(encoding="utf-8")
    assert 'getattr(user, "role", "") != "admin"' in backend
    assert '"submittedBy"' in backend
    assert '"canFollowUp"' in backend
    assert "record.canFollowUp!==false" in frontend
    assert "提交人：" in frontend
    assert 'data-cy-fc-reward="' in frontend
    assert "追加反馈（" in frontend


def test_feedback_mine_backfills_status_token_for_pre_loop_feedback(monkeypatch):
    from pathlib import Path
    source = Path("changying/web/v1_product_assistant.py").read_text(encoding="utf-8")
    assert "Backfill pre-status-loop feedback cards lazily" in source
    assert 'missing_ids = [int(row.id) for row in rows if str(int(row.id)) not in freeman_status]' in source
    assert '_post_feedback_import(ref["statusToken"], int(ref["sourceId"]))' in source
    assert 'freeman_status.update(_freeman_feedback_status(refreshed_refs))' in source


def test_handled_feedback_links_to_original_context_before_user_confirmation():
    from pathlib import Path
    backend = Path("changying/web/v1_product_assistant.py").read_text(encoding="utf-8")
    center = Path("changying/web/feedback_center.js").read_text(encoding="utf-8")
    assert '"acceptanceUrl": _feedback_acceptance_path(detail)' in backend
    assert "cy_feedback_review" in backend
    assert "cy_feedback_return" in backend
    assert "返回反馈记录" in backend
    assert "已处理 · 点击去验收" in backend
    assert "const reviewHref=record=>" in center
    assert "已处理 · 点击去验收" in center
    assert "确认通过" in center
    assert "追加反馈" in center
    assert "cy_feedback_return" in center


def test_feedback_confirmation_is_gated_until_user_returns_from_review():
    from pathlib import Path
    backend = Path("changying/web/v1_product_assistant.py").read_text(encoding="utf-8")
    center = Path("changying/web/feedback_center.js").read_text(encoding="utf-8")
    assert "reviewed='+encodeURIComponent" in backend
    assert "验收完成，返回反馈记录" in backend
    assert "已处理 · 点击去验收" in backend
    assert "reviewed&&canConfirm" in backend
    assert "reviewed&&canFollow" in backend
    assert "reviewed='+encodeURIComponent" in center
    assert "已处理 · 点击去验收" in center
    assert "reviewed&&canConfirm" in center


def test_workspace_feedback_acceptance_targets_specific_product_surface():
    from changying.web.v1_product_assistant import _feedback_acceptance_path
    assert _feedback_acceptance_path({
        "page": "/v1/workspace?tab=feedback-records",
        "message": "学生测试与练习里面缺少难度选择",
        "followUps": [],
    }) == "/v1/student"
    assert _feedback_acceptance_path({
        "page": "/v1/workspace",
        "message": "顶部反馈记录和助手里的反馈记录应该合并",
        "followUps": [],
    }) == "/v1/workspace?tab=feedback-records"
    assert _feedback_acceptance_path({
        "page": "/v1/workspace",
        "message": "一个无法匹配具体功能的普通界面建议",
        "followUps": [],
    }) == "/v1/workspace?tab=feedback-records"
    assert _feedback_acceptance_path({
        "page": "/v1/classroom",
        "message": "这里有一个显示问题",
        "followUps": [],
    }) == "/v1/classroom"


def test_assistant_feedback_acceptance_targets_product_assistant():
    from changying.web.v1_product_assistant import _feedback_acceptance_path
    assert _feedback_acceptance_path({
        "page": "/v1/workspace",
        "message": "询问助手相关功能不能直接提供关联卡片 能不能提高助手的产品引导能力",
        "followUps": [],
    }) == "/v1/workspace?tab=ask"
