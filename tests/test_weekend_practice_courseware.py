from pathlib import Path
import importlib.util
import sys

spec=importlib.util.spec_from_file_location('practice_courseware_helpers',Path(__file__).resolve().parent/'test_homework_solve.py')
helpers=importlib.util.module_from_spec(spec);sys.modules[spec.name]=helpers;spec.loader.exec_module(helpers)


def test_choice_binding_includes_options():
    from changying.services.weekend_answers import choice_courseware_binding, courseware_answer_binding
    assert choice_courseware_binding('同一题干', ['3','4']) != choice_courseware_binding('同一题干', ['4','3'])
    assert courseware_answer_binding('choice', 0, '解析') != courseware_answer_binding('choice', 1, '解析')
    assert courseware_answer_binding('choice', 0, '解析') != courseware_answer_binding('choice', 0, '修改后的解析')
    assert courseware_answer_binding('written', '旧答案') != courseware_answer_binding('written', '新答案')


def test_practice_courseware_is_bound_to_question_and_waits_for_release(tmp_path):
    helpers.run_isolated(tmp_path,helpers.COMMON+r'''
from sqlalchemy import update
from changying.web.weekend_written import register_written_tables
from changying.web.weekend_courseware import register_courseware_template_table, register_courseware_table
from changying.services.lesson_written import written_templates,template_meta
MD="""# 第12课：面积
## 本节目标
计算面积。
## 教学流程
讲解与练习。
## 例题
1. 求长4厘米宽2厘米的长方形面积。
【答案】8平方厘米。
## 课后练习
1. 第1题 梯形上底3厘米、下底5厘米、高4厘米，求面积。
【答案】16平方厘米。
2. 第2题 梯形上底2厘米、下底6厘米、高3厘米，求面积。
【答案】12平方厘米。
"""
with TestClient(app) as client:
 th,sh,sid,school=setup(client)
 r=client.post('/teacher/weekend/lessons/import/markdown',headers=th,data={'subject':'数学'},files={'files':('lesson.md',MD.encode('utf8'),'text/markdown')})
 assert r.status_code==200,r.text
 lid=r.json()['items'][0]['lessonId']
 with legacy.SessionLocal() as db:
  tid=db.scalar(select(legacy.User.id).where(legacy.User.username=='teacher1'))
  t=register_written_tables(legacy)['questions'];rows=written_templates(db,t,school,tid,lid)
  assert len(rows)==2
  stems=[q.stem.split('\n\n')[-1].strip() for q in rows]
  for q in rows: db.execute(update(t).where(t.c.id==q.id).values(hints_json=json.dumps({**template_meta(q),'approved':True},ensure_ascii=False)))
  db.commit()
 pages=[{'stageNo':4,'page':i,'expectedPageText':stem,'kind':'steps','params':{'problem':stem,'steps':['找对应的底和高','代入面积公式'],'answer':str(i+1)},'writtenTask':False} for i,stem in enumerate(stems)]
 url=f'/teacher/weekend/lessons/{lid}/courseware/prepared-import'
 r=client.post(url,headers=th,json={'dryRun':False,'pages':pages});assert r.status_code==200,r.text
 for i in range(2):
  r=client.post(f'/teacher/weekend/lessons/{lid}/courseware/approve',headers=th,json={'stageNo':4,'page':i});assert r.status_code==200,r.text
 # Practice must never generate an additional student exercise or call AI.
 r=client.post(f'/teacher/weekend/lessons/{lid}/courseware/generate',headers=th,json={'stageNo':4,'page':0})
 assert r.status_code==400,r.text
 # Even a pre-existing template with written_task=True must not create a duplicate.
 saved=client.post(f'/teacher/weekend/lessons/{lid}/courseware/save-as-template',headers=th,json={'stageNo':4,'page':0,'name':'测试模板'})
 assert saved.status_code==200,saved.text
 template_id=saved.json()['templateId']
 with legacy.SessionLocal() as db:
  cwtable=register_courseware_template_table(legacy)
  db.execute(update(cwtable).where(cwtable.c.id==template_id).values(written_task=True))
  db.commit()
 reused=client.post(f'/teacher/weekend/lessons/{lid}/courseware/from-template',headers=th,json={'stageNo':4,'page':0,'templateId':template_id})
 assert reused.status_code==200,reused.text
 assert not next(x for x in reused.json()['items'] if x['stage']==4 and x['page']==0)['writtenTask']
 r=client.post(f'/teacher/weekend/lessons/{lid}/courseware/approve',headers=th,json={'stageNo':4,'page':0})
 assert r.status_code==200,r.text
 with legacy.SessionLocal() as db:
  assert len(written_templates(db,t,school,tid,lid))==2
 session=client.post('/teacher/weekend/sessions',headers=th,json={'lessonId':lid});assert session.status_code==200,session.text
 base=f"/teacher/weekend/sessions/{session.json()['id']}"
 client.post(base+'/start',headers=th);client.post(base+'/goto',headers=th,json={'stage':4})
 assert client.get(base+'/board',headers=th).json().get('courseware') is None
 assert client.post(base+'/publish-answers',headers=th,json={'question':1}).status_code==200
 assert client.get(base+'/board',headers=th).json()['courseware']['page']==0
 # Changing the source order after class started must not bind question 1's
 # courseware to question 2; the session retains its original snapshots.
 with legacy.SessionLocal() as db:
  q=written_templates(db,t,school,tid,lid)[0]
  db.execute(update(t).where(t.c.id==q.id).values(hints_json=json.dumps({**template_meta(q),'approved':False},ensure_ascii=False)))
  db.commit()
 assert client.get(base+'/board',headers=th).json()['courseware']['page']==0
 assert client.post(base+'/practice-question',headers=th,json={'question':2}).status_code==200
 assert client.get(base+'/board',headers=th).json().get('courseware') is None
 assert client.post(base+'/publish-answers',headers=th,json={'question':2}).status_code==200
 assert client.get(base+'/board',headers=th).json()['courseware']['page']==1
 # The approved slide becomes stale when the snapshotted source answer changes.
 with legacy.SessionLocal() as db:
  snapshots=list(db.execute(select(t).where(t.c.session_id==session.json()['id']).order_by(t.c.id)))
  assert len(snapshots)>=2
  db.execute(update(t).where(t.c.id==snapshots[1].id).values(reference='另一个评分答案'))
  db.commit()
 assert client.get(base+'/board',headers=th).json().get('courseware') is None
 # A legacy stage-wide slide may include answers to all questions.
 # Hide it even after the *first* question is published.
 with legacy.SessionLocal() as db:
  first=written_templates(db,t,school,tid,lid)[0]
  db.execute(update(t).where(t.c.id==first.id).values(hints_json=json.dumps({**template_meta(first),'approved':True},ensure_ascii=False)))
  courseware_table=register_courseware_table(legacy)
  cwrow=db.execute(select(courseware_table).where(courseware_table.c.lesson_id==lid)).first()
  assert cwrow is not None
  old_items=json.loads(cwrow.params_json)['items']
  legacy_item=dict(next(x for x in old_items if x['stage']==4 and x['page']==0))
  legacy_item.update(page=None,pageText='',approvedPageText='',writtenTask=True,templateId=None)
  legacy_item.pop('approvedAnswerBinding',None)
  db.execute(update(courseware_table).where(courseware_table.c.id==cwrow.id).values(
    params_json=json.dumps({'version':2,'items':[legacy_item]},ensure_ascii=False),
    approved_json=json.dumps([[4,None]]),live_json='{}'))
  db.commit()
 legacy_approval=client.post(f'/teacher/weekend/lessons/{lid}/courseware/approve',headers=th,json={'stageNo':4,'page':None})
 assert legacy_approval.status_code==200,legacy_approval.text
 assert next(x for x in legacy_approval.json()['items'] if x['stage']==4 and x['page'] is None)['writtenTask'] is False
 with legacy.SessionLocal() as db:
  assert len(written_templates(db,t,school,tid,lid))==2
 second=client.post('/teacher/weekend/sessions',headers=th,json={'lessonId':lid})
 assert second.status_code==200,second.text
 base2=f"/teacher/weekend/sessions/{second.json()['id']}"
 assert client.post(base2+'/start',headers=th).status_code==200
 assert client.post(base2+'/goto',headers=th,json={'stage':4}).status_code==200
 assert client.get(base2+'/board',headers=th).json().get('courseware') is None
 assert client.post(base2+'/publish-answers',headers=th,json={'question':1}).status_code==200
 assert client.get(base2+'/board',headers=th).json().get('courseware') is None
 assert client.post(base2+'/practice-question',headers=th,json={'question':2}).status_code==200
 assert client.get(base2+'/board',headers=th).json().get('courseware') is None
 assert client.post(base2+'/publish-answers',headers=th,json={'question':2}).status_code==200
 assert client.get(base2+'/board',headers=th).json().get('courseware') is not None
print('OK')
''',{'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'})
