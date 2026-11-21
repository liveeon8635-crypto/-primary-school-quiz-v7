"""Dedicated document consent is independent from student-data permission."""
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from changying.services import guardian_consent as consent

spec = importlib.util.spec_from_file_location("document_egress_helpers", Path(__file__).with_name("test_homework_solve.py"))
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


@pytest.mark.parametrize("images", [None, ["data:image/png;base64,AAAA"]])
def test_document_guard_requires_dedicated_permission(monkeypatch, images):
    calls = []
    student_checks = []
    impl = SimpleNamespace(_ai_call=lambda *a, **kw: calls.append(kw))
    user = SimpleNamespace(id=2, school_id=1, role="teacher")
    monkeypatch.delenv("TEACHING_DOCUMENT_AI_EGRESS_APPROVED", raising=False)
    monkeypatch.setattr(consent, "require_student_ai_authorized", lambda *a, **kw: student_checks.append(kw))
    consent.install_ai_egress_guard(impl)
    for ids in ((), (3,)):
        with pytest.raises(HTTPException) as exc:
            impl._ai_call(None, user, "weekend_lesson_draft", "教师原文", images=images, student_ids=ids)
        assert exc.value.status_code == 403
    assert calls == student_checks == []
    monkeypatch.setenv("TEACHING_DOCUMENT_AI_EGRESS_APPROVED", "1")
    impl._ai_call(None, user, "weekend_lesson_draft", "教师原文", images=images)
    assert len(calls) == 1 and not student_checks
    impl._ai_call(None, user, "weekend_lesson_draft", "含学生内容", images=images, student_ids=(3,))
    assert len(student_checks) == 1


def test_math_document_import_defaults_local_even_when_student_switch_enabled(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
os.environ.pop("TEACHING_DOCUMENT_AI_EGRESS_APPROVED", None)
with TestClient(app) as client:
    th, sh, student, school = setup(client)
    source = "构造普通数学教案\n观察规律，先独立尝试，再讨论方法。完整原文结束。"
    result = client.post('/teacher/weekend/lessons/import', headers=th,
        data={"subject":"数学","lessonNo":"18","text":source})
    assert result.status_code == 200, result.text
    assert result.json()["importMode"] == "local" and not calls
    lid = result.json()["lessonId"]
    assert client.get(f'/teacher/weekend/lessons/{lid}',headers=th).json()["sourceText"] == source
    print("OK")
''')
