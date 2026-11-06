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
import logging

records = []


class Capture(logging.Handler):
    def emit(self, record):
        records.append(record.getMessage())


logger = logging.getLogger('changying.weekend_lesson_import')
logger.addHandler(Capture())
logger.setLevel(logging.WARNING)

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)

    # 1. Legacy .doc: refused before any extraction or model call, with a repair step.
    r = client.post('/teacher/weekend/lessons/import', headers=th,
                    data={'subject': '语文', 'lessonNo': '3'},
                    files={'file': ('第03课-教案.doc', b'\xd0\xcf\x11\xe0' + b'\x00' * 64, 'application/msword')})
    assert r.status_code == 400, r.text
    detail = r.json()['detail']
    assert '旧版 Word' in detail and '另存为' in detail, detail

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
    assert '第03课-教案.doc' in joined and '旧版 Word' in joined, joined
    assert '第04课.docx' in joined and 'Office 文件损坏' in joined, joined
    assert 'status=400' in joined, joined

    # 4. Nothing was written: the lesson still has no plan.
    schedule = client.get('/teacher/weekend/schedule?subject=语文', headers=th).json()
    assert not any(row['hasPlan'] for row in schedule['items'])

print('OK')
''')
