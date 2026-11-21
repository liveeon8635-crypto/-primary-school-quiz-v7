"""Real routes: generation is a draft and future slide payloads stay private."""
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location('chinese_draft_helpers', Path(__file__).with_name('test_homework_solve.py'))
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_generation_review_and_slide_response_boundaries(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
with TestClient(app) as client:
    th, sh, student, school = setup(client)
    passage = '\n'.join('第%d段：' % n + '完整正文' * 110 for n in range(12)) + '\n末段不得冒充答案'
    with legacy.SessionLocal() as db:
        program = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school))
        lesson = legacy.TeachingLesson(school_id=school, program_id=program.id, subject='语文', lesson_no=18,
            title='构造阅读样本', reading_plan=passage, teacher_plan='仅教师可见的教学提示')
        db.add(lesson); db.commit(); lid=lesson.id
    r=client.put('/teacher/weekend/schedule/语文/18/course-type', headers=th,
        json={'courseType':'reading','expectedRevision':0})
    assert r.status_code==200, r.text
    base='/teacher/weekend/lessons/%d/courseware' % lid
    generated=client.post(base+'/generate-all', headers=th, json={})
    assert generated.status_code==200, generated.text
    d=generated.json()
    assert len(d['stageOptions'])==6
    assert {i['stage'] for i in d['items']}=={2}, d
    item=d['items'][0]
    assert item['kind']=='slide' and item['approved'] is None and item['status']=='draft'
    body=''.join(line for page in item['params']['slides'] for line in page['body'])
    assert body==passage.replace('\n','')
    assert 'answer' not in item['params']
    assert '仅教师可见的教学提示' not in str(item['params'])
    assert client.post(base+'/generate-all', headers=th,json={}).json()['generated']==0
    saved=client.put(base,headers=th,json={'stageNo':2,'page':0,'kind':'slide','writtenTask':False,
        'params':{'title':'构造幻灯片','slides':[
            {'heading':'已开放第一页','body':['第一段']},
            {'heading':'后续秘密页','body':['后续秘密答案'], 'audioUrl':'/secret-future-audio.mp3'}]}})
    assert saved.status_code==200,saved.text
    approved=client.post(base+'/approve',headers=th,json={'stageNo':2,'page':0})
    assert approved.status_code==200,approved.text
    again=client.post(base+'/generate-all',headers=th,json={}).json()
    assert again['generated']==0 and again['items'][0]['approved'] is not None
    created=client.post('/teacher/weekend/sessions',headers=th,json={'lessonId':lid})
    assert created.status_code==200,created.text
    sb='/teacher/weekend/sessions/%d' % created.json()['id']
    assert client.post(sb+'/start',headers=th).status_code==200
    assert client.post(sb+'/goto',headers=th,json={'stage':2}).status_code==200
    first=client.get(sb+'/board',headers=th)
    assert first.status_code==200 and '已开放第一页' in first.text,first.text
    assert '后续秘密' not in first.text and 'secret-future-audio' not in first.text
    assert client.get(sb+'/board',headers=sh).status_code in (403,404)
    moved=client.post(sb+'/courseware/view',headers=th,json={'stageNo':2,'page':0,'view':{'slideIndex':1}})
    assert moved.status_code==200,moved.text
    assert '后续秘密答案' in client.get(sb+'/board',headers=th).text
    assert client.post(sb+'/courseware/view',headers=th,json={'stageNo':2,'page':0,'view':{'slideIndex':0}}).status_code==200
    assert '后续秘密' not in client.get(sb+'/board',headers=th).text
    page=client.get('/v1/weekend-plan').text
    assert '六环节课件状态' in page and '缺少素材：请配置本环节内容并审核。' in page
    assert 'cwPreview(' not in page
    print('OK')
''')

