from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
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
    assert 'data-feedback-ui-revision="3"' in html
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
    assert "data-cy-fc-ack" in html
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

        freeman_state.update({
            "status": "selected",
            "operatorReply": "反馈已取用，正在处理。",
        })
        adopted = client.get(FEEDBACK_MINE_PATH)
        assert adopted.status_code == 200
        adopted_payload = adopted.json()
        adopted_record = adopted_payload["records"][0]
        assert adopted_record["rewardStatus"] == "granted"
        assert adopted_record["rewardPoints"] == 1
        assert adopted_payload["rewardSummary"]["earnedPoints"] == 1
        with session_factory() as db:
            reward = db.execute(select(reward_table)).mappings().one()
            assert reward["status"] == "granted"
            assert reward["points"] == 1

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
    assert 'data-feedback-ui-revision="3"' in html
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
    assert "验收完成 · 返回" in backend
    assert "已处理 · 点击去验收" in backend
    assert "const reviewHref=record=>" in center
    assert "已处理 · 点击去验收" in center
    assert "确认已达预期" in center
    assert "追加反馈" in center
    assert "cy_feedback_return" in center


def test_feedback_confirmation_is_offered_whenever_awaiting_user_confirmation():
    # Feedback #348: confirmation no longer depends on returning via the review bar.
    from pathlib import Path
    backend = Path("changying/web/v1_product_assistant.py").read_text(encoding="utf-8")
    center = Path("changying/web/feedback_center.js").read_text(encoding="utf-8")
    assert "reviewed='+encodeURIComponent" in backend
    assert "验收完成 · 返回" in backend
    assert "已处理 · 点击去验收" in backend
    assert "(canConfirm?'<button class=\"btn primary\" type=\"button\" data-pa-confirm-feedback=" in backend
    assert "reviewed&&canConfirm" not in backend
    assert "(reviewed||canConfirm)&&canFollow" in backend
    assert "reviewed='+encodeURIComponent" in center
    assert "已处理 · 点击去验收" in center
    assert "(canConfirm&&own?'<button class=\"green\" data-cy-fc-ack=" in center
    assert "reviewed&&canConfirm" not in center


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
    }) == "/v1/feedback"
    assert _feedback_acceptance_path({
        "page": "/v1/workspace",
        "message": "一个无法匹配具体功能的普通界面建议",
        "followUps": [],
    }) == "/v1/feedback"
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


def test_feedback_review_link_remains_available_after_returning():
    from pathlib import Path
    backend = Path("changying/web/v1_product_assistant.py").read_text(encoding="utf-8")
    center = Path("changying/web/feedback_center.js").read_text(encoding="utf-8")
    assert "reviewed?'重新去验收':'已处理 · 点击去验收'" in backend
    assert "reviewed?'重新去验收':'已处理 · 点击去验收'" in center


def test_acceptance_target_prefers_assistant_navigation_over_generic_student_word():
    from changying.web.v1_product_assistant import _feedback_acceptance_path
    assert _feedback_acceptance_path({
        "page": "/v1/workspace",
        "message": "学生问助手产品功能时应该直接提供对应导航卡片，不要只给文字说明",
        "followUps": [],
    }) == "/v1/workspace?tab=ask"


def test_specific_feedback_subject_overrides_raw_source_page_for_acceptance():
    from changying.web.v1_product_assistant import _feedback_acceptance_path
    assert _feedback_acceptance_path({
        "page": "/v1/student?id=10",
        "message": "学生问产品助手时应该直接给导航卡片，不要只显示文字说明",
        "followUps": [],
    }) == "/v1/workspace?tab=ask"


def test_feedback_review_return_focuses_exact_record():
    from pathlib import Path
    backend = Path("changying/web/v1_product_assistant.py").read_text(encoding="utf-8")
    center = Path("changying/web/feedback_center.js").read_text(encoding="utf-8")
    assert "&focus='+encodeURIComponent" in backend
    assert "get('focus')" in backend
    assert "scrollIntoView({behavior:'smooth',block:'center'})" in backend
    assert "&focus='+encodeURIComponent" in center
    assert "get('focus')" in center


def test_review_bar_routes_failed_acceptance_into_exact_followup_form():
    from pathlib import Path
    source = Path("changying/web/v1_product_assistant.py").read_text(encoding="utf-8")
    assert "未通过 · 追加反馈" in source
    assert "searchParams.set('followup',String(reviewId))" in source
    assert "params.get('followup')" in source
    assert "data-pa-followup-form" in source
    assert "form.hidden=false" in source
    assert "input?.focus()" in source


def test_feedback_309_reward_acceptance_ignores_unrelated_student_source_page():
    from changying.web.v1_product_assistant import _feedback_acceptance_path
    assert _feedback_acceptance_path({
        "page": "/v1/student?id=10",
        "message": "每提交一条反馈，被取用后对应增加1个反馈奖励分，可用于兑换账号时长，具体兑换比例后续确定",
        "followUps": [],
    }) == "/v1/feedback"


def test_dedicated_feedback_page_is_directly_reachable():
    response = TestClient(app).get("/v1/feedback")
    assert response.status_code == 200
    assert 'data-feedback-page="standalone"' in response.text
    assert "我的反馈记录" in response.text
    assert "处理回执" in response.text
    assert "反馈奖励分" in response.text
    assert "ChangyingFeedbackCenter.open()" in response.text
    assert response.headers["cache-control"].startswith("no-store")


def test_stale_feedback_review_link_self_heals_to_current_acceptance_target():
    from pathlib import Path
    source = Path("changying/web/v1_product_assistant.py").read_text(encoding="utf-8")
    assert "const repairFeedbackReviewTarget=async()=>{" in source
    assert "record.acceptanceUrl||record.page||'/v1/feedback'" in source
    assert "location.replace(target.pathname+target.search+target.hash)" in source
    assert "repairFeedbackReviewTarget().then" in source


def test_feedback_review_returns_to_assistant_history_with_exact_record_focus():
    from pathlib import Path
    backend = Path("changying/web/v1_product_assistant.py").read_text(encoding="utf-8")
    center = Path("changying/web/feedback_center.js").read_text(encoding="utf-8")
    expected = "/v1/workspace?tab=feedback-records&from=feedback&reviewed="
    assert expected in backend
    assert expected in center
    assert "cy-feedback-back-records" in backend
    assert "返回助手反馈记录" in backend
    assert "cyFeedbackId=cyFeedbackParams.get('cy_feedback_review')||cyFeedbackParams.get('reviewed')||cyFeedbackParams.get('focus')" in backend
    assert "cyFeedbackBack.href='/v1/workspace?tab=feedback-records&from=feedback&reviewed='" in backend


def test_feedback_page_workspace_return_does_not_reenter_tutorial_flow():
    response = TestClient(app).get("/v1/feedback")
    assert response.status_code == 200
    html = response.text
    assert 'id="cy-feedback-back-workspace"' in html
    assert 'href="/v1/workspace?from=feedback"' in html
    assert "cyFeedbackWorkspace.href='/v1/workspace?from=feedback'" in html
    assert "reviewed='+encodeURIComponent(cyFeedbackId)" in html


def test_standalone_feedback_fallback_keeps_feedback_origin_marker():
    from pathlib import Path
    center = Path("changying/web/feedback_center.js").read_text(encoding="utf-8")
    assert "location.href='/v1/workspace?tab=feedback&from=feedback'" in center
    assert "/v1/workspace?tab=feedback-records&from=feedback&reviewed=" in center


def test_feedback_review_bar_reserves_mobile_space_for_underlying_actions():
    from pathlib import Path
    source = Path("changying/web/v1_product_assistant.py").read_text(encoding="utf-8")
    assert "--cy-feedback-review-clearance" in source
    assert "getBoundingClientRect().height" in source
    assert "requestAnimationFrame(syncReviewClearance)" in source
