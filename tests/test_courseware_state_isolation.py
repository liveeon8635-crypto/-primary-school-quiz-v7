"""Playback state must belong to one page of one lesson, and previewing must not touch the classroom."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('state_helpers', ROOT / 'tests/test_weekend_backup.py')
b = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = b
spec.loader.exec_module(b)

SETUP = b.COMMON + r'''
from sqlalchemy import select
from changying.web.weekend_views import register_weekend_tables

def two_example_pages(client, th, lid):
    with legacy.SessionLocal() as db:
        lesson = db.get(legacy.TeachingLesson, lid)
        lesson.examples_json = json.dumps(['例题1：转动方法', '例题2：平移方法'], ensure_ascii=False)
        db.commit()
    pages = client.get('/teacher/weekend/lessons/' + str(lid) + '/courseware', headers=th).json()['pages'].get('3') or []
    return pages

STEPS = ['先看清题目里的条件', '找出每次增加的个数', '写出第 n 次的算式', '把数代进去检验']

def save_page(client, th, url, page, text):
    r = client.put(url, headers=th, json={'stageNo': 3, 'page': page, 'kind': 'steps',
        'params': {'problem': text[:40], 'steps': list(STEPS), 'answer': '答案' + str(page), 'figure': {}}, 'writtenTask': False})
    assert r.status_code == 200, r.text
    r = client.post(url + '/approve', headers=th, json={'stageNo': 3, 'page': page})
    assert r.status_code == 200, r.text

def live_step(client, th, base):
    body = client.get(base, headers=th).json()
    cw = body.get('courseware')
    return (cw or {}).get('view', {}).get('step'), cw, body.get('coursewareNotice')
'''


def test_each_page_keeps_its_own_step_counter(tmp_path):
    b.helpers.run_isolated(tmp_path, SETUP + r'''
with TestClient(app) as client:
    th, sh, student, school, lid, qid, wid, sid, base, body = prepare(client)
    url = '/teacher/weekend/lessons/' + str(lid) + '/courseware'
    pages = two_example_pages(client, th, lid)
    assert len(pages) >= 2, pages
    for page in (0, 1):
        save_page(client, th, url, page, pages[page])
    assert client.post(base + '/start', headers=th).status_code == 200
    assert client.post(base + '/goto', headers=th, json={'stage': 3}).status_code == 200
    step, cw, notice = live_step(client, th, base)
    assert cw, notice
    assert step == 0, (step, cw)
    r = client.post(base + '/courseware/view', headers=th, json={'stageNo': 3, 'page': 0, 'view': {'step': 2, 'showAnswer': False}})
    assert r.status_code == 200, r.text
    step, cw, _ = live_step(client, th, base)
    assert step == 2, (step, cw)
    r = client.post(base + '/slide', headers=th, json={'delta': 1})
    assert r.status_code == 200, r.text
    step, cw, _ = live_step(client, th, base)
    assert cw and cw['page'] == 1, cw
    assert step == 0, '第二页不能继承第一页的进度'
    r = client.post(base + '/courseware/view', headers=th, json={'stageNo': 3, 'page': 1, 'view': {'step': 1, 'showAnswer': True}})
    assert r.status_code == 200, r.text
    r = client.post(base + '/slide', headers=th, json={'delta': -1})
    assert r.status_code == 200, r.text
    step, cw, _ = live_step(client, th, base)
    assert cw['page'] == 0 and step == 2, (cw, step)
    print('OK')
''')


def test_saving_a_page_again_clears_its_old_playback(tmp_path):
    b.helpers.run_isolated(tmp_path, SETUP + r'''
with TestClient(app) as client:
    th, sh, student, school, lid, qid, wid, sid, base, body = prepare(client)
    url = '/teacher/weekend/lessons/' + str(lid) + '/courseware'
    pages = two_example_pages(client, th, lid)
    assert len(pages) >= 2, pages
    for page in (0, 1):
        save_page(client, th, url, page, pages[page])
    assert client.post(base + '/start', headers=th).status_code == 200
    assert client.post(base + '/goto', headers=th, json={'stage': 3}).status_code == 200
    r = client.post(base + '/courseware/view', headers=th, json={'stageNo': 3, 'page': 0, 'view': {'step': 3, 'showAnswer': True}})
    assert r.status_code == 200, r.text
    step, cw, _ = live_step(client, th, base)
    assert step == 3, (step, cw)
    r = client.put(url, headers=th, json={'stageNo': 3, 'page': 0, 'kind': 'steps',
        'params': {'problem': pages[0][:40], 'steps': list(STEPS), 'answer': '改过的答案', 'figure': {}}, 'writtenTask': False})
    assert r.status_code == 200, r.text
    step, cw, _ = live_step(client, th, base)
    assert step == 0, '重新保存同一页后旧进度必须清掉'
    assert cw['params']['answer'] == '答案0', '未经审核的修改不能直接上大屏'
    r = client.post(url + '/approve', headers=th, json={'stageNo': 3, 'page': 0})
    assert r.status_code == 200, r.text
    step, cw, _ = live_step(client, th, base)
    assert cw['params']['answer'] == '改过的答案' and step == 0, (cw['params']['answer'], step)
    print('OK')
''')


def test_previewing_one_page_does_not_write_the_classroom_state(tmp_path):
    b.helpers.run_isolated(tmp_path, SETUP + r'''
from sqlalchemy import select as _select
from changying.web.weekend_courseware import register_courseware_table

with TestClient(app) as client:
    th, sh, student, school, lid, qid, wid, sid, base, body = prepare(client)
    url = '/teacher/weekend/lessons/' + str(lid) + '/courseware'
    pages = two_example_pages(client, th, lid)
    assert len(pages) >= 2, pages
    for page in (0, 1):
        save_page(client, th, url, page, pages[page])
    assert client.post(base + '/start', headers=th).status_code == 200
    assert client.post(base + '/goto', headers=th, json={'stage': 3}).status_code == 200
    r = client.post(base + '/courseware/view', headers=th, json={'stageNo': 3, 'page': 0, 'view': {'step': 2, 'showAnswer': False}})
    assert r.status_code == 200, r.text
    table = register_courseware_table(legacy)
    with legacy.SessionLocal() as db:
        before = db.execute(_select(table.c.live_json)).first()[0]
    # 备课页预览：只读课程，不改课堂状态。
    assert client.get(url, headers=th).status_code == 200
    assert client.get('/v1/weekend-plan', headers=th).status_code == 200
    with legacy.SessionLocal() as db:
        after = db.execute(_select(table.c.live_json)).first()[0]
    assert before == after, (before, after)
    step, cw, _ = live_step(client, th, base)
    assert step == 2, (step, cw)
    print('OK')
''')
