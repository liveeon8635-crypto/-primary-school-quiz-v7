from pathlib import Path
import importlib.util
import sys

spec=importlib.util.spec_from_file_location('practice_courseware_helpers',Path(__file__).resolve().parent/'test_homework_solve.py')
helpers=importlib.util.module_from_spec(spec);sys.modules[spec.name]=helpers;spec.loader.exec_module(helpers)


def test_practice_courseware_is_bound_to_question_and_waits_for_release(tmp_path):
    helpers.run_isolated(tmp_path,helpers.COMMON+r'''
from sqlalchemy import update
from changying.web.weekend_written import register_written_tables
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
print('OK')
''',{'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'})
