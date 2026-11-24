"""Regression tests for actionable作文整包课次校验反馈."""
import importlib.util
import sys
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "writing_import_helpers", Path(__file__).with_name("test_homework_solve.py")
)
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_writing_bundle_import_explains_which_identity_does_not_match(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
import json
from fastapi.testclient import TestClient
from app import app

def upload(form_subject, form_lesson_no, file_subject, file_lesson_no):
    bundle = {
        'schemaVersion': 1,
        'subject': file_subject,
        'items': [{'lessonNo': file_lesson_no, 'writingPackage': {'title': '测试', 'nodes': []}}],
    }
    return client.post(
        '/teacher/weekend/lessons/import',
        headers=teacher_headers,
        data={'subject': form_subject, 'lessonNo': str(form_lesson_no), 'courseType': 'writing'},
        files={'file': ('writing.json', json.dumps(bundle, ensure_ascii=False).encode(), 'application/json')},
    )

with TestClient(app) as client:
    teacher_headers, _, _, _ = setup(client)

    wrong_workbench_subject = upload('数学', 13, '语文', 13)
    assert wrong_workbench_subject.status_code == 422
    assert '只能导入语文课程' in wrong_workbench_subject.text
    assert '数学' in wrong_workbench_subject.text and '第 13 次' in wrong_workbench_subject.text

    wrong_file_subject = upload('语文', 13, '数学', 13)
    assert wrong_file_subject.status_code == 422
    assert '文件标记学科为“数学”' in wrong_file_subject.text
    assert '当前工作栏为“语文”第 13 次' in wrong_file_subject.text

    wrong_file_lesson = upload('语文', 13, '语文', 12)
    assert wrong_file_lesson.status_code == 422
    assert '文件标记第 12 次课' in wrong_file_lesson.text
    assert '当前工作栏是第 13 次课' in wrong_file_lesson.text
    print('OK writing bundle identity mismatches are explicit')
''')
