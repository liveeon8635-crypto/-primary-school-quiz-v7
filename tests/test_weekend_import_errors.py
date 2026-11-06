from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("weekend_import_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_a_rejected_lesson_upload_says_why_and_is_logged(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
import io
import logging
import zipfile
from html import escape

records = []


class Capture(logging.Handler):
    def emit(self, record):
        records.append(record.getMessage())


logger = logging.getLogger('changying.weekend_lesson_import')
logger.addHandler(Capture())
logger.setLevel(logging.WARNING)


def docx(lines):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('[Content_Types].xml', '<Types/>')
        z.writestr('word/document.xml', '<w:document>' + ''.join(
            '<w:p><w:r><w:t>' + escape(line) + '</w:t></w:r></w:p>' for line in lines) + '</w:document>')
    return buf.getvalue()


PLAN = docx(['第10课 教案', '本节目标：小数乘法。', '这是老师自己写的教案正文，需要完整保留。' * 10])

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)

    # 1. Legacy .doc: refused before any extraction or model call, naming the file and the fix.
    r = client.post('/teacher/weekend/lessons/import', headers=th,
                    data={'subject': '语文', 'lessonNo': '3'},
                    files={'file': ('第03课-教案.doc', b'\xd0\xcf\x11\xe0' + b'\x00' * 64, 'application/msword')})
    assert r.status_code == 400, r.text
    detail = r.json()['detail']
    assert '《第03课-教案.doc》' in detail and '.doc 格式' in detail and '另存为' in detail, detail

    # 2. A .docx that is not a readable Office package keeps its reason and gains a hint.
    r = client.post('/teacher/weekend/lessons/import', headers=th,
                    data={'subject': '语文', 'lessonNo': '4'},
                    files={'file': ('第04课.docx', b'not a zip file', 'application/octet-stream')})
    assert r.status_code == 400, r.text
    detail = r.json()['detail']
    assert 'Office 文件损坏' in detail and '另存为' in detail, detail

    # 3. Every refusal is traceable in the server log: which file, why. Otherwise production
    #    only shows "400" and a teacher's report cannot be answered.
    joined = '\n'.join(records)
    assert '第03课-教案.doc' in joined and '.doc 格式' in joined, joined
    assert '第04课.docx' in joined and 'Office 文件损坏' in joined, joined
    assert 'status=400' in joined, joined

    # 4. Nothing was written: the lesson still has no plan.
    schedule = client.get('/teacher/weekend/schedule?subject=语文', headers=th).json()
    assert not any(row['hasPlan'] for row in schedule['items'])

    # 5. Preview reports the same reasons per file (no model call), and the message names the
    #    file whose suffix was rejected. Download-manager suffixes with a trailing space work.
    r = client.post('/teacher/weekend/lessons/import/preview', headers=th, data={'subject': '语文'}, files=[
        ('files', ('第10课.docx ', PLAN, 'application/octet-stream')),
        ('files', ('第11课', PLAN, 'application/octet-stream')),
        ('files', ('第12课.wps', PLAN, 'application/octet-stream')),
    ])
    assert r.status_code == 200, r.text
    items = r.json()['items']
    assert items[0]['ok'] is True and items[0]['chars'] > 0, items[0]
    assert '没有扩展名' in items[1]['error'] and '《第11课》' in items[1]['error'], items[1]
    assert '.wps' in items[2]['error'] and '另存为' in items[2]['error'], items[2]

print('OK')
''')
