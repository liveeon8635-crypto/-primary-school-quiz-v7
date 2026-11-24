"""Writing acceptance through the real application, using an isolated SQLite database."""
import importlib.util
import sys
import os
import pytest
from pathlib import Path
from contextlib import contextmanager

spec=importlib.util.spec_from_file_location('writing_helpers',Path(__file__).with_name('test_homework_solve.py'))
helpers=importlib.util.module_from_spec(spec);sys.modules[spec.name]=helpers;spec.loader.exec_module(helpers)


@contextmanager
def playwright_or_skip():
    playwright=pytest.importorskip('playwright.sync_api')
    try:
        with playwright.sync_playwright() as runtime:
            yield runtime
    except PermissionError as exc:
        pytest.skip('Windows sandbox denied Chromium IPC: '+str(exc))


def test_writing_page_javascript_compiles(tmp_path):
    import re
    import shutil
    import subprocess
    from changying.web.writing_pages import writing_page
    node=shutil.which('node')
    if not node:
        pytest.skip('Node is required for the actual page script syntax check')
    script=tmp_path/'writing.js'
    script.write_text('\n'.join(re.findall(r'<script[^>]*>(.*?)</script>',writing_page(),re.S)),encoding='utf8')
    checked=subprocess.run([node,'--check',str(script)],capture_output=True,text=True)
    assert checked.returncode==0,checked.stderr


def test_writing_workbench_and_classroom_render_in_browser(tmp_path):
    from changying.web.writing_pages import writing_page
    import json
    html=writing_page()
    sample={
        'package':{'title':'我最喜欢的季节','nodes':[
            {'id':'model-1','kind':'text','role':'model','status':'pending','text':'走进果园，苹果挂满枝头。','targets':[],
             'source':{'file':'第13次语文教案原版.docx','part':'word/document.xml#body:1'},'reason':'范文标题后'},
        ],'history':[]},'revision':1,
        'readiness':{'canStart':False,'stageReadiness':[
            {'name':name,'status':'缺少素材','missing':['待审核']} for name in
            ('点名与回顾','范文导览','看图写话','技法梳理','随堂练习','课后反馈')],
            'startReasons':['范文配图组缺失','看图写话图片组缺失']},
    }
    with playwright_or_skip() as p:
        try:
            browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
        except Exception as exc:
            pytest.skip('Chromium unavailable: '+str(exc)[:120])
        try:
            page=browser.new_page(viewport={'width':390,'height':844})
            page.add_init_script("sessionStorage.setItem('v717Token','browser-test-token')")
            page.route('https://changying.test/v1/weekend-writing?lesson=13',
                lambda route:route.fulfill(status=200,content_type='text/html; charset=utf-8',body=html))
            page.route('https://changying.test/teacher/weekend/lessons/13/writing',
                lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(sample,ensure_ascii=False)))
            page.goto('https://changying.test/v1/weekend-writing?lesson=13')
            page.get_by_role('heading',name='作文素材与审核').wait_for()
            assert page.get_by_role('navigation',name='作文六环节').count()==1
            assert page.get_by_role('navigation',name='作文六环节').get_by_role('button').count()==7
            assert page.get_by_text('范文配图组缺失').count()>0
            assert page.get_by_text('看图写话图片组缺失').count()>0
            assert page.get_by_role('button',name='审核通过',exact=True).count()==1
            assert page.get_by_label('素材归属').count()==1
            assert page.locator('.wr-stages + .wr-stage-panel').count()==1
            assert page.get_by_role('button',name='忽略待分类（0项）',include_hidden=True).count()==1

            page.get_by_role('button',name='3. 看图写话').click()
            assert page.get_by_text('本环节还没有素材。').count()==1
            page.get_by_role('button',name='2. 范文导览').click()
            assert page.get_by_label('素材归属').count()==1
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(tmp_path/'writing-workbench-mobile.png'),full_page=True)
            sample['package']['nodes'].append({'id':'misc','kind':'text','role':'pending','status':'pending',
                                               'text':'待判断的材料','targets':[]})
            page.reload()
            page.get_by_role('button',name='待分类').click()
            assert page.get_by_label('素材正文').input_value()=='待判断的材料'
            assert page.locator('.wr-stage-panel').evaluate('(p)=>document.activeElement===p')
            page.get_by_text('补充或批量处理素材',exact=True).click()
            def ignore(route):
                assert route.request.post_data_json=={'expectedRevision':1,'action':'ignore_unassigned'}
                sample['package']['nodes'][-1]['status']='ignored'
                route.fulfill(json={**sample,'updated':1,'revision':2})
            page.route('**/writing/bulk-review',ignore)
            page.once('dialog',lambda dialog:dialog.accept())
            page.get_by_role('button',name='忽略待分类（1项）').click()
            page.get_by_role('status').filter(has_text='已将 1 项标为忽略').wait_for()
            assert page.get_by_label('审核状态').input_value()=='ignored'

            classroom={'title':'我最喜欢的季节','status':'running','stage':2,'revision':0,
                'teacher':True,'open':[],'students':[],'completion':{},'feedback':{},
                'stages':[{'no':i+1,'name':name} for i,name in enumerate(
                    ('点名与回顾','范文导览','看图写话','技法梳理','随堂练习','课后反馈'))],
                'nodes':[{'id':'model-1','kind':'text','role':'model','text':'走进果园，苹果挂满枝头。','targets':[]}]}
            page.route('https://changying.test/v1/weekend-writing?session=13',
                lambda route:route.fulfill(status=200,content_type='text/html; charset=utf-8',body=html))
            page.route('https://changying.test/weekend/writing/sessions/13',
                lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(classroom,ensure_ascii=False)))
            page.route('https://changying.test/teacher/weekend/sessions/13/written',
                lambda route:route.fulfill(status=200,content_type='application/json',body='{"questions":[]}'))
            page.goto('https://changying.test/v1/weekend-writing?session=13')
            page.get_by_role('heading',name='我最喜欢的季节').wait_for()
            for stage in ('点名与回顾','范文导览','看图写话','技法梳理','随堂练习','课后反馈'):
                assert page.get_by_role('button',name=stage,exact=True).count()==1
            page.get_by_label('查看环节').select_option('3')
            assert page.get_by_text('本环节还没有开放内容。').count()==1
            page.get_by_label('查看环节').select_option('2')
            assert page.get_by_text('走进果园，苹果挂满枝头。').count()==1
            assert page.get_by_role('button',name='保存开放范围').count()==1
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(tmp_path/'writing-classroom-mobile.png'),full_page=True)
            page.unroute('https://changying.test/weekend/writing/sessions/13')
            student_view={**classroom,'teacher':False,'nodes':[{'id':'task','kind':'text','role':'task',
                'text':'我最喜欢的季节','targets':[]}],'open':['task'],'feedback':None}
            page.route('https://changying.test/weekend/writing/sessions/13',
                lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(student_view,ensure_ascii=False)))
            page.route('https://changying.test/student/weekend/sessions/13/written',
                lambda route:route.fulfill(status=200,content_type='application/json',
                    body=json.dumps({'questions':[{'id':1,'stem':'我最喜欢的季节','submission':None}]},ensure_ascii=False)))
            page.goto('https://changying.test/v1/weekend-writing?session=13')
            page.get_by_role('button',name='提交／重拍后再次提交').wait_for()
            assert page.get_by_role('link',name='点名、课堂计时与班级控制').count()==0
            assert page.get_by_label('拍照或重拍').get_attribute('capture')=='environment'
            assert page.get_by_label('选择多张照片').get_attribute('multiple') is not None
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(tmp_path/'writing-student-mobile.png'),full_page=True)
        finally:
            browser.close()


def test_writing_workbar_renders_in_browser(tmp_path):
    from changying.web.weekend_pages import plan_page_html
    from urllib.parse import unquote
    import json
    html=plan_page_html()
    row={'lessonNo':13,'schoolWeek':13,'schoolUnit':'季节写作','plannedDate':'2026-11-28',
        'hasPlan':True,'lessonId':13,'title':'我最喜欢的季节','courseType':'writing',
        'workflowLabel':'作文课','workflowRevision':1,'coursewareApproved':False,
        'coursewareStatus':'pending','pendingMaterials':0,'startReasons':['范文配图缺失','看图写话图片缺失'],
        'draftQuestions':0,'practiceReady':0,'taught':False}
    with playwright_or_skip() as p:
        try:
            browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
        except Exception as exc:
            pytest.skip('Chromium unavailable: '+str(exc)[:120])
        try:
            page=browser.new_page(viewport={'width':390,'height':844})
            page.add_init_script("sessionStorage.setItem('v717Token','browser-test-token')")
            page.route('https://changying.test/v1/weekend-plan',
                lambda route:route.fulfill(status=200,content_type='text/html; charset=utf-8',body=html))
            page.route('https://changying.test/session',
                lambda route:route.fulfill(status=200,content_type='application/json',body='{"role":"teacher"}'))
            page.route('https://changying.test/teacher/weekend/next',
                lambda route:route.fulfill(status=200,content_type='application/json',body='{"items":[]}'))
            page.route('https://changying.test/teacher/weekend/schedule?subject=*',
                lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(
                    {'items':[row] if '语文' in unquote(route.request.url) else []},ensure_ascii=False)))
            page.goto('https://changying.test/v1/weekend-plan')
            page.get_by_role('button',name='语文',exact=True).click()
            entry=page.get_by_role('link',name='继续作文备课')
            entry.wait_for()
            assert entry.get_attribute('href')=='/v1/weekend-writing?lesson=13'
            assert page.get_by_label('语文课型').input_value()=='writing'
            assert page.get_by_text('范文配图缺失').count()>0
            assert page.get_by_text('看图写话图片缺失').count()>0
            assert page.get_by_role('button',name='开课',exact=True).is_disabled()
            assert page.get_by_placeholder('2026-09-12').input_value()=='2026-11-28'
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(tmp_path/'writing-workbar-mobile.png'),full_page=True)
            package={'schemaVersion':1,'subject':'语文','items':[{'lessonNo':13,'writingPackage':{'nodes':[{}]}}],
                     'courseware':{'pages':[{'params':{'slides':[{},{}]}}]}}
            uploads=[]
            def uploaded(route):
                uploads.append(route.request.method)
                route.fulfill(json={'lessonId':13})
            page.route('**/teacher/weekend/lessons/import',uploaded)
            page.route('**/v1/weekend-writing?lesson=13&imported=1',
                       lambda route:route.fulfill(content_type='text/html',body='<main></main>'))
            file_input=page.locator('input[type=file][accept^=".docx"]:not([multiple])').last
            file_input.set_input_files({'name':'季节.json','mimeType':'application/json',
                                        'buffer':json.dumps(package).encode()})
            preview=page.get_by_role('button',name='导入为备课草稿')
            preview.wait_for()
            assert '2页课件' in preview.locator('..').inner_text()
            assert not uploads
            page.once('dialog',lambda dialog:dialog.accept())
            preview.click()
            page.wait_for_url('**/v1/weekend-writing?lesson=13&imported=1')
            assert uploads==['POST']

        finally:
            browser.close()


@pytest.mark.skipif(not os.environ.get('WRITING_LESSON13_DOCX'),reason='Requires the privately supplied lesson 13 original')
def test_lesson13_real_import_preserves_inventory_and_blocks_missing_images(tmp_path):
    helpers.run_isolated(tmp_path,helpers.COMMON+r'''
import hashlib
from pathlib import Path
source=Path(os.environ['WRITING_LESSON13_DOCX']);raw=source.read_bytes();before=hashlib.sha256(raw).hexdigest()
with TestClient(app) as client:
    th,sh,student,school=setup(client)
    result=client.post('/teacher/weekend/lessons/import',headers=th,
        data={'subject':'语文','lessonNo':13,'courseType':'writing'},
        files={'file':('第13次语文教案原版.docx',raw,'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
    assert result.status_code==200,result.text
    lid=result.json()['lessonId'];base=f'/teacher/weekend/lessons/{lid}/writing'
    data=client.get(base,headers=th).json();nodes=data['package']['nodes']
    assert len([n for n in nodes if n['kind']=='image'])==11
    tables=[n for n in nodes if n['kind']=='table'];assert len(tables)==1 and tables[0]['rows']
    text='\n'.join(n['text'] for n in nodes)
    for phrase in ['醉美秋天','春归万物苏','按空间顺序','按时间顺序','按逻辑顺序','多种感官','修辞','动静结合','我最喜欢的季节']:
        assert phrase in text,phrase
    assert any(n['role']=='task' and n['text']=='我最喜欢的季节' for n in nodes)
    assert all(n['status']=='pending' for n in nodes)
    assert all(n.get('contexts') is not None for n in nodes if n['kind']=='image')
    review=client.put(base,headers=th,json={'expectedRevision':data['revision'],'nodes':nodes,'title':'我最喜欢的季节','approve':True})
    assert review.status_code==409 and '范文配图' in review.text and '看图写话' in review.text
    assert client.post('/teacher/weekend/sessions',headers=th,json={'lessonId':lid,'requireReady':False}).status_code==409
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    assert not calls
    print('OK real lesson: 11 images, 1 table, missing materials blocked, original unchanged')
''')


@pytest.mark.skipif(not os.environ.get('WRITING_LESSON13_BUNDLE'),reason='Requires the generated lesson 13 import package')
def test_lesson13_bundle_import_retains_sources_tables_and_review_gate(tmp_path):
    helpers.run_isolated(tmp_path,helpers.COMMON+r'''
from pathlib import Path
file=Path(os.environ['WRITING_LESSON13_BUNDLE'])
with TestClient(app) as client:
    th,sh,student,school=setup(client)
    result=client.post('/teacher/weekend/lessons/import',headers=th,
        data={'subject':'语文','lessonNo':13,'courseType':'writing'},
        files={'file':(file.name,file.read_bytes(),'application/json')})
    assert result.status_code==200,result.text
    lid=result.json()['lessonId']
    data=client.get(f'/teacher/weekend/lessons/{lid}/writing',headers=th).json()
    nodes=data['package']['nodes']
    assert len(nodes)==74
    assert len([n for n in nodes if n['kind']=='image'])==15
    assert any(n['kind']=='table' and len(n['rows'])==5 for n in nodes)
    generated=[n for n in nodes if n.get('declaredSource',{}).get('file','').startswith('AI生成-')]
    assert len(generated)==4
    assert all(n['status']=='pending' for n in generated)
    assert len([n for n in generated if n['role']=='model_image' and n['targets']])==3
    assert not data['readiness']['canStart']
    assert client.post('/teacher/weekend/sessions',headers=th,json={'lessonId':lid,'requireReady':False}).status_code==409
    bulk=f'/teacher/weekend/lessons/{lid}/writing/bulk-review'
    confirmed=client.post(bulk,headers=th,json={'expectedRevision':data['revision'],'action':'confirm_assigned'})
    assert confirmed.status_code==200,confirmed.text
    data=confirmed.json()
    ignored=client.post(bulk,headers=th,json={'expectedRevision':data['revision'],'action':'ignore_unassigned'})
    assert ignored.status_code==200,ignored.text
    data=ignored.json();assert data['readiness']['pendingMaterials']==0
    reviewed=client.put(f'/teacher/weekend/lessons/{lid}/writing',headers=th,json={
        'expectedRevision':data['revision'],'nodes':data['package']['nodes'],
        'title':data['package']['title'],'approve':True})
    assert reviewed.status_code==200,reviewed.text
    assert reviewed.json()['readiness']['canStart'],reviewed.json()['readiness']['startReasons']
    assert not calls
    print('OK bundle imported, batch reviewed, and passed all six real-course readiness checks')
''')


@pytest.mark.skipif(not os.environ.get('WRITING_LESSON13_DOCX'),
    reason='Requires the privately supplied original lesson')
def test_lesson13_real_review_and_classroom_with_generated_images(tmp_path):
    helpers.run_isolated(tmp_path,helpers.COMMON+r'''
import hashlib
from pathlib import Path
doc=Path(os.environ['WRITING_LESSON13_DOCX'])
assets=Path('assets/writing_lesson13')
original_hash=hashlib.sha256(doc.read_bytes()).hexdigest()
with TestClient(app) as client:
    th,sh,student,school=setup(client)
    result=client.post('/teacher/weekend/lessons/import',headers=th,
        data={'subject':'语文','lessonNo':13,'courseType':'writing'},
        files={'file':(doc.name,doc.read_bytes(),'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
    assert result.status_code==200,result.text
    lid=result.json()['lessonId'];base=f'/teacher/weekend/lessons/{lid}/writing'
    data=client.get(base,headers=th).json()
    for name in ('autumn-orchard.jpg','autumn-wheat.jpg','autumn-ginkgo.jpg','spring-observation.jpg'):
        raw=(assets/('AI生成-'+name)).read_bytes()
        added=client.post(base+'/images',headers=th,data={'expectedRevision':data['revision']},
            files={'file':('AI生成-'+name,raw,'image/jpeg')})
        assert added.status_code==200,added.text
        data=added.json()
    nodes=data['package']['nodes']
    for node in nodes: node['status']='ignored'
    model=[n for n in nodes if n['role']=='model' and n['text'].strip()]
    assert len(model)>=3
    for node in model: node['status']='confirmed'
    methods=[n for n in nodes if n['role']=='method' and n['text'].strip()]
    assert any('感官' in n['text'] for n in methods)
    assert any('动静' in n['text'] for n in methods)
    for node in methods: node['status']='confirmed'
    task=next(n for n in nodes if n['role']=='task' and n['text']=='我最喜欢的季节')
    task['status']='confirmed'
    by_name={n['source']['file'].removeprefix('AI生成-'):n for n in nodes
        if n['kind']=='image' and n['source']['file'].endswith('.jpg')}
    for name,target_text in (('autumn-orchard.jpg','走进果园'),('autumn-wheat.jpg','走出果园'),('autumn-ginkgo.jpg','沿着田埂')):
        target=next(n for n in model if target_text in n['text'])
        by_name[name].update(role='model_image',status='confirmed',targets=[target['id']])
    by_name['spring-observation.jpg'].update(role='picture',status='confirmed')
    nodes.extend([
        dict(id='lesson13-review',kind='text',role='review',status='confirmed',text='回顾景物观察记录',targets=[]),
        dict(id='lesson13-feedback',kind='text',role='feedback',status='confirmed',text='检查观察顺序与感官描写',targets=[]),
    ])
    saved=client.put(base,headers=th,json={'expectedRevision':data['revision'],'nodes':nodes,
        'title':'我最喜欢的季节','approve':True})
    assert saved.status_code==200,saved.text
    assert saved.json()['readiness']['canStart']
    assert saved.json()['readiness']['pendingMaterials']==0
    assert len(saved.json()['readiness']['stageReadiness'])==6
    with legacy.SessionLocal() as db:
        cls=db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id==school))
        cid=cls.id
        other=legacy.User(school_id=school,username='lesson13_other',password_hash=legacy.hash_password('x'),
            name='同班学生',role='student',grade=3)
        parent=legacy.User(school_id=school,username='lesson13_parent',password_hash=legacy.hash_password('x'),
            name='测试家长',role='parent')
        db.add(other);db.add(parent);db.flush()
        db.add(legacy.ClassStudent(class_id=cid,student_id=other.id))
        db.add(legacy.ParentStudent(parent_id=parent.id,student_id=student));db.commit()
    other_headers={'Authorization':'Bearer '+login_and_change(client,'lesson13_other','x','Other1234')}
    parent_headers={'Authorization':'Bearer '+login_and_change(client,'lesson13_parent','x','Parent1234')}
    created=client.post('/teacher/weekend/sessions',headers=th,json={'lessonId':lid,'classId':cid})
    assert created.status_code==200,created.text
    sid=created.json()['id']
    assert client.post(f'/teacher/weekend/sessions/{sid}/start',headers=th).status_code==200
    state_url=f'/weekend/writing/sessions/{sid}'
    assert client.get(state_url,headers=sh).json()['nodes']==[]
    teacher=client.get(state_url,headers=th).json()
    assert [stage['name'] for stage in teacher['stages']]==[
        '点名与回顾','范文导览','看图写话','技法梳理','随堂练习','课后反馈']
    assert len([n for n in teacher['nodes'] if n['role']=='model_image'])==3
    assert len([n for n in teacher['nodes'] if n['role']=='picture'])==1
    opened=client.post(f'/teacher/weekend/writing/sessions/{sid}/release',headers=th,
        json={'expectedRevision':0,'nodeIds':[task['id']]})
    assert opened.status_code==200,opened.text
    questions=client.get(f'/student/weekend/sessions/{sid}/written',headers=sh).json()['questions']
    assert len(questions)==1 and '我最喜欢的季节' in questions[0]['stem']
    photo=(assets/'AI生成-spring-observation.jpg').read_bytes()
    submission=client.post(f'/student/weekend/sessions/{sid}/written/{questions[0]["id"]}',headers=sh,
        data={'revision':0,'text':'我喜欢春天'},files=[('photos',('writing.jpg',photo,'image/jpeg'))])
    assert submission.status_code==200,submission.text
    versions=client.get(f'/student/weekend/sessions/{sid}/written/{questions[0]["id"]}/versions',headers=sh).json()['versions']
    assert len(versions)==1 and len(versions[0]['photos'])==1
    others=client.get(f'/student/weekend/sessions/{sid}/written/{questions[0]["id"]}/versions',headers=other_headers)
    assert others.status_code==200 and others.json()['versions']==[]
    annotation=client.post(f'/teacher/weekend/sessions/{sid}/written/{questions[0]["id"]}/students/{student}/annotate',
        headers=th,json={'submissionVersionId':versions[0]['id'],'verdict':'needs_revision',
            'comment':'增加听觉描写','shapes':[{'kind':'arrow','x':10,'y':10,'w':20,'h':20}]})
    assert annotation.status_code==200,annotation.text
    feedback=f'/teacher/weekend/writing/sessions/{sid}/feedback'
    draft={'expectedRevision':1,'studentId':student,'comment':'已经完成初稿','nextStep':'增加听觉描写','publish':False}
    assert client.post(feedback,headers=th,json=draft).status_code==200
    assert client.get(state_url,headers=sh).json()['feedback'] is None
    assert client.get(f'/parent/weekend/writing/students/{student}',headers=parent_headers).json()['items']==[]
    draft.update(expectedRevision=2,publish=True)
    assert client.post(feedback,headers=th,json=draft).status_code==200
    assert client.get(state_url,headers=sh).json()['feedback']['nextStep']=='增加听觉描写'
    published=client.get(f'/parent/weekend/writing/students/{student}',headers=parent_headers)
    assert published.status_code==200 and published.json()['items'][0]['versions'][-1]['comment']=='已经完成初稿'
    assert hashlib.sha256(doc.read_bytes()).hexdigest()==original_hash
    assert not calls
    print('OK lesson13 original + four generated images + approved classroom + student photo + teacher annotation + published feedback')
''')


def test_writing_import_review_freeze_photo_feedback(tmp_path):
    helpers.run_isolated(tmp_path,helpers.COMMON+r'''
import io, base64
from PIL import Image
with TestClient(app) as client:
    th,sh,student,school=setup(client)
    assert client.put('/teacher/weekend/schedule/语文/13/course-type',headers=th,
        json={'courseType':'writing','expectedRevision':0}).status_code==200
    imported=client.post('/teacher/weekend/lessons/import',headers=th,
        data={'subject':'语文','lessonNo':'13','courseType':'writing'},
        files={'file':('writing.txt','范文展示\n秋天是我喜爱的季节。\n按空间顺序观察景物。'.encode(),'text/plain')})
    assert imported.status_code==200,imported.text
    lid=imported.json()['lessonId'];base=f'/teacher/weekend/lessons/{lid}/writing'
    d=client.get(base,headers=th).json()
    assert not d['readiness']['canStart']
    assert client.get(base,headers=sh).status_code==403
    assert client.post('/teacher/weekend/sessions',headers=th,json={'lessonId':lid,'requireReady':False}).status_code==409
    image=io.BytesIO();Image.new('RGB',(12,12),'green').save(image,format='PNG');photo=image.getvalue()
    for i in range(2):
        added=client.post(base+'/images',headers=th,data={'expectedRevision':d['revision']},files={'file':(f'scene{i}.png',photo,'image/png')})
        assert added.status_code==200,added.text
        d=added.json()
    nodes=d['package']['nodes']
    for n in nodes:n['status']='ignored'
    def node(id,role,text):return dict(id=id,kind='text',text=text,role=role,status='confirmed',targets=[])
    nodes += [node('review','review','回顾观察记录'),node('model','model','秋天是我喜爱的季节。走进果园，苹果挂在枝头，桂花的香气随风飘来。站在田埂上，我听见稻田里沙沙的声音，看到远处的银杏叶缓缓落下。脚下的土地有些湿润，手边的稻穗沉甸甸的。傍晚时分，晚霞照亮了天空，我想把这些景象一一记下来。秋天带来了丰收，也让我愿意放慢脚步，细细感受这个季节。'),
        node('method','method','按空间顺序描写，例如从远到近。'),node('task','task','我最喜欢的季节'),node('feedback','feedback','检查描写顺序并修改')]
    pictures=[n for n in nodes if n['kind']=='image']
    pictures[0].update(role='model_image',status='confirmed',targets=['model'])
    pictures[1].update(role='picture',status='confirmed')
    body=dict(expectedRevision=d['revision'],nodes=nodes,title='我最喜欢的季节',approve=True)
    saved=client.put(base,headers=th,json=body);assert saved.status_code==200,saved.text
    assert saved.json()['readiness']['canStart']
    assert client.put(base,headers=th,json=body).status_code==409
    with legacy.SessionLocal() as db:
        cls=db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id==school))
        cid=cls.id
    created=client.post('/teacher/weekend/sessions',headers=th,json={'lessonId':lid,'classId':cid})
    assert created.status_code==200,created.text
    sid=created.json()['id']
    second=client.post('/teacher/weekend/sessions',headers=th,json={'lessonId':lid,'classId':cid})
    assert second.status_code==200,second.text
    sid2=second.json()['id']
    # Later draft edits must not change either frozen classroom or stop its start.
    d=saved.json();body.update(expectedRevision=d['revision'],approve=False,title='later draft')
    assert client.put(base,headers=th,json=body).status_code==200
    assert client.post(f'/teacher/weekend/sessions/{sid}/start',headers=th).status_code==200
    state_url=f'/weekend/writing/sessions/{sid}'
    assert client.get(state_url,headers=sh).json()['nodes']==[]
    state=client.get(state_url,headers=th).json();assert state['title']=='我最喜欢的季节'
    released=client.post(f'/teacher/weekend/writing/sessions/{sid}/release',headers=th,json={'expectedRevision':0,'nodeIds':['task']})
    assert released.status_code==200,released.text
    public=client.get(state_url,headers=sh).json()
    assert [n['id'] for n in public['nodes']]==['task']
    assert client.get(f'/weekend/writing/sessions/{sid2}',headers=sh).json()['nodes']==[]
    tasks=client.get(f'/student/weekend/sessions/{sid}/written',headers=sh).json()
    assert len(tasks['questions'])==1,tasks
    qid=tasks['questions'][0]['id']
    # Upload remains accepted after classroom has moved away from practice.
    assert client.post(f'/teacher/weekend/sessions/{sid}/goto',headers=th,json={'stage':6}).status_code==200
    for revision in range(2):
        reply=client.post(f'/student/weekend/sessions/{sid}/written/{qid}',headers=sh,
            data={'revision':revision,'text':'我的作文'},files=[('photos',('a.png',photo,'image/png')),('photos',('b.png',photo,'image/png'))])
        assert reply.status_code==200,reply.text
        assert reply.json()['versionNo']==revision+1
    versions=client.get(f'/student/weekend/sessions/{sid}/written/{qid}/versions',headers=sh).json()['versions']
    assert len(versions)==2 and len(versions[-1]['photos'])==2
    assert base64.b64decode(versions[-1]['photos'][0]['originalBase64'])==photo
    ann=client.post(f'/teacher/weekend/sessions/{sid}/written/{qid}/students/{student}/annotate',headers=th,
        json={'submissionVersionId':versions[-1]['id'],'verdict':'needs_revision','comment':'补充感官描写','shapes':[{'kind':'circle','x':1,'y':1,'w':5,'h':5}]})
    assert ann.status_code==200,ann.text
    feedback=f'/teacher/weekend/writing/sessions/{sid}/feedback'
    b=dict(expectedRevision=1,studentId=student,comment='已完成初稿',nextStep='补充感官描写',publish=False)
    draft=client.post(feedback,headers=th,json=b);assert draft.status_code==200,draft.text
    assert client.get(state_url,headers=sh).json()['feedback'] is None
    b.update(expectedRevision=2,publish=True)
    assert client.post(feedback,headers=th,json=b).status_code==200
    assert client.get(state_url,headers=sh).json()['feedback']['comment']=='已完成初稿'
    assert not calls,'Writing documents/submissions must not invoke external AI'
    assert client.get('/v1/weekend-writing').status_code==200
    print('OK')
''')


def test_writing_bundle_bulk_review_routes_and_start_gate(tmp_path):
    helpers.run_isolated(tmp_path,helpers.COMMON+r'''
import base64, io
from datetime import datetime
from PIL import Image
from fastapi.testclient import TestClient
from app import app
image=io.BytesIO();Image.new('RGB',(8,8),'orange').save(image,format='PNG')
data_url='data:image/png;base64,'+base64.b64encode(image.getvalue()).decode()
model_text='秋天的果园里，苹果在阳光下发亮。'+('我沿着田埂慢慢向前，听见风吹麦浪的沙沙声，也闻到桂花淡淡的香气。'*8)
nodes=[
 {'id':'review','kind':'text','role':'review','text':'回顾上次的观察记录。','status':'pending'},
 {'id':'model','kind':'text','role':'model','text':model_text,'status':'pending'},
 {'id':'model-pic','kind':'image','role':'model_image','text':'','dataUrl':data_url,'targets':['model'],'status':'pending'},
 {'id':'picture','kind':'image','role':'picture','text':'','dataUrl':data_url,'targets':[],'status':'pending'},
 {'id':'method','kind':'text','role':'method','text':'按空间顺序描写，并调动多种感官。','status':'pending'},
 {'id':'task','kind':'text','role':'task','text':'我最喜欢的季节','status':'pending'},
 {'id':'feedback','kind':'text','role':'feedback','text':'检查描写顺序和感官细节。','status':'pending'},
 {'id':'unassigned','kind':'text','role':'pending','text':'本次课程暂不使用的原始练习页。','status':'pending'},
]
bundle={'schemaVersion':1,'subject':'语文','items':[{'lessonNo':13,'writingPackage':{'title':'我最喜欢的季节','nodes':nodes}}]}
with TestClient(app) as client:
 th,sh,student,school=setup(client)
 imported=client.post('/teacher/weekend/lessons/import',headers=th,data={'subject':'语文','lessonNo':'13','courseType':'writing'},files={'file':('writing.json',json.dumps(bundle,ensure_ascii=False).encode(),'application/json')})
 assert imported.status_code==200,imported.text
 lid=imported.json()['lessonId'];url=f'/teacher/weekend/lessons/{lid}/writing';data=client.get(url,headers=th).json()
 assert data['readiness']['pendingMaterials']==8 and not data['readiness']['canStart']
 with legacy.SessionLocal() as db:
  from changying.services.weekend_course_types import register_weekend_course_type_tables
  from sqlalchemy import insert
  materials=register_weekend_course_type_tables(legacy)['materials']
  teacher_id=client.get('/session',headers=th).json()['userID']
  for status,part in [('confirmed','confirmed-scene.png'),('pending','pending-scene.png')]:
   db.execute(insert(materials).values(school_id=school,lesson_id=lid,source_file='lesson.docx',source_part=part,
    source_sha256=(part.encode().hex()+'0'*64)[:64],source_format='docx',media_type='image/png',data_url=data_url,
    status=status,relationship='picture_writing' if status=='confirmed' else '',stage_no=3 if status=='confirmed' else None,
    sort_order=1,revision=1,created_by=teacher_id,created_at=datetime.utcnow()))
  db.commit()
 imported_images=client.post(url+'/imported-images',headers=th)
 assert imported_images.status_code==200,imported_images.text
 data=imported_images.json();assert data['created']==1 and data['revision']==2
 added=next(n for n in data['package']['nodes'] if n.get('importedMaterialId'))
 assert added['status']=='pending' and added['role']=='picture' and not added['targets']
 repeated=client.post(url+'/imported-images',headers=th)
 assert repeated.status_code==200 and repeated.json()['created']==0 and repeated.json()['revision']==2
 bulk=f'/teacher/weekend/lessons/{lid}/writing/bulk-review'
 assert client.post(bulk,headers=sh,json={'expectedRevision':data['revision'],'action':'confirm_assigned'}).status_code==403
 first=client.post(bulk,headers=th,json={'expectedRevision':data['revision'],'action':'confirm_assigned'})
 assert first.status_code==200,first.text
 data=first.json();assert data['updated']==8 and data['revision']==3 and not data['package']['approved']
 assert data['readiness']['pendingMaterials']==1 and not data['readiness']['canStart']
 assert client.post(bulk,headers=th,json={'expectedRevision':2,'action':'ignore_unassigned'}).status_code==409
 second=client.post(bulk,headers=th,json={'expectedRevision':data['revision'],'action':'ignore_unassigned'})
 assert second.status_code==200,second.text
 data=second.json();assert data['updated']==1 and data['readiness']['pendingMaterials']==0
 assert not data['readiness']['canStart'] and not data['package']['approved']
 nodes=data['package']['nodes']
 ignored=next(n for n in nodes if n['role']=='pending')
 assert ignored['status']=='ignored' and '原始练习页' in ignored['text']
 model=next(n for n in nodes if n['role']=='model')
 model_pic=next(n for n in nodes if n['role']=='model_image')
 assert model_pic['targets']==[model['id']]
 saved=client.put(url,headers=th,json={'expectedRevision':data['revision'],'nodes':nodes,'title':'我最喜欢的季节','approve':True})
 assert saved.status_code==200,saved.text
 assert saved.json()['readiness']['canStart'] and saved.json()['package']['approved']
 assert len(saved.json()['package']['history'])==3
 assert not calls
 print('OK: bulk review is teacher-only, revision guarded, auditable, and preserves final approval gate')
''')

