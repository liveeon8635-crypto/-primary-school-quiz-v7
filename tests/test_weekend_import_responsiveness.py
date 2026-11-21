from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('import_responsiveness_helpers', ROOT / 'tests/test_homework_solve.py')
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_slow_lesson_import_keeps_health_and_teacher_pages_responsive(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError

entered=threading.Event()
release=threading.Event()
original_ai=legacy._ai_call

def waiting_ai(*args,**kwargs):
    entered.set()
    if not release.wait(10):
        raise RuntimeError('Test AI wait timed out')
    return original_ai(*args,**kwargs)

legacy._ai_call=waiting_ai
# 国语课的原文已改为本地导入（不发给外部 AI），因此这里用数学还有 AI 路径的学科验证「导入不阻塞应用」。
with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as pool:
    th,sh,sid,school_id=setup(client)
    for mode,no in [('paste',17),('file',18)]:
        entered.clear();release.clear()
        replies.append(json.dumps({'title':'数学教案','coreTarget':'两位数减一位数','teacherPlan':'先计算再检查','ppt':['目标'], 'examples':[], 'questions':[]},ensure_ascii=False))
        source='这是一份老师自己的数学教案。练习 12-5 这类退位减法。'
        def submit():
            data={'subject':'数学','lessonNo':str(no)}
            files=None
            if mode=='paste':data['text']=source
            else:files={'file':('lesson.txt',source.encode(),'text/plain')}
            return client.post('/teacher/weekend/lessons/import',headers=th,data=data,files=files)
        importing=pool.submit(submit)
        assert entered.wait(3),'Import did not reach AI'
        def browse():
            return [client.get('/health'),client.get('/v1/weekend-plan'),client.get('/teacher/weekend/schedule?subject=数学',headers=th)]
        browsing=pool.submit(browse)
        responsive=False
        try:
            responses=browsing.result(timeout=3)
            responsive=all(r.status_code==200 for r in responses)
            assert not importing.done(),'AI should still be waiting during health probes'
        except TimeoutError:
            pass
        finally:
            release.set()
        imported=importing.result(timeout=5)
        browsing.result(timeout=5)
        assert imported.status_code==200,imported.text
        assert responsive,'Synchronous AI import blocked the app event loop and health checks'
        lid=imported.json()['lessonId']
        saved=client.get(f'/teacher/weekend/lessons/{lid}',headers=th).json()
        assert saved['sourceText']==source
    assert client.post('/teacher/weekend/lessons/import',headers=sh,data={'subject':'语文','lessonNo':'17','courseType':'reading','text':source}).status_code==403
    print('OK')
''')
