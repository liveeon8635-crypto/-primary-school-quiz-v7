from changying.web.v1_audit_localization import (
    V1_AUDIT_LOCALIZATION_MARKER,
    patch_v1_audit_localization,
)


def test_audit_localization_adds_business_labels_without_write_semantics():
    html = patch_v1_audit_localization("<html><body><iframe id='toolFrame'></iframe></body></html>")

    assert V1_AUDIT_LOCALIZATION_MARKER in html
    assert "记录学生积分" in html
    assert "发放自动奖励" in html
    assert "取消自动奖励" in html
    assert "新建班级积分规则" in html
    assert "修改班级积分规则" in html
    assert "生成 AI 教学内容" in html
    assert "原始事件：" in html
    assert "原始记录：" in html
    assert "fetch(" not in html
    assert "POST" not in html
    assert "PUT" not in html
    assert "DELETE" not in html


def test_audit_localization_is_idempotent():
    once = patch_v1_audit_localization("<body></body>")
    twice = patch_v1_audit_localization(once)
    assert once == twice
