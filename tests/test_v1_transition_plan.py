from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_transition_plan_is_explicit_append_only_and_does_not_mutate_student_state(tmp_path):
    db_path = tmp_path / "transition-plan.sqlite3"
    script = r"""
from fastapi.testclient import TestClient
import app_v924 as legacy
from app import app

def login_change(client,u,p,n):
    x=client.post('/login',json={'username':u,'password':p,'remember':False}); assert x.status_code==200,x.text
    t=x.json()['token']
    y=client.post('/change-password',headers={'Authorization':'Bearer '+t},json={'current_password':p,'new_password':n,'remember':False}); assert y.status_code==200,y.text
    return y.json()['token']

with TestClient(app) as client:
    tt=login_change(client,'teacher1','123456','Teacher1234')
    st=login_change(client,'student1','123456','Student1234')
    th={'Authorization':'Bearer '+tt}; sh={'Authorization':'Bearer '+st}
    sid=client.get('/session',headers=sh).json()['userID']
    with legacy.SessionLocal() as db:
        student=db.get(legacy.User,sid)
        before=(student.grade, db.scalar(legacy.select(legacy.func.count()).select_from(legacy.ClassStudent).where(legacy.ClassStudent.student_id==sid)),
                db.scalar(legacy.select(legacy.func.count()).select_from(legacy.LearningEvidenceEvent)),
                db.scalar(legacy.select(legacy.func.count()).select_from(legacy.PointLedger)))
    payload={'transitionType':'五升六','previousStage':'五年级事实回看','nextStageRequirement':'六年级要求由教师填写',
      'prerequisiteCheck':['分数与小数'],'gaps':['待教师确认'],'plan':['每周复查一次'],'holidayIntervention':['暑期练习'],'openingDiagnosis':['开学诊断'],'nextStage':'进入六年级后复查'}
    r=client.post(f'/v1/students/{sid}/transition-plans',headers=th,json=payload); assert r.status_code==200,r.text
    body=r.json(); assert body['studentID']==sid and body['status']=='active' and body['plan']==['每周复查一次']
    history=client.get(f'/v1/students/{sid}/transition-plans',headers=th); assert history.status_code==200 and len(history.json()['plans'])==1
    forbidden=client.post(f'/v1/students/{sid}/transition-plans',headers=sh,json=payload); assert forbidden.status_code==403
    closed=client.post(f"/v1/students/{sid}/transition-plans/{body['id']}/close",headers=th); assert closed.status_code==200 and closed.json()['status']=='closed'
    history2=client.get(f'/v1/students/{sid}/transition-plans',headers=th).json()['plans']; assert len(history2)==1 and history2[0]['status']=='closed'
    with legacy.SessionLocal() as db:
        student=db.get(legacy.User,sid)
        after=(student.grade, db.scalar(legacy.select(legacy.func.count()).select_from(legacy.ClassStudent).where(legacy.ClassStudent.student_id==sid)),
               db.scalar(legacy.select(legacy.func.count()).select_from(legacy.LearningEvidenceEvent)),
               db.scalar(legacy.select(legacy.func.count()).select_from(legacy.PointLedger)))
        audits=db.scalars(legacy.select(legacy.AuditLog).where(legacy.AuditLog.action.in_(['student.transition_plan.create','student.transition_plan.close']))).all()
    assert before==after
    assert len(audits)==2
"""
    env=os.environ.copy(); env.update({
      "DATABASE_URL":f"sqlite:///{db_path}",
      "JWT_SECRET":"integration-test-jwt-secret-0123456789abcdef0123456789abcdef",
      "COMMERCIAL_ADMIN_KEY":"integration-test-commercial-key-0123456789",
      "ENABLE_DEMO_SEED":"1","PYTHONPATH":str(ROOT),
    })
    result=subprocess.run([sys.executable,"-c",script],cwd=ROOT,env=env,capture_output=True,text=True,timeout=120)
    assert result.returncode==0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
