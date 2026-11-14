"""例题逐题审核、独立导题、第4环节可用题数：全部走生产应用入口的真实路由。"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('example_review_helpers', ROOT/'tests/test_homework_solve.py')
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)

COMMON = helpers.COMMON + r'''
import atexit
from changying.web.weekend_written import register_written_tables

# Each case runs at module top level, so enter the app lifespan here and let it
# close at interpreter exit; assertions still fail the subprocess with a traceback.
client = TestClient(app)
client.__enter__()
atexit.register(lambda: client.__exit__(None, None, None))

EX1 = "平行四边形底6厘米、高4厘米，面积是多少平方厘米？"
EX2 = "三角形底8厘米、高5厘米，面积是多少平方厘米？"

def prepare(client):
    th, sh, student, school = setup(client)
    with legacy.SessionLocal() as db:
        teacher = db.scalar(select(legacy.User).where(legacy.User.username=='teacher1'))
        program = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id==school))
        lesson = legacy.TeachingLesson(school_id=school,program_id=program.id,subject='数学',lesson_no=918,
            title='多边形的面积',core_target='平行四边形与三角形的面积',duration_min=90,teacher_plan='环节1：复习\n环节2：讲解',
            reading_plan='',examples_json=json.dumps([EX1,EX2],ensure_ascii=False))
        db.add(lesson);db.flush();lid=lesson.id
        ok=legacy.TeachingQuestion(school_id=school,program_id=program.id,lesson_id=lid,subject='数学',stage='lesson',
            level='B',knowledge='梯形面积',stem='梯形上底3厘米、下底5厘米、高4厘米，面积是多少平方厘米？',options_json='["16平方厘米","32平方厘米"]',
            correct_index=0,explanation='验算：(3+5)×4÷2=16',active=False)
        dup=legacy.TeachingQuestion(school_id=school,program_id=program.id,lesson_id=lid,subject='数学',stage='lesson',
            level='B',knowledge='平行四边形面积',stem=EX1,options_json='["24平方厘米","12平方厘米"]',
            correct_index=0,explanation='验算：6×4=24',active=False)
        decimal=legacy.TeachingQuestion(school_id=school,program_id=program.id,lesson_id=lid,subject='数学',stage='lesson',
            level='C',knowledge='小数乘法',stem='2.5×4等于多少？',options_json='["10","100"]',
            correct_index=0,explanation='验算：2.5×4=10',active=False)
        db.add(ok);db.add(dup);db.add(decimal);db.flush()
        cls = db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id==school));cls.teacher_id=teacher.id
        link = db.scalar(select(legacy.ClassStudent).where(legacy.ClassStudent.student_id==student))
        if link:link.class_id=cls.id
        else:db.add(legacy.ClassStudent(class_id=cls.id,student_id=student))
        db.commit()
        ids=(lid,ok.id,dup.id,decimal.id,cls.id)
    return (th,)+ids
'''


def test_example_review_states_and_page_wiring(tmp_path):
    helpers.run_isolated(tmp_path, COMMON+r'''
th,lid,ok_id,dup_id,decimal_id,class_id = prepare(client)
base='/teacher/weekend/lessons/'+str(lid)
d=client.get(base+'/questions',headers=th).json()
assert len(d['workedExamples'])==2,d['workedExamples']
assert all(e['status']=='pending' for e in d['workedExamples']),d['workedExamples']
assert d['summary']['exampleCount']==2 and d['summary']['examplePending']==2,d['summary']
assert d['summary']['practiceReady']==0,d['summary']
assert d['summary']['coursewareApproved'] is False,d['summary']

r=client.post(base+'/examples/review',headers=th,json={'approve':[0]})
assert r.status_code==200,r.text
got=r.json()
assert got['workedExamples'][0]['status']=='approved',got
assert got['summary']['examplePending']==1,got['summary']
assert '已更新 1 道例题' in got['message'],got['message']

r=client.post(base+'/examples/review',headers=th,json={'retract':[0]})
assert r.json()['workedExamples'][0]['status']=='pending',r.text

r=client.post(base+'/examples/review',headers=th,json={'approveAll':True})
assert r.json()['summary']['examplePending']==0,r.text
assert r.json()['summary']['exampleApproved']==2,r.text

# 改过例题内容（同一位置换了题干）必须回到“待重新审核”，不能继续沿用旧审核。
with legacy.SessionLocal() as db:
    row=db.get(legacy.TeachingLesson,lid)
    row.examples_json=json.dumps([EX1,'三角形底8厘米、高6厘米，面积是多少平方厘米？'],ensure_ascii=False)
    db.commit()
got=client.get(base+'/questions',headers=th).json()['workedExamples']
assert got[0]['status']=='approved' and got[1]['status']=='changed',got

# 越界序号不能静默通过。
assert client.post(base+'/examples/review',headers=th,json={'approve':[9]}).status_code==400

# 页面接线：导入入口、逐题审核按钮、题数分列都在真实页面上。
html=client.get('/v1/weekend-plan').text
for marker in ('单独导入随堂练习','核对通过','撤回审核','data-practice-import','data-practice-summary','单独导入随堂练习（不动教案和例题）'):
    assert marker in html,marker
print('OK')
''')


def test_practice_ready_counts_only_non_duplicate_approved(tmp_path):
    helpers.run_isolated(tmp_path, COMMON+r'''
th,lid,ok_id,dup_id,decimal_id,class_id = prepare(client)
base='/teacher/weekend/lessons/'+str(lid)
q=client.get(base+'/questions',headers=th).json()['items']
by_id={item['id']:item for item in q}
assert by_id[dup_id]['duplicateOf']=='例1',by_id[dup_id]
# 小数点和整数乘法不是同一道题：2.5×4 不能因为去掉点号被当成 25×4。
assert by_id[decimal_id]['duplicateOf']=='',by_id[decimal_id]

r=client.post(base+'/questions',headers=th,json={'approve':[dup_id]})
assert r.status_code==409,r.text
assert '例题' in r.json()['detail'],r.json()

r=client.post(base+'/questions',headers=th,json={'approve':[ok_id]})
assert r.status_code==200,r.text
assert r.json()['practiceReady']==1,r.json()

# 撤回通过：题不再发放，但题目本身还在备课里。
r=client.post(base+'/questions',headers=th,json={'retract':[ok_id]})
assert r.json()['practiceReady']==0,r.text
items={item['id']:item for item in client.get(base+'/questions',headers=th).json()['items']}
assert items[ok_id]['active'] is False,items[ok_id]

# 已经通过的文字题与例题重复时也能撤回，撤回后仍保留这道备课题。
with legacy.SessionLocal() as db:
    written=register_written_tables(legacy)['questions']
    db.execute(written.insert().values(school_id=1,teacher_id=db.scalar(select(legacy.User.id).where(legacy.User.username=='teacher1')),
        lesson_id=lid,session_id=0,stem=EX1,reference='教师参考答案',
        hints_json=json.dumps({'approved':True,'type':'short_answer','hints':[]},ensure_ascii=False)))
    db.commit()
w=client.get(base+'/written/questions',headers=th).json()['items']
assert w and w[0]['duplicateOf']=='例1',w
r=client.post(base+'/written/questions',headers=th,json={'retract':[w[0]['id']]})
assert r.status_code==200,r.text
w2=client.get(base+'/written/questions',headers=th).json()['items']
assert w2 and w2[0]['approved'] is False,w2
print('OK')
''')


def test_practice_import_keeps_lesson_untouched(tmp_path):
    helpers.run_isolated(tmp_path, COMMON+r'''
th,lid,ok_id,dup_id,decimal_id,class_id = prepare(client)
base='/teacher/weekend/lessons/'+str(lid)
with legacy.SessionLocal() as db:
    before=db.get(legacy.TeachingLesson,lid)
    before_title=before.title;before_examples=before.examples_json;before_updated=before.updated_at
replies.append(json.dumps({"questions":[
    {"stem":EX1,"options":["24平方厘米","12平方厘米"],"correctIndex":0,"explanation":"与例题相同","knowledge":"平行四边形面积"},
    {"stem":"一个平行四边形底9厘米、高3厘米，面积是多少平方厘米？","options":["27平方厘米","12平方厘米"],"correctIndex":0,"explanation":"验算：9×3=27","knowledge":"平行四边形面积"}],
    "writtenQuestions":[{"type":"short_answer","material":"","stem":"一个梯形上底4厘米、下底6厘米、高5厘米，面积是多少平方厘米？","reference":"25 平方厘米","hints":[]}]},ensure_ascii=False))
r=client.post(base+'/practice/import',headers=th,data={'text':'第1题 平行四边形面积 24 平方厘米；第2题 平行四边形底9厘米高3厘米'})
assert r.status_code==200,r.text
got=r.json()
assert got['choices']==1,got
assert got['written']==1,got
assert got['droppedDuplicate']==1,got
assert '待审核' in got['message'],got['message']

items=client.get(base+'/questions',headers=th).json()['items']
new=[item for item in items if '底9厘米' in item['stem']]
assert len(new)==1 and new[0]['active'] is False,items
assert len([item for item in items if item['stem']==EX1])==1,items

with legacy.SessionLocal() as db:
    after=db.get(legacy.TeachingLesson,lid)
    assert after.title==before_title and after.examples_json==before_examples,after.examples_json
    assert after.updated_at==before_updated,(after.updated_at,before_updated)

# 识别不出题时明确报错，不写任何数据。
replies.append(json.dumps({"questions":[],"writtenQuestions":[]},ensure_ascii=False))
r=client.post(base+'/practice/import',headers=th,data={'text':'这份材料里其实没有题目，只是一些说明文字。'})
assert r.status_code==502,r.text
print('OK')
''')


def test_stage4_without_practice_says_so_on_board(tmp_path):
    helpers.run_isolated(tmp_path, COMMON+r'''
th,lid,ok_id,dup_id,decimal_id,class_id = prepare(client)
sid=client.post('/teacher/weekend/sessions',headers=th,json={'lessonId':lid,'classId':class_id}).json()['id']
assert client.post('/teacher/weekend/sessions/'+str(sid)+'/start',headers=th).status_code==200
for _ in range(3):
    r=client.post('/teacher/weekend/sessions/'+str(sid)+'/next',headers=th)
    assert r.status_code==200,r.text
state=client.get('/teacher/weekend/sessions/'+str(sid)+'/board',headers=th).json()
assert state['currentStage']==4,state
text='\n'.join(state['content'])
assert '没有可用的随堂练习' in text,text
assert '单独导入随堂练习' in text,text
print('OK')
''')


def test_duplicate_guard_is_not_fooled_by_short_options_or_fraction(tmp_path):
    helpers.run_isolated(tmp_path, COMMON+r"""
th,lid,ok_id,dup_id,decimal_id,class_id = prepare(client)
base='/teacher/weekend/lessons/'+str(lid)
import changying.services.weekend_question_gen as qg
from changying.web.weekend_plan_views import _worked_example_match_text
from changying.services.weekend_answers import _question_key

# 分数线是题目内容，不是标点：1/2+1/3 与 12+13 是两道不同的题。
assert qg.question_key('计算 1/2+1/3=')!=qg.question_key('计算 12+13=')
assert qg.question_key('计算 1/2+1/3=')==qg.question_key('计算 1／2+1／3=')

# 审核页与第4环节必须用同一段文字比对：版面头“第3题（基础）（4分）”“原题｜”不能留在键里，
# 否则审核页说“与例3重复”，课堂照样把这道题发给学生。
page='第3题（基础）（4分）\n原题｜计算 2.5×4=？'
assert _question_key(_worked_example_match_text(page))==qg.question_key('计算 2.5×4=？')

with legacy.SessionLocal() as db:
    program_id=db.get(legacy.TeachingLesson,lid).program_id
    for stem,opts in (('判断：平行四边形的对边相等。',['√','×']),('判断：长方形也是平行四边形。',['√','×']),
                      ('下面哪个数是偶数？',['3','4','5','6'])):
        db.add(legacy.TeachingQuestion(school_id=db.get(legacy.TeachingLesson,lid).school_id,program_id=program_id,lesson_id=lid,subject='数学',
            stage='lesson',level='B',knowledge='图形的认识',stem=stem,options_json=json.dumps(opts,ensure_ascii=False),
            correct_index=0,explanation='解析',active=False))
    db.commit()

# 短选项（√／×、只差一位的数字）在互不相干的题里天天出现，不能拿来判重。
items=client.get(base+'/questions',headers=th).json()['items']
judge=[i for i in items if i['stem'].startswith('判断')]
assert len(judge)==2 and all(i['duplicateOf']=='' for i in judge),judge
assert all(i['duplicateOf']=='' for i in items if i['stem'].startswith('下面哪个数')),items
ids=[i['id'] for i in judge]
r=client.post(base+'/questions',headers=th,json={'approve':ids})
assert r.status_code==200,r.text
assert r.json()['practiceReady']>=2,r.json()

# 正在上课时撤回已通过的题必须被拦下：第4环节现查“已通过”的题，撤回会当场少一道题、打乱答案序号。
sid=client.post('/teacher/weekend/sessions',headers=th,json={'lessonId':lid,'classId':class_id}).json()['id']
assert client.post('/teacher/weekend/sessions/'+str(sid)+'/start',headers=th).status_code==200
r=client.post(base+'/questions',headers=th,json={'retract':[ids[0]]})
assert r.status_code==409,r.text
assert '正在上课' in r.json()['detail'],r.json()
print('OK')
""")
