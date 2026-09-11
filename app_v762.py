import os, io, json, secrets, hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import FastAPI, HTTPException, Header, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from sqlalchemy import create_engine, String, Integer, ForeignKey, Text, DateTime, Boolean, UniqueConstraint, select, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session

# ---------------- Database ----------------
BASE = Path(__file__).resolve().parent
raw_url = os.getenv("DATABASE_URL", f"sqlite:///{BASE/'school_quiz_v7.db'}")
if raw_url.startswith("postgres://"):
    raw_url = raw_url.replace("postgres://","postgresql+psycopg://",1)
elif raw_url.startswith("postgresql://") and "+psycopg" not in raw_url:
    raw_url = raw_url.replace("postgresql://","postgresql+psycopg://",1)
engine = create_engine(
    raw_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args={"check_same_thread":False} if raw_url.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase): pass

class School(Base):
    __tablename__="schools"
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(120),unique=True,index=True)
    code:Mapped[str]=mapped_column(String(40),unique=True,index=True)
    active:Mapped[bool]=mapped_column(Boolean,default=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class User(Base):
    __tablename__="users"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    username:Mapped[str]=mapped_column(String(100),unique=True,index=True)
    password_hash:Mapped[str]=mapped_column(String(300))
    name:Mapped[str]=mapped_column(String(100))
    role:Mapped[str]=mapped_column(String(20),index=True)
    grade:Mapped[int|None]=mapped_column(Integer,nullable=True)
    active:Mapped[bool]=mapped_column(Boolean,default=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class UserSecurity(Base):
    __tablename__="user_security"
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"),primary_key=True)
    must_change_password:Mapped[bool]=mapped_column(Boolean,default=True)
    failed_login_count:Mapped[int]=mapped_column(Integer,default=0)
    locked_until:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    password_changed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)

class SchoolClass(Base):
    __tablename__="classes"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    name:Mapped[str]=mapped_column(String(120))
    grade:Mapped[int]=mapped_column(Integer)
    teacher_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class ClassStudent(Base):
    __tablename__="class_students"
    __table_args__=(UniqueConstraint("class_id","student_id",name="uq_class_student"),)
    id:Mapped[int]=mapped_column(primary_key=True)
    class_id:Mapped[int]=mapped_column(ForeignKey("classes.id"),index=True)
    student_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)

class StudentClassHistory(Base):
    __tablename__="student_class_history"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    student_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    class_id:Mapped[int]=mapped_column(ForeignKey("classes.id"),index=True)
    joined_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)
    left_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True,index=True)
    leave_reason:Mapped[str]=mapped_column(String(30),default="")
    actor_id:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    source:Mapped[str]=mapped_column(String(30),default="system")

class AssignmentRecipient(Base):
    __tablename__="assignment_recipients"
    __table_args__=(UniqueConstraint("assignment_id","student_id",name="uq_assignment_recipient"),)
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    assignment_id:Mapped[int]=mapped_column(ForeignKey("assignments.id"),index=True)
    class_id:Mapped[int]=mapped_column(ForeignKey("classes.id"),index=True)
    student_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    assigned_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    source:Mapped[str]=mapped_column(String(30),default="assignment")

class ParentStudent(Base):
    __tablename__="parent_students"
    __table_args__=(UniqueConstraint("parent_id","student_id",name="uq_parent_student"),)
    id:Mapped[int]=mapped_column(primary_key=True)
    parent_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    student_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)

class Question(Base):
    __tablename__="questions"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    grade:Mapped[int]=mapped_column(Integer,index=True)
    subject:Mapped[str]=mapped_column(String(30),index=True)
    textbook:Mapped[str]=mapped_column(String(80),default="人教版")
    semester:Mapped[str]=mapped_column(String(20),default="上册")
    unit:Mapped[str]=mapped_column(String(100),default="综合")
    knowledge:Mapped[str]=mapped_column(String(120),index=True)
    text:Mapped[str]=mapped_column(Text)
    options_json:Mapped[str]=mapped_column(Text)
    correct_index:Mapped[int]=mapped_column(Integer)
    explanation:Mapped[str]=mapped_column(Text,default="")
    creator_id:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class Paper(Base):
    __tablename__="papers"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    title:Mapped[str]=mapped_column(String(160))
    grade:Mapped[int]=mapped_column(Integer)
    subject:Mapped[str]=mapped_column(String(30))
    textbook:Mapped[str]=mapped_column(String(80),default="")
    unit:Mapped[str]=mapped_column(String(100),default="")
    question_ids_json:Mapped[str]=mapped_column(Text)
    teacher_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class Assignment(Base):
    __tablename__="assignments"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    title:Mapped[str]=mapped_column(String(160))
    class_id:Mapped[int]=mapped_column(ForeignKey("classes.id"),index=True)
    paper_id:Mapped[int]=mapped_column(ForeignKey("papers.id"),index=True)
    due_date:Mapped[str]=mapped_column(String(20))
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class Submission(Base):
    __tablename__="submissions"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    assignment_id:Mapped[int|None]=mapped_column(ForeignKey("assignments.id"),nullable=True,index=True)
    student_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    title:Mapped[str]=mapped_column(String(160),default="练习")
    score:Mapped[int]=mapped_column(Integer)
    correct:Mapped[int]=mapped_column(Integer)
    total:Mapped[int]=mapped_column(Integer)
    answers_json:Mapped[str]=mapped_column(Text,default="[]")
    submitted_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class ImportJob(Base):
    __tablename__="import_jobs"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    filename:Mapped[str]=mapped_column(String(255))
    status:Mapped[str]=mapped_column(String(20))
    summary:Mapped[str]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"))

class AuditLog(Base):
    __tablename__="audit_logs"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    user_id:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    action:Mapped[str]=mapped_column(String(100),index=True)
    detail:Mapped[str]=mapped_column(Text,default="")
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)


class TeachingProgram(Base):
    __tablename__="teaching_programs"
    __table_args__=(UniqueConstraint("school_id","academic_year","term","grade",name="uq_teaching_program_term"),)
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    title:Mapped[str]=mapped_column(String(180),default="2026年秋五年级上册语数定制教学")
    academic_year:Mapped[int]=mapped_column(Integer,default=2026,index=True)
    term:Mapped[str]=mapped_column(String(20),default="秋季")
    grade:Mapped[int]=mapped_column(Integer,default=5,index=True)
    semester:Mapped[str]=mapped_column(String(20),default="上册")
    chinese_textbook:Mapped[str]=mapped_column(String(100),default="人教版")
    math_textbook:Mapped[str]=mapped_column(String(100),default="人教版")
    pass_threshold:Mapped[int]=mapped_column(Integer,default=60)
    active:Mapped[bool]=mapped_column(Boolean,default=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class TeachingLesson(Base):
    __tablename__="teaching_lessons"
    __table_args__=(UniqueConstraint("program_id","subject","lesson_no",name="uq_teaching_lesson_no"),)
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    program_id:Mapped[int]=mapped_column(ForeignKey("teaching_programs.id"),index=True)
    subject:Mapped[str]=mapped_column(String(20),index=True)
    lesson_no:Mapped[int]=mapped_column(Integer,index=True)
    unit:Mapped[str]=mapped_column(String(120),default="待配置单元")
    title:Mapped[str]=mapped_column(String(180))
    core_target:Mapped[str]=mapped_column(Text,default="")
    duration_min:Mapped[int]=mapped_column(Integer,default=120)
    teacher_plan:Mapped[str]=mapped_column(Text,default="")
    reading_plan:Mapped[str]=mapped_column(Text,default="")
    writing_plan:Mapped[str]=mapped_column(Text,default="")
    examples_json:Mapped[str]=mapped_column(Text,default="[]")
    ppt_json:Mapped[str]=mapped_column(Text,default="[]")
    closure_training:Mapped[str]=mapped_column(Text,default="")
    essay_review:Mapped[str]=mapped_column(Text,default="")
    published:Mapped[bool]=mapped_column(Boolean,default=False,index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class TeachingQuestion(Base):
    __tablename__="teaching_questions"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    program_id:Mapped[int]=mapped_column(ForeignKey("teaching_programs.id"),index=True)
    lesson_id:Mapped[int|None]=mapped_column(ForeignKey("teaching_lessons.id"),nullable=True,index=True)
    stage:Mapped[str]=mapped_column(String(20),default="lesson",index=True)
    subject:Mapped[str]=mapped_column(String(20),index=True)
    level:Mapped[str]=mapped_column(String(2),index=True)
    knowledge:Mapped[str]=mapped_column(String(160),default="")
    stem:Mapped[str]=mapped_column(Text)
    options_json:Mapped[str]=mapped_column(Text)
    correct_index:Mapped[int]=mapped_column(Integer)
    explanation:Mapped[str]=mapped_column(Text,default="")
    active:Mapped[bool]=mapped_column(Boolean,default=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class TeachingAdaptiveSession(Base):
    __tablename__="teaching_adaptive_sessions"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    program_id:Mapped[int]=mapped_column(ForeignKey("teaching_programs.id"),index=True)
    lesson_id:Mapped[int|None]=mapped_column(ForeignKey("teaching_lessons.id"),nullable=True,index=True)
    student_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    stage:Mapped[str]=mapped_column(String(20),default="lesson",index=True)
    subject:Mapped[str]=mapped_column(String(20),index=True)
    current_level:Mapped[str]=mapped_column(String(2),default="C")
    status:Mapped[str]=mapped_column(String(20),default="active",index=True)
    final_level:Mapped[str|None]=mapped_column(String(2),nullable=True)
    final_score:Mapped[int|None]=mapped_column(Integer,nullable=True)
    started_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    completed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)

class TeachingAttempt(Base):
    __tablename__="teaching_attempts"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    program_id:Mapped[int]=mapped_column(ForeignKey("teaching_programs.id"),index=True)
    session_id:Mapped[int]=mapped_column(ForeignKey("teaching_adaptive_sessions.id"),index=True)
    lesson_id:Mapped[int|None]=mapped_column(ForeignKey("teaching_lessons.id"),nullable=True,index=True)
    student_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    stage:Mapped[str]=mapped_column(String(20),default="lesson",index=True)
    subject:Mapped[str]=mapped_column(String(20),index=True)
    level:Mapped[str]=mapped_column(String(2),index=True)
    score:Mapped[int]=mapped_column(Integer)
    correct:Mapped[int]=mapped_column(Integer)
    total:Mapped[int]=mapped_column(Integer)
    answers_json:Mapped[str]=mapped_column(Text,default="[]")
    passed:Mapped[bool]=mapped_column(Boolean,default=False)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class TeachingEssay(Base):
    __tablename__="teaching_essays"
    __table_args__=(UniqueConstraint("lesson_id","student_id",name="uq_teaching_essay_student_lesson"),)
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    lesson_id:Mapped[int]=mapped_column(ForeignKey("teaching_lessons.id"),index=True)
    student_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    draft:Mapped[str]=mapped_column(Text,default="")
    revised_draft:Mapped[str]=mapped_column(Text,default="")
    teacher_feedback:Mapped[str]=mapped_column(Text,default="")
    status:Mapped[str]=mapped_column(String(20),default="draft",index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)


# ---------------- V7.5 classroom points & rewards ----------------
class PointRule(Base):
    __tablename__="point_rules"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    name:Mapped[str]=mapped_column(String(120))
    category:Mapped[str]=mapped_column(String(30),default="activity",index=True)
    points:Mapped[int]=mapped_column(Integer,default=1)
    active:Mapped[bool]=mapped_column(Boolean,default=True,index=True)
    require_note:Mapped[bool]=mapped_column(Boolean,default=False)
    sort_order:Mapped[int]=mapped_column(Integer,default=0)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class PointLedger(Base):
    __tablename__="point_ledger"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    student_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    class_id:Mapped[int|None]=mapped_column(ForeignKey("classes.id"),nullable=True,index=True)
    actor_id:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True,index=True)
    rule_id:Mapped[int|None]=mapped_column(ForeignKey("point_rules.id"),nullable=True,index=True)
    category:Mapped[str]=mapped_column(String(30),default="activity",index=True)
    points:Mapped[int]=mapped_column(Integer)
    reason:Mapped[str]=mapped_column(String(180),default="")
    note:Mapped[str]=mapped_column(Text,default="")
    source:Mapped[str]=mapped_column(String(30),default="classroom",index=True)
    related_id:Mapped[int|None]=mapped_column(Integer,nullable=True,index=True)
    reversed:Mapped[bool]=mapped_column(Boolean,default=False,index=True)
    reversal_of_id:Mapped[int|None]=mapped_column(ForeignKey("point_ledger.id"),nullable=True,index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)

class RewardItem(Base):
    __tablename__="reward_items"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    name:Mapped[str]=mapped_column(String(140))
    description:Mapped[str]=mapped_column(Text,default="")
    icon:Mapped[str]=mapped_column(String(30),default="🎁")
    cost_points:Mapped[int]=mapped_column(Integer,index=True)
    stock:Mapped[int]=mapped_column(Integer,default=0)
    unlimited_stock:Mapped[bool]=mapped_column(Boolean,default=False)
    per_student_limit:Mapped[int]=mapped_column(Integer,default=0)
    start_date:Mapped[str]=mapped_column(String(20),default="")
    end_date:Mapped[str]=mapped_column(String(20),default="")
    active:Mapped[bool]=mapped_column(Boolean,default=True,index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class RewardRedemption(Base):
    __tablename__="reward_redemptions"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    student_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    reward_id:Mapped[int]=mapped_column(ForeignKey("reward_items.id"),index=True)
    reward_name:Mapped[str]=mapped_column(String(140))
    cost_points:Mapped[int]=mapped_column(Integer)
    status:Mapped[str]=mapped_column(String(30),default="pending",index=True)
    note:Mapped[str]=mapped_column(Text,default="")
    requested_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)
    handled_by:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True,index=True)
    handled_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True,index=True)


def get_db():
    d=SessionLocal()
    try: yield d
    finally: d.close()

def security_for(db,u):
    s=db.get(UserSecurity,u.id)
    if not s:
        s=UserSecurity(user_id=u.id,must_change_password=True,failed_login_count=0)
        db.add(s);db.flush()
    return s

# ---------------- Authentication ----------------
JWT_SECRET=os.getenv("JWT_SECRET","CHANGE-ME-IN-PRODUCTION-"+secrets.token_urlsafe(24))
JWT_ALG="HS256"
ACCESS_HOURS=int(os.getenv("ACCESS_TOKEN_HOURS","12"))
REMEMBER_DAYS=int(os.getenv("REMEMBER_TOKEN_DAYS","30"))

def hash_password(password,salt=None):
    salt=salt or secrets.token_hex(16)
    digest=hashlib.scrypt(password.encode(),salt=salt.encode(),n=2**14,r=8,p=1,dklen=32).hex()
    return f"scrypt${salt}${digest}"

def verify_password(password,stored):
    try:
        alg,salt,digest=stored.split("$",2)
        return alg=="scrypt" and secrets.compare_digest(hash_password(password,salt).split("$",2)[2],digest)
    except: return False

def password_ok(password):
    return len(password)>=8 and any(ch.isalpha() for ch in password) and any(ch.isdigit() for ch in password)

def password_version(sec):
    return int(sec.password_changed_at.timestamp()) if sec.password_changed_at else 0

def make_token(u,sec,remember=False):
    now=datetime.now(timezone.utc)
    expiry=now+(timedelta(days=REMEMBER_DAYS) if remember else timedelta(hours=ACCESS_HOURS))
    return jwt.encode({
        "sub":str(u.id),"role":u.role,"school_id":u.school_id,
        "pwdv":password_version(sec),"iat":now,"exp":expiry
    },JWT_SECRET,algorithm=JWT_ALG)

def authenticated_user(authorization:Optional[str]=Header(default=None),db:Session=Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "): raise HTTPException(401,"未登录")
    try:
        payload=jwt.decode(authorization[7:],JWT_SECRET,algorithms=[JWT_ALG])
        uid=int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401,"登录已过期，请重新登录")
    except Exception:
        raise HTTPException(401,"登录令牌无效")
    u=db.get(User,uid)
    if not u or not u.active: raise HTTPException(401,"账号不可用")
    school=db.get(School,u.school_id)
    if not school or not school.active: raise HTTPException(401,"学校账号不可用")
    sec=security_for(db,u)
    if payload.get("pwdv") != password_version(sec):
        raise HTTPException(401,"登录状态已失效，请重新登录")
    return u

def current_user(u:User=Depends(authenticated_user),db:Session=Depends(get_db)):
    s=security_for(db,u)
    if s.must_change_password:
        raise HTTPException(428,"请先修改初始密码")
    return u

def need(u,*roles):
    if u.role not in roles: raise HTTPException(403,"无权限")

# ---------------- Schemas ----------------
class LoginBody(BaseModel): username:str;password:str;remember:bool=False
class ChangePasswordBody(BaseModel): current_password:str;new_password:str;remember:bool=False
class ResetPasswordBody(BaseModel): new_password:str
class ActiveBody(BaseModel): active:bool
class TransferStudentBody(BaseModel): target_class_id:int
class RestoreStudentBody(BaseModel): class_id:int
class ParentBindBody(BaseModel): parent_id:Optional[int]=None
class UserCreate(BaseModel): name:str;username:str;password:str;role:str
class ClassCreate(BaseModel): name:str;grade:int
class StudentCreate(BaseModel): name:str;username:str;password:str;grade:int;class_id:int;parent_username:Optional[str]=None
class QuestionCreate(BaseModel): grade:int;subject:str;textbook:str;semester:str;unit:str;knowledge:str;text:str;options:list[str];correct_index:int;explanation:str=""
class PaperCreate(BaseModel): title:str;grade:int;subject:str;textbook:str="";unit:str="";question_ids:list[int]
class AssignmentCreate(BaseModel): title:str;class_id:int;paper_id:int;due_date:str
class AnswerItem(BaseModel): question_id:int;selected_index:int;correct:Optional[bool]=None
class SubmitBody(BaseModel): title:Optional[str]=None;correct:Optional[int]=None;total:Optional[int]=None;score:Optional[int]=None;answers:list[AnswerItem]=[]

class TeachingProgramUpdate(BaseModel):
    title:Optional[str]=None
    chinese_textbook:Optional[str]=None
    math_textbook:Optional[str]=None
    pass_threshold:Optional[int]=None
class TeachingLessonUpdate(BaseModel):
    unit:Optional[str]=None
    title:Optional[str]=None
    core_target:Optional[str]=None
    teacher_plan:Optional[str]=None
    reading_plan:Optional[str]=None
    writing_plan:Optional[str]=None
    examples:Optional[list[str]]=None
    ppt:Optional[list[str]]=None
    closure_training:Optional[str]=None
    essay_review:Optional[str]=None
    published:Optional[bool]=None
class TeachingQuestionCreate(BaseModel):
    lesson_id:Optional[int]=None
    stage:str="lesson"
    subject:str
    level:str
    knowledge:str=""
    stem:str
    options:list[str]
    correct_index:int
    explanation:str=""
class TeachingAdaptiveStartBody(BaseModel):
    lesson_id:Optional[int]=None
    stage:str="lesson"
    subject:Optional[str]=None
class TeachingAdaptiveSubmitBody(BaseModel):
    session_id:int
    answers:list[AnswerItem]
class TeachingEssayBody(BaseModel):
    draft:str=""
    revised_draft:str=""
class TeachingEssayFeedbackBody(BaseModel):
    teacher_feedback:str
    status:str="reviewed"


class PointRuleBody(BaseModel):
    name:str
    category:str="activity"
    points:int=1
    active:bool=True
    require_note:bool=False
    sort_order:int=0
class PointRecordBody(BaseModel):
    student_ids:list[int]
    class_id:Optional[int]=None
    rule_id:Optional[int]=None
    points:Optional[int]=None
    category:Optional[str]=None
    reason:Optional[str]=None
    note:str=""
class RewardItemBody(BaseModel):
    name:str
    description:str=""
    icon:str="🎁"
    cost_points:int
    stock:int=0
    unlimited_stock:bool=False
    per_student_limit:int=0
    start_date:str=""
    end_date:str=""
    active:bool=True
class RewardRedeemBody(BaseModel):
    note:str=""
class RewardHandleBody(BaseModel):
    action:str
    note:str=""

# ---------------- Seed ----------------
def seed(db):
    school=db.scalar(select(School).where(School.code=="demo"))
    if not school:
        school=School(name="演示小学",code="demo");db.add(school);db.flush()
    defaults=[("admin","123456","平台管理员","admin",None),("teacher1","123456","王老师","teacher",None),("student1","123456","小明","student",3),("parent1","123456","小明家长","parent",None)]
    users={}
    for un,pw,name,role,grade in defaults:
        u=db.scalar(select(User).where(User.username==un))
        if not u:
            u=User(school_id=school.id,username=un,password_hash=hash_password(pw),name=name,role=role,grade=grade);db.add(u);db.flush()
        users[un]=u
    for demo_user in users.values():
        if not db.get(UserSecurity,demo_user.id):
            db.add(UserSecurity(user_id=demo_user.id,must_change_password=True,failed_login_count=0))
    cl=db.scalar(select(SchoolClass).where(SchoolClass.school_id==school.id,SchoolClass.name=="三年级一班"))
    if not cl:
        cl=SchoolClass(school_id=school.id,name="三年级一班",grade=3,teacher_id=users["teacher1"].id);db.add(cl);db.flush()
    if not db.scalar(select(ClassStudent).where(ClassStudent.class_id==cl.id,ClassStudent.student_id==users["student1"].id)):
        db.add(ClassStudent(class_id=cl.id,student_id=users["student1"].id))
    if not db.scalar(select(ParentStudent).where(ParentStudent.parent_id==users["parent1"].id,ParentStudent.student_id==users["student1"].id)):
        db.add(ParentStudent(parent_id=users["parent1"].id,student_id=users["student1"].id))
    if not db.scalar(select(Question.id).where(Question.school_id==school.id).limit(1)):
        qs=[
            (1,"数学","人教版","上册","第一单元","20以内加法","7 + 5 = ?",["10","11","12","13"],2,"7+5=12。"),
            (2,"数学","人教版","上册","第四单元","乘法口诀","7 × 8 = ?",["54","56","58","64"],1,"七八五十六。"),
            (3,"数学","人教版","上册","第一单元","时分秒","1分钟等于多少秒？",["30","60","90","100"],1,"1分钟=60秒。"),
            (3,"语文","人教版","上册","第一单元","词语","“绚丽多彩”的近义词是？",["五颜六色","灰暗无光","一模一样","安安静静"],0,"与五颜六色意思相近。"),
            (3,"英语","人教PEP","上册","Unit 1","单词","“尺子”的英文是？",["book","ruler","pencil","bag"],1,"ruler=尺子。"),
            (4,"数学","苏教版","上册","第二单元","除法","96÷8等于多少？",["10","11","12","13"],2,"96÷8=12。"),
            (5,"数学","北师大版","下册","第三单元","分数","1/2 + 1/4 = ?",["1/6","2/6","3/4","1"],2,"通分后为3/4。"),
            (6,"数学","人教版","上册","第六单元","百分数","240人中女生占45%，女生多少人？",["98","108","120","132"],1,"240×45%=108。")
        ]
        for q in qs:
            db.add(Question(school_id=school.id,grade=q[0],subject=q[1],textbook=q[2],semester=q[3],unit=q[4],knowledge=q[5],text=q[6],options_json=json.dumps(q[7],ensure_ascii=False),correct_index=q[8],explanation=q[9],creator_id=users["admin"].id))
    db.commit()

# ---------------- API helpers ----------------
def uj(u): return {"id":u.id,"username":u.username,"name":u.name,"role":u.role,"grade":u.grade,"active":bool(u.active)}
def qj(q): return {"id":q.id,"grade":q.grade,"subject":q.subject,"textbook":q.textbook,"semester":q.semester,"unit":q.unit,"knowledge":q.knowledge,"text":q.text,"options":json.loads(q.options_json),"correctIndex":q.correct_index,"explanation":q.explanation}
def qj_public(q): return {"id":q.id,"grade":q.grade,"subject":q.subject,"textbook":q.textbook,"semester":q.semester,"unit":q.unit,"knowledge":q.knowledge,"text":q.text,"options":json.loads(q.options_json)}
def pj(p): return {"id":p.id,"title":p.title,"grade":p.grade,"subject":p.subject,"textbook":p.textbook,"unit":p.unit,"questionIDs":json.loads(p.question_ids_json)}
def audit(db,u,action,detail=""):
    db.add(AuditLog(school_id=u.school_id,user_id=u.id,action=action,detail=detail))

SCHOOL_TZ=timezone(timedelta(hours=8))

def due_deadline_utc(value):
    """Interpret stored assignment deadline as China-local time and return naive UTC."""
    s=(value or "").strip()
    if not s:
        return None
    try:
        if len(s)==10:
            local=datetime.fromisoformat(s).replace(hour=23,minute=59,second=59,tzinfo=SCHOOL_TZ)
        else:
            parsed=datetime.fromisoformat(s.replace("Z","+00:00"))
            local=parsed.replace(tzinfo=SCHOOL_TZ) if parsed.tzinfo is None else parsed
        return local.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return None

def assignment_status(due_date,sub=None,now=None):
    deadline=due_deadline_utc(due_date)
    now=now or datetime.utcnow()
    completed=bool(sub)
    late=bool(completed and deadline and sub.submitted_at>deadline)
    overdue=bool((not completed) and deadline and now>deadline)
    if completed:
        status="逾期完成" if late else "已完成"
        code="late_completed" if late else "completed"
    else:
        status="逾期未交" if overdue else "未完成"
        code="overdue" if overdue else "pending"
    return {
        "completed":completed,
        "status":status,
        "statusCode":code,
        "late":late,
        "overdue":overdue,
        "deadlinePassed":bool(deadline and now>deadline),
    }
def aj(db,a):
    p=db.scalar(select(Paper).where(Paper.id==a.paper_id,Paper.school_id==a.school_id))
    student_count=db.scalar(select(func.count()).select_from(AssignmentRecipient).where(AssignmentRecipient.assignment_id==a.id,AssignmentRecipient.school_id==a.school_id)) or 0
    completed=db.scalar(select(func.count(func.distinct(Submission.student_id))).join(AssignmentRecipient,(AssignmentRecipient.assignment_id==Submission.assignment_id)&(AssignmentRecipient.student_id==Submission.student_id)).where(Submission.assignment_id==a.id,Submission.school_id==a.school_id)) or 0
    pending=max(student_count-completed,0);meta=assignment_status(a.due_date)
    return {"id":a.id,"title":a.title,"classID":a.class_id,"paperID":a.paper_id,"dueDate":a.due_date,"paper":pj(p) if p else None,"submissionCount":completed,"studentCount":student_count,"completedCount":completed,"pendingCount":pending,"completionRate":round(completed/student_count*100) if student_count else 0,"deadlinePassed":meta["deadlinePassed"],"deadlineStatus":"已截止" if meta["deadlinePassed"] else "进行中"}

def protected_question_ids_for_student(db,u):
    if u.role!="student": return set()
    assignments=db.scalars(select(Assignment).join(AssignmentRecipient,AssignmentRecipient.assignment_id==Assignment.id).where(Assignment.school_id==u.school_id,AssignmentRecipient.student_id==u.id)).all()
    protected=set()
    for a in assignments:
        submitted=db.scalar(select(Submission.id).where(Submission.assignment_id==a.id,Submission.student_id==u.id,Submission.school_id==u.school_id).limit(1))
        if submitted: continue
        p=db.scalar(select(Paper).where(Paper.id==a.paper_id,Paper.school_id==u.school_id))
        if not p: continue
        try: protected.update(int(x) for x in json.loads(p.question_ids_json or "[]"))
        except Exception: pass
    return protected

def normalized_answer_stats(db,answers,school_id):
    know={}
    valid=0
    for a in answers:
        qid=a.get("question_id")
        selected=a.get("selected_index")
        q=db.scalar(select(Question).where(Question.id==qid,Question.school_id==school_id)) if qid is not None else None
        if not q or not isinstance(selected,int):
            continue
        ok=(selected==q.correct_index)
        hit,total=know.get(q.knowledge,(0,0))
        know[q.knowledge]=(hit+(1 if ok else 0),total+1)
        valid+=1
    return know,valid

def progress_for(db,sid,school_id):
    subs=db.scalars(select(Submission).where(Submission.school_id==school_id,Submission.student_id==sid).order_by(Submission.submitted_at.desc())).all()
    avg=round(sum(x.score for x in subs)/len(subs)) if subs else 0
    know={};total_answered=0
    for sub in subs:
        try: answers=json.loads(sub.answers_json or "[]")
        except Exception: answers=[]
        sub_know,valid=normalized_answer_stats(db,answers,school_id);total_answered+=valid
        for k,(hit,total) in sub_know.items():
            old_hit,old_total=know.get(k,(0,0));know[k]=(old_hit+hit,old_total+total)
    items=[{"knowledge":k,"accuracy":round(v[0]/v[1]*100) if v[1] else 0,"answered":v[1]} for k,v in know.items()]
    items.sort(key=lambda x:x["accuracy"])
    return {"avgScore":avg,"totalAnswered":total_answered,"submissions":len(subs),"knowledge":items}

def grade_answers(db,u,answers,allowed_question_ids=None,require_all=False):
    if not answers: raise HTTPException(400,"没有答题记录")
    if len(answers)>100: raise HTTPException(400,"单次提交题量过多")
    allowed=set(allowed_question_ids) if allowed_question_ids is not None else None
    seen=set();normalized=[];correct=0
    for a in answers:
        qid=a.question_id
        if qid in seen: raise HTTPException(400,"答题记录包含重复题目")
        seen.add(qid)
        if allowed is not None and qid not in allowed: raise HTTPException(400,"答题记录包含不属于本试卷的题目")
        q=db.scalar(select(Question).where(Question.id==qid,Question.school_id==u.school_id))
        if not q: raise HTTPException(400,"题目不存在或无权限")
        try: option_count=len(json.loads(q.options_json))
        except Exception: option_count=0
        if a.selected_index<0 or a.selected_index>=option_count: raise HTTPException(400,"答案选项无效")
        ok=(a.selected_index==q.correct_index)
        correct+=1 if ok else 0
        normalized.append({"question_id":qid,"selected_index":a.selected_index,"correct":ok})
    if require_all and allowed is not None and seen!=allowed:
        raise HTTPException(400,"请完成试卷全部题目后再提交")
    total=len(normalized);score=round(correct/total*100) if total else 0
    return normalized,correct,total,score

# ---------------- V7.3 lifecycle / assignment snapshots ----------------
def school_local_iso(value):
    """Serialize a UTC database datetime as a school-local, human-friendly timestamp."""
    if not value:return ""
    aware=value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return aware.astimezone(SCHOOL_TZ).strftime("%Y-%m-%d %H:%M")

def current_class_for(db,student_id,school_id):
    # V7.3 lifecycle history is the authoritative current-class signal. This
    # also protects upgraded V7.2.1 data from a stale ClassStudent link after
    # a graduation archive.
    open_hist=db.scalar(select(StudentClassHistory).where(StudentClassHistory.school_id==school_id,StudentClassHistory.student_id==student_id,StudentClassHistory.left_at.is_(None)).order_by(StudentClassHistory.joined_at.desc(),StudentClassHistory.id.desc()).limit(1))
    if open_hist:
        return db.get(SchoolClass,open_hist.class_id)
    latest=db.scalar(select(StudentClassHistory).where(StudentClassHistory.school_id==school_id,StudentClassHistory.student_id==student_id).order_by(StudentClassHistory.joined_at.desc(),StudentClassHistory.id.desc()).limit(1))
    if latest and latest.leave_reason=="graduate" and latest.left_at is not None:
        return None
    return db.scalar(select(SchoolClass).join(ClassStudent,ClassStudent.class_id==SchoolClass.id).where(ClassStudent.student_id==student_id,SchoolClass.school_id==school_id).limit(1))

def ensure_history_open(db,school_id,student_id,class_id,actor_id=None,source="system",joined_at=None):
    existing=db.scalar(select(StudentClassHistory).where(StudentClassHistory.school_id==school_id,StudentClassHistory.student_id==student_id,StudentClassHistory.class_id==class_id,StudentClassHistory.left_at.is_(None)).limit(1))
    if existing:return existing
    row=StudentClassHistory(school_id=school_id,student_id=student_id,class_id=class_id,joined_at=joined_at or datetime.utcnow(),actor_id=actor_id,source=source)
    db.add(row);db.flush();return row

def close_history(db,school_id,student_id,class_ids,reason,actor_id=None):
    now=datetime.utcnow()
    if not class_ids:return
    rows=db.scalars(select(StudentClassHistory).where(StudentClassHistory.school_id==school_id,StudentClassHistory.student_id==student_id,StudentClassHistory.class_id.in_(class_ids),StudentClassHistory.left_at.is_(None))).all()
    for row in rows:
        row.left_at=now;row.leave_reason=reason;row.actor_id=actor_id

def ensure_recipient(db,a,student_id,source="assignment",assigned_at=None):
    row=db.scalar(select(AssignmentRecipient).where(AssignmentRecipient.assignment_id==a.id,AssignmentRecipient.student_id==student_id).limit(1))
    if row:return row
    row=AssignmentRecipient(school_id=a.school_id,assignment_id=a.id,class_id=a.class_id,student_id=student_id,assigned_at=assigned_at or a.created_at or datetime.utcnow(),source=source)
    db.add(row);db.flush();return row

def replay_legacy_class_history(db):
    """Reconstruct V7.2.1 transfer/archive history from existing audit logs when possible."""
    students=db.scalars(select(User).where(User.role=="student")).all()
    for stu in students:
        if db.scalar(select(StudentClassHistory.id).where(StudentClassHistory.school_id==stu.school_id,StudentClassHistory.student_id==stu.id).limit(1)):
            continue
        logs=db.scalars(select(AuditLog).where(AuditLog.school_id==stu.school_id,AuditLog.action.in_(["student.transfer","student.archive"])).order_by(AuditLog.created_at,AuditLog.id)).all()
        open_rows={}
        for log in logs:
            detail=log.detail or ""
            try:
                if action:=log.action:
                    if action=="student.transfer":
                        left,move=detail.rsplit(":",1);sid=int(left.split(":",1)[0])
                        if sid!=stu.id:continue
                        old_text,new_text=move.split("->",1);old_ids=[int(x) for x in old_text.split(",") if x];new_id=int(new_text)
                        for cid in old_ids:
                            row=open_rows.pop(cid,None)
                            if row:
                                row.left_at=log.created_at;row.leave_reason="transfer";row.actor_id=log.user_id
                            else:
                                row=StudentClassHistory(school_id=stu.school_id,student_id=stu.id,class_id=cid,joined_at=stu.created_at or log.created_at,left_at=log.created_at,leave_reason="transfer",actor_id=log.user_id,source="legacy_audit_backfill");db.add(row)
                        row=StudentClassHistory(school_id=stu.school_id,student_id=stu.id,class_id=new_id,joined_at=log.created_at,actor_id=log.user_id,source="legacy_audit_backfill");db.add(row);db.flush();open_rows[new_id]=row
                    elif action=="student.archive":
                        parts=detail.split(":",2);sid=int(parts[0])
                        if sid!=stu.id:continue
                        class_ids=[]
                        if len(parts)>2 and "classes=" in parts[2]:class_ids=[int(x) for x in parts[2].split("classes=",1)[1].split(",") if x]
                        targets=class_ids or list(open_rows)
                        for cid in targets:
                            row=open_rows.pop(cid,None)
                            if row:
                                row.left_at=log.created_at;row.leave_reason="graduate";row.actor_id=log.user_id
                            else:
                                row=StudentClassHistory(school_id=stu.school_id,student_id=stu.id,class_id=cid,joined_at=stu.created_at or log.created_at,left_at=log.created_at,leave_reason="graduate",actor_id=log.user_id,source="legacy_audit_backfill");db.add(row)
                        for cid,row in list(open_rows.items()):
                            row.left_at=log.created_at;row.leave_reason="graduate";row.actor_id=log.user_id;open_rows.pop(cid,None)
            except Exception:
                continue
        db.flush()

def v730_backfill(db):
    """Idempotent additive backfill. Never mutates V7.2.1 business tables."""
    replay_legacy_class_history(db)
    # Current class links become open lifecycle periods.
    links=db.execute(select(ClassStudent.student_id,ClassStudent.class_id,SchoolClass.school_id,User.created_at).join(SchoolClass,SchoolClass.id==ClassStudent.class_id).join(User,User.id==ClassStudent.student_id)).all()
    for sid,cid,school_id,created_at in links:
        latest=db.scalar(select(StudentClassHistory).where(StudentClassHistory.school_id==school_id,StudentClassHistory.student_id==sid).order_by(StudentClassHistory.joined_at.desc(),StudentClassHistory.id.desc()).limit(1))
        # A legacy graduation audit is stronger evidence than a stale old
        # class_students row, so never reopen an archived lifecycle period.
        if latest and latest.leave_reason=="graduate" and latest.left_at is not None:
            continue
        ensure_history_open(db,school_id,sid,cid,source="v730_backfill",joined_at=created_at)
    # Submitted historical assignments are definite recipients.
    subs=db.scalars(select(Submission).where(Submission.assignment_id.is_not(None))).all()
    for sub in subs:
        a=db.get(Assignment,sub.assignment_id)
        if a and a.school_id==sub.school_id:ensure_recipient(db,a,sub.student_id,"submission_backfill",a.created_at)
    # Recover recipients from class lifecycle overlap. This also reconstructs V7.2.1
    # unsubmitted work for students whose transfer/archive events exist in audit_logs.
    assignments=db.scalars(select(Assignment)).all()
    for a in assignments:
        when=a.created_at or datetime.utcnow()
        histories=db.scalars(select(StudentClassHistory).where(StudentClassHistory.school_id==a.school_id,StudentClassHistory.class_id==a.class_id)).all()
        for h in histories:
            if h.joined_at<=when and (h.left_at is None or when<=h.left_at):ensure_recipient(db,a,h.student_id,"class_history_backfill",when)
        # Fallback for any current link not represented above.
        sids=db.scalars(select(ClassStudent.student_id).join(User,User.id==ClassStudent.student_id).where(ClassStudent.class_id==a.class_id,User.school_id==a.school_id,User.role=="student",User.active==True)).all()
        for sid in sids:ensure_recipient(db,a,sid,"current_member_backfill",when)
    db.commit()

def recipient_students(db,a):
    return db.scalars(select(User).join(AssignmentRecipient,AssignmentRecipient.student_id==User.id).where(AssignmentRecipient.assignment_id==a.id,AssignmentRecipient.school_id==a.school_id,User.school_id==a.school_id,User.role=="student").order_by(User.name,User.id)).all()

def class_history_rows(db,student_id,school_id):
    rows=db.scalars(select(StudentClassHistory).where(StudentClassHistory.student_id==student_id,StudentClassHistory.school_id==school_id).order_by(StudentClassHistory.joined_at.desc(),StudentClassHistory.id.desc())).all()
    out=[]
    reason_names={"transfer":"调班","graduate":"毕业归档","restore":"恢复入班","":"在读"}
    for x in rows:
        c=db.get(SchoolClass,x.class_id)
        out.append({"id":x.id,"classID":x.class_id,"className":c.name if c else f"班级#{x.class_id}","grade":c.grade if c else None,"joinedAt":school_local_iso(x.joined_at),"leftAt":school_local_iso(x.left_at) if x.left_at else None,"leaveReason":x.leave_reason,"leaveReasonName":reason_names.get(x.leave_reason,x.leave_reason or "在读"),"current":x.left_at is None})
    return out

def save_sub(db,u,aid,title,normalized,correct,total,score):
    answers=json.dumps(normalized,ensure_ascii=False)
    if aid is not None:
        old=db.scalar(select(Submission).where(Submission.assignment_id==aid,Submission.student_id==u.id,Submission.school_id==u.school_id))
        if old:
            old.title=title;old.score=score;old.correct=correct;old.total=total;old.answers_json=answers;old.submitted_at=datetime.utcnow();return old
    sub=Submission(school_id=u.school_id,assignment_id=aid,student_id=u.id,title=title,score=score,correct=correct,total=total,answers_json=answers);db.add(sub);db.flush();return sub

def audit_readable(db,row):
    action=row.action;detail=row.detail or ""
    names={"class.create":"新建班级","student.create":"创建学生","student.transfer":"学生调班","student.archive":"毕业归档","student.restore":"恢复学生","paper.create":"创建试卷","assignment.create":"布置作业","assignment.export":"导出成绩","class.export":"导出班级报表","student.export":"导出学生成绩单","question.create":"新增题目","user.create":"创建账号","user.reset_password":"重置密码","user.active":"账号状态变更","import.xlsx":"批量导入","points.rule.create":"新增积分规则","points.rule.update":"修改积分规则","points.record":"课堂积分记录","points.undo":"撤销积分","reward.create":"新增奖品","reward.update":"修改奖品","reward.redeem":"积分兑换","reward.fulfill":"奖品发放","reward.reject":"兑换拒绝退款","points.export":"导出积分奖励报表","points.weekly.export":"导出班级积分周报","parent.bind":"绑定家长","parent.unbind":"解除家长绑定"}
    try:
        if action=="student.transfer":
            sid_name,move=detail.rsplit(":",1);parts=sid_name.split(":",1);name=parts[1] if len(parts)>1 else f"学生#{parts[0]}";old,new=move.split("->",1)
            old_names=[(db.get(SchoolClass,int(x)).name if db.get(SchoolClass,int(x)) else f"班级#{x}") for x in old.split(",") if x]
            nc=db.get(SchoolClass,int(new));return f"将 {name} 从 {' / '.join(old_names) or '原班级'} 调到 {nc.name if nc else '班级#'+new}"
        if action=="student.archive":
            parts=detail.split(":",2);name=parts[1] if len(parts)>1 else "学生";return f"将 {name} 毕业归档并停用账号"
        if action=="student.restore":
            parts=detail.split(":",2);name=parts[1] if len(parts)>1 else "学生";cid=int(parts[2].split("=")[-1]);c=db.get(SchoolClass,cid);return f"恢复 {name} 并安排到 {c.name if c else '指定班级'}"
        if action=="class.create":
            parts=detail.split(":",1);return f"新建班级：{parts[1] if len(parts)>1 else detail}"
        if action=="assignment.create":
            parts=detail.split(":",2);return f"布置作业：{parts[1] if len(parts)>1 else detail}"
        if action=="assignment.export":
            parts=detail.split(":",1);return f"导出作业成绩：{parts[1] if len(parts)>1 else detail}"
        if action=="paper.create":
            parts=detail.split(":",1);return f"创建试卷：{parts[1] if len(parts)>1 else detail}"
        if action=="question.create":return f"新增题目 #{detail}"
        if action=="student.create":
            parts=detail.split(":",2);return f"创建学生：{parts[1] if len(parts)>1 else detail}"
        if action=="user.active":
            uid,status=detail.split(":",1);target=db.get(User,int(uid));return f"{('启用' if status=='enabled' else '停用')}账号：{target.name if target else uid}"
        if action=="user.reset_password":
            target=db.get(User,int(detail));return f"重置密码：{target.name if target else detail}"
        if action=="user.create":
            uid,_=detail.split(":",1);target=db.get(User,int(uid));return f"创建账号：{target.name if target else uid}"
        if action=="class.export":return f"导出班级成绩报表：{detail.split(':',1)[-1]}"
        if action=="student.export":return f"导出学生成绩单：{detail.split(':',1)[-1]}"
    except Exception:pass
    return detail or names.get(action,action)


# ---------------- V7.4 customized teaching module ----------------
TEACHING_LEVELS=("C","B","A")
TEACHING_STAGES=("lesson","midterm","final")
TEACHING_SUBJECTS=("语文","数学")

def _json_list(raw):
    try:
        v=json.loads(raw or "[]")
        return v if isinstance(v,list) else []
    except Exception:
        return []

def v740_seed_teaching(db):
    """Additive, idempotent course shell for the requested 2026 autumn Grade 5 program."""
    schools=db.scalars(select(School)).all()
    for school in schools:
        p=db.scalar(select(TeachingProgram).where(
            TeachingProgram.school_id==school.id,TeachingProgram.academic_year==2026,
            TeachingProgram.term=="秋季",TeachingProgram.grade==5
        ))
        if not p:
            p=TeachingProgram(school_id=school.id,title="2026年秋五年级上册语数定制教学",academic_year=2026,term="秋季",grade=5,semester="上册",chinese_textbook="人教版",math_textbook="人教版",pass_threshold=60,active=True)
            db.add(p);db.flush()
        blueprints={
            "语文":(8,"120分钟：10分钟导入与目标；35分钟阅读理解；20分钟语文要素训练；35分钟同步作文；10分钟C/B/A分层训练；10分钟总结复盘。"),
            "数学":(16,"120分钟：10分钟诊断；25分钟概念建构；30分钟例题精讲；35分钟C/B/A分层训练；10分钟错题订正；10分钟总结。")
        }
        for subject,(count,timeline) in blueprints.items():
            for no in range(1,count+1):
                row=db.scalar(select(TeachingLesson).where(TeachingLesson.program_id==p.id,TeachingLesson.subject==subject,TeachingLesson.lesson_no==no))
                legacy_ppt=["本课目标","核心知识/语文要素","例题/文本精读","方法提炼","分层挑战 C→B→A","当堂总结与复盘"]
                math_ppt=["本课目标","核心知识点","例题精讲","方法提炼","分层挑战 C→B→A","错题订正与总结"]
                if row:
                    # Stable-release migration: only rewrite the untouched generic V7.4.0 math template.
                    # Teacher-customized PPT content is never overwritten.
                    if subject=="数学" and _json_list(row.ppt_json)==legacy_ppt:
                        row.ppt_json=json.dumps(math_ppt,ensure_ascii=False)
                    continue
                ppt=legacy_ppt if subject=="语文" else math_ppt
                row=TeachingLesson(
                    school_id=school.id,program_id=p.id,subject=subject,lesson_no=no,
                    unit="待按学校实际教材配置",title=f"{subject}同步课时 {no}",core_target="请依据学校2026秋实际教材版本填写本课核心目标。",
                    duration_min=120,teacher_plan=timeline,
                    reading_plan=("请填写本课阅读理解教案：文本目标、问题链、方法训练、当堂检测。" if subject=="语文" else ""),
                    writing_plan=("请填写本课同步作文教案：审题、选材、结构、表达、当堂成文。" if subject=="语文" else ""),
                    examples_json="[]",ppt_json=json.dumps(ppt,ensure_ascii=False),
                    closure_training=("根据本课阅读错题知识点配置专属巩固训练。" if subject=="语文" else "根据本课错题知识点配置分层巩固训练。"),
                    essay_review=("配置当堂作文修改清单：内容、结构、语言、书写与二次修改。" if subject=="语文" else ""),
                    published=False
                )
                db.add(row)
    db.commit()

def teaching_program_for(db,school_id):
    return db.scalar(select(TeachingProgram).where(TeachingProgram.school_id==school_id,TeachingProgram.academic_year==2026,TeachingProgram.term=="秋季",TeachingProgram.grade==5).order_by(TeachingProgram.id.desc()).limit(1))

def require_teaching_grade(user,p):
    if user.role=="student" and user.grade!=p.grade:
        raise HTTPException(403,f"本教学方案仅面向{p.grade}年级学生")

def teaching_question_counts(db,p):
    out={}
    rows=db.execute(select(TeachingQuestion.stage,TeachingQuestion.subject,TeachingQuestion.level,func.count()).where(TeachingQuestion.program_id==p.id,TeachingQuestion.school_id==p.school_id,TeachingQuestion.active==True).group_by(TeachingQuestion.stage,TeachingQuestion.subject,TeachingQuestion.level)).all()
    for stage,subject,level,count in rows:
        out.setdefault(stage,{}).setdefault(subject,{})[level]=int(count or 0)
    return out

def teaching_program_json(db,p):
    lessons=db.scalars(select(TeachingLesson).where(TeachingLesson.program_id==p.id).order_by(TeachingLesson.subject,TeachingLesson.lesson_no)).all()
    return {"id":p.id,"title":p.title,"academicYear":p.academic_year,"term":p.term,"grade":p.grade,"semester":p.semester,
            "chineseTextbook":p.chinese_textbook,"mathTextbook":p.math_textbook,"passThreshold":p.pass_threshold,"active":bool(p.active),
            "lessonCounts":{"语文":sum(1 for x in lessons if x.subject=="语文"),"数学":sum(1 for x in lessons if x.subject=="数学")},
            "publishedCounts":{"语文":sum(1 for x in lessons if x.subject=="语文" and x.published),"数学":sum(1 for x in lessons if x.subject=="数学" and x.published)},
            "questionCounts":teaching_question_counts(db,p)}

def teaching_lesson_json(l,full=True):
    d={"id":l.id,"programID":l.program_id,"subject":l.subject,"lessonNo":l.lesson_no,"unit":l.unit,"title":l.title,"coreTarget":l.core_target,"durationMin":l.duration_min,"ppt":_json_list(l.ppt_json),"published":bool(l.published)}
    if full:
        d.update({"teacherPlan":l.teacher_plan,"readingPlan":l.reading_plan,"writingPlan":l.writing_plan,"examples":_json_list(l.examples_json),"closureTraining":l.closure_training,"essayReview":l.essay_review})
    return d

def teaching_question_json(q,public=False):
    d={"id":q.id,"lessonID":q.lesson_id,"stage":q.stage,"subject":q.subject,"level":q.level,"knowledge":q.knowledge,"stem":q.stem,"options":_json_list(q.options_json)}
    if not public:d.update({"correctIndex":q.correct_index,"explanation":q.explanation})
    return d

def teaching_questions_for_level(db,p,level,lesson=None,stage="lesson",subject=None):
    q=select(TeachingQuestion).where(TeachingQuestion.school_id==p.school_id,TeachingQuestion.program_id==p.id,TeachingQuestion.active==True,TeachingQuestion.level==level)
    if lesson is not None:q=q.where(TeachingQuestion.lesson_id==lesson.id,TeachingQuestion.stage=="lesson",TeachingQuestion.subject==lesson.subject)
    else:q=q.where(TeachingQuestion.lesson_id.is_(None),TeachingQuestion.stage==stage,TeachingQuestion.subject==subject)
    return db.scalars(q.order_by(TeachingQuestion.id)).all()

def first_available_level(db,p,lesson=None,stage="lesson",subject=None,after=None):
    levels=list(TEACHING_LEVELS)
    if after in levels:levels=levels[levels.index(after)+1:]
    for level in levels:
        if teaching_questions_for_level(db,p,level,lesson,stage,subject):return level
    return None

def teaching_grade_answers(db,u,questions,answers):
    if not questions:raise HTTPException(400,"当前层级尚未配置题目")
    allowed={q.id:q for q in questions};seen=set();normalized=[];correct=0
    if len(answers)!=len(allowed):raise HTTPException(400,"请完成当前层级全部题目后再提交")
    for a in answers:
        if a.question_id in seen or a.question_id not in allowed:raise HTTPException(400,"答题记录与当前层级不匹配")
        q=allowed[a.question_id];seen.add(a.question_id);opts=_json_list(q.options_json)
        if a.selected_index<0 or a.selected_index>=len(opts):raise HTTPException(400,"答案选项无效")
        ok=a.selected_index==q.correct_index;correct+=1 if ok else 0
        normalized.append({"question_id":q.id,"selected_index":a.selected_index,"correct":ok})
    total=len(normalized);score=round(correct/total*100) if total else 0
    return normalized,correct,total,score

def teaching_review_for_attempt(db,attempt,lesson):
    try:answers=json.loads(attempt.answers_json or "[]")
    except Exception:answers=[]
    out=[]
    for a in answers:
        if a.get("correct"):continue
        q=db.get(TeachingQuestion,a.get("question_id"))
        if q and q.school_id==attempt.school_id:
            out.append({"questionID":q.id,"knowledge":q.knowledge,"stem":q.stem,"explanation":q.explanation})
    return {"wrongQuestions":out,"closureTraining":lesson.closure_training if lesson and out else "","essayReview":lesson.essay_review if lesson and lesson.subject=="语文" else ""}

def teaching_session_json(db,session,p,lesson=None,include_questions=True):
    qs=teaching_questions_for_level(db,p,session.current_level,lesson,session.stage,session.subject) if session.status=="active" else []
    return {"sessionID":session.id,"stage":session.stage,"subject":session.subject,"lessonID":session.lesson_id,"level":session.current_level,"status":session.status,"passThreshold":p.pass_threshold,
            "questions":[teaching_question_json(x,True) for x in qs] if include_questions else []}

def latest_teaching_session(db,student_id,program_id,lesson_id=None,stage="lesson",subject=None):
    q=select(TeachingAdaptiveSession).where(TeachingAdaptiveSession.student_id==student_id,TeachingAdaptiveSession.program_id==program_id,TeachingAdaptiveSession.stage==stage)
    if lesson_id is not None:q=q.where(TeachingAdaptiveSession.lesson_id==lesson_id)
    else:q=q.where(TeachingAdaptiveSession.lesson_id.is_(None),TeachingAdaptiveSession.subject==subject)
    return db.scalar(q.order_by(TeachingAdaptiveSession.id.desc()).limit(1))


# ---------------- V7.5 classroom points & rewards helpers ----------------
POINT_CATEGORIES=("activity","discipline","reward","adjustment")
REDEMPTION_ACTIVE_STATUSES=("pending","fulfilled")

def v750_seed_point_rules(db):
    """Create a small editable starter rule set only when a school has no point rules."""
    defaults=[
        ("主动回答","activity",1,False,10),("高质量回答","activity",2,False,20),
        ("课堂任务完成","activity",2,False,30),("小组合作","activity",1,False,40),
        ("按时到课","discipline",1,False,50),("专注听讲","discipline",1,False,60),
        ("影响课堂","discipline",-1,True,70),("多次违纪","discipline",-2,True,80),
    ]
    for school in db.scalars(select(School)).all():
        exists=db.scalar(select(PointRule.id).where(PointRule.school_id==school.id).limit(1))
        if exists: continue
        for name,category,points,require_note,sort_order in defaults:
            db.add(PointRule(school_id=school.id,name=name,category=category,points=points,active=True,require_note=require_note,sort_order=sort_order))
    db.commit()

def point_balance(db,student_id,school_id):
    return int(db.scalar(select(func.coalesce(func.sum(PointLedger.points),0)).where(PointLedger.student_id==student_id,PointLedger.school_id==school_id)) or 0)

def point_summary(db,student_id,school_id):
    rows=db.execute(select(PointLedger.category,PointLedger.points,PointLedger.source).where(PointLedger.student_id==student_id,PointLedger.school_id==school_id)).all()
    raw=sum(int(points or 0) for _,points,_ in rows)
    earned=sum(int(points or 0) for _,points,source in rows if (points or 0)>0 and source in ("classroom","adjustment"))
    activity=sum(int(points or 0) for category,points,source in rows if category=="activity" and source in ("classroom","adjustment","reversal"))
    discipline=sum(int(points or 0) for category,points,source in rows if category=="discipline" and source in ("classroom","adjustment","reversal"))
    reward_flow=sum(int(points or 0) for _,points,source in rows if source in ("redemption","refund"))
    redeemed=max(0,-reward_flow)
    return {"balance":raw,"available":max(raw,0),"earned":earned,"activity":activity,"discipline":discipline,"redeemed":redeemed}

def point_ledger_json(db,row):
    stu=db.get(User,row.student_id);actor=db.get(User,row.actor_id) if row.actor_id else None;rule=db.get(PointRule,row.rule_id) if row.rule_id else None
    return {"id":row.id,"studentID":row.student_id,"studentName":stu.name if stu else "","classID":row.class_id,
            "actorName":actor.name if actor else "系统","ruleName":rule.name if rule else "","category":row.category,"points":row.points,
            "reason":row.reason,"note":row.note,"source":row.source,"relatedID":row.related_id,"reversed":bool(row.reversed),
            "createdAt":school_local_iso(row.created_at)}

def point_rule_json(row):
    return {"id":row.id,"name":row.name,"category":row.category,"points":row.points,"active":bool(row.active),"requireNote":bool(row.require_note),"sortOrder":row.sort_order}

def reward_json(db,row,student_id=None):
    used=0
    if student_id:
        used=int(db.scalar(select(func.count()).select_from(RewardRedemption).where(RewardRedemption.school_id==row.school_id,RewardRedemption.student_id==student_id,RewardRedemption.reward_id==row.id,RewardRedemption.status.in_(REDEMPTION_ACTIVE_STATUSES))) or 0)
    today=datetime.now(SCHOOL_TZ).date().isoformat();in_window=(not row.start_date or today>=row.start_date) and (not row.end_date or today<=row.end_date)
    available=bool(row.active and in_window and (row.unlimited_stock or row.stock>0) and (row.per_student_limit<=0 or used<row.per_student_limit))
    return {"id":row.id,"name":row.name,"description":row.description,"icon":row.icon or "🎁","costPoints":row.cost_points,
            "stock":row.stock,"unlimitedStock":bool(row.unlimited_stock),"perStudentLimit":row.per_student_limit,"usedCount":used,
            "startDate":row.start_date,"endDate":row.end_date,"active":bool(row.active),"available":available}

def redemption_json(db,row):
    stu=db.get(User,row.student_id);reward=db.get(RewardItem,row.reward_id);actor=db.get(User,row.handled_by) if row.handled_by else None
    return {"id":row.id,"studentID":row.student_id,"studentName":stu.name if stu else "","rewardID":row.reward_id,
            "rewardName":row.reward_name,"icon":reward.icon if reward else "🎁","costPoints":row.cost_points,"status":row.status,"note":row.note,
            "requestedAt":school_local_iso(row.requested_at),"handledBy":actor.name if actor else "","handledAt":school_local_iso(row.handled_at) if row.handled_at else None}

def period_cutoff_utc(days:int=7):
    days=max(1,min(int(days or 7),90))
    local_now=datetime.now(SCHOOL_TZ)
    cutoff=local_now-timedelta(days=days)
    return cutoff.astimezone(timezone.utc).replace(tzinfo=None),days

def student_period_points(db,student_id,school_id,days:int=7):
    cutoff,days=period_cutoff_utc(days)
    rows=db.scalars(select(PointLedger).where(
        PointLedger.school_id==school_id,PointLedger.student_id==student_id,
        PointLedger.created_at>=cutoff
    ).order_by(PointLedger.id.desc())).all()
    classroom=[x for x in rows if x.source in ("classroom","adjustment","reversal")]
    positive=sum(int(x.points or 0) for x in rows if (x.points or 0)>0 and x.source in ("classroom","adjustment"))
    net=sum(int(x.points or 0) for x in classroom)
    activity=sum(int(x.points or 0) for x in classroom if x.category=="activity")
    discipline=sum(int(x.points or 0) for x in classroom if x.category=="discipline")
    reason_map={}
    for x in classroom:
        key=x.reason or "积分记录"
        item=reason_map.setdefault(key,{"reason":key,"count":0,"points":0})
        item["count"]+=1;item["points"]+=int(x.points or 0)
    reasons=sorted(reason_map.values(),key=lambda z:(abs(z["points"]),z["count"]),reverse=True)[:5]
    red=db.scalars(select(RewardRedemption).where(
        RewardRedemption.school_id==school_id,RewardRedemption.student_id==student_id,
        RewardRedemption.requested_at>=cutoff
    ).order_by(RewardRedemption.id.desc())).all()
    active_red=[x for x in red if x.status!="rejected"]
    return {"days":days,"earned":positive,"net":net,"activity":activity,"discipline":discipline,
            "redemptionCount":len(active_red),"redeemedPoints":sum(x.cost_points for x in active_red),
            "topReasons":reasons}

def current_teacher_class(db,u,class_id):
    c=db.scalar(select(SchoolClass).where(SchoolClass.id==class_id,SchoolClass.school_id==u.school_id))
    if not c: raise HTTPException(404,"班级不存在")
    if u.role=="teacher" and c.teacher_id!=u.id: raise HTTPException(403,"无权管理该班级")
    return c

def can_manage_student_points(db,u,student_id,class_id=None):
    stu=db.scalar(select(User).where(User.id==student_id,User.school_id==u.school_id,User.role=="student"))
    if not stu: raise HTTPException(404,"学生不存在")
    if u.role=="admin": return stu
    need(u,"teacher")
    if class_id:
        c=current_teacher_class(db,u,class_id)
        linked=db.scalar(select(ClassStudent.id).where(ClassStudent.class_id==c.id,ClassStudent.student_id==student_id))
    else:
        linked=db.scalar(select(ClassStudent.id).join(SchoolClass,SchoolClass.id==ClassStudent.class_id).where(ClassStudent.student_id==student_id,SchoolClass.school_id==u.school_id,SchoolClass.teacher_id==u.id))
    if not linked: raise HTTPException(403,"该学生不在你的在读班级")
    return stu

# ---------------- App ----------------
app=FastAPI(title="小学题库 V7.6.2 运营周报稳定修正版",version="7.6.2")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=False,allow_methods=["*"],allow_headers=["*"])

@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
    # V7.3.0: keep the V7.2.0 production seeding behavior; never create public demo credentials automatically on PostgreSQL.
    # Existing production users are untouched. Set ENABLE_DEMO_SEED=1 only for an intentional demo.
    if raw_url.startswith("sqlite") or os.getenv("ENABLE_DEMO_SEED","0")=="1":
        with SessionLocal() as db:
            seed(db)
    with SessionLocal() as db:
        v730_backfill(db)
        v740_seed_teaching(db)
        v750_seed_point_rules(db)

@app.get("/health")
def health(db:Session=Depends(get_db)):
    db.scalar(select(func.count()).select_from(School))
    return {"status":"ok","database":"connected"}

@app.post("/login")
def login(b:LoginBody,db:Session=Depends(get_db)):
    u=db.scalar(select(User).where(User.username==b.username))
    now=datetime.utcnow()
    if u:
        if not u.active:
            raise HTTPException(401,"账号已停用，请联系管理员")
        school=db.get(School,u.school_id)
        if not school or not school.active:
            raise HTTPException(401,"学校账号不可用")
        sec=security_for(db,u)
        if sec.locked_until and sec.locked_until>now:
            raise HTTPException(429,"登录尝试过多，请15分钟后再试")
    if not u or not verify_password(b.password,u.password_hash):
        if u:
            sec.failed_login_count=(sec.failed_login_count or 0)+1
            if sec.failed_login_count>=5:
                sec.failed_login_count=0
                sec.locked_until=now+timedelta(minutes=15)
            db.commit()
        raise HTTPException(401,"账号或密码错误")
    sec=security_for(db,u)
    sec.failed_login_count=0
    sec.locked_until=None
    db.commit()
    return {
        "token":make_token(u,sec,b.remember),"role":u.role,"userID":u.id,
        "name":u.name,"grade":u.grade,
        "mustChangePassword":bool(sec.must_change_password)
    }

@app.get("/session")
def session_status(u:User=Depends(authenticated_user),db:Session=Depends(get_db)):
    sec=security_for(db,u)
    return {
        "valid":True,
        "userID":u.id,
        "name":u.name,
        "role":u.role,
        "grade":u.grade,
        "mustChangePassword":bool(sec.must_change_password)
    }

@app.post("/change-password")
def change_password(b:ChangePasswordBody,u:User=Depends(authenticated_user),db:Session=Depends(get_db)):
    if not verify_password(b.current_password,u.password_hash):
        raise HTTPException(400,"当前密码不正确")
    if not password_ok(b.new_password):
        raise HTTPException(400,"新密码至少8位，并同时包含字母和数字")
    if verify_password(b.new_password,u.password_hash):
        raise HTTPException(400,"新密码不能与当前密码相同")
    sec=security_for(db,u)
    u.password_hash=hash_password(b.new_password)
    sec.must_change_password=False
    sec.failed_login_count=0;sec.locked_until=None;sec.password_changed_at=datetime.utcnow()
    db.commit()
    return {"ok":True,"token":make_token(u,sec,b.remember)}

@app.get("/questions")
def questions(grade:int|None=None,subject:str|None=None,textbook:str|None=None,unit:str|None=None,u:User=Depends(current_user),db:Session=Depends(get_db)):
    s=select(Question).where(Question.school_id==u.school_id)
    if grade is not None:s=s.where(Question.grade==grade)
    if subject:s=s.where(Question.subject==subject)
    if textbook:s=s.where(Question.textbook==textbook)
    if unit:s=s.where(Question.unit==unit)
    rows=db.scalars(s.order_by(Question.id)).all()
    if u.role=="student":
        protected=protected_question_ids_for_student(db,u)
        rows=[x for x in rows if x.id not in protected]
    serializer=qj if u.role in ("admin","teacher") else qj_public
    return [serializer(x) for x in rows]

@app.post("/questions")
def addq(b:QuestionCreate,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin","teacher")
    if b.grade not in range(1,7): raise HTTPException(400,"年级必须为1-6")
    if len(b.options)<2 or len(b.options)>8: raise HTTPException(400,"选项数量必须为2-8个")
    if b.correct_index<0 or b.correct_index>=len(b.options): raise HTTPException(400,"正确选项无效")
    if not b.text.strip(): raise HTTPException(400,"题目不能为空")
    q=Question(school_id=u.school_id,grade=b.grade,subject=b.subject,textbook=b.textbook,semester=b.semester,unit=b.unit,knowledge=b.knowledge,text=b.text,options_json=json.dumps(b.options,ensure_ascii=False),correct_index=b.correct_index,explanation=b.explanation,creator_id=u.id)
    db.add(q);db.flush();audit(db,u,"question.create",str(q.id));db.commit();return qj(q)

@app.get("/admin/overview")
def overview(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");sid=u.school_id
    cnt=lambda model,*conds: db.scalar(select(func.count()).select_from(model).where(*conds)) or 0
    books=db.scalars(select(Question.textbook).where(Question.school_id==sid).distinct()).all()
    now=datetime.utcnow()
    archived=0
    students=db.scalars(select(User).where(User.school_id==sid,User.role=="student",User.active==False)).all()
    for s in students:
        last=db.scalar(select(StudentClassHistory).where(StudentClassHistory.school_id==sid,StudentClassHistory.student_id==s.id).order_by(StudentClassHistory.id.desc()).limit(1))
        if last and last.leave_reason=="graduate":archived+=1
    locked=db.scalar(select(func.count()).select_from(UserSecurity).join(User,User.id==UserSecurity.user_id).where(User.school_id==sid,UserSecurity.locked_until.is_not(None),UserSecurity.locked_until>now)) or 0
    return {"teachers":cnt(User,User.school_id==sid,User.role=="teacher"),"students":cnt(User,User.school_id==sid,User.role=="student"),"activeStudents":cnt(User,User.school_id==sid,User.role=="student",User.active==True),"archivedStudents":archived,"inactiveAccounts":cnt(User,User.school_id==sid,User.active==False),"lockedAccounts":locked,"parents":cnt(User,User.school_id==sid,User.role=="parent"),"classes":cnt(SchoolClass,SchoolClass.school_id==sid),"questions":cnt(Question,Question.school_id==sid),"papers":cnt(Paper,Paper.school_id==sid),"assignments":cnt(Assignment,Assignment.school_id==sid),"submissions":cnt(Submission,Submission.school_id==sid),"assignmentRecipients":cnt(AssignmentRecipient,AssignmentRecipient.school_id==sid),"classHistoryRecords":cnt(StudentClassHistory,StudentClassHistory.school_id==sid),"textbooks":list(books)}

@app.get("/admin/users")
def admin_users(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin")
    rows=db.scalars(select(User).where(User.school_id==u.school_id).order_by(User.id.desc())).all();out=[]
    for x in rows:
        sec=db.get(UserSecurity,x.id);d=uj(x);c=current_class_for(db,x.id,u.school_id) if x.role=="student" else None
        last=db.scalar(select(StudentClassHistory).where(StudentClassHistory.school_id==u.school_id,StudentClassHistory.student_id==x.id).order_by(StudentClassHistory.id.desc()).limit(1)) if x.role=="student" else None
        archived=bool(x.role=="student" and not x.active and not c and last and last.leave_reason=="graduate")
        d.update({"mustChangePassword":bool(sec.must_change_password) if sec else True,"passwordStatus":"待修改" if (not sec or sec.must_change_password) else "已设置","lockedUntil":school_local_iso(sec.locked_until) if sec and sec.locked_until and sec.locked_until>datetime.utcnow() else None,"passwordChangedAt":school_local_iso(sec.password_changed_at) if sec and sec.password_changed_at else None,"currentClassID":c.id if c else None,"currentClassName":c.name if c else None,"archived":archived,"lifecycleStatus":"毕业归档" if archived else ("在读" if x.role=="student" and c else ("未分班" if x.role=="student" and x.active else ("已停用" if not x.active else "正常")))})
        out.append(d)
    return out

@app.post("/admin/users")
def admin_user(b:UserCreate,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin")
    if b.role not in ("teacher","parent"):raise HTTPException(400,"仅可创建教师或家长")
    if not b.name.strip() or not b.username.strip():raise HTTPException(400,"姓名和账号不能为空")
    if not password_ok(b.password):raise HTTPException(400,"初始密码至少8位，并同时包含字母和数字")
    if db.scalar(select(User).where(User.username==b.username.strip())):raise HTTPException(400,"账号已存在")
    x=User(school_id=u.school_id,username=b.username.strip(),password_hash=hash_password(b.password),name=b.name.strip(),role=b.role,active=True)
    db.add(x);db.flush()
    db.add(UserSecurity(user_id=x.id,must_change_password=True,failed_login_count=0))
    audit(db,u,"user.create",f"{x.id}:{x.role}")
    db.commit();db.refresh(x);return uj(x)

@app.post("/admin/users/{uid}/reset-password")
def admin_reset_password(uid:int,b:ResetPasswordBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin")
    if not password_ok(b.new_password):
        raise HTTPException(400,"临时密码至少8位，并同时包含字母和数字")
    target=db.scalar(select(User).where(User.id==uid,User.school_id==u.school_id))
    if not target:
        raise HTTPException(404,"用户不存在")
    sec=security_for(db,target)
    target.password_hash=hash_password(b.new_password)
    sec.must_change_password=True
    sec.failed_login_count=0;sec.locked_until=None;sec.password_changed_at=datetime.utcnow()
    audit(db,u,"user.reset_password",str(target.id))
    db.commit()
    return {"ok":True,"mustChangePassword":True,"passwordStatus":"待修改"}

@app.post("/admin/users/{uid}/active")
def admin_set_user_active(uid:int,b:ActiveBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin")
    target=db.scalar(select(User).where(User.id==uid,User.school_id==u.school_id))
    if not target:raise HTTPException(404,"用户不存在")
    if target.id==u.id and not b.active:raise HTTPException(400,"不能停用当前登录的管理员账号")
    target.active=bool(b.active)
    sec=security_for(db,target)
    sec.failed_login_count=0;sec.locked_until=None
    if not target.active:
        sec.password_changed_at=datetime.utcnow()  # invalidate all previously issued login tokens
    audit(db,u,"user.active",f"{target.id}:{'enabled' if target.active else 'disabled'}")
    db.commit()
    return {"ok":True,"id":target.id,"active":bool(target.active)}

@app.get("/admin/classes")
def admin_classes(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");rows=db.scalars(select(SchoolClass).where(SchoolClass.school_id==u.school_id).order_by(SchoolClass.grade,SchoolClass.name)).all();out=[]
    for c in rows:
        t=db.get(User,c.teacher_id);out.append({"id":c.id,"name":c.name,"grade":c.grade,"teacherName":t.name if t else "","studentCount":db.scalar(select(func.count()).select_from(ClassStudent).where(ClassStudent.class_id==c.id)) or 0})
    return out

@app.get("/admin/students/{sid}/history")
def admin_student_history(sid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");s=db.scalar(select(User).where(User.id==sid,User.school_id==u.school_id,User.role=="student"))
    if not s:raise HTTPException(404,"学生不存在")
    return class_history_rows(db,sid,u.school_id)

@app.post("/admin/students/{sid}/restore")
def admin_restore_student(sid:int,b:RestoreStudentBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");s=db.scalar(select(User).where(User.id==sid,User.school_id==u.school_id,User.role=="student"));c=db.scalar(select(SchoolClass).where(SchoolClass.id==b.class_id,SchoolClass.school_id==u.school_id))
    if not s:raise HTTPException(404,"学生不存在")
    if not c:raise HTTPException(404,"目标班级不存在")
    for link in db.scalars(select(ClassStudent).join(SchoolClass,SchoolClass.id==ClassStudent.class_id).where(ClassStudent.student_id==sid,SchoolClass.school_id==u.school_id)).all():db.delete(link)
    db.add(ClassStudent(class_id=c.id,student_id=s.id));s.grade=c.grade;s.active=True
    sec=security_for(db,s);sec.failed_login_count=0;sec.locked_until=None;sec.password_changed_at=datetime.utcnow()
    ensure_history_open(db,u.school_id,s.id,c.id,u.id,"restore")
    audit(db,u,"student.restore",f"{s.id}:{s.name}:class={c.id}");db.commit()
    return {"ok":True,"studentID":s.id,"active":True,"classID":c.id,"className":c.name,"grade":c.grade}

@app.get("/admin/audit-logs")
def admin_audit_logs(limit:int=150,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");limit=max(1,min(limit,300));rows=db.scalars(select(AuditLog).where(AuditLog.school_id==u.school_id).order_by(AuditLog.id.desc()).limit(limit)).all();out=[]
    for x in rows:
        actor=db.get(User,x.user_id) if x.user_id else None
        out.append({"id":x.id,"action":x.action,"actionName":{"student.transfer":"学生调班","student.archive":"毕业归档","student.restore":"恢复学生","assignment.create":"布置作业","assignment.export":"导出成绩","class.export":"导出班级报表","student.export":"导出学生成绩单","user.active":"账号状态变更","user.reset_password":"重置密码","import.xlsx":"批量导入","class.create":"新建班级","student.create":"创建学生","paper.create":"创建试卷","question.create":"新增题目","user.create":"创建账号","teaching.program.update":"教学方案设置","teaching.lesson.update":"更新定制课时","teaching.question.create":"新增分层题","teaching.question.delete":"删除分层题","teaching.essay.feedback":"作文批改","parent.bind":"绑定家长","parent.unbind":"解除家长绑定"}.get(x.action,x.action),"summary":audit_readable(db,x),"actorName":actor.name if actor else "系统","actorRole":actor.role if actor else "system","createdAt":school_local_iso(x.created_at)})
    return out

@app.get("/admin/import-jobs")
def jobs(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");rows=db.scalars(select(ImportJob).where(ImportJob.school_id==u.school_id).order_by(ImportJob.id.desc()).limit(20)).all()
    return [{"id":x.id,"filename":x.filename,"status":x.status,"summary":x.summary,"createdAt":school_local_iso(x.created_at)} for x in rows]

def import_cell(v,default=""):
    if v is None:return default
    if isinstance(v,float) and v.is_integer():return str(int(v))
    return str(v).strip()

def import_active(v):
    s=import_cell(v,"启用").lower()
    if s in ("启用","是","yes","y","true","1","正常"):return True
    if s in ("停用","否","no","n","false","0","禁用"):return False
    raise ValueError("启用状态请填写 启用/停用")

@app.get("/admin/import-template")
def import_template(u:User=Depends(current_user)):
    need(u,"admin")
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    wb=Workbook();ws=wb.active;ws.title="题库导入"
    sheets={
        "题库导入":(["年级","科目","教材版本","学期","单元","知识点","题目","选项A","选项B","选项C","选项D","正确答案(1-4)","解析"],[3,"数学","人教版","上册","第一单元","时分秒","1分钟等于多少秒？","30","60","90","100",2,"1分钟=60秒。"]),
        "教师导入":(["姓名","登录账号","初始密码","启用状态"],["王老师","teacher1001","School2026","启用"]),
        "学生导入":(["姓名","登录账号","初始密码","年级","班级","家长账号(可空)","启用状态"],["小明","student1001","Study2026",3,"三年级一班","","启用"]),
    }
    for idx,(name,(headers,sample)) in enumerate(sheets.items()):
        sh=ws if idx==0 else wb.create_sheet(name)
        sh.append(headers);sh.append(sample);sh.freeze_panes="A2"
        for c in sh[1]:
            c.font=Font(bold=True,color="FFFFFF");c.fill=PatternFill("solid",fgColor="5362E8");c.alignment=Alignment(horizontal="center",vertical="center")
        for col in sh.columns:
            letter=col[0].column_letter
            width=min(max(max(len(import_cell(c.value)) for c in col)+2,12),34)
            sh.column_dimensions[letter].width=width
    note=wb.create_sheet("填写说明",0)
    note.append(["小学题库 V7.4.0 Excel 批量导入说明"]);note.append(["1. 可同时填写题库导入、教师导入、学生导入三个工作表；空工作表会自动跳过。"]);note.append(["2. 教师/学生初始密码至少8位，并同时包含字母和数字；首次登录必须修改。"]);note.append(["3. 学生导入的“班级”必须已存在，并且年级要与班级一致；家长账号可留空。"]);note.append(["4. 已存在的登录账号不会覆盖，会计入跳过行；有效数据仍会继续导入。"]);note.column_dimensions["A"].width=95
    for row in note.iter_rows():
        for c in row:c.alignment=Alignment(wrap_text=True,vertical="top")
    bio=io.BytesIO();wb.save(bio)
    return Response(bio.getvalue(),media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":"attachment; filename=primary-school-import-template-v740.xlsx","Cache-Control":"no-store"})

@app.post("/admin/import-xlsx")
async def import_xlsx(file:UploadFile=File(...),u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin")
    if not (file.filename or "").lower().endswith(".xlsx"):raise HTTPException(400,"请上传 XLSX")
    from openpyxl import load_workbook
    try:wb=load_workbook(io.BytesIO(await file.read()),data_only=True)
    except Exception:raise HTTPException(400,"Excel 无法读取")
    recognized={"题库导入","教师导入","学生导入"}
    if not recognized.intersection(wb.sheetnames):raise HTTPException(400,"未找到题库导入、教师导入或学生导入工作表")
    qcount=scount=tcount=skipped=0;errors=[]
    existing_usernames=set(db.scalars(select(User.username)).all())
    classes=db.scalars(select(SchoolClass).where(SchoolClass.school_id==u.school_id)).all()
    class_map={}
    for c in classes:class_map.setdefault((c.name.strip(),c.grade),[]).append(c)
    parents={x.username:x for x in db.scalars(select(User).where(User.school_id==u.school_id,User.role=="parent")).all()}

    if "题库导入" in wb.sheetnames:
        for rn,row in enumerate(wb["题库导入"].iter_rows(min_row=2,values_only=True),start=2):
            if not row or not any(v is not None and import_cell(v) for v in row):continue
            try:
                grade=int(row[0]);sub=import_cell(row[1]);text=import_cell(row[6]);opts=[import_cell(row[i]) for i in range(7,11)];correct=int(row[11])-1
                if grade not in range(1,7):raise ValueError("年级必须为1-6")
                if not sub or not text or any(not x for x in opts):raise ValueError("科目、题目和4个选项不能为空")
                if correct not in range(4):raise ValueError("正确答案必须为1-4")
                db.add(Question(school_id=u.school_id,grade=grade,subject=sub,textbook=import_cell(row[2],"人教版"),semester=import_cell(row[3],"上册"),unit=import_cell(row[4],"综合"),knowledge=import_cell(row[5],"综合"),text=text,options_json=json.dumps(opts,ensure_ascii=False),correct_index=correct,explanation=import_cell(row[12] if len(row)>12 else None),creator_id=u.id));qcount+=1
            except Exception as e:
                skipped+=1
                if len(errors)<12:errors.append(f"题库导入第{rn}行：{str(e) or '格式错误'}")

    if "教师导入" in wb.sheetnames:
        for rn,row in enumerate(wb["教师导入"].iter_rows(min_row=2,values_only=True),start=2):
            if not row or not any(v is not None and import_cell(v) for v in row):continue
            try:
                name=import_cell(row[0]);username=import_cell(row[1]);password=import_cell(row[2]);active=import_active(row[3] if len(row)>3 else None)
                if not name or not username:raise ValueError("姓名和登录账号不能为空")
                if username in existing_usernames:raise ValueError("登录账号已存在")
                if not password_ok(password):raise ValueError("初始密码至少8位，并同时包含字母和数字")
                x=User(school_id=u.school_id,username=username,password_hash=hash_password(password),name=name,role="teacher",active=active);db.add(x);db.flush();db.add(UserSecurity(user_id=x.id,must_change_password=True,failed_login_count=0));existing_usernames.add(username);tcount+=1
            except Exception as e:
                skipped+=1
                if len(errors)<12:errors.append(f"教师导入第{rn}行：{str(e) or '格式错误'}")

    if "学生导入" in wb.sheetnames:
        for rn,row in enumerate(wb["学生导入"].iter_rows(min_row=2,values_only=True),start=2):
            if not row or not any(v is not None and import_cell(v) for v in row):continue
            try:
                name=import_cell(row[0]);username=import_cell(row[1]);password=import_cell(row[2]);grade=int(row[3]);class_name=import_cell(row[4]);parent_username=import_cell(row[5] if len(row)>5 else None);active=import_active(row[6] if len(row)>6 else None)
                if not name or not username or not class_name:raise ValueError("姓名、登录账号和班级不能为空")
                if grade not in range(1,7):raise ValueError("年级必须为1-6")
                if username in existing_usernames:raise ValueError("登录账号已存在")
                if not password_ok(password):raise ValueError("初始密码至少8位，并同时包含字母和数字")
                matches=class_map.get((class_name,grade),[])
                if not matches:raise ValueError("找不到同年级班级")
                if len(matches)>1:raise ValueError("同年级存在重名班级，请先整理班级名称")
                parent=None
                if parent_username:
                    parent=parents.get(parent_username)
                    if not parent:raise ValueError("家长账号不存在")
                x=User(school_id=u.school_id,username=username,password_hash=hash_password(password),name=name,role="student",grade=grade,active=active);db.add(x);db.flush();db.add(UserSecurity(user_id=x.id,must_change_password=True,failed_login_count=0));db.add(ClassStudent(class_id=matches[0].id,student_id=x.id));ensure_history_open(db,u.school_id,x.id,matches[0].id,u.id,"import",x.created_at)
                if parent:db.add(ParentStudent(parent_id=parent.id,student_id=x.id))
                existing_usernames.add(username);scount+=1
            except Exception as e:
                skipped+=1
                if len(errors)<12:errors.append(f"学生导入第{rn}行：{str(e) or '格式错误'}")

    status="成功" if skipped==0 else ("部分成功" if qcount+tcount+scount else "失败")
    summary=f"题库 {qcount} 道，教师 {tcount} 名，学生 {scount} 名，跳过 {skipped} 行"
    if errors:summary+=f"；首个问题：{errors[0]}"
    db.add(ImportJob(school_id=u.school_id,filename=file.filename or "upload.xlsx",status=status,summary=summary,user_id=u.id));audit(db,u,"import.xlsx",summary);db.commit()
    return {"summary":summary,"status":status,"errors":errors,"questions":qcount,"teachers":tcount,"students":scount,"skipped":skipped}

@app.get("/teacher/classes")
def tclasses(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher");rows=db.scalars(select(SchoolClass).where(SchoolClass.school_id==u.school_id,SchoolClass.teacher_id==u.id).order_by(SchoolClass.id.desc())).all()
    return [{"id":c.id,"name":c.name,"grade":c.grade,"teacherID":c.teacher_id,"studentCount":db.scalar(select(func.count()).select_from(ClassStudent).where(ClassStudent.class_id==c.id)) or 0} for c in rows]

@app.post("/teacher/classes")
def addclass(b:ClassCreate,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher");c=SchoolClass(school_id=u.school_id,name=b.name,grade=b.grade,teacher_id=u.id);db.add(c);db.flush();audit(db,u,"class.create",f"{c.id}:{c.name}");db.commit();db.refresh(c);return {"id":c.id,"name":c.name,"grade":c.grade,"teacherID":c.teacher_id,"studentCount":0}

@app.get("/teacher/classes/{cid}/students")
def cstudents(cid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher")
    c=db.scalar(select(SchoolClass).where(SchoolClass.id==cid,SchoolClass.school_id==u.school_id,SchoolClass.teacher_id==u.id))
    if not c:raise HTTPException(404,"班级不存在")
    rows=db.scalars(select(User).join(ClassStudent,ClassStudent.student_id==User.id).where(ClassStudent.class_id==cid)).all()
    out=[]
    for s in rows:
        p=db.scalar(select(User).join(ParentStudent,ParentStudent.parent_id==User.id).where(ParentStudent.student_id==s.id).limit(1))
        d=uj(s);d["parentName"]=p.name if p else None;d["parentID"]=p.id if p else None;d["parentUsername"]=p.username if p else None;out.append(d)
    return out

@app.post("/teacher/students")
def addstudent(b:StudentCreate,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher");c=db.scalar(select(SchoolClass).where(SchoolClass.id==b.class_id,SchoolClass.school_id==u.school_id,SchoolClass.teacher_id==u.id))
    if not c:raise HTTPException(404,"班级不存在或无权限")
    if db.scalar(select(User).where(User.username==b.username)):raise HTTPException(400,"学生账号已存在")
    if not password_ok(b.password):raise HTTPException(400,"初始密码至少8位，并同时包含字母和数字")
    s=User(school_id=u.school_id,username=b.username,password_hash=hash_password(b.password),name=b.name,role="student",grade=c.grade);db.add(s);db.flush();db.add(UserSecurity(user_id=s.id,must_change_password=True,failed_login_count=0));db.add(ClassStudent(class_id=c.id,student_id=s.id));ensure_history_open(db,u.school_id,s.id,c.id,u.id,"teacher_create",s.created_at)
    if b.parent_username:
        p=db.scalar(select(User).where(User.school_id==u.school_id,User.username==b.parent_username,User.role=="parent"))
        if p:db.add(ParentStudent(parent_id=p.id,student_id=s.id))
    audit(db,u,"student.create",f"{s.id}:{s.name}:class={c.id}");db.commit();return uj(s)

@app.get("/teacher/parents")
def teacher_parents(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher")
    rows=db.scalars(select(User).where(User.school_id==u.school_id,User.role=="parent",User.active==True).order_by(User.name,User.username)).all()
    return [{"id":x.id,"name":x.name,"username":x.username} for x in rows]

@app.post("/teacher/students/{sid}/parent")
def bind_student_parent(sid:int,b:ParentBindBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher")
    student=db.scalar(select(User).where(User.id==sid,User.school_id==u.school_id,User.role=="student"))
    if not student:raise HTTPException(404,"学生不存在")
    owned=db.scalar(select(ClassStudent.id).join(SchoolClass,ClassStudent.class_id==SchoolClass.id).where(ClassStudent.student_id==sid,SchoolClass.school_id==u.school_id,SchoolClass.teacher_id==u.id).limit(1))
    if not owned:raise HTTPException(403,"该学生不在你管理的班级中")
    old_links=db.scalars(select(ParentStudent).where(ParentStudent.student_id==sid)).all()
    old_parent_names=[]
    for link in old_links:
        old_parent=db.get(User,link.parent_id)
        if old_parent:old_parent_names.append(old_parent.name)
        db.delete(link)
    if b.parent_id is None:
        audit(db,u,"parent.unbind",f"{student.id}:{student.name}:{','.join(old_parent_names) or '无'}")
        db.commit()
        return {"ok":True,"studentID":student.id,"parent":None}
    parent=db.scalar(select(User).where(User.id==b.parent_id,User.school_id==u.school_id,User.role=="parent",User.active==True))
    if not parent:raise HTTPException(404,"家长账号不存在或已停用")
    db.add(ParentStudent(parent_id=parent.id,student_id=student.id))
    audit(db,u,"parent.bind",f"{student.id}:{student.name}:{parent.id}:{parent.name}")
    db.commit()
    return {"ok":True,"studentID":student.id,"parent":{"id":parent.id,"name":parent.name,"username":parent.username}}

@app.post("/teacher/students/{sid}/transfer")
def transfer_student(sid:int,b:TransferStudentBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher");student=db.scalar(select(User).where(User.id==sid,User.school_id==u.school_id,User.role=="student"));target=db.scalar(select(SchoolClass).where(SchoolClass.id==b.target_class_id,SchoolClass.school_id==u.school_id,SchoolClass.teacher_id==u.id))
    if not student:raise HTTPException(404,"学生不存在")
    if not target:raise HTTPException(404,"目标班级不存在或无权限")
    owned_links=db.scalars(select(ClassStudent).join(SchoolClass,ClassStudent.class_id==SchoolClass.id).where(ClassStudent.student_id==sid,SchoolClass.school_id==u.school_id,SchoolClass.teacher_id==u.id)).all()
    if not owned_links:raise HTTPException(403,"该学生不在你管理的班级中")
    old_class_ids=[x.class_id for x in owned_links]
    if len(old_class_ids)==1 and old_class_ids[0]==target.id:raise HTTPException(400,"学生已在目标班级")
    close_history(db,u.school_id,sid,old_class_ids,"transfer",u.id)
    for link in owned_links:db.delete(link)
    if not db.scalar(select(ClassStudent.id).where(ClassStudent.class_id==target.id,ClassStudent.student_id==sid).limit(1)):db.add(ClassStudent(class_id=target.id,student_id=sid))
    ensure_history_open(db,u.school_id,sid,target.id,u.id,"transfer");student.grade=target.grade
    audit(db,u,"student.transfer",f"{student.id}:{student.name}:{','.join(map(str,old_class_ids))}->{target.id}");db.commit()
    return {"ok":True,"studentID":student.id,"classID":target.id,"className":target.name,"grade":target.grade}

@app.post("/teacher/students/{sid}/archive")
def archive_student(sid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher");student=db.scalar(select(User).where(User.id==sid,User.school_id==u.school_id,User.role=="student"))
    if not student:raise HTTPException(404,"学生不存在")
    links=db.scalars(select(ClassStudent).join(SchoolClass,ClassStudent.class_id==SchoolClass.id).where(ClassStudent.student_id==sid,SchoolClass.school_id==u.school_id,SchoolClass.teacher_id==u.id)).all()
    if not links:raise HTTPException(403,"该学生不在你管理的班级中")
    class_ids=[x.class_id for x in links];close_history(db,u.school_id,sid,class_ids,"graduate",u.id)
    for link in links:db.delete(link)
    student.active=False;sec=security_for(db,student);sec.failed_login_count=0;sec.locked_until=None;sec.password_changed_at=datetime.utcnow()
    audit(db,u,"student.archive",f"{student.id}:{student.name}:classes={','.join(map(str,class_ids))}");db.commit();return {"ok":True,"studentID":student.id,"active":False,"archived":True}

@app.get("/teacher/students/{sid}/history")
def teacher_student_history(sid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher");s=db.scalar(select(User).where(User.id==sid,User.school_id==u.school_id,User.role=="student"))
    if not s:raise HTTPException(404,"学生不存在")
    allowed=db.scalar(select(StudentClassHistory.id).join(SchoolClass,SchoolClass.id==StudentClassHistory.class_id).where(StudentClassHistory.student_id==sid,StudentClassHistory.school_id==u.school_id,SchoolClass.teacher_id==u.id).limit(1))
    if not allowed:raise HTTPException(403,"无权查看该学生班级历史")
    return class_history_rows(db,sid,u.school_id)

@app.get("/teacher/audit-logs")
def teacher_audit_logs(limit:int=120,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher");limit=max(1,min(limit,250));rows=db.scalars(select(AuditLog).where(AuditLog.school_id==u.school_id,AuditLog.user_id==u.id).order_by(AuditLog.id.desc()).limit(limit)).all()
    names={"class.create":"新建班级","student.create":"创建学生","student.transfer":"学生调班","student.archive":"毕业归档","paper.create":"创建试卷","assignment.create":"布置作业","assignment.export":"导出成绩","class.export":"导出班级报表","student.export":"导出学生成绩单","question.create":"新增题目","teaching.program.update":"教学方案设置","teaching.lesson.update":"更新定制课时","teaching.question.create":"新增分层题","teaching.question.delete":"删除分层题","teaching.essay.feedback":"作文批改"}
    return [{"id":x.id,"action":x.action,"actionName":names.get(x.action,x.action),"detail":x.detail,"summary":audit_readable(db,x),"createdAt":school_local_iso(x.created_at)} for x in rows]

@app.post("/teacher/papers")
def addpaper(b:PaperCreate,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher")
    if not b.question_ids or len(b.question_ids)>100: raise HTTPException(400,"试卷题量必须为1-100题")
    if len(set(b.question_ids))!=len(b.question_ids): raise HTTPException(400,"试卷包含重复题目")
    valid=db.scalars(select(Question.id).where(Question.school_id==u.school_id,Question.id.in_(b.question_ids))).all()
    if set(valid)!=set(b.question_ids): raise HTTPException(400,"试卷包含不存在或无权限的题目")
    p=Paper(school_id=u.school_id,title=b.title,grade=b.grade,subject=b.subject,textbook=b.textbook,unit=b.unit,question_ids_json=json.dumps(b.question_ids),teacher_id=u.id);db.add(p);db.flush();audit(db,u,"paper.create",f"{p.id}:{p.title}");db.commit();db.refresh(p);return pj(p)

@app.post("/teacher/assignments")
def addassignment(b:AssignmentCreate,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher");c=db.scalar(select(SchoolClass).where(SchoolClass.id==b.class_id,SchoolClass.school_id==u.school_id,SchoolClass.teacher_id==u.id));p=db.scalar(select(Paper).where(Paper.id==b.paper_id,Paper.school_id==u.school_id,Paper.teacher_id==u.id))
    if not c:raise HTTPException(404,"班级不存在或无权限")
    if not p:raise HTTPException(404,"试卷不存在或无权限")
    a=Assignment(school_id=u.school_id,title=b.title,class_id=c.id,paper_id=p.id,due_date=b.due_date);db.add(a);db.flush()
    sids=db.scalars(select(ClassStudent.student_id).join(User,User.id==ClassStudent.student_id).where(ClassStudent.class_id==c.id,User.school_id==u.school_id,User.role=="student",User.active==True)).all()
    for sid in sids:ensure_recipient(db,a,sid,"assignment")
    audit(db,u,"assignment.create",f"{a.id}:{a.title}:class={c.id}:due={a.due_date}:recipients={len(sids)}");db.commit();db.refresh(a);return aj(db,a)

@app.get("/teacher/assignments")
def tassign(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher");rows=db.scalars(select(Assignment).join(SchoolClass,Assignment.class_id==SchoolClass.id).where(Assignment.school_id==u.school_id,SchoolClass.teacher_id==u.id).order_by(Assignment.id.desc())).all();return [aj(db,a) for a in rows]

@app.get("/teacher/assignments/{aid}/submissions")
def tsubs(aid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher");a=db.scalar(select(Assignment).join(SchoolClass,Assignment.class_id==SchoolClass.id).where(Assignment.id==aid,Assignment.school_id==u.school_id,SchoolClass.teacher_id==u.id))
    if not a:raise HTTPException(404,"作业不存在或无权限")
    students=recipient_students(db,a);sids=[x.id for x in students]
    subs=db.scalars(select(Submission).where(Submission.assignment_id==aid,Submission.school_id==u.school_id,Submission.student_id.in_(sids)).order_by(Submission.submitted_at.desc())).all() if sids else []
    latest={}
    for sub in subs:latest.setdefault(sub.student_id,sub)
    out=[]
    for stu in students:
        sub=latest.get(stu.id);meta=assignment_status(a.due_date,sub);out.append({"id":sub.id if sub else None,"studentID":stu.id,"studentName":stu.name,"username":stu.username,**meta,"score":sub.score if sub else None,"correct":sub.correct if sub else None,"total":sub.total if sub else None,"submittedAt":school_local_iso(sub.submitted_at) if sub else None})
    rank={"overdue":0,"pending":1,"late_completed":2,"completed":3};out.sort(key=lambda x:(rank.get(x["statusCode"],9),-(x["score"] if x["score"] is not None else -1),x["studentName"]));return out

@app.get("/teacher/assignments/{aid}/export.xlsx")
def export_assignment_report(aid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher");a=db.scalar(select(Assignment).join(SchoolClass,Assignment.class_id==SchoolClass.id).where(Assignment.id==aid,Assignment.school_id==u.school_id,SchoolClass.teacher_id==u.id))
    if not a:raise HTTPException(404,"作业不存在或无权限")
    c=db.get(SchoolClass,a.class_id);students=recipient_students(db,a);sids=[x.id for x in students]
    subs=db.scalars(select(Submission).where(Submission.assignment_id==aid,Submission.school_id==u.school_id,Submission.student_id.in_(sids)).order_by(Submission.submitted_at.desc())).all() if sids else [];latest={}
    for sub in subs:latest.setdefault(sub.student_id,sub)
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    wb=Workbook();ws=wb.active;ws.title="作业成绩";ws.append(["作业名称",a.title]);ws.append(["布置班级",c.name if c else ""]);ws.append(["截止时间",a.due_date]);ws.append(["接收学生",len(students)]);ws.append([]);ws.append(["学生","账号","状态","分数","答对","总题数","提交时间"]);header_row=6
    for cell in ws[header_row]:cell.font=Font(bold=True,color="FFFFFF");cell.fill=PatternFill("solid",fgColor="5362E8");cell.alignment=Alignment(horizontal="center")
    for stu in students:
        sub=latest.get(stu.id);meta=assignment_status(a.due_date,sub);submitted=school_local_iso(sub.submitted_at).replace("T"," ")[:19] if sub else "";ws.append([stu.name,stu.username,meta["status"],sub.score if sub else "",sub.correct if sub else "",sub.total if sub else "",submitted])
    for i,w in enumerate([18,20,14,10,10,10,22],1):ws.column_dimensions[chr(64+i)].width=w
    ws.freeze_panes="A7";bio=io.BytesIO();wb.save(bio);audit(db,u,"assignment.export",f"{a.id}:{a.title}");db.commit();return Response(bio.getvalue(),media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":f"attachment; filename=assignment-{a.id}-report-v730.xlsx","Cache-Control":"no-store"})

@app.get("/teacher/classes/{cid}/report.xlsx")
def export_class_report(cid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher");c=db.scalar(select(SchoolClass).where(SchoolClass.id==cid,SchoolClass.school_id==u.school_id,SchoolClass.teacher_id==u.id))
    if not c:raise HTTPException(404,"班级不存在或无权限")
    students=db.scalars(select(User).join(ClassStudent,ClassStudent.student_id==User.id).where(ClassStudent.class_id==cid,User.school_id==u.school_id,User.role=="student").order_by(User.name)).all()
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill
    wb=Workbook();ws=wb.active;ws.title="班级成绩汇总";ws.append(["班级",c.name]);ws.append(["年级",c.grade]);ws.append([]);ws.append(["学生","账号","当前状态","正式作业数","已完成","平均分","历史提交数"])
    for cell in ws[4]:cell.font=Font(bold=True,color="FFFFFF");cell.fill=PatternFill("solid",fgColor="5362E8")
    for stu in students:
        recipients=db.scalars(select(AssignmentRecipient).where(AssignmentRecipient.school_id==u.school_id,AssignmentRecipient.student_id==stu.id)).all();aids=[x.assignment_id for x in recipients];formal=db.scalars(select(Submission).where(Submission.school_id==u.school_id,Submission.student_id==stu.id,Submission.assignment_id.in_(aids))).all() if aids else [];latest={}
        for sub in sorted(formal,key=lambda x:x.submitted_at,reverse=True):latest.setdefault(sub.assignment_id,sub)
        avg=round(sum(x.score for x in latest.values())/len(latest)) if latest else 0;all_subs=db.scalar(select(func.count()).select_from(Submission).where(Submission.school_id==u.school_id,Submission.student_id==stu.id)) or 0
        ws.append([stu.name,stu.username,"在读" if stu.active else "已停用",len(aids),len(latest),avg,all_subs])
    for col,w in zip("ABCDEFG",[18,20,12,14,12,12,14]):ws.column_dimensions[col].width=w
    bio=io.BytesIO();wb.save(bio);audit(db,u,"class.export",f"{c.id}:{c.name}");db.commit();return Response(bio.getvalue(),media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":f"attachment; filename=class-{c.id}-report-v730.xlsx","Cache-Control":"no-store"})

@app.get("/teacher/students/{sid}/report.xlsx")
def export_student_report(sid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher");s=db.scalar(select(User).where(User.id==sid,User.school_id==u.school_id,User.role=="student"))
    if not s:raise HTTPException(404,"学生不存在")
    allowed=db.scalar(select(StudentClassHistory.id).join(SchoolClass,SchoolClass.id==StudentClassHistory.class_id).where(StudentClassHistory.student_id==sid,StudentClassHistory.school_id==u.school_id,SchoolClass.teacher_id==u.id).limit(1))
    if not allowed:raise HTTPException(403,"无权导出该学生成绩")
    recipients=db.scalars(select(AssignmentRecipient).where(AssignmentRecipient.school_id==u.school_id,AssignmentRecipient.student_id==sid).order_by(AssignmentRecipient.assignment_id)).all();aids=[x.assignment_id for x in recipients]
    subs=db.scalars(select(Submission).where(Submission.school_id==u.school_id,Submission.student_id==sid).order_by(Submission.submitted_at.desc())).all();latest={}
    for sub in subs:
        if sub.assignment_id is not None:latest.setdefault(sub.assignment_id,sub)
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill
    wb=Workbook();ws=wb.active;ws.title="学生成绩单";ws.append(["学生",s.name]);ws.append(["账号",s.username]);ws.append(["当前年级",s.grade or ""]);ws.append([]);ws.append(["作业","布置班级","截止日期","状态","分数","答对","总题数","提交时间"])
    for cell in ws[5]:cell.font=Font(bold=True,color="FFFFFF");cell.fill=PatternFill("solid",fgColor="5362E8")
    for r in recipients:
        a=db.get(Assignment,r.assignment_id);c=db.get(SchoolClass,r.class_id);sub=latest.get(r.assignment_id)
        if not a:continue
        meta=assignment_status(a.due_date,sub);ws.append([a.title,c.name if c else "",a.due_date,meta["status"],sub.score if sub else "",sub.correct if sub else "",sub.total if sub else "",school_local_iso(sub.submitted_at).replace("T"," ")[:19] if sub else ""])
    for col,w in zip("ABCDEFGH",[20,18,14,14,10,10,10,22]):ws.column_dimensions[col].width=w
    kh=wb.create_sheet("班级历程");kh.append(["班级","年级","进入时间","离开时间","状态/原因"])
    for x in class_history_rows(db,sid,u.school_id):kh.append([x["className"],x["grade"] or "",x["joinedAt"].replace("T"," ")[:19],(x["leftAt"] or "").replace("T"," ")[:19],"当前在读" if x["current"] else x["leaveReasonName"]])
    bio=io.BytesIO();wb.save(bio);audit(db,u,"student.export",f"{s.id}:{s.name}");db.commit();return Response(bio.getvalue(),media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":f"attachment; filename=student-{s.id}-report-v730.xlsx","Cache-Control":"no-store"})

def teacher_analytics_data(db,u):
    classes=db.scalars(select(SchoolClass).where(SchoolClass.school_id==u.school_id,SchoolClass.teacher_id==u.id).order_by(SchoolClass.id)).all();cids=[c.id for c in classes]
    assignments=db.scalars(select(Assignment).where(Assignment.school_id==u.school_id,Assignment.class_id.in_(cids)).order_by(Assignment.id)).all() if cids else [];by_class={c.id:[] for c in classes}
    for a in assignments:by_class.setdefault(a.class_id,[]).append(a)
    aids=[a.id for a in assignments];subs=db.scalars(select(Submission).where(Submission.school_id==u.school_id,Submission.assignment_id.in_(aids))).all() if aids else [];latest={}
    for sub in sorted(subs,key=lambda x:x.submitted_at,reverse=True):latest.setdefault((sub.assignment_id,sub.student_id),sub)
    know={};correct_sum=total_sum=0
    for sub in latest.values():
        correct_sum+=sub.correct or 0;total_sum+=sub.total or 0
        try:answers=json.loads(sub.answers_json or "[]")
        except Exception:answers=[]
        part,_=normalized_answer_stats(db,answers,u.school_id)
        for k,(hit,total) in part.items():old_hit,old_total=know.get(k,(0,0));know[k]=(old_hit+hit,old_total+total)
    knowledge=[{"knowledge":k,"accuracy":round(v[0]/v[1]*100) if v[1] else 0,"answered":v[1]} for k,v in know.items()];knowledge.sort(key=lambda x:(x["accuracy"],-x["answered"],x["knowledge"]))
    class_stats=[];student_rollup={};all_student_ids=set()
    for c in classes:
        class_a=by_class.get(c.id,[]);recipient_pairs=[]
        for a in class_a:
            sids=db.scalars(select(AssignmentRecipient.student_id).where(AssignmentRecipient.assignment_id==a.id,AssignmentRecipient.school_id==u.school_id)).all()
            for sid in sids:
                recipient_pairs.append((a,sid));all_student_ids.add(sid)
                stu=db.get(User,sid);rec=student_rollup.setdefault(sid,{"studentID":sid,"studentName":stu.name if stu else str(sid),"scores":[],"assigned":0,"completed":0,"classes":set()})
                rec["assigned"]+=1;rec["classes"].add(c.name);sub=latest.get((a.id,sid))
                if sub:rec["completed"]+=1;rec["scores"].append(sub.score)
        expected=len(recipient_pairs);class_subs=[latest[(a.id,sid)] for a,sid in recipient_pairs if (a.id,sid) in latest];completed=len(class_subs);avg_score=round(sum(x.score for x in class_subs)/completed) if completed else 0;c_correct=sum(x.correct or 0 for x in class_subs);c_total=sum(x.total or 0 for x in class_subs);current_students=db.scalar(select(func.count()).select_from(ClassStudent).where(ClassStudent.class_id==c.id)) or 0
        class_stats.append({"classID":c.id,"className":c.name,"grade":c.grade,"students":current_students,"assignments":len(class_a),"expectedSubmissions":expected,"completedSubmissions":completed,"pendingSubmissions":max(expected-completed,0),"completionRate":round(completed/expected*100) if expected else 0,"avgScore":avg_score,"accuracy":round(c_correct/c_total*100) if c_total else 0})
    weak=[]
    for rec in student_rollup.values():
        assigned=rec["assigned"];completed=rec["completed"];avg=round(sum(rec["scores"])/len(rec["scores"])) if rec["scores"] else 0;completion=round(completed/assigned*100) if assigned else 0
        if assigned and (completed<assigned or avg<70):weak.append({"studentID":rec["studentID"],"studentName":rec["studentName"],"className":" / ".join(sorted(rec["classes"])),"avgScore":avg,"assigned":assigned,"completed":completed,"pending":max(assigned-completed,0),"completionRate":completion})
    weak.sort(key=lambda x:(x["completionRate"],x["avgScore"],x["studentName"]));formal=list(latest.values());avg_score=round(sum(x.score for x in formal)/len(formal)) if formal else 0;avg_accuracy=round(correct_sum/total_sum*100) if total_sum else 0;expected_total=sum(x["expectedSubmissions"] for x in class_stats);completed_total=sum(x["completedSubmissions"] for x in class_stats)
    return {"classes":len(classes),"students":len(all_student_ids),"assignments":len(assignments),"submissions":completed_total,"expectedSubmissions":expected_total,"pendingSubmissions":max(expected_total-completed_total,0),"completionRate":round(completed_total/expected_total*100) if expected_total else 0,"avgScore":avg_score,"avgAccuracy":avg_accuracy,"weakKnowledge":knowledge[:5],"knowledge":knowledge,"classStats":class_stats,"weakStudents":weak[:8]}

@app.get("/teacher/dashboard")
def tdashboard(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher")
    return teacher_analytics_data(db,u)

@app.get("/teacher/analytics")
def tanalytics(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher")
    d=teacher_analytics_data(db,u)
    return {"totalSubmissions":d["submissions"],"expectedSubmissions":d["expectedSubmissions"],"pendingSubmissions":d["pendingSubmissions"],"completionRate":d["completionRate"],"avgScore":d["avgScore"],"avgAccuracy":d["avgAccuracy"],"knowledge":d["knowledge"],"classStats":d["classStats"],"weakStudents":d["weakStudents"]}

@app.get("/student/assignments")
def sassign(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"student");rows=db.scalars(select(Assignment).join(AssignmentRecipient,AssignmentRecipient.assignment_id==Assignment.id).where(Assignment.school_id==u.school_id,AssignmentRecipient.school_id==u.school_id,AssignmentRecipient.student_id==u.id).order_by(Assignment.id.desc())).all();out=[]
    for a in rows:
        d=aj(db,a);sub=db.scalar(select(Submission).where(Submission.assignment_id==a.id,Submission.student_id==u.id,Submission.school_id==u.school_id).order_by(Submission.submitted_at.desc()));meta=assignment_status(a.due_date,sub);r=db.scalar(select(AssignmentRecipient).where(AssignmentRecipient.assignment_id==a.id,AssignmentRecipient.student_id==u.id));c=db.get(SchoolClass,r.class_id) if r else None;d.update({**meta,"score":sub.score if sub else None,"submittedAt":school_local_iso(sub.submitted_at) if sub else None,"assignedClassName":c.name if c else ""});out.append(d)
    return out

@app.get("/papers/{pid}/questions")
def paperq(pid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    p=db.scalar(select(Paper).where(Paper.id==pid,Paper.school_id==u.school_id))
    if not p:raise HTTPException(404,"试卷不存在")
    if u.role=="teacher" and p.teacher_id!=u.id:raise HTTPException(403,"无权查看此试卷")
    if u.role=="student":
        allowed=db.scalar(select(AssignmentRecipient.id).join(Assignment,Assignment.id==AssignmentRecipient.assignment_id).where(Assignment.paper_id==pid,Assignment.school_id==u.school_id,AssignmentRecipient.student_id==u.id).limit(1))
        if not allowed:raise HTTPException(403,"无权查看此试卷")
    elif u.role not in ("admin","teacher"):raise HTTPException(403,"无权查看此试卷")
    serializer=qj_public if u.role=="student" else qj
    return [serializer(q) for qid in json.loads(p.question_ids_json) if (q:=db.get(Question,qid)) and q.school_id==u.school_id]

@app.post("/student/assignments/{aid}/submit")
def ssubmit(aid:int,b:SubmitBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"student");a=db.scalar(select(Assignment).where(Assignment.id==aid,Assignment.school_id==u.school_id).with_for_update())
    if not a:raise HTTPException(403,"不能提交")
    recipient=db.scalar(select(AssignmentRecipient.id).where(AssignmentRecipient.assignment_id==aid,AssignmentRecipient.student_id==u.id,AssignmentRecipient.school_id==u.school_id))
    if not recipient:raise HTTPException(403,"你不是此作业的接收学生")
    old=db.scalar(select(Submission.id).where(Submission.assignment_id==aid,Submission.student_id==u.id,Submission.school_id==u.school_id).limit(1))
    if old:raise HTTPException(409,"作业已提交，不能重复提交")
    p=db.scalar(select(Paper).where(Paper.id==a.paper_id,Paper.school_id==u.school_id))
    if not p:raise HTTPException(400,"作业试卷不存在")
    expected=json.loads(p.question_ids_json or "[]");normalized,correct,total,score=grade_answers(db,u,b.answers,expected,require_all=True);sub=save_sub(db,u,aid,a.title,normalized,correct,total,score);meta=assignment_status(a.due_date,sub);db.commit();return {"id":sub.id,"score":sub.score,"correct":sub.correct,"total":sub.total,"status":meta["status"],"late":meta["late"]}

@app.post("/student/practice-submit")
def psubmit(b:SubmitBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"student")
    protected=protected_question_ids_for_student(db,u)
    if any(a.question_id in protected for a in b.answers):
        raise HTTPException(403,"未完成正式作业中的题目不能通过自主练习判题")
    normalized,correct,total,score=grade_answers(db,u,b.answers)
    sub=save_sub(db,u,None,(b.title or "自主练习")[:160],normalized,correct,total,score);db.commit()
    return {"id":sub.id,"score":sub.score,"correct":sub.correct,"total":sub.total}

@app.get("/student/progress")
def sprogress(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"student");return progress_for(db,u.id,u.school_id)

@app.get("/leaderboard")
def leaderboard(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","student")
    cids=db.scalars(select(SchoolClass.id).join(ClassStudent,ClassStudent.class_id==SchoolClass.id).where(ClassStudent.student_id==u.id,SchoolClass.school_id==u.school_id)).all() if u.role=="student" else db.scalars(select(SchoolClass.id).where(SchoolClass.school_id==u.school_id,SchoolClass.teacher_id==u.id)).all()
    out=[]
    for cid in cids:
        c=db.scalar(select(SchoolClass).where(SchoolClass.id==cid,SchoolClass.school_id==u.school_id))
        if not c: continue
        for sid in db.scalars(select(ClassStudent.student_id).join(User,User.id==ClassStudent.student_id).where(ClassStudent.class_id==cid,User.school_id==u.school_id)).all():
            stu=db.scalar(select(User).where(User.id==sid,User.school_id==u.school_id));rows=db.scalars(select(Submission).where(Submission.school_id==u.school_id,Submission.student_id==sid)).all()
            if rows and stu:out.append({"studentName":stu.name,"className":c.name if c else "","avgScore":round(sum(x.score for x in rows)/len(rows)),"submissions":len(rows)})
    out.sort(key=lambda x:(-x["avgScore"],-x["submissions"]));return out

@app.get("/parent/children")
def children(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"parent");rows=db.scalars(select(User).join(ParentStudent,ParentStudent.student_id==User.id).where(ParentStudent.parent_id==u.id,User.school_id==u.school_id)).all();out=[]
    for s in rows:
        p=progress_for(db,s.id,u.school_id);c=current_class_for(db,s.id,u.school_id);assignments=db.scalars(select(Assignment).join(AssignmentRecipient,AssignmentRecipient.assignment_id==Assignment.id).where(Assignment.school_id==u.school_id,AssignmentRecipient.student_id==s.id,AssignmentRecipient.school_id==u.school_id)).all();pending=overdue=0
        for a in assignments:
            sub=db.scalar(select(Submission).where(Submission.assignment_id==a.id,Submission.student_id==s.id,Submission.school_id==u.school_id).order_by(Submission.submitted_at.desc()));meta=assignment_status(a.due_date,sub);pending+=0 if meta["completed"] else 1;overdue+=1 if meta["overdue"] else 0
        out.append({"id":s.id,"name":s.name,"grade":s.grade,"className":c.name if c else "","avgScore":p["avgScore"],"pendingAssignments":pending,"overdueAssignments":overdue,"active":bool(s.active),"archived":bool((not s.active) and not c)})
    return out

@app.get("/parent/children/{sid}/assignments")
def child_assignments(sid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"parent")
    if not db.scalar(select(ParentStudent).where(ParentStudent.parent_id==u.id,ParentStudent.student_id==sid)):raise HTTPException(403,"未绑定")
    student=db.scalar(select(User).where(User.id==sid,User.school_id==u.school_id,User.role=="student"))
    if not student:raise HTTPException(404,"学生不存在")
    recs=db.scalars(select(AssignmentRecipient).where(AssignmentRecipient.school_id==u.school_id,AssignmentRecipient.student_id==sid).order_by(AssignmentRecipient.assignment_id.desc())).all();out=[]
    for r in recs:
        a=db.scalar(select(Assignment).where(Assignment.id==r.assignment_id,Assignment.school_id==u.school_id));
        if not a:continue
        p=db.scalar(select(Paper).where(Paper.id==a.paper_id,Paper.school_id==u.school_id));sub=db.scalar(select(Submission).where(Submission.assignment_id==a.id,Submission.student_id==sid,Submission.school_id==u.school_id).order_by(Submission.submitted_at.desc()));meta=assignment_status(a.due_date,sub);c=db.get(SchoolClass,r.class_id)
        out.append({"id":a.id,"title":a.title,"dueDate":a.due_date,"subject":p.subject if p else "",**meta,"score":sub.score if sub else None,"submittedAt":school_local_iso(sub.submitted_at) if sub else None,"assignedClassName":c.name if c else "","assignedAt":school_local_iso(r.assigned_at)})
    return out

@app.get("/parent/children/{sid}/progress")
def child_progress(sid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"parent")
    if not db.scalar(select(ParentStudent).where(ParentStudent.parent_id==u.id,ParentStudent.student_id==sid)):raise HTTPException(403,"未绑定")
    s=db.scalar(select(User).where(User.id==sid,User.school_id==u.school_id,User.role=="student"))
    if not s:raise HTTPException(404,"学生不存在")
    c=current_class_for(db,sid,u.school_id);p=progress_for(db,sid,u.school_id);p.update({"studentName":s.name,"grade":s.grade,"className":c.name if c else "","active":bool(s.active),"classHistory":class_history_rows(db,sid,u.school_id)});return p

# ---------------- V7.4 customized teaching APIs ----------------
@app.get("/teaching/program")
def get_teaching_program(u:User=Depends(current_user),db:Session=Depends(get_db)):
    p=teaching_program_for(db,u.school_id)
    if not p:raise HTTPException(404,"五年级教学方案尚未初始化")
    return teaching_program_json(db,p)

@app.put("/teaching/program")
def update_teaching_program(b:TeachingProgramUpdate,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin","teacher");p=teaching_program_for(db,u.school_id)
    if not p:raise HTTPException(404,"教学方案不存在")
    if b.title is not None and b.title.strip():p.title=b.title.strip()
    if b.chinese_textbook is not None and b.chinese_textbook.strip():p.chinese_textbook=b.chinese_textbook.strip()
    if b.math_textbook is not None and b.math_textbook.strip():p.math_textbook=b.math_textbook.strip()
    if b.pass_threshold is not None:
        if b.pass_threshold<1 or b.pass_threshold>100:raise HTTPException(400,"分层通过线必须为1-100")
        p.pass_threshold=b.pass_threshold
    p.updated_at=datetime.utcnow();audit(db,u,"teaching.program.update",p.title);db.commit();return teaching_program_json(db,p)

@app.get("/teaching/lessons")
def get_teaching_lessons(subject:str|None=None,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin","teacher");p=teaching_program_for(db,u.school_id)
    if not p:return []
    q=select(TeachingLesson).where(TeachingLesson.program_id==p.id,TeachingLesson.school_id==u.school_id)
    if subject:q=q.where(TeachingLesson.subject==subject)
    return [teaching_lesson_json(x,True) for x in db.scalars(q.order_by(TeachingLesson.subject,TeachingLesson.lesson_no)).all()]

@app.get("/teaching/lessons/{lid}")
def get_teaching_lesson(lid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin","teacher");l=db.scalar(select(TeachingLesson).where(TeachingLesson.id==lid,TeachingLesson.school_id==u.school_id))
    if not l:raise HTTPException(404,"课时不存在")
    return teaching_lesson_json(l,True)

@app.put("/teaching/lessons/{lid}")
def update_teaching_lesson(lid:int,b:TeachingLessonUpdate,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin","teacher");l=db.scalar(select(TeachingLesson).where(TeachingLesson.id==lid,TeachingLesson.school_id==u.school_id))
    if not l:raise HTTPException(404,"课时不存在")
    for attr,val in (("unit",b.unit),("title",b.title),("core_target",b.core_target),("teacher_plan",b.teacher_plan),("reading_plan",b.reading_plan),("writing_plan",b.writing_plan),("closure_training",b.closure_training),("essay_review",b.essay_review)):
        if val is not None:setattr(l,attr,val.strip())
    if b.examples is not None:l.examples_json=json.dumps([str(x).strip() for x in b.examples if str(x).strip()],ensure_ascii=False)
    if b.ppt is not None:l.ppt_json=json.dumps([str(x).strip() for x in b.ppt if str(x).strip()],ensure_ascii=False)
    if b.published is not None:l.published=bool(b.published)
    l.updated_at=datetime.utcnow();audit(db,u,"teaching.lesson.update",f"{l.subject}第{l.lesson_no}课时：{l.title}");db.commit();return teaching_lesson_json(l,True)

@app.get("/teaching/questions")
def get_teaching_questions(lesson_id:int|None=None,stage:str="lesson",subject:str|None=None,level:str|None=None,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin","teacher");p=teaching_program_for(db,u.school_id)
    if not p:return []
    q=select(TeachingQuestion).where(TeachingQuestion.school_id==u.school_id,TeachingQuestion.program_id==p.id,TeachingQuestion.active==True)
    if lesson_id is not None:q=q.where(TeachingQuestion.lesson_id==lesson_id)
    else:q=q.where(TeachingQuestion.lesson_id.is_(None),TeachingQuestion.stage==stage)
    if subject:q=q.where(TeachingQuestion.subject==subject)
    if level:q=q.where(TeachingQuestion.level==level)
    return [teaching_question_json(x,False) for x in db.scalars(q.order_by(TeachingQuestion.level.desc(),TeachingQuestion.id)).all()]

@app.post("/teaching/questions")
def add_teaching_question(b:TeachingQuestionCreate,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin","teacher");p=teaching_program_for(db,u.school_id)
    if not p:raise HTTPException(404,"教学方案不存在")
    if b.level not in TEACHING_LEVELS:raise HTTPException(400,"层级必须为A、B或C")
    if b.stage not in TEACHING_STAGES:raise HTTPException(400,"测评类型无效")
    if b.subject not in TEACHING_SUBJECTS:raise HTTPException(400,"科目仅支持语文或数学")
    if len(b.options)!=4 or any(not str(x).strip() for x in b.options):raise HTTPException(400,"分层客观题必须填写4个有效选项")
    if b.correct_index not in range(4):raise HTTPException(400,"正确选项必须为1-4")
    lesson=None
    if b.stage=="lesson":
        if not b.lesson_id:raise HTTPException(400,"课时练习必须选择课时")
        lesson=db.scalar(select(TeachingLesson).where(TeachingLesson.id==b.lesson_id,TeachingLesson.program_id==p.id,TeachingLesson.school_id==u.school_id))
        if not lesson:raise HTTPException(404,"课时不存在")
        if lesson.subject!=b.subject:raise HTTPException(400,"题目科目与课时不一致")
    elif b.lesson_id is not None:raise HTTPException(400,"期中/期末题不绑定具体课时")
    q=TeachingQuestion(school_id=u.school_id,program_id=p.id,lesson_id=lesson.id if lesson else None,stage=b.stage,subject=b.subject,level=b.level,knowledge=b.knowledge.strip(),stem=b.stem.strip(),options_json=json.dumps([str(x).strip() for x in b.options],ensure_ascii=False),correct_index=b.correct_index,explanation=b.explanation.strip(),active=True)
    if not q.stem:raise HTTPException(400,"题目不能为空")
    db.add(q);db.flush();audit(db,u,"teaching.question.create",f"{b.subject} {b.stage} {b.level}层 #{q.id}");db.commit();return teaching_question_json(q,False)

@app.delete("/teaching/questions/{qid}")
def delete_teaching_question(qid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin","teacher");q=db.scalar(select(TeachingQuestion).where(TeachingQuestion.id==qid,TeachingQuestion.school_id==u.school_id))
    if not q:raise HTTPException(404,"题目不存在")
    q.active=False;audit(db,u,"teaching.question.delete",f"#{q.id}");db.commit();return {"ok":True}

@app.get("/teaching/lessons/{lid}/progress")
def teaching_lesson_progress(lid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin","teacher");l=db.scalar(select(TeachingLesson).where(TeachingLesson.id==lid,TeachingLesson.school_id==u.school_id));p=teaching_program_for(db,u.school_id)
    if not l or not p:raise HTTPException(404,"课时不存在")
    students=db.scalars(select(User).where(User.school_id==u.school_id,User.role=="student",User.grade==p.grade).order_by(User.name)).all();out=[]
    for stu in students:
        ses=latest_teaching_session(db,stu.id,p.id,l.id,"lesson",l.subject)
        out.append({"studentID":stu.id,"studentName":stu.name,"active":bool(stu.active),"status":ses.status if ses else "not_started","level":(ses.final_level or ses.current_level) if ses else None,"score":ses.final_score if ses else None})
    return out

@app.get("/teaching/lessons/{lid}/essays")
def teaching_lesson_essays(lid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin","teacher");l=db.scalar(select(TeachingLesson).where(TeachingLesson.id==lid,TeachingLesson.school_id==u.school_id,TeachingLesson.subject=="语文"))
    if not l:raise HTTPException(404,"语文课时不存在")
    rows=db.scalars(select(TeachingEssay).where(TeachingEssay.lesson_id==lid,TeachingEssay.school_id==u.school_id).order_by(TeachingEssay.updated_at.desc())).all();out=[]
    for e in rows:
        stu=db.get(User,e.student_id);out.append({"id":e.id,"studentID":e.student_id,"studentName":stu.name if stu else f"学生#{e.student_id}","draft":e.draft,"revisedDraft":e.revised_draft,"teacherFeedback":e.teacher_feedback,"status":e.status,"updatedAt":school_local_iso(e.updated_at)})
    return out

@app.put("/teaching/essays/{eid}/feedback")
def teaching_essay_feedback(eid:int,b:TeachingEssayFeedbackBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin","teacher");e=db.scalar(select(TeachingEssay).where(TeachingEssay.id==eid,TeachingEssay.school_id==u.school_id))
    if not e:raise HTTPException(404,"作文记录不存在")
    e.teacher_feedback=b.teacher_feedback.strip();e.status=b.status if b.status in ("submitted","reviewed","revised") else "reviewed";e.updated_at=datetime.utcnow();audit(db,u,"teaching.essay.feedback",f"作文#{e.id}");db.commit();return {"ok":True}

@app.get("/student/teaching/overview")
def student_teaching_overview(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"student");p=teaching_program_for(db,u.school_id)
    if not p:raise HTTPException(404,"教学方案不存在")
    lessons=db.scalars(select(TeachingLesson).where(TeachingLesson.program_id==p.id,TeachingLesson.published==True).order_by(TeachingLesson.subject,TeachingLesson.lesson_no)).all();items=[]
    for l in lessons:
        ses=latest_teaching_session(db,u.id,p.id,l.id,"lesson",l.subject)
        items.append({**teaching_lesson_json(l,False),"studyStatus":ses.status if ses else "not_started","bestLevel":(ses.final_level or ses.current_level) if ses else None,"score":ses.final_score if ses else None})
    stage_counts=teaching_question_counts(db,p)
    tests=[]
    for stage in ("midterm","final"):
        for subject in TEACHING_SUBJECTS:
            ses=latest_teaching_session(db,u.id,p.id,None,stage,subject);counts=stage_counts.get(stage,{}).get(subject,{})
            tests.append({"stage":stage,"stageName":"期中测试" if stage=="midterm" else "期末测试","subject":subject,"counts":{x:counts.get(x,0) for x in TEACHING_LEVELS},"available":sum(counts.values())>0,"status":ses.status if ses else "not_started","level":(ses.final_level or ses.current_level) if ses else None,"score":ses.final_score if ses else None})
    return {"program":teaching_program_json(db,p),"gradeMatch":u.grade==p.grade,"studentGrade":u.grade,"lessons":items,"tests":tests}

@app.get("/student/teaching/lessons/{lid}")
def student_teaching_lesson(lid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"student");p=teaching_program_for(db,u.school_id);l=db.scalar(select(TeachingLesson).where(TeachingLesson.id==lid,TeachingLesson.school_id==u.school_id,TeachingLesson.published==True))
    if not p or not l or l.program_id!=p.id:raise HTTPException(404,"课时未发布或不存在")
    require_teaching_grade(u,p)
    essay=db.scalar(select(TeachingEssay).where(TeachingEssay.lesson_id==lid,TeachingEssay.student_id==u.id,TeachingEssay.school_id==u.school_id)) if l.subject=="语文" else None
    attempts=db.scalars(select(TeachingAttempt).where(TeachingAttempt.lesson_id==lid,TeachingAttempt.student_id==u.id,TeachingAttempt.school_id==u.school_id).order_by(TeachingAttempt.id.desc()).limit(6)).all();has_wrong=any(x.correct<x.total for x in attempts)
    d=teaching_lesson_json(l,False);d.update({"examples":_json_list(l.examples_json),"closureTraining":l.closure_training if has_wrong else "","essayReview":l.essay_review if l.subject=="语文" else "","essay":{"id":essay.id,"draft":essay.draft,"revisedDraft":essay.revised_draft,"teacherFeedback":essay.teacher_feedback,"status":essay.status} if essay else None})
    return d

@app.post("/student/teaching/adaptive/start")
def student_teaching_adaptive_start(b:TeachingAdaptiveStartBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"student");p=teaching_program_for(db,u.school_id)
    if not p:raise HTTPException(404,"教学方案不存在")
    require_teaching_grade(u,p)
    if b.stage not in TEACHING_STAGES:raise HTTPException(400,"测评类型无效")
    lesson=None;subject=b.subject
    if b.stage=="lesson":
        if not b.lesson_id:raise HTTPException(400,"请选择课时")
        lesson=db.scalar(select(TeachingLesson).where(TeachingLesson.id==b.lesson_id,TeachingLesson.program_id==p.id,TeachingLesson.school_id==u.school_id,TeachingLesson.published==True))
        if not lesson:raise HTTPException(404,"课时未发布或不存在")
        subject=lesson.subject
        active=db.scalar(select(TeachingAdaptiveSession).where(TeachingAdaptiveSession.student_id==u.id,TeachingAdaptiveSession.lesson_id==lesson.id,TeachingAdaptiveSession.stage=="lesson",TeachingAdaptiveSession.status=="active").order_by(TeachingAdaptiveSession.id.desc()).limit(1))
        if active:return teaching_session_json(db,active,p,lesson,True)
    else:
        if subject not in TEACHING_SUBJECTS:raise HTTPException(400,"请选择语文或数学")
        old=latest_teaching_session(db,u.id,p.id,None,b.stage,subject)
        if old and old.status!="active":raise HTTPException(409,f"{('期中' if b.stage=='midterm' else '期末')}{subject}测试已完成，正式测评不可重复提交")
        if old:return teaching_session_json(db,old,p,None,True)
    level=first_available_level(db,p,lesson,b.stage,subject)
    if not level:raise HTTPException(400,"当前项目尚未配置分层题目")
    ses=TeachingAdaptiveSession(school_id=u.school_id,program_id=p.id,lesson_id=lesson.id if lesson else None,student_id=u.id,stage=b.stage,subject=subject,current_level=level,status="active")
    db.add(ses);db.commit();db.refresh(ses);return teaching_session_json(db,ses,p,lesson,True)

@app.post("/student/teaching/adaptive/submit")
def student_teaching_adaptive_submit(b:TeachingAdaptiveSubmitBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"student");ses=db.scalar(select(TeachingAdaptiveSession).where(TeachingAdaptiveSession.id==b.session_id,TeachingAdaptiveSession.student_id==u.id,TeachingAdaptiveSession.school_id==u.school_id))
    if not ses:raise HTTPException(404,"分层训练会话不存在")
    if ses.status!="active":raise HTTPException(409,"本次分层训练已经完成")
    p=db.get(TeachingProgram,ses.program_id);lesson=db.get(TeachingLesson,ses.lesson_id) if ses.lesson_id else None
    qs=teaching_questions_for_level(db,p,ses.current_level,lesson,ses.stage,ses.subject);normalized,correct,total,score=teaching_grade_answers(db,u,qs,b.answers)
    passed=score>=p.pass_threshold;attempt=TeachingAttempt(school_id=u.school_id,program_id=p.id,session_id=ses.id,lesson_id=ses.lesson_id,student_id=u.id,stage=ses.stage,subject=ses.subject,level=ses.current_level,score=score,correct=correct,total=total,answers_json=json.dumps(normalized,ensure_ascii=False),passed=passed);db.add(attempt);db.flush()
    completed=False;next_level=None
    if passed:
        ses.status="passed";ses.final_level=ses.current_level;ses.final_score=score;ses.completed_at=datetime.utcnow();completed=True
    else:
        next_level=first_available_level(db,p,lesson,ses.stage,ses.subject,after=ses.current_level)
        if next_level:ses.current_level=next_level
        else:ses.status="completed";ses.final_level=ses.current_level;ses.final_score=score;ses.completed_at=datetime.utcnow();completed=True
    db.commit();db.refresh(attempt)
    result={"sessionID":ses.id,"stage":ses.stage,"subject":ses.subject,"submittedLevel":attempt.level,"score":score,"correct":correct,"total":total,"passed":passed,"completed":completed,"status":ses.status,"nextLevel":next_level,"passThreshold":p.pass_threshold,"questions":[]}
    if next_level:result["questions"]=[teaching_question_json(x,True) for x in teaching_questions_for_level(db,p,next_level,lesson,ses.stage,ses.subject)]
    if ses.stage=="lesson":result["review"]=teaching_review_for_attempt(db,attempt,lesson)
    return result

@app.post("/student/teaching/lessons/{lid}/essay")
def student_teaching_essay(lid:int,b:TeachingEssayBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"student");l=db.scalar(select(TeachingLesson).where(TeachingLesson.id==lid,TeachingLesson.school_id==u.school_id,TeachingLesson.subject=="语文",TeachingLesson.published==True))
    if not l:raise HTTPException(404,"语文课时不存在")
    p=teaching_program_for(db,u.school_id)
    if not p or l.program_id!=p.id:raise HTTPException(404,"教学方案不存在")
    require_teaching_grade(u,p)
    e=db.scalar(select(TeachingEssay).where(TeachingEssay.lesson_id==lid,TeachingEssay.student_id==u.id,TeachingEssay.school_id==u.school_id))
    if not e:e=TeachingEssay(school_id=u.school_id,lesson_id=lid,student_id=u.id);db.add(e)
    e.draft=b.draft.strip();e.revised_draft=b.revised_draft.strip();e.status="revised" if e.revised_draft else "submitted";e.updated_at=datetime.utcnow();db.commit();db.refresh(e);return {"id":e.id,"status":e.status,"teacherFeedback":e.teacher_feedback}

@app.get("/parent/children/{sid}/teaching")
def parent_child_teaching(sid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"parent");link=db.scalar(select(ParentStudent).where(ParentStudent.parent_id==u.id,ParentStudent.student_id==sid))
    if not link:raise HTTPException(403,"未绑定该学生")
    stu=db.scalar(select(User).where(User.id==sid,User.school_id==u.school_id,User.role=="student"));p=teaching_program_for(db,u.school_id)
    if not stu or not p:raise HTTPException(404,"学生或教学方案不存在")
    lessons=db.scalars(select(TeachingLesson).where(TeachingLesson.program_id==p.id,TeachingLesson.published==True).order_by(TeachingLesson.subject,TeachingLesson.lesson_no)).all();items=[]
    for l in lessons:
        ses=latest_teaching_session(db,sid,p.id,l.id,"lesson",l.subject)
        essay=db.scalar(select(TeachingEssay).where(TeachingEssay.lesson_id==l.id,TeachingEssay.student_id==sid)) if l.subject=="语文" else None
        items.append({"id":l.id,"subject":l.subject,"lessonNo":l.lesson_no,"title":l.title,"unit":l.unit,"status":ses.status if ses else "not_started","level":(ses.final_level or ses.current_level) if ses else None,"score":ses.final_score if ses else None,"essayStatus":essay.status if essay else None})
    tests=[]
    for stage in ("midterm","final"):
        for subject in TEACHING_SUBJECTS:
            ses=latest_teaching_session(db,sid,p.id,None,stage,subject)
            tests.append({"stage":stage,"stageName":"期中测试" if stage=="midterm" else "期末测试","subject":subject,"status":ses.status if ses else "not_started","level":(ses.final_level or ses.current_level) if ses else None,"score":ses.final_score if ses else None})
    return {"student":{"id":stu.id,"name":stu.name,"grade":stu.grade},"program":teaching_program_json(db,p),"lessons":items,"tests":tests}


# ---------------- V7.5 classroom points & rewards API ----------------
@app.get("/points/rules")
def get_point_rules(active_only:bool=False,u:User=Depends(current_user),db:Session=Depends(get_db)):
    q=select(PointRule).where(PointRule.school_id==u.school_id)
    if active_only:q=q.where(PointRule.active==True)
    rows=db.scalars(q.order_by(PointRule.sort_order,PointRule.id)).all()
    return [point_rule_json(x) for x in rows]

@app.post("/admin/points/rules")
def create_point_rule(b:PointRuleBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");name=b.name.strip()
    if not name:raise HTTPException(400,"规则名称不能为空")
    if b.category not in ("activity","discipline"):raise HTTPException(400,"规则类别无效")
    if b.points==0 or abs(b.points)>100:raise HTTPException(400,"单次积分须为 -100 到 100 且不能为0")
    row=PointRule(school_id=u.school_id,name=name,category=b.category,points=b.points,active=b.active,require_note=b.require_note,sort_order=b.sort_order)
    db.add(row);db.flush();audit(db,u,"points.rule.create",f"{row.id}:{row.name}:{row.points}");db.commit();db.refresh(row);return point_rule_json(row)

@app.put("/admin/points/rules/{rid}")
def update_point_rule(rid:int,b:PointRuleBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");row=db.scalar(select(PointRule).where(PointRule.id==rid,PointRule.school_id==u.school_id))
    if not row:raise HTTPException(404,"积分规则不存在")
    if b.category not in ("activity","discipline"):raise HTTPException(400,"规则类别无效")
    if b.points==0 or abs(b.points)>100:raise HTTPException(400,"单次积分须为 -100 到 100 且不能为0")
    row.name=b.name.strip() or row.name;row.category=b.category;row.points=b.points;row.active=b.active;row.require_note=b.require_note;row.sort_order=b.sort_order;row.updated_at=datetime.utcnow()
    audit(db,u,"points.rule.update",f"{row.id}:{row.name}:{row.points}");db.commit();return point_rule_json(row)

@app.get("/teacher/points/classes/{cid}")
def teacher_points_class(cid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");c=current_teacher_class(db,u,cid)
    students=db.scalars(select(User).join(ClassStudent,ClassStudent.student_id==User.id).where(ClassStudent.class_id==c.id,User.school_id==u.school_id,User.role=="student",User.active==True).order_by(User.name)).all()
    return {"class":{"id":c.id,"name":c.name,"grade":c.grade},"students":[{"id":x.id,"name":x.name,"username":x.username,**point_summary(db,x.id,u.school_id)} for x in students]}

@app.post("/teacher/points/record")
def teacher_record_points(b:PointRecordBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin")
    ids=list(dict.fromkeys(int(x) for x in b.student_ids if int(x)>0))
    if not ids:raise HTTPException(400,"请选择学生")
    if len(ids)>100:raise HTTPException(400,"单次最多记录100名学生")
    rule=None;points=b.points;category=(b.category or "activity").strip();reason=(b.reason or "").strip();note=(b.note or "").strip()
    if b.rule_id:
        rule=db.scalar(select(PointRule).where(PointRule.id==b.rule_id,PointRule.school_id==u.school_id,PointRule.active==True))
        if not rule:raise HTTPException(404,"积分规则不存在或已停用")
        points=rule.points;category=rule.category;reason=rule.name
        if rule.require_note and not note:raise HTTPException(400,"该规则要求填写原因/备注")
    if points is None or points==0 or abs(points)>100:raise HTTPException(400,"单次积分须为 -100 到 100 且不能为0")
    if category not in ("activity","discipline","adjustment"):raise HTTPException(400,"积分类别无效")
    if points<0 and not (reason or note):raise HTTPException(400,"扣分必须填写原因")
    c=None
    if b.class_id:c=current_teacher_class(db,u,b.class_id)
    created=[]
    for sid in ids:
        stu=can_manage_student_points(db,u,sid,b.class_id)
        row=PointLedger(school_id=u.school_id,student_id=stu.id,class_id=c.id if c else None,actor_id=u.id,rule_id=rule.id if rule else None,category=category,points=int(points),reason=reason or ("课堂积分调整" if points>0 else "课堂守纪扣分"),note=note,source="classroom")
        db.add(row);db.flush();created.append(row)
    audit(db,u,"points.record",f"students={','.join(str(x) for x in ids)};points={points};reason={reason or note}");db.commit()
    return {"count":len(created),"points":int(points),"records":[point_ledger_json(db,x) for x in created]}

@app.get("/teacher/points/recent")
def teacher_points_recent(class_id:int|None=None,limit:int=40,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");limit=max(1,min(limit,200))
    q=select(PointLedger).where(PointLedger.school_id==u.school_id,PointLedger.source.in_(("classroom","reversal","adjustment")))
    if class_id:
        current_teacher_class(db,u,class_id);q=q.where(PointLedger.class_id==class_id)
    elif u.role=="teacher":
        own_ids=select(SchoolClass.id).where(SchoolClass.school_id==u.school_id,SchoolClass.teacher_id==u.id);q=q.where(PointLedger.class_id.in_(own_ids))
    rows=db.scalars(q.order_by(PointLedger.id.desc()).limit(limit)).all();return [point_ledger_json(db,x) for x in rows]

@app.post("/teacher/points/ledger/{lid}/undo")
def teacher_points_undo(lid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");row=db.scalar(select(PointLedger).where(PointLedger.id==lid,PointLedger.school_id==u.school_id))
    if not row:raise HTTPException(404,"积分记录不存在")
    if row.source not in ("classroom","adjustment") or row.reversed:raise HTTPException(400,"该记录不能撤销或已撤销")
    can_manage_student_points(db,u,row.student_id,row.class_id)
    rev=PointLedger(school_id=u.school_id,student_id=row.student_id,class_id=row.class_id,actor_id=u.id,rule_id=row.rule_id,category=row.category,points=-row.points,reason=f"撤销：{row.reason}",note="撤销原积分记录",source="reversal",reversal_of_id=row.id)
    row.reversed=True;db.add(rev);db.flush();audit(db,u,"points.undo",f"ledger={row.id};reversal={rev.id}");db.commit();return {"ok":True,"record":point_ledger_json(db,rev)}

@app.get("/student/points")
def student_points(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"student");summary=point_summary(db,u.id,u.school_id)
    rows=db.scalars(select(PointLedger).where(PointLedger.school_id==u.school_id,PointLedger.student_id==u.id).order_by(PointLedger.id.desc()).limit(120)).all()
    red=db.scalars(select(RewardRedemption).where(RewardRedemption.school_id==u.school_id,RewardRedemption.student_id==u.id).order_by(RewardRedemption.id.desc()).limit(50)).all()
    return {"summary":summary,"weekly":student_period_points(db,u.id,u.school_id,7),"ledger":[point_ledger_json(db,x) for x in rows],"redemptions":[redemption_json(db,x) for x in red]}

@app.get("/student/rewards")
def student_rewards(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"student");summary=point_summary(db,u.id,u.school_id)
    rows=db.scalars(select(RewardItem).where(RewardItem.school_id==u.school_id,RewardItem.active==True).order_by(RewardItem.cost_points,RewardItem.id)).all()
    return {"summary":summary,"rewards":[reward_json(db,x,u.id) for x in rows]}

@app.post("/student/rewards/{rid}/redeem")
def student_redeem_reward(rid:int,b:RewardRedeemBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"student")
    # Lock the student row to serialize concurrent redemption attempts for the same account.
    db.execute(select(User).where(User.id==u.id).with_for_update()).scalar_one()
    reward=db.execute(select(RewardItem).where(RewardItem.id==rid,RewardItem.school_id==u.school_id).with_for_update()).scalar_one_or_none()
    if not reward or not reward.active:raise HTTPException(404,"奖品不存在或已下架")
    data=reward_json(db,reward,u.id)
    if not data["available"]:raise HTTPException(400,"该奖品当前不可兑换")
    balance=point_balance(db,u.id,u.school_id)
    if balance<reward.cost_points:raise HTTPException(400,f"可用积分不足，还差 {reward.cost_points-balance} 分")
    row=RewardRedemption(school_id=u.school_id,student_id=u.id,reward_id=reward.id,reward_name=reward.name,cost_points=reward.cost_points,status="pending",note=b.note.strip())
    db.add(row);db.flush()
    ledger=PointLedger(school_id=u.school_id,student_id=u.id,class_id=(current_class_for(db,u.id,u.school_id).id if current_class_for(db,u.id,u.school_id) else None),actor_id=u.id,category="reward",points=-reward.cost_points,reason=f"兑换：{reward.name}",note=b.note.strip(),source="redemption",related_id=row.id)
    db.add(ledger)
    if not reward.unlimited_stock:reward.stock-=1
    audit(db,u,"reward.redeem",f"redemption={row.id};reward={reward.name};cost={reward.cost_points}");db.commit();db.refresh(row)
    return {"redemption":redemption_json(db,row),"summary":point_summary(db,u.id,u.school_id)}

@app.get("/admin/rewards")
def admin_rewards(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");rows=db.scalars(select(RewardItem).where(RewardItem.school_id==u.school_id).order_by(RewardItem.cost_points,RewardItem.id)).all();return [reward_json(db,x) for x in rows]

@app.post("/admin/rewards")
def create_reward(b:RewardItemBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");name=b.name.strip()
    if not name:raise HTTPException(400,"奖品名称不能为空")
    if b.cost_points<=0:raise HTTPException(400,"兑换积分必须大于0")
    if b.stock<0 or b.per_student_limit<0:raise HTTPException(400,"库存和限兑次数不能为负数")
    row=RewardItem(school_id=u.school_id,name=name,description=b.description.strip(),icon=(b.icon.strip() or "🎁")[:30],cost_points=b.cost_points,stock=b.stock,unlimited_stock=b.unlimited_stock,per_student_limit=b.per_student_limit,start_date=b.start_date.strip(),end_date=b.end_date.strip(),active=b.active)
    db.add(row);db.flush();audit(db,u,"reward.create",f"{row.id}:{row.name}:{row.cost_points}");db.commit();db.refresh(row);return reward_json(db,row)

@app.put("/admin/rewards/{rid}")
def update_reward(rid:int,b:RewardItemBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");row=db.scalar(select(RewardItem).where(RewardItem.id==rid,RewardItem.school_id==u.school_id))
    if not row:raise HTTPException(404,"奖品不存在")
    if b.cost_points<=0 or b.stock<0 or b.per_student_limit<0:raise HTTPException(400,"奖品参数无效")
    row.name=b.name.strip() or row.name;row.description=b.description.strip();row.icon=(b.icon.strip() or "🎁")[:30];row.cost_points=b.cost_points;row.stock=b.stock;row.unlimited_stock=b.unlimited_stock;row.per_student_limit=b.per_student_limit;row.start_date=b.start_date.strip();row.end_date=b.end_date.strip();row.active=b.active;row.updated_at=datetime.utcnow()
    audit(db,u,"reward.update",f"{row.id}:{row.name}:{row.cost_points}");db.commit();return reward_json(db,row)

@app.get("/rewards/redemptions")
def reward_redemptions(status:str|None=None,student_id:int|None=None,limit:int=150,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");limit=max(1,min(limit,500))
    q=select(RewardRedemption).where(RewardRedemption.school_id==u.school_id)
    if status:q=q.where(RewardRedemption.status==status)
    if student_id:q=q.where(RewardRedemption.student_id==student_id)
    rows=db.scalars(q.order_by(RewardRedemption.id.desc()).limit(limit)).all()
    if u.role=="teacher":
        own_students=set(db.scalars(select(ClassStudent.student_id).join(SchoolClass,SchoolClass.id==ClassStudent.class_id).where(SchoolClass.school_id==u.school_id,SchoolClass.teacher_id==u.id)).all())
        rows=[x for x in rows if x.student_id in own_students]
    return [redemption_json(db,x) for x in rows]

@app.post("/rewards/redemptions/{xid}/handle")
def handle_redemption(xid:int,b:RewardHandleBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");row=db.execute(select(RewardRedemption).where(RewardRedemption.id==xid,RewardRedemption.school_id==u.school_id).with_for_update()).scalar_one_or_none()
    if not row:raise HTTPException(404,"兑换记录不存在")
    can_manage_student_points(db,u,row.student_id,None)
    if row.status!="pending":raise HTTPException(400,"该兑换已处理")
    action=b.action.strip().lower()
    if action not in ("fulfill","reject"):raise HTTPException(400,"处理动作无效")
    row.handled_by=u.id;row.handled_at=datetime.utcnow();row.note=b.note.strip() or row.note
    if action=="fulfill":
        row.status="fulfilled";audit(db,u,"reward.fulfill",f"redemption={row.id};student={row.student_id};reward={row.reward_name}")
    else:
        row.status="rejected"
        reward=db.execute(select(RewardItem).where(RewardItem.id==row.reward_id).with_for_update()).scalar_one_or_none()
        if reward and not reward.unlimited_stock:reward.stock+=1
        refund=PointLedger(school_id=u.school_id,student_id=row.student_id,class_id=(current_class_for(db,row.student_id,u.school_id).id if current_class_for(db,row.student_id,u.school_id) else None),actor_id=u.id,category="reward",points=row.cost_points,reason=f"兑换退回：{row.reward_name}",note=b.note.strip(),source="refund",related_id=row.id)
        db.add(refund);audit(db,u,"reward.reject",f"redemption={row.id};refund={row.cost_points}")
    db.commit();return redemption_json(db,row)

@app.get("/parent/children/{sid}/points")
def parent_child_points(sid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"parent");link=db.scalar(select(ParentStudent.id).where(ParentStudent.parent_id==u.id,ParentStudent.student_id==sid))
    if not link:raise HTTPException(403,"未绑定该学生")
    stu=db.scalar(select(User).where(User.id==sid,User.school_id==u.school_id,User.role=="student"))
    if not stu:raise HTTPException(404,"学生不存在")
    rows=db.scalars(select(PointLedger).where(PointLedger.school_id==u.school_id,PointLedger.student_id==sid).order_by(PointLedger.id.desc()).limit(80)).all()
    red=db.scalars(select(RewardRedemption).where(RewardRedemption.school_id==u.school_id,RewardRedemption.student_id==sid).order_by(RewardRedemption.id.desc()).limit(50)).all()
    return {"student":{"id":stu.id,"name":stu.name,"grade":stu.grade},"summary":point_summary(db,sid,u.school_id),"weekly":student_period_points(db,sid,u.school_id,7),"ledger":[point_ledger_json(db,x) for x in rows],"redemptions":[redemption_json(db,x) for x in red]}

@app.get("/teacher/points/classes/{cid}/weekly")
def teacher_points_weekly(cid:int,days:int=7,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");c=current_teacher_class(db,u,cid);cutoff,days=period_cutoff_utc(days)
    students=db.scalars(select(User).join(ClassStudent,ClassStudent.student_id==User.id).where(
        ClassStudent.class_id==c.id,User.school_id==u.school_id,User.role=="student",User.active==True
    ).order_by(User.name)).all()
    ranking=[]
    totals={"earned":0,"net":0,"activity":0,"discipline":0,"redemptionCount":0,"redeemedPoints":0}
    for stu in students:
        w=student_period_points(db,stu.id,u.school_id,days)
        row={"studentID":stu.id,"studentName":stu.name,**w};ranking.append(row)
        for k in totals:totals[k]+=int(w.get(k,0) or 0)
    ranking.sort(key=lambda x:(x["earned"],x["net"],x["studentName"]),reverse=True)
    for i,x in enumerate(ranking,1):x["rank"]=i
    return {"class":{"id":c.id,"name":c.name,"grade":c.grade},"days":days,"studentCount":len(students),"totals":totals,"ranking":ranking}

@app.get("/teacher/points/classes/{cid}/weekly.xlsx")
def teacher_points_weekly_export(cid:int,days:int=7,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");data=teacher_points_weekly(cid,days,u,db)
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill
    wb=Workbook();ws=wb.active;ws.title=f"近{data['days']}天课堂积分"
    ws.append(["排名","学生","近期开获得","净表现","课堂活动","守纪积分","兑换次数","兑换积分","当前可用","累计获得"])
    for x in data["ranking"]:
        sm=point_summary(db,x["studentID"],u.school_id)
        ws.append([x["rank"],x["studentName"],x["earned"],x["net"],x["activity"],x["discipline"],x["redemptionCount"],x["redeemedPoints"],sm["available"],sm["earned"]])
    for cell in ws[1]:cell.font=Font(bold=True,color="FFFFFF");cell.fill=PatternFill("solid",fgColor="5362E8")
    ws.freeze_panes="A2"
    for col,width in {"A":8,"B":18,"C":13,"D":12,"E":12,"F":12,"G":12,"H":12,"I":12,"J":12}.items():ws.column_dimensions[col].width=width
    buf=io.BytesIO();wb.save(buf);audit(db,u,"points.weekly.export",f"class={cid};days={data['days']}");db.commit()
    return Response(buf.getvalue(),media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":f"attachment; filename=class_points_weekly_{cid}.xlsx"})

@app.get("/admin/points/dashboard")
def admin_points_dashboard(days:int=30,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");cutoff,days=period_cutoff_utc(days)
    ledgers=db.scalars(select(PointLedger).where(PointLedger.school_id==u.school_id,PointLedger.created_at>=cutoff)).all()
    classroom=[x for x in ledgers if x.source in ("classroom","adjustment","reversal")]
    earned=sum(int(x.points or 0) for x in ledgers if (x.points or 0)>0 and x.source in ("classroom","adjustment"))
    activity=sum(int(x.points or 0) for x in classroom if x.category=="activity")
    discipline=sum(int(x.points or 0) for x in classroom if x.category=="discipline")
    reds=db.scalars(select(RewardRedemption).where(RewardRedemption.school_id==u.school_id,RewardRedemption.requested_at>=cutoff)).all()
    active=[x for x in reds if x.status!="rejected"]
    by_reward={}
    for x in active:
        z=by_reward.setdefault(x.reward_name,{"rewardName":x.reward_name,"count":0,"points":0})
        z["count"]+=1;z["points"]+=int(x.cost_points or 0)
    popular=sorted(by_reward.values(),key=lambda z:(z["count"],z["points"]),reverse=True)[:8]
    low=db.scalars(select(RewardItem).where(
        RewardItem.school_id==u.school_id,RewardItem.active==True,
        RewardItem.unlimited_stock==False,RewardItem.stock<=5
    ).order_by(RewardItem.stock,RewardItem.cost_points)).all()
    student_count=int(db.scalar(select(func.count()).select_from(User).where(User.school_id==u.school_id,User.role=="student",User.active==True)) or 0)
    return {"days":days,"studentCount":student_count,"earned":earned,"activity":activity,"discipline":discipline,
            "redemptionCount":len(active),"redeemedPoints":sum(int(x.cost_points or 0) for x in active),
            "pending":sum(1 for x in reds if x.status=="pending"),"fulfilled":sum(1 for x in reds if x.status=="fulfilled"),
            "rejected":sum(1 for x in reds if x.status=="rejected"),"popularRewards":popular,
            "lowStock":[{"id":x.id,"name":x.name,"icon":x.icon or "🎁","stock":x.stock,"costPoints":x.cost_points} for x in low]}

@app.get("/admin/points/export.xlsx")
def export_points_report(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin")
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill
    wb=Workbook();ws=wb.active;ws.title="学生积分汇总";ws.append(["学生","账号","年级","当前班级","累计获得","当前余额","课堂活动","守纪积分","已兑换"]);header=1
    students=db.scalars(select(User).where(User.school_id==u.school_id,User.role=="student").order_by(User.grade,User.name)).all()
    for stu in students:
        c=current_class_for(db,stu.id,u.school_id);sm=point_summary(db,stu.id,u.school_id);ws.append([stu.name,stu.username,stu.grade or "",c.name if c else "",sm["earned"],sm["balance"],sm["activity"],sm["discipline"],sm["redeemed"]])
    for cell in ws[header]:cell.font=Font(bold=True);cell.fill=PatternFill("solid",fgColor="5362E8");cell.font=Font(bold=True,color="FFFFFF")
    ws2=wb.create_sheet("积分流水");ws2.append(["时间","学生","账号","类别","积分","原因","备注","来源","记录人"])
    rows=db.scalars(select(PointLedger).where(PointLedger.school_id==u.school_id).order_by(PointLedger.id.desc())).all()
    for x in rows:
        stu=db.get(User,x.student_id);actor=db.get(User,x.actor_id) if x.actor_id else None;ws2.append([school_local_iso(x.created_at),stu.name if stu else "",stu.username if stu else "",x.category,x.points,x.reason,x.note,x.source,actor.name if actor else "系统"])
    for cell in ws2[1]:cell.font=Font(bold=True,color="FFFFFF");cell.fill=PatternFill("solid",fgColor="5362E8")
    ws3=wb.create_sheet("奖品兑换");ws3.append(["申请时间","学生","奖品","积分","状态","处理人","处理时间","备注"])
    reds=db.scalars(select(RewardRedemption).where(RewardRedemption.school_id==u.school_id).order_by(RewardRedemption.id.desc())).all()
    for x in reds:
        j=redemption_json(db,x);ws3.append([j["requestedAt"],j["studentName"],j["rewardName"],j["costPoints"],j["status"],j["handledBy"],j["handledAt"] or "",j["note"]])
    for cell in ws3[1]:cell.font=Font(bold=True,color="FFFFFF");cell.fill=PatternFill("solid",fgColor="5362E8")
    buf=io.BytesIO();wb.save(buf);audit(db,u,"points.export","积分奖励报表");db.commit();return Response(buf.getvalue(),media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":"attachment; filename=points_rewards_report.xlsx"})

INDEX_HTML = '<!doctype html>\n<html lang="zh-CN">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n  <meta name="theme-color" content="#5362e8">\n  <meta name="apple-mobile-web-app-capable" content="yes">\n  <meta name="apple-mobile-web-app-title" content="小学题库">\n  <title>小学题库 V7</title>\n  \n  \n  <style>\n\n:root{\n  --bg:#f4f6fb;--card:#fff;--text:#1f2738;--muted:#778095;--line:#e5e8f0;\n  --primary:#5362e8;--soft:#eef0ff;--green:#18855d;--red:#d6485e;--amber:#d98b25;\n  --shadow:0 14px 38px rgba(38,48,95,.10)\n}\n*{box-sizing:border-box}\nhtml,body{margin:0;min-height:100%;font-family:Inter,"PingFang SC","Microsoft YaHei",system-ui,sans-serif;background:var(--bg);color:var(--text)}\nbutton,input,select,textarea{font:inherit} button{cursor:pointer}\n.hidden{display:none!important}.muted{color:var(--muted)}\n.login-screen{min-height:100vh;display:grid;place-items:center;padding:20px;background:linear-gradient(135deg,#edf0ff,#fafbff)}\n.login-card{width:min(430px,100%);background:#fff;border:1px solid var(--line);border-radius:28px;padding:28px;box-shadow:var(--shadow)}\n.logo{width:84px;height:84px;border-radius:26px;display:grid;place-items:center;font-size:42px;margin:auto;background:linear-gradient(135deg,var(--primary),#8b75ef)}\n.login-card h1{text-align:center;margin:12px 0 3px}.login-card>p{text-align:center;margin:0 0 22px}\nlabel{display:block;font-size:12px;font-weight:800;margin:12px 0 6px}\ninput,select,textarea{width:100%;padding:11px 12px;border:1px solid var(--line);border-radius:12px;background:#fff;color:var(--text);outline:none}\ninput:focus,select:focus,textarea:focus{border-color:#9ba5f1;box-shadow:0 0 0 3px rgba(83,98,232,.10)}\ntextarea{min-height:100px;resize:vertical}\n.btn{border:0;border-radius:12px;padding:10px 13px}.primary{background:var(--primary);color:#fff;font-weight:800}.secondary{background:#eef1f6;color:#3b455e;font-weight:700}.danger{background:#fff0f2;color:var(--red)}.full{width:100%;margin-top:11px}\n.demo-box{margin-top:16px;padding:12px;background:#f7f8fc;border-radius:12px;color:var(--muted);font-size:12px;line-height:1.7}\n\n.shell{display:grid;grid-template-columns:258px minmax(0,1fr);min-height:100vh}\n.sidebar{height:100vh;position:sticky;top:0;background:#fff;border-right:1px solid var(--line);padding:17px;display:flex;flex-direction:column;z-index:30}\n.brand{display:flex;align-items:center;gap:10px;padding:5px 5px 18px}.brand>span{font-size:24px;background:var(--soft);padding:9px;border-radius:14px}.brand b,.brand small{display:block}.brand small{color:var(--muted);font-size:11px;margin-top:2px}\nnav{display:grid;gap:5px}.nav-btn{border:0;background:transparent;color:#626c81;border-radius:12px;padding:11px 12px;display:flex;gap:10px;align-items:center;text-align:left}.nav-btn.active{background:var(--soft);color:var(--primary);font-weight:800}\n.sidebar-foot{margin-top:auto}.user-badge{font-size:13px;padding:10px 4px}.user-badge b,.user-badge span{display:block}.user-badge span{color:var(--muted);font-size:12px}\n.main{padding:28px;min-width:0}.mobile-header{display:none}\n.page-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;margin-bottom:18px}.page-head h1{margin:0 0 5px;font-size:26px}.page-head p{margin:0;color:var(--muted)}\n.actions{display:flex;gap:8px;flex-wrap:wrap}\n.card{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:18px;box-shadow:0 8px 24px rgba(38,48,95,.05)}\n.hero{border-radius:23px;padding:24px;background:linear-gradient(135deg,#5362e8,#8a72ec);color:#fff}.hero p{color:#e7e9ff;max-width:760px}\n.grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.grid3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.grid4{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}\n.stat b{display:block;font-size:28px;color:var(--primary)}.stat small{color:var(--muted)}\n.section{margin-top:18px}.section h2{font-size:17px;margin:0 0 11px}\n.list{display:grid;gap:9px}.item{background:#fff;border:1px solid var(--line);border-radius:15px;padding:13px 14px;display:flex;justify-content:space-between;align-items:center;gap:10px}.item-main{min-width:0}.item-main b{display:block;margin-bottom:4px}.item-main small{color:var(--muted)}\n.badge{display:inline-flex;border-radius:999px;padding:4px 8px;background:var(--soft);color:var(--primary);font-size:11px;font-weight:800}.badge.green{background:#eaf8f2;color:var(--green)}.badge.red{background:#fff0f2;color:var(--red)}.badge.amber{background:#fff7e7;color:var(--amber)}\n.filters{display:flex;gap:9px;flex-wrap:wrap;margin-bottom:12px}.filters>*{width:auto;min-width:130px;flex:0 1 auto}\n.small{font-size:12px;padding:7px 9px}.empty{text-align:center;color:var(--muted);padding:36px}\n.table-wrap{overflow:auto}.table{width:100%;border-collapse:collapse;min-width:720px}.table th,.table td{padding:11px;border-bottom:1px solid var(--line);font-size:13px;text-align:left}.table th{color:var(--muted);font-weight:700}\n.progress{height:9px;border-radius:999px;background:#eaedf4;overflow:hidden}.progress i{height:100%;display:block;background:var(--primary)}\n.question{font-size:22px;line-height:1.6;font-weight:800;margin:18px 0}.option{width:100%;display:flex;align-items:center;gap:10px;text-align:left;padding:13px;margin:9px 0;background:#fff;border:1px solid var(--line);border-radius:14px}.option.selected{background:var(--soft);border-color:#a5adf3}.option.correct{background:#edf9f4;border-color:#75cfaa}.option.wrong{background:#fff1f3;border-color:#ef929e}.letter{width:31px;height:31px;border-radius:50%;display:grid;place-items:center;background:#f0f2f7;font-weight:800;flex:none}.answer{margin-top:14px;padding:13px;border-radius:14px;background:#f6f7fb;line-height:1.6}\n.chart-row{display:grid;grid-template-columns:repeat(10,1fr);align-items:end;height:180px;gap:8px;padding:10px 4px 0}.bar{background:linear-gradient(180deg,#7580ef,#5362e8);border-radius:8px 8px 2px 2px;min-height:4px;position:relative}.bar span{position:absolute;bottom:-24px;left:50%;transform:translateX(-50%);font-size:10px;color:var(--muted);white-space:nowrap}\n.knowledge{display:grid;gap:9px}.knowledge-row{display:grid;grid-template-columns:minmax(110px,1fr) 3fr 55px;gap:10px;align-items:center}.knowledge-row small{overflow:hidden;text-overflow:ellipsis}.knowledge-meter{height:9px;background:#edf0f5;border-radius:999px;overflow:hidden}.knowledge-meter i{display:block;height:100%;background:var(--primary)}\n.toast{position:fixed;top:18px;right:18px;z-index:100;background:#252b3e;color:#fff;padding:11px 15px;border-radius:12px;box-shadow:var(--shadow);opacity:0;transform:translateY(-10px);transition:.2s;pointer-events:none}.toast.show{opacity:1;transform:none}\ndialog{border:0;background:transparent;padding:16px;width:min(700px,100%)}dialog::backdrop{background:rgba(22,27,42,.47)}.modal-card{background:#fff;border-radius:22px;padding:18px;max-height:88vh;overflow:auto;box-shadow:var(--shadow)}.modal-head{display:flex;align-items:center;justify-content:space-between}.modal-head h3{margin:0}.icon-btn{border:0;background:transparent;padding:8px}\n.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}\n.note{font-size:12px;background:#fff7e7;color:#7b5719;padding:10px 12px;border-radius:12px}\n.rank1{font-weight:900;color:#b37511}\n.mobile-only{display:none}.status-line{display:flex;gap:6px;flex-wrap:wrap;align-items:center}.account-card{display:grid;gap:10px}.account-card .account-actions{display:flex;gap:8px;flex-wrap:wrap}.account-card .account-actions .btn{flex:1}.bottom-nav{display:none}.compact-help{margin-top:10px}.compact-help summary{cursor:pointer;font-weight:800;color:var(--primary)}.compact-help p{margin:8px 0 0;line-height:1.65}\n@media(max-width:960px){\n .shell{grid-template-columns:1fr}.sidebar{position:fixed;left:-270px;width:258px;transition:.2s;box-shadow:var(--shadow)}.sidebar.open{left:0}\n .main{padding:0 14px 25px}.mobile-header{display:flex;position:sticky;top:0;z-index:20;margin:0 -14px 18px;padding:calc(12px + env(safe-area-inset-top)) 14px 12px;align-items:center;justify-content:space-between;background:rgba(255,255,255,.96);border-bottom:1px solid var(--line)}\n .grid4{grid-template-columns:repeat(2,1fr)}\n}\n@media(max-width:650px){\n .main{padding-bottom:calc(116px + env(safe-area-inset-bottom))}.grid2,.grid3{grid-template-columns:1fr}.page-head{display:block;margin-bottom:13px}.page-head h1{font-size:22px}.page-head p{font-size:13px}.page-head .actions{margin-top:10px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.page-head .actions .btn{width:100%;padding:10px 8px}\n .card{padding:14px;border-radius:16px}.section{margin-top:13px}.stat b{font-size:24px}.form-grid{grid-template-columns:1fr}.filters{display:grid;grid-template-columns:1fr 1fr;gap:8px}.filters>*{width:100%;min-width:0}.question{font-size:19px}\n .knowledge-row{grid-template-columns:92px 1fr 42px}.desktop-only{display:none!important}.mobile-only{display:block}.item{align-items:flex-start}.toast{left:14px;right:14px;top:12px;text-align:center}\n dialog{padding:0;align-items:end}.modal-card{border-radius:22px 22px 0 0;max-height:calc(82vh - env(safe-area-inset-top));padding-bottom:calc(18px + env(safe-area-inset-bottom))}.bottom-nav{position:fixed;left:0;right:0;bottom:0;z-index:25;display:grid;grid-template-columns:repeat(var(--bottom-count,5),minmax(0,1fr));padding:7px 8px calc(7px + env(safe-area-inset-bottom));background:rgba(255,255,255,.97);border-top:1px solid var(--line);box-shadow:0 -8px 24px rgba(38,48,95,.08)}.bottom-nav:empty{display:none}.bottom-nav-btn{border:0;background:transparent;color:#778095;display:grid;place-items:center;gap:2px;padding:4px 2px;font-size:10px;min-width:0}.bottom-nav-btn span{font-size:20px}.bottom-nav-btn.active{color:var(--primary);font-weight:800}\n}\n\n.teach-hero{background:linear-gradient(135deg,#4658df,#7a66e9);color:#fff}.teach-hero p{color:#eef0ff}.subject-tabs{display:flex;gap:8px;flex-wrap:wrap}.subject-tabs .btn.active{background:var(--primary);color:#fff}.lesson-meta{display:flex;gap:6px;flex-wrap:wrap;margin-top:7px}.level-badge{display:inline-flex;min-width:30px;justify-content:center;border-radius:999px;padding:5px 9px;font-size:12px;font-weight:900}.level-C{background:#f4eefe;color:#6f42c1}.level-B{background:#eef4ff;color:#315fc4}.level-A{background:#eaf8f2;color:#18855d}.slide-view{min-height:280px;display:grid;place-items:center;text-align:center;padding:26px;border-radius:18px;background:linear-gradient(135deg,#f5f6ff,#fff);border:1px solid var(--line)}.slide-view h2{font-size:26px;line-height:1.5}.adaptive-q{padding:14px;border:1px solid var(--line);border-radius:15px;margin:10px 0}.adaptive-q b{display:block;margin-bottom:9px}.adaptive-option{display:flex;gap:8px;align-items:flex-start;padding:8px;border-radius:10px}.adaptive-option input{width:auto;margin-top:4px}.lesson-tools{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}.lesson-tools .btn{flex:0 0 auto}.teaching-timeline{white-space:pre-wrap;line-height:1.75}.essay-box textarea{min-height:150px}.stage-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}@media(max-width:650px){.stage-grid{grid-template-columns:1fr}.lesson-tools{display:grid;grid-template-columns:1fr 1fr}.lesson-tools .btn{width:100%}.slide-view{min-height:230px}.slide-view h2{font-size:22px}}\n\n\n.reward-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.reward-card{position:relative}.reward-icon{font-size:36px}.point-positive{color:var(--green);font-weight:900}.point-negative{color:var(--red);font-weight:900}.rule-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.rule-btn{border:1px solid var(--line);background:#fff;border-radius:14px;padding:11px;text-align:left}.rule-btn.active{border-color:var(--primary);box-shadow:0 0 0 3px rgba(83,98,232,.10);background:var(--soft)}.check-card{display:flex;align-items:center;gap:10px}.check-card input{width:auto}.split-tabs{display:flex;gap:8px;flex-wrap:wrap}.split-tabs .btn.active{background:var(--primary);color:#fff}.ledger-row{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:start}.ledger-row small{display:block;color:var(--muted);margin-top:4px}@media(max-width:650px){.reward-grid{grid-template-columns:1fr 1fr}.rule-grid{grid-template-columns:1fr 1fr}}\n</style>\n</head>\n<body>\n<div id="toast" class="toast"></div><div id="sessionCheck" class="hidden" style="position:fixed;inset:0;z-index:9998;background:rgba(244,246,251,.96);display:grid;place-items:center;text-align:center;padding:24px"><div><div style="font-size:42px">📚</div><h3>正在验证登录状态…</h3><p class="muted">请稍候</p></div></div>\n\n<section id="loginScreen" class="login-screen">\n  <div class="login-card">\n    <div class="logo">📚</div>\n    <h1>小学题库</h1>\n    <p class="muted">V7.6.2 运营周报稳定修正版</p>\n    <label>服务器地址（网址版保持默认即可）</label>\n    <input id="serverURL" placeholder="http://127.0.0.1:8000">\n    <label>账号</label>\n    <input id="username" placeholder="请输入账号" autocomplete="username">\n    <label>密码</label>\n    <input id="password" type="password" value="" placeholder="请输入密码" autocomplete="current-password">\n    <div style="display:grid;gap:8px;margin:10px 0 14px">\n      <label style="display:flex;align-items:center;gap:8px;margin:0;font-weight:500"><input id="showPwd" type="checkbox" style="width:auto">显示密码</label>\n      <label style="display:flex;align-items:center;gap:8px;margin:0;font-weight:500"><input id="rememberLogin" type="checkbox" style="width:auto">在此设备保持登录（个人设备）</label>\n      <small class="muted">共享、学校公共设备请不要勾选；未勾选时只在当前浏览器会话中保存登录。</small>\n    </div><button id="loginBtn" class="btn primary full">登录</button>\n    <button id="offlineBtn" class="btn secondary full">离线学生体验</button>\n    <div class="demo-box">请使用管理员或学校分配的账号登录。首次登录如提示修改密码，请设置自己的安全密码。</div>\n  </div>\n</section>\n\n<div id="shell" class="shell hidden">\n  <aside id="sidebar" class="sidebar">\n    <div class="brand"><span>📚</span><div><b>小学题库</b><small>V7.6.2 运营周报稳定修正版</small></div></div>\n    <nav id="nav"></nav>\n    <div class="sidebar-foot">\n      <div id="userBadge" class="user-badge"></div>\n      <button id="logoutBtn" class="btn secondary full">退出登录</button>\n    </div>\n  </aside>\n  <main class="main">\n    <header class="mobile-header">\n      <button id="menuBtn" class="icon-btn">☰</button>\n      <b>小学题库 V7.6.2</b>\n      <span></span>\n    </header>\n    <div id="page"></div>\n  </main>\n  <nav id="bottomNav" class="bottom-nav"></nav>\n</div>\n\n<dialog id="modal">\n  <div class="modal-card">\n    <div class="modal-head"><h3 id="modalTitle"></h3><button id="modalClose" class="icon-btn">✕</button></div>\n    <div id="modalBody"></div>\n  </div>\n</dialog>\n\n<script>\n\nconst $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];\nconst defaultAPI=(location.protocol==="http:"||location.protocol==="https:")?location.origin:"http://127.0.0.1:8000";\n// V7.1.8: keep the V7.1.7 browser-session migration for backward compatibility.\nif(localStorage.getItem("v6Token") && !localStorage.getItem("v717Migrated")){\n sessionStorage.setItem("v717Token",localStorage.getItem("v6Token")||"");\n sessionStorage.setItem("v717User",localStorage.getItem("v6User")||"null");\n localStorage.removeItem("v6Token");localStorage.removeItem("v6User");\n localStorage.setItem("v717Migrated","1");\n}\nconst initialRemember=localStorage.getItem("v717Remember")==="1";\nconst state={\n api:localStorage.getItem("v6Server")||defaultAPI,\n token:(initialRemember?localStorage.getItem("v717Token"):sessionStorage.getItem("v717Token"))||"",\n user:JSON.parse((initialRemember?localStorage.getItem("v717User"):sessionStorage.getItem("v717User"))||"null"),\n remember:initialRemember,\n offline:false,page:""\n};\nfunction saveAuth(){\n const store=state.remember?localStorage:sessionStorage;\n const other=state.remember?sessionStorage:localStorage;\n store.setItem("v717Token",state.token||"");store.setItem("v717User",JSON.stringify(state.user||null));\n other.removeItem("v717Token");other.removeItem("v717User");\n localStorage.setItem("v717Remember",state.remember?"1":"0");\n}\nfunction clearAuth(){\n state.token="";state.user=null;state.remember=false;\n localStorage.removeItem("v717Token");localStorage.removeItem("v717User");localStorage.removeItem("v717Remember");\n sessionStorage.removeItem("v717Token");sessionStorage.removeItem("v717User");\n localStorage.removeItem("v6Token");localStorage.removeItem("v6User");\n}\nconst offlineBank=[\n {id:1,grade:1,subject:"数学",textbook:"人教版",semester:"上册",unit:"第一单元",knowledge:"20以内加法",text:"7 + 5 = ?",options:["10","11","12","13"],correctIndex:2,explanation:"7+5=12。"},\n {id:2,grade:3,subject:"数学",textbook:"人教版",semester:"上册",unit:"第一单元",knowledge:"时分秒",text:"1分钟等于多少秒？",options:["30","60","90","100"],correctIndex:1,explanation:"1分钟=60秒。"},\n {id:3,grade:3,subject:"语文",textbook:"人教版",semester:"上册",unit:"第一单元",knowledge:"词语",text:"“绚丽多彩”的近义词是？",options:["五颜六色","灰暗无光","一模一样","安安静静"],correctIndex:0,explanation:"与“五颜六色”意思相近。"},\n {id:4,grade:3,subject:"英语",textbook:"人教PEP",semester:"上册",unit:"Unit 1",knowledge:"单词",text:"“尺子”的英文是？",options:["book","ruler","pencil","bag"],correctIndex:1,explanation:"ruler=尺子。"},\n {id:5,grade:5,subject:"数学",textbook:"北师大版",semester:"下册",unit:"第三单元",knowledge:"分数",text:"1/2 + 1/4 = ?",options:["1/6","2/6","3/4","1"],correctIndex:2,explanation:"通分后为3/4。"}\n];\n\nconst menus={\n admin:[["admin","🛡️","平台总览"],["users","👥","账号管理"],["pointsAdmin","⭐","积分奖励"],["teaching","🎯","定制教学"],["imports","📥","批量导入"],["catalog","📚","教材题库"],["adminAudit","🧾","全校审计"],["system","⚙️","系统设置"]],\n teacher:[["teacher","📊","教师工作台"],["classes","👥","班级学生"],["classPoints","⭐","课堂积分"],["teaching","🎯","定制教学"],["catalog","📚","教材题库"],["papers","📝","组卷作业"],["analytics","📈","学情分析"],["audit","🧾","操作记录"],["leaderboard","🏆","排行榜"],["account","👤","我的"]],\n student:[["student","🏠","学习首页"],["syncLearning","🎯","同步课堂"],["rewards","🎁","积分奖励"],["assignments","📝","我的作业"],["practice","✏️","自主练习"],["progress","📈","我的学情"],["leaderboard","🏆","班级排行"],["account","👤","我的"]],\n parent:[["parent","👨\u200d👩\u200d👧","家长首页"],["childLearning","🎯","孩子课程"],["childRewards","🎁","课堂表现"],["childProgress","📈","孩子学情"],["childAssignments","📝","孩子作业"],["account","👤","我的"]],\n offline:[["practice","✏️","离线练习"],["account","👤","本机设置"]]\n};\n\nfunction esc(v=""){return String(v).replace(/[&<>"\']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",\'"\':"&quot;","\'":"&#039;"}[m]))}\nfunction toast(msg){const t=$("#toast");t.textContent=msg;t.classList.add("show");setTimeout(()=>t.classList.remove("show"),2300)}\nfunction roleName(r){return ({admin:"管理员",teacher:"教师",student:"学生",parent:"家长"})[r]||r}\nfunction head(t,s,a=""){return `<div class="page-head"><div><h1>${t}</h1><p>${s}</p></div><div class="actions">${a}</div></div>`}\nfunction stat(v,t){return `<div class="card stat"><b>${esc(v)}</b><small>${esc(t)}</small></div>`}\nfunction empty(t){return `<div class="card empty">${esc(t)}</div>`}\nfunction modal(title,body){$("#modalTitle").textContent=title;$("#modalBody").innerHTML=body;if(!$("#modal").open)$("#modal").showModal()}\nfunction closeModal(){$("#modal").close()}\nfunction pct(n,d){return d?Math.round(n/d*100):0}\nfunction statusClass(code){return code==="completed"?"green":(code==="pending"?"":(code==="late_completed"?"amber":"red"))}\nasync function downloadWithAuth(path,filename){\n const r=await fetch(state.api+path,{headers:{Authorization:`Bearer ${state.token}`}});\n if(!r.ok){let d={};try{d=await r.json()}catch{};throw new Error(d.detail||"下载失败")}\n const blob=await r.blob(),url=URL.createObjectURL(blob),a=document.createElement("a");\n a.href=url;a.download=filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1200)\n}\nasync function api(path,opt={}){\n if(state.offline)throw new Error("离线模式无法访问服务器");\n const h={"Content-Type":"application/json",...(opt.headers||{})}; if(state.token)h.Authorization=`Bearer ${state.token}`;\n const r=await fetch(state.api+path,{...opt,headers:h});let d={};try{d=await r.json()}catch{}\n if(!r.ok){\n  if(r.status===401 && state.token){\n    const msg=d.detail||"登录已过期，请重新登录";\n    clearAuth();\n    $("#shell").classList.add("hidden");$("#loginScreen").classList.remove("hidden");\n    toast(msg);\n    throw new Error(msg);\n  }\n  if(r.status===428 && state.user){\n    state.user.mustChangePassword=true;saveAuth();\n    if(state.page!=="forcePassword") go("forcePassword");\n  }\n  throw new Error(d.detail||`请求失败 ${r.status}`)\n }\n return d\n}\nfunction renderNav(){\n const key=state.offline?"offline":state.user?.role;\n const visibleMenus=(!state.offline&&state.user?.mustChangePassword)?[]:(menus[key]||[]);\n $("#nav").innerHTML=visibleMenus.map(([id,ico,name])=>`<button class="nav-btn ${state.page===id?"active":""}" data-page="${id}"><span>${ico}</span>${name}</button>`).join("");\n $$(".nav-btn").forEach(b=>b.onclick=()=>go(b.dataset.page));\n const bottomIds={admin:["admin","users","pointsAdmin","teaching","system"],teacher:["teacher","classes","classPoints","teaching","account"],student:["student","syncLearning","rewards","assignments","account"],parent:["parent","childRewards","childAssignments","childProgress","account"],offline:["practice","account"]}[key]||[];\n const bottomMenus=visibleMenus.filter(x=>bottomIds.includes(x[0]));\n $("#bottomNav").style.setProperty("--bottom-count",Math.max(bottomMenus.length,1));\n $("#bottomNav").innerHTML=bottomMenus.map(([id,ico,name])=>`<button class="bottom-nav-btn ${state.page===id?"active":""}" data-page="${id}"><span>${ico}</span><b>${name}</b></button>`).join("");\n $$(".bottom-nav-btn").forEach(b=>b.onclick=()=>go(b.dataset.page));\n $("#userBadge").innerHTML=state.offline?`<b>离线学生</b><span>本机体验</span>`:`<b>${esc(state.user?.name||"")}</b><span>${roleName(state.user?.role)}</span>`;\n}\nasync function go(p){\n state.page=p;renderNav();$("#sidebar").classList.remove("open");\n const fn={admin,users,imports,catalog,adminAudit,system,pointsAdmin,teaching,teacher,classes,classPoints,papers,analytics,audit,leaderboard,student,syncLearning,syncLesson,rewards,assignments,practice,progress,parent,childLearning,childRewards,childProgress,childAssignments,account,forcePassword}[p]||practice;\n try{await fn();requestAnimationFrame(()=>{window.scrollTo(0,0);document.documentElement.scrollTop=0;document.body.scrollTop=0})}catch(e){$("#page").innerHTML=empty(e.message)}\n}\n\n// Login\nasync function login(){\n state.api=$("#serverURL").value.trim().replace(/\\/$/,"");localStorage.setItem("v6Server",state.api);\n const btn=$("#loginBtn"),oldText=btn.textContent;\n btn.disabled=true;btn.textContent="正在连接服务器…";\n try{\n  const remember=$("#rememberLogin").checked;\n  const r=await fetch(state.api+"/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:$("#username").value.trim(),password:$("#password").value,remember})});\n  const d=await r.json();if(!r.ok)throw new Error(d.detail||"登录失败");\n  state.token=d.token;state.user={id:d.userID,name:d.name,role:d.role,grade:d.grade,mustChangePassword:!!d.mustChangePassword};state.remember=remember;state.offline=false;\n  saveAuth();enter();\n }catch(e){toast(e.message)}finally{btn.disabled=false;btn.textContent=oldText}\n}\nfunction enter(){\n $("#loginScreen").classList.add("hidden");$("#shell").classList.remove("hidden");\n const d=state.offline?"practice":(state.user?.mustChangePassword?"forcePassword":({admin:"admin",teacher:"teacher",student:"student",parent:"parent"})[state.user.role]);\n go(d);\n}\nfunction logout(){\n if(!state.offline && !confirm("确定退出当前账号吗？"))return;\n clearAuth();state.offline=false;state.page="";\n $("#shell").classList.add("hidden");$("#loginScreen").classList.remove("hidden");\n $("#password").value="";toast("已退出登录");\n}\n\n\nasync function pointsAdmin(){\n const [rules,rewards,reds,dash]=await Promise.all([api("/points/rules"),api("/admin/rewards"),api("/rewards/redemptions?limit=100"),api("/admin/points/dashboard?days=30")]);\n const pending=reds.filter(x=>x.status==="pending");\n const tabs=`<div class="split-tabs"><button class="btn secondary active" id="paRulesTab">积分规则</button><button class="btn secondary" id="paRewardsTab">奖品设置</button><button class="btn secondary" id="paRedeemTab">兑换处理 ${pending.length?`(${pending.length})`:""}</button><button class="btn secondary" id="paStatsTab">运营统计</button></div>`;\n const ruleCard=x=>`<div class="item"><div class="item-main"><b>${esc(x.name)} <span class="${x.points>0?"point-positive":"point-negative"}">${x.points>0?"+":""}${x.points}</span></b><small>${x.category==="activity"?"课堂活动":"守纪情况"}${x.requireNote?" · 必填备注":""} · ${x.active?"启用":"停用"}</small></div><button class="btn secondary small editRule" data-id="${x.id}">编辑</button></div>`;\n const rewardCard=x=>`<div class="card reward-card"><div class="reward-icon">${esc(x.icon)}</div><h2>${esc(x.name)}</h2><p class="muted">${esc(x.description||"暂无说明")}</p><div class="status-line"><span class="badge">${x.costPoints}积分</span><span class="badge ${x.active?"green":"red"}">${x.active?"上架":"下架"}</span><span class="badge">${x.unlimitedStock?"不限库存":"库存 "+x.stock}</span></div><button class="btn secondary full editReward" data-id="${x.id}">编辑奖品</button></div>`;\n function statsView(d){return `<div class="filters"><select id="opsDays"><option value="7">近7天</option><option value="30" selected>近30天</option><option value="90">近90天</option></select></div><div class="grid4">${stat(d.earned,"发放积分")}${stat(d.redeemedPoints,"兑换积分")}${stat(d.redemptionCount,"有效兑换")}${stat(d.pending,"待发放")}</div><div class="section grid2"><div class="card"><h2>积分结构</h2><div class="list"><div class="item"><b>课堂活动净积分</b><b class="point-positive">${d.activity}</b></div><div class="item"><b>守纪净积分</b><b class="${d.discipline>=0?"point-positive":"point-negative"}">${d.discipline}</b></div><div class="item"><b>在用学生</b><b>${d.studentCount}</b></div><div class="item"><b>已领取 / 已退回</b><b>${d.fulfilled} / ${d.rejected}</b></div></div></div><div class="card"><h2>热门奖品</h2><div class="list">${d.popularRewards.map(x=>`<div class="item"><div><b>${esc(x.rewardName)}</b><small>${x.points}积分</small></div><span class="badge">${x.count}次</span></div>`).join("")||`<span class="muted">暂无兑换数据</span>`}</div></div></div><div class="section card"><h2>低库存提醒</h2><div class="list">${d.lowStock.map(x=>`<div class="item"><div><b>${esc(x.icon)} ${esc(x.name)}</b><small>${x.costPoints}积分</small></div><span class="badge ${x.stock===0?"red":"amber"}">库存 ${x.stock}</span></div>`).join("")||`<span class="muted">暂无低库存奖品</span>`}</div></div>`}\n function draw(which){\n  $$(".split-tabs .btn").forEach(b=>b.classList.remove("active"));\n  if(which==="rules"){$("#paRulesTab").classList.add("active");$("#pointsAdminBody").innerHTML=`<div class="section"><div class="actions"><button id="newRule" class="btn primary">＋新增规则</button><button id="exportPoints" class="btn secondary">导出积分奖励报表</button></div></div><div class="section list">${rules.map(ruleCard).join("")||empty("暂无积分规则")}</div>`;bindRules()}\n  if(which==="rewards"){$("#paRewardsTab").classList.add("active");$("#pointsAdminBody").innerHTML=`<div class="section"><button id="newReward" class="btn primary">＋新增奖品</button></div><div class="section reward-grid">${rewards.map(rewardCard).join("")||empty("暂无奖品")}</div>`;bindRewards()}\n  if(which==="redeem"){$("#paRedeemTab").classList.add("active");$("#pointsAdminBody").innerHTML=`<div class="section list">${reds.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.studentName)} · ${esc(x.rewardName)}</b><small>${x.costPoints}积分 · ${esc(x.requestedAt||"")} · ${x.status==="pending"?"待领取":x.status==="fulfilled"?"已领取":"已拒绝/退回"}</small></div>${x.status==="pending"?`<div class="actions"><button class="btn primary small fulfillRed" data-id="${x.id}">确认发放</button><button class="btn danger small rejectRed" data-id="${x.id}">拒绝退分</button></div>`:`<span class="badge ${x.status==="fulfilled"?"green":"red"}">${x.status==="fulfilled"?"已领取":"已退回"}</span>`}</div>`).join("")||empty("暂无兑换记录")}</div>`;bindRedeem()}\n  if(which==="stats"){$("#paStatsTab").classList.add("active");$("#pointsAdminBody").innerHTML=statsView(dash);const changeOpsDays=async()=>{try{const days=+$("#opsDays").value,d=await api(`/admin/points/dashboard?days=${days}`);dash.days=d.days;dash.studentCount=d.studentCount;dash.earned=d.earned;dash.activity=d.activity;dash.discipline=d.discipline;dash.redemptionCount=d.redemptionCount;dash.redeemedPoints=d.redeemedPoints;dash.pending=d.pending;dash.fulfilled=d.fulfilled;dash.rejected=d.rejected;dash.popularRewards=d.popularRewards;dash.lowStock=d.lowStock;draw("stats")}catch(e){toast(e.message)}};$("#opsDays").value=String(dash.days||30);$("#opsDays").onchange=changeOpsDays}\n }\n function ruleForm(x={}){modal(x.id?"编辑积分规则":"新增积分规则",`<label>规则名称</label><input id="prName" value="${esc(x.name||"")}"><div class="form-grid"><div><label>类别</label><select id="prCat"><option value="activity" ${x.category==="activity"?"selected":""}>课堂活动</option><option value="discipline" ${x.category==="discipline"?"selected":""}>守纪情况</option></select></div><div><label>积分（可负数）</label><input id="prPts" type="number" value="${x.points??1}"></div></div><label style="display:flex;gap:8px;align-items:center"><input id="prNote" type="checkbox" style="width:auto" ${x.requireNote?"checked":""}>要求填写备注</label><label style="display:flex;gap:8px;align-items:center"><input id="prActive" type="checkbox" style="width:auto" ${x.active===false?"":"checked"}>启用</label><button id="saveRule" class="btn primary full">保存</button>`);$("#saveRule").onclick=async()=>{try{const body={name:$("#prName").value,category:$("#prCat").value,points:+$("#prPts").value,active:$("#prActive").checked,require_note:$("#prNote").checked,sort_order:x.sortOrder||0};await api(x.id?`/admin/points/rules/${x.id}`:"/admin/points/rules",{method:x.id?"PUT":"POST",body:JSON.stringify(body)});closeModal();toast("积分规则已保存");pointsAdmin()}catch(e){toast(e.message)}}}\n function rewardForm(x={}){modal(x.id?"编辑奖品":"新增奖品",`<div class="form-grid"><div><label>图标</label><input id="rwIcon" value="${esc(x.icon||"🎁")}"></div><div><label>奖品名称</label><input id="rwName" value="${esc(x.name||"")}"></div></div><label>奖品说明</label><textarea id="rwDesc">${esc(x.description||"")}</textarea><div class="form-grid"><div><label>所需积分</label><input id="rwCost" type="number" min="1" value="${x.costPoints||100}"></div><div><label>库存</label><input id="rwStock" type="number" min="0" value="${x.stock||0}"></div><div><label>每人限兑次数（0不限）</label><input id="rwLimit" type="number" min="0" value="${x.perStudentLimit||0}"></div><div><label>有效开始日期</label><input id="rwStart" type="date" value="${esc(x.startDate||"")}"></div><div><label>有效截止日期</label><input id="rwEnd" type="date" value="${esc(x.endDate||"")}"></div></div><label style="display:flex;gap:8px;align-items:center"><input id="rwUnlimited" type="checkbox" style="width:auto" ${x.unlimitedStock?"checked":""}>不限库存</label><label style="display:flex;gap:8px;align-items:center"><input id="rwActive" type="checkbox" style="width:auto" ${x.active===false?"":"checked"}>上架启用</label><button id="saveReward" class="btn primary full">保存奖品</button>`);$("#saveReward").onclick=async()=>{try{const body={name:$("#rwName").value,description:$("#rwDesc").value,icon:$("#rwIcon").value,cost_points:+$("#rwCost").value,stock:+$("#rwStock").value,unlimited_stock:$("#rwUnlimited").checked,per_student_limit:+$("#rwLimit").value,start_date:$("#rwStart").value,end_date:$("#rwEnd").value,active:$("#rwActive").checked};await api(x.id?`/admin/rewards/${x.id}`:"/admin/rewards",{method:x.id?"PUT":"POST",body:JSON.stringify(body)});closeModal();toast("奖品已保存");pointsAdmin()}catch(e){toast(e.message)}}}\n function bindRules(){if($("#newRule"))$("#newRule").onclick=()=>ruleForm();if($("#exportPoints"))$("#exportPoints").onclick=async()=>{try{await downloadWithAuth("/admin/points/export.xlsx","积分奖励报表.xlsx");toast("报表已导出")}catch(e){toast(e.message)}};$$(\'.editRule\').forEach(b=>b.onclick=()=>ruleForm(rules.find(x=>x.id==+b.dataset.id)))}\n function bindRewards(){if($("#newReward"))$("#newReward").onclick=()=>rewardForm();$$(\'.editReward\').forEach(b=>b.onclick=()=>rewardForm(rewards.find(x=>x.id==+b.dataset.id)))}\n function bindRedeem(){$$(\'.fulfillRed\').forEach(b=>b.onclick=async()=>{try{await api(`/rewards/redemptions/${+b.dataset.id}/handle`,{method:"POST",body:JSON.stringify({action:"fulfill",note:""})});toast("已确认发放");pointsAdmin()}catch(e){toast(e.message)}});$$(\'.rejectRed\').forEach(b=>b.onclick=async()=>{const note=prompt("填写拒绝/退回原因（可选）","")||"";try{await api(`/rewards/redemptions/${+b.dataset.id}/handle`,{method:"POST",body:JSON.stringify({action:"reject",note})});toast("已拒绝并退回积分");pointsAdmin()}catch(e){toast(e.message)}})}\n $("#page").innerHTML=head("积分奖励","积分规则、奖品库存、兑换核销与运营统计")+tabs+`<div id="pointsAdminBody"></div>`;$("#paRulesTab").onclick=()=>draw("rules");$("#paRewardsTab").onclick=()=>draw("rewards");$("#paRedeemTab").onclick=()=>draw("redeem");$("#paStatsTab").onclick=()=>draw("stats");draw("rules");\n}\n\nasync function admin(){\n const d=await api("/admin/overview");\n $("#page").innerHTML=head("平台总览","学校正式运营数据与安全状态")+\n `<div class="grid4">${stat(d.teachers,"教师")}${stat(d.activeStudents,"在读学生")}${stat(d.archivedStudents,"毕业归档")}${stat(d.parents,"家长")}</div>\n <div class="section grid4">${stat(d.classes,"班级")}${stat(d.assignments,"作业")}${stat(d.assignmentRecipients,"作业接收记录")}${stat(d.submissions,"答题提交")}</div>\n <div class="section grid2"><div class="card"><h2>账号与安全</h2><div class="grid2">${stat(d.inactiveAccounts,"停用账号")}${stat(d.lockedAccounts,"登录锁定")}</div></div><div class="card"><h2>数据留痕</h2><p class="muted">班级历史 ${d.classHistoryRecords} 条 · 作业接收快照 ${d.assignmentRecipients} 条。V7.5.0 继续完整记录调班、毕业、作业、课堂积分与奖励兑换。</p></div></div>\n <div class="section card"><h2>教材覆盖</h2><p class="muted">${esc((d.textbooks||[]).join("、")||"暂无")}</p></div>`;\n}\nasync function users(){\n const list=await api("/admin/users");\n const controls=`<div class="filters"><input id="userSearch" placeholder="搜索姓名或账号"><select id="userRole"><option value="">全部身份</option><option value="teacher">教师</option><option value="student">学生</option><option value="parent">家长</option><option value="admin">管理员</option></select><select id="userStatus"><option value="">全部状态</option><option value="active">已启用</option><option value="inactive">已停用</option><option value="archived">毕业归档</option><option value="password">待改密码</option></select></div>`;\n $("#page").innerHTML=head("账号管理","账号安全、毕业归档与恢复入班",`<button class="btn primary" id="newTeacher">＋教师</button><button class="btn secondary" id="newParent">＋家长</button>`)+controls+\n `<div class="card table-wrap desktop-only"><table class="table"><thead><tr><th>姓名</th><th>账号</th><th>身份</th><th>学籍/班级</th><th>账号</th><th>操作</th></tr></thead><tbody id="userTableBody"></tbody></table></div><div id="userCards" class="list mobile-only"></div>`;\n const pwdBadge=x=>x.mustChangePassword?`<span class="badge amber">待修改密码</span>`:`<span class="badge green">密码已设置</span>`;\n const activeBadge=x=>x.active?`<span class="badge green">已启用</span>`:`<span class="badge red">已停用</span>`;\n const lifeBadge=x=>x.role==="student"?`<span class="badge ${x.archived?"amber":""}">${esc(x.lifecycleStatus||"")}</span>`:"";\n const actions=x=>`<button class="btn secondary small resetPwd" data-id="${x.id}" data-name="${esc(x.name)}">重置密码</button>${x.role==="student"?`<button class="btn secondary small userHistory" data-id="${x.id}" data-name="${esc(x.name)}">班级历史</button>`:""}${x.archived?`<button class="btn primary small restoreStudent" data-id="${x.id}" data-name="${esc(x.name)}">恢复入班</button>`:`<button class="btn ${x.active?"danger":"secondary"} small toggleUser" data-id="${x.id}" data-active="${x.active?"1":"0"}" ${x.id===state.user?.id?"disabled":""}>${x.active?"停用":"启用"}</button>`}`;\n function bindUserActions(){\n  $$(".resetPwd").forEach(b=>b.onclick=()=>resetPasswordForm(+b.dataset.id,b.dataset.name));\n  $$(".toggleUser").forEach(b=>b.onclick=async()=>{const active=b.dataset.active==="1",id=+b.dataset.id;if(active&&!confirm("停用后该账号会立即无法继续使用，确定停用吗？"))return;try{await api(`/admin/users/${id}/active`,{method:"POST",body:JSON.stringify({active:!active})});toast(active?"账号已停用":"账号已启用");go("users")}catch(e){toast(e.message)}});\n  $$(".userHistory").forEach(b=>b.onclick=()=>showAdminHistory(+b.dataset.id,b.dataset.name));\n  $$(".restoreStudent").forEach(b=>b.onclick=()=>restoreStudentForm(+b.dataset.id,b.dataset.name));\n }\n function drawUsers(){\n  const q=$("#userSearch").value.trim().toLowerCase(),role=$("#userRole").value,status=$("#userStatus").value;\n  const rows=list.filter(x=>(!q||x.name.toLowerCase().includes(q)||x.username.toLowerCase().includes(q))&&(!role||x.role===role)&&(!status||(status==="active"&&x.active)||(status==="inactive"&&!x.active)||(status==="archived"&&x.archived)||(status==="password"&&x.mustChangePassword)));\n  $("#userTableBody").innerHTML=rows.map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.username)}</td><td>${roleName(x.role)}</td><td>${lifeBadge(x)} ${x.currentClassName?esc(x.currentClassName):""}</td><td>${activeBadge(x)} ${pwdBadge(x)} ${x.lockedUntil?`<span class="badge amber">登录锁定</span>`:""}</td><td>${actions(x)}</td></tr>`).join("")||`<tr><td colspan="6" class="muted">没有匹配账号</td></tr>`;\n  $("#userCards").innerHTML=rows.map(x=>`<div class="card account-card"><div><b>${esc(x.name)}</b><div class="muted" style="font-size:12px;margin-top:3px">${esc(x.username)} · ${roleName(x.role)}${x.currentClassName?` · ${esc(x.currentClassName)}`:""}</div></div><div class="status-line">${lifeBadge(x)}${activeBadge(x)}${pwdBadge(x)}</div><div class="account-actions">${actions(x)}</div></div>`).join("")||`<div class="card empty">没有匹配账号</div>`;bindUserActions();\n }\n $("#newTeacher").onclick=()=>userForm("teacher");$("#newParent").onclick=()=>userForm("parent");$("#userSearch").oninput=drawUsers;$("#userRole").onchange=drawUsers;$("#userStatus").onchange=drawUsers;drawUsers();\n}\nasync function showAdminHistory(id,name){\n try{const rows=await api(`/admin/students/${id}/history`);modal(`${esc(name)} · 班级历史`,rows.length?`<div class="list">${rows.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.className)}</b><small>${(x.joinedAt||"").slice(0,10)} → ${x.current?"当前":(x.leftAt||"").slice(0,10)} · ${esc(x.current?"在读":x.leaveReasonName)}</small></div></div>`).join("")}</div>`:"<div class=\'empty\'>暂无历史</div>")}catch(e){toast(e.message)}\n}\nasync function restoreStudentForm(id,name){\n try{const cs=await api("/admin/classes");if(!cs.length){toast("请先建立班级");return}modal("恢复学生入班",`<p>恢复 <b>${esc(name)}</b> 的账号，并安排到指定班级。</p><label>目标班级</label><select id="restoreClass">${cs.map(c=>`<option value="${c.id}">${esc(c.name)} · ${c.grade}年级 · ${esc(c.teacherName)}</option>`).join("")}</select><div class="note" style="margin-top:10px">恢复后旧登录令牌不会复活，学生需要重新登录。历史成绩与原班级记录保留。</div><button class="btn primary full" id="saveRestore">确认恢复</button>`);$("#saveRestore").onclick=async()=>{try{await api(`/admin/students/${id}/restore`,{method:"POST",body:JSON.stringify({class_id:+$("#restoreClass").value})});closeModal();toast("学生已恢复并重新入班");go("users")}catch(e){toast(e.message)}}}catch(e){toast(e.message)}\n}\nfunction userForm(role){\n modal(role==="teacher"?"创建教师":"创建家长",`<label>姓名</label><input id="nuName"><label>登录账号</label><input id="nuUser"><label>初始密码</label><input id="nuPass" type="password" placeholder="至少8位，包含字母和数字"><button class="btn primary full" id="saveUser">创建</button>`);\n $("#saveUser").onclick=async()=>{try{await api("/admin/users",{method:"POST",body:JSON.stringify({name:$("#nuName").value,username:$("#nuUser").value,password:$("#nuPass").value,role})});closeModal();toast("账号已创建");go("users")}catch(e){toast(e.message)}};\n}\nasync function imports(){\n const jobs=await api("/admin/import-jobs");\n $("#page").innerHTML=head("批量导入","题库、教师、学生均支持 Excel 批量导入",`<button class="btn secondary" id="downloadTemplate">下载模板</button><button class="btn primary" id="uploadXlsx">上传 XLSX</button>`)+\n `<div class="card"><div class="note">V7.4.0 可同时处理“题库导入”“教师导入”“学生导入”工作表。学生导入前请先在教师端建立对应班级。</div><details class="compact-help"><summary>查看模板填写规则</summary><p class="muted">教师/学生初始密码至少8位并包含字母和数字；学生的年级与班级必须匹配；家长账号可留空；重复账号不会覆盖原数据。</p></details><input type="file" id="xlsxFile" accept=".xlsx" class="hidden"></div>\n <div class="section"><h2>最近导入</h2><div class="list">${jobs.length?jobs.map(j=>`<div class="item"><div class="item-main"><b>${esc(j.filename)}</b><small>${esc(j.createdAt)} · ${esc(j.summary)}</small></div><span class="badge ${j.status==="成功"?"green":(j.status==="失败"?"red":"amber")}">${esc(j.status)}</span></div>`).join(""):"<div class=\'card empty\'>暂无导入记录</div>"}</div></div>`;\n $("#downloadTemplate").onclick=async()=>{try{const r=await fetch(state.api+"/admin/import-template",{headers:{Authorization:`Bearer ${state.token}`}});if(!r.ok){let d={};try{d=await r.json()}catch{};throw new Error(d.detail||"模板下载失败")}const blob=await r.blob(),url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="小学题库_V7.4.0_批量导入模板.xlsx";document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){toast(e.message)}};\n $("#uploadXlsx").onclick=()=>$("#xlsxFile").click();\n $("#xlsxFile").onchange=async()=>{\n  const f=$("#xlsxFile").files[0];if(!f)return;\n  const fd=new FormData();fd.append("file",f);\n  try{\n   const r=await fetch(state.api+"/admin/import-xlsx",{method:"POST",headers:{Authorization:`Bearer ${state.token}`},body:fd});const d=await r.json();if(!r.ok)throw new Error(d.detail||"导入失败");\n   if((d.errors||[]).length)modal("导入完成",`<div class="note">${esc(d.summary)}</div><div class="list" style="margin-top:10px">${d.errors.map(x=>`<div class="item"><small>${esc(x)}</small></div>`).join("")}</div><button class="btn primary full" id="importDone">知道了</button>`),setTimeout(()=>{$("#importDone").onclick=()=>{closeModal();go("imports")}},0);else{toast(d.summary);go("imports")}\n  }catch(e){toast(e.message)}\n };\n}\nasync function adminAudit(){\n const rows=await api("/admin/audit-logs?limit=200");\n $("#page").innerHTML=head("全校操作审计","管理员查看学校关键操作记录")+`<div class="filters"><input id="auditSearch" placeholder="搜索操作人或内容"><select id="auditType"><option value="">全部操作</option>${[...new Set(rows.map(x=>x.actionName))].map(x=>`<option>${esc(x)}</option>`).join("")}</select></div><div class="card"><div id="adminAuditList" class="list"></div></div>`;\n function draw(){const q=$("#auditSearch").value.trim().toLowerCase(),t=$("#auditType").value;const xs=rows.filter(x=>(!q||`${x.actorName} ${x.summary}`.toLowerCase().includes(q))&&(!t||x.actionName===t));$("#adminAuditList").innerHTML=xs.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.actionName)}</b><small>${esc((x.createdAt||"").slice(0,16).replace("T"," "))} · ${esc(x.actorName)} · ${esc(x.summary)}</small></div></div>`).join("")||"<div class=\'empty\'>没有匹配记录</div>"}$("#auditSearch").oninput=draw;$("#auditType").onchange=draw;draw();\n}\nasync function system(){\n $("#page").innerHTML=head("系统设置","部署、备份和客户端安装说明")+\n `<div class="grid2"><div class="card"><h2>跨平台客户端</h2><p class="muted">Web/PWA、iOS、Android、Windows、macOS、Linux 共用一套业务前端。</p></div>\n <div class="card"><h2>生产环境建议</h2><p class="muted">正式上线建议启用 HTTPS、PostgreSQL、对象存储、每日备份和学校多租户隔离。</p></div></div>\n <div class="section card"><h2>当前服务器</h2><input id="sysURL" value="${esc(state.api)}"><button class="btn secondary full" id="saveSys">保存</button></div>`;\n $("#saveSys").onclick=()=>{state.api=$("#sysURL").value.trim().replace(/\\/$/,"");localStorage.setItem("v6Server",state.api);toast("已保存")};\n}\n\n\n// V7.4 customized teaching: 2026 autumn Grade 5 Chinese + Math\nfunction splitLines(v){return String(v||"").split(/\\n+/).map(x=>x.trim()).filter(Boolean)}\nfunction teachStatus(s){return ({not_started:"未开始",active:"进行中",passed:"已达标",completed:"已完成"})[s]||s}\nfunction levelBadge(l){return l?`<span class="level-badge level-${l}">${l}层</span>`:""}\nasync function teaching(){\n const p=await api("/teaching/program"),lessons=await api("/teaching/lessons");state.teachingSubject=state.teachingSubject||"语文";\n const subject=state.teachingSubject,rows=lessons.filter(x=>x.subject===subject),qc=p.questionCounts||{};\n const lessonQ=lessons.reduce((n,l)=>n,0),stageCount=(stage)=>Object.values(qc[stage]||{}).reduce((a,o)=>a+Object.values(o||{}).reduce((x,y)=>x+y,0),0);\n $("#page").innerHTML=head("五年级定制教学",`${p.academicYear}年${p.term} · ${p.grade}年级${p.semester} · 每课时120分钟`,\n `<button class="btn secondary" id="teachSettings">教学设置</button><button class="btn secondary" id="midtermBank">期中题库</button><button class="btn secondary" id="finalBank">期末题库</button>`)+\n `<div class="card teach-hero"><h2 style="margin-top:0">${esc(p.title)}</h2><p>语文 ${p.lessonCounts?.语文||8} 课时：阅读理解 + 同步作文 + 精简PPT + 错题巩固 + 作文复盘；数学 ${p.lessonCounts?.数学||16} 课时：完整教案 + 例题 + C/B/A分层练习 + 精简PPT。</p><div class="status-line"><span class="badge">语文已发布 ${p.publishedCounts?.语文||0}/8</span><span class="badge">数学已发布 ${p.publishedCounts?.数学||0}/16</span><span class="badge">分层通过线 ${p.passThreshold}%</span><span class="badge">期中题 ${stageCount("midterm")}</span><span class="badge">期末题 ${stageCount("final")}</span></div></div>\n <div class="section subject-tabs"><button class="btn ${subject==="语文"?"active":"secondary"}" id="teachChinese">语文 8课时</button><button class="btn ${subject==="数学"?"active":"secondary"}" id="teachMath">数学 16课时</button></div>\n <div class="section list">${rows.map(l=>`<div class="card"><div style="display:flex;justify-content:space-between;gap:10px"><div><b>${esc(l.title)}</b><div class="muted" style="margin-top:4px">第${l.lessonNo}课时 · ${esc(l.unit)}</div></div><span class="badge ${l.published?"green":"amber"}">${l.published?"已发布":"未发布"}</span></div><p class="muted">${esc(l.coreTarget||"尚未配置核心目标")}</p><div class="lesson-tools"><button class="btn primary small teachEdit" data-id="${l.id}">编辑课时</button><button class="btn secondary small teachSlides" data-id="${l.id}">课堂PPT</button><button class="btn secondary small teachQ" data-id="${l.id}" data-subject="${l.subject}">分层题库</button><button class="btn secondary small teachProgress" data-id="${l.id}">学习进度</button>${l.subject==="语文"?`<button class="btn secondary small teachEssays" data-id="${l.id}">作文复盘</button>`:""}</div></div>`).join("")}</div>`;\n $("#teachChinese").onclick=()=>{state.teachingSubject="语文";teaching()};$("#teachMath").onclick=()=>{state.teachingSubject="数学";teaching()};\n $("#teachSettings").onclick=()=>teachingSettings(p);$("#midtermBank").onclick=()=>stageQuestionBank("midterm");$("#finalBank").onclick=()=>stageQuestionBank("final");\n $$(".teachEdit").forEach(b=>b.onclick=()=>editTeachingLesson(+b.dataset.id));$$(".teachSlides").forEach(b=>b.onclick=()=>presentTeachingSlides(+b.dataset.id));$$(".teachQ").forEach(b=>b.onclick=()=>lessonQuestionBank(+b.dataset.id,b.dataset.subject));$$(".teachProgress").forEach(b=>b.onclick=()=>teachingProgress(+b.dataset.id));$$(".teachEssays").forEach(b=>b.onclick=()=>teachingEssays(+b.dataset.id));\n}\nfunction teachingSettings(p){\n modal("2026秋教学设置",`<label>方案名称</label><input id="tpTitle" value="${esc(p.title)}"><div class="form-grid"><div><label>语文教材版本</label><input id="tpChinese" value="${esc(p.chineseTextbook)}"></div><div><label>数学教材版本</label><input id="tpMath" value="${esc(p.mathTextbook)}"></div></div><label>C/B/A层通过线（%）</label><input id="tpThreshold" type="number" min="1" max="100" value="${p.passThreshold}"><div class="note" style="margin-top:10px">模块已固定创建语文8课时、数学16课时；具体单元语文要素与数学知识点请按学校2026秋实际教材版本校准后发布。</div><button class="btn primary full" id="saveTeachingSettings">保存</button>`);\n $("#saveTeachingSettings").onclick=async()=>{try{await api("/teaching/program",{method:"PUT",body:JSON.stringify({title:$("#tpTitle").value,chinese_textbook:$("#tpChinese").value,math_textbook:$("#tpMath").value,pass_threshold:+$("#tpThreshold").value})});closeModal();toast("教学设置已保存");teaching()}catch(e){toast(e.message)}};\n}\nasync function editTeachingLesson(id){\n try{const l=await api(`/teaching/lessons/${id}`);modal(`${l.subject}第${l.lessonNo}课时`,`<div class="form-grid"><div><label>课时名称</label><input id="tlTitle" value="${esc(l.title)}"></div><div><label>教材单元</label><input id="tlUnit" value="${esc(l.unit)}"></div></div><label>${l.subject==="语文"?"核心知识 / 单元语文要素":"核心知识点 / 本课目标"}</label><textarea id="tlTarget">${esc(l.coreTarget)}</textarea><label>120分钟完整教案</label><textarea id="tlPlan">${esc(l.teacherPlan)}</textarea>${l.subject==="语文"?`<label>阅读理解教案</label><textarea id="tlReading">${esc(l.readingPlan)}</textarea><label>同步作文教案</label><textarea id="tlWriting">${esc(l.writingPlan)}</textarea><label>作文修改复盘训练</label><textarea id="tlEssayReview">${esc(l.essayReview)}</textarea>`:`<label>课堂例题（每行1题/1组）</label><textarea id="tlExamples">${esc((l.examples||[]).join("\\n"))}</textarea>`}<label>错题闭环 / 巩固训练</label><textarea id="tlClosure">${esc(l.closureTraining)}</textarea><label>精简版课堂PPT（每行1页）</label><textarea id="tlPpt">${esc((l.ppt||[]).join("\\n"))}</textarea><label style="display:flex;gap:8px;align-items:center"><input id="tlPublished" type="checkbox" style="width:auto" ${l.published?"checked":""}>发布给学生</label><button class="btn primary full" id="saveTeachingLesson">保存课时</button>`);\n $("#saveTeachingLesson").onclick=async()=>{try{await api(`/teaching/lessons/${id}`,{method:"PUT",body:JSON.stringify({title:$("#tlTitle").value,unit:$("#tlUnit").value,core_target:$("#tlTarget").value,teacher_plan:$("#tlPlan").value,reading_plan:$("#tlReading")?.value||null,writing_plan:$("#tlWriting")?.value||null,essay_review:$("#tlEssayReview")?.value||null,examples:$("#tlExamples")?splitLines($("#tlExamples").value):null,closure_training:$("#tlClosure").value,ppt:splitLines($("#tlPpt").value),published:$("#tlPublished").checked})});closeModal();toast("课时已保存");teaching()}catch(e){toast(e.message)}}\n }catch(e){toast(e.message)}\n}\nasync function presentTeachingSlides(id){\n try{const l=await api(`/teaching/lessons/${id}`),slides=l.ppt?.length?l.ppt:["本课PPT尚未配置"];let i=0;modal(`${esc(l.title)} · 精简PPT`,`<div id="slideView"></div><div class="actions" style="margin-top:12px"><button class="btn secondary" id="slidePrev">上一页</button><button class="btn secondary" id="slideNext">下一页</button></div>`);const draw=()=>{$("#slideView").innerHTML=`<div class="slide-view"><div><span class="badge">${i+1}/${slides.length}</span><h2>${esc(slides[i])}</h2></div></div>`};draw();$("#slidePrev").onclick=()=>{i=Math.max(0,i-1);draw()};$("#slideNext").onclick=()=>{i=Math.min(slides.length-1,i+1);draw()}}catch(e){toast(e.message)}\n}\nasync function lessonQuestionBank(id,subject){return teachingQuestionBank({lesson_id:id,stage:"lesson",subject})}\nasync function stageQuestionBank(stage){\n modal(stage==="midterm"?"期中分层题库":"期末分层题库",`<p>选择科目后管理 A/B/C 三层题目。学生正式测评从 C 层开始，不达标自动降到 B，再降到 A。</p><div class="grid2"><button class="btn primary stageSubject" data-subject="语文">语文</button><button class="btn primary stageSubject" data-subject="数学">数学</button></div>`);$$(".stageSubject").forEach(b=>b.onclick=()=>teachingQuestionBank({lesson_id:null,stage,subject:b.dataset.subject}));\n}\nasync function teachingQuestionBank(cfg){\n try{const qs=await api(`/teaching/questions?stage=${cfg.stage}&subject=${encodeURIComponent(cfg.subject)}${cfg.lesson_id?`&lesson_id=${cfg.lesson_id}`:""}`),counts={A:0,B:0,C:0};qs.forEach(q=>counts[q.level]++);modal(`${cfg.subject} · ${cfg.stage==="lesson"?"课时练习":cfg.stage==="midterm"?"期中测试":"期末测试"}`,`<div class="status-line">${["C","B","A"].map(l=>`<span class="level-badge level-${l}">${l}层 ${counts[l]}题</span>`).join("")}</div><button class="btn primary full" id="newTeachingQuestion">＋新增分层题</button><div class="list" style="margin-top:12px">${qs.map(q=>`<div class="item"><div class="item-main"><b>${levelBadge(q.level)} ${esc(q.stem)}</b><small>${esc(q.knowledge)} · 正确：${esc(q.options[q.correctIndex])}</small></div><button class="btn danger small delTeachingQ" data-id="${q.id}">删除</button></div>`).join("")||"<div class=\'empty\'>尚未配置题目</div>"}</div>`);$("#newTeachingQuestion").onclick=()=>newTeachingQuestion(cfg);$$(".delTeachingQ").forEach(b=>b.onclick=async()=>{if(!confirm("确定删除这道分层题吗？"))return;try{await api(`/teaching/questions/${b.dataset.id}`,{method:"DELETE"});teachingQuestionBank(cfg)}catch(e){toast(e.message)}})}catch(e){toast(e.message)}\n}\nfunction newTeachingQuestion(cfg){\n modal("新增A/B/C分层题",`<div class="form-grid"><div><label>层级</label><select id="tqLevel"><option>C</option><option>B</option><option>A</option></select></div><div><label>知识点</label><input id="tqKnowledge"></div></div><label>题目</label><textarea id="tqStem"></textarea>${[0,1,2,3].map((x)=>`<label>选项 ${String.fromCharCode(65+x)}</label><input id="tqO${x}">`).join("")}<label>正确答案</label><select id="tqCorrect"><option value="0">A</option><option value="1">B</option><option value="2">C</option><option value="3">D</option></select><label>解析</label><textarea id="tqExplain"></textarea><button class="btn primary full" id="saveTeachingQ">保存题目</button>`);$("#saveTeachingQ").onclick=async()=>{try{await api("/teaching/questions",{method:"POST",body:JSON.stringify({lesson_id:cfg.lesson_id||null,stage:cfg.stage,subject:cfg.subject,level:$("#tqLevel").value,knowledge:$("#tqKnowledge").value,stem:$("#tqStem").value,options:[0,1,2,3].map(i=>$("#tqO"+i).value),correct_index:+$("#tqCorrect").value,explanation:$("#tqExplain").value})});toast("题目已保存");teachingQuestionBank(cfg)}catch(e){toast(e.message)}};\n}\nasync function teachingProgress(id){try{const rows=await api(`/teaching/lessons/${id}/progress`);modal("课时学习进度",`<div class="list">${rows.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.studentName)}</b><small>${teachStatus(x.status)}${x.level?` · ${x.level}层`:""}${x.score!==null?` · ${x.score}分`:""}</small></div><span class="badge ${x.active?"green":"red"}">${x.active?"在用":"停用"}</span></div>`).join("")||"<div class=\'empty\'>暂无五年级学生</div>"}</div>`)}catch(e){toast(e.message)}}\nasync function teachingEssays(id){try{const rows=await api(`/teaching/lessons/${id}/essays`);modal("作文提交与复盘",`<div class="list">${rows.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.studentName)}</b><small>${esc(x.status)} · ${(x.updatedAt||"").slice(0,16).replace("T"," ")}</small></div><button class="btn secondary small essayReviewBtn" data-id="${x.id}">批改</button></div>`).join("")||"<div class=\'empty\'>暂无作文提交</div>"}</div>`);$$(".essayReviewBtn").forEach(b=>b.onclick=()=>reviewEssay(+b.dataset.id,rows.find(x=>x.id===+b.dataset.id),id))}catch(e){toast(e.message)}}\nfunction reviewEssay(eid,e,lid){modal(`${esc(e.studentName)} · 作文复盘`, `<label>初稿</label><div class="card">${esc(e.draft||"暂无")}</div><label>学生修改稿</label><div class="card">${esc(e.revisedDraft||"暂无")}</div><label>教师反馈</label><textarea id="essayFeedback">${esc(e.teacherFeedback||"")}</textarea><button class="btn primary full" id="saveEssayFeedback">保存反馈</button>`);$("#saveEssayFeedback").onclick=async()=>{try{await api(`/teaching/essays/${eid}/feedback`,{method:"PUT",body:JSON.stringify({teacher_feedback:$("#essayFeedback").value,status:"reviewed"})});toast("作文反馈已保存");teachingEssays(lid)}catch(err){toast(err.message)}}}\n\nasync function syncLearning(){\n const d=await api("/student/teaching/overview"),p=d.program;const groups=s=>d.lessons.filter(x=>x.subject===s);\n $("#page").innerHTML=head("同步课堂",`${p.academicYear}年${p.term} · 五年级${p.semester} · C层优先，未达标自动进入B层，再进入A层`)+\n `<div class="card teach-hero"><h2 style="margin-top:0">${esc(p.title)}</h2><p>${d.gradeMatch?"当前账号年级与方案匹配。":"当前账号为"+esc(d.studentGrade||"未设置")+"年级；此处为五年级教学方案预览/学习入口。"}</p></div>`+\n ["语文","数学"].map(s=>`<div class="section"><h2>${s}同步课时</h2><div class="list">${groups(s).map(l=>`<div class="item"><div class="item-main"><b>第${l.lessonNo}课时 · ${esc(l.title)}</b><small>${esc(l.unit)} · ${esc(l.coreTarget)}</small><div class="status-line" style="margin-top:6px">${levelBadge(l.bestLevel)}<span class="badge">${teachStatus(l.studyStatus)}</span>${l.score!==null?`<span class="badge green">${l.score}分</span>`:""}</div></div><button class="btn primary small enterSyncLesson" data-id="${l.id}" ${d.gradeMatch?"":"disabled"}>${d.gradeMatch?"进入课堂":"仅限五年级"}</button></div>`).join("")||"<div class=\'card empty\'>教师尚未发布课时</div>"}</div></div>`).join("")+\n `<div class="section"><h2>阶段性测评</h2><div class="stage-grid">${d.tests.map(t=>`<div class="card"><b>${t.subject} · ${t.stageName}</b><p class="muted">C ${t.counts.C}题 / B ${t.counts.B}题 / A ${t.counts.A}题</p><div class="status-line">${levelBadge(t.level)}<span class="badge">${teachStatus(t.status)}</span></div><button class="btn primary full startStageTest" data-stage="${t.stage}" data-subject="${t.subject}" ${d.gradeMatch&&t.available&&t.status==="not_started"?"":"disabled"}>${!d.gradeMatch?"仅限五年级":t.available?(t.status==="not_started"?"开始测评":"已完成"):"教师尚未配置"}</button></div>`).join("")}</div></div>`;\n $$(".enterSyncLesson").forEach(b=>b.onclick=()=>{state.teachingLessonID=+b.dataset.id;go("syncLesson")});$$(".startStageTest").forEach(b=>b.onclick=()=>startTeachingAdaptive({stage:b.dataset.stage,subject:b.dataset.subject}));\n}\nasync function syncLesson(){\n const id=state.teachingLessonID;if(!id){go("syncLearning");return}const l=await api(`/student/teaching/lessons/${id}`);\n $("#page").innerHTML=head(l.title,`${l.subject} · 第${l.lessonNo}课时 · ${esc(l.unit)} · ${l.durationMin}分钟`, `<button class="btn secondary" id="backSync">返回课程</button>`)+\n `<div class="card"><h2>本课目标</h2><p class="muted">${esc(l.coreTarget)}</p><button class="btn secondary" id="studentSlides">课堂PPT</button><button class="btn primary" id="startLessonAdaptive">开始C层优先挑战</button></div>`+\n `${l.subject==="数学"&&l.examples?.length?`<div class="section card"><h2>课堂例题</h2><div class="list">${l.examples.map(x=>`<div class="item"><div class="item-main">${esc(x)}</div></div>`).join("")}</div></div>`:""}`+\n `${l.closureTraining?`<div class="section card"><h2>错题闭环训练</h2><p class="teaching-timeline">${esc(l.closureTraining)}</p></div>`:""}`+\n `${l.subject==="语文"?`<div class="section card essay-box"><h2>同步作文与修改复盘</h2><div class="note">${esc(l.essayReview||"完成当堂作文后，根据老师反馈进行二次修改。")}</div><label>当堂作文初稿</label><textarea id="essayDraft">${esc(l.essay?.draft||"")}</textarea><label>修改稿</label><textarea id="essayRevised">${esc(l.essay?.revisedDraft||"")}</textarea>${l.essay?.teacherFeedback?`<div class="card" style="margin-top:10px"><b>教师反馈</b><p>${esc(l.essay.teacherFeedback)}</p></div>`:""}<button class="btn primary full" id="saveEssay">保存作文/修改稿</button></div>`:""}`;\n $("#backSync").onclick=()=>go("syncLearning");$("#studentSlides").onclick=()=>studentSlideDeck(l);$("#startLessonAdaptive").onclick=()=>startTeachingAdaptive({stage:"lesson",lesson_id:id});\n if($("#saveEssay"))$("#saveEssay").onclick=async()=>{try{await api(`/student/teaching/lessons/${id}/essay`,{method:"POST",body:JSON.stringify({draft:$("#essayDraft").value,revised_draft:$("#essayRevised").value})});toast("作文已保存");syncLesson()}catch(e){toast(e.message)}};\n}\nfunction studentSlideDeck(l){const slides=l.ppt?.length?l.ppt:["本课PPT尚未配置"];let i=0;modal(`${esc(l.title)} · 学生PPT`,`<div id="studentSlide"></div><div class="actions" style="margin-top:12px"><button class="btn secondary" id="spPrev">上一页</button><button class="btn secondary" id="spNext">下一页</button></div>`);const draw=()=>$("#studentSlide").innerHTML=`<div class="slide-view"><div><span class="badge">${i+1}/${slides.length}</span><h2>${esc(slides[i])}</h2></div></div>`;draw();$("#spPrev").onclick=()=>{i=Math.max(0,i-1);draw()};$("#spNext").onclick=()=>{i=Math.min(slides.length-1,i+1);draw()}}\nasync function startTeachingAdaptive(payload){try{const d=await api("/student/teaching/adaptive/start",{method:"POST",body:JSON.stringify(payload)});renderAdaptive(d)}catch(e){toast(e.message)}}\nfunction renderAdaptive(d){\n modal(`${d.subject} · ${d.stage==="lesson"?"分层课堂":d.stage==="midterm"?"期中测评":"期末测评"} · ${d.level}层`,`<div class="note">优先挑战C层；本方案通过线 ${d.passThreshold}%。未达标时系统自动降层，不需要学生自己选择难度。</div><div id="adaptiveQuestions">${(d.questions||[]).map((q,n)=>`<div class="adaptive-q"><b>${n+1}. ${esc(q.stem)}</b>${q.options.map((o,i)=>`<label class="adaptive-option"><input type="radio" name="teachq_${q.id}" value="${i}"><span>${String.fromCharCode(65+i)}. ${esc(o)}</span></label>`).join("")}</div>`).join("")}</div><button class="btn primary full" id="submitAdaptive">提交${d.level}层</button>`);\n $("#submitAdaptive").onclick=async()=>{const answers=[];for(const q of d.questions||[]){const x=document.querySelector(`input[name="teachq_${q.id}"]:checked`);if(!x){toast("请完成当前层全部题目");return}answers.push({question_id:q.id,selected_index:+x.value})}try{const r=await api("/student/teaching/adaptive/submit",{method:"POST",body:JSON.stringify({session_id:d.sessionID,answers})});showAdaptiveResult(r)}catch(e){toast(e.message)}};\n}\nfunction showAdaptiveResult(r){\n const review=r.review||{},next=r.nextLevel;modal("分层结果",`<div class="grid3">${stat(r.score,"本层得分")}${stat(`${r.correct}/${r.total}`,"答对")}${stat(r.submittedLevel,"完成层级")}</div><div class="section note">${r.passed?`已达到${r.submittedLevel}层要求。`:next?`${r.submittedLevel}层暂未达标，系统将自动进入${next}层。`:"已完成A层基础巩固。"}</div>${review.wrongQuestions?.length?`<div class="section card"><h2>本次错题</h2>${review.wrongQuestions.map(x=>`<p><b>${esc(x.knowledge)}</b>：${esc(x.stem)}<br><span class="muted">${esc(x.explanation||"请结合课堂方法重新订正。")}</span></p>`).join("")}</div>`:""}${review.closureTraining?`<div class="section card"><h2>专属巩固训练</h2><p>${esc(review.closureTraining)}</p></div>`:""}${next?`<button class="btn primary full" id="continueAdaptive">进入${next}层</button>`:`<button class="btn primary full" id="finishAdaptive">完成</button>`}`);\n if(next)$("#continueAdaptive").onclick=()=>renderAdaptive({sessionID:r.sessionID,stage:r.stage,subject:r.subject,lessonID:null,level:next,status:"active",passThreshold:r.passThreshold,questions:r.questions});else $("#finishAdaptive").onclick=()=>{closeModal();if(state.page==="syncLesson")syncLesson();else syncLearning()};\n}\n\nasync function childLearning(){\n const c=await api("/parent/children");if(!c.length){$("#page").innerHTML=head("孩子课程","暂无绑定学生")+empty("请联系学校绑定孩子");return}const sid=(state.childID&&c.some(x=>x.id===state.childID))?state.childID:c[0].id;state.childID=sid;const d=await api(`/parent/children/${sid}/teaching`),chooser=c.length>1?`<select id="teachingChild">${c.map(x=>`<option value="${x.id}" ${x.id===sid?"selected":""}>${esc(x.name)}</option>`).join("")}</select>`:"";\n $("#page").innerHTML=head(`${esc(d.student.name)}的同步课程`,`${d.program.academicYear}年${d.program.term} · 五年级${d.program.semester}`,chooser)+`<div class="grid2">${stat(d.lessons.filter(x=>x.status!=="not_started").length,"已开始课时")}${stat(d.lessons.filter(x=>x.status==="passed"||x.status==="completed").length,"已完成课时")}</div><div class="section"><h2>课时学习</h2><div class="list">${d.lessons.map(x=>`<div class="item"><div class="item-main"><b>${x.subject}第${x.lessonNo}课时 · ${esc(x.title)}</b><small>${teachStatus(x.status)}${x.level?` · ${x.level}层`:""}${x.score!==null?` · ${x.score}分`:""}${x.essayStatus?` · 作文${esc(x.essayStatus)}`:""}</small></div></div>`).join("")||"<div class=\'card empty\'>暂无已发布课时</div>"}</div></div><div class="section"><h2>阶段测评</h2><div class="stage-grid">${d.tests.map(t=>`<div class="card"><b>${t.subject} · ${t.stageName}</b><p class="muted">${teachStatus(t.status)}${t.level?` · ${t.level}层`:""}${t.score!==null?` · ${t.score}分`:""}</p></div>`).join("")}</div></div>`;if($("#teachingChild"))$("#teachingChild").onchange=()=>{state.childID=+$("#teachingChild").value;childLearning()};\n}\n\n// Shared catalog\nasync function catalog(){\n const qs=await api("/questions");\n $("#page").innerHTML=head("教材题库",`共 ${qs.length} 道云端题目`,state.user?.role==="teacher"||state.user?.role==="admin"?`<button class="btn primary" id="addQ">＋新增题目</button>`:"")+\n `<div class="filters"><select id="fGrade"><option value="">全部年级</option>${[1,2,3,4,5,6].map(x=>`<option value="${x}">${x}年级</option>`).join("")}</select>\n <select id="fSubject"><option value="">全部科目</option><option>数学</option><option>语文</option><option>英语</option></select>\n <select id="fBook"><option value="">全部教材</option>${[...new Set(qs.map(q=>q.textbook))].map(x=>`<option>${esc(x)}</option>`).join("")}</select>\n <input id="fSearch" placeholder="搜索知识点或题目"></div><div id="catalogList"></div>`;\n const draw=()=>{\n  const g=$("#fGrade").value,s=$("#fSubject").value,b=$("#fBook").value,k=$("#fSearch").value.trim();\n  const list=qs.filter(q=>(!g||q.grade==g)&&(!s||q.subject===s)&&(!b||q.textbook===b)&&(!k||q.text.includes(k)||q.knowledge.includes(k)||q.unit.includes(k)));\n  $("#catalogList").innerHTML=`<div class="list">${list.map(q=>`<div class="item"><div class="item-main"><b>${esc(q.text)}</b><small>${q.grade}年级 · ${esc(q.subject)} · ${esc(q.textbook)} · ${esc(q.semester)} · ${esc(q.unit)} · ${esc(q.knowledge)}</small></div><span class="badge">${esc(q.options[q.correctIndex])}</span></div>`).join("")||"<div class=\'card empty\'>暂无题目</div>"}</div>`;\n };\n ["#fGrade","#fSubject","#fBook","#fSearch"].forEach(x=>$(x).oninput=draw);draw();\n if($("#addQ"))$("#addQ").onclick=()=>questionForm();\n}\nfunction questionForm(){\n modal("新增教材题目",`<div class="form-grid">\n <div><label>年级</label><select id="qg">${[1,2,3,4,5,6].map(x=>`<option>${x}</option>`).join("")}</select></div>\n <div><label>科目</label><select id="qs"><option>数学</option><option>语文</option><option>英语</option></select></div>\n <div><label>教材版本</label><input id="qb" value="人教版"></div><div><label>学期</label><select id="qsem"><option>上册</option><option>下册</option></select></div>\n <div><label>单元</label><input id="qu" placeholder="第一单元"></div><div><label>知识点</label><input id="qk"></div>\n </div><label>题目</label><textarea id="qt"></textarea>\n <div class="form-grid">${["A","B","C","D"].map((x,i)=>`<div><label>选项${x}</label><input id="qo${i}"></div>`).join("")}</div>\n <label>正确选项</label><select id="qc"><option value="0">A</option><option value="1">B</option><option value="2">C</option><option value="3">D</option></select>\n <label>解析</label><textarea id="qe"></textarea><button class="btn primary full" id="saveQ">保存题目</button>`);\n $("#saveQ").onclick=async()=>{try{\n  await api("/questions",{method:"POST",body:JSON.stringify({grade:+$("#qg").value,subject:$("#qs").value,textbook:$("#qb").value,semester:$("#qsem").value,unit:$("#qu").value,knowledge:$("#qk").value,text:$("#qt").value,options:[0,1,2,3].map(i=>$(`#qo${i}`).value),correct_index:+$("#qc").value,explanation:$("#qe").value})});\n  closeModal();toast("题目已保存");go("catalog")\n }catch(e){toast(e.message)}};\n}\n\n// Teacher\n\nasync function classPoints(){\n $("#page").innerHTML=head("课堂积分","正在加载班级、积分规则与周报…")+`<div class="card empty">正在加载课堂积分，请稍候…</div>`;\n let classes;\n try{classes=await api("/teacher/classes")}catch(e){\n  $("#page").innerHTML=head("课堂积分","课堂积分数据暂未载入")+`<div class="card empty">班级列表加载失败：${esc(e.message||"网络异常")}<br><button id="retryClassPoints" class="btn primary" style="margin-top:14px">重新加载</button></div>`;\n  $("#retryClassPoints").onclick=classPoints;return\n }\n if(!classes.length){$("#page").innerHTML=head("课堂积分","快速记录课堂活动与守纪情况")+empty("请先创建班级");return}\n const cid=state.pointClassID&&classes.some(x=>x.id===state.pointClassID)?state.pointClassID:classes[0].id;state.pointClassID=cid;\n const timed=async(path,ms=9000)=>{\n  const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),ms);\n  try{return {ok:true,value:await api(path,{signal:ctl.signal})}}\n  catch(e){return {ok:false,error:(e?.name==="AbortError"?"请求超时，请稍后重试":(e?.message||"加载失败"))}}\n  finally{clearTimeout(timer)}\n };\n const [dataR,rulesR,recentR,redsR,weeklyR]=await Promise.all([\n  timed(`/teacher/points/classes/${cid}`),\n  timed("/points/rules?active_only=true"),\n  timed(`/teacher/points/recent?class_id=${cid}&limit=30`),\n  timed("/rewards/redemptions?status=pending&limit=80"),\n  timed(`/teacher/points/classes/${cid}/weekly?days=7`)\n ]);\n if(!dataR.ok){\n  $("#page").innerHTML=head("课堂积分","课堂积分数据暂未载入")+`<div class="card empty">学生积分数据加载失败：${esc(dataR.error)}<br><button id="retryClassPoints" class="btn primary" style="margin-top:14px">重新加载</button></div>`;\n  $("#retryClassPoints").onclick=classPoints;return\n }\n const data=dataR.value;\n const rules=rulesR.ok?rulesR.value:[];\n const recent=recentR.ok?recentR.value:[];\n const reds=redsR.ok?redsR.value:[];\n const weekly=weeklyR.ok?weeklyR.value:{\n   class:data.class,days:7,studentCount:data.students.length,\n   totals:{earned:0,net:0,activity:0,discipline:0,redemptionCount:0,redeemedPoints:0},ranking:[]\n };\n if(!state.pointRuleID||!rules.some(x=>x.id===state.pointRuleID))state.pointRuleID=rules[0]?.id||null;\n const clsChooser=`<select id="pointClassSelect" style="width:auto">${classes.map(x=>`<option value="${x.id}" ${x.id===cid?"selected":""}>${esc(x.name)}</option>`).join("")}</select>`;\n const ruleButtons=rules.map(x=>`<button class="rule-btn ${state.pointRuleID===x.id?"active":""}" data-rule="${x.id}"><b>${esc(x.name)}</b><div class="${x.points>0?"point-positive":"point-negative"}">${x.points>0?"+":""}${x.points} 分</div><small class="muted">${x.category==="activity"?"课堂活动":"守纪情况"}</small></button>`).join("")||`<div class="muted">${rulesR.ok?"管理员尚未启用积分规则":"积分规则暂未载入"}</div>`;\n const cards=data.students.map(x=>`<div class="card check-card"><input class="pointStu" type="checkbox" value="${x.id}"><div style="flex:1"><b>${esc(x.name)}</b><div class="muted" style="font-size:12px">可用 ${x.available} · 累计 ${x.earned} · 活动 ${x.activity} · 守纪 ${x.discipline}</div></div><button class="btn primary small onePoint" data-id="${x.id}">记录</button></div>`).join("")||empty("当前班级暂无在读学生");\n const weekRank=(weekly.ranking||[]).slice(0,10).map(x=>`<div class="item"><div class="item-main"><b>${x.rank}. ${esc(x.studentName)}</b><small>活动 ${x.activity} · 守纪 ${x.discipline} · 净表现 ${x.net}${x.redemptionCount?` · 兑换${x.redemptionCount}次`:""}</small></div><span class="badge green">本周 +${x.earned}</span></div>`).join("")||`<span class="muted">本周暂无积分记录</span>`;\n const loadWarnings=[\n  !rulesR.ok?`积分规则：${rulesR.error}`:"",\n  !recentR.ok?`最近记录：${recentR.error}`:"",\n  !redsR.ok?`待发放奖励：${redsR.error}`:"",\n  !weeklyR.ok?`班级周报：${weeklyR.error}`:""\n ].filter(Boolean);\n const warningHtml=loadWarnings.length?`<div class="note" style="margin-bottom:14px"><b>部分数据暂未载入</b><br>${loadWarnings.map(esc).join("<br>")}<br><button id="retryPartialPoint" class="btn secondary small" style="margin-top:8px">重新加载</button></div>`:"";\n const totals=weekly.totals||{earned:0,activity:0,discipline:0,redemptionCount:0};\n $("#page").innerHTML=head("课堂积分","批量快捷记分 + 班级周报",clsChooser)+warningHtml+`<div class="grid4">${stat(totals.earned||0,"本周获得")}${stat(totals.activity||0,"活动净分")}${stat(totals.discipline||0,"守纪净分")}${stat(totals.redemptionCount||0,"本周兑换")}</div><div class="section card"><div class="actions"><button id="selectAllPoint" class="btn secondary small">全选学生</button><button id="clearPoint" class="btn secondary small">清空选择</button><button id="exportWeekPoint" class="btn secondary small" ${weeklyR.ok?"":"disabled"}>导出本周积分周报</button></div><h2 style="margin-top:14px">1. 选择规则</h2><div class="rule-grid">${ruleButtons}</div><label>备注（扣分规则通常要求填写）</label><input id="pointNote" placeholder="例如：主动举手并完整说明解题思路"><button id="batchPoint" class="btn primary full" ${rules.length?"":"disabled"}>给选中学生批量记录</button></div><div class="section"><h2>2. 选择学生</h2><div class="list">${cards}</div></div><div class="section card"><h2>本周积极表现</h2><div class="list">${weekRank}</div></div><div class="section card"><h2>待发放奖励</h2><div class="list">${reds.filter(x=>data.students.some(s=>s.id===x.studentID)).map(x=>`<div class="item"><div class="item-main"><b>${esc(x.studentName)} · ${esc(x.rewardName)}</b><small>${x.costPoints}积分 · ${esc(x.requestedAt||"")}</small></div><div class="actions"><button class="btn primary small tFulfill" data-id="${x.id}">确认发放</button><button class="btn danger small tReject" data-id="${x.id}">拒绝退分</button></div></div>`).join("")||`<span class="muted">${redsR.ok?"暂无待发放奖励":"待发放奖励暂未载入"}</span>`}</div></div><div class="section card"><h2>最近积分记录</h2><div class="list">${recent.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.studentName)} · ${esc(x.reason)} <span class="${x.points>0?"point-positive":"point-negative"}">${x.points>0?"+":""}${x.points}</span></b><small>${esc(x.createdAt||"")} · ${esc(x.note||x.actorName||"")}</small></div>${!x.reversed&&["classroom","adjustment"].includes(x.source)?`<button class="btn secondary small undoPoint" data-id="${x.id}">撤销</button>`:`<span class="badge">${x.reversed?"已撤销":"流水"}</span>`}</div>`).join("")||`<span class="muted">${recentR.ok?"暂无记录":"最近记录暂未载入"}</span>`}</div></div>`;\n if($("#retryPartialPoint"))$("#retryPartialPoint").onclick=classPoints;\n $("#pointClassSelect").onchange=()=>{state.pointClassID=+$("#pointClassSelect").value;classPoints()};\n $$(\'.rule-btn\').forEach(b=>b.onclick=()=>{state.pointRuleID=+b.dataset.rule;classPoints()});\n async function record(ids){if(!state.pointRuleID){toast("请先选择积分规则");return}try{await api("/teacher/points/record",{method:"POST",body:JSON.stringify({student_ids:ids,class_id:cid,rule_id:state.pointRuleID,note:$("#pointNote").value})});toast(`已记录 ${ids.length} 名学生`);classPoints()}catch(e){toast(e.message)}}\n $$(\'.onePoint\').forEach(b=>b.onclick=()=>record([+b.dataset.id]));\n $("#batchPoint").onclick=()=>{const ids=$$(\'.pointStu:checked\').map(x=>+x.value);if(!ids.length){toast("请先勾选学生");return}record(ids)};\n $("#selectAllPoint").onclick=()=>$$(\'.pointStu\').forEach(x=>x.checked=true);\n $("#clearPoint").onclick=()=>$$(\'.pointStu\').forEach(x=>x.checked=false);\n $("#exportWeekPoint").onclick=async()=>{if(!weeklyR.ok){toast("周报数据暂未载入，请先重新加载");return}try{await downloadWithAuth(`/teacher/points/classes/${cid}/weekly.xlsx?days=7`,`${data.class.name}_本周课堂积分.xlsx`);toast("本周积分周报已导出")}catch(e){toast(e.message)}};\n $$(\'.undoPoint\').forEach(b=>b.onclick=async()=>{if(!confirm("确定撤销这条积分记录吗？系统会生成一条反向流水。"))return;try{await api(`/teacher/points/ledger/${+b.dataset.id}/undo`,{method:"POST",body:"{}"});toast("已撤销");classPoints()}catch(e){toast(e.message)}});\n $$(\'.tFulfill\').forEach(b=>b.onclick=async()=>{try{await api(`/rewards/redemptions/${+b.dataset.id}/handle`,{method:"POST",body:JSON.stringify({action:"fulfill",note:""})});toast("已发放");classPoints()}catch(e){toast(e.message)}});\n $$(\'.tReject\').forEach(b=>b.onclick=async()=>{const note=prompt("填写拒绝/退回原因（可选）","")||"";try{await api(`/rewards/redemptions/${+b.dataset.id}/handle`,{method:"POST",body:JSON.stringify({action:"reject",note})});toast("已退回积分");classPoints()}catch(e){toast(e.message)}});\n}\n\nasync function teacher(){\n const d=await api("/teacher/dashboard");\n $("#page").innerHTML=head("教师工作台","班级教学与学情概览")+\n `<div class="grid4">${stat(d.classes,"班级")}${stat(d.students,"学生")}${stat(d.assignments,"作业")}${stat(`${d.submissions}/${d.expectedSubmissions}`,"已交 / 应交")}</div>\n <div class="section grid2"><div class="card"><h2>班级平均分</h2><div style="font-size:42px;font-weight:900;color:var(--primary)">${d.avgScore}</div><p class="muted">整体正确率 ${d.avgAccuracy}% · 完成率 ${d.completionRate}%</p></div>\n <div class="card"><h2>薄弱知识点</h2><div class="knowledge">${(d.weakKnowledge||[]).slice(0,5).map(x=>`<div class="knowledge-row"><small>${esc(x.knowledge)}</small><div class="knowledge-meter"><i style="width:${x.accuracy}%"></i></div><b>${x.accuracy}%</b></div>`).join("")||"<span class=\'muted\'>暂无数据</span>"}</div></div></div>`;\n}\nasync function classes(){\n const list=await api("/teacher/classes");\n $("#page").innerHTML=head("班级学生","学生全生命周期、成绩报表与家长绑定",`<button class="btn primary" id="newClass">＋新建班级</button>`)+\n `<div class="list">${list.map(c=>`<div class="item"><div class="item-main"><b>${esc(c.name)}</b><small>${c.grade}年级 · ${c.studentCount}名学生</small></div><div class="actions"><button class="btn secondary small showStudents" data-id="${c.id}">学生管理</button><button class="btn secondary small classReport" data-id="${c.id}" data-name="${esc(c.name)}">班级报表</button><button class="btn primary small addStudent" data-id="${c.id}" data-grade="${c.grade}">加学生</button></div></div>`).join("")||"<div class=\'card empty\'>暂无班级</div>"}</div>`;\n $("#newClass").onclick=()=>{modal("新建班级",`<label>班级名称</label><input id="cn"><label>年级</label><select id="cg">${[1,2,3,4,5,6].map(x=>`<option>${x}</option>`).join("")}</select><button id="saveClass" class="btn primary full">保存</button>`);$("#saveClass").onclick=async()=>{try{await api("/teacher/classes",{method:"POST",body:JSON.stringify({name:$("#cn").value||"新班级",grade:+$("#cg").value})});closeModal();toast("班级已创建");go("classes")}catch(e){toast(e.message)}}};\n $$(".showStudents").forEach(b=>b.onclick=()=>studentList(+b.dataset.id));$$(".addStudent").forEach(b=>b.onclick=()=>studentForm(+b.dataset.id,+b.dataset.grade));$$(".classReport").forEach(b=>b.onclick=async()=>{try{await downloadWithAuth(`/teacher/classes/${+b.dataset.id}/report.xlsx`,`${b.dataset.name}_成绩汇总.xlsx`);toast("班级报表已导出")}catch(e){toast(e.message)}});\n}\nasync function studentList(cid){\n const [a,classes]=await Promise.all([api(`/teacher/classes/${cid}/students`),api("/teacher/classes")]);\n modal("班级学生",a.length?`<div class="note" style="margin-bottom:10px">系统会永久记录班级历程；调班后原作业按接收快照保留，不会消失。</div><div class="list">${a.map(s=>`<div class="item"><div class="item-main"><b>${esc(s.name)}</b><small>${esc(s.username)} · 家长 ${s.parentName?esc(s.parentName):"未绑定"}</small></div><div class="actions"><button class="btn secondary small studentHistory" data-id="${s.id}" data-name="${esc(s.name)}">班级历史</button><button class="btn secondary small studentReport" data-id="${s.id}" data-name="${esc(s.name)}">成绩单</button><button class="btn secondary small bindParent" data-id="${s.id}" data-name="${esc(s.name)}" data-parent="${s.parentID||""}">${s.parentName?"更换家长":"绑定家长"}</button><button class="btn secondary small moveStudent" data-id="${s.id}" data-name="${esc(s.name)}">调班</button><button type="button" class="btn danger small archiveStudent" style="flex:1 0 100%;min-height:44px" data-id="${s.id}" data-name="${esc(s.name)}">毕业归档</button></div></div>`).join("")}</div>`:"<div class=\'empty\'>暂无学生</div>");\n $$(".bindParent").forEach(b=>b.onclick=()=>parentBindForm(+b.dataset.id,b.dataset.name,cid,b.dataset.parent?+b.dataset.parent:null));\n $$(".moveStudent").forEach(b=>b.onclick=()=>transferStudentForm(+b.dataset.id,b.dataset.name,cid,classes));\n $$(".archiveStudent").forEach(b=>b.onclick=()=>archiveStudentForm(+b.dataset.id,b.dataset.name,cid));\n $$(".studentHistory").forEach(b=>b.onclick=async()=>{try{const rows=await api(`/teacher/students/${+b.dataset.id}/history`);modal(`${esc(b.dataset.name)} · 班级历史`,rows.length?`<div class="list">${rows.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.className)}</b><small>${(x.joinedAt||"").slice(0,10)} → ${x.current?"当前":(x.leftAt||"").slice(0,10)} · ${esc(x.current?"在读":x.leaveReasonName)}</small></div></div>`).join("")}</div>`:"<div class=\'empty\'>暂无历史</div>")}catch(e){toast(e.message)}});\n $$(".studentReport").forEach(b=>b.onclick=async()=>{try{await downloadWithAuth(`/teacher/students/${+b.dataset.id}/report.xlsx`,`${b.dataset.name}_个人成绩单.xlsx`);toast("学生成绩单已导出")}catch(e){toast(e.message)}});\n}\nfunction archiveStudentForm(sid,name,cid){\n modal(`${name} · 毕业归档`,`<div class="note" style="margin-bottom:12px">毕业归档后：学生账号会立即停用并退出当前班级；作业接收记录、成绩、积分、兑换记录和班级历史都会保留。家长绑定关系也会保留，便于继续查看历史记录。</div>\n <p style="line-height:1.7">确定将 <b>${esc(name)}</b> 毕业归档吗？</p>\n <div class="actions" style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px">\n   <button type="button" id="cancelArchive" class="btn secondary">取消</button>\n   <button type="button" id="confirmArchive" class="btn danger">确认毕业归档</button>\n </div>`);\n $("#cancelArchive").onclick=()=>studentList(cid);\n $("#confirmArchive").onclick=async()=>{\n   const btn=$("#confirmArchive");btn.disabled=true;btn.textContent="处理中…";\n   try{\n     await api(`/teacher/students/${sid}/archive`,{method:"POST"});\n     closeModal();toast("学生已毕业归档并停用账号");go("classes")\n   }catch(e){btn.disabled=false;btn.textContent="确认毕业归档";toast(e.message)}\n };\n}\nasync function parentBindForm(sid,name,cid,currentParentID){\n try{\n  const parents=await api("/teacher/parents");\n  if(!parents.length){toast("暂无可用家长账号，请先让管理员创建家长账号");return}\n  modal(`${name} · 家长绑定`,`<div class="note">绑定后，家长可查看该学生的学情、作业、课堂积分和奖励兑换记录。</div>\n  <label>选择家长账号</label>\n  <select id="bindParentSelect"><option value="">— 解除绑定 —</option>${parents.map(p=>`<option value="${p.id}" ${currentParentID===p.id?"selected":""}>${esc(p.name)}（${esc(p.username)}）</option>`).join("")}</select>\n  <button id="saveParentBind" class="btn primary full">保存家长绑定</button>`);\n  $("#saveParentBind").onclick=async()=>{const v=$("#bindParentSelect").value;try{await api(`/teacher/students/${sid}/parent`,{method:"POST",body:JSON.stringify({parent_id:v?+v:null})});closeModal();toast(v?"家长绑定已保存":"已解除家长绑定");studentList(cid)}catch(e){toast(e.message)}}\n }catch(e){toast(e.message)}\n}\nfunction transferStudentForm(sid,name,currentCid,classes){\n const targets=classes.filter(c=>c.id!==currentCid);\n if(!targets.length){toast("请先建立另一个目标班级");return}\n modal("学生调班",`<p>将 <b>${esc(name)}</b> 调整到：</p><label>目标班级</label><select id="targetClass">${targets.map(c=>`<option value="${c.id}">${esc(c.name)} · ${c.grade}年级</option>`).join("")}</select><div class="note" style="margin-top:10px">调班后学生年级会自动同步到目标班级，历史成绩不会删除。</div><button id="saveTransfer" class="btn primary full">确认调班</button>`);\n $("#saveTransfer").onclick=async()=>{try{await api(`/teacher/students/${sid}/transfer`,{method:"POST",body:JSON.stringify({target_class_id:+$("#targetClass").value})});closeModal();toast("调班完成");go("classes")}catch(e){toast(e.message)}};\n}\nfunction studentForm(cid,grade){\n modal("创建学生账号",`<div class="form-grid"><div><label>学生姓名</label><input id="sn"></div><div><label>学生账号</label><input id="su"></div><div><label>初始密码</label><input id="sp" type="password" placeholder="至少8位，包含字母和数字"></div><div><label>家长账号（可选）</label><input id="sparent" placeholder="已有家长登录账号"></div></div><button id="saveStudent" class="btn primary full">创建</button>`);\n $("#saveStudent").onclick=async()=>{try{await api("/teacher/students",{method:"POST",body:JSON.stringify({name:$("#sn").value,username:$("#su").value,password:$("#sp").value,grade,class_id:cid,parent_username:$("#sparent").value||null})});closeModal();toast("学生已创建");go("classes")}catch(e){toast(e.message)}};\n}\nasync function papers(){\n const [cs,as]=await Promise.all([api("/teacher/classes"),api("/teacher/assignments")]);\n $("#page").innerHTML=head("组卷与作业","作业接收快照、截止逾期和成绩报表统一管理",`<button class="btn primary" id="newAssignment">✨自动组卷</button>`)+\n `<div class="list">${as.map(a=>`<div class="item"><div class="item-main"><b>${esc(a.title)}</b><small>${esc(a.paper?.textbook||"")} · ${esc(a.paper?.unit||"综合")} · 截止 ${esc(a.dueDate)} · 已交 ${a.completedCount}/${a.studentCount} · 未交 ${a.pendingCount}</small><div class="status-line" style="margin-top:6px"><span class="badge ${a.deadlinePassed?"red":"green"}">${esc(a.deadlineStatus)}</span>${a.deadlinePassed&&a.pendingCount?`<span class="badge red">逾期未交 ${a.pendingCount}</span>`:""}</div></div><div class="actions"><button class="btn secondary small subs" data-id="${a.id}">完成情况</button><button class="btn secondary small exportAssignment" data-id="${a.id}" data-title="${esc(a.title)}">导出成绩</button></div></div>`).join("")||"<div class=\'card empty\'>暂无作业</div>"}</div>`;\n $("#newAssignment").onclick=()=>assignmentForm(cs);\n $$(".subs").forEach(b=>b.onclick=()=>submissionList(+b.dataset.id));\n $$(".exportAssignment").forEach(b=>b.onclick=async()=>{try{await downloadWithAuth(`/teacher/assignments/${+b.dataset.id}/export.xlsx`,`作业成绩_${b.dataset.title}.xlsx`);toast("成绩报表已导出")}catch(e){toast(e.message)}});\n}\nfunction assignmentForm(classes){\n if(!classes.length){toast("请先新建班级");return}\n modal("自动组卷",`<label>作业名称</label><input id="at" value="课后练习"><div class="form-grid">\n <div><label>班级</label><select id="ac">${classes.map(c=>`<option value="${c.id}" data-grade="${c.grade}" data-count="${c.studentCount||0}">${esc(c.name)} · ${c.grade}年级 · ${c.studentCount||0}人</option>`).join("")}</select></div>\n <div><label>科目</label><select id="as"><option>数学</option><option>语文</option><option>英语</option></select></div>\n <div><label>教材版本</label><input id="ab" value="人教版"></div><div><label>单元</label><input id="au" placeholder="留空=综合"></div>\n <div><label>题量</label><select id="an"><option>5</option><option>10</option><option>15</option><option>20</option></select></div><div><label>截止日期</label><input type="date" id="ad"></div>\n </div><div class="note" style="margin-top:10px">班级名称后会显示当前学生人数；系统会优先选中有学生的班级。截止日期按学校本地时间当天 23:59 计算；布置时会固定记录接收学生，之后调班或毕业也不会丢失该作业。</div><button id="saveAssignment" class="btn primary full">生成并布置</button>`);\n const firstNonEmpty=classes.find(c=>(c.studentCount||0)>0);if(firstNonEmpty)$("#ac").value=String(firstNonEmpty.id);\n $("#saveAssignment").onclick=async()=>{try{\n  const o=$("#ac").selectedOptions[0],grade=+o.dataset.grade,class_id=+o.value,studentCount=+o.dataset.count,subject=$("#as").value,textbook=$("#ab").value,unit=$("#au").value;\n  if(studentCount===0&&!confirm("当前班级暂无学生。继续布置将生成 0 名接收学生的作业，确定继续吗？"))return;\n  const params=new URLSearchParams({grade,subject});if(textbook)params.set("textbook",textbook);if(unit)params.set("unit",unit);\n  const qs=await api("/questions?"+params.toString());const ids=qs.sort(()=>Math.random()-.5).slice(0,+$("#an").value).map(q=>q.id);if(!ids.length)throw new Error("没有符合条件的题目");\n  const p=await api("/teacher/papers",{method:"POST",body:JSON.stringify({title:$("#at").value,grade,subject,textbook,unit,question_ids:ids})});\n  await api("/teacher/assignments",{method:"POST",body:JSON.stringify({title:$("#at").value,class_id,paper_id:p.id,due_date:$("#ad").value||new Date(Date.now()+7*86400000).toISOString().slice(0,10)})});\n  closeModal();toast("作业已布置");go("papers")\n }catch(e){toast(e.message)}};\n}\nasync function submissionList(id){\n const rows=await api(`/teacher/assignments/${id}/submissions`);\n const done=rows.filter(r=>r.completed).length,pending=rows.length-done,overdue=rows.filter(r=>r.statusCode==="overdue").length,late=rows.filter(r=>r.statusCode==="late_completed").length;\n modal("作业完成情况",rows.length?`<div class="note" style="margin-bottom:12px">已完成 ${done} 人 · 未完成 ${pending} 人${overdue?` · 逾期未交 ${overdue} 人`:""}${late?` · 逾期完成 ${late} 人`:""} <button class="btn secondary small" id="modalExport" style="margin-left:8px">导出成绩</button></div><div class="table-wrap"><table class="table"><thead><tr><th>学生</th><th>状态</th><th>分数</th><th>正确</th><th>提交时间</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.studentName)}</td><td><span class="badge ${statusClass(r.statusCode)}">${r.status}</span></td><td>${r.completed?`<b>${r.score}</b>`:"—"}</td><td>${r.completed?`${r.correct}/${r.total}`:"—"}</td><td>${r.submittedAt?esc(r.submittedAt.slice(0,16).replace("T"," ")):"—"}</td></tr>`).join("")}</tbody></table></div>`:"<div class=\'empty\'>班级暂无学生</div>");\n if($("#modalExport"))$("#modalExport").onclick=async()=>{try{await downloadWithAuth(`/teacher/assignments/${id}/export.xlsx`,`作业成绩_${id}.xlsx`);toast("成绩报表已导出")}catch(e){toast(e.message)}};\n}\nasync function analytics(){\n const d=await api("/teacher/analytics");\n $("#page").innerHTML=head("学情分析","班级平均分、知识点正确率与薄弱学生")+\n `<div class="grid4">${stat(d.avgScore,"平均分")}${stat(d.avgAccuracy+"%","正确率")}${stat(d.completionRate+"%","作业完成率")}${stat(d.pendingSubmissions,"未交份数")}</div>\n <div class="section card"><h2>班级表现</h2>${d.classStats.length?`<div class="table-wrap"><table class="table"><thead><tr><th>班级</th><th>平均分</th><th>正确率</th><th>完成率</th><th>未交</th></tr></thead><tbody>${d.classStats.map(c=>`<tr><td><b>${esc(c.className)}</b><br><small class="muted">${c.grade}年级 · ${c.students}人 · ${c.assignments}份作业</small></td><td>${c.avgScore}</td><td>${c.accuracy}%</td><td>${c.completionRate}%</td><td>${c.pendingSubmissions}</td></tr>`).join("")}</tbody></table></div>`:"<span class=\'muted\'>暂无班级作业数据</span>"}</div>\n <div class="section grid2"><div class="card"><h2>知识点正确率</h2><div class="knowledge">${d.knowledge.map(k=>`<div class="knowledge-row"><small>${esc(k.knowledge)}</small><div class="knowledge-meter"><i style="width:${k.accuracy}%"></i></div><b>${k.accuracy}%</b></div>`).join("")||"<span class=\'muted\'>暂无答题数据</span>"}</div></div>\n <div class="card"><h2>薄弱学生</h2><div class="list">${d.weakStudents.map(s=>`<div class="item"><div class="item-main"><b>${esc(s.studentName)}</b><small>${esc(s.className)} · 平均 ${s.avgScore}分 · 已交 ${s.completed}/${s.assigned}</small></div><span class="badge ${s.pending?"red":""}">${s.pending?`未交${s.pending}`:`${s.avgScore}分`}</span></div>`).join("")||"<span class=\'muted\'>暂无需要重点关注的学生</span>"}</div></div></div>`;\n}\nasync function audit(){\n const rows=await api("/teacher/audit-logs?limit=200");\n $("#page").innerHTML=head("操作记录","中文可读的关键教学管理操作")+`<div class="filters"><input id="teacherAuditSearch" placeholder="搜索操作内容"><select id="teacherAuditType"><option value="">全部类型</option>${[...new Set(rows.map(x=>x.actionName))].map(x=>`<option>${esc(x)}</option>`).join("")}</select></div><div class="card"><div class="list" id="teacherAuditList"></div></div>`;\n function draw(){const q=$("#teacherAuditSearch").value.trim().toLowerCase(),t=$("#teacherAuditType").value;const xs=rows.filter(x=>(!q||(x.summary||"").toLowerCase().includes(q))&&(!t||x.actionName===t));$("#teacherAuditList").innerHTML=xs.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.actionName||x.action)}</b><small>${esc((x.createdAt||"").slice(0,16).replace("T"," "))} · ${esc(x.summary||x.detail||"")}</small></div></div>`).join("")||"<div class=\'empty\'>没有匹配记录</div>"}$("#teacherAuditSearch").oninput=draw;$("#teacherAuditType").onchange=draw;draw();\n}\nasync function leaderboard(){\n const rows=await api("/leaderboard");\n $("#page").innerHTML=head("班级排行榜","按最近累计答题成绩计算")+\n `<div class="card table-wrap"><table class="table"><thead><tr><th>排名</th><th>学生</th><th>班级</th><th>平均分</th><th>提交次数</th></tr></thead><tbody>${rows.map((r,i)=>`<tr><td class="${i===0?"rank1":""}">${i+1}</td><td>${esc(r.studentName)}</td><td>${esc(r.className)}</td><td><b>${r.avgScore}</b></td><td>${r.submissions}</td></tr>`).join("")}</tbody></table></div>`;\n}\n\n// Student\nasync function student(){\n const [as,p]=await Promise.all([api("/student/assignments"),api("/student/progress")]);\n const pending=as.filter(a=>!a.completed),overdue=pending.filter(a=>a.statusCode==="overdue").length;\n $("#page").innerHTML=head("学习首页",`${esc(state.user.name)}，今天继续加油`)+\n `<div class="hero"><h2>今日学习</h2><p>完成老师布置的作业，并针对薄弱知识点进行专项练习。</p><button id="goPractice" class="btn secondary">开始自主练习</button></div>\n <div class="section grid4">${stat(pending.length,"待完成")}${stat(overdue,"逾期未交")}${stat(p.avgScore,"平均分")}${stat(p.totalAnswered,"累计答题")}</div>\n <div class="section"><h2>待完成作业</h2><div class="list">${pending.map(a=>`<div class="item"><div class="item-main"><b>${esc(a.title)}</b><small>${esc(a.paper?.subject||"")} · 截止 ${esc(a.dueDate)}</small></div><div class="actions"><span class="badge ${statusClass(a.statusCode)}">${a.status}</span><button class="btn primary small doA" data-id="${a.id}">${a.overdue?"补交":"开始"}</button></div></div>`).join("")||"<div class=\'card empty\'>当前没有待完成作业</div>"}</div></div>`;\n $("#goPractice").onclick=()=>go("practice");$$(".doA").forEach(b=>b.onclick=()=>startAssignment(+b.dataset.id));\n}\n\nasync function rewards(){\n const [shop,p]=await Promise.all([api("/student/rewards"),api("/student/points")]);const s=shop.summary;\n const w=p.weekly||{}; $("#page").innerHTML=head("积分奖励","课堂表现积分与奖励兑换；兑换不会减少累计获得积分")+`<div class="grid4">${stat(s.available,"可用积分")}${stat(s.earned,"累计获得")}${stat(s.activity,"课堂活动")}${stat(s.discipline,"守纪积分")}</div><div class="section card"><h2>我的本周表现</h2><div class="grid4">${stat(w.earned||0,"本周获得")}${stat(w.net||0,"本周净表现")}${stat(w.activity||0,"本周活动")}${stat(w.discipline||0,"本周守纪")}</div></div><div class="section"><h2>奖励商城</h2><div class="reward-grid">${shop.rewards.map(x=>`<div class="card reward-card"><div class="reward-icon">${esc(x.icon)}</div><h2>${esc(x.name)}</h2><p class="muted">${esc(x.description||"")}</p><div class="status-line"><span class="badge">${x.costPoints}积分</span><span class="badge">${x.unlimitedStock?"不限库存":"剩余 "+x.stock}</span>${x.perStudentLimit?`<span class="badge">限兑 ${x.perStudentLimit} 次</span>`:""}</div><button class="btn ${x.available&&s.available>=x.costPoints?"primary":"secondary"} full redeemReward" data-id="${x.id}" data-name="${esc(x.name)}" data-cost="${x.costPoints}" ${x.available&&s.available>=x.costPoints?"":"disabled"}>${!x.available?"暂不可兑":s.available<x.costPoints?"积分不足":"兑换"}</button></div>`).join("")||empty("管理员尚未上架奖品")}</div></div><div class="section card"><h2>我的兑换</h2><div class="list">${p.redemptions.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.icon)} ${esc(x.rewardName)}</b><small>${x.costPoints}积分 · ${esc(x.requestedAt||"")}</small></div><span class="badge ${x.status==="fulfilled"?"green":x.status==="rejected"?"red":"amber"}">${x.status==="pending"?"待领取":x.status==="fulfilled"?"已领取":"已退回"}</span></div>`).join("")||`<span class="muted">暂无兑换记录</span>`}</div></div><div class="section card"><h2>积分流水</h2><div class="list">${p.ledger.slice(0,40).map(x=>`<div class="item ledger-row"><div><b>${esc(x.reason||"积分记录")}</b><small>${esc(x.createdAt||"")} ${x.note?"· "+esc(x.note):""}</small></div><b class="${x.points>0?"point-positive":"point-negative"}">${x.points>0?"+":""}${x.points}</b></div>`).join("")||`<span class="muted">暂无积分记录</span>`}</div></div>`;\n $$(\'.redeemReward\').forEach(b=>b.onclick=async()=>{const name=b.dataset.name,cost=+b.dataset.cost;if(!confirm(`确定用 ${cost} 积分兑换“${name}”吗？兑换后进入待领取状态。`))return;try{await api(`/student/rewards/${+b.dataset.id}/redeem`,{method:"POST",body:JSON.stringify({note:""})});toast("兑换成功，请等待领取");rewards()}catch(e){toast(e.message)}});\n}\n\nasync function assignments(){\n const as=await api("/student/assignments");\n $("#page").innerHTML=head("我的作业","正式作业由服务器判分；逾期后仍可补交并保留逾期标记")+\n `<div class="list">${as.map(a=>`<div class="item"><div class="item-main"><b>${esc(a.title)}</b><small>${esc(a.assignedClassName||"")} · ${esc(a.paper?.textbook||"")} · ${esc(a.paper?.unit||"综合")} · 截止 ${esc(a.dueDate)}${a.completed?` · 成绩 ${a.score}分`:""}</small></div><div class="actions"><span class="badge ${statusClass(a.statusCode)}">${a.status}</span>${a.completed?`<button class="btn secondary small" disabled>已提交</button>`:`<button class="btn primary small doA" data-id="${a.id}">${a.overdue?"补交":"开始答题"}</button>`}</div></div>`).join("")||"<div class=\'card empty\'>暂无作业</div>"}</div>`;\n $$(".doA").forEach(b=>b.onclick=()=>startAssignment(+b.dataset.id));\n}\nasync function practice(){\n const qs=state.offline?offlineBank:await api("/questions");\n $("#page").innerHTML=head(state.offline?"离线练习":"自主练习","按教材和知识点选择练习内容")+\n `<div class="card"><div class="form-grid">\n <div><label>年级</label><select id="pg">${[1,2,3,4,5,6].map(x=>`<option ${x==3?"selected":""}>${x}</option>`).join("")}</select></div>\n <div><label>科目</label><select id="ps"><option>数学</option><option>语文</option><option>英语</option></select></div>\n <div><label>教材</label><select id="pb"><option value="">全部</option>${[...new Set(qs.map(q=>q.textbook))].map(x=>`<option>${esc(x)}</option>`).join("")}</select></div>\n <div><label>题量</label><select id="pn"><option>5</option><option>10</option><option>15</option></select></div>\n </div><button class="btn primary full" id="startP">开始练习</button></div>`;\n $("#startP").onclick=()=>{\n  const g=+$("#pg").value,s=$("#ps").value,b=$("#pb").value,n=+$("#pn").value;\n  let list=qs.filter(q=>q.grade===g&&q.subject===s&&(!b||q.textbook===b));if(!list.length&&state.offline)list=qs;\n  startQuiz(list.sort(()=>Math.random()-.5).slice(0,n),`${g}年级${s}练习`,null);\n };\n}\nasync function startAssignment(id){\n const as=await api("/student/assignments"),a=as.find(x=>x.id===id);if(!a)return;\n const qs=await api(`/papers/${a.paperID}/questions`);startQuiz(qs,a.title,id)\n}\nfunction startQuiz(qs,title,aid){\n if(!qs.length){toast("没有可用题目");return}\n let i=0,sel=null,done=false,correct=0,answers=[];\n const onlineServerGraded=!state.offline;\n const render=()=>{\n  const q=qs[i];\n  $("#page").innerHTML=head(title,`第 ${i+1}/${qs.length} 题${onlineServerGraded?" · 服务器判分":""}`,`<button class="btn secondary" id="quitQuiz">退出</button>`)+\n  `<div class="card"><div class="progress"><i style="width:${pct(i+(done?1:0),qs.length)}%"></i></div>\n  <div style="margin-top:12px"><span class="badge">${esc(q.textbook)} · ${esc(q.unit)} · ${esc(q.knowledge)}</span></div>\n  <div class="question">${esc(q.text)}</div>\n  ${q.options.map((o,n)=>`<button class="option ${sel===n?"selected":""} ${!onlineServerGraded&&done&&n===q.correctIndex?"correct":""} ${!onlineServerGraded&&done&&sel===n&&n!==q.correctIndex?"wrong":""}" data-i="${n}"><span class="letter">${String.fromCharCode(65+n)}</span>${esc(o)}</button>`).join("")}\n  ${!onlineServerGraded&&done?`<div class="answer"><b>${sel===q.correctIndex?"✅ 正确":"❌ 错误"}</b><br>正确答案：${esc(q.options[q.correctIndex])}<br><span class="muted">${esc(q.explanation)}</span></div>`:""}\n  ${onlineServerGraded&&aid?`<div class="note">正式作业不会在提交前显示正确答案或解析。</div>`:""}\n  <button id="quizNext" class="btn primary full" ${sel===null&&!done?"disabled":""}>${onlineServerGraded?(i===qs.length-1?"提交整份答卷":"保存并下一题"):(done?(i===qs.length-1?"完成练习":"下一题"):"提交答案")}</button></div>`;\n  $("#quitQuiz").onclick=()=>go(aid?"assignments":"practice");\n  $$(".option").forEach(b=>b.onclick=()=>{if(done&&!onlineServerGraded)return;sel=+b.dataset.i;render()});\n  $("#quizNext").onclick=async()=>{\n   if(onlineServerGraded){\n    answers.push({question_id:q.id,selected_index:sel});\n    if(i<qs.length-1){i++;sel=null;render();return}\n    try{\n     const r=aid?await api(`/student/assignments/${aid}/submit`,{method:"POST",body:JSON.stringify({answers})}):await api("/student/practice-submit",{method:"POST",body:JSON.stringify({title,answers})});\n     $("#page").innerHTML=head(aid?"作业已提交":"练习完成",title)+`<div class="card empty"><div style="font-size:62px">🏆</div><h1 style="color:var(--primary)">${r.score}分</h1><p>答对 ${r.correct} 题，答错 ${r.total-r.correct} 题</p>${aid?"<p class=\'muted\'>成绩已回传教师端。</p>":""}<button id="backQuiz" class="btn primary">返回</button></div>`;\n     $("#backQuiz").onclick=()=>go(aid?"assignments":"practice");\n    }catch(e){answers.pop();toast(e.message)}\n    return\n   }\n   if(!done){done=true;const ok=sel===q.correctIndex;if(ok)correct++;answers.push({question_id:q.id,selected_index:sel,correct:ok});render();return}\n   if(i<qs.length-1){i++;sel=null;done=false;render();return}\n   const score=pct(correct,qs.length);\n   $("#page").innerHTML=head("练习完成",title)+`<div class="card empty"><div style="font-size:62px">🏆</div><h1 style="color:var(--primary)">${score}分</h1><p>答对 ${correct} 题，答错 ${qs.length-correct} 题</p><button id="backQuiz" class="btn primary">返回</button></div>`;\n   $("#backQuiz").onclick=()=>go("practice")\n  };\n };render()\n}\nasync function progress(){\n const p=await api("/student/progress");\n $("#page").innerHTML=head("我的学情","查看成绩趋势和薄弱知识点")+\n `<div class="grid3">${stat(p.avgScore,"平均分")}${stat(p.totalAnswered,"累计答题")}${stat(p.submissions,"练习次数")}</div>\n <div class="section card"><h2>知识点掌握</h2><div class="knowledge">${p.knowledge.map(k=>`<div class="knowledge-row"><small>${esc(k.knowledge)}</small><div class="knowledge-meter"><i style="width:${k.accuracy}%"></i></div><b>${k.accuracy}%</b></div>`).join("")||"<span class=\'muted\'>暂无数据</span>"}</div></div>\n <div class="section"><button id="goRewardsFromProgress" class="btn secondary full">查看课堂积分与奖励</button></div>`;\n if($("#goRewardsFromProgress"))$("#goRewardsFromProgress").onclick=()=>go("rewards");\n}\n\n// Parent\nasync function parent(){\n const c=await api("/parent/children");\n $("#page").innerHTML=head("家长首页","查看孩子成绩、待完成和逾期作业")+\n `<div class="list">${c.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.name)}</b><small>${x.grade}年级 · ${esc(x.className||"未分班")} · 平均 ${x.avgScore}分</small><div class="status-line" style="margin-top:6px"><span class="badge">${x.pendingAssignments}份待完成</span>${x.overdueAssignments?`<span class="badge red">${x.overdueAssignments}份逾期</span>`:""}</div></div><div class="actions"><button class="btn secondary small parentProgressBtn" data-id="${x.id}">学情</button><button class="btn primary small parentAssignmentsBtn" data-id="${x.id}">作业</button></div></div>`).join("")||"<div class=\'card empty\'>尚未绑定孩子</div>"}</div>`;\n $$(".parentProgressBtn").forEach(b=>b.onclick=()=>{state.childID=+b.dataset.id;go("childProgress")});\n $$(".parentAssignmentsBtn").forEach(b=>b.onclick=()=>{state.childID=+b.dataset.id;go("childAssignments")});\n}\n\nasync function childRewards(){\n const c=await api("/parent/children");if(!c.length){$("#page").innerHTML=head("课堂表现","暂无绑定学生")+empty("请联系教师或管理员绑定家长账号");return}\n const cid=(state.childID&&c.some(x=>x.id===state.childID))?state.childID:c[0].id;state.childID=cid;const d=await api(`/parent/children/${cid}/points`);const s=d.summary,w=d.weekly||{};\n const chooser=c.length>1?`<select id="parentPointChild" style="width:auto">${c.map(x=>`<option value="${x.id}" ${x.id===cid?"selected":""}>${esc(x.name)}</option>`).join("")}</select>`:"";\n const reasons=(w.topReasons||[]).map(x=>`<div class="item"><div><b>${esc(x.reason)}</b><small>${x.count}次</small></div><b class="${x.points>=0?"point-positive":"point-negative"}">${x.points>0?"+":""}${x.points}</b></div>`).join("")||`<span class="muted">本周暂无课堂积分记录</span>`;\n $("#page").innerHTML=head(`${esc(d.student.name)}的课堂表现`,"课堂积分、每周表现与奖励兑换",chooser)+`<div class="grid4">${stat(s.available,"可用积分")}${stat(s.earned,"累计获得")}${stat(s.activity,"课堂活动")}${stat(s.discipline,"守纪积分")}</div><div class="section card"><h2>近7天课堂周报</h2><div class="grid4">${stat(w.earned||0,"本周获得")}${stat(w.net||0,"净表现")}${stat(w.activity||0,"活动积分")}${stat(w.discipline||0,"守纪积分")}</div><div class="section"><h2>主要表现</h2><div class="list">${reasons}</div></div><p class="muted">本周兑换 ${w.redemptionCount||0} 次 · 使用 ${w.redeemedPoints||0} 积分</p></div><div class="section card"><h2>最近课堂表现</h2><div class="list">${d.ledger.slice(0,50).map(x=>`<div class="item ledger-row"><div><b>${esc(x.reason||"积分记录")}</b><small>${esc(x.createdAt||"")} ${x.note?"· "+esc(x.note):""}</small></div><b class="${x.points>0?"point-positive":"point-negative"}">${x.points>0?"+":""}${x.points}</b></div>`).join("")||`<span class="muted">暂无积分记录</span>`}</div></div><div class="section card"><h2>奖励兑换</h2><div class="list">${d.redemptions.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.icon)} ${esc(x.rewardName)}</b><small>${x.costPoints}积分 · ${esc(x.requestedAt||"")}</small></div><span class="badge ${x.status==="fulfilled"?"green":x.status==="rejected"?"red":"amber"}">${x.status==="pending"?"待领取":x.status==="fulfilled"?"已领取":"已退回"}</span></div>`).join("")||`<span class="muted">暂无兑换记录</span>`}</div></div>`;\n if($("#parentPointChild"))$("#parentPointChild").onchange=()=>{state.childID=+$("#parentPointChild").value;childRewards()}\n}\n\nasync function childProgress(){\n const c=await api("/parent/children");\n if(!c.length){$("#page").innerHTML=head("孩子学情","暂无绑定学生")+empty("请联系教师或管理员绑定家长账号");return}\n const cid=(state.childID&&c.some(x=>x.id===state.childID))?state.childID:c[0].id;state.childID=cid;\n const p=await api(`/parent/children/${cid}/progress`);\n const chooser=c.length>1?`<select id="parentChildSelect" style="width:auto">${c.map(x=>`<option value="${x.id}" ${x.id===cid?"selected":""}>${esc(x.name)}</option>`).join("")}</select>`:"";\n $("#page").innerHTML=head(`${esc(p.studentName)}的学情`,`${p.grade}年级 · ${esc(p.className||"未分班")} · 最近学习概况`,chooser)+\n `<div class="grid3">${stat(p.avgScore,"平均分")}${stat(p.totalAnswered,"累计答题")}${stat(p.submissions,"练习次数")}</div>\n <div class="section card"><h2>薄弱知识点</h2><div class="knowledge">${p.knowledge.map(k=>`<div class="knowledge-row"><small>${esc(k.knowledge)}</small><div class="knowledge-meter"><i style="width:${k.accuracy}%"></i></div><b>${k.accuracy}%</b></div>`).join("")||"<span class=\'muted\'>暂无数据</span>"}</div></div>\n <div class="section card"><h2>班级历程</h2><div class="list">${(p.classHistory||[]).map(x=>`<div class="item"><div class="item-main"><b>${esc(x.className)}</b><small>${(x.joinedAt||"").slice(0,10)} → ${x.current?"当前":(x.leftAt||"").slice(0,10)} · ${esc(x.current?"在读":x.leaveReasonName)}</small></div></div>`).join("")||"<span class=\'muted\'>暂无班级历史</span>"}</div></div>`;\n if($("#parentChildSelect"))$("#parentChildSelect").onchange=()=>{state.childID=+$("#parentChildSelect").value;childProgress()};\n}\nasync function childAssignments(){\n const c=await api("/parent/children");\n if(!c.length){$("#page").innerHTML=head("孩子作业","暂无绑定学生")+empty("请联系教师或管理员绑定家长账号");return}\n const cid=(state.childID&&c.some(x=>x.id===state.childID))?state.childID:c[0].id;state.childID=cid;\n const child=c.find(x=>x.id===cid),rows=await api(`/parent/children/${cid}/assignments`);\n const chooser=c.length>1?`<select id="parentAssignmentChild" style="width:auto">${c.map(x=>`<option value="${x.id}" ${x.id===cid?"selected":""}>${esc(x.name)}</option>`).join("")}</select>`:"";\n $("#page").innerHTML=head(`${esc(child?.name||"孩子")}的作业`,"只读查看作业完成与逾期状态",chooser)+\n `<div class="list">${rows.map(a=>`<div class="item"><div class="item-main"><b>${esc(a.title)}</b><small>${esc(a.assignedClassName||"")} · ${esc(a.subject||"")} · 截止 ${esc(a.dueDate)}${a.score!==null?` · ${a.score}分`:""}</small></div><span class="badge ${statusClass(a.statusCode)}">${a.status}</span></div>`).join("")||"<div class=\'card empty\'>暂无作业</div>"}</div>`;\n if($("#parentAssignmentChild"))$("#parentAssignmentChild").onchange=()=>{state.childID=+$("#parentAssignmentChild").value;childAssignments()};\n}\nasync function account(){\n $("#page").innerHTML=head("我的","账号与客户端设置")+\n `<div class="grid2"><div class="card"><h2>${esc(state.user?.name||"离线学生")}</h2><p class="muted">${state.offline?"离线体验":roleName(state.user?.role)}</p></div>\n <div class="card"><h2>服务器</h2><input id="accountURL" value="${esc(state.api)}" ${state.offline?"disabled":""}><button id="saveURL" class="btn secondary full" ${state.offline?"disabled":""}>保存</button></div></div>\n <div class="section card"><h2>修改密码</h2>\n <label>当前密码</label><input id="oldPwd" type="password">\n <label>新密码</label><input id="newPwd" type="password" placeholder="至少8位，包含字母和数字">\n <label>确认新密码</label><input id="newPwd2" type="password">\n <button id="changePwdBtn" class="btn primary full">修改密码</button></div>\n <div class="section card"><h2>登录会话</h2><p class="muted">${state.offline?"离线模式":(state.remember?"个人设备：保持登录约30天":"共享设备模式：仅当前浏览器会话")}</p>${state.offline?"":`<button id="accountLogoutBtn" class="btn secondary full">退出登录</button>`}</div>\n <div class="section note">iPhone/iPad：Safari → 分享 → 添加到主屏幕；Android/Windows：Chrome/Edge → 安装应用。</div>`;\n if($("#saveURL"))$("#saveURL").onclick=()=>{state.api=$("#accountURL").value.trim().replace(/\\/$/,"");localStorage.setItem("v6Server",state.api);toast("已保存")};\n if($("#accountLogoutBtn"))$("#accountLogoutBtn").onclick=logout;\n if($("#changePwdBtn"))$("#changePwdBtn").onclick=async()=>{\n   const old=$("#oldPwd").value,n=$("#newPwd").value,n2=$("#newPwd2").value;\n   if(n!==n2){toast("两次新密码不一致");return}\n   try{const r=await api("/change-password",{method:"POST",body:JSON.stringify({current_password:old,new_password:n,remember:state.remember})});if(r.token){state.token=r.token;saveAuth()}toast("密码修改成功");$("#oldPwd").value=$("#newPwd").value=$("#newPwd2").value=""}\n   catch(e){toast(e.message)}\n };\n}\n\n\nfunction passwordOK(p){return p.length>=8 && /[A-Za-z]/.test(p) && /\\d/.test(p)}\nasync function forcePassword(){\n $("#page").innerHTML=head("首次登录安全设置","请先把初始密码修改成你自己的密码")+\n `<div class="card" style="max-width:620px;margin:auto">\n   <div class="note">新密码至少 8 位，并同时包含字母和数字。修改完成后才能进入系统。</div>\n   <label>当前初始密码</label><input id="fpOld" type="password">\n   <label>新密码</label><input id="fpNew" type="password" placeholder="例如 School2026!">\n   <label>再次输入新密码</label><input id="fpNew2" type="password">\n   <button id="fpSave" class="btn primary full">保存新密码并进入系统</button>\n </div>`;\n $("#fpSave").onclick=async()=>{\n   const old=$("#fpOld").value,n=$("#fpNew").value,n2=$("#fpNew2").value;\n   if(n!==n2){toast("两次新密码不一致");return}\n   if(!passwordOK(n)){toast("新密码至少8位，并同时包含字母和数字");return}\n   try{\n     const r=await api("/change-password",{method:"POST",body:JSON.stringify({current_password:old,new_password:n,remember:state.remember})});\n     if(r.token)state.token=r.token;\n     state.user.mustChangePassword=false;\n     saveAuth();\n     toast("密码修改成功");\n     go(({admin:"admin",teacher:"teacher",student:"student",parent:"parent"})[state.user.role]||"account");\n   }catch(e){toast(e.message)}\n };\n}\nfunction resetPasswordForm(id,name){\n modal("重置密码",`<p>为 <b>${esc(name)}</b> 设置临时密码。用户下次登录必须修改。</p>\n <label>临时密码</label><input id="tempPwd" type="password" placeholder="至少8位，包含字母和数字">\n <button id="saveResetPwd" class="btn primary full">确认重置</button>`);\n $("#saveResetPwd").onclick=async()=>{\n   try{\n     await api(`/admin/users/${id}/reset-password`,{method:"POST",body:JSON.stringify({new_password:$("#tempPwd").value})});\n     closeModal();toast("密码已重置，状态已改为待修改");go("users");\n   }catch(e){toast(e.message)}\n };\n}\n\nasync function validateSavedSession(){\n if(!state.token||!state.user)return false;\n const overlay=$("#sessionCheck");overlay.classList.remove("hidden");\n try{\n   const r=await fetch(state.api+"/session",{headers:{"Authorization":`Bearer ${state.token}`}});\n   let d={};try{d=await r.json()}catch{}\n   if(!r.ok)throw new Error(d.detail||"登录已过期");\n   state.user={id:d.userID,name:d.name,role:d.role,grade:d.grade,mustChangePassword:!!d.mustChangePassword};\n   saveAuth();enter();return true;\n }catch(e){\n   clearAuth();$("#shell").classList.add("hidden");$("#loginScreen").classList.remove("hidden");\n   toast("登录已过期，请重新登录");return false;\n }finally{overlay.classList.add("hidden");}\n}\nasync function bootApp(){\n $("#serverURL").value=state.api;$("#rememberLogin").checked=state.remember;\n if(state.token&&state.user)await validateSavedSession();\n}\n\n$("#serverURL").value=state.api;\n$("#loginBtn").onclick=login;\n$("#showPwd").onchange=()=>$("#password").type=$("#showPwd").checked?"text":"password";\n$("#offlineBtn").onclick=()=>{state.offline=true;state.user={name:"离线学生",role:"student"};enter()};\n$("#logoutBtn").onclick=logout;\n$("#menuBtn").onclick=()=>$("#sidebar").classList.toggle("open");\n$("#modalClose").onclick=closeModal;\nif("serviceWorker" in navigator)window.addEventListener("load",async()=>{\n try{await navigator.serviceWorker.register("/sw.js?v=762",{updateViaCache:"none"});}catch(_){}\n});\nbootApp();\n\n</script>\n</body>\n</html>\n'
MANIFEST = '{\n  "name": "小学题库 V7.6.2 运营周报稳定修正版",\n  "short_name": "小学题库",\n  "start_url": "./",\n  "scope": "./",\n  "display": "standalone",\n  "background_color": "#f4f6fb",\n  "theme_color": "#5362e8",\n  "lang": "zh-CN",\n  "icons": [\n    {\n      "src": "icon.svg",\n      "sizes": "any",\n      "type": "image/svg+xml",\n      "purpose": "any maskable"\n    }\n  ]\n}'
ICON_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">\n<rect width="512" height="512" rx="112" fill="#5362e8"/>\n<path fill="#fff" d="M100 126c66-20 116-6 156 29v252c-41-30-92-40-156-21V126zm312 0c-66-20-116-6-156 29v252c41-30 92-40 156-21V126z"/>\n</svg>'
SERVICE_WORKER = 'const VERSION="v762-frontend-restore-1";\nself.addEventListener("install",event=>{self.skipWaiting();});\nself.addEventListener("activate",event=>{event.waitUntil((async()=>{const keys=await caches.keys();await Promise.all(keys.map(k=>caches.delete(k)));await self.clients.claim();})());});\n// V7.6.2 intentionally has no fetch handler to avoid stale app shells.\n'

@app.get("/version")
def version():
    return {"version":"7.6.2","status":"ok","schema":"additive-v762-frontend-restore"}

@app.get("/probe-v740")
def probe_v740():
    return {"running":"app_v740.py","version":"7.4.0","ok":True,"assignmentSnapshots":True,"classHistory":True,"customTeaching":True,"adaptiveABC":True,"stableFixes":True}

@app.get("/probe-v730")
def probe_v730_compat():
    return {"running":"app_v740.py","version":"7.4.0","ok":True,"compat":"v730"}

def fresh_html():
    return HTMLResponse(INDEX_HTML,headers={"Cache-Control":"no-store, no-cache, must-revalidate, max-age=0","Pragma":"no-cache","Expires":"0"})

@app.get("/", response_class=HTMLResponse)
def home():return fresh_html()

@app.get("/fresh-v762", response_class=HTMLResponse)
def fresh_v762():return fresh_html()

@app.get("/fresh-v761", response_class=HTMLResponse)
def fresh_v761_compat():return fresh_html()

@app.get("/fresh-v760", response_class=HTMLResponse)
def fresh_v760_compat():return fresh_html()

@app.get("/fresh-v752", response_class=HTMLResponse)
def fresh_v752_compat():return fresh_html()

@app.get("/fresh-v751", response_class=HTMLResponse)
def fresh_v751_compat():return fresh_html()

@app.get("/fresh-v750", response_class=HTMLResponse)
def fresh_v750_compat():return fresh_html()

@app.get("/fresh-v740", response_class=HTMLResponse)
def fresh_v740_compat():return fresh_html()

@app.get("/fresh-v730", response_class=HTMLResponse)
def fresh_v730_compat():return fresh_html()

@app.get("/manifest.webmanifest")
def manifest():return Response(MANIFEST,media_type="application/manifest+json",headers={"Cache-Control":"no-store"})

@app.get("/icon.svg")
def icon():return Response(ICON_SVG,media_type="image/svg+xml")

@app.get("/sw.js")
def service_worker():return Response(SERVICE_WORKER,media_type="application/javascript",headers={"Cache-Control":"no-store, no-cache, must-revalidate, max-age=0"})
