from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepared_courseware_helpers', ROOT / 'tests' / 'test_homework_solve.py')
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_prepared_courseware_matches_existing_lesson_without_touching_questions(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
from changying.web.weekend_courseware import stage_pages
MD = """# 第12课：梯形面积
## 本节目标
认识梯形面积和对应的高。
## 教学流程
先拼合，再计算。
## 例题
1. 上底5厘米、下底7厘米、高5厘米，求梯形面积。
【答案】30平方厘米。
2. 上底3厘米、下底9厘米、高4厘米，求梯形面积。
【答案】24平方厘米。
## 课后练习
""" + "\n".join(f"{i}. 第{i}题　练习第{i}题，面积是多少？\n【答案】请写过程。" for i in range(1,24))

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    imported=client.post('/teacher/weekend/lessons/import/markdown',headers=th,
        data={'subject':'数学'},files={'files':('第12课-梯形面积.md',MD.encode('utf8'),'text/markdown')})
    assert imported.status_code==200 and imported.json()['imported']==1,imported.text
    lid=imported.json()['items'][0]['lessonId']
    url=f'/teacher/weekend/lessons/{lid}/courseware/prepared-import'
    before=client.get(f'/teacher/weekend/lessons/{lid}/written/questions',headers=th).json()
    assert len(before['items'])==23 and len(before['workedExamples'])==2
    with legacy.SessionLocal() as db:
        lesson=db.get(legacy.TeachingLesson,lid)
        page_texts=stage_pages(lesson,3)
    assert len(page_texts)==2
    def page(i):
        return {'stageNo':3,'page':i,'expectedPageText':page_texts[i],'kind':'steps','writtenTask':False,
            'params':{'title':f'例{i+1}','problem':page_texts[i].split('\n【答案】')[0],
                      'steps':['先找底和高','写出面积公式'],'answer':'面积待老师核对',
                      'figure':{'type':'uploaded_image','data_url':'data:image/jpeg;base64,/9j/2Q==','alt':'题图'}}}
    bundle={'dryRun':True,'pages':[page(0),page(1)]}
    assert client.post(url,headers=sh,json=bundle).status_code==403
    preview=client.post(url,headers=th,json=bundle)
    assert preview.status_code==200 and preview.json()['ready']==2,preview.text
    assert client.get(f'/teacher/weekend/lessons/{lid}/courseware',headers=th).json()['items']==[]
    stale=json.loads(json.dumps(bundle));stale['pages'][0]['expectedPageText']='题目已变'
    assert client.post(url,headers=th,json=stale).status_code==409
    leak=json.loads(json.dumps(bundle));leak['pages'][0]['params']['problem']+='【答案】不应在初始题干出现'
    assert client.post(url,headers=th,json=leak).status_code==400
    dup=json.loads(json.dumps(bundle));dup['pages'].append(dup['pages'][0])
    assert client.post(url,headers=th,json=dup).status_code==400
    assert client.get(f'/teacher/weekend/lessons/{lid}/courseware',headers=th).json()['items']==[]
    bundle['dryRun']=False
    real_audit=legacy.audit
    def failing_audit(*a,**k): raise RuntimeError('audit store unavailable')
    legacy.audit=failing_audit
    try:
        try:
            client.post(url,headers=th,json=bundle); raise AssertionError('import must fail with its audit')
        except RuntimeError:
            pass
    finally:
        legacy.audit=real_audit
    assert client.get(f'/teacher/weekend/lessons/{lid}/courseware',headers=th).json()['items']==[]
    saved=client.post(url,headers=th,json=bundle)
    assert saved.status_code==200 and saved.json()['imported']==2,saved.text
    items=saved.json()['courseware']['items']
    assert len(items)==2 and all(x['status']=='draft' and x['approved'] is None for x in items)
    assert all(x['params']['figure']['type']=='uploaded_image' for x in items)
    assert client.post(url,headers=th,json=bundle).status_code==409
    updated=json.loads(json.dumps(bundle))
    for p in updated['pages']:
        p['params']['stepFigures']=[p['params']['figure']]*3
        p['params']['steps'][0]='更新后的第一步'
    updated.update(dryRun=True,replaceExisting=True)
    preview=client.post(url,headers=th,json=updated)
    assert preview.status_code==200 and preview.json()['replacing']==2,preview.text
    updated.update(dryRun=False,expectedRevision='0'*64)
    assert client.post(url,headers=th,json=updated).status_code==409
    updated['expectedRevision']=preview.json()['revision']
    replaced=client.post(url,headers=th,json=updated)
    assert replaced.status_code==200,replaced.text
    items=replaced.json()['courseware']['items']
    assert len(items)==2 and all(len(x['params']['stepFigures'])==3 and x['previousDraft'] for x in items)
    assert all(x['status']=='draft' for x in items)
    with legacy.SessionLocal() as db:
        audits=db.query(legacy.AuditLog).filter_by(action='weekend.courseware.prepared_import').all()
    assert [a.detail for a in audits]==[f'lesson={lid}:pages=2']*2
    after=client.get(f'/teacher/weekend/lessons/{lid}/written/questions',headers=th).json()
    assert [(q['id'],q['stem'],q['reference']) for q in before['items']]==[(q['id'],q['stem'],q['reference']) for q in after['items']]
    assert before['workedExamples']==after['workedExamples'] and not calls
print('OK')
''', {'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'})


def test_prepared_import_entry_is_in_the_actual_preparation_page():
    from changying.web.weekend_pages import plan_page_html
    page = plan_page_html()
    assert '预检并导入课件包' in page
    assert '/courseware/prepared-import' in page
    assert '替换对应页并保留上一版' in page
