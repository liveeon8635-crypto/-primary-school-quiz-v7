"""Cross-scene learning evidence on Knowledge Map without altering mastery formula."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("km_ev_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_cross_scene_evidence_does_not_alter_mastery(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
from datetime import datetime
from changying.services.homework_knowledge import register_homework_knowledge_table
from changying.web.knowledge_map_student import register_knowledge_map_run_table
from changying.web.weekend_practice import register_practice_tables

with TestClient(app) as client:
    th, sh, student_id, school_id = setup(client)
    created = client.post('/teacher/knowledge-maps', headers=th, json={'template': 'rj2026-g5-math-up'})
    assert created.status_code == 200, created.text
    mid = created.json()['id']

    with legacy.SessionLocal() as db:
        teacher = db.scalar(select(legacy.User).where(legacy.User.username == 'teacher1'))
        cls = db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id == school_id))
        cls.teacher_id = teacher.id
        if db.scalar(select(legacy.ClassStudent).where(legacy.ClassStudent.class_id == cls.id, legacy.ClassStudent.student_id == student_id)) is None:
            db.add(legacy.ClassStudent(class_id=cls.id, student_id=student_id))
        db.commit()
        cid = cls.id

    pub = client.post(f'/teacher/knowledge-maps/{mid}/publish', headers=th, json={'revision': created.json()['revision']})
    assert pub.status_code == 200, pub.text

    # Baseline mastery before cross-scene records
    base = client.get(f'/teacher/knowledge-maps/{mid}/classes/{cid}', headers=th)
    assert base.status_code == 200, base.text
    base_st = [s for s in base.json()['students'] if s['id'] == student_id][0]
    assert base_st['evidence'] == [], base_st

    # Insert cross-scene records: weekend answer with hint, homework AI help, knowledge_map run
    with legacy.SessionLocal() as db:
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        tq = legacy.TeachingQuestion(
            school_id=school_id, program_id=p.id, lesson_id=None, subject='数学', stage='lesson',
            level='B', knowledge='小数乘整数', stem='0.5×4=?', options_json='["2","20"]',
            correct_index=0, explanation='2', active=True,
        )
        db.add(tq); db.flush()
        pt = register_practice_tables(legacy)
        db.execute(pt['answers'].insert().values(
            school_id=school_id, session_id=1, student_id=student_id, question_id=tq.id,
            selected=0, correct=True, max_hint=2, created_at=datetime(2026, 11, 14, 10, 0),
        ))
        hk = register_homework_knowledge_table(legacy)
        db.execute(hk.insert().values(
            school_id=school_id, student_id=student_id, help_id=88, grade=5, subject='数学',
            knowledge_key='小数乘整数', raw_knowledge='小数乘整数', matched=True,
            question_excerpt='3.2×5 怎么算', verify_status='skipped', created_at=datetime(2026, 11, 14, 18, 0),
        ))
        runs = register_knowledge_map_run_table(legacy)
        db.execute(runs.insert().values(
            school_id=school_id, map_id=mid, student_id=student_id, map_revision=1,
            items_json=json.dumps([['2-1', tq.id]]), status='submitted', correct=1,
            created_at=datetime(2026, 11, 14, 9, 0), submitted_at=datetime(2026, 11, 14, 9, 5),
        ))
        db.commit()

    after = client.get(f'/teacher/knowledge-maps/{mid}/classes/{cid}', headers=th)
    assert after.status_code == 200, after.text
    data = after.json()
    assert '不直接合并或修改掌握度' in data['evidenceDisclaimer']
    st = [s for s in data['students'] if s['id'] == student_id][0]

    # Mastery formula is untouched
    assert st['nodes'] == base_st['nodes']
    assert st['units'] == base_st['units']

    # All 3 sources present with required fields and "未知" where untracked
    sources = {e['source']: e for e in st['evidence']}
    assert set(sources) == {'weekend', 'homework', 'knowledge_map'}, sources
    assert '2级' in sources['weekend']['helpStatus'] and '正确' in sources['weekend']['gradingStatus']
    assert 'AI/老师辅导' in sources['homework']['helpStatus']
    assert sources['knowledge_map']['helpStatus'] == '未知'
    assert all(k in sources['weekend'] for k in ('source', 'time', 'count', 'gradingStatus', 'helpStatus'))
    assert '查看证据' in client.get('/v1/knowledge-map').text
print('OK')
''', extra_env={'KNOWLEDGE_MAP': '1'})
