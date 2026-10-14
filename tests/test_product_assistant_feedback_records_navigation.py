"""反馈 #316 回归测试：产品助手必须能把用户导航到明确的反馈记录功能界面。

验证两点：
1. 用户询问“反馈记录”时，助手导航卡片返回 feedback_records 卡片，指向可打开的反馈记录页面路径；
2. 未命中关键词时，feedback_records 也参与默认引导卡片集合，反馈记录入口始终可被发现。
"""
from changying.web.v1_product_assistant import _guidance_cards


def test_feedback_records_card_returned_for_records_query():
    cards = _guidance_cards("我在哪里可以看到我提交过的反馈记录和回执？", "/v1/workspace")
    assert any(
        card["key"] == "feedback_records"
        and card["path"] == "/v1/feedback"
        and "反馈记录" in card["title"]
        for card in cards
    ), cards


def test_feedback_records_card_title_and_description_not_placeholder():
    cards = _guidance_cards("反馈记录", "")
    card = next((c for c in cards if c["key"] == "feedback_records"), None)
    assert card is not None
    assert card["title"].strip()
    assert card["description"].strip()
    assert card["path"].startswith("/v1")


def test_students_and_parents_never_get_teacher_navigation_cards():
    teacher_only = {"current_teaching", "student_profile", "homework_create", "targeted_practice",
                    "classroom_review", "history_transition", "catalog_questions", "paper_import_saved"}
    questions = ["这题考什么？", "这道题怎么想", "我的作业在哪里", "今天要上课吗", "布置作业", "练习", "学情和错题"]
    for role in ("student", "parent"):
        for question in questions:
            keys = {c["key"] for c in _guidance_cards(question, "/classic", role=role)}
            assert not keys & teacher_only, (role, question, keys)
        # A question about their own work is not a navigation request.
        assert _guidance_cards("这题考什么？", "/classic", role=role) == []
        # Product-help cards that everyone can open are still offered.
        assert any(c["key"] == "feedback_records" for c in _guidance_cards("反馈记录", "", role=role))


def test_teachers_keep_their_navigation_cards():
    assert [c["key"] for c in _guidance_cards("这题考什么？", "/v1", role="teacher")] == ["current_teaching", "student_profile", "feedback"]
    assert _guidance_cards("布置作业在哪里？", "/v1", role="teacher")[0]["key"] == "homework_create"


def test_administrators_get_admin_cards_not_teacher_pages():
    teacher_only = {"current_teaching", "student_profile", "homework_create", "targeted_practice",
                    "classroom_review", "history_transition"}
    for role in ("admin", "school_admin"):
        assert [c["key"] for c in _guidance_cards("AI设置怎么配置", "/classic", role=role)] == ["admin_ai"]
        assert [c["key"] for c in _guidance_cards("怎么重置教师密码", "/classic", role=role)] == ["admin_users"]
        assert [c["key"] for c in _guidance_cards("套餐什么时候到期", "/classic", role=role)] == ["admin_subscription"]
        # No navigation request: no cards at all (never the teacher default).
        assert _guidance_cards("这个页面是干什么的", "/classic", role=role) == []
        for question in ("这题考什么", "今天上课", "布置作业", "学生档案", "怎么用"):
            assert not {c["key"] for c in _guidance_cards(question, "/classic", role=role)} & teacher_only
    # "mainstream" must not trigger the AI card just because it contains the letters "ai".
    assert _guidance_cards("mainstream", "", role="admin") == []
    assert all(c["path"].startswith("/v1/tool?page=") for c in _guidance_cards("账号 积分 审计 系统 套餐 批量导入", "", limit=8, role="admin"))
