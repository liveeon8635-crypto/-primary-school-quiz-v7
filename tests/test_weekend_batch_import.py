from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from changying.services.lesson_import import detect_lesson_no

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("batch_import_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_detect_lesson_no_reads_the_name_and_never_a_date():
    assert detect_lesson_no("第03课-民间故事.docx") == 3
    assert detect_lesson_no("语文 第 12 课.pptx") == 12
    assert detect_lesson_no("lesson-07.pdf") == 7
    assert detect_lesson_no("07-作文.txt") == 7
    assert detect_lesson_no("课次9 说明.md") == 9
    # A date must never be read as a lesson number, and out-of-range numbers are ignored.
    assert detect_lesson_no("2026-10-26 教案.docx") is None
    assert detect_lesson_no("第19课.docx") is None
    assert detect_lesson_no("教案.docx") is None
    assert detect_lesson_no("") is None


def test_batch_import_imports_every_named_file_and_reports_the_rest(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
import io, zipfile
from html import escape

def docx(lines):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('[Content_Types].xml', '<Types/>')
        z.writestr('word/document.xml', '<w:document>' + ''.join(
            '<w:p><w:r><w:t>' + escape(line) + '</w:t></w:r></w:p>' for line in lines) + '</w:document>')
    return buf.getvalue()

def plan(n):
    return docx([f'第{n}课 教案', '本节目标：练习。', '这是老师自己写的教案正文，需要完整保留。' * 40])

def reply(title):
    return json.dumps({'title': title, 'coreTarget': '本节目标', 'teacherPlan': '教学流程',
                       'ppt': ['讲解页' + title], 'examples': ['例题' + title], 'closureTraining': '课后练习',
                       'questions': [], 'writtenQuestions': []}, ensure_ascii=False)

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    files = [('files', (f'第{n:02d}课.docx', plan(n), 'application/octet-stream')) for n in (1, 2, 3)]
    files.append(('files', ('教案没有课次.docx', plan(4), 'application/octet-stream')))

    # Preview reads every file but writes nothing and calls no model.
    r = client.post('/teacher/weekend/lessons/import/preview', headers=th, data={'subject': '语文', 'courseType':'reading'}, files=files)
    assert r.status_code == 200, r.text
    preview = r.json()
    assert [i['lessonNo'] for i in preview['items']] == [1, 2, 3, None]
    assert preview['detected'] == 3 and preview['ready'] == 3
    assert all(i['ok'] for i in preview['items'])
    assert not calls, 'preview must not call the model'
    assert not any(row['hasPlan'] for row in client.get('/teacher/weekend/schedule?subject=语文', headers=th).json()['items'])

    # The batch imports the three named files and reports the unnamed one without stopping.
    replies.extend([reply('第一课'), reply('第二课'), reply('第三课')])
    r = client.post('/teacher/weekend/lessons/import/batch', headers=th, data={'subject': '语文', 'courseType':'reading'}, files=files)
    assert r.status_code == 200, r.text
    got = r.json()
    assert got['imported'] == 3 and got['failed'] == 1, got
    assert [i['lessonNo'] for i in got['items']] == [1, 2, 3, None]
    assert got['items'][3]['ok'] is False and '课次' in got['items'][3]['error']
    assert len(calls) == 3

    # Each imported lesson kept its own complete original text.
    schedule = client.get('/teacher/weekend/schedule?subject=语文', headers=th).json()
    by_no = {row['lessonNo']: row['lessonId'] for row in schedule['items'] if row['hasPlan']}
    assert sorted(by_no) == [1, 2, 3], by_no
    for lesson_id in by_no.values():
        detail = client.get(f'/teacher/weekend/lessons/{lesson_id}', headers=th).json()
        assert '这是老师自己写的教案正文，需要完整保留。' in detail['sourceText']

    # Without force an existing plan is refused per file and the stored lesson is untouched.
    before = client.get(f"/teacher/weekend/lessons/{by_no[1]}", headers=th).json()
    r = client.post('/teacher/weekend/lessons/import/batch', headers=th, data={'subject': '语文', 'courseType':'reading'}, files=files[:2])
    assert r.status_code == 200, r.text
    again = r.json()
    assert again['imported'] == 0 and again['failed'] == 2
    assert all('已经有教案' in i['error'] for i in again['items']), again['items']
    after = client.get(f"/teacher/weekend/lessons/{by_no[1]}", headers=th).json()
    assert after['sourceText'] == before['sourceText']
print('OK')
''')


def test_batch_import_rejects_a_non_lesson_plan_without_failing_the_batch(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
import io, zipfile
from html import escape

def docx(lines):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('[Content_Types].xml', '<Types/>')
        z.writestr('word/document.xml', '<w:document>' + ''.join(
            '<w:p><w:r><w:t>' + escape(line) + '</w:t></w:r></w:p>' for line in lines) + '</w:document>')
    return buf.getvalue()

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    good = docx(['第05课 教案', '本节目标：练习。', '这是老师自己写的教案正文，需要完整保留。' * 40])
    blank = docx(['短'])
    replies.append(json.dumps({'title': '第五课', 'coreTarget': '本节目标', 'teacherPlan': '流程', 'ppt': [],
                               'examples': ['例题'], 'closureTraining': '练习', 'questions': [],
                               'writtenQuestions': []}, ensure_ascii=False))
    files = [('files', ('第05课.docx', good, 'application/octet-stream')),
             ('files', ('第06课.docx', blank, 'application/octet-stream'))]
    r = client.post('/teacher/weekend/lessons/import/batch', headers=th, data={'subject': '数学'}, files=files)
    assert r.status_code == 200, r.text
    got = r.json()
    assert got['imported'] == 1 and got['failed'] == 1, got
    assert got['items'][0]['ok'] is True and got['items'][0]['lessonNo'] == 5
    assert got['items'][1]['ok'] is False and got['items'][1]['lessonNo'] == 6
    assert '没有读到足够的文字' in got['items'][1]['error']
    assert len(calls) == 1, 'the unreadable file must not reach the model'
print('OK')
''')
