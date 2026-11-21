"""Moving the practice board must never publish or erase answers by itself."""
import importlib.util
import sys
from pathlib import Path


spec = importlib.util.spec_from_file_location('practice_slide_helpers', Path(__file__).with_name('test_homework_solve.py'))
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


SETUP = r'''
with TestClient(app) as client:
    with legacy.SessionLocal() as db:
        teacher = db.scalar(select(legacy.User).where(legacy.User.username == 'teacher1'))
        student = db.scalar(select(legacy.User).where(legacy.User.username == 'student1'))
        sec = db.scalar(select(legacy.UserSecurity).where(legacy.UserSecurity.user_id == teacher.id))
        program = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == teacher.school_id))
        lesson = legacy.TeachingLesson(school_id=teacher.school_id, program_id=program.id, subject='数学', lesson_no=909,
            title='图形的运动', core_target='旋转', duration_min=90, teacher_plan='环节1：观察', reading_plan='')
        db.add(lesson); db.flush(); lid = lesson.id
        cls = db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id == teacher.school_id))
        cls.teacher_id = teacher.id
        link = db.scalar(select(legacy.ClassStudent).where(legacy.ClassStudent.student_id == student.id))
        if link:
            link.class_id = cls.id
        else:
            db.add(legacy.ClassStudent(class_id=cls.id, student_id=student.id))
        for stem in ('第一道题', '第二道题'):
            db.add(legacy.TeachingQuestion(school_id=teacher.school_id, program_id=program.id, lesson_id=lid,
                subject='数学', stage='lesson', level='B', knowledge='旋转中心', stem=stem,
                options_json='["甲","乙"]', correct_index=0, explanation='解析', active=True))
        db.commit()
        sec.must_change_password = False; db.commit()
        th = {'Authorization': 'Bearer ' + legacy.make_token(teacher, sec)}
        class_id = cls.id
    sid = client.post('/teacher/weekend/sessions', headers=th, json={'lessonId': lid, 'classId': class_id}).json()['id']
    base = '/teacher/weekend/sessions/' + str(sid)
'''


def test_moving_the_board_does_not_publish_answers(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + SETUP + r'''
    assert client.post(base + '/start', headers=th).status_code == 200
    assert client.post(base + '/goto', headers=th, json={'stage': 4}).status_code == 200
    moved = client.post(base + '/slide', headers=th, json={'delta': 1}).json()
    assert moved['deck']['index'] == 1, moved['deck']
    assert moved['answerRelease']['published'] == 0, moved['answerRelease']
    assert moved['answerRelease']['currentPublished'] is False, moved['answerRelease']
    print('OK')
''')


def test_board_move_does_not_erase_published_answers(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + SETUP + r'''
    assert client.post(base + '/start', headers=th).status_code == 200
    assert client.post(base + '/goto', headers=th, json={'stage': 4}).status_code == 200
    assert client.post(base + '/slide', headers=th, json={'delta': 1}).status_code == 200
    published = client.post(base + '/publish-answers', headers=th, json={'question': 1})
    assert published.status_code == 200, published.text
    assert published.json()['answerRelease']['published'] == 1, published.json()['answerRelease']
    forward = client.post(base + '/slide', headers=th, json={'delta': 1}).json()
    assert forward['deck']['index'] == 1, forward['deck']
    assert forward['answerRelease']['published'] == 1, forward['answerRelease']
    back = client.post(base + '/slide', headers=th, json={'delta': -1}).json()
    assert back['deck']['index'] == 0, back['deck']
    assert back['answerRelease']['published'] == 1, back['answerRelease']
    print('OK')
''')
