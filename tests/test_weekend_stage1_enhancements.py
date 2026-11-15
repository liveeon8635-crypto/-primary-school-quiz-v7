"""Stage 1 weekend enhancements: material grouping, 0-practice start block, missing-figure guard, and manual practice sync."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('stage1_helpers', ROOT / 'tests/test_weekend_example_review.py')
ex_helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ex_helpers
spec.loader.exec_module(ex_helpers)

COMMON = ex_helpers.COMMON


def test_material_group_preview_and_apply(tmp_path):
    ex_helpers.helpers.run_isolated(tmp_path, COMMON + r'''
th, lid, ok_id, dup_id, decimal_id, class_id = prepare(client)
base = '/teacher/weekend/lessons/' + str(lid)
mixed = (
    "例1：已知长方形长8厘米、宽5厘米，面积是多少？\n\n"
    "随堂练习\n"
    "第1题 一个正方形边长6厘米，面积是多少平方厘米？\n\n"
)
r = client.post(base + '/materials/preview', headers=th, data={'text': mixed})
assert r.status_code == 200, r.text
body = r.json()
assert body['counts']['example'] == 1 and body['counts']['practice'] == 1, body

# Ambiguous material without heading/marker stays pending and never enters practice
ambig = "补充思考：把两个完全一样的三角形拼成一个平行四边形。"
r2 = client.post(base + '/materials/preview', headers=th, data={'text': ambig})
assert r2.status_code == 200, r2.text
assert r2.json()['counts']['pending'] == 1, r2.json()

# Apply with one example, one practice, and one pending item
payload = {
    "items": [
        {"text": "例3：已知长方形长8厘米、宽5厘米，面积是多少？", "role": "example"},
        {
            "text": "一个正方形边长6厘米，面积是多少平方厘米？",
            "role": "practice",
            "options": ["24", "36", "12"],
            "correctIndex": 1,
            "explanation": "6×6=36",
            "knowledge": "正方形面积",
        },
        {"text": ambig, "role": "pending"},
    ]
}
applied = client.post(base + '/materials/apply', headers=th, json=payload)
assert applied.status_code == 200, applied.text
res = applied.json()
assert res['addedExamples'] == 1 and res['addedChoices'] == 1 and res['skippedPending'] == 1, res

# Verify pending item did NOT enter TQ or written or examples, and new practice is still draft (active=False)
qs = client.get(base + '/questions', headers=th).json()
stems = [q['stem'] for q in qs['items']]
assert not any('补充思考' in s for s in stems), stems
new_q = [q for q in qs['items'] if '正方形边长6厘米' in q['stem']]
assert len(new_q) == 1 and new_q[0]['active'] is False, new_q
assert qs['workedExamples'][-1]['status'] == 'pending', qs['workedExamples']
print('OK')
''')


def test_zero_practice_blocks_start_and_missing_figure_guard(tmp_path):
    ex_helpers.helpers.run_isolated(tmp_path, COMMON + r'''
th, lid, ok_id, dup_id, decimal_id, class_id = prepare(client)
base = '/teacher/weekend/lessons/' + str(lid)

# 0 practiceReady blocks requireReady=True session creation
r0 = client.post('/teacher/weekend/sessions', headers=th, json={'lessonId': lid, 'classId': class_id, 'requireReady': True})
assert r0.status_code == 409, r0.text
assert '随堂练习为 0' in r0.json()['detail'], r0.json()

# Schedule and /next include practiceReady and coursewareApproved
sched = client.get('/teacher/weekend/schedule?subject=数学', headers=th).json()['items']
assert sched and all('practiceReady' in x and 'coursewareApproved' in x for x in sched), sched
assert client.get(base + '/questions', headers=th).json()['summary']['practiceReady'] == 0
nxt = client.get('/teacher/weekend/next', headers=th).json()['items']
assert any('practiceReady' in x and 'coursewareApproved' in x for x in nxt), nxt

# Add a choice question mentioning 如图 without figure -> 409 unless confirmMissingFigure=True
with legacy.SessionLocal() as db:
    program_id = db.get(legacy.TeachingLesson, lid).program_id
    school_id = db.get(legacy.TeachingLesson, lid).school_id
    fig_q = legacy.TeachingQuestion(
        school_id=school_id, program_id=program_id, lesson_id=lid, subject='数学',
        stage='lesson', level='A', knowledge='图形面积',
        stem='如图，求平行四边形的面积。', options_json='["12","24"]', correct_index=1,
        explanation='解析', active=False, figure_json='{}',
    )
    db.add(fig_q); db.commit(); fig_qid = fig_q.id

r_block = client.post(base + '/questions', headers=th, json={'approve': [fig_qid]})
assert r_block.status_code == 409, r_block.text
assert '配图' in r_block.json()['detail'], r_block.json()

r_ok = client.post(base + '/questions', headers=th, json={'approve': [fig_qid], 'confirmMissingFigure': True})
assert r_ok.status_code == 200 and r_ok.json()['practiceReady'] == 1, r_ok.json()

# Now requireReady=True succeeds
r_go = client.post('/teacher/weekend/sessions', headers=th, json={'lessonId': lid, 'classId': class_id, 'requireReady': True})
assert r_go.status_code == 200, r_go.text
print('OK')
''')


def test_running_session_manual_sync_practice(tmp_path):
    ex_helpers.helpers.run_isolated(tmp_path, COMMON + r'''
th, lid, ok_id, dup_id, decimal_id, class_id = prepare(client)
base = '/teacher/weekend/lessons/' + str(lid)

# Approve 1 choice question before starting classroom
assert client.post(base + '/questions', headers=th, json={'approve': [ok_id]}).status_code == 200
sid = client.post('/teacher/weekend/sessions', headers=th, json={'lessonId': lid, 'classId': class_id, 'requireReady': True}).json()['id']
assert client.post(f'/teacher/weekend/sessions/{sid}/start', headers=th).status_code == 200
assert client.post(f'/teacher/weekend/sessions/{sid}/goto', headers=th, json={'stage': 4}).status_code == 200

# Approve another choice question & a written question while classroom is running
w_tpl = client.get(base + '/written/questions', headers=th).json()['items']
with legacy.SessionLocal() as db:
    school_id = db.get(legacy.TeachingLesson, lid).school_id
    teacher_id = db.scalar(select(legacy.User.id).where(legacy.User.role == 'teacher', legacy.User.school_id == school_id))
    wt = register_written_tables(legacy)['questions']
    wid = int(db.execute(wt.insert().values(
        school_id=school_id, teacher_id=teacher_id, lesson_id=lid, session_id=0,
        stem='新加的简答题：写出计算步骤。', reference='底乘高',
        hints_json=json.dumps({'approved': False, 'type': 'short_answer', 'hints': [], 'figure': {}}, ensure_ascii=False),
    )).inserted_primary_key[0])
    db.commit()

assert client.post(base + '/questions', headers=th, json={'approve': [decimal_id]}).status_code == 200
assert client.post(base + '/written/questions', headers=th, json={'approve': [wid]}).status_code == 200

# Running classroom must NOT auto-push the newly approved questions
st_before = client.get(f'/teacher/weekend/sessions/{sid}', headers=th).json()
assert st_before['pendingPracticeSync'] == 2, st_before
sh = {'Authorization': 'Bearer ' + client.post('/login', json={'username': 'student1', 'password': 'Student1234', 'remember': False}).json()['token']}
pr_before = client.get('/student/weekend/current', headers=sh).json()
assert len(pr_before['questions']) == 1, pr_before

# Manual sync pushes both newly approved questions without touching existing state
synced = client.post(f'/teacher/weekend/sessions/{sid}/sync-practice', headers=th)
assert synced.status_code == 200, synced.text
sj = synced.json()
assert sj['addedChoices'] == 1 and sj['addedWritten'] == 1 and sj['addedTotal'] == 2 and sj['pendingPracticeSync'] == 0, sj

pr_after = client.get('/student/weekend/current', headers=sh).json()
assert len(pr_after['questions']) == 2, pr_after
wr_after = client.get(f'/student/weekend/sessions/{sid}/written', headers=sh).json()
assert len(wr_after['questions']) == 1, wr_after
print('OK')
''')
