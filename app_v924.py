import os, io, json, secrets, hashlib, time, threading, base64
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import FastAPI, HTTPException, Header, Depends, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from sqlalchemy import create_engine, String, Integer, ForeignKey, Text, DateTime, Boolean, UniqueConstraint, select, func, inspect as sa_inspect
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


class SchemaMigration(Base):
    __tablename__="schema_migrations"
    version:Mapped[str]=mapped_column(String(40),primary_key=True)
    description:Mapped[str]=mapped_column(String(240),default="")
    applied_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)

class SchoolSubscription(Base):
    __tablename__="school_subscriptions"
    __table_args__=(UniqueConstraint("school_id",name="uq_school_subscription"),)
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    plan_code:Mapped[str]=mapped_column(String(40),default="free",index=True)
    status:Mapped[str]=mapped_column(String(30),default="active",index=True)
    started_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    trial_ends_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    current_period_ends_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    grace_ends_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    source:Mapped[str]=mapped_column(String(40),default="system")
    note:Mapped[str]=mapped_column(Text,default="")
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class SubscriptionEvent(Base):
    __tablename__="subscription_events"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    action:Mapped[str]=mapped_column(String(40),index=True)
    plan_code:Mapped[str]=mapped_column(String(40),default="")
    status:Mapped[str]=mapped_column(String(30),default="")
    detail:Mapped[str]=mapped_column(Text,default="")
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)

class CommercialCustomer(Base):
    __tablename__="commercial_customers"
    __table_args__=(UniqueConstraint("school_id",name="uq_commercial_customer_school"),)
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    contact_name:Mapped[str]=mapped_column(String(100),default="")
    contact_value:Mapped[str]=mapped_column(String(200),default="")
    source:Mapped[str]=mapped_column(String(80),default="")
    note:Mapped[str]=mapped_column(Text,default="")
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class CommercialFollowUp(Base):
    __tablename__="commercial_followups"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    follow_type:Mapped[str]=mapped_column(String(40),default="contact",index=True)
    content:Mapped[str]=mapped_column(Text,default="")
    next_followup_date:Mapped[str]=mapped_column(String(10),default="",index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)

class CommercialQuotaOverride(Base):
    __tablename__="commercial_quota_overrides"
    __table_args__=(UniqueConstraint("school_id",name="uq_commercial_quota_override_school"),)
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    limits_json:Mapped[str]=mapped_column(Text,default="{}")
    note:Mapped[str]=mapped_column(Text,default="")
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class CommercialOperationLog(Base):
    __tablename__="commercial_operation_logs"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    action:Mapped[str]=mapped_column(String(60),index=True)
    actor:Mapped[str]=mapped_column(String(100),default="commercial_operator")
    before_json:Mapped[str]=mapped_column(Text,default="{}")
    after_json:Mapped[str]=mapped_column(Text,default="{}")
    detail:Mapped[str]=mapped_column(Text,default="")
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)

class CommercialRenewal(Base):
    __tablename__="commercial_renewals"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    plan_code:Mapped[str]=mapped_column(String(40),default="",index=True)
    service_start_at:Mapped[datetime]=mapped_column(DateTime,index=True)
    service_end_at:Mapped[datetime]=mapped_column(DateTime,index=True)
    amount_cents:Mapped[int]=mapped_column(Integer,default=0)
    currency:Mapped[str]=mapped_column(String(10),default="CNY")
    payment_method:Mapped[str]=mapped_column(String(40),default="")
    payment_reference:Mapped[str]=mapped_column(String(160),default="")
    note:Mapped[str]=mapped_column(Text,default="")
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)

class CommercialOrder(Base):
    __tablename__="commercial_orders"
    __table_args__=(UniqueConstraint("order_no",name="uq_commercial_order_no"),UniqueConstraint("source_renewal_id",name="uq_commercial_order_renewal"),)
    id:Mapped[int]=mapped_column(primary_key=True)
    order_no:Mapped[str]=mapped_column(String(60),index=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    order_type:Mapped[str]=mapped_column(String(30),default="service",index=True)
    plan_code:Mapped[str]=mapped_column(String(40),default="",index=True)
    title:Mapped[str]=mapped_column(String(180),default="")
    amount_due_cents:Mapped[int]=mapped_column(Integer,default=0)
    currency:Mapped[str]=mapped_column(String(10),default="CNY")
    status:Mapped[str]=mapped_column(String(30),default="pending",index=True)
    source_renewal_id:Mapped[int|None]=mapped_column(ForeignKey("commercial_renewals.id"),nullable=True,index=True)
    note:Mapped[str]=mapped_column(Text,default="")
    voided_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True,index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)

class CommercialPayment(Base):
    __tablename__="commercial_payments"
    id:Mapped[int]=mapped_column(primary_key=True)
    order_id:Mapped[int]=mapped_column(ForeignKey("commercial_orders.id"),index=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    payment_type:Mapped[str]=mapped_column(String(20),default="payment",index=True)
    amount_cents:Mapped[int]=mapped_column(Integer,default=0)
    currency:Mapped[str]=mapped_column(String(10),default="CNY")
    payment_method:Mapped[str]=mapped_column(String(40),default="")
    payment_reference:Mapped[str]=mapped_column(String(160),default="")
    payment_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)
    note:Mapped[str]=mapped_column(Text,default="")
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)

class AccountDeletionRequest(Base):
    __tablename__="account_deletion_requests"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    reason:Mapped[str]=mapped_column(Text,default="")
    status:Mapped[str]=mapped_column(String(30),default="pending",index=True)
    requested_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)
    resolved_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True,index=True)
    resolved_by:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True,index=True)
    resolution_note:Mapped[str]=mapped_column(Text,default="")


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

class AutoRewardRule(Base):
    __tablename__="auto_reward_rules"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    name:Mapped[str]=mapped_column(String(140))
    reward_id:Mapped[int]=mapped_column(ForeignKey("reward_items.id"),index=True)
    period:Mapped[str]=mapped_column(String(20),default="weekly",index=True)
    metric:Mapped[str]=mapped_column(String(30),default="net",index=True)
    threshold:Mapped[int]=mapped_column(Integer,default=10)
    active:Mapped[bool]=mapped_column(Boolean,default=True,index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class AutoRewardGrant(Base):
    __tablename__="auto_reward_grants"
    __table_args__=(UniqueConstraint("rule_id","student_id","period_key",name="uq_auto_reward_student_period"),)
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    rule_id:Mapped[int]=mapped_column(ForeignKey("auto_reward_rules.id"),index=True)
    student_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    reward_id:Mapped[int]=mapped_column(ForeignKey("reward_items.id"),index=True)
    reward_name:Mapped[str]=mapped_column(String(140))
    period_key:Mapped[str]=mapped_column(String(30),index=True)
    metric_value:Mapped[int]=mapped_column(Integer,default=0)
    threshold:Mapped[int]=mapped_column(Integer,default=0)
    status:Mapped[str]=mapped_column(String(30),default="pending",index=True)
    note:Mapped[str]=mapped_column(Text,default="")
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)
    handled_by:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True,index=True)
    handled_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True,index=True)



class ClassroomGroup(Base):
    __tablename__="classroom_groups"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    class_id:Mapped[int]=mapped_column(ForeignKey("classes.id"),index=True)
    name:Mapped[str]=mapped_column(String(80))
    sort_order:Mapped[int]=mapped_column(Integer,default=0)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class ClassroomGroupMember(Base):
    __tablename__="classroom_group_members"
    __table_args__=(UniqueConstraint("group_id","student_id",name="uq_classroom_group_member"),)
    id:Mapped[int]=mapped_column(primary_key=True)
    group_id:Mapped[int]=mapped_column(ForeignKey("classroom_groups.id"),index=True)
    student_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)


# ---------------- V8.1 student follow-up & class affairs ----------------
class StudentFollowUp(Base):
    __tablename__="student_followups"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    class_id:Mapped[int]=mapped_column(ForeignKey("classes.id"),index=True)
    student_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    title:Mapped[str]=mapped_column(String(180))
    category:Mapped[str]=mapped_column(String(30),default="growth",index=True)
    priority:Mapped[str]=mapped_column(String(20),default="normal",index=True)
    status:Mapped[str]=mapped_column(String(20),default="open",index=True)
    due_date:Mapped[str]=mapped_column(String(20),default="",index=True)
    source:Mapped[str]=mapped_column(String(30),default="manual",index=True)
    note:Mapped[str]=mapped_column(Text,default="")
    created_by:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True,index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)
    completed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True,index=True)

class StudentFollowUpLog(Base):
    __tablename__="student_followup_logs"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    followup_id:Mapped[int]=mapped_column(ForeignKey("student_followups.id"),index=True)
    student_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    actor_id:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True,index=True)
    log_type:Mapped[str]=mapped_column(String(30),default="note",index=True)
    content:Mapped[str]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)

class ClassTodo(Base):
    __tablename__="class_todos"
    id:Mapped[int]=mapped_column(primary_key=True)
    school_id:Mapped[int]=mapped_column(ForeignKey("schools.id"),index=True)
    class_id:Mapped[int]=mapped_column(ForeignKey("classes.id"),index=True)
    title:Mapped[str]=mapped_column(String(180))
    priority:Mapped[str]=mapped_column(String(20),default="normal",index=True)
    status:Mapped[str]=mapped_column(String(20),default="open",index=True)
    due_date:Mapped[str]=mapped_column(String(20),default="",index=True)
    note:Mapped[str]=mapped_column(Text,default="")
    created_by:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True,index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)
    completed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True,index=True)


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

LOGIN_RATE_WINDOW_SECONDS=int(os.getenv("LOGIN_RATE_WINDOW_SECONDS","900"))
LOGIN_RATE_MAX_ATTEMPTS=int(os.getenv("LOGIN_RATE_MAX_ATTEMPTS","30"))
_login_rate_hits={}
_login_rate_lock=threading.Lock()

def _client_ip(request:Request):
    forwarded=(request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")

def login_rate_check(request:Request):
    key=_client_ip(request);now=time.time()
    with _login_rate_lock:
        hits=[x for x in _login_rate_hits.get(key,[]) if now-x<LOGIN_RATE_WINDOW_SECONDS]
        _login_rate_hits[key]=hits
        if len(hits)>=LOGIN_RATE_MAX_ATTEMPTS:
            raise HTTPException(429,"登录请求过于频繁，请稍后再试")
    return key

def login_rate_failure(key):
    with _login_rate_lock:_login_rate_hits.setdefault(key,[]).append(time.time())

def login_rate_clear(key):
    with _login_rate_lock:_login_rate_hits.pop(key,None)

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

def current_user(request:Request,u:User=Depends(authenticated_user),db:Session=Depends(get_db)):
    s=security_for(db,u)
    if s.must_change_password:
        raise HTTPException(428,"请先修改初始密码")
    if request.method.upper() in ("POST","PUT","PATCH","DELETE"):
        exempt=(
            request.url.path.startswith("/account/deletion-request") or
            request.url.path.startswith("/admin/deletion-requests/")
        )
        if not exempt:
            blocked,payload=commercial_write_blocked(db,u.school_id)
            if blocked:
                raise HTTPException(402,f"当前套餐状态为“{payload['statusName']}”，已进入只读模式；历史数据仍可查看，请续费或升级后继续新增/修改")
    return u

def need(u,*roles):
    if u.role not in roles: raise HTTPException(403,"无权限")

# ---------------- Schemas ----------------
class SubscriptionUpdateBody(BaseModel):
    plan_code:str
    status:str="active"
    trial_days:int=14
    period_days:int=365
    grace_days:int=7
    end_date:str=""
    note:str=""

class OperatorSchoolCreateBody(BaseModel):
    school_name:str
    school_code:str
    admin_name:str
    admin_username:str
    admin_password:str
    contact_name:str=""
    contact_value:str=""
    source:str="manual"
    plan_code:str="teacher_pro"
    status:str="trial"
    trial_days:int=14
    period_days:int=365
    grace_days:int=7
    note:str=""

class OperatorResetPasswordBody(BaseModel):
    username:str=""
    new_password:str

class OperatorCustomerUpdateBody(BaseModel):
    contact_name:str=""
    contact_value:str=""
    source:str=""
    note:str=""

class OperatorFollowUpCreateBody(BaseModel):
    follow_type:str="contact"
    content:str
    next_followup_date:str=""

class OperatorSchoolStateBody(BaseModel):
    active:bool
    note:str=""

class OperatorQuotaUpdateBody(BaseModel):
    teachers:str="inherit"
    classes:str="inherit"
    students:str="inherit"
    note:str=""

class OperatorRenewalCreateBody(BaseModel):
    plan_code:str=""
    period_days:int=365
    end_date:str=""
    grace_days:int=7
    amount_yuan:float=0
    payment_method:str=""
    payment_reference:str=""
    note:str=""

class OperatorOrderCreateBody(BaseModel):
    title:str=""
    order_type:str="service"
    plan_code:str=""
    amount_due_yuan:float=0
    amount_paid_yuan:float=0
    payment_method:str=""
    payment_reference:str=""
    payment_date:str=""
    note:str=""

class OperatorPaymentCreateBody(BaseModel):
    amount_yuan:float
    payment_method:str=""
    payment_reference:str=""
    payment_date:str=""
    note:str=""

class OperatorRefundCreateBody(BaseModel):
    amount_yuan:float
    payment_method:str=""
    payment_reference:str=""
    payment_date:str=""
    note:str=""

class OperatorOrderVoidBody(BaseModel):
    note:str=""

class LoginBody(BaseModel): username:str;password:str;remember:bool=False
class ChangePasswordBody(BaseModel): current_password:str;new_password:str;remember:bool=False
class ResetPasswordBody(BaseModel): new_password:str
class ActiveBody(BaseModel): active:bool
class AccountDeletionBody(BaseModel): reason:str=""
class DeletionResolveBody(BaseModel): action:str;note:str=""
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
class AutoRewardRuleBody(BaseModel):
    name:str
    reward_id:int
    period:str="weekly"
    metric:str="net"
    threshold:int=10
    active:bool=True
class AutoRewardHandleBody(BaseModel):
    action:str
    note:str=""

class ClassroomGroupBody(BaseModel):
    name:str
    sort_order:int=0
class ClassroomGroupMembersBody(BaseModel):
    student_ids:list[int]=[]


class FollowUpCreateBody(BaseModel):
    student_id:int
    title:str
    category:str="growth"
    priority:str="normal"
    due_date:str=""
    note:str=""
    source:str="manual"
class FollowUpStatusBody(BaseModel):
    status:str
class FollowUpLogBody(BaseModel):
    log_type:str="note"
    content:str
class ClassTodoBody(BaseModel):
    title:str
    priority:str="normal"
    due_date:str=""
    note:str=""
class ClassTodoStatusBody(BaseModel):
    status:str

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
    names={"class.create":"新建班级","student.create":"创建学生","student.transfer":"学生调班","student.archive":"毕业归档","student.restore":"恢复学生","paper.create":"创建试卷","assignment.create":"布置作业","assignment.export":"导出成绩","class.export":"导出班级报表","student.export":"导出学生成绩单","growth_report.export":"导出学生成长报告","question.create":"新增题目","user.create":"创建账号","user.reset_password":"重置密码","user.active":"账号状态变更","import.xlsx":"批量导入","points.rule.create":"新增积分规则","points.rule.update":"修改积分规则","points.record":"课堂积分记录","points.undo":"撤销积分","reward.create":"新增奖品","reward.update":"修改奖品","reward.redeem":"积分兑换","reward.fulfill":"奖品发放","reward.reject":"兑换拒绝退款","points.export":"导出积分奖励报表","points.weekly.export":"导出班级积分周报","parent.bind":"绑定家长","parent.unbind":"解除家长绑定","auto.reward.rule.create":"新增自动奖励规则","auto.reward.rule.update":"修改自动奖励规则","auto.reward.grant":"自动奖励触发","auto.reward.fulfill":"自动奖励发放","auto.reward.cancel":"自动奖励取消","account.export":"个人数据导出","account.deletion.request":"账号注销申请","account.deletion.cancel":"取消注销申请","account.deletion.resolve":"处理注销申请","backup.export":"学校数据备份"}
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
        if action=="growth_report.export":return f"导出学生成长报告：{detail.split(':',1)[-1]}"
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
    auto_rows=db.scalars(select(AutoRewardGrant).where(
        AutoRewardGrant.school_id==school_id,AutoRewardGrant.student_id==student_id,
        AutoRewardGrant.created_at>=cutoff
    ).order_by(AutoRewardGrant.id.desc())).all()
    active_auto=[x for x in auto_rows if x.status!="canceled"]
    return {"days":days,"earned":positive,"net":net,"activity":activity,"discipline":discipline,
            "redemptionCount":len(active_red),"redeemedPoints":sum(x.cost_points for x in active_red),
            "autoRewardCount":len(active_auto),
            "autoRewardFulfilled":sum(1 for x in active_auto if x.status=="fulfilled"),
            "topReasons":reasons}


def student_weekly_trend(db,student_id:int,school_id:int,weeks:int=4):
    """Calendar-week classroom point trend, oldest to newest, in the school timezone."""
    weeks=max(2,min(int(weeks or 4),12))
    local_now=datetime.now(SCHOOL_TZ)
    current_start=(local_now-timedelta(days=local_now.weekday())).replace(hour=0,minute=0,second=0,microsecond=0)
    first_start=current_start-timedelta(weeks=weeks-1)
    final_end=current_start+timedelta(days=7)
    first_utc=first_start.astimezone(timezone.utc).replace(tzinfo=None)
    final_utc=final_end.astimezone(timezone.utc).replace(tzinfo=None)
    ledgers=db.scalars(select(PointLedger).where(
        PointLedger.school_id==school_id,PointLedger.student_id==student_id,
        PointLedger.created_at>=first_utc,PointLedger.created_at<final_utc,
        PointLedger.source.in_(("classroom","adjustment","reversal"))
    ).order_by(PointLedger.created_at)).all()
    autos=db.scalars(select(AutoRewardGrant).where(
        AutoRewardGrant.school_id==school_id,AutoRewardGrant.student_id==student_id,
        AutoRewardGrant.created_at>=first_utc,AutoRewardGrant.created_at<final_utc
    ).order_by(AutoRewardGrant.created_at)).all()
    out=[]
    for idx in range(weeks):
        start_local=first_start+timedelta(weeks=idx)
        end_local=start_local+timedelta(days=7)
        start_utc=start_local.astimezone(timezone.utc).replace(tzinfo=None)
        end_utc=end_local.astimezone(timezone.utc).replace(tzinfo=None)
        rows=[x for x in ledgers if start_utc<=x.created_at<end_utc]
        week_autos=[x for x in autos if start_utc<=x.created_at<end_utc and x.status!="canceled"]
        earned=sum(int(x.points or 0) for x in rows if (x.points or 0)>0 and x.source in ("classroom","adjustment"))
        net=sum(int(x.points or 0) for x in rows)
        activity=sum(int(x.points or 0) for x in rows if x.category=="activity")
        discipline=sum(int(x.points or 0) for x in rows if x.category=="discipline")
        label="本周" if idx==weeks-1 else f"{start_local.month}/{start_local.day}-{(end_local-timedelta(days=1)).month}/{(end_local-timedelta(days=1)).day}"
        iso=start_local.isocalendar()
        out.append({"label":label,"periodKey":f"{iso.year}-W{iso.week:02d}","startDate":start_local.date().isoformat(),
                    "earned":earned,"net":net,"activity":activity,"discipline":discipline,
                    "autoRewardCount":len(week_autos),"autoRewardFulfilled":sum(1 for x in week_autos if x.status=="fulfilled")})
    return out

def auto_period_window(period:str):
    now=datetime.now(SCHOOL_TZ)
    period=(period or "weekly").strip().lower()
    if period=="monthly":
        start=now.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
        key=now.strftime("%Y-%m")
    else:
        period="weekly"
        start=(now-timedelta(days=now.weekday())).replace(hour=0,minute=0,second=0,microsecond=0)
        iso=now.isocalendar();key=f"{iso.year}-W{iso.week:02d}"
    return start.astimezone(timezone.utc).replace(tzinfo=None),key,period

def auto_metric_value(db,student_id:int,school_id:int,period:str,metric:str):
    cutoff,key,period=auto_period_window(period)
    rows=db.scalars(select(PointLedger).where(
        PointLedger.school_id==school_id,PointLedger.student_id==student_id,
        PointLedger.created_at>=cutoff,
        PointLedger.source.in_(("classroom","adjustment","reversal"))
    )).all()
    metric=(metric or "net").strip().lower()
    if metric=="issued":
        value=sum(int(x.points or 0) for x in rows if (x.points or 0)>0 and x.source in ("classroom","adjustment"))
    elif metric=="activity":
        value=sum(int(x.points or 0) for x in rows if x.category=="activity")
    elif metric=="discipline":
        value=sum(int(x.points or 0) for x in rows if x.category=="discipline")
    else:
        metric="net";value=sum(int(x.points or 0) for x in rows)
    return int(value),key,period,metric

def auto_rule_json(db,row):
    reward=db.get(RewardItem,row.reward_id)
    return {"id":row.id,"name":row.name,"rewardID":row.reward_id,"rewardName":reward.name if reward else "已删除奖品",
            "rewardIcon":reward.icon if reward else "🎁","period":row.period,"metric":row.metric,
            "threshold":row.threshold,"active":bool(row.active)}

def auto_grant_json(db,row):
    stu=db.get(User,row.student_id);reward=db.get(RewardItem,row.reward_id);rule=db.get(AutoRewardRule,row.rule_id)
    actor=db.get(User,row.handled_by) if row.handled_by else None
    c=current_class_for(db,row.student_id,row.school_id)
    return {"id":row.id,"studentID":row.student_id,"studentName":stu.name if stu else "","classID":c.id if c else None,
            "className":c.name if c else "","ruleID":row.rule_id,"ruleName":rule.name if rule else "自动奖励",
            "rewardID":row.reward_id,"rewardName":row.reward_name,"rewardIcon":reward.icon if reward else "🎁",
            "periodKey":row.period_key,"metricValue":row.metric_value,"threshold":row.threshold,"status":row.status,
            "note":row.note,"createdAt":school_local_iso(row.created_at),"handledBy":actor.name if actor else "",
            "handledAt":school_local_iso(row.handled_at) if row.handled_at else None}

def _reward_window_ok(row):
    today=datetime.now(SCHOOL_TZ).date().isoformat()
    return (not row.start_date or today>=row.start_date) and (not row.end_date or today<=row.end_date)

def _restore_auto_grant_stock(db,grant):
    reward=db.get(RewardItem,grant.reward_id)
    if reward and not reward.unlimited_stock:reward.stock+=1

def reconcile_auto_rewards(db,school_id:int,student_ids:list[int],actor_id:int|None=None):
    ids=list(dict.fromkeys(int(x) for x in student_ids if int(x)>0))
    if not ids:return []
    rules=db.scalars(select(AutoRewardRule).where(AutoRewardRule.school_id==school_id)).all()
    changed=[]
    for sid in ids:
        stu=db.scalar(select(User).where(User.id==sid,User.school_id==school_id,User.role=="student",User.active==True))
        if not stu:continue
        for rule in rules:
            value,key,period,metric=auto_metric_value(db,sid,school_id,rule.period,rule.metric)
            grant=db.scalar(select(AutoRewardGrant).where(
                AutoRewardGrant.rule_id==rule.id,AutoRewardGrant.student_id==sid,AutoRewardGrant.period_key==key
            ))
            if not rule.active:
                if grant and grant.status=="pending":
                    _restore_auto_grant_stock(db,grant);grant.status="canceled";grant.note="自动奖励规则已停用";grant.handled_by=actor_id;grant.handled_at=datetime.utcnow();changed.append(grant)
                continue
            if value>=rule.threshold:
                if grant is None:
                    reward=db.scalar(select(RewardItem).where(RewardItem.id==rule.reward_id,RewardItem.school_id==school_id))
                    if not reward or not reward.active or not _reward_window_ok(reward):continue
                    if not reward.unlimited_stock and reward.stock<=0:continue
                    if not reward.unlimited_stock:reward.stock-=1
                    grant=AutoRewardGrant(school_id=school_id,rule_id=rule.id,student_id=sid,reward_id=reward.id,reward_name=reward.name,
                                          period_key=key,metric_value=value,threshold=rule.threshold,status="pending",
                                          note=f"自动达标：{rule.name}")
                    db.add(grant);db.flush();changed.append(grant)
                elif grant.status=="pending":
                    grant.metric_value=value;grant.threshold=rule.threshold
                elif grant.status=="canceled":
                    reward=db.scalar(select(RewardItem).where(RewardItem.id==rule.reward_id,RewardItem.school_id==school_id))
                    if reward and reward.active and _reward_window_ok(reward) and (reward.unlimited_stock or reward.stock>0):
                        if not reward.unlimited_stock:reward.stock-=1
                        grant.reward_id=reward.id;grant.reward_name=reward.name;grant.metric_value=value;grant.threshold=rule.threshold;grant.status="pending";grant.note=f"重新达标：{rule.name}";grant.handled_by=None;grant.handled_at=None;changed.append(grant)
            elif grant and grant.status=="pending":
                _restore_auto_grant_stock(db,grant);grant.status="canceled";grant.metric_value=value;grant.note="积分变动后未达到自动奖励条件";grant.handled_by=actor_id;grant.handled_at=datetime.utcnow();changed.append(grant)
    return changed

def cancel_auto_rule_pending(db,rule_id:int,actor_id:int|None=None,reason:str="自动奖励规则已停用"):
    rows=db.scalars(select(AutoRewardGrant).where(AutoRewardGrant.rule_id==rule_id,AutoRewardGrant.status=="pending")).all()
    for g in rows:
        _restore_auto_grant_stock(db,g);g.status="canceled";g.note=reason;g.handled_by=actor_id;g.handled_at=datetime.utcnow()
    return rows


def calendar_week_window_utc(offset_weeks:int=0):
    local_now=datetime.now(SCHOOL_TZ)
    start=(local_now-timedelta(days=local_now.weekday())+timedelta(weeks=offset_weeks)).replace(hour=0,minute=0,second=0,microsecond=0)
    end=start+timedelta(days=7)
    return (start.astimezone(timezone.utc).replace(tzinfo=None),
            end.astimezone(timezone.utc).replace(tzinfo=None),
            start.date().isoformat(),(end-timedelta(days=1)).date().isoformat())

def month_window_utc(month:str|None=None):
    now=datetime.now(SCHOOL_TZ)
    if month:
        try:
            y,m=[int(x) for x in month.split("-",1)]
            start=now.replace(year=y,month=m,day=1,hour=0,minute=0,second=0,microsecond=0)
        except Exception:
            raise HTTPException(400,"月份格式应为 YYYY-MM")
    else:
        start=now.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    end=start.replace(year=start.year+1,month=1) if start.month==12 else start.replace(month=start.month+1)
    return (start.astimezone(timezone.utc).replace(tzinfo=None),
            end.astimezone(timezone.utc).replace(tzinfo=None),
            start.strftime("%Y-%m"))

def point_window_summary(db,student_id:int,school_id:int,start_utc:datetime,end_utc:datetime):
    rows=db.scalars(select(PointLedger).where(
        PointLedger.school_id==school_id,PointLedger.student_id==student_id,
        PointLedger.created_at>=start_utc,PointLedger.created_at<end_utc,
        PointLedger.source.in_(("classroom","adjustment","reversal"))
    )).all()
    earned=sum(int(x.points or 0) for x in rows if (x.points or 0)>0 and x.source in ("classroom","adjustment"))
    return {"earned":earned,
            "net":sum(int(x.points or 0) for x in rows),
            "activity":sum(int(x.points or 0) for x in rows if x.category=="activity"),
            "discipline":sum(int(x.points or 0) for x in rows if x.category=="discipline"),
            "records":len(rows)}

def student_growth_badges(db,student_id:int,school_id:int):
    cur_start,cur_end,_,_=calendar_week_window_utc(0);prev_start,prev_end,_,_=calendar_week_window_utc(-1)
    cur=point_window_summary(db,student_id,school_id,cur_start,cur_end);prev=point_window_summary(db,student_id,school_id,prev_start,prev_end)
    auto_count=int(db.scalar(select(func.count()).select_from(AutoRewardGrant).where(
        AutoRewardGrant.school_id==school_id,AutoRewardGrant.student_id==student_id,
        AutoRewardGrant.created_at>=cur_start,AutoRewardGrant.created_at<cur_end,AutoRewardGrant.status=="fulfilled"
    )) or 0)
    badges=[]
    if cur["net"]>=1:badges.append({"key":"weekly_star","icon":"🌟","name":"本周之星","detail":"本周净表现为正"})
    if cur["activity"]>=3:badges.append({"key":"active","icon":"🙋","name":"积极达人","detail":"本周课堂活动积分达到3分"})
    if cur["discipline"]>=2:badges.append({"key":"discipline","icon":"🛡️","name":"守纪之星","detail":"本周守纪积分达到2分"})
    if cur["net"]>prev["net"]:badges.append({"key":"improved","icon":"📈","name":"进步之星","detail":f"较上周提升 {cur['net']-prev['net']} 分"})
    if auto_count>0:badges.append({"key":"reward","icon":"🎁","name":"荣誉获得","detail":f"本周已发放自动奖励 {auto_count} 次"})
    return badges

def student_growth_advice(db,student_id:int,school_id:int):
    cur_start,cur_end,_,_=calendar_week_window_utc(0);prev_start,prev_end,_,_=calendar_week_window_utc(-1)
    cur=point_window_summary(db,student_id,school_id,cur_start,cur_end);prev=point_window_summary(db,student_id,school_id,prev_start,prev_end)
    if cur["records"]==0:return ["本周暂未产生课堂积分记录，可关注孩子课堂参与和守纪情况。"]
    advice=[]
    if cur["net"]>prev["net"]:advice.append(f"本周净表现较上周提升 {cur['net']-prev['net']} 分，建议及时肯定这份进步。")
    elif cur["net"]<prev["net"]:advice.append(f"本周净表现较上周减少 {prev['net']-cur['net']} 分，可和孩子一起回顾课堂状态。")
    else:advice.append("本周净表现与上周持平，可继续保持稳定的课堂节奏。")
    if cur["activity"]<=0:advice.append("课堂活动积分偏少，可以鼓励孩子主动举手、参与讨论或完成课堂任务。")
    elif cur["activity"]>=3:advice.append("课堂参与较积极，可继续鼓励孩子保持主动表达和合作。")
    if cur["discipline"]<0:advice.append("守纪积分出现扣分，建议结合具体记录和孩子沟通改进。")
    elif cur["discipline"]>=2:advice.append("守纪表现良好，可以给予明确表扬，强化好习惯。")
    return advice[:3]

def class_groups_json(db,c:SchoolClass,school_id:int):
    groups=db.scalars(select(ClassroomGroup).where(ClassroomGroup.class_id==c.id,ClassroomGroup.school_id==school_id).order_by(ClassroomGroup.sort_order,ClassroomGroup.id)).all()
    cur_start,cur_end,_,_=calendar_week_window_utc(0);out=[]
    for g in groups:
        ids=list(db.scalars(select(ClassroomGroupMember.student_id).where(ClassroomGroupMember.group_id==g.id)).all())
        members=[];totals={"net":0,"earned":0,"activity":0,"discipline":0}
        for sid in ids:
            stu=db.scalar(select(User).where(User.id==sid,User.school_id==school_id,User.role=="student",User.active==True))
            if not stu:continue
            s=point_window_summary(db,sid,school_id,cur_start,cur_end);members.append({"id":stu.id,"name":stu.name,**s})
            for k in totals:totals[k]+=int(s.get(k,0) or 0)
        out.append({"id":g.id,"name":g.name,"sortOrder":g.sort_order,"memberCount":len(members),"members":members,**totals})
    ranked=sorted(out,key=lambda x:(x["net"],x["earned"],x["activity"],x["name"]),reverse=True);rank_by_id={x["id"]:i for i,x in enumerate(ranked,1)}
    for x in out:x["rank"]=rank_by_id.get(x["id"],0)
    return out

def class_growth_dashboard_data(db,c:SchoolClass,school_id:int):
    students=db.scalars(select(User).join(ClassStudent,ClassStudent.student_id==User.id).where(
        ClassStudent.class_id==c.id,User.school_id==school_id,User.role=="student",User.active==True
    ).order_by(User.name)).all()
    cur_start,cur_end,cur_s,cur_e=calendar_week_window_utc(0);prev_start,prev_end,prev_s,prev_e=calendar_week_window_utc(-1)
    progress=[]
    for stu in students:
        cur=point_window_summary(db,stu.id,school_id,cur_start,cur_end);prev=point_window_summary(db,stu.id,school_id,prev_start,prev_end)
        progress.append({"studentID":stu.id,"studentName":stu.name,"currentNet":cur["net"],"previousNet":prev["net"],
                         "change":cur["net"]-prev["net"],"activity":cur["activity"],"discipline":cur["discipline"],
                         "badges":student_growth_badges(db,stu.id,school_id)})
    progress.sort(key=lambda x:(x["change"],x["currentNet"],x["studentName"]),reverse=True)
    for i,x in enumerate(progress,1):x["rank"]=i
    category={}
    rows=db.scalars(select(PointLedger).where(PointLedger.school_id==school_id,PointLedger.class_id==c.id,
        PointLedger.created_at>=cur_start,PointLedger.created_at<cur_end,PointLedger.source.in_(("classroom","adjustment","reversal")))).all()
    for row in rows:
        key=row.reason or ("课堂活动" if row.category=="activity" else "守纪情况")
        z=category.setdefault(key,{"reason":key,"category":row.category,"count":0,"points":0});z["count"]+=1;z["points"]+=int(row.points or 0)
    categories=sorted(category.values(),key=lambda x:(abs(x["points"]),x["count"]),reverse=True)[:12]
    return {"class":{"id":c.id,"name":c.name,"grade":c.grade},"currentWeek":{"start":cur_s,"end":cur_e},
            "previousWeek":{"start":prev_s,"end":prev_e},"groups":sorted(class_groups_json(db,c,school_id),key=lambda x:(x["rank"] or 999,x["name"])),
            "progressRanking":progress,"categoryStats":categories}


def day_window_utc(offset_days:int=0):
    local_now=datetime.now(SCHOOL_TZ)+timedelta(days=offset_days)
    start=local_now.replace(hour=0,minute=0,second=0,microsecond=0)
    end=start+timedelta(days=1)
    return (start.astimezone(timezone.utc).replace(tzinfo=None),
            end.astimezone(timezone.utc).replace(tzinfo=None),
            start.date().isoformat())

def class_period_profile(db,student_ids:list[int],school_id:int,start_utc:datetime,end_utc:datetime):
    totals={"earned":0,"net":0,"activity":0,"discipline":0,"records":0}
    active=positive=negative=0
    for sid in student_ids:
        s=point_window_summary(db,sid,school_id,start_utc,end_utc)
        for k in totals:totals[k]+=int(s.get(k,0) or 0)
        if s["records"]>0:active+=1
        if s["net"]>0:positive+=1
        elif s["net"]<0:negative+=1
    auto_count=0
    if student_ids:
        auto_count=int(db.scalar(select(func.count()).select_from(AutoRewardGrant).where(
            AutoRewardGrant.school_id==school_id,AutoRewardGrant.student_id.in_(student_ids),
            AutoRewardGrant.created_at>=start_utc,AutoRewardGrant.created_at<end_utc,
            AutoRewardGrant.status!="canceled"
        )) or 0)
    count=len(student_ids)
    return {**totals,"studentCount":count,"activeStudents":active,"positiveStudents":positive,
            "negativeStudents":negative,"participationRate":round(active*100/count) if count else 0,
            "positiveRate":round(positive*100/count) if count else 0,
            "averageNet":round(totals["net"]/count,1) if count else 0,"autoRewards":auto_count}

def student_academic_summary(db,student_id:int,school_id:int,days:int=30):
    cutoff,_=period_cutoff_utc(days)
    rows=db.scalars(select(Submission).where(
        Submission.school_id==school_id,Submission.student_id==student_id,
        Submission.submitted_at>=cutoff
    ).order_by(Submission.submitted_at.desc())).all()
    if not rows:return {"days":days,"count":0,"avgScore":None,"avgAccuracy":None,"latestScore":None}
    scores=[int(x.score or 0) for x in rows]
    acc=[(int(x.correct or 0)*100/int(x.total)) for x in rows if int(x.total or 0)>0]
    return {"days":days,"count":len(rows),"avgScore":round(sum(scores)/len(scores),1),
            "avgAccuracy":round(sum(acc)/len(acc),1) if acc else None,
            "latestScore":scores[0] if scores else None}

def _progress_streak_from_trend(trend:list[dict]):
    if len(trend)<2:return 0
    streak=0
    for i in range(len(trend)-1,0,-1):
        if int(trend[i].get("net",0))>int(trend[i-1].get("net",0)):streak+=1
        else:break
    return streak

def _discipline_streak_from_trend(trend:list[dict]):
    streak=0
    for x in reversed(trend):
        if int(x.get("discipline",0))<0:streak+=1
        else:break
    return streak

def student_homeroom_snapshot(db,stu:User,school_id:int):
    cur_start,cur_end,_,_=calendar_week_window_utc(0)
    month_start,month_end,_=month_window_utc()
    weekly=point_window_summary(db,stu.id,school_id,cur_start,cur_end)
    monthly=point_window_summary(db,stu.id,school_id,month_start,month_end)
    trend=student_weekly_trend(db,stu.id,school_id,4)
    academic=student_academic_summary(db,stu.id,school_id,30)
    progress_streak=_progress_streak_from_trend(trend)
    discipline_streak=_discipline_streak_from_trend(trend)
    risk=[];positive=[]
    if weekly["discipline"]<0:risk.append("本周守纪有扣分")
    if weekly["net"]<0:risk.append("本周净表现为负")
    if discipline_streak>=2:risk.append(f"连续{discipline_streak}周守纪有扣分")
    if academic["avgScore"] is not None and academic["avgScore"]<60:risk.append("近30天学习成绩需关注")
    if weekly["records"]>0 and weekly["activity"]<=0:risk.append("本周课堂参与偏少")
    if progress_streak>=2:positive.append(f"连续{progress_streak}周进步")
    elif progress_streak==1:positive.append("本周较上周进步")
    if weekly["net"]>=3:positive.append("本周课堂表现积极")
    if academic["avgScore"] is not None and academic["avgScore"]>=85:positive.append("近30天学习表现良好")
    if academic["count"]==0:
        link_label="暂无成绩"
    elif academic["avgScore"]>=80 and monthly["net"]>=2:
        link_label="学业课堂双向积极"
    elif academic["avgScore"]<60 and monthly["net"]<0:
        link_label="综合需关注"
    elif academic["avgScore"]<60:
        link_label="学业需关注"
    elif monthly["net"]<0:
        link_label="课堂表现需关注"
    else:
        link_label="整体稳定"
    parts=[f"{stu.name}本周课堂净表现 {weekly['net']:+d} 分"]
    if weekly["activity"] or weekly["discipline"]:
        parts.append(f"其中课堂活动 {weekly['activity']:+d}、守纪 {weekly['discipline']:+d}")
    if academic["avgScore"] is not None:
        parts.append(f"近30天完成 {academic['count']} 次练习，平均 {academic['avgScore']} 分")
    if risk:
        parts.append("建议关注："+"、".join(risk[:2]))
    elif positive:
        parts.append("值得肯定："+"、".join(positive[:2]))
    else:
        parts.append("整体表现较稳定，可继续保持")
    communication="；".join(parts)+"。"
    return {"studentID":stu.id,"studentName":stu.name,"weekly":weekly,"monthly":monthly,
            "trend":trend,"academic":academic,"progressStreak":progress_streak,
            "disciplineStreak":discipline_streak,"riskFlags":risk,"positiveFlags":positive,
            "linkLabel":link_label,"communicationSummary":communication}

def class_homeroom_dashboard_data(db,c:SchoolClass,school_id:int):
    students=db.scalars(select(User).join(ClassStudent,ClassStudent.student_id==User.id).where(
        ClassStudent.class_id==c.id,User.school_id==school_id,User.role=="student",User.active==True
    ).order_by(User.name)).all()
    ids=[x.id for x in students]
    today_start,today_end,today_key=day_window_utc(0)
    week_start,week_end,week_s,week_e=calendar_week_window_utc(0)
    month_start,month_end,month_key=month_window_utc()
    today_rows=db.scalars(select(PointLedger).where(
        PointLedger.school_id==school_id,PointLedger.class_id==c.id,
        PointLedger.created_at>=today_start,PointLedger.created_at<today_end,
        PointLedger.source.in_(("classroom","adjustment","reversal"))
    ).order_by(PointLedger.id.desc())).all()
    by_student={}
    for row in today_rows:
        z=by_student.setdefault(row.student_id,{"studentID":row.student_id,"net":0,"activity":0,"discipline":0,"records":0})
        z["net"]+=int(row.points or 0);z["records"]+=1
        if row.category=="activity":z["activity"]+=int(row.points or 0)
        if row.category=="discipline":z["discipline"]+=int(row.points or 0)
    name_by_id={x.id:x.name for x in students}
    today_students=[]
    for sid,z in by_student.items():
        if sid in name_by_id:today_students.append({**z,"studentName":name_by_id[sid]})
    today_students.sort(key=lambda x:(x["net"],x["activity"],x["studentName"]),reverse=True)
    today={"date":today_key,"recordCount":len(today_rows),"studentCount":len(by_student),
           "positiveStudents":sum(1 for x in today_students if x["net"]>0),
           "negativeStudents":sum(1 for x in today_students if x["net"]<0),
           "activity":sum(int(x.points or 0) for x in today_rows if x.category=="activity"),
           "discipline":sum(int(x.points or 0) for x in today_rows if x.category=="discipline"),
           "net":sum(int(x.points or 0) for x in today_rows),"students":today_students[:12]}
    snapshots=[student_homeroom_snapshot(db,stu,school_id) for stu in students]
    focus=[x for x in snapshots if x["riskFlags"]]
    focus.sort(key=lambda x:(len(x["riskFlags"]),-x["weekly"]["net"]),reverse=True)
    positive=[x for x in snapshots if x["positiveFlags"]]
    positive.sort(key=lambda x:(x["progressStreak"],x["weekly"]["net"],
                                x["academic"]["avgScore"] if x["academic"]["avgScore"] is not None else -1),reverse=True)
    academics=sorted(snapshots,key=lambda x:(
        x["academic"]["avgScore"] if x["academic"]["avgScore"] is not None else -1,
        x["monthly"]["net"],x["studentName"]),reverse=True)
    return {"class":{"id":c.id,"name":c.name,"grade":c.grade},"today":today,
            "profiles":{"week":{"label":f"{week_s} 至 {week_e}",**class_period_profile(db,ids,school_id,week_start,week_end)},
                        "month":{"label":month_key,**class_period_profile(db,ids,school_id,month_start,month_end)}},
            "focusList":focus[:12],"positiveAlerts":positive[:12],"students":snapshots,
            "academicBehavior":academics,"generatedAt":school_local_iso(datetime.utcnow())}



FOLLOWUP_CATEGORY_NAMES={"growth":"成长跟进","learning":"学习跟进","classroom":"课堂表现","parent":"家校沟通","other":"其他"}
FOLLOWUP_PRIORITY_NAMES={"low":"低","normal":"普通","high":"高"}
FOLLOWUP_STATUS_NAMES={"open":"待跟进","in_progress":"跟进中","done":"已完成"}
FOLLOWUP_LOG_NAMES={"note":"跟进记录","parent_contact":"家长沟通","result":"处理结果"}

def _safe_local_date(value:str):
    s=(value or "").strip()
    if not s:return None
    try:return datetime.fromisoformat(s[:10]).date()
    except Exception:return None

def _due_meta(due_date:str,status:str):
    if status=="done":return {"dueState":"done","dueLabel":"已完成","overdue":False}
    d=_safe_local_date(due_date)
    if not d:return {"dueState":"none","dueLabel":"未设截止","overdue":False}
    today=datetime.now(SCHOOL_TZ).date()
    delta=(d-today).days
    if delta<0:return {"dueState":"overdue","dueLabel":f"逾期 {abs(delta)} 天","overdue":True}
    if delta==0:return {"dueState":"today","dueLabel":"今天到期","overdue":False}
    if delta<=3:return {"dueState":"soon","dueLabel":f"{delta} 天后到期","overdue":False}
    return {"dueState":"upcoming","dueLabel":due_date[:10],"overdue":False}

def followup_log_json(db,row:StudentFollowUpLog):
    actor=db.get(User,row.actor_id) if row.actor_id else None
    return {"id":row.id,"followupID":row.followup_id,"studentID":row.student_id,
            "type":row.log_type,"typeName":FOLLOWUP_LOG_NAMES.get(row.log_type,row.log_type),
            "content":row.content,"actorName":actor.name if actor else "",
            "createdAt":school_local_iso(row.created_at)}

def followup_json(db,row:StudentFollowUp,include_logs:bool=False):
    stu=db.get(User,row.student_id);actor=db.get(User,row.created_by) if row.created_by else None
    logs=db.scalars(select(StudentFollowUpLog).where(
        StudentFollowUpLog.followup_id==row.id,StudentFollowUpLog.school_id==row.school_id
    ).order_by(StudentFollowUpLog.created_at.desc(),StudentFollowUpLog.id.desc())).all()
    out={"id":row.id,"classID":row.class_id,"studentID":row.student_id,
         "studentName":stu.name if stu else f"学生{row.student_id}","title":row.title,
         "category":row.category,"categoryName":FOLLOWUP_CATEGORY_NAMES.get(row.category,row.category),
         "priority":row.priority,"priorityName":FOLLOWUP_PRIORITY_NAMES.get(row.priority,row.priority),
         "status":row.status,"statusName":FOLLOWUP_STATUS_NAMES.get(row.status,row.status),
         "dueDate":row.due_date or "","source":row.source or "manual","note":row.note or "",
         "createdBy":actor.name if actor else "","createdAt":school_local_iso(row.created_at),
         "updatedAt":school_local_iso(row.updated_at),"completedAt":school_local_iso(row.completed_at) if row.completed_at else "",
         "logCount":len(logs),"latestLog":followup_log_json(db,logs[0]) if logs else None,
         **_due_meta(row.due_date,row.status)}
    if include_logs:out["logs"]=[followup_log_json(db,x) for x in logs]
    return out

def class_todo_json(db,row:ClassTodo):
    actor=db.get(User,row.created_by) if row.created_by else None
    return {"id":row.id,"classID":row.class_id,"title":row.title,"priority":row.priority,
            "priorityName":FOLLOWUP_PRIORITY_NAMES.get(row.priority,row.priority),
            "status":row.status,"statusName":"已完成" if row.status=="done" else "待办",
            "dueDate":row.due_date or "","note":row.note or "","createdBy":actor.name if actor else "",
            "createdAt":school_local_iso(row.created_at),"completedAt":school_local_iso(row.completed_at) if row.completed_at else "",
            **_due_meta(row.due_date,row.status)}

def class_followup_dashboard_data(db,c:SchoolClass,school_id:int):
    rows=db.scalars(select(StudentFollowUp).where(
        StudentFollowUp.school_id==school_id,StudentFollowUp.class_id==c.id
    ).order_by(StudentFollowUp.status,StudentFollowUp.updated_at.desc(),StudentFollowUp.id.desc())).all()
    todos=db.scalars(select(ClassTodo).where(
        ClassTodo.school_id==school_id,ClassTodo.class_id==c.id
    ).order_by(ClassTodo.status,ClassTodo.created_at.desc(),ClassTodo.id.desc())).all()
    cases=[followup_json(db,x) for x in rows];todo_rows=[class_todo_json(db,x) for x in todos]
    open_rows=[x for x in cases if x["status"]!="done"]
    done_rows=[x for x in cases if x["status"]=="done"]
    communications=int(db.scalar(select(func.count()).select_from(StudentFollowUpLog).join(
        StudentFollowUp,StudentFollowUp.id==StudentFollowUpLog.followup_id
    ).where(StudentFollowUp.school_id==school_id,StudentFollowUp.class_id==c.id,
            StudentFollowUpLog.log_type=="parent_contact")) or 0)
    return {"class":{"id":c.id,"name":c.name,"grade":c.grade},
            "summary":{"open":len(open_rows),"inProgress":sum(1 for x in open_rows if x["status"]=="in_progress"),
                       "overdue":sum(1 for x in open_rows if x["overdue"]),"done":len(done_rows),
                       "communications":communications,
                       "todoOpen":sum(1 for x in todo_rows if x["status"]!="done")},
            "cases":cases,"todos":todo_rows}

def student_growth_timeline_data(db,student_id:int,school_id:int,class_id:int|None=None,limit:int=80):
    events=[]
    q=select(PointLedger).where(PointLedger.school_id==school_id,PointLedger.student_id==student_id)
    if class_id:q=q.where(PointLedger.class_id==class_id)
    for x in db.scalars(q.order_by(PointLedger.created_at.desc()).limit(30)).all():
        events.append({"type":"point","icon":"⭐" if int(x.points or 0)>=0 else "📝","title":x.reason or "课堂积分",
                       "detail":f"{'+' if int(x.points or 0)>0 else ''}{int(x.points or 0)} 分"+(f" · {x.note}" if x.note else ""),
                       "time":school_local_iso(x.created_at),"ts":x.created_at})
    for x in db.scalars(select(AutoRewardGrant).where(
        AutoRewardGrant.school_id==school_id,AutoRewardGrant.student_id==student_id
    ).order_by(AutoRewardGrant.created_at.desc()).limit(15)).all():
        events.append({"type":"reward","icon":"🎁","title":x.reward_name,
                       "detail":f"自动奖励 · {x.status} · 达标 {x.metric_value}/{x.threshold}",
                       "time":school_local_iso(x.created_at),"ts":x.created_at})
    fq=select(StudentFollowUp).where(StudentFollowUp.school_id==school_id,StudentFollowUp.student_id==student_id)
    if class_id:fq=fq.where(StudentFollowUp.class_id==class_id)
    follows=db.scalars(fq.order_by(StudentFollowUp.created_at.desc()).limit(20)).all()
    ids=[x.id for x in follows]
    for x in follows:
        events.append({"type":"followup","icon":"📌","title":f"跟进事项：{x.title}",
                       "detail":f"{FOLLOWUP_CATEGORY_NAMES.get(x.category,x.category)} · {FOLLOWUP_STATUS_NAMES.get(x.status,x.status)}",
                       "time":school_local_iso(x.created_at),"ts":x.created_at})
    if ids:
        for x in db.scalars(select(StudentFollowUpLog).where(
            StudentFollowUpLog.followup_id.in_(ids),StudentFollowUpLog.school_id==school_id
        ).order_by(StudentFollowUpLog.created_at.desc()).limit(40)).all():
            events.append({"type":"followup_log","icon":"💬" if x.log_type=="parent_contact" else "🗒️",
                           "title":FOLLOWUP_LOG_NAMES.get(x.log_type,x.log_type),"detail":x.content,
                           "time":school_local_iso(x.created_at),"ts":x.created_at})
    for x in db.scalars(select(Submission).where(
        Submission.school_id==school_id,Submission.student_id==student_id
    ).order_by(Submission.submitted_at.desc()).limit(20)).all():
        events.append({"type":"academic","icon":"📈","title":x.title or "学习练习",
                       "detail":f"{x.score} 分 · {x.correct}/{x.total}",
                       "time":school_local_iso(x.submitted_at),"ts":x.submitted_at})
    events.sort(key=lambda x:x["ts"] or datetime.min,reverse=True)
    for x in events:x.pop("ts",None)
    return events[:max(10,min(int(limit or 80),120))]

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


APP_VERSION="9.2.5"
SCHEMA_VERSION="9.2.5"
RELEASE_CHANNEL="commercial-pilot"
RELEASE_NAME="商业版 C2.5"

COMMERCIAL_ADMIN_KEY=os.getenv("COMMERCIAL_ADMIN_KEY","").strip()
COMMERCIAL_CONTACT=os.getenv("COMMERCIAL_CONTACT","").strip()

COMMERCIAL_PLANS={
    "free":{
        "code":"free","name":"免费体验版","monthlyPrice":0,"annualPrice":0,
        "limits":{"teachers":1,"classes":2,"students":80},
        "features":{
            "growth_profile":True,"growth_report":False,"parent_communication":False,
            "bulk_import":False,"school_backup":False,"school_audit":False
        }
    },
    "teacher_pro":{
        "code":"teacher_pro","name":"教师专业版","monthlyPrice":39,"annualPrice":299,
        "limits":{"teachers":1,"classes":10,"students":500},
        "features":{
            "growth_profile":True,"growth_report":True,"parent_communication":True,
            "bulk_import":False,"school_backup":False,"school_audit":False
        }
    },
    "school_basic":{
        "code":"school_basic","name":"学校基础版","monthlyPrice":None,"annualPrice":2980,
        "limits":{"teachers":10,"classes":None,"students":500},
        "features":{
            "growth_profile":True,"growth_report":True,"parent_communication":True,
            "bulk_import":True,"school_backup":True,"school_audit":True
        }
    },
    "school_standard":{
        "code":"school_standard","name":"学校标准版","monthlyPrice":None,"annualPrice":6800,
        "limits":{"teachers":30,"classes":None,"students":1500},
        "features":{
            "growth_profile":True,"growth_report":True,"parent_communication":True,
            "bulk_import":True,"school_backup":True,"school_audit":True
        }
    },
    "custom":{
        "code":"custom","name":"学校定制版","monthlyPrice":None,"annualPrice":None,
        "limits":{"teachers":None,"classes":None,"students":None},
        "features":{
            "growth_profile":True,"growth_report":True,"parent_communication":True,
            "bulk_import":True,"school_backup":True,"school_audit":True
        }
    }
}
SUBSCRIPTION_STATUS_NAMES={"trial":"试用中","active":"已开通","grace":"宽限期","expired":"已到期"}
FEATURE_NAMES={
    "growth_profile":"学生成长档案","growth_report":"成长报告导出","parent_communication":"家校沟通",
    "bulk_import":"批量导入","school_backup":"学校数据备份","school_audit":"全校审计"
}

def _commercial_plan(code):
    return COMMERCIAL_PLANS.get(code) or COMMERCIAL_PLANS["free"]

def _effective_subscription_status(row,now=None):
    now=now or datetime.utcnow()
    status=(row.status or "active").lower()
    if status=="trial":
        if row.trial_ends_at and row.trial_ends_at<=now:return "expired"
        return "trial"
    if status=="active":
        if row.current_period_ends_at and row.current_period_ends_at<=now:
            if row.grace_ends_at and row.grace_ends_at>now:return "grace"
            return "expired"
        return "active"
    if status=="grace":
        if row.grace_ends_at and row.grace_ends_at<=now:return "expired"
        return "grace"
    return "expired" if status=="expired" else status

def ensure_subscription(db,school_id):
    row=db.scalar(select(SchoolSubscription).where(SchoolSubscription.school_id==school_id))
    if row:return row
    # 9.1.0 迁移后新出现的学校默认进入免费体验版；已有学校在迁移时会被 grandfather 到学校标准版。
    row=SchoolSubscription(
        school_id=school_id,plan_code="free",status="active",
        source="default_free",note="新学校默认免费体验版"
    )
    db.add(row);db.commit();db.refresh(row)
    return row

def subscription_usage(db,school_id):
    return {
        "teachers":db.scalar(select(func.count()).select_from(User).where(
            User.school_id==school_id,User.role=="teacher",User.active==True
        )) or 0,
        "classes":db.scalar(select(func.count()).select_from(SchoolClass).where(
            SchoolClass.school_id==school_id
        )) or 0,
        "students":db.scalar(select(func.count()).select_from(User).where(
            User.school_id==school_id,User.role=="student",User.active==True
        )) or 0
    }

def subscription_payload(db,school_id):
    row=ensure_subscription(db,school_id)
    plan=_commercial_plan(row.plan_code)
    status=_effective_subscription_status(row)
    usage=subscription_usage(db,school_id)
    plan_limits=dict(plan["limits"])
    quota_overrides=commercial_quota_limits(db,school_id)
    effective_limits=dict(plan_limits)
    for resource,value in quota_overrides.items():
        if resource in ("teachers","classes","students"):
            effective_limits[resource]=value
    now=datetime.utcnow()
    end=None
    if status=="trial":end=row.trial_ends_at
    elif status=="active":end=row.current_period_ends_at
    elif status=="grace":end=row.grace_ends_at
    days=None
    if end:
        days=max(0,(end-now).days + (1 if (end-now).seconds>0 else 0))
    renewal_due=(status=="expired") or bool(end and end<=now+timedelta(days=7))
    school=db.get(School,school_id)
    return {
        "schoolID":school_id,
        "schoolName":school.name if school else "",
        "schoolCode":school.code if school else "",
        "planCode":plan["code"],
        "planName":plan["name"],
        "status":status,
        "statusName":SUBSCRIPTION_STATUS_NAMES.get(status,status),
        "canWrite":status in ("trial","active"),
        "readOnly":status in ("grace","expired"),
        "daysRemaining":days,
        "serviceEndAt":school_local_iso(end) if end else None,
        "renewalDue":renewal_due,
        "trialEndsAt":school_local_iso(row.trial_ends_at) if row.trial_ends_at else None,
        "periodEndsAt":school_local_iso(row.current_period_ends_at) if row.current_period_ends_at else None,
        "graceEndsAt":school_local_iso(row.grace_ends_at) if row.grace_ends_at else None,
        "limits":effective_limits,
        "planLimits":plan_limits,
        "quotaOverrides":quota_overrides,
        "hasQuotaOverride":bool(quota_overrides),
        "usage":usage,
        "features":plan["features"],
        "monthlyPrice":plan["monthlyPrice"],
        "annualPrice":plan["annualPrice"],
        "source":row.source,
        "contact":COMMERCIAL_CONTACT,
        "note":row.note or ""
    }

def require_plan_feature(db,school_id,feature):
    payload=subscription_payload(db,school_id)
    if not payload["features"].get(feature,False):
        name=FEATURE_NAMES.get(feature,feature)
        raise HTTPException(402,f"当前套餐不包含“{name}”，请升级套餐后使用")
    return payload

def require_plan_capacity(db,school_id,resource,amount=1):
    payload=subscription_payload(db,school_id)
    limit=payload["limits"].get(resource)
    used=payload["usage"].get(resource,0)
    if limit is not None and used+amount>limit:
        label={"teachers":"教师","classes":"班级","students":"在读学生"}.get(resource,resource)
        raise HTTPException(402,f"{payload['planName']}的{label}上限为 {limit}，当前已使用 {used}，请升级套餐")
    return payload

def commercial_write_blocked(db,school_id):
    payload=subscription_payload(db,school_id)
    return payload["readOnly"],payload

def commercial_operator(x_commercial_key:Optional[str]=Header(default=None)):
    if not COMMERCIAL_ADMIN_KEY:
        raise HTTPException(503,"尚未配置 COMMERCIAL_ADMIN_KEY，商业运营控制台暂不可用")
    if not x_commercial_key or not secrets.compare_digest(x_commercial_key,COMMERCIAL_ADMIN_KEY):
        raise HTTPException(403,"商业运营密钥无效")
    return True

def commercial_customer_for(db,school_id,create=False):
    row=db.scalar(select(CommercialCustomer).where(CommercialCustomer.school_id==school_id))
    if not row and create:
        row=CommercialCustomer(school_id=school_id,source="existing_school")
        db.add(row);db.flush()
    return row

def commercial_quota_for(db,school_id,create=False):
    row=db.scalar(select(CommercialQuotaOverride).where(CommercialQuotaOverride.school_id==school_id))
    if not row and create:
        row=CommercialQuotaOverride(school_id=school_id,limits_json="{}")
        db.add(row);db.flush()
    return row

def commercial_quota_limits(db,school_id):
    row=commercial_quota_for(db,school_id,False)
    if not row:return {}
    try:
        data=json.loads(row.limits_json or "{}")
        return data if isinstance(data,dict) else {}
    except Exception:
        return {}

def _operator_snapshot(db,school_id):
    school=db.get(School,school_id)
    sub=ensure_subscription(db,school_id) if school else None
    quota=commercial_quota_limits(db,school_id) if school else {}
    return {
        "schoolActive":bool(school.active) if school else False,
        "planCode":sub.plan_code if sub else "",
        "status":_effective_subscription_status(sub) if sub else "",
        "storedStatus":sub.status if sub else "",
        "trialEndsAt":school_local_iso(sub.trial_ends_at) if sub and sub.trial_ends_at else None,
        "periodEndsAt":school_local_iso(sub.current_period_ends_at) if sub and sub.current_period_ends_at else None,
        "graceEndsAt":school_local_iso(sub.grace_ends_at) if sub and sub.grace_ends_at else None,
        "quotaOverrides":quota
    }

def commercial_operation(db,school_id,action,before=None,after=None,detail="",actor="commercial_operator"):
    db.add(CommercialOperationLog(
        school_id=school_id,action=action,actor=actor,
        before_json=json.dumps(before or {},ensure_ascii=False,default=str),
        after_json=json.dumps(after or {},ensure_ascii=False,default=str),
        detail=(detail or "")[:2000]
    ))

def parse_quota_mode(value):
    raw=(value or "inherit").strip().lower()
    if raw in ("inherit","default","plan"):return False,None
    if raw in ("unlimited","none","不限"):return True,None
    try:
        n=int(raw)
    except Exception:
        raise HTTPException(400,"额度必须填写正整数、inherit 或 unlimited")
    if n<1 or n>1000000:raise HTTPException(400,"额度范围应为 1 到 1000000")
    return True,n

def commercial_end_date_utc(value):
    value=(value or "").strip()
    if not value:return None
    try:
        local=datetime.strptime(value,"%Y-%m-%d").replace(hour=23,minute=59,second=59,tzinfo=SCHOOL_TZ)
        return local.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        raise HTTPException(400,"服务到期日期格式应为 YYYY-MM-DD")

def commercial_admins_for(db,school_id):
    rows=db.scalars(select(User).where(User.school_id==school_id,User.role=="admin").order_by(User.active.desc(),User.id)).all()
    return [{"id":x.id,"name":x.name,"username":x.username,"active":bool(x.active)} for x in rows]

ORDER_STATUS_NAMES={
    "pending":"待收款","partial":"部分收款","paid":"已收款","partial_refund":"部分退款","refunded":"已退款","void":"已作废"
}
ORDER_TYPE_NAMES={"service":"服务订单","renewal":"续费订单","new":"新签订单","custom":"其他订单"}

def commercial_money_cents(value,label="金额"):
    try:amount=float(value or 0)
    except Exception:raise HTTPException(400,f"{label}格式无效")
    if amount<0:raise HTTPException(400,f"{label}不能为负数")
    if amount>100000000:raise HTTPException(400,f"{label}过大")
    return int(round(amount*100))

def commercial_payment_date_utc(value):
    raw=(value or "").strip()
    if not raw:return datetime.utcnow()
    try:
        local=datetime.strptime(raw,"%Y-%m-%d").replace(hour=12,minute=0,second=0,tzinfo=SCHOOL_TZ)
        return local.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        raise HTTPException(400,"付款日期格式应为 YYYY-MM-DD")

def commercial_order_no(db,school_id):
    prefix=datetime.now(SCHOOL_TZ).strftime("CY%Y%m%d")
    for _ in range(20):
        value=f"{prefix}-{school_id:04d}-{secrets.token_hex(3).upper()}"
        if not db.scalar(select(CommercialOrder.id).where(CommercialOrder.order_no==value).limit(1)):
            return value
    raise HTTPException(500,"生成订单号失败，请重试")

def commercial_order_money(db,order_id):
    paid=db.scalar(select(func.coalesce(func.sum(CommercialPayment.amount_cents),0)).where(CommercialPayment.order_id==order_id,CommercialPayment.payment_type=="payment")) or 0
    refunded=db.scalar(select(func.coalesce(func.sum(CommercialPayment.amount_cents),0)).where(CommercialPayment.order_id==order_id,CommercialPayment.payment_type=="refund")) or 0
    return int(paid),int(refunded)

def commercial_order_refresh(db,row):
    if row.status=="void":return row
    paid,refunded=commercial_order_money(db,row.id)
    net=max(0,paid-refunded);due=max(0,int(row.amount_due_cents or 0))
    if paid>0 and refunded>=paid:row.status="refunded"
    elif refunded>0:row.status="partial_refund"
    elif due<=0:row.status="paid"
    elif net<=0:row.status="pending"
    elif net<due:row.status="partial"
    else:row.status="paid"
    row.updated_at=datetime.utcnow()
    return row

def commercial_order_json(db,row,school=None,include_payments=True):
    paid,refunded=commercial_order_money(db,row.id)
    net=max(0,paid-refunded)
    outstanding=max(0,(row.amount_due_cents or 0)-net) if row.status not in ("void","refunded") else 0
    data={
        "id":row.id,"orderNo":row.order_no,"schoolID":row.school_id,"schoolName":school.name if school else "",
        "orderType":row.order_type,"orderTypeName":ORDER_TYPE_NAMES.get(row.order_type,row.order_type),
        "planCode":row.plan_code,"planName":_commercial_plan(row.plan_code)["name"] if row.plan_code in COMMERCIAL_PLANS else row.plan_code,
        "title":row.title or "","status":row.status,"statusName":ORDER_STATUS_NAMES.get(row.status,row.status),
        "amountDueYuan":round((row.amount_due_cents or 0)/100,2),"amountPaidYuan":round(paid/100,2),
        "amountRefundedYuan":round(refunded/100,2),"netPaidYuan":round(net/100,2),"outstandingYuan":round(outstanding/100,2),
        "currency":row.currency or "CNY","sourceRenewalID":row.source_renewal_id,"note":row.note or "",
        "voidedAt":school_local_iso(row.voided_at) if row.voided_at else None,"createdAt":school_local_iso(row.created_at),"updatedAt":school_local_iso(row.updated_at)
    }
    if include_payments:
        tx=db.scalars(select(CommercialPayment).where(CommercialPayment.order_id==row.id).order_by(CommercialPayment.payment_at.desc(),CommercialPayment.id.desc())).all()
        data["transactions"]=[{
            "id":x.id,"type":x.payment_type,"typeName":"收款" if x.payment_type=="payment" else "退款",
            "amountYuan":round((x.amount_cents or 0)/100,2),"paymentMethod":x.payment_method or "",
            "paymentReference":x.payment_reference or "","paymentAt":school_local_iso(x.payment_at),"note":x.note or "","createdAt":school_local_iso(x.created_at)
        } for x in tx]
    return data

def create_order_for_renewal(db,renewal):
    existing=db.scalar(select(CommercialOrder).where(CommercialOrder.source_renewal_id==renewal.id).limit(1))
    if existing:return existing
    school=db.get(School,renewal.school_id)
    order=CommercialOrder(
        order_no=commercial_order_no(db,renewal.school_id),school_id=renewal.school_id,order_type="renewal",plan_code=renewal.plan_code,
        title=f"续费/转正式 · {_commercial_plan(renewal.plan_code)['name']}",amount_due_cents=max(0,int(renewal.amount_cents or 0)),
        currency=renewal.currency or "CNY",status="paid",source_renewal_id=renewal.id,note=(renewal.note or "")[:1000],
        created_at=renewal.created_at or datetime.utcnow(),updated_at=renewal.created_at or datetime.utcnow()
    )
    db.add(order);db.flush()
    if order.amount_due_cents>0:
        db.add(CommercialPayment(
            order_id=order.id,school_id=renewal.school_id,payment_type="payment",amount_cents=order.amount_due_cents,currency=order.currency,
            payment_method=(renewal.payment_method or "")[:40],payment_reference=(renewal.payment_reference or "")[:160],
            payment_at=renewal.created_at or datetime.utcnow(),note="由 C2.4 续费登记自动生成"
        ))
    return order

def commercial_school_order_summary(db,school_id):
    rows=db.scalars(select(CommercialOrder).where(CommercialOrder.school_id==school_id).order_by(CommercialOrder.id.desc())).all()
    outstanding=0;net_paid=0
    latest=rows[0] if rows else None
    for row in rows:
        paid,refunded=commercial_order_money(db,row.id);net=max(0,paid-refunded)
        if row.status not in ("void","refunded"):outstanding+=max(0,(row.amount_due_cents or 0)-net)
        if row.status!="void":net_paid+=net
    return {"count":len(rows),"outstandingCents":outstanding,"netPaidCents":net_paid,"latest":latest}

def operator_school_payload(db,school_id):
    payload=subscription_payload(db,school_id)
    customer=commercial_customer_for(db,school_id,False)
    school=db.get(School,school_id)
    latest=db.scalar(select(CommercialFollowUp).where(
        CommercialFollowUp.school_id==school_id
    ).order_by(CommercialFollowUp.id.desc()).limit(1))
    today=datetime.now(SCHOOL_TZ).date().isoformat()
    next_date=(latest.next_followup_date or "") if latest else ""
    latest_renewal=db.scalar(select(CommercialRenewal).where(
        CommercialRenewal.school_id==school_id
    ).order_by(CommercialRenewal.id.desc()).limit(1))
    renewal_count=db.scalar(select(func.count()).select_from(CommercialRenewal).where(CommercialRenewal.school_id==school_id)) or 0
    renewal_total_cents=db.scalar(select(func.coalesce(func.sum(CommercialRenewal.amount_cents),0)).where(CommercialRenewal.school_id==school_id)) or 0
    order_summary=commercial_school_order_summary(db,school_id)
    latest_order=order_summary["latest"]
    payload.update({
        "schoolActive":bool(school.active) if school else False,
        "operatorStatus":"paused" if school and not school.active else payload["status"],
        "operatorStatusName":"已暂停" if school and not school.active else payload["statusName"],
        "contactName":customer.contact_name if customer else "",
        "contactValue":customer.contact_value if customer else "",
        "customerSource":customer.source if customer else "",
        "customerNote":customer.note if customer else "",
        "admins":commercial_admins_for(db,school_id),
        "latestFollowUp":{
            "id":latest.id,
            "type":latest.follow_type,
            "content":latest.content,
            "nextFollowupDate":latest.next_followup_date,
            "createdAt":school_local_iso(latest.created_at)
        } if latest else None,
        "nextFollowupDate":next_date,
        "followupDue":bool(next_date and next_date<=today),
        "renewalCount":int(renewal_count),
        "renewalTotalYuan":round(int(renewal_total_cents)/100,2),
        "orderCount":int(order_summary["count"]),
        "outstandingYuan":round(int(order_summary["outstandingCents"])/100,2),
        "orderNetPaidYuan":round(int(order_summary["netPaidCents"])/100,2),
        "latestOrder":commercial_order_json(db,latest_order,school,False) if latest_order else None,
        "latestRenewal":{
            "id":latest_renewal.id,
            "planCode":latest_renewal.plan_code,
            "serviceStartAt":school_local_iso(latest_renewal.service_start_at),
            "serviceEndAt":school_local_iso(latest_renewal.service_end_at),
            "amountYuan":round((latest_renewal.amount_cents or 0)/100,2),
            "paymentMethod":latest_renewal.payment_method,
            "paymentReference":latest_renewal.payment_reference,
            "note":latest_renewal.note,
            "createdAt":school_local_iso(latest_renewal.created_at)
        } if latest_renewal else None
    })
    return payload

def _json_value(v):
    if isinstance(v,datetime): return v.isoformat()
    return v

def model_dict(obj,exclude=None):
    exclude=set(exclude or [])
    return {c.key:_json_value(getattr(obj,c.key)) for c in sa_inspect(obj).mapper.column_attrs if c.key not in exclude}

def deletion_json(db,row):
    if not row:return None
    target=db.get(User,row.user_id);resolver=db.get(User,row.resolved_by) if row.resolved_by else None
    return {"id":row.id,"userID":row.user_id,"userName":target.name if target else "","username":target.username if target else "","role":target.role if target else "","reason":row.reason,"status":row.status,"requestedAt":school_local_iso(row.requested_at),"resolvedAt":school_local_iso(row.resolved_at) if row.resolved_at else None,"resolvedBy":resolver.name if resolver else "","resolutionNote":row.resolution_note}

def run_schema_migrations(db):
    migrations=[
        ("8.3.0","上线基础：迁移登记、系统健康、数据导出、注销申请与安全基线"),
        ("9.1.0","商业版 C1：学校套餐、试用/到期状态、容量限制与功能权限"),
        ("9.2.0","商业版 C2：运营控制台、客户建档、试用开通、续费与到期管理"),
        ("9.2.2","商业版 C2.2：客户跟进记录、下次跟进日期与到期提醒"),
        ("9.2.3","商业版 C2.3：学校状态控制、额度覆盖、搜索筛选与运营操作留痕"),
        ("9.2.4","商业版 C2.4：试用/到期自动生效、续费登记、服务期延长与续费记录"),
        ("9.2.5","商业版 C2.5：订单、应收实收、分次收款、退款作废与收费台账")
    ]
    changed=False
    for version,description in migrations:
        if db.get(SchemaMigration,version):
            continue
        if version=="9.1.0":
            for school in db.scalars(select(School).order_by(School.id)).all():
                exists=db.scalar(select(SchoolSubscription).where(SchoolSubscription.school_id==school.id))
                if not exists:
                    db.add(SchoolSubscription(school_id=school.id,plan_code="school_standard",status="active",source="grandfathered_v910",note="V9.1.0 商业化迁移：既有学校权益保留"))
                    db.add(SubscriptionEvent(school_id=school.id,action="grandfather",plan_code="school_standard",status="active",detail="V9.1.0 迁移自动保留既有学校权益"))
        elif version=="9.2.0":
            for school in db.scalars(select(School).order_by(School.id)).all():
                if not db.scalar(select(CommercialCustomer).where(CommercialCustomer.school_id==school.id)):
                    db.add(CommercialCustomer(school_id=school.id,source="existing_school",note="V9.2.0 迁移自动建立商业客户档案"))
        elif version=="9.2.5":
            for renewal in db.scalars(select(CommercialRenewal).order_by(CommercialRenewal.id)).all():
                create_order_for_renewal(db,renewal)
        db.add(SchemaMigration(version=version,description=description));changed=True
    if changed:db.commit()

def school_backup_payload(db,school_id):
    school=db.get(School,school_id)
    users=db.scalars(select(User).where(User.school_id==school_id).order_by(User.id)).all();user_ids=[x.id for x in users]
    classes=db.scalars(select(SchoolClass).where(SchoolClass.school_id==school_id).order_by(SchoolClass.id)).all();class_ids=[x.id for x in classes]
    groups=db.scalars(select(ClassroomGroup).where(ClassroomGroup.school_id==school_id).order_by(ClassroomGroup.id)).all();group_ids=[x.id for x in groups]
    def rows(model): return [model_dict(x) for x in db.scalars(select(model).where(model.school_id==school_id).order_by(model.id)).all()]
    return {
      "meta":{"appVersion":APP_VERSION,"schemaVersion":SCHEMA_VERSION,"generatedAt":datetime.utcnow().isoformat(),"school":model_dict(school) if school else None},
      "users":[model_dict(x,{"password_hash"}) for x in users],
      "userSecurity":[model_dict(x) for x in db.scalars(select(UserSecurity).where(UserSecurity.user_id.in_(user_ids))).all()] if user_ids else [],
      "classes":[model_dict(x) for x in classes],
      "classStudents":[model_dict(x) for x in db.scalars(select(ClassStudent).where(ClassStudent.class_id.in_(class_ids))).all()] if class_ids else [],
      "classHistory":rows(StudentClassHistory),"assignmentRecipients":rows(AssignmentRecipient),
      "parentStudents":[model_dict(x) for x in db.scalars(select(ParentStudent).where(ParentStudent.parent_id.in_(user_ids))).all()] if user_ids else [],
      "questions":rows(Question),"papers":rows(Paper),"assignments":rows(Assignment),"submissions":rows(Submission),
      "pointRules":rows(PointRule),"pointLedger":rows(PointLedger),"rewardItems":rows(RewardItem),"rewardRedemptions":rows(RewardRedemption),
      "autoRewardRules":rows(AutoRewardRule),"autoRewardGrants":rows(AutoRewardGrant),
      "classroomGroups":[model_dict(x) for x in groups],
      "classroomGroupMembers":[model_dict(x) for x in db.scalars(select(ClassroomGroupMember).where(ClassroomGroupMember.group_id.in_(group_ids))).all()] if group_ids else [],
      "studentFollowups":rows(StudentFollowUp),"studentFollowupLogs":rows(StudentFollowUpLog),"classTodos":rows(ClassTodo),
      "auditLogs":rows(AuditLog),"accountDeletionRequests":rows(AccountDeletionRequest),
      "subscription":model_dict(ensure_subscription(db,school_id)),
      "commercialCustomer":model_dict(commercial_customer_for(db,school_id,False)) if commercial_customer_for(db,school_id,False) else None,
      "commercialFollowUps":[model_dict(x) for x in db.scalars(select(CommercialFollowUp).where(CommercialFollowUp.school_id==school_id).order_by(CommercialFollowUp.id)).all()],
      "commercialRenewals":[model_dict(x) for x in db.scalars(select(CommercialRenewal).where(CommercialRenewal.school_id==school_id).order_by(CommercialRenewal.id)).all()],
      "subscriptionEvents":[model_dict(x) for x in db.scalars(select(SubscriptionEvent).where(SubscriptionEvent.school_id==school_id).order_by(SubscriptionEvent.id)).all()]
    }

def personal_audit_export_row(row):
    # 个人数据导出只保留“本人做过什么、何时做”的审计事实。
    # detail 可能包含学生、家长或其他第三方的姓名/用户名/业务内容，
    # 因此个人导出统一脱敏；完整 detail 仅管理员学校备份保留。
    return {
        "id":row.id,
        "school_id":row.school_id,
        "user_id":row.user_id,
        "action":row.action,
        "detail":"[已脱敏：完整操作详情仅学校管理员备份可见]" if (row.detail or "").strip() else "",
        "detailRedacted":True,
        "created_at":_json_value(row.created_at)
    }

def account_export_payload(db,u):
    sec=security_for(db,u);school=db.get(School,u.school_id)
    audit_rows=db.scalars(select(AuditLog).where(
        AuditLog.school_id==u.school_id,AuditLog.user_id==u.id
    ).order_by(AuditLog.id.desc()).limit(500)).all()
    data={
      "meta":{
        "appVersion":APP_VERSION,
        "generatedAt":datetime.utcnow().isoformat(),
        "schoolName":school.name if school else "",
        "auditDetailPolicy":"redacted"
      },
      "profile":model_dict(u,{"password_hash"}),
      "security":{
        "mustChangePassword":bool(sec.must_change_password),
        "passwordChangedAt":_json_value(sec.password_changed_at)
      },
      "auditActions":[personal_audit_export_row(x) for x in audit_rows]
    }
    if u.role=="student":
        data["classHistory"]=[model_dict(x) for x in db.scalars(select(StudentClassHistory).where(StudentClassHistory.school_id==u.school_id,StudentClassHistory.student_id==u.id).order_by(StudentClassHistory.id)).all()]
        data["submissions"]=[model_dict(x) for x in db.scalars(select(Submission).where(Submission.school_id==u.school_id,Submission.student_id==u.id).order_by(Submission.id)).all()]
        data["pointLedger"]=[model_dict(x) for x in db.scalars(select(PointLedger).where(PointLedger.school_id==u.school_id,PointLedger.student_id==u.id).order_by(PointLedger.id)).all()]
        data["rewards"]=[model_dict(x) for x in db.scalars(select(RewardRedemption).where(RewardRedemption.school_id==u.school_id,RewardRedemption.student_id==u.id).order_by(RewardRedemption.id)).all()]
        data["followups"]=[model_dict(x) for x in db.scalars(select(StudentFollowUp).where(StudentFollowUp.school_id==u.school_id,StudentFollowUp.student_id==u.id).order_by(StudentFollowUp.id)).all()]
        data["followupLogs"]=[model_dict(x) for x in db.scalars(select(StudentFollowUpLog).where(StudentFollowUpLog.school_id==u.school_id,StudentFollowUpLog.student_id==u.id).order_by(StudentFollowUpLog.id)).all()]
    elif u.role=="parent":
        links=db.scalars(select(ParentStudent).where(ParentStudent.parent_id==u.id)).all();data["linkedStudents"]=[{"studentID":x.student_id,"studentName":(db.get(User,x.student_id).name if db.get(User,x.student_id) else "")} for x in links]
    elif u.role=="teacher":
        data["managedClasses"]=[model_dict(x) for x in db.scalars(select(SchoolClass).where(SchoolClass.school_id==u.school_id,SchoolClass.teacher_id==u.id).order_by(SchoolClass.id)).all()]
    return data

def legal_page(title,body):
    html=f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#5362e8"><title>{title} - 长缨辅学</title><style>body{{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;background:#f4f6fb;color:#1f2738;margin:0;min-height:100dvh;-webkit-text-size-adjust:100%}}main{{max-width:760px;margin:0 auto;padding:calc(28px + env(safe-area-inset-top)) calc(20px + env(safe-area-inset-right)) calc(90px + env(safe-area-inset-bottom)) calc(20px + env(safe-area-inset-left))}}article{{background:#fff;border:1px solid #e5e8f0;border-radius:20px;padding:24px;line-height:1.8}}h1{{margin-top:0}}.note{{background:#fff7e7;padding:12px;border-radius:12px;color:#7b5719}}</style></head><body><main><article><h1>{title}</h1>'+body+'<p class="note">正式公开上架前，请根据实际运营主体、所在地区法规、学校数据处理协议和联系方式完成最终法律文本确认。</p></article></main></body></html>'
    return HTMLResponse(html,headers={"Cache-Control":"no-store"})

# ---------------- App ----------------
app=FastAPI(title="长缨辅学 V9.2.5 商业版 C2.5",version=APP_VERSION)
_cors_raw=os.getenv("CORS_ORIGINS","*").strip()
_cors_origins=["*"] if _cors_raw=="*" else [x.strip() for x in _cors_raw.split(",") if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=_cors_origins,allow_credentials=False,allow_methods=["*"],allow_headers=["*"])

@app.middleware("http")
async def production_security_headers(request:Request,call_next):
    response=await call_next(request)
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["X-Frame-Options"]="DENY"
    response.headers["Referrer-Policy"]="strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"]="camera=(), microphone=(), geolocation=()"
    response.headers["X-App-Version"]=APP_VERSION
    response.headers["X-Release-Channel"]=RELEASE_CHANNEL
    if (request.headers.get("x-forwarded-proto") or request.url.scheme)=="https":response.headers["Strict-Transport-Security"]="max-age=31536000; includeSubDomains"
    return response

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
        run_schema_migrations(db)


@app.get("/commercial/plans")
def commercial_plans():
    return {
        "currency":"CNY",
        "manualActivation":True,
        "paymentAutomation":False,
        "plans":[COMMERCIAL_PLANS[k] for k in ("free","teacher_pro","school_basic","school_standard","custom")]
    }

@app.get("/subscription/me")
def my_subscription(u:User=Depends(current_user),db:Session=Depends(get_db)):
    return subscription_payload(db,u.school_id)

@app.get("/operator/schools")
def operator_schools(_ok:bool=Depends(commercial_operator),db:Session=Depends(get_db)):
    return [operator_school_payload(db,school.id) for school in db.scalars(select(School).order_by(School.id.desc())).all()]

@app.get("/operator/summary")
def operator_summary(_ok:bool=Depends(commercial_operator),db:Session=Depends(get_db)):
    rows=[operator_school_payload(db,x.id) for x in db.scalars(select(School).order_by(School.id)).all()]
    now=datetime.utcnow();trial_soon=0;service_soon=0
    for x in rows:
        days=x.get("daysRemaining")
        if x.get("schoolActive") and x["status"]=="trial" and days is not None and 0<=days<=7:trial_soon+=1
        if x.get("schoolActive") and x["status"] in ("trial","active","grace") and days is not None and 0<=days<=7:service_soon+=1
    since=now-timedelta(days=30)
    renewals30=db.scalar(select(func.count()).select_from(CommercialRenewal).where(CommercialRenewal.created_at>=since)) or 0
    revenue30=db.scalar(select(func.coalesce(func.sum(CommercialRenewal.amount_cents),0)).where(CommercialRenewal.created_at>=since)) or 0
    orders=db.scalars(select(CommercialOrder).order_by(CommercialOrder.id.desc())).all()
    unpaid_orders=0;receivable_cents=0
    for order in orders:
        paid,refunded=commercial_order_money(db,order.id);net=max(0,paid-refunded)
        if order.status not in ("void","refunded"):
            remaining=max(0,(order.amount_due_cents or 0)-net)
            if remaining>0:unpaid_orders+=1;receivable_cents+=remaining
    collected30=db.scalar(select(func.coalesce(func.sum(CommercialPayment.amount_cents),0)).where(CommercialPayment.payment_type=="payment",CommercialPayment.payment_at>=since)) or 0
    refunded30=db.scalar(select(func.coalesce(func.sum(CommercialPayment.amount_cents),0)).where(CommercialPayment.payment_type=="refund",CommercialPayment.payment_at>=since)) or 0
    orders30=db.scalar(select(func.count()).select_from(CommercialOrder).where(CommercialOrder.created_at>=since)) or 0
    return {
        "totalSchools":len(rows),
        "active":sum(1 for x in rows if x["status"]=="active" and x.get("schoolActive")),
        "trial":sum(1 for x in rows if x["status"]=="trial" and x.get("schoolActive")),
        "grace":sum(1 for x in rows if x["status"]=="grace" and x.get("schoolActive")),
        "expired":sum(1 for x in rows if x["status"]=="expired" and x.get("schoolActive")),
        "paused":sum(1 for x in rows if not x.get("schoolActive")),
        "trialEnding7d":trial_soon,
        "serviceEnding7d":service_soon,
        "renewalDue":sum(1 for x in rows if x.get("schoolActive") and x.get("renewalDue")),
        "renewals30d":int(renewals30),
        "renewalRevenue30dYuan":round(int(revenue30)/100,2),
        "orders30d":int(orders30),
        "unpaidOrders":int(unpaid_orders),
        "receivableOutstandingYuan":round(int(receivable_cents)/100,2),
        "cashCollected30dYuan":round(int(collected30)/100,2),
        "refund30dYuan":round(int(refunded30)/100,2),
        "netRevenue30dYuan":round((int(collected30)-int(refunded30))/100,2),
        "activeStudents":sum((x.get("usage") or {}).get("students",0) for x in rows),
        "activeTeachers":sum((x.get("usage") or {}).get("teachers",0) for x in rows),
        "missingContact":sum(1 for x in rows if not (x.get("contactName") or "").strip() and not (x.get("contactValue") or "").strip()),
        "followupDue":sum(1 for x in rows if x.get("followupDue"))
    }

@app.get("/operator/orders")
def operator_orders(limit:int=300,school_id:Optional[int]=None,status:Optional[str]=None,_ok:bool=Depends(commercial_operator),db:Session=Depends(get_db)):
    limit=max(1,min(limit,500));q=select(CommercialOrder)
    if school_id is not None:q=q.where(CommercialOrder.school_id==school_id)
    if status:q=q.where(CommercialOrder.status==status)
    rows=db.scalars(q.order_by(CommercialOrder.id.desc()).limit(limit)).all()
    school_ids={x.school_id for x in rows};smap={x.id:x for x in db.scalars(select(School).where(School.id.in_(school_ids))).all()} if school_ids else {}
    return [commercial_order_json(db,x,smap.get(x.school_id),True) for x in rows]

@app.get("/operator/schools/{school_id}/orders")
def operator_school_orders(school_id:int,limit:int=200,_ok:bool=Depends(commercial_operator),db:Session=Depends(get_db)):
    school=db.get(School,school_id)
    if not school:raise HTTPException(404,"学校不存在")
    limit=max(1,min(limit,300));rows=db.scalars(select(CommercialOrder).where(CommercialOrder.school_id==school_id).order_by(CommercialOrder.id.desc()).limit(limit)).all()
    return [commercial_order_json(db,x,school,True) for x in rows]

@app.post("/operator/schools/{school_id}/orders")
def operator_add_order(school_id:int,b:OperatorOrderCreateBody,_ok:bool=Depends(commercial_operator),db:Session=Depends(get_db)):
    school=db.get(School,school_id)
    if not school:raise HTTPException(404,"学校不存在")
    order_type=(b.order_type or "service").strip().lower()
    if order_type not in ORDER_TYPE_NAMES:raise HTTPException(400,"订单类型无效")
    plan_code=(b.plan_code or ensure_subscription(db,school_id).plan_code or "school_standard").strip()
    if plan_code and plan_code not in COMMERCIAL_PLANS:raise HTTPException(400,"套餐代码无效")
    due=commercial_money_cents(b.amount_due_yuan,"应收金额");paid=commercial_money_cents(b.amount_paid_yuan,"本次实收")
    if paid>due and due>0:raise HTTPException(400,"本次实收不能大于应收金额")
    now=datetime.utcnow();title=(b.title or "").strip()[:180] or f"{ORDER_TYPE_NAMES[order_type]} · {_commercial_plan(plan_code)['name']}"
    row=CommercialOrder(order_no=commercial_order_no(db,school_id),school_id=school_id,order_type=order_type,plan_code=plan_code,title=title,amount_due_cents=due,currency="CNY",status="paid" if due==0 else "pending",note=(b.note or "")[:1000],created_at=now,updated_at=now)
    db.add(row);db.flush()
    if paid>0:
        db.add(CommercialPayment(order_id=row.id,school_id=school_id,payment_type="payment",amount_cents=paid,currency="CNY",payment_method=(b.payment_method or "")[:40],payment_reference=(b.payment_reference or "")[:160],payment_at=commercial_payment_date_utc(b.payment_date),note="新建订单首笔收款"))
        db.flush()
    commercial_order_refresh(db,row);db.flush()
    after=commercial_order_json(db,row,school,True)
    commercial_operation(db,school_id,"order_create",{},after,f"订单 {row.order_no}；应收 ¥{due/100:.2f}；首收 ¥{paid/100:.2f}；{(b.note or '')[:300]}")
    db.commit();db.refresh(row)
    return {"ok":True,"order":commercial_order_json(db,row,school,True),"school":operator_school_payload(db,school_id)}

@app.post("/operator/orders/{order_id}/payments")
def operator_add_payment(order_id:int,b:OperatorPaymentCreateBody,_ok:bool=Depends(commercial_operator),db:Session=Depends(get_db)):
    row=db.get(CommercialOrder,order_id)
    if not row:raise HTTPException(404,"订单不存在")
    if row.status=="void":raise HTTPException(400,"已作废订单不能收款")
    amount=commercial_money_cents(b.amount_yuan,"收款金额")
    if amount<=0:raise HTTPException(400,"收款金额必须大于 0")
    paid,refunded=commercial_order_money(db,row.id);net=max(0,paid-refunded)
    due=max(0,row.amount_due_cents or 0)
    if due>0 and net+amount>due:raise HTTPException(400,f"本次收款超过剩余应收 ¥{max(0,due-net)/100:.2f}")
    before=commercial_order_json(db,row,db.get(School,row.school_id),True)
    tx=CommercialPayment(order_id=row.id,school_id=row.school_id,payment_type="payment",amount_cents=amount,currency=row.currency or "CNY",payment_method=(b.payment_method or "")[:40],payment_reference=(b.payment_reference or "")[:160],payment_at=commercial_payment_date_utc(b.payment_date),note=(b.note or "")[:1000])
    db.add(tx);db.flush();commercial_order_refresh(db,row);db.flush();after=commercial_order_json(db,row,db.get(School,row.school_id),True)
    commercial_operation(db,row.school_id,"order_payment",before,after,f"订单 {row.order_no} 收款 ¥{amount/100:.2f}；{(b.payment_method or '')[:40]}；{(b.note or '')[:300]}")
    db.commit();return {"ok":True,"order":commercial_order_json(db,row,db.get(School,row.school_id),True)}

@app.post("/operator/orders/{order_id}/refunds")
def operator_add_refund(order_id:int,b:OperatorRefundCreateBody,_ok:bool=Depends(commercial_operator),db:Session=Depends(get_db)):
    row=db.get(CommercialOrder,order_id)
    if not row:raise HTTPException(404,"订单不存在")
    if row.status=="void":raise HTTPException(400,"已作废订单不能退款")
    amount=commercial_money_cents(b.amount_yuan,"退款金额")
    if amount<=0:raise HTTPException(400,"退款金额必须大于 0")
    paid,refunded=commercial_order_money(db,row.id);available=max(0,paid-refunded)
    if amount>available:raise HTTPException(400,f"退款金额超过可退余额 ¥{available/100:.2f}")
    before=commercial_order_json(db,row,db.get(School,row.school_id),True)
    tx=CommercialPayment(order_id=row.id,school_id=row.school_id,payment_type="refund",amount_cents=amount,currency=row.currency or "CNY",payment_method=(b.payment_method or "")[:40],payment_reference=(b.payment_reference or "")[:160],payment_at=commercial_payment_date_utc(b.payment_date),note=(b.note or "")[:1000])
    db.add(tx);db.flush();commercial_order_refresh(db,row);db.flush();after=commercial_order_json(db,row,db.get(School,row.school_id),True)
    commercial_operation(db,row.school_id,"order_refund",before,after,f"订单 {row.order_no} 退款 ¥{amount/100:.2f}；{(b.payment_method or '')[:40]}；{(b.note or '')[:300]}")
    db.commit();return {"ok":True,"order":commercial_order_json(db,row,db.get(School,row.school_id),True)}

@app.post("/operator/orders/{order_id}/void")
def operator_void_order(order_id:int,b:OperatorOrderVoidBody,_ok:bool=Depends(commercial_operator),db:Session=Depends(get_db)):
    row=db.get(CommercialOrder,order_id)
    if not row:raise HTTPException(404,"订单不存在")
    if row.status=="void":return {"ok":True,"order":commercial_order_json(db,row,db.get(School,row.school_id),True)}
    paid,refunded=commercial_order_money(db,row.id)
    if paid-refunded>0:raise HTTPException(400,"订单仍有未退实收款，需先退款后才能作废")
    before=commercial_order_json(db,row,db.get(School,row.school_id),True);row.status="void";row.voided_at=datetime.utcnow();row.updated_at=datetime.utcnow()
    if (b.note or "").strip():row.note=((row.note or "")+"\n作废："+(b.note or "").strip())[:1000]
    db.flush();after=commercial_order_json(db,row,db.get(School,row.school_id),True)
    commercial_operation(db,row.school_id,"order_void",before,after,f"订单 {row.order_no} 作废；{(b.note or '')[:300]}")
    db.commit();return {"ok":True,"order":commercial_order_json(db,row,db.get(School,row.school_id),True)}

def commercial_renewal_json(row,school=None):
    return {
        "id":row.id,"schoolID":row.school_id,"schoolName":school.name if school else "",
        "planCode":row.plan_code,"planName":_commercial_plan(row.plan_code)["name"],
        "serviceStartAt":school_local_iso(row.service_start_at),"serviceEndAt":school_local_iso(row.service_end_at),
        "amountYuan":round((row.amount_cents or 0)/100,2),"currency":row.currency or "CNY",
        "paymentMethod":row.payment_method or "","paymentReference":row.payment_reference or "",
        "note":row.note or "","createdAt":school_local_iso(row.created_at)
    }

@app.get("/operator/renewals")
def operator_renewals(limit:int=200,school_id:Optional[int]=None,_ok:bool=Depends(commercial_operator),db:Session=Depends(get_db)):
    limit=max(1,min(limit,500))
    q=select(CommercialRenewal)
    if school_id is not None:q=q.where(CommercialRenewal.school_id==school_id)
    rows=db.scalars(q.order_by(CommercialRenewal.id.desc()).limit(limit)).all()
    school_ids={x.school_id for x in rows}
    smap={x.id:x for x in db.scalars(select(School).where(School.id.in_(school_ids))).all()} if school_ids else {}
    return [commercial_renewal_json(x,smap.get(x.school_id)) for x in rows]

@app.get("/operator/schools/{school_id}/renewals")
def operator_school_renewals(school_id:int,limit:int=100,_ok:bool=Depends(commercial_operator),db:Session=Depends(get_db)):
    school=db.get(School,school_id)
    if not school:raise HTTPException(404,"学校不存在")
    limit=max(1,min(limit,300))
    rows=db.scalars(select(CommercialRenewal).where(CommercialRenewal.school_id==school_id).order_by(CommercialRenewal.id.desc()).limit(limit)).all()
    return [commercial_renewal_json(x,school) for x in rows]

@app.post("/operator/schools/{school_id}/renewals")
def operator_add_renewal(school_id:int,b:OperatorRenewalCreateBody,_ok:bool=Depends(commercial_operator),db:Session=Depends(get_db)):
    school=db.get(School,school_id)
    if not school:raise HTTPException(404,"学校不存在")
    row=ensure_subscription(db,school_id)
    plan_code=(b.plan_code or row.plan_code or "school_standard").strip()
    if plan_code not in COMMERCIAL_PLANS:raise HTTPException(400,"套餐代码无效")
    now=datetime.utcnow();before=_operator_snapshot(db,school_id)
    exact_end=commercial_end_date_utc(b.end_date) if (b.end_date or "").strip() else None
    if exact_end is not None:
        if exact_end<=now:raise HTTPException(400,"续费后的服务到期日必须晚于今天")
        service_start=now
        service_end=exact_end
    else:
        days=max(1,min(int(b.period_days or 365),3650))
        current_end=row.current_period_ends_at
        service_start=current_end if current_end and current_end>now else now
        service_end=service_start+timedelta(days=days)
    grace=max(0,min(int(b.grace_days or 7),60))
    try:amount=max(0.0,float(b.amount_yuan or 0))
    except:raise HTTPException(400,"续费金额格式无效")
    if amount>100000000:raise HTTPException(400,"续费金额过大")
    amount_cents=int(round(amount*100))
    row.plan_code=plan_code;row.status="active";row.trial_ends_at=None
    row.current_period_ends_at=service_end;row.grace_ends_at=service_end+timedelta(days=grace) if grace else None
    row.updated_at=now;row.source="renewal";row.note=(b.note or "")[:1000]
    renewal=CommercialRenewal(
        school_id=school_id,plan_code=plan_code,service_start_at=service_start,service_end_at=service_end,
        amount_cents=amount_cents,currency="CNY",payment_method=(b.payment_method or "")[:40],
        payment_reference=(b.payment_reference or "")[:160],note=(b.note or "")[:1000]
    )
    db.add(renewal);db.flush()
    order=create_order_for_renewal(db,renewal)
    db.add(SubscriptionEvent(
        school_id=school_id,action="renewal",plan_code=plan_code,status="active",
        detail=f"service_start={service_start.isoformat()};service_end={service_end.isoformat()};amount_yuan={amount:.2f};payment_method={(b.payment_method or '')[:40]};reference={(b.payment_reference or '')[:120]};note={(b.note or '')[:300]}"
    ))
    db.flush();after=_operator_snapshot(db,school_id)
    commercial_operation(db,school_id,"renewal_add",before,after,f"续费 ¥{amount:.2f}；订单 {order.order_no}；{(b.payment_method or '未登记付款方式')[:40]}；服务至 {school_local_iso(service_end)}；{(b.note or '')[:300]}")
    db.commit();db.refresh(renewal);db.refresh(order)
    return {"ok":True,"renewal":commercial_renewal_json(renewal,school),"order":commercial_order_json(db,order,school,True),"school":operator_school_payload(db,school_id)}

@app.get("/operator/schools/{school_id}/events")
def operator_school_events(school_id:int,limit:int=80,_ok:bool=Depends(commercial_operator),db:Session=Depends(get_db)):
    if not db.get(School,school_id):raise HTTPException(404,"学校不存在")
    limit=max(1,min(limit,200));rows=db.scalars(select(SubscriptionEvent).where(SubscriptionEvent.school_id==school_id).order_by(SubscriptionEvent.id.desc()).limit(limit)).all()
    return [{"id":x.id,"action":x.action,"planCode":x.plan_code,"status":x.status,"detail":x.detail,"createdAt":school_local_iso(x.created_at)} for x in rows]

@app.get("/operator/operations")
def operator_operations(limit:int=200,school_id:Optional[int]=None,_ok:bool=Depends(commercial_operator),db:Session=Depends(get_db)):
    limit=max(1,min(limit,500))
    if school_id is None:
        q=select(CommercialOperationLog).order_by(CommercialOperationLog.id.desc()).limit(limit)
    else:
        q=select(CommercialOperationLog).where(CommercialOperationLog.school_id==school_id).order_by(CommercialOperationLog.id.desc()).limit(limit)
    rows=db.scalars(q).all();school_ids={x.school_id for x in rows};schools_map={x.id:x for x in db.scalars(select(School).where(School.id.in_(school_ids))).all()} if school_ids else {}
    action_names={"school_state":"学校状态","quota_update":"额度调整","subscription_update":"套餐/服务期调整","renewal_add":"续费登记","order_create":"新建订单","order_payment":"订单收款","order_refund":"订单退款","order_void":"订单作废","customer_update":"客户资料","admin_password_reset":"管理员密码重置","followup_add":"商业跟进","school_create":"新建客户"}
    out=[]
    for x in rows:
        try:before=json.loads(x.before_json or "{}")
        except:before={}
        try:after=json.loads(x.after_json or "{}")
        except:after={}
        school=schools_map.get(x.school_id)
        out.append({"id":x.id,"schoolID":x.school_id,"schoolName":school.name if school else f"学校{x.school_id}","action":x.action,"actionName":action_names.get(x.action,x.action),"actor":x.actor,"before":before,"after":after,"detail":x.detail,"createdAt":school_local_iso(x.created_at)})
    return out

@app.post("/operator/schools/{school_id}/state")
def operator_school_state(school_id:int,b:OperatorSchoolStateBody,_ok:bool=Depends(commercial_operator),db:Session=Depends(get_db)):
    school=db.get(School,school_id)
    if not school:raise HTTPException(404,"学校不存在")
    before=_operator_snapshot(db,school_id)
    school.active=bool(b.active)
    sub=ensure_subscription(db,school_id)
    db.add(SubscriptionEvent(school_id=school_id,action="school_resume" if school.active else "school_pause",plan_code=sub.plan_code,status=_effective_subscription_status(sub),detail=(b.note or "")[:1000]))
    db.flush();after=_operator_snapshot(db,school_id)
    commercial_operation(db,school_id,"school_state",before,after,(b.note or "")[:1000])
    db.commit()
    return operator_school_payload(db,school_id)

@app.post("/operator/schools/{school_id}/quota")
def operator_school_quota(school_id:int,b:OperatorQuotaUpdateBody,_ok:bool=Depends(commercial_operator),db:Session=Depends(get_db)):
    if not db.get(School,school_id):raise HTTPException(404,"学校不存在")
    before=_operator_snapshot(db,school_id);limits={}
    for resource,raw in (("teachers",b.teachers),("classes",b.classes),("students",b.students)):
        include,value=parse_quota_mode(raw)
        if include:limits[resource]=value
    row=commercial_quota_for(db,school_id,True)
    row.limits_json=json.dumps(limits,ensure_ascii=False);row.note=(b.note or "")[:1000];row.updated_at=datetime.utcnow()
    db.flush();after=_operator_snapshot(db,school_id)
    sub=ensure_subscription(db,school_id)
    db.add(SubscriptionEvent(school_id=school_id,action="quota_update",plan_code=sub.plan_code,status=_effective_subscription_status(sub),detail=f"overrides={json.dumps(limits,ensure_ascii=False)};note={row.note}"))
    commercial_operation(db,school_id,"quota_update",before,after,row.note)
    db.commit()
    return operator_school_payload(db,school_id)

@app.post("/operator/schools/create")
def operator_create_school(b:OperatorSchoolCreateBody,_ok:bool=Depends(commercial_operator),db:Session=Depends(get_db)):
    school_name=b.school_name.strip();school_code=b.school_code.strip();admin_name=b.admin_name.strip();admin_username=b.admin_username.strip();admin_password=b.admin_password
    if not school_name or not school_code:raise HTTPException(400,"学校名称和学校代码不能为空")
    if len(school_code)>40:raise HTTPException(400,"学校代码过长")
    if not admin_name or not admin_username:raise HTTPException(400,"管理员姓名和账号不能为空")
    if not password_ok(admin_password):raise HTTPException(400,"初始密码至少8位，并同时包含字母和数字")
    if b.plan_code not in COMMERCIAL_PLANS:raise HTTPException(400,"套餐代码无效")
    if db.scalar(select(School).where(School.name==school_name)):raise HTTPException(400,"学校名称已存在")
    if db.scalar(select(School).where(School.code==school_code)):raise HTTPException(400,"学校代码已存在")
    if db.scalar(select(User).where(User.username==admin_username)):raise HTTPException(400,"管理员账号已存在")
    school=School(name=school_name,code=school_code,active=True);db.add(school);db.flush()
    admin=User(school_id=school.id,username=admin_username,password_hash=hash_password(admin_password),name=admin_name,role="admin",active=True);db.add(admin);db.flush();db.add(UserSecurity(user_id=admin.id,must_change_password=True,failed_login_count=0))
    now=datetime.utcnow();status=(b.status or "trial").lower()
    if status not in ("trial","active","grace","expired"):raise HTTPException(400,"订阅状态无效")
    row=SchoolSubscription(school_id=school.id,plan_code=b.plan_code,status=status,started_at=now,source="operator_create",note=(b.note or "")[:1000])
    if status=="trial":row.trial_ends_at=now+timedelta(days=max(1,min(int(b.trial_days or 14),90)))
    elif status=="active":
        days=max(0,min(int(b.period_days or 365),3650));grace=max(0,min(int(b.grace_days or 7),60))
        if days:
            row.current_period_ends_at=now+timedelta(days=days)
            if grace:row.grace_ends_at=row.current_period_ends_at+timedelta(days=grace)
    elif status=="grace":row.current_period_ends_at=now;row.grace_ends_at=now+timedelta(days=max(1,min(int(b.grace_days or 7),60)))
    else:row.current_period_ends_at=now;row.grace_ends_at=now
    db.add(row);db.add(CommercialCustomer(school_id=school.id,contact_name=(b.contact_name or "").strip()[:100],contact_value=(b.contact_value or "").strip()[:200],source=(b.source or "manual").strip()[:80],note=(b.note or "").strip()[:1000]));db.add(SubscriptionEvent(school_id=school.id,action="create_school",plan_code=b.plan_code,status=status,detail=f"admin={admin_username};contact={(b.contact_value or '').strip()};note={(b.note or '').strip()[:300]}"));db.flush();commercial_operation(db,school.id,"school_create",{},_operator_snapshot(db,school.id),f"admin={admin_username};contact={(b.contact_value or '').strip()}");db.commit()
    return {"ok":True,"school":operator_school_payload(db,school.id),"temporaryCredential":{"schoolName":school.name,"schoolCode":school.code,"username":admin.username,"password":admin_password,"mustChangePassword":True}}

@app.get("/operator/schools/{school_id}/followups")
def operator_school_followups(school_id:int,limit:int=50,_ok:bool=Depends(commercial_operator),db:Session=Depends(get_db)):
    if not db.get(School,school_id):raise HTTPException(404,"学校不存在")
    limit=max(1,min(limit,200))
    rows=db.scalars(select(CommercialFollowUp).where(
        CommercialFollowUp.school_id==school_id
    ).order_by(CommercialFollowUp.id.desc()).limit(limit)).all()
    names={"contact":"联系沟通","demo":"产品演示","quote":"报价","payment":"付款/续费","other":"其他"}
    return [{
        "id":x.id,"type":x.follow_type,"typeName":names.get(x.follow_type,x.follow_type),
        "content":x.content,"nextFollowupDate":x.next_followup_date,
        "createdAt":school_local_iso(x.created_at)
    } for x in rows]

@app.post("/operator/schools/{school_id}/followups")
def operator_add_followup(school_id:int,b:OperatorFollowUpCreateBody,_ok:bool=Depends(commercial_operator),db:Session=Depends(get_db)):
    school=db.get(School,school_id)
    if not school:raise HTTPException(404,"学校不存在")
    follow_type=(b.follow_type or "contact").strip().lower()
    if follow_type not in ("contact","demo","quote","payment","other"):
        raise HTTPException(400,"跟进类型无效")
    content=(b.content or "").strip()
    if not content:raise HTTPException(400,"跟进内容不能为空")
    next_date=(b.next_followup_date or "").strip()
    if next_date:
        try:
            datetime.strptime(next_date,"%Y-%m-%d")
        except:
            raise HTTPException(400,"下次跟进日期格式应为 YYYY-MM-DD")
    row=CommercialFollowUp(
        school_id=school_id,follow_type=follow_type,
        content=content[:2000],next_followup_date=next_date
    )
    db.add(row)
    sub=ensure_subscription(db,school_id)
    db.add(SubscriptionEvent(
        school_id=school_id,action="commercial_followup",
        plan_code=sub.plan_code,status=_effective_subscription_status(sub),
        detail=f"type={follow_type};next={next_date};content={content[:300]}"
    ))
    commercial_operation(db,school_id,"followup_add",{}, {"type":follow_type,"nextFollowupDate":next_date},content[:500])
    db.commit();db.refresh(row)
    return operator_school_payload(db,school_id)

@app.post("/operator/schools/{school_id}/customer")
def operator_update_customer(school_id:int,b:OperatorCustomerUpdateBody,_ok:bool=Depends(commercial_operator),db:Session=Depends(get_db)):
    school=db.get(School,school_id)
    if not school:raise HTTPException(404,"学校不存在")
    row=commercial_customer_for(db,school_id,True)
    old_customer={"contactName":row.contact_name,"contactValue":row.contact_value,"source":row.source,"note":row.note}
    row.contact_name=(b.contact_name or "").strip()[:100]
    row.contact_value=(b.contact_value or "").strip()[:200]
    row.source=(b.source or "").strip()[:80]
    row.note=(b.note or "").strip()[:1000]
    row.updated_at=datetime.utcnow()
    sub=ensure_subscription(db,school_id)
    db.add(SubscriptionEvent(
        school_id=school_id,action="customer_profile_update",
        plan_code=sub.plan_code,status=_effective_subscription_status(sub),
        detail=f"contact_name={row.contact_name};contact_value={row.contact_value};source={row.source};note={row.note[:300]}"
    ))
    new_customer={"contactName":row.contact_name,"contactValue":row.contact_value,"source":row.source,"note":row.note}
    commercial_operation(db,school_id,"customer_update",old_customer,new_customer,"客户资料修改")
    db.commit();db.refresh(row)
    return operator_school_payload(db,school_id)

@app.post("/operator/schools/{school_id}/reset-admin")
def operator_reset_admin(school_id:int,b:OperatorResetPasswordBody,_ok:bool=Depends(commercial_operator),db:Session=Depends(get_db)):
    if not password_ok(b.new_password):raise HTTPException(400,"新密码至少8位，并同时包含字母和数字")
    if not db.get(School,school_id):raise HTTPException(404,"学校不存在")
    q=select(User).where(User.school_id==school_id,User.role=="admin")
    if (b.username or "").strip():q=q.where(User.username==b.username.strip())
    admin=db.scalar(q.order_by(User.active.desc(),User.id))
    if not admin:raise HTTPException(404,"未找到学校管理员")
    admin.password_hash=hash_password(b.new_password);sec=security_for(db,admin);sec.must_change_password=True;sec.failed_login_count=0;sec.locked_until=None;sec.password_changed_at=datetime.utcnow();sub=ensure_subscription(db,school_id);db.add(SubscriptionEvent(school_id=school_id,action="reset_admin_password",plan_code=sub.plan_code,status=_effective_subscription_status(sub),detail=f"username={admin.username}"));commercial_operation(db,school_id,"admin_password_reset",{"username":admin.username},{"username":admin.username,"mustChangePassword":True},"重置学校管理员密码");db.commit();return {"ok":True,"username":admin.username,"mustChangePassword":True}

@app.post("/operator/subscriptions/{school_id}")
def operator_update_subscription(school_id:int,b:SubscriptionUpdateBody,_ok:bool=Depends(commercial_operator),db:Session=Depends(get_db)):
    school=db.get(School,school_id)
    if not school:raise HTTPException(404,"学校不存在")
    if b.plan_code not in COMMERCIAL_PLANS:raise HTTPException(400,"套餐代码无效")
    status=(b.status or "active").lower()
    if status not in ("trial","active","grace","expired"):raise HTTPException(400,"订阅状态无效")
    before=_operator_snapshot(db,school_id)
    row=ensure_subscription(db,school_id)
    now=datetime.utcnow()
    row.plan_code=b.plan_code
    row.status=status
    row.started_at=now
    row.updated_at=now
    row.source="operator"
    row.note=(b.note or "")[:1000]
    row.trial_ends_at=None
    row.current_period_ends_at=None
    row.grace_ends_at=None

    exact_end=commercial_end_date_utc(b.end_date) if (b.end_date or "").strip() else None
    if status=="trial":
        days=max(1,min(int(b.trial_days or 14),90))
        row.trial_ends_at=exact_end or (now+timedelta(days=days))
    elif status=="active":
        days=max(0,min(int(b.period_days or 0),3650))
        grace=max(0,min(int(b.grace_days or 7),60))
        if exact_end or days:
            row.current_period_ends_at=exact_end or (now+timedelta(days=days))
            if grace:row.grace_ends_at=row.current_period_ends_at+timedelta(days=grace)
    elif status=="grace":
        grace=max(1,min(int(b.grace_days or 7),60))
        row.current_period_ends_at=now
        row.grace_ends_at=exact_end or (now+timedelta(days=grace))
    elif status=="expired":
        row.current_period_ends_at=now
        row.grace_ends_at=now

    db.add(SubscriptionEvent(
        school_id=school_id,action="operator_update",
        plan_code=b.plan_code,status=status,
        detail=f"period_days={b.period_days};trial_days={b.trial_days};grace_days={b.grace_days};end_date={b.end_date};note={row.note}"
    ))
    db.flush();after=_operator_snapshot(db,school_id)
    commercial_operation(db,school_id,"subscription_update",before,after,row.note)
    db.commit();db.refresh(row)
    return operator_school_payload(db,school_id)

@app.get("/health")
def health():
    # Render deployment readiness probe must return quickly.
    # Database connectivity is checked separately at /health/db.
    return {"status":"ok"}

@app.get("/health/db")
def health_db(db:Session=Depends(get_db)):
    db.scalar(select(func.count()).select_from(School))
    return {"status":"ok","database":"connected"}

@app.get("/operator-console",response_class=HTMLResponse)
def operator_console():
    return HTMLResponse(OPERATOR_HTML,headers={"Cache-Control":"no-store, no-cache, must-revalidate, max-age=0"})

@app.post("/login")
def login(b:LoginBody,request:Request,db:Session=Depends(get_db)):
    rate_key=login_rate_check(request)
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
        login_rate_failure(rate_key)
        raise HTTPException(401,"账号或密码错误")
    login_rate_clear(rate_key)
    sec=security_for(db,u)
    sec.failed_login_count=0
    sec.locked_until=None
    db.commit()
    return {
        "token":make_token(u,sec,b.remember),"role":u.role,"userID":u.id,
        "name":u.name,"grade":u.grade,
        "mustChangePassword":bool(sec.must_change_password),
        "subscription":subscription_payload(db,u.school_id)
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
        "mustChangePassword":bool(sec.must_change_password),
        "subscription":subscription_payload(db,u.school_id)
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


@app.get("/legal/privacy",response_class=HTMLResponse)
def privacy_policy():return legal_page("隐私政策",'<p>长缨辅学用于学校教学、作业、课堂表现、积分奖励、家校沟通和学习分析。</p><h2>我们处理的数据</h2><p>可能包括账号资料、班级关系、学习与作业记录、课堂积分与奖励、教师跟进及家校沟通记录，以及保障账号安全所需的登录安全信息。</p><h2>使用目的</h2><p>数据仅用于提供教学服务、生成学习报告、保障账号安全、支持学校管理与经授权的家校沟通。</p><h2>家长与学生数据</h2><p>家长仅能查看与其账号绑定的学生数据；教师与管理员依据学校角色权限访问业务所需数据。</p><h2>数据导出与注销</h2><p>登录后可在“我的”中导出个人数据并发起账号注销申请。个人导出中的操作审计详情会进行脱敏，避免把其他学生、家长或教职工的可识别信息一并导出；学校管理员备份可在授权范围内保留完整审计详情。学校托管账号可能因教学档案、审计和法定义务需要保留部分历史记录。</p><h2>安全措施</h2><p>系统使用 HTTPS、密码哈希、登录失败锁定、会话失效机制、权限隔离与操作审计等措施降低数据风险。</p>')

@app.get("/legal/terms",response_class=HTMLResponse)
def terms_of_service():return legal_page("用户协议",'<p>使用长缨辅学即表示用户同意按照学校授权范围使用本系统，并妥善保管账号与密码。</p><h2>账号使用</h2><p>账号仅限本人或学校授权人员使用，不得共享、转售或用于与教学无关的违法活动。</p><h2>教学数据</h2><p>系统中的课堂表现、积分、作业、跟进和家校沟通用于教学辅助，不应脱离真实教学情境作为自动处分或高风险决策的唯一依据。</p><h2>服务可用性</h2><p>系统会持续改进稳定性，但网络、云服务、设备或维护可能造成短暂不可用。重要学校资料应按学校制度定期备份。</p><h2>账号终止</h2><p>用户可在应用内发起注销申请；学校管理员可依据账号归属、档案保存要求和当地法规处理停用与数据保留。</p>')

@app.get("/account/export.json")
def account_export(u:User=Depends(current_user),db:Session=Depends(get_db)):
    payload=account_export_payload(db,u);audit(db,u,"account.export","个人数据导出");db.commit()
    return Response(json.dumps(payload,ensure_ascii=False,indent=2).encode("utf-8"),media_type="application/json; charset=utf-8",headers={"Content-Disposition":"attachment; filename=my-data-v920.json","Cache-Control":"no-store"})

@app.get("/account/deletion-request")
def account_deletion_status(u:User=Depends(current_user),db:Session=Depends(get_db)):
    row=db.scalar(select(AccountDeletionRequest).where(AccountDeletionRequest.school_id==u.school_id,AccountDeletionRequest.user_id==u.id).order_by(AccountDeletionRequest.id.desc()).limit(1));return {"request":deletion_json(db,row)}

@app.post("/account/deletion-request")
def account_deletion_request(b:AccountDeletionBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    if u.role=="admin":raise HTTPException(400,"管理员账号请先移交管理权限后再处理注销")
    pending=db.scalar(select(AccountDeletionRequest).where(AccountDeletionRequest.school_id==u.school_id,AccountDeletionRequest.user_id==u.id,AccountDeletionRequest.status=="pending").limit(1))
    if pending:raise HTTPException(400,"已有待处理的注销申请")
    row=AccountDeletionRequest(school_id=u.school_id,user_id=u.id,reason=(b.reason or "").strip()[:500],status="pending");db.add(row);db.flush();audit(db,u,"account.deletion.request",f"request={row.id}");db.commit();db.refresh(row);return {"ok":True,"request":deletion_json(db,row)}

@app.post("/account/deletion-request/cancel")
def account_deletion_cancel(u:User=Depends(current_user),db:Session=Depends(get_db)):
    row=db.scalar(select(AccountDeletionRequest).where(AccountDeletionRequest.school_id==u.school_id,AccountDeletionRequest.user_id==u.id,AccountDeletionRequest.status=="pending").order_by(AccountDeletionRequest.id.desc()).limit(1))
    if not row:raise HTTPException(404,"没有待处理的注销申请")
    row.status="cancelled";row.resolved_at=datetime.utcnow();row.resolved_by=u.id;row.resolution_note="用户主动取消";audit(db,u,"account.deletion.cancel",f"request={row.id}");db.commit();return {"ok":True,"request":deletion_json(db,row)}

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


@app.get("/admin/system-health")
def admin_system_health(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");db.scalar(select(func.count()).select_from(School));migrations=db.scalars(select(SchemaMigration).order_by(SchemaMigration.applied_at.desc())).all();pending=db.scalar(select(func.count()).select_from(AccountDeletionRequest).where(AccountDeletionRequest.school_id==u.school_id,AccountDeletionRequest.status=="pending")) or 0
    warnings=[];jwt_configured=bool(os.getenv("JWT_SECRET"));db_backend="PostgreSQL" if raw_url.startswith("postgresql") else "SQLite"
    if not jwt_configured:warnings.append("尚未在环境变量中固定 JWT_SECRET；服务重启会使现有登录会话全部失效。")
    if db_backend!="PostgreSQL":warnings.append("当前不是 PostgreSQL；正式多用户上线建议使用托管 PostgreSQL。")
    if _cors_raw=="*":warnings.append("CORS_ORIGINS 当前为 *；原生 App 域名确定后建议收紧允许来源。")
    if os.getenv("ENABLE_DEMO_SEED","0")=="1":warnings.append("ENABLE_DEMO_SEED 已开启；正式生产环境应关闭演示数据自动创建。")
    return {"appVersion":APP_VERSION,"schemaVersion":SCHEMA_VERSION,"database":"ok","databaseBackend":db_backend,"jwtConfigured":jwt_configured,"corsOrigins":_cors_raw,"demoSeedEnabled":os.getenv("ENABLE_DEMO_SEED","0")=="1","loginRateLimit":{"windowSeconds":LOGIN_RATE_WINDOW_SECONDS,"maxAttempts":LOGIN_RATE_MAX_ATTEMPTS},"securityHeaders":True,"pendingDeletionRequests":pending,"migrations":[{"version":x.version,"description":x.description,"appliedAt":school_local_iso(x.applied_at)} for x in migrations[:20]],"warnings":warnings,"serverTime":school_local_iso(datetime.utcnow())}


@app.get("/admin/release-readiness")
def admin_release_readiness(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin")
    db.scalar(select(func.count()).select_from(School))
    db_backend="PostgreSQL" if raw_url.startswith("postgresql") else "SQLite"
    jwt_configured=bool(os.getenv("JWT_SECRET"))
    demo_seed=os.getenv("ENABLE_DEMO_SEED","0")=="1"
    latest_migration=db.scalar(select(SchemaMigration).order_by(SchemaMigration.applied_at.desc()).limit(1))
    migration_version=latest_migration.version if latest_migration else ""

    blockers=[]
    advisories=[]
    if db_backend!="PostgreSQL":
        blockers.append("正式多用户上线应使用托管 PostgreSQL。")
    if not jwt_configured:
        blockers.append("必须在环境变量中固定 JWT_SECRET，避免服务重启导致全部登录会话失效。")
    if demo_seed:
        blockers.append("ENABLE_DEMO_SEED 必须关闭，避免正式环境自动创建演示数据。")
    if migration_version!=SCHEMA_VERSION:
        blockers.append(f"数据库迁移版本为 {migration_version or '未知'}，当前应用要求 {SCHEMA_VERSION}。")
    if _cors_raw=="*":
        advisories.append("CORS_ORIGINS 当前为 *。网页版同源运行可继续使用，但确定正式域名后建议收紧允许来源。")

    pending=db.scalar(select(func.count()).select_from(AccountDeletionRequest).where(
        AccountDeletionRequest.school_id==u.school_id,
        AccountDeletionRequest.status=="pending"
    )) or 0
    if pending:
        advisories.append(f"当前有 {pending} 条待处理账号注销申请。")

    return {
        "appVersion":APP_VERSION,
        "schemaVersion":SCHEMA_VERSION,
        "releaseChannel":RELEASE_CHANNEL,
        "releaseName":RELEASE_NAME,
        "status":"ready" if not blockers else "blocked",
        "ready":not blockers,
        "blockers":blockers,
        "advisories":advisories,
        "checks":{
            "databaseBackend":{"ok":db_backend=="PostgreSQL","value":db_backend},
            "jwtSecret":{"ok":jwt_configured,"value":"已固定" if jwt_configured else "未固定"},
            "schemaMigration":{"ok":migration_version==SCHEMA_VERSION,"value":migration_version or "未知"},
            "demoSeed":{"ok":not demo_seed,"value":"已关闭" if not demo_seed else "已开启"},
            "securityHeaders":{"ok":True,"value":"已启用"},
            "loginRateLimit":{"ok":True,"value":f"{LOGIN_RATE_MAX_ATTEMPTS}/{round(LOGIN_RATE_WINDOW_SECONDS/60)}分钟"},
            "legacyPwaCache":{"ok":True,"value":"已停用"}
        },
        "serverTime":school_local_iso(datetime.utcnow())
    }

@app.get("/admin/backup.json")
def admin_backup(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");require_plan_feature(db,u.school_id,"school_backup");payload=school_backup_payload(db,u.school_id);audit(db,u,"backup.export",f"schema={SCHEMA_VERSION}");db.commit();body=json.dumps(payload,ensure_ascii=False,indent=2).encode("utf-8")
    return Response(body,media_type="application/json; charset=utf-8",headers={"Content-Disposition":f"attachment; filename=school-backup-v830-{datetime.utcnow().strftime('%Y%m%d')}.json","Cache-Control":"no-store"})

@app.get("/admin/deletion-requests")
def admin_deletion_requests(limit:int=100,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");limit=max(1,min(limit,300));rows=db.scalars(select(AccountDeletionRequest).where(AccountDeletionRequest.school_id==u.school_id).order_by(AccountDeletionRequest.id.desc()).limit(limit)).all();return [deletion_json(db,x) for x in rows]

@app.post("/admin/deletion-requests/{rid}/resolve")
def admin_resolve_deletion(rid:int,b:DeletionResolveBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");row=db.scalar(select(AccountDeletionRequest).where(AccountDeletionRequest.id==rid,AccountDeletionRequest.school_id==u.school_id))
    if not row:raise HTTPException(404,"注销申请不存在")
    if row.status!="pending":raise HTTPException(400,"该申请已处理")
    target=db.scalar(select(User).where(User.id==row.user_id,User.school_id==u.school_id))
    if not target:raise HTTPException(404,"账号不存在")
    action=(b.action or "").strip().lower()
    if action not in ("approve","reject"):raise HTTPException(400,"处理动作必须为 approve 或 reject")
    if action=="approve":
        if target.id==u.id:raise HTTPException(400,"不能注销当前登录的管理员账号")
        target.active=False;sec=security_for(db,target);sec.failed_login_count=0;sec.locked_until=None;sec.password_changed_at=datetime.utcnow()
        if target.role=="parent":
            for link in db.scalars(select(ParentStudent).where(ParentStudent.parent_id==target.id)).all():db.delete(link)
        row.status="approved"
    else:row.status="rejected"
    row.resolved_at=datetime.utcnow();row.resolved_by=u.id;row.resolution_note=(b.note or "").strip()[:500];audit(db,u,"account.deletion.resolve",f"request={row.id};user={target.id};action={row.status}");db.commit();return {"ok":True,"request":deletion_json(db,row),"accountActive":bool(target.active)}

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
    if b.role=="teacher":require_plan_capacity(db,u.school_id,"teachers")
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
    if b.active and not target.active:
        if target.role=="teacher":require_plan_capacity(db,u.school_id,"teachers")
        if target.role=="student":require_plan_capacity(db,u.school_id,"students")
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
    if not s.active:require_plan_capacity(db,u.school_id,"students")
    for link in db.scalars(select(ClassStudent).join(SchoolClass,SchoolClass.id==ClassStudent.class_id).where(ClassStudent.student_id==sid,SchoolClass.school_id==u.school_id)).all():db.delete(link)
    db.add(ClassStudent(class_id=c.id,student_id=s.id));s.grade=c.grade;s.active=True
    sec=security_for(db,s);sec.failed_login_count=0;sec.locked_until=None;sec.password_changed_at=datetime.utcnow()
    ensure_history_open(db,u.school_id,s.id,c.id,u.id,"restore")
    audit(db,u,"student.restore",f"{s.id}:{s.name}:class={c.id}");db.commit()
    return {"ok":True,"studentID":s.id,"active":True,"classID":c.id,"className":c.name,"grade":c.grade}

@app.get("/admin/audit-logs")
def admin_audit_logs(limit:int=150,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");require_plan_feature(db,u.school_id,"school_audit");limit=max(1,min(limit,300));rows=db.scalars(select(AuditLog).where(AuditLog.school_id==u.school_id).order_by(AuditLog.id.desc()).limit(limit)).all();out=[]
    for x in rows:
        actor=db.get(User,x.user_id) if x.user_id else None
        out.append({"id":x.id,"action":x.action,"actionName":{"student.transfer":"学生调班","student.archive":"毕业归档","student.restore":"恢复学生","assignment.create":"布置作业","assignment.export":"导出成绩","class.export":"导出班级报表","student.export":"导出学生成绩单","user.active":"账号状态变更","user.reset_password":"重置密码","import.xlsx":"批量导入","class.create":"新建班级","student.create":"创建学生","paper.create":"创建试卷","question.create":"新增题目","user.create":"创建账号","teaching.program.update":"教学方案设置","teaching.lesson.update":"更新定制课时","teaching.question.create":"新增分层题","teaching.question.delete":"删除分层题","teaching.essay.feedback":"作文批改","parent.bind":"绑定家长","parent.unbind":"解除家长绑定","auto.reward.rule.create":"新增自动奖励规则","auto.reward.rule.update":"修改自动奖励规则","auto.reward.grant":"自动奖励触发","auto.reward.fulfill":"自动奖励发放","auto.reward.cancel":"自动奖励取消","account.export":"个人数据导出","account.deletion.request":"账号注销申请","account.deletion.cancel":"取消注销申请","account.deletion.resolve":"处理注销申请","backup.export":"学校数据备份"}.get(x.action,x.action),"summary":audit_readable(db,x),"actorName":actor.name if actor else "系统","actorRole":actor.role if actor else "system","createdAt":school_local_iso(x.created_at)})
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
def import_template(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");require_plan_feature(db,u.school_id,"bulk_import")
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
    note.append(["长缨辅学 V7.4.0 Excel 批量导入说明"]);note.append(["1. 可同时填写题库导入、教师导入、学生导入三个工作表；空工作表会自动跳过。"]);note.append(["2. 教师/学生初始密码至少8位，并同时包含字母和数字；首次登录必须修改。"]);note.append(["3. 学生导入的“班级”必须已存在，并且年级要与班级一致；家长账号可留空。"]);note.append(["4. 已存在的登录账号不会覆盖，会计入跳过行；有效数据仍会继续导入。"]);note.column_dimensions["A"].width=95
    for row in note.iter_rows():
        for c in row:c.alignment=Alignment(wrap_text=True,vertical="top")
    bio=io.BytesIO();wb.save(bio)
    return Response(bio.getvalue(),media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":"attachment; filename=primary-school-import-template-v740.xlsx","Cache-Control":"no-store"})

@app.post("/admin/import-xlsx")
async def import_xlsx(file:UploadFile=File(...),u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");require_plan_feature(db,u.school_id,"bulk_import")
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
                if active:require_plan_capacity(db,u.school_id,"teachers")
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
                if active:require_plan_capacity(db,u.school_id,"students")
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


@app.get("/global-search")
def global_search(q:str="",limit:int=24,u:User=Depends(current_user),db:Session=Depends(get_db)):
    q=(q or "").strip().lower()
    limit=max(6,min(int(limit or 24),60))
    if not q:
        return {"query":"","results":[]}

    results=[]
    def add(kind,title,subtitle="",**extra):
        if len(results)>=limit:return
        item={"kind":kind,"title":title,"subtitle":subtitle}
        item.update(extra);results.append(item)

    if u.role=="teacher":
        classes=db.scalars(select(SchoolClass).where(
            SchoolClass.school_id==u.school_id,SchoolClass.teacher_id==u.id
        ).order_by(SchoolClass.id.desc())).all()
        cids=[c.id for c in classes]
        class_map={c.id:c for c in classes}

        for c in classes:
            if q in (c.name or "").lower() or q in str(c.grade):
                add("class",c.name,f"{c.grade}年级 · 班级",classID=c.id,target="classPoints")

        if cids:
            links=db.scalars(select(ClassStudent).where(ClassStudent.class_id.in_(cids))).all()
            sid_to_classes={}
            for link in links:sid_to_classes.setdefault(link.student_id,[]).append(link.class_id)
            sids=list(sid_to_classes)
            students=db.scalars(select(User).where(
                User.school_id==u.school_id,User.role=="student",User.id.in_(sids)
            ).order_by(User.name)).all() if sids else []
            for s in students:
                if q in (s.name or "").lower() or q in (s.username or "").lower():
                    cid=(sid_to_classes.get(s.id) or [None])[0]
                    cname=class_map.get(cid).name if cid in class_map else ""
                    add("student",s.name,f"{cname} · {s.username}",studentID=s.id,classID=cid,target="classPoints")

            assignments=db.scalars(select(Assignment).where(
                Assignment.school_id==u.school_id,Assignment.class_id.in_(cids)
            ).order_by(Assignment.id.desc())).all()
            for a in assignments:
                if q in (a.title or "").lower() or q in (a.due_date or "").lower():
                    c=class_map.get(a.class_id)
                    add("assignment",a.title,f"{c.name if c else ''} · 截止 {a.due_date}",assignmentID=a.id,classID=a.class_id,target="papers")

            followups=db.scalars(select(StudentFollowUp).where(
                StudentFollowUp.school_id==u.school_id,StudentFollowUp.class_id.in_(cids)
            ).order_by(StudentFollowUp.updated_at.desc(),StudentFollowUp.id.desc())).all()
            student_ids=list({f.student_id for f in followups})
            student_names={x.id:x.name for x in db.scalars(select(User).where(
                User.school_id==u.school_id,User.id.in_(student_ids)
            )).all()} if student_ids else {}
            for f in followups:
                student_name=student_names.get(f.student_id,"")
                hay=" ".join([f.title or "",f.note or "",student_name]).lower()
                if q in hay:
                    c=class_map.get(f.class_id)
                    status={"open":"待跟进","doing":"跟进中","in_progress":"跟进中","done":"已完成"}.get(f.status,f.status)
                    add("followup",f.title,f"{student_name} · {c.name if c else ''} · {status}",followupID=f.id,studentID=f.student_id,classID=f.class_id,target="classPoints")

    elif u.role=="admin":
        users=db.scalars(select(User).where(User.school_id==u.school_id).order_by(User.id.desc())).all()
        for x in users:
            if q in (x.name or "").lower() or q in (x.username or "").lower() or q in (x.role or "").lower():
                add("user",x.name,f"{x.username} · { {'teacher':'教师','student':'学生','parent':'家长','admin':'管理员'}.get(x.role,x.role) }",userID=x.id,target="users")

        classes=db.scalars(select(SchoolClass).where(SchoolClass.school_id==u.school_id).order_by(SchoolClass.id.desc())).all()
        teachers={x.id:x.name for x in users if x.role=="teacher"}
        for c in classes:
            if q in (c.name or "").lower() or q in str(c.grade) or q in (teachers.get(c.teacher_id,"") or "").lower():
                add("class",c.name,f"{c.grade}年级 · {teachers.get(c.teacher_id,'')}",classID=c.id,target="users")
    else:
        raise HTTPException(403,"仅管理员或教师可使用快捷搜索")

    return {"query":q,"count":len(results),"results":results}


@app.get("/teacher/classes")
def tclasses(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher");rows=db.scalars(select(SchoolClass).where(SchoolClass.school_id==u.school_id,SchoolClass.teacher_id==u.id).order_by(SchoolClass.id.desc())).all()
    return [{"id":c.id,"name":c.name,"grade":c.grade,"teacherID":c.teacher_id,"studentCount":db.scalar(select(func.count()).select_from(ClassStudent).where(ClassStudent.class_id==c.id)) or 0} for c in rows]

@app.post("/teacher/classes")
def addclass(b:ClassCreate,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher");require_plan_capacity(db,u.school_id,"classes");c=SchoolClass(school_id=u.school_id,name=b.name,grade=b.grade,teacher_id=u.id);db.add(c);db.flush();audit(db,u,"class.create",f"{c.id}:{c.name}");db.commit();db.refresh(c);return {"id":c.id,"name":c.name,"grade":c.grade,"teacherID":c.teacher_id,"studentCount":0}

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
    need(u,"teacher");require_plan_capacity(db,u.school_id,"students");c=db.scalar(select(SchoolClass).where(SchoolClass.id==b.class_id,SchoolClass.school_id==u.school_id,SchoolClass.teacher_id==u.id))
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
    auto_changed=reconcile_auto_rewards(db,u.school_id,ids,u.id)
    for g in auto_changed:
        if g.status=="pending":audit(db,u,"auto.reward.grant",f"grant={g.id};student={g.student_id};reward={g.reward_name};value={g.metric_value}")
    audit(db,u,"points.record",f"students={','.join(str(x) for x in ids)};points={points};reason={reason or note}");db.commit()
    return {"count":len(created),"points":int(points),"records":[point_ledger_json(db,x) for x in created],"autoRewards":[auto_grant_json(db,x) for x in auto_changed if x.status=="pending"]}

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
    row.reversed=True;db.add(rev);db.flush();reconcile_auto_rewards(db,u.school_id,[row.student_id],u.id);audit(db,u,"points.undo",f"ledger={row.id};reversal={rev.id}");db.commit();return {"ok":True,"record":point_ledger_json(db,rev)}

@app.get("/student/points")
def student_points(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"student");summary=point_summary(db,u.id,u.school_id)
    rows=db.scalars(select(PointLedger).where(PointLedger.school_id==u.school_id,PointLedger.student_id==u.id).order_by(PointLedger.id.desc()).limit(120)).all()
    red=db.scalars(select(RewardRedemption).where(RewardRedemption.school_id==u.school_id,RewardRedemption.student_id==u.id).order_by(RewardRedemption.id.desc()).limit(50)).all()
    auto_rows=db.scalars(select(AutoRewardGrant).where(AutoRewardGrant.school_id==u.school_id,AutoRewardGrant.student_id==u.id).order_by(AutoRewardGrant.id.desc()).limit(50)).all()
    return {"summary":summary,"weekly":student_period_points(db,u.id,u.school_id,7),
            "trend":student_weekly_trend(db,u.id,u.school_id,4),
            "badges":student_growth_badges(db,u.id,u.school_id),"growthAdvice":student_growth_advice(db,u.id,u.school_id),
            "ledger":[point_ledger_json(db,x) for x in rows],
            "redemptions":[redemption_json(db,x) for x in red],
            "autoRewards":[auto_grant_json(db,x) for x in auto_rows]}

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
    auto_rows=db.scalars(select(AutoRewardGrant).where(AutoRewardGrant.school_id==u.school_id,AutoRewardGrant.student_id==sid).order_by(AutoRewardGrant.id.desc()).limit(50)).all()
    return {"student":{"id":stu.id,"name":stu.name,"grade":stu.grade},
            "summary":point_summary(db,sid,u.school_id),
            "weekly":student_period_points(db,sid,u.school_id,7),
            "trend":student_weekly_trend(db,sid,u.school_id,4),
            "badges":student_growth_badges(db,sid,u.school_id),"growthAdvice":student_growth_advice(db,sid,u.school_id),
            "ledger":[point_ledger_json(db,x) for x in rows],
            "redemptions":[redemption_json(db,x) for x in red],
            "autoRewards":[auto_grant_json(db,x) for x in auto_rows]}

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
    ranking.sort(key=lambda x:(x["net"],x["earned"],x["activity"],x["studentName"]),reverse=True)
    for i,x in enumerate(ranking,1):x["rank"]=i
    return {"class":{"id":c.id,"name":c.name,"grade":c.grade},"days":days,"studentCount":len(students),"totals":totals,"ranking":ranking}


@app.get("/teacher/points/students/{sid}/trend")
def teacher_points_student_trend(sid:int,weeks:int=4,class_id:int|None=None,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin")
    stu=can_manage_student_points(db,u,sid,class_id)
    c=current_class_for(db,stu.id,u.school_id)
    return {"student":{"id":stu.id,"name":stu.name,"className":c.name if c else "未分班"},
            "summary":point_summary(db,stu.id,u.school_id),
            "trend":student_weekly_trend(db,stu.id,u.school_id,weeks),
            "badges":student_growth_badges(db,stu.id,u.school_id),"growthAdvice":student_growth_advice(db,stu.id,u.school_id)}

@app.post("/teacher/points/classes/{cid}/auto-rewards/fulfill-pending")
def teacher_fulfill_class_auto_rewards(cid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");c=current_teacher_class(db,u,cid)
    ids=list(db.scalars(select(ClassStudent.student_id).where(ClassStudent.class_id==c.id)).all())
    if not ids:return {"count":0,"records":[]}
    rows=db.execute(select(AutoRewardGrant).where(
        AutoRewardGrant.school_id==u.school_id,AutoRewardGrant.student_id.in_(ids),AutoRewardGrant.status=="pending"
    ).order_by(AutoRewardGrant.id).with_for_update()).scalars().all()
    now=datetime.utcnow()
    for row in rows:
        row.status="fulfilled";row.handled_by=u.id;row.handled_at=now
        if not row.note:row.note="教师一键发放本班自动奖励"
        audit(db,u,"auto.reward.bulk_fulfill",f"grant={row.id};class={cid};student={row.student_id};reward={row.reward_name}")
    db.commit()
    return {"count":len(rows),"records":[auto_grant_json(db,x) for x in rows]}

@app.get("/teacher/points/classes/{cid}/weekly.xlsx")
def teacher_points_weekly_export(cid:int,days:int=7,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");data=teacher_points_weekly(cid,days,u,db)
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill
    wb=Workbook();ws=wb.active;ws.title=f"近{data['days']}天课堂积分"
    ws.append(["排名","学生","近期开获得","净表现","课堂活动","守纪积分","兑换次数","兑换积分","当前可用","累计发放"])
    for x in data["ranking"]:
        sm=point_summary(db,x["studentID"],u.school_id)
        ws.append([x["rank"],x["studentName"],x["earned"],x["net"],x["activity"],x["discipline"],x["redemptionCount"],x["redeemedPoints"],sm["available"],sm["earned"]])
    for cell in ws[1]:cell.font=Font(bold=True,color="FFFFFF");cell.fill=PatternFill("solid",fgColor="5362E8")
    ws.freeze_panes="A2"
    for col,width in {"A":8,"B":18,"C":13,"D":12,"E":12,"F":12,"G":12,"H":12,"I":12,"J":12}.items():ws.column_dimensions[col].width=width
    buf=io.BytesIO();wb.save(buf);audit(db,u,"points.weekly.export",f"class={cid};days={data['days']}");db.commit()
    return Response(buf.getvalue(),media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":f"attachment; filename=class_points_weekly_{cid}.xlsx"})


@app.get("/teacher/points/classes/{cid}/groups")
def teacher_point_groups(cid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");c=current_teacher_class(db,u,cid);return class_groups_json(db,c,u.school_id)

@app.post("/teacher/points/classes/{cid}/groups")
def teacher_create_point_group(cid:int,b:ClassroomGroupBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");c=current_teacher_class(db,u,cid);name=b.name.strip()
    if not name:raise HTTPException(400,"小组名称不能为空")
    if len(name)>80:raise HTTPException(400,"小组名称过长")
    if db.scalar(select(ClassroomGroup).where(ClassroomGroup.class_id==c.id,ClassroomGroup.school_id==u.school_id,ClassroomGroup.name==name)):raise HTTPException(400,"该班级已存在同名小组")
    row=ClassroomGroup(school_id=u.school_id,class_id=c.id,name=name,sort_order=b.sort_order);db.add(row);db.flush()
    audit(db,u,"points.group.create",f"class={cid};group={row.id};name={name}");db.commit();db.refresh(row)
    return {"id":row.id,"name":row.name,"sortOrder":row.sort_order}

@app.put("/teacher/points/classes/{cid}/groups/{gid}/members")
def teacher_set_point_group_members(cid:int,gid:int,b:ClassroomGroupMembersBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");c=current_teacher_class(db,u,cid)
    g=db.scalar(select(ClassroomGroup).where(ClassroomGroup.id==gid,ClassroomGroup.class_id==c.id,ClassroomGroup.school_id==u.school_id))
    if not g:raise HTTPException(404,"小组不存在")
    ids=list(dict.fromkeys(int(x) for x in b.student_ids if int(x)>0))
    if ids:
        valid=set(db.scalars(select(ClassStudent.student_id).where(ClassStudent.class_id==c.id,ClassStudent.student_id.in_(ids))).all())
        if len(valid)!=len(ids):raise HTTPException(400,"包含不属于当前班级的学生")
        other_groups=list(db.scalars(select(ClassroomGroup.id).where(ClassroomGroup.class_id==c.id,ClassroomGroup.id!=g.id)).all())
        if other_groups:
            for x in db.scalars(select(ClassroomGroupMember).where(ClassroomGroupMember.group_id.in_(other_groups),ClassroomGroupMember.student_id.in_(ids))).all():db.delete(x)
    for x in db.scalars(select(ClassroomGroupMember).where(ClassroomGroupMember.group_id==g.id)).all():db.delete(x)
    db.flush()
    for sid in ids:db.add(ClassroomGroupMember(group_id=g.id,student_id=sid))
    audit(db,u,"points.group.members",f"class={cid};group={gid};students={','.join(str(x) for x in ids)}");db.commit()
    return {"ok":True,"groupID":g.id,"studentIDs":ids}

@app.delete("/teacher/points/classes/{cid}/groups/{gid}")
def teacher_delete_point_group(cid:int,gid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");c=current_teacher_class(db,u,cid)
    g=db.scalar(select(ClassroomGroup).where(ClassroomGroup.id==gid,ClassroomGroup.class_id==c.id,ClassroomGroup.school_id==u.school_id))
    if not g:raise HTTPException(404,"小组不存在")
    for x in db.scalars(select(ClassroomGroupMember).where(ClassroomGroupMember.group_id==g.id)).all():db.delete(x)
    audit(db,u,"points.group.delete",f"class={cid};group={gid};name={g.name}");db.delete(g);db.commit();return {"ok":True}

@app.get("/teacher/points/classes/{cid}/growth-dashboard")
def teacher_class_growth_dashboard(cid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");c=current_teacher_class(db,u,cid);return class_growth_dashboard_data(db,c,u.school_id)

@app.get("/teacher/points/classes/{cid}/growth-monthly.xlsx")
def teacher_growth_monthly_export(cid:int,month:str|None=None,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");c=current_teacher_class(db,u,cid);start,end,key=month_window_utc(month)
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill,Alignment
    students=db.scalars(select(User).join(ClassStudent,ClassStudent.student_id==User.id).where(
        ClassStudent.class_id==c.id,User.school_id==u.school_id,User.role=="student",User.active==True
    ).order_by(User.name)).all()
    rows=[]
    for stu in students:
        p=point_window_summary(db,stu.id,u.school_id,start,end);sm=point_summary(db,stu.id,u.school_id)
        autos=int(db.scalar(select(func.count()).select_from(AutoRewardGrant).where(
            AutoRewardGrant.school_id==u.school_id,AutoRewardGrant.student_id==stu.id,AutoRewardGrant.created_at>=start,
            AutoRewardGrant.created_at<end,AutoRewardGrant.status!="canceled")) or 0)
        rows.append({"student":stu.name,**p,"available":sm["available"],"auto":autos})
    rows.sort(key=lambda x:(x["net"],x["earned"],x["activity"],x["student"]),reverse=True)
    wb=Workbook();ws=wb.active;ws.title="学生表现";ws.append(["排名","学生","净表现","发放积分","课堂活动","守纪积分","积分记录数","自动奖励","当前可用"])
    for i,x in enumerate(rows,1):ws.append([i,x["student"],x["net"],x["earned"],x["activity"],x["discipline"],x["records"],x["auto"],x["available"]])
    wg=wb.create_sheet("小组排行");wg.append(["排名","小组","成员数","月度净表现","月度发放","课堂活动","守纪积分"])
    month_groups=[]
    for g in db.scalars(select(ClassroomGroup).where(ClassroomGroup.class_id==c.id,ClassroomGroup.school_id==u.school_id).order_by(ClassroomGroup.sort_order,ClassroomGroup.id)).all():
        ids=list(db.scalars(select(ClassroomGroupMember.student_id).where(ClassroomGroupMember.group_id==g.id)).all())
        total={"net":0,"earned":0,"activity":0,"discipline":0}
        for sid in ids:
            s=point_window_summary(db,sid,u.school_id,start,end)
            for k in total:total[k]+=int(s.get(k,0) or 0)
        month_groups.append({"name":g.name,"memberCount":len(ids),**total})
    month_groups.sort(key=lambda x:(x["net"],x["earned"],x["activity"],x["name"]),reverse=True)
    for i,x in enumerate(month_groups,1):wg.append([i,x["name"],x["memberCount"],x["net"],x["earned"],x["activity"],x["discipline"]])
    category={}
    for row in db.scalars(select(PointLedger).where(PointLedger.school_id==u.school_id,PointLedger.class_id==c.id,
        PointLedger.created_at>=start,PointLedger.created_at<end,PointLedger.source.in_(("classroom","adjustment","reversal")))).all():
        rkey=row.reason or ("课堂活动" if row.category=="activity" else "守纪情况")
        z=category.setdefault(rkey,{"reason":rkey,"category":row.category,"count":0,"points":0});z["count"]+=1;z["points"]+=int(row.points or 0)
    wc=wb.create_sheet("月度表现分类");wc.append(["表现项目","类别","次数","净积分"])
    for x in sorted(category.values(),key=lambda z:(abs(z["points"]),z["count"]),reverse=True):wc.append([x["reason"],"课堂活动" if x["category"]=="activity" else "守纪情况",x["count"],x["points"]])
    for sh in wb.worksheets:
        sh.freeze_panes="A2"
        for cell in sh[1]:cell.font=Font(bold=True,color="FFFFFF");cell.fill=PatternFill("solid",fgColor="5362E8");cell.alignment=Alignment(horizontal="center")
        for col in sh.columns:sh.column_dimensions[col[0].column_letter].width=min(28,max(10,max(len(str(cell.value or "")) for cell in col)+2))
    buf=io.BytesIO();wb.save(buf);audit(db,u,"points.growth.monthly.export",f"class={cid};month={key}");db.commit()
    return Response(buf.getvalue(),media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition":f"attachment; filename=class_growth_{cid}_{key}.xlsx"})


@app.get("/teacher/points/classes/{cid}/homeroom-dashboard")
def teacher_homeroom_dashboard(cid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");c=current_teacher_class(db,u,cid)
    return class_homeroom_dashboard_data(db,c,u.school_id)

@app.get("/teacher/points/classes/{cid}/homeroom-report.xlsx")
def teacher_homeroom_report(cid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");c=current_teacher_class(db,u,cid)
    data=class_homeroom_dashboard_data(db,c,u.school_id)
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill,Alignment
    wb=Workbook();ws=wb.active;ws.title="班级画像"
    ws.append(["维度","周期","学生数","参与人数","参与率","正向学生","需关注学生","发放积分","净表现","课堂活动","守纪积分","自动奖励"])
    for key,name in (("week","本周"),("month","本月")):
        p=data["profiles"][key]
        ws.append([name,p["label"],p["studentCount"],p["activeStudents"],p["participationRate"],p["positiveStudents"],p["negativeStudents"],
                   p["earned"],p["net"],p["activity"],p["discipline"],p["autoRewards"]])
    wt=wb.create_sheet("今日表现");wt.append(["学生","今日净表现","课堂活动","守纪","记录数"])
    for x in data["today"]["students"]:wt.append([x["studentName"],x["net"],x["activity"],x["discipline"],x["records"]])
    wf=wb.create_sheet("重点关注");wf.append(["学生","本周净表现","本周活动","本周守纪","近30天平均分","提醒"])
    for x in data["focusList"]:
        wf.append([x["studentName"],x["weekly"]["net"],x["weekly"]["activity"],x["weekly"]["discipline"],
                   x["academic"]["avgScore"] if x["academic"]["avgScore"] is not None else "","；".join(x["riskFlags"])])
    wa=wb.create_sheet("学业课堂联动");wa.append(["学生","近30天练习数","平均分","本月课堂净表现","本周净表现","联动标签"])
    for x in data["academicBehavior"]:
        wa.append([x["studentName"],x["academic"]["count"],x["academic"]["avgScore"] if x["academic"]["avgScore"] is not None else "",
                   x["monthly"]["net"],x["weekly"]["net"],x["linkLabel"]])
    wc=wb.create_sheet("家校沟通摘要");wc.append(["学生","沟通摘要"])
    for x in data["students"]:wc.append([x["studentName"],x["communicationSummary"]])
    for sh in wb.worksheets:
        sh.freeze_panes="A2"
        for cell in sh[1]:
            cell.font=Font(bold=True,color="FFFFFF");cell.fill=PatternFill("solid",fgColor="5362E8");cell.alignment=Alignment(horizontal="center")
        for col in sh.columns:
            letter=col[0].column_letter
            width=max(10,max(len(str(cell.value or "")) for cell in col)+2)
            sh.column_dimensions[letter].width=min(48,width)
    buf=io.BytesIO();wb.save(buf)
    audit(db,u,"points.homeroom.export",f"class={cid}");db.commit()
    return Response(buf.getvalue(),media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition":f"attachment; filename=homeroom_dashboard_{cid}.xlsx"})




# ---------------- V8.2 active reminders & daily workbench ----------------
def _workbench_due_item(kind:str,row_json:dict):
    return {
        "kind":kind,"id":row_json.get("id"),"title":row_json.get("title",""),
        "studentID":row_json.get("studentID"),"studentName":row_json.get("studentName",""),
        "priority":row_json.get("priority","normal"),"priorityName":row_json.get("priorityName","普通"),
        "status":row_json.get("status","open"),"statusName":row_json.get("statusName",""),
        "dueDate":row_json.get("dueDate",""),"dueState":row_json.get("dueState","none"),
        "dueLabel":row_json.get("dueLabel",""),"overdue":bool(row_json.get("overdue")),
    }

def class_workbench_data(db,c:SchoolClass,school_id:int):
    follow=class_followup_dashboard_data(db,c,school_id)
    homeroom=class_homeroom_dashboard_data(db,c,school_id)
    cases=follow.get("cases",[])
    todos=follow.get("todos",[])
    urgent=[]
    due_today=due_soon=overdue=0
    for x in cases:
        if x.get("status")=="done":
            continue
        st=x.get("dueState")
        if st in ("overdue","today","soon"):
            urgent.append(_workbench_due_item("followup",x))
            if st=="overdue":overdue+=1
            elif st=="today":due_today+=1
            elif st=="soon":due_soon+=1
    for x in todos:
        if x.get("status")=="done":
            continue
        st=x.get("dueState")
        if st in ("overdue","today","soon"):
            urgent.append(_workbench_due_item("todo",x))
            if st=="overdue":overdue+=1
            elif st=="today":due_today+=1
            elif st=="soon":due_soon+=1
    state_order={"overdue":0,"today":1,"soon":2,"upcoming":3,"none":4,"done":5}
    priority_order={"high":0,"normal":1,"low":2}
    urgent.sort(key=lambda x:(state_order.get(x.get("dueState"),9),priority_order.get(x.get("priority"),9),x.get("dueDate") or "9999"))

    cutoff=datetime.utcnow()-timedelta(days=7)
    stale_rows=db.scalars(select(StudentFollowUp).where(
        StudentFollowUp.school_id==school_id,StudentFollowUp.class_id==c.id,
        StudentFollowUp.status!="done",StudentFollowUp.updated_at<=cutoff
    ).order_by(StudentFollowUp.updated_at,StudentFollowUp.id)).all()
    stale=[]
    for row in stale_rows:
        j=followup_json(db,row)
        days=max(7,(datetime.utcnow()-row.updated_at).days)
        stale.append({**_workbench_due_item("followup",j),"daysWithoutUpdate":days,"updatedAt":school_local_iso(row.updated_at)})

    callbacks=[]
    open_rows=db.scalars(select(StudentFollowUp).where(
        StudentFollowUp.school_id==school_id,StudentFollowUp.class_id==c.id,StudentFollowUp.status!="done"
    ).order_by(StudentFollowUp.updated_at.desc())).all()
    for row in open_rows:
        contact=db.scalar(select(StudentFollowUpLog).where(
            StudentFollowUpLog.school_id==school_id,StudentFollowUpLog.followup_id==row.id,
            StudentFollowUpLog.log_type=="parent_contact"
        ).order_by(StudentFollowUpLog.created_at.desc(),StudentFollowUpLog.id.desc()).limit(1))
        if not contact:
            continue
        result_after=db.scalar(select(StudentFollowUpLog.id).where(
            StudentFollowUpLog.school_id==school_id,StudentFollowUpLog.followup_id==row.id,
            StudentFollowUpLog.log_type=="result",StudentFollowUpLog.id>contact.id
        ).order_by(StudentFollowUpLog.id.asc()).limit(1))
        if result_after:
            continue
        stu=db.get(User,row.student_id)
        callbacks.append({
            "followupID":row.id,"studentID":row.student_id,"studentName":stu.name if stu else f"学生{row.student_id}",
            "title":row.title,"contactAt":school_local_iso(contact.created_at),"contactContent":contact.content,
            "daysSinceContact":max(0,(datetime.utcnow()-contact.created_at).days)
        })

    risk=[]
    for x in homeroom.get("focusList",[]):
        risk.append({"studentID":x.get("studentID"),"studentName":x.get("studentName",""),
                     "flags":x.get("riskFlags",[])[:3],"weeklyNet":x.get("weekly",{}).get("net",0),
                     "disciplineStreak":x.get("disciplineStreak",0)})
    progress=[]
    for x in homeroom.get("positiveAlerts",[]):
        progress.append({"studentID":x.get("studentID"),"studentName":x.get("studentName",""),
                         "flags":x.get("positiveFlags",[])[:3],"weeklyNet":x.get("weekly",{}).get("net",0),
                         "progressStreak":x.get("progressStreak",0)})

    open_todos=[x for x in todos if x.get("status")!="done"]
    open_todos.sort(key=lambda x:(state_order.get(x.get("dueState"),9),priority_order.get(x.get("priority"),9),x.get("dueDate") or "9999"))
    total_reminders=len(urgent)+len(stale)+len(callbacks)+len(risk)+len(progress)
    return {
        "class":{"id":c.id,"name":c.name,"grade":c.grade},
        "ruleNote":"到期提醒覆盖逾期、今天到期和3天内到期；长期未处理指7天未更新；家长沟通待回访指已沟通但尚无‘处理结果’记录。",
        "summary":{"reminders":total_reminders,"overdue":overdue,"dueToday":due_today,"dueSoon":due_soon,
                   "stale":len(stale),"callbacks":len(callbacks),"risk":len(risk),"progress":len(progress),
                   "openTodos":len(open_todos)},
        "urgent":urgent[:30],"stale":stale[:20],"callbacks":callbacks[:20],
        "riskAlerts":risk[:20],"progressAlerts":progress[:20],"todos":open_todos[:30],
        "generatedAt":school_local_iso(datetime.utcnow())
    }

@app.get("/teacher/points/classes/{cid}/workbench")
def teacher_class_workbench(cid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");c=current_teacher_class(db,u,cid)
    return class_workbench_data(db,c,u.school_id)

@app.get("/teacher/workbench-summary")
def teacher_workbench_summary(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin")
    q=select(SchoolClass).where(SchoolClass.school_id==u.school_id)
    if u.role=="teacher":q=q.where(SchoolClass.teacher_id==u.id)
    classes=db.scalars(q.order_by(SchoolClass.grade,SchoolClass.name)).all()
    rows=[]
    total={"reminders":0,"overdue":0,"dueToday":0,"dueSoon":0,"stale":0,"callbacks":0,"risk":0,"progress":0,"openTodos":0}
    for c in classes:
        d=class_workbench_data(db,c,u.school_id);s=d["summary"]
        rows.append({"class":d["class"],"summary":s})
        for k in total:total[k]+=int(s.get(k,0) or 0)
    return {"summary":total,"classes":rows,"generatedAt":school_local_iso(datetime.utcnow())}

@app.get("/teacher/points/classes/{cid}/followups")
def teacher_followup_dashboard(cid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");c=current_teacher_class(db,u,cid)
    return class_followup_dashboard_data(db,c,u.school_id)

@app.post("/teacher/points/classes/{cid}/followups")
def teacher_create_followup(cid:int,b:FollowUpCreateBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");c=current_teacher_class(db,u,cid)
    stu=can_manage_student_points(db,u,int(b.student_id),cid)
    title=(b.title or "").strip()
    if not title:raise HTTPException(400,"跟进事项不能为空")
    if len(title)>180:raise HTTPException(400,"跟进事项过长")
    category=b.category if b.category in FOLLOWUP_CATEGORY_NAMES else "other"
    priority=b.priority if b.priority in FOLLOWUP_PRIORITY_NAMES else "normal"
    due=(b.due_date or "").strip()
    if due and not _safe_local_date(due):raise HTTPException(400,"截止日期格式无效")
    row=StudentFollowUp(school_id=u.school_id,class_id=c.id,student_id=stu.id,title=title,
        category=category,priority=priority,status="open",due_date=due,source=(b.source or "manual")[:30],
        note=(b.note or "").strip(),created_by=u.id)
    db.add(row);db.flush()
    if row.note:
        db.add(StudentFollowUpLog(school_id=u.school_id,followup_id=row.id,student_id=stu.id,
                                  actor_id=u.id,log_type="note",content=row.note))
    audit(db,u,"followup.create",f"class={cid};followup={row.id};student={stu.id};title={title}")
    db.commit();db.refresh(row);return followup_json(db,row,True)

@app.get("/teacher/points/classes/{cid}/followups/{fid}")
def teacher_followup_detail(cid:int,fid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");c=current_teacher_class(db,u,cid)
    row=db.scalar(select(StudentFollowUp).where(StudentFollowUp.id==fid,StudentFollowUp.class_id==c.id,StudentFollowUp.school_id==u.school_id))
    if not row:raise HTTPException(404,"跟进事项不存在")
    return followup_json(db,row,True)

@app.put("/teacher/points/classes/{cid}/followups/{fid}/status")
def teacher_followup_status(cid:int,fid:int,b:FollowUpStatusBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");c=current_teacher_class(db,u,cid)
    row=db.scalar(select(StudentFollowUp).where(StudentFollowUp.id==fid,StudentFollowUp.class_id==c.id,StudentFollowUp.school_id==u.school_id))
    if not row:raise HTTPException(404,"跟进事项不存在")
    if b.status not in FOLLOWUP_STATUS_NAMES:raise HTTPException(400,"状态无效")
    row.status=b.status;row.updated_at=datetime.utcnow();row.completed_at=datetime.utcnow() if b.status=="done" else None
    audit(db,u,"followup.status",f"class={cid};followup={fid};status={b.status}");db.commit();db.refresh(row)
    return followup_json(db,row,True)

@app.post("/teacher/points/classes/{cid}/followups/{fid}/logs")
def teacher_add_followup_log(cid:int,fid:int,b:FollowUpLogBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");c=current_teacher_class(db,u,cid)
    row=db.scalar(select(StudentFollowUp).where(StudentFollowUp.id==fid,StudentFollowUp.class_id==c.id,StudentFollowUp.school_id==u.school_id))
    if not row:raise HTTPException(404,"跟进事项不存在")
    content=(b.content or "").strip()
    if not content:raise HTTPException(400,"跟进内容不能为空")
    if len(content)>3000:raise HTTPException(400,"跟进内容过长")
    log_type=b.log_type if b.log_type in FOLLOWUP_LOG_NAMES else "note"
    if log_type=="parent_contact":require_plan_feature(db,u.school_id,"parent_communication")
    log=StudentFollowUpLog(school_id=u.school_id,followup_id=row.id,student_id=row.student_id,
                           actor_id=u.id,log_type=log_type,content=content)
    db.add(log);row.updated_at=datetime.utcnow()
    if row.status=="open":row.status="in_progress"
    audit(db,u,"followup.log",f"class={cid};followup={fid};type={log_type}");db.commit();db.refresh(log)
    return followup_log_json(db,log)

@app.post("/teacher/points/classes/{cid}/todos")
def teacher_create_class_todo(cid:int,b:ClassTodoBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");c=current_teacher_class(db,u,cid)
    title=(b.title or "").strip()
    if not title:raise HTTPException(400,"班级待办不能为空")
    due=(b.due_date or "").strip()
    if due and not _safe_local_date(due):raise HTTPException(400,"截止日期格式无效")
    priority=b.priority if b.priority in FOLLOWUP_PRIORITY_NAMES else "normal"
    row=ClassTodo(school_id=u.school_id,class_id=c.id,title=title,priority=priority,status="open",
                  due_date=due,note=(b.note or "").strip(),created_by=u.id)
    db.add(row);db.flush();audit(db,u,"class.todo.create",f"class={cid};todo={row.id};title={title}");db.commit();db.refresh(row)
    return class_todo_json(db,row)

@app.put("/teacher/points/classes/{cid}/todos/{tid}/status")
def teacher_class_todo_status(cid:int,tid:int,b:ClassTodoStatusBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");c=current_teacher_class(db,u,cid)
    row=db.scalar(select(ClassTodo).where(ClassTodo.id==tid,ClassTodo.class_id==c.id,ClassTodo.school_id==u.school_id))
    if not row:raise HTTPException(404,"班级待办不存在")
    if b.status not in ("open","done"):raise HTTPException(400,"状态无效")
    row.status=b.status;row.completed_at=datetime.utcnow() if b.status=="done" else None
    audit(db,u,"class.todo.status",f"class={cid};todo={tid};status={b.status}");db.commit();db.refresh(row)
    return class_todo_json(db,row)


def student_growth_profile_data(db,stu:User,school_id:int,class_id:int|None=None):
    c=None
    if class_id:
        c=db.scalar(select(SchoolClass).where(SchoolClass.id==class_id,SchoolClass.school_id==school_id))
    if not c:
        c=current_class_for(db,stu.id,school_id)

    # 家长绑定
    parent_links=db.scalars(select(ParentStudent).where(ParentStudent.student_id==stu.id)).all()
    parents=[]
    for link in parent_links:
        p=db.scalar(select(User).where(User.id==link.parent_id,User.school_id==school_id,User.role=="parent"))
        if p:parents.append({"id":p.id,"name":p.name,"username":p.username})

    # 学业总体
    progress=progress_for(db,stu.id,school_id)
    all_subs=db.scalars(select(Submission).where(
        Submission.school_id==school_id,Submission.student_id==stu.id
    ).order_by(Submission.submitted_at.desc(),Submission.id.desc())).all()
    total_correct=sum(int(x.correct or 0) for x in all_subs)
    total_questions=sum(int(x.total or 0) for x in all_subs)
    accuracy=round(total_correct/total_questions*100) if total_questions else 0

    recent_submissions=[]
    for sub in all_subs[:8]:
        subject=""
        assignment_title=""
        if sub.assignment_id:
            a=db.scalar(select(Assignment).where(Assignment.id==sub.assignment_id,Assignment.school_id==school_id))
            if a:
                assignment_title=a.title
                p=db.scalar(select(Paper).where(Paper.id==a.paper_id,Paper.school_id==school_id))
                subject=p.subject if p else ""
        recent_submissions.append({
            "id":sub.id,"title":sub.title or assignment_title or "学习练习",
            "score":sub.score,"correct":sub.correct,"total":sub.total,
            "subject":subject,"submittedAt":school_local_iso(sub.submitted_at),
            "formal":bool(sub.assignment_id)
        })

    # 当前/指定班级作业完成情况
    rq=select(AssignmentRecipient).where(
        AssignmentRecipient.school_id==school_id,AssignmentRecipient.student_id==stu.id
    )
    if c:rq=rq.where(AssignmentRecipient.class_id==c.id)
    recipients=db.scalars(rq.order_by(AssignmentRecipient.assigned_at.desc(),AssignmentRecipient.id.desc())).all()
    assignment_rows=[]
    completed=pending=overdue=0
    for rec in recipients:
        a=db.scalar(select(Assignment).where(Assignment.id==rec.assignment_id,Assignment.school_id==school_id))
        if not a:continue
        sub=db.scalar(select(Submission).where(
            Submission.school_id==school_id,Submission.assignment_id==a.id,Submission.student_id==stu.id
        ).order_by(Submission.submitted_at.desc(),Submission.id.desc()))
        meta=assignment_status(a.due_date,sub)
        if meta["completed"]:completed+=1
        else:pending+=1
        if meta["overdue"]:overdue+=1
        if len(assignment_rows)<8:
            p=db.scalar(select(Paper).where(Paper.id==a.paper_id,Paper.school_id==school_id))
            assignment_rows.append({
                "id":a.id,"title":a.title,"dueDate":a.due_date,
                "subject":p.subject if p else "",
                "status":meta["status"],"statusCode":meta["statusCode"],
                "completed":meta["completed"],"overdue":meta["overdue"],
                "score":sub.score if sub else None,
                "submittedAt":school_local_iso(sub.submitted_at) if sub else ""
            })
    assignment_total=len(recipients)
    completion_rate=round(completed/assignment_total*100) if assignment_total else 0

    # 课堂表现
    points=point_summary(db,stu.id,school_id)
    weekly=student_period_points(db,stu.id,school_id,7)
    monthly=student_period_points(db,stu.id,school_id,30)
    lq=select(PointLedger).where(PointLedger.school_id==school_id,PointLedger.student_id==stu.id)
    if c:lq=lq.where(PointLedger.class_id==c.id)
    ledgers=db.scalars(lq.order_by(PointLedger.created_at.desc(),PointLedger.id.desc()).limit(10)).all()
    recent_points=[point_ledger_json(db,x) for x in ledgers]

    # 跟进与家校沟通
    fq=select(StudentFollowUp).where(StudentFollowUp.school_id==school_id,StudentFollowUp.student_id==stu.id)
    if c:fq=fq.where(StudentFollowUp.class_id==c.id)
    follow_rows=db.scalars(fq.order_by(StudentFollowUp.updated_at.desc(),StudentFollowUp.id.desc())).all()
    followups=[followup_json(db,x) for x in follow_rows[:8]]
    open_followups=[x for x in followups if x["status"]!="done"]
    overdue_followups=[x for x in open_followups if x.get("overdue")]
    fids=[x.id for x in follow_rows]
    contacts=[]
    if fids:
        contact_rows=db.scalars(select(StudentFollowUpLog).where(
            StudentFollowUpLog.school_id==school_id,
            StudentFollowUpLog.student_id==stu.id,
            StudentFollowUpLog.followup_id.in_(fids),
            StudentFollowUpLog.log_type=="parent_contact"
        ).order_by(StudentFollowUpLog.created_at.desc(),StudentFollowUpLog.id.desc()).limit(8)).all()
        contacts=[followup_log_json(db,x) for x in contact_rows]

    # 事实型亮点与教学提示，不做自动处分/高风险决策
    highlights=[]
    suggestions=[]
    if all_subs and progress["avgScore"]>=85:
        highlights.append(f"累计平均分 {progress['avgScore']} 分，学习成绩保持较好。")
    if weekly["net"]>0:
        highlights.append(f"近7天课堂净表现 +{weekly['net']} 分。")
    if weekly["activity"]>0:
        highlights.append(f"近7天课堂活动积分 +{weekly['activity']} 分，参与表现积极。")
    if contacts:
        highlights.append(f"已形成 {len(contacts)} 条近期家校沟通记录。")

    if overdue:
        suggestions.append(f"当前有 {overdue} 份逾期未交作业，建议优先确认补交安排。")
    elif pending:
        suggestions.append(f"当前有 {pending} 份待完成作业，建议跟进完成进度。")
    if all_subs and progress["avgScore"]<70:
        suggestions.append(f"累计平均分为 {progress['avgScore']} 分，可结合错题和知识点进行针对性巩固。")
    weak=[x for x in (progress.get("knowledge") or []) if x.get("answered",0)>=2 and x.get("accuracy",100)<70][:3]
    if weak:
        suggestions.append("可优先关注知识点："+"、".join(f"{x['knowledge']}（{x['accuracy']}%）" for x in weak)+"。")
    if open_followups:
        suggestions.append(f"当前仍有 {len(open_followups)} 项学生跟进未完成。")
    if overdue_followups:
        suggestions.append(f"其中 {len(overdue_followups)} 项跟进已逾期，建议及时更新处理状态。")
    if open_followups and not contacts:
        suggestions.append("已有学生跟进事项但暂无家长沟通记录，如教学需要可考虑家校协同。")
    if not suggestions:
        suggestions.append("当前没有明显待处理事项，建议保持日常观察并持续记录成长变化。")
    if not highlights:
        highlights.append("当前可继续积累作业、课堂表现和跟进记录，形成更完整的成长轨迹。")

    raw_class_history=class_history_rows(db,stu.id,school_id)
    class_history=[]
    seen_history=set()
    for h in raw_class_history:
        # 只合并“真正完全一致”的历史事件。
        # 同一天内若学生发生了两次真实调班/恢复入班，必须全部保留，避免隐藏真实班级轨迹。
        key=(
            h.get("classID"),
            h.get("joinedAt") or "",
            h.get("leftAt") or "",
            h.get("leaveReason") or "",
            bool(h.get("current"))
        )
        if key in seen_history:
            continue
        seen_history.add(key)
        row=dict(h)
        row["joinedDay"]=(h.get("joinedAt") or "")[:10]
        row["leftDay"]=(h.get("leftAt") or "")[:10]
        class_history.append(row)
    timeline=student_growth_timeline_data(db,stu.id,school_id,c.id if c else None,40)

    return {
        "student":{
            "id":stu.id,"name":stu.name,"username":stu.username,"grade":stu.grade,
            "active":bool(stu.active),
            "className":c.name if c else "未分班",
            "classID":c.id if c else None,
            "parents":parents
        },
        "class":{"id":c.id,"name":c.name,"grade":c.grade} if c else None,
        "academic":{
            "avgScore":progress["avgScore"],"accuracy":accuracy,
            "submissionCount":progress["submissions"],"totalAnswered":progress["totalAnswered"],
            "assignmentTotal":assignment_total,"completedAssignments":completed,
            "pendingAssignments":pending,"overdueAssignments":overdue,
            "completionRate":completion_rate,
            "weakKnowledge":(progress.get("knowledge") or [])[:6],
            "recentSubmissions":recent_submissions,
            "recentAssignments":assignment_rows
        },
        "points":{
            "summary":points,"weekly":weekly,"monthly":monthly,
            "recent":recent_points
        },
        "followup":{
            "open":len(open_followups),
            "inProgress":sum(1 for x in open_followups if x["status"] in ("doing","in_progress")),
            "overdue":len(overdue_followups),
            "total":len(follow_rows),
            "cases":followups,
            "parentContacts":contacts
        },
        "highlights":highlights,
        "suggestions":suggestions,
        "classHistory":class_history,
        "timeline":timeline
    }

@app.get("/teacher/students/{sid}/growth-profile")
def teacher_student_growth_profile(sid:int,class_id:int|None=None,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin")
    stu=can_manage_student_points(db,u,sid,class_id)
    return student_growth_profile_data(db,stu,u.school_id,class_id)



@app.get("/teacher/students/{sid}/growth-report.xlsx")
def teacher_student_growth_report(sid:int,class_id:int|None=None,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");require_plan_feature(db,u.school_id,"growth_report")
    stu=can_manage_student_points(db,u,sid,class_id)
    data=student_growth_profile_data(db,stu,u.school_id,class_id)

    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill,Alignment,Border,Side
    from openpyxl.utils import get_column_letter

    wb=Workbook()
    ws=wb.active
    ws.title="成长摘要"

    primary="5362E8";soft="EEF0FF";green="EAF8F2";amber="FFF7E7";line="E5E8F0";dark="1F2738";muted="778095"
    thin=Side(style="thin",color=line)

    point_category_names={"activity":"课堂活动","discipline":"守纪表现","other":"其他"}
    timeline_type_names={"followup_log":"跟进记录","followup":"跟进事项","academic":"学习成绩","point":"课堂积分","reward":"奖励"}
    reward_status_names={"fulfilled":"已发放","pending":"待发放","canceled":"已取消","cancelled":"已取消"}

    def clean_text(v):
        if v is None:return ""
        return str(v).strip()

    def localize_detail(v):
        text=clean_text(v)
        for raw,zh in reward_status_names.items():
            text=text.replace(raw,zh)
        return text

    def title(sheet,text):
        sheet.merge_cells(start_row=1,start_column=1,end_row=1,end_column=6)
        c=sheet.cell(1,1,text)
        c.font=Font(size=18,bold=True,color="FFFFFF")
        c.fill=PatternFill("solid",fgColor=primary)
        c.alignment=Alignment(horizontal="center",vertical="center")
        sheet.row_dimensions[1].height=32

    def section(sheet,row,text):
        sheet.merge_cells(start_row=row,start_column=1,end_row=row,end_column=6)
        c=sheet.cell(row,1,text)
        c.font=Font(size=12,bold=True,color=dark)
        c.fill=PatternFill("solid",fgColor=soft)
        c.alignment=Alignment(vertical="center")
        sheet.row_dimensions[row].height=24
        return row+1

    def header(sheet,row,values):
        for col,val in enumerate(values,1):
            c=sheet.cell(row,col,val)
            c.font=Font(bold=True,color=dark)
            c.fill=PatternFill("solid",fgColor="F4F6FB")
            c.border=Border(bottom=thin)
            c.alignment=Alignment(vertical="center",wrap_text=True)
        return row+1

    def fit(sheet,widths=None):
        widths=widths or {}
        for i in range(1,sheet.max_column+1):
            sheet.column_dimensions[get_column_letter(i)].width=widths.get(i,18)
        for row in sheet.iter_rows():
            for c in row:
                c.alignment=Alignment(vertical="top",wrap_text=True)
        sheet.freeze_panes="A2"

    s=data["student"];a=data["academic"];p=data["points"];f=data["followup"]

    # ---------- 成长摘要 ----------
    title(ws,f"{s['name']}｜学生成长报告")
    r=3
    r=section(ws,r,"基本信息")
    basics=[
        ("学生",s["name"]),("账号",s["username"]),("年级",f"{s.get('grade') or ''}年级"),
        ("当前班级",s.get("className") or "未分班"),("账号状态","在读" if s.get("active") else "停用"),
        ("家长","、".join(f"{x['name']}（{x['username']}）" for x in s.get("parents",[])) or "未绑定")
    ]
    for i in range(0,len(basics),2):
        ws.cell(r,1,basics[i][0]).font=Font(bold=True,color=muted);ws.cell(r,2,basics[i][1])
        if i+1<len(basics):
            ws.cell(r,4,basics[i+1][0]).font=Font(bold=True,color=muted);ws.cell(r,5,basics[i+1][1])
        r+=1

    r+=1
    r=section(ws,r,"核心指标")
    kpis=[
        ("累计平均分",a.get("avgScore",0)),
        ("班级作业完成率",f"{a.get('completionRate',0)}%"),
        ("累计答题正确率",f"{a.get('accuracy',0)}%"),
        ("近7天课堂净表现",p.get("weekly",{}).get("net",0)),
        ("未完成跟进",f.get("open",0)),
        ("逾期跟进",f.get("overdue",0))
    ]
    r=header(ws,r,["指标","数值","指标","数值","指标","数值"])
    for i in range(0,len(kpis),3):
        row=[]
        for j in range(3):
            if i+j<len(kpis):row += [kpis[i+j][0],kpis[i+j][1]]
            else:row += ["",""]
        for col,val in enumerate(row,1):
            ws.cell(r,col,val)
            if col%2==1:ws.cell(r,col).font=Font(bold=True,color=muted)
            else:ws.cell(r,col).font=Font(bold=True,color=primary)
        r+=1

    r+=1
    r=section(ws,r,"成长亮点")
    for x in data.get("highlights",[]) or ["暂无"]:
        ws.merge_cells(start_row=r,start_column=1,end_row=r,end_column=6)
        ws.cell(r,1,"• "+str(x));r+=1

    r+=1
    r=section(ws,r,"教学提示")
    for x in data.get("suggestions",[]) or ["暂无"]:
        ws.merge_cells(start_row=r,start_column=1,end_row=r,end_column=6)
        ws.cell(r,1,"• "+str(x));r+=1

    r+=1
    r=section(ws,r,"班级历程")
    r=header(ws,r,["班级","年级","进入时间","离开时间","状态/原因","当前"])
    for x in reversed(data.get("classHistory",[]) or []):
        ws.append([
            x.get("className",""),x.get("grade",""),x.get("joinedAt",""),x.get("leftAt") or "至今",
            "在读" if x.get("current") else x.get("leaveReasonName","已离班"),
            "是" if x.get("current") else "否"
        ])
        r+=1
    ws.merge_cells(start_row=r+1,start_column=1,end_row=r+2,end_column=6)
    ws.cell(r+1,1,"说明：本报告汇总学习、课堂表现、教师跟进和家校沟通，仅用于教师观察与教学支持，不作为自动处分或高风险决策的唯一依据。")
    ws.cell(r+1,1).fill=PatternFill("solid",fgColor=amber)
    ws.cell(r+1,1).font=Font(color="7B5719")
    fit(ws,{1:20,2:18,3:22,4:22,5:20,6:14})

    # ---------- 学习作业 ----------
    wa=wb.create_sheet("学习作业")
    title(wa,f"{s['name']}｜学习与作业")
    r=3
    r=section(wa,r,"学习概览")
    wa.append(["累计平均分",a.get("avgScore",0),"答题正确率",f"{a.get('accuracy',0)}%","累计提交",a.get("submissionCount",0)])
    wa.append(["班级作业",a.get("assignmentTotal",0),"已完成",a.get("completedAssignments",0),"待完成",a.get("pendingAssignments",0)])
    wa.append(["逾期未交",a.get("overdueAssignments",0),"完成率",f"{a.get('completionRate',0)}%","累计答题",a.get("totalAnswered",0)])

    r=wa.max_row+2
    r=section(wa,r,"近期班级作业")
    r=header(wa,r,["作业","科目","截止日期","状态","分数","提交时间"])
    for x in a.get("recentAssignments",[]) or []:
        wa.append([clean_text(x.get("title","")),clean_text(x.get("subject","")),x.get("dueDate",""),x.get("status",""),x.get("score",""),x.get("submittedAt","")])

    r=wa.max_row+2
    r=section(wa,r,"近期学习提交")
    r=header(wa,r,["练习/作业","科目","分数","答对","总题数","提交时间"])
    for x in a.get("recentSubmissions",[]) or []:
        wa.append([clean_text(x.get("title","")),clean_text(x.get("subject","")),x.get("score",""),x.get("correct",""),x.get("total",""),x.get("submittedAt","")])

    r=wa.max_row+2
    r=section(wa,r,"知识点掌握")
    r=header(wa,r,["知识点","正确率","已答题数","","",""])
    for x in a.get("weakKnowledge",[]) or []:
        wa.append([x.get("knowledge",""),f"{x.get('accuracy',0)}%",x.get("answered",0),"","",""])
    fit(wa,{1:28,2:16,3:16,4:14,5:14,6:22})

    # ---------- 课堂表现 ----------
    wp=wb.create_sheet("课堂表现")
    title(wp,f"{s['name']}｜课堂表现")
    wp.append(["可用积分",p.get("summary",{}).get("available",0),"近7天活动",p.get("weekly",{}).get("activity",0),"近7天守纪",p.get("weekly",{}).get("discipline",0)])
    wp.append(["近7天净表现",p.get("weekly",{}).get("net",0),"近30天净表现",p.get("monthly",{}).get("net",0),"累计发放",p.get("summary",{}).get("earned",0)])
    r=wp.max_row+2
    r=section(wp,r,"最近课堂记录")
    r=header(wp,r,["时间","类别","事项","积分","教师/来源","备注"])
    for x in p.get("recent",[]) or []:
        wp.append([
            x.get("createdAt",""),
            clean_text(x.get("categoryName")) or point_category_names.get(x.get("category"),clean_text(x.get("category"))),
            clean_text(x.get("reason")),
            x.get("points",0),
            clean_text(x.get("actorName")) or clean_text(x.get("source")),
            clean_text(x.get("note"))
        ])
    fit(wp,{1:22,2:16,3:26,4:12,5:18,6:30})

    # ---------- 跟进沟通 ----------
    wf=wb.create_sheet("跟进沟通")
    title(wf,f"{s['name']}｜跟进与家校沟通")
    wf.append(["未完成跟进",f.get("open",0),"跟进中",f.get("inProgress",0),"已逾期",f.get("overdue",0)])
    r=wf.max_row+2
    r=section(wf,r,"学生跟进事项")
    r=header(wf,r,["事项","类别","优先级","状态","截止日期","最近记录"])
    for x in f.get("cases",[]) or []:
        latest=x.get("latestLog") or {}
        wf.append([clean_text(x.get("title")),clean_text(x.get("categoryName")),clean_text(x.get("priorityName")),clean_text(x.get("statusName")),x.get("dueDate",""),clean_text(latest.get("content"))])

    r=wf.max_row+2
    r=section(wf,r,"家校沟通")
    r=header(wf,r,["时间","教师","沟通内容","","",""])
    for x in f.get("parentContacts",[]) or []:
        wf.append([x.get("createdAt",""),clean_text(x.get("actorName")),clean_text(x.get("content")),"","",""])
    fit(wf,{1:28,2:18,3:18,4:14,5:18,6:38})

    # ---------- 成长时间线 ----------
    wt=wb.create_sheet("成长时间线")
    title(wt,f"{s['name']}｜成长时间线")
    r=3
    r=header(wt,r,["时间","类型","事件","详情","班级",""])
    for x in data.get("timeline",[]) or []:
        wt.append([
            x.get("time",""),
            clean_text(x.get("typeName")) or timeline_type_names.get(x.get("type"),clean_text(x.get("type"))),
            clean_text(x.get("title")),
            localize_detail(x.get("detail")),
            clean_text(x.get("className")),
            ""
        ])
    fit(wt,{1:22,2:16,3:26,4:46,5:20,6:8})

    # 全工作簿统一样式
    for sheet in wb.worksheets:
        sheet.sheet_view.showGridLines=False
        for row in sheet.iter_rows():
            for c in row:
                if c.row>1 and c.value is not None and not c.fill.fill_type:
                    c.border=Border(bottom=Side(style="hair",color="EEF0F5"))

    bio=io.BytesIO()
    wb.save(bio)
    audit(db,u,"growth_report.export",f"{stu.id}:{stu.name}")
    db.commit()
    return Response(
        bio.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition":'attachment; filename="student_growth_report_v880.xlsx"',"Cache-Control":"no-store"}
    )

@app.get("/teacher/points/students/{sid}/growth-timeline")
def teacher_student_growth_timeline(sid:int,class_id:int|None=None,limit:int=80,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");stu=can_manage_student_points(db,u,sid,class_id)
    return {"student":{"id":stu.id,"name":stu.name},"events":student_growth_timeline_data(db,stu.id,u.school_id,class_id,limit)}

@app.get("/parent/children/{sid}/communication-history")
def parent_child_communication_history(sid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"parent")
    if not db.scalar(select(ParentStudent.id).where(ParentStudent.parent_id==u.id,ParentStudent.student_id==sid)):raise HTTPException(403,"未绑定该学生")
    rows=db.scalars(select(StudentFollowUpLog).join(StudentFollowUp,StudentFollowUp.id==StudentFollowUpLog.followup_id).where(
        StudentFollowUpLog.school_id==u.school_id,StudentFollowUpLog.student_id==sid,
        StudentFollowUpLog.log_type=="parent_contact"
    ).order_by(StudentFollowUpLog.created_at.desc(),StudentFollowUpLog.id.desc()).limit(50)).all()
    return [followup_log_json(db,x) for x in rows]

@app.get("/teacher/points/classes/{cid}/followups-report.xlsx")
def teacher_followups_report(cid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");c=current_teacher_class(db,u,cid);data=class_followup_dashboard_data(db,c,u.school_id)
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill,Alignment
    wb=Workbook();ws=wb.active;ws.title="学生跟进"
    ws.append(["学生","事项","类别","优先级","状态","截止日期","到期状态","创建时间","最近跟进"])
    for x in data["cases"]:
        latest=x.get("latestLog") or {}
        ws.append([x["studentName"],x["title"],x["categoryName"],x["priorityName"],x["statusName"],x["dueDate"],x["dueLabel"],x["createdAt"],latest.get("content","")])
    wt=wb.create_sheet("班级待办");wt.append(["事项","优先级","状态","截止日期","到期状态","备注","创建时间"])
    for x in data["todos"]:wt.append([x["title"],x["priorityName"],x["statusName"],x["dueDate"],x["dueLabel"],x["note"],x["createdAt"]])
    wc=wb.create_sheet("家校沟通记录");wc.append(["学生","沟通内容","教师","时间"])
    rows=db.scalars(select(StudentFollowUpLog).join(StudentFollowUp,StudentFollowUp.id==StudentFollowUpLog.followup_id).where(
        StudentFollowUp.school_id==u.school_id,StudentFollowUp.class_id==c.id,StudentFollowUpLog.log_type=="parent_contact"
    ).order_by(StudentFollowUpLog.created_at.desc())).all()
    for x in rows:
        j=followup_log_json(db,x);stu=db.get(User,x.student_id)
        wc.append([stu.name if stu else x.student_id,j["content"],j["actorName"],j["createdAt"]])
    for sh in wb.worksheets:
        sh.freeze_panes="A2"
        for cell in sh[1]:
            cell.font=Font(bold=True,color="FFFFFF");cell.fill=PatternFill("solid",fgColor="5362E8");cell.alignment=Alignment(horizontal="center")
        for col in sh.columns:
            letter=col[0].column_letter
            sh.column_dimensions[letter].width=min(46,max(10,max(len(str(cell.value or "")) for cell in col)+2))
    buf=io.BytesIO();wb.save(buf);audit(db,u,"followup.export",f"class={cid}");db.commit()
    return Response(buf.getvalue(),media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition":f"attachment; filename=class_followups_{cid}.xlsx"})

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
    auto_pending=int(db.scalar(select(func.count()).select_from(AutoRewardGrant).where(AutoRewardGrant.school_id==u.school_id,AutoRewardGrant.status=="pending")) or 0)
    return {"days":days,"studentCount":student_count,"earned":earned,"activity":activity,"discipline":discipline,
            "redemptionCount":len(active),"redeemedPoints":sum(int(x.cost_points or 0) for x in active),
            "pending":sum(1 for x in reds if x.status=="pending")+auto_pending,"autoPending":auto_pending,"fulfilled":sum(1 for x in reds if x.status=="fulfilled"),
            "rejected":sum(1 for x in reds if x.status=="rejected"),"popularRewards":popular,
            "lowStock":[{"id":x.id,"name":x.name,"icon":x.icon or "🎁","stock":x.stock,"costPoints":x.cost_points} for x in low]}

@app.get("/points/leaderboard")
def points_leaderboard(class_id:int|None=None,days:int=7,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","student")
    if u.role=="student":
        c=current_class_for(db,u.id,u.school_id)
        if not c:return {"class":None,"days":days,"ranking":[]}
        class_id=c.id
    if not class_id:raise HTTPException(400,"请选择班级")
    c=current_teacher_class(db,u,class_id) if u.role=="teacher" else db.scalar(select(SchoolClass).where(SchoolClass.id==class_id,SchoolClass.school_id==u.school_id))
    if not c:raise HTTPException(404,"班级不存在")
    if u.role=="student" and not db.scalar(select(ClassStudent.id).where(ClassStudent.class_id==c.id,ClassStudent.student_id==u.id)):raise HTTPException(403,"无权查看该班级")
    students=db.scalars(select(User).join(ClassStudent,ClassStudent.student_id==User.id).where(
        ClassStudent.class_id==c.id,User.school_id==u.school_id,User.role=="student",User.active==True
    ).order_by(User.name)).all()
    rows=[]
    for stu in students:
        p=student_period_points(db,stu.id,u.school_id,days);sm=point_summary(db,stu.id,u.school_id)
        rows.append({"studentID":stu.id,"studentName":stu.name,"net":p["net"],"issued":p["earned"],"activity":p["activity"],
                     "discipline":p["discipline"],"available":sm["available"]})
    rows.sort(key=lambda x:(x["net"],x["issued"],x["activity"],x["studentName"]),reverse=True)
    for i,x in enumerate(rows,1):x["rank"]=i
    return {"class":{"id":c.id,"name":c.name,"grade":c.grade},"days":max(1,min(int(days or 7),90)),"ranking":rows}

@app.get("/admin/auto-reward-rules")
def admin_auto_reward_rules(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin")
    rows=db.scalars(select(AutoRewardRule).where(AutoRewardRule.school_id==u.school_id).order_by(AutoRewardRule.id.desc())).all()
    return [auto_rule_json(db,x) for x in rows]

@app.post("/admin/auto-reward-rules")
def create_auto_reward_rule(b:AutoRewardRuleBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");name=b.name.strip()
    if not name:raise HTTPException(400,"规则名称不能为空")
    if b.period not in ("weekly","monthly"):raise HTTPException(400,"周期仅支持 weekly/monthly")
    if b.metric not in ("net","issued","activity","discipline"):raise HTTPException(400,"统计口径无效")
    if b.threshold<=0 or b.threshold>10000:raise HTTPException(400,"达标值须在1到10000之间")
    reward=db.scalar(select(RewardItem).where(RewardItem.id==b.reward_id,RewardItem.school_id==u.school_id))
    if not reward:raise HTTPException(404,"奖品不存在")
    row=AutoRewardRule(school_id=u.school_id,name=name,reward_id=reward.id,period=b.period,metric=b.metric,threshold=b.threshold,active=b.active)
    db.add(row);db.flush();audit(db,u,"auto.reward.rule.create",f"{row.id}:{row.name}:{reward.name}:{row.threshold}")
    ids=db.scalars(select(User.id).where(User.school_id==u.school_id,User.role=="student",User.active==True)).all()
    reconcile_auto_rewards(db,u.school_id,list(ids),u.id);db.commit();db.refresh(row);return auto_rule_json(db,row)

@app.put("/admin/auto-reward-rules/{rid}")
def update_auto_reward_rule(rid:int,b:AutoRewardRuleBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");row=db.scalar(select(AutoRewardRule).where(AutoRewardRule.id==rid,AutoRewardRule.school_id==u.school_id))
    if not row:raise HTTPException(404,"自动奖励规则不存在")
    if b.period not in ("weekly","monthly") or b.metric not in ("net","issued","activity","discipline") or b.threshold<=0:raise HTTPException(400,"自动奖励参数无效")
    reward=db.scalar(select(RewardItem).where(RewardItem.id==b.reward_id,RewardItem.school_id==u.school_id))
    if not reward:raise HTTPException(404,"奖品不存在")
    row.name=b.name.strip() or row.name;row.reward_id=reward.id;row.period=b.period;row.metric=b.metric;row.threshold=b.threshold;row.active=b.active;row.updated_at=datetime.utcnow()
    if not row.active:cancel_auto_rule_pending(db,row.id,u.id)
    else:
        ids=db.scalars(select(User.id).where(User.school_id==u.school_id,User.role=="student",User.active==True)).all();reconcile_auto_rewards(db,u.school_id,list(ids),u.id)
    audit(db,u,"auto.reward.rule.update",f"{row.id}:{row.name}:{reward.name}:{row.threshold}:{'on' if row.active else 'off'}");db.commit();return auto_rule_json(db,row)

@app.post("/admin/auto-rewards/evaluate")
def evaluate_auto_reward_rules(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");ids=db.scalars(select(User.id).where(User.school_id==u.school_id,User.role=="student",User.active==True)).all()
    changed=reconcile_auto_rewards(db,u.school_id,list(ids),u.id);db.commit()
    return {"changed":len(changed),"pending":sum(1 for x in changed if x.status=="pending"),"canceled":sum(1 for x in changed if x.status=="canceled")}

@app.get("/auto-reward-grants")
def auto_reward_grants(status:str|None=None,class_id:int|None=None,limit:int=150,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");limit=max(1,min(limit,500))
    q=select(AutoRewardGrant).where(AutoRewardGrant.school_id==u.school_id)
    if status:q=q.where(AutoRewardGrant.status==status)
    rows=db.scalars(q.order_by(AutoRewardGrant.id.desc()).limit(limit)).all()
    if class_id:
        c=current_teacher_class(db,u,class_id) if u.role=="teacher" else db.scalar(select(SchoolClass).where(SchoolClass.id==class_id,SchoolClass.school_id==u.school_id))
        if not c:raise HTTPException(404,"班级不存在")
        ids=set(db.scalars(select(ClassStudent.student_id).where(ClassStudent.class_id==c.id)).all());rows=[x for x in rows if x.student_id in ids]
    elif u.role=="teacher":
        ids=set(db.scalars(select(ClassStudent.student_id).join(SchoolClass,SchoolClass.id==ClassStudent.class_id).where(SchoolClass.school_id==u.school_id,SchoolClass.teacher_id==u.id)).all());rows=[x for x in rows if x.student_id in ids]
    return [auto_grant_json(db,x) for x in rows]

@app.post("/auto-reward-grants/{gid}/handle")
def handle_auto_reward_grant(gid:int,b:AutoRewardHandleBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","admin");row=db.execute(select(AutoRewardGrant).where(AutoRewardGrant.id==gid,AutoRewardGrant.school_id==u.school_id).with_for_update()).scalar_one_or_none()
    if not row:raise HTTPException(404,"自动奖励记录不存在")
    can_manage_student_points(db,u,row.student_id,None)
    if row.status!="pending":raise HTTPException(400,"该自动奖励已处理")
    action=b.action.strip().lower();row.handled_by=u.id;row.handled_at=datetime.utcnow();row.note=b.note.strip() or row.note
    if action=="fulfill":row.status="fulfilled";audit(db,u,"auto.reward.fulfill",f"grant={row.id};student={row.student_id};reward={row.reward_name}")
    elif action in ("cancel","reject"):_restore_auto_grant_stock(db,row);row.status="canceled";audit(db,u,"auto.reward.cancel",f"grant={row.id};student={row.student_id};reward={row.reward_name}")
    else:raise HTTPException(400,"处理动作无效")
    db.commit();return auto_grant_json(db,row)

@app.get("/parent/children/{sid}/points-weekly.xlsx")
def parent_points_weekly_export(sid:int,days:int=7,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"parent")
    if not db.scalar(select(ParentStudent.id).where(ParentStudent.parent_id==u.id,ParentStudent.student_id==sid)):raise HTTPException(403,"未绑定该学生")
    stu=db.scalar(select(User).where(User.id==sid,User.school_id==u.school_id,User.role=="student"))
    if not stu:raise HTTPException(404,"学生不存在")
    w=student_period_points(db,sid,u.school_id,days);sm=point_summary(db,sid,u.school_id)
    cutoff,_=period_cutoff_utc(days)
    autos=db.scalars(select(AutoRewardGrant).where(
        AutoRewardGrant.school_id==u.school_id,AutoRewardGrant.student_id==sid,
        AutoRewardGrant.created_at>=cutoff
    ).order_by(AutoRewardGrant.id.desc())).all()
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill
    wb=Workbook();ws=wb.active;ws.title=f"近{w['days']}天课堂周报"
    ws.append(["学生","周期","本期发放","净表现","课堂活动","守纪积分","兑换次数","兑换积分","自动奖励","当前可用","累计发放"])
    ws.append([stu.name,f"近{w['days']}天",w['earned'],w['net'],w['activity'],w['discipline'],w['redemptionCount'],w['redeemedPoints'],w.get("autoRewardCount",0),sm['available'],sm['earned']])
    ws.append([]);ws.append(["主要表现","次数","积分合计"])
    for x in w['topReasons']:ws.append([x['reason'],x['count'],x['points']])
    if autos:
        ws.append([]);ws.append(["自动奖励","规则","状态","生成时间","处理时间"])
        status_names={"pending":"待发放","fulfilled":"已发放","canceled":"已取消"}
        for x in autos:
            j=auto_grant_json(db,x)
            ws.append([j["rewardName"],j["ruleName"],status_names.get(j["status"],j["status"]),j["createdAt"],j["handledAt"] or ""])
    for cell in ws[1]:cell.font=Font(bold=True,color="FFFFFF");cell.fill=PatternFill("solid",fgColor="5362E8")
    for cell in ws[4]:cell.font=Font(bold=True)
    for col,width in {"A":18,"B":14,"C":12,"D":12,"E":12,"F":12,"G":12,"H":12,"I":12,"J":12,"K":12}.items():ws.column_dimensions[col].width=width
    buf=io.BytesIO();wb.save(buf)
    return Response(buf.getvalue(),media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":f"attachment; filename=parent_weekly_points_{sid}.xlsx"})

@app.get("/admin/points/export.xlsx")
def export_points_report(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin")
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill
    wb=Workbook();ws=wb.active;ws.title="学生积分汇总";ws.append(["学生","账号","年级","当前班级","累计发放","当前余额","课堂活动","守纪积分","已兑换"]);header=1
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

INDEX_HTML = '<!doctype html>\n<html lang="zh-CN">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n  <meta name="theme-color" content="#5362e8">\n  <meta name="apple-mobile-web-app-capable" content="yes">\n  <meta name="mobile-web-app-capable" content="yes">\n  <meta name="apple-mobile-web-app-status-bar-style" content="default">\n  <meta name="apple-mobile-web-app-title" content="长缨辅学">\n  <link rel="manifest" href="/manifest.webmanifest?v=925">\n  <link rel="apple-touch-icon" sizes="180x180" href="/icon-180.png?v=925">\n  <link rel="icon" type="image/png" sizes="192x192" href="/icon-192.png?v=925">\n  <title>长缨辅学 V9.2.5</title>\n  \n  \n  <style>\n\n:root{\n  --bg:#f4f6fb;--card:#fff;--text:#1f2738;--muted:#778095;--line:#e5e8f0;\n  --primary:#5362e8;--soft:#eef0ff;--green:#18855d;--red:#d6485e;--amber:#d98b25;\n  --shadow:0 14px 38px rgba(38,48,95,.10)\n}\n*{box-sizing:border-box}\nhtml,body{margin:0;min-height:100%;min-height:100dvh;font-family:Inter,"PingFang SC","Microsoft YaHei",system-ui,sans-serif;background:var(--bg);color:var(--text);overscroll-behavior-y:none;-webkit-text-size-adjust:100%}\nbutton,input,select,textarea{font:inherit} button{cursor:pointer}\n.hidden{display:none!important}.muted{color:var(--muted)}\n.login-screen{min-height:100vh;min-height:100dvh;display:grid;place-items:center;padding:calc(20px + env(safe-area-inset-top)) calc(20px + env(safe-area-inset-right)) calc(20px + env(safe-area-inset-bottom)) calc(20px + env(safe-area-inset-left));background:linear-gradient(135deg,#edf0ff,#fafbff)}\n.login-card{width:min(430px,100%);background:#fff;border:1px solid var(--line);border-radius:28px;padding:28px;box-shadow:var(--shadow)}\n.logo{width:84px;height:84px;border-radius:26px;display:grid;place-items:center;font-size:42px;margin:auto;background:linear-gradient(135deg,var(--primary),#8b75ef)}\n.login-card h1{text-align:center;margin:12px 0 3px}.login-card>p{text-align:center;margin:0 0 22px}\nlabel{display:block;font-size:12px;font-weight:800;margin:12px 0 6px}\ninput,select,textarea{width:100%;padding:11px 12px;border:1px solid var(--line);border-radius:12px;background:#fff;color:var(--text);outline:none}\ninput:focus,select:focus,textarea:focus{border-color:#9ba5f1;box-shadow:0 0 0 3px rgba(83,98,232,.10)}\ntextarea{min-height:100px;resize:vertical}\n.btn{border:0;border-radius:12px;padding:10px 13px}.btn:disabled{opacity:.55;cursor:not-allowed}.primary{background:var(--primary);color:#fff;font-weight:800}.secondary{background:#eef1f6;color:#3b455e;font-weight:700}.danger{background:#fff0f2;color:var(--red)}.full{width:100%;margin-top:11px}\n.demo-box{margin-top:16px;padding:12px;background:#f7f8fc;border-radius:12px;color:var(--muted);font-size:12px;line-height:1.7}\n\n.shell{display:grid;grid-template-columns:258px minmax(0,1fr);min-height:100vh}\n.sidebar{height:100vh;position:sticky;top:0;background:#fff;border-right:1px solid var(--line);padding:17px;display:flex;flex-direction:column;z-index:30}\n.brand{display:flex;align-items:center;gap:10px;padding:5px 5px 18px}.brand>span{font-size:24px;background:var(--soft);padding:9px;border-radius:14px}.brand b,.brand small{display:block}.brand small{color:var(--muted);font-size:11px;margin-top:2px}\nnav{display:grid;gap:5px}.nav-btn{border:0;background:transparent;color:#626c81;border-radius:12px;padding:11px 12px;display:flex;gap:10px;align-items:center;text-align:left}.nav-btn.active{background:var(--soft);color:var(--primary);font-weight:800}\n.sidebar-foot{margin-top:auto}.user-badge{font-size:13px;padding:10px 4px}.user-badge b,.user-badge span{display:block}.user-badge span{color:var(--muted);font-size:12px}\n.main{padding:28px;min-width:0}.mobile-header{display:none}\n.page-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;margin-bottom:18px}.page-head h1{margin:0 0 5px;font-size:26px}.page-head p{margin:0;color:var(--muted)}\n.actions{display:flex;gap:8px;flex-wrap:wrap}\n.card{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:18px;box-shadow:0 8px 24px rgba(38,48,95,.05)}\n.hero{border-radius:23px;padding:24px;background:linear-gradient(135deg,#5362e8,#8a72ec);color:#fff}.hero p{color:#e7e9ff;max-width:760px}\n.grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.grid3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.grid4{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}\n.stat b{display:block;font-size:28px;color:var(--primary)}.stat small{color:var(--muted)}\n.section{margin-top:18px}.section h2{font-size:17px;margin:0 0 11px}\n.list{display:grid;gap:9px}.item{background:#fff;border:1px solid var(--line);border-radius:15px;padding:13px 14px;display:flex;justify-content:space-between;align-items:center;gap:10px}.item-main{min-width:0}.item-main b{display:block;margin-bottom:4px}.item-main small{color:var(--muted)}\n.badge{display:inline-flex;border-radius:999px;padding:4px 8px;background:var(--soft);color:var(--primary);font-size:11px;font-weight:800;white-space:nowrap;flex-shrink:0}.badge.green{background:#eaf8f2;color:var(--green)}.badge.red{background:#fff0f2;color:var(--red)}.badge.amber{background:#fff7e7;color:var(--amber)}\n.filters{display:flex;gap:9px;flex-wrap:wrap;margin-bottom:12px}.filters>*{width:auto;min-width:130px;flex:0 1 auto}\n.small{font-size:12px;padding:7px 9px}.empty{text-align:center;color:var(--muted);padding:36px}\n.table-wrap{overflow:auto}.table{width:100%;border-collapse:collapse;min-width:720px}.table th,.table td{padding:11px;border-bottom:1px solid var(--line);font-size:13px;text-align:left}.table th{color:var(--muted);font-weight:700}\n.progress{height:9px;border-radius:999px;background:#eaedf4;overflow:hidden}.progress i{height:100%;display:block;background:var(--primary)}\n.trend-list{display:grid;gap:10px}.trend-row{display:grid;grid-template-columns:minmax(76px,95px) 1fr auto;gap:10px;align-items:center}.trend-track{height:10px;border-radius:999px;background:#edf0f5;overflow:hidden}.trend-track i{display:block;height:100%;border-radius:999px;background:var(--primary)}.trend-track i.neg{background:var(--red)}.star-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}.star-card{padding:14px;border:1px solid var(--line);border-radius:18px;background:#fff}.star-card .medal{font-size:28px}.star-card b{display:block;margin-top:5px}.star-card small{display:block;color:var(--muted);margin-top:5px;line-height:1.5}\n.question{font-size:22px;line-height:1.6;font-weight:800;margin:18px 0}.option{width:100%;display:flex;align-items:center;gap:10px;text-align:left;padding:13px;margin:9px 0;background:#fff;border:1px solid var(--line);border-radius:14px}.option.selected{background:var(--soft);border-color:#a5adf3}.option.correct{background:#edf9f4;border-color:#75cfaa}.option.wrong{background:#fff1f3;border-color:#ef929e}.letter{width:31px;height:31px;border-radius:50%;display:grid;place-items:center;background:#f0f2f7;font-weight:800;flex:none}.answer{margin-top:14px;padding:13px;border-radius:14px;background:#f6f7fb;line-height:1.6}\n.chart-row{display:grid;grid-template-columns:repeat(10,1fr);align-items:end;height:180px;gap:8px;padding:10px 4px 0}.bar{background:linear-gradient(180deg,#7580ef,#5362e8);border-radius:8px 8px 2px 2px;min-height:4px;position:relative}.bar span{position:absolute;bottom:-24px;left:50%;transform:translateX(-50%);font-size:10px;color:var(--muted);white-space:nowrap}\n.knowledge{display:grid;gap:9px}.knowledge-row{display:grid;grid-template-columns:minmax(110px,1fr) 3fr 55px;gap:10px;align-items:center}.knowledge-row small{overflow:hidden;text-overflow:ellipsis}.knowledge-meter{height:9px;background:#edf0f5;border-radius:999px;overflow:hidden}.knowledge-meter i{display:block;height:100%;background:var(--primary)}\n.toast{position:fixed;top:calc(18px + env(safe-area-inset-top));right:calc(18px + env(safe-area-inset-right));z-index:100;background:#252b3e;color:#fff;padding:11px 15px;border-radius:12px;box-shadow:var(--shadow);opacity:0;transform:translateY(-10px);transition:.2s;pointer-events:none}.toast.show{opacity:1;transform:none}\ndialog{border:0;background:transparent;padding:16px;width:min(700px,100%)}dialog::backdrop{background:rgba(22,27,42,.47)}.modal-card{background:#fff;border-radius:22px;padding:18px;max-height:min(88vh,calc(var(--visual-vh,100dvh) - 28px));overflow:auto;box-shadow:var(--shadow);overscroll-behavior:contain}.modal-head{display:flex;align-items:center;justify-content:space-between}.modal-head h3{margin:0}.icon-btn{border:0;background:transparent;padding:8px}body.modal-open{overflow:hidden}body.modal-open .bottom-nav{display:none!important}\n.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}\n.note{font-size:12px;background:#fff7e7;color:#7b5719;padding:10px 12px;border-radius:12px}\n.rank1{font-weight:900;color:#b37511}\n.mobile-only{display:none}.status-line{display:flex;gap:6px;flex-wrap:wrap;align-items:center}\n.history-list{display:grid;gap:8px;margin-top:12px}\n.history-row{display:grid;grid-template-columns:minmax(0,1fr);gap:4px;padding:10px 12px;border-radius:14px;background:#f2f3ff;border:1px solid #e2e5ff;min-width:0}\n.history-title{font-weight:800;color:#4f5ee6;line-height:1.35;overflow-wrap:anywhere;word-break:break-word}\n.history-period{font-size:13px;color:#69748e;line-height:1.45;overflow-wrap:anywhere;word-break:break-word}\n.history-row.current{background:#eef9f3;border-color:#d8f0e3}\n.history-row.current .history-title{color:#2f855a}.account-card{display:grid;gap:10px}.account-card .account-actions{display:flex;gap:8px;flex-wrap:wrap}.account-card .account-actions .btn{flex:1}.bottom-nav{display:none}.compact-help{margin-top:10px}.compact-help summary{cursor:pointer;font-weight:800;color:var(--primary)}.compact-help p{margin:8px 0 0;line-height:1.65}\n\n.network-banner{position:fixed;left:12px;right:12px;top:calc(8px + env(safe-area-inset-top));z-index:110;background:#252b3e;color:#fff;border-radius:14px;padding:10px 14px;text-align:center;font-size:12px;box-shadow:var(--shadow)}\n.app-runtime{display:flex;gap:7px;flex-wrap:wrap;align-items:center;margin:10px 0}.app-runtime .badge{font-size:12px}.install-help{line-height:1.7;margin:9px 0 0}.safe-bottom{padding-bottom:calc(8px + env(safe-area-inset-bottom))}\n.timeline{display:grid;gap:0}.timeline-item{display:grid;grid-template-columns:34px 1fr;gap:10px;position:relative;padding-bottom:14px}.timeline-item:not(:last-child)::before{content:"";position:absolute;left:16px;top:32px;bottom:0;width:2px;background:var(--line)}.timeline-icon{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:var(--soft);z-index:1}.timeline-main{padding:7px 0}.timeline-main b{display:block}.timeline-main small{display:block;color:var(--muted);line-height:1.5;margin-top:3px}\n\n@media(max-width:960px){\n .shell{grid-template-columns:1fr}.sidebar{position:fixed;left:-270px;width:258px;transition:.2s;box-shadow:var(--shadow)}.sidebar.open{left:0}\n .main{padding:0 14px 25px}.mobile-header{display:flex;position:sticky;top:0;z-index:20;margin:0 -14px 18px;padding:calc(12px + env(safe-area-inset-top)) 14px 12px;align-items:center;justify-content:space-between;background:rgba(255,255,255,.96);border-bottom:1px solid var(--line)}\n .grid4{grid-template-columns:repeat(2,1fr)}\n}\n@media(max-width:650px){\n .main{padding-bottom:calc(116px + env(safe-area-inset-bottom))}.grid2,.grid3{grid-template-columns:1fr}.page-head{display:block;margin-bottom:13px}.page-head h1{font-size:22px}.page-head p{font-size:13px}.page-head .actions{margin-top:10px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.page-head .actions .btn{width:100%;padding:10px 8px}\n .card{padding:14px;border-radius:16px}.section{margin-top:13px}.stat b{font-size:24px}.form-grid{grid-template-columns:1fr}.filters{display:grid;grid-template-columns:1fr 1fr;gap:8px}.filters>*{width:100%;min-width:0}.question{font-size:19px}\n .knowledge-row{grid-template-columns:92px 1fr 42px}.desktop-only{display:none!important}.mobile-only{display:block}.item{align-items:flex-start}.toast{left:14px;right:14px;top:calc(12px + env(safe-area-inset-top));text-align:center}\n dialog{padding:0;align-items:end}.modal-card{border-radius:22px 22px 0 0;max-height:calc(var(--visual-vh,100dvh) - env(safe-area-inset-top) - 8px);padding-bottom:calc(28px + env(safe-area-inset-bottom));scroll-padding-bottom:calc(28px + env(safe-area-inset-bottom));overscroll-behavior:contain}.modal-head{position:sticky;top:-18px;z-index:4;background:#fff;padding:18px 0 10px;margin-top:-18px;border-bottom:1px solid var(--line)}.bottom-nav{position:fixed;left:0;right:0;bottom:0;z-index:25;display:grid;grid-template-columns:repeat(var(--bottom-count,5),minmax(0,1fr));padding:7px 8px calc(7px + env(safe-area-inset-bottom));background:rgba(255,255,255,.97);border-top:1px solid var(--line);box-shadow:0 -8px 24px rgba(38,48,95,.08)}.bottom-nav:empty{display:none}.bottom-nav-btn{border:0;background:transparent;color:#778095;display:grid;place-items:center;gap:2px;padding:4px 2px;font-size:10px;min-width:0}.bottom-nav-btn span{font-size:20px}.bottom-nav-btn.active{color:var(--primary);font-weight:800}\n}\n\n.teach-hero{background:linear-gradient(135deg,#4658df,#7a66e9);color:#fff}.teach-hero p{color:#eef0ff}.subject-tabs{display:flex;gap:8px;flex-wrap:wrap}.subject-tabs .btn.active{background:var(--primary);color:#fff}.lesson-meta{display:flex;gap:6px;flex-wrap:wrap;margin-top:7px}.level-badge{display:inline-flex;min-width:30px;justify-content:center;border-radius:999px;padding:5px 9px;font-size:12px;font-weight:900}.level-C{background:#f4eefe;color:#6f42c1}.level-B{background:#eef4ff;color:#315fc4}.level-A{background:#eaf8f2;color:#18855d}.slide-view{min-height:280px;display:grid;place-items:center;text-align:center;padding:26px;border-radius:18px;background:linear-gradient(135deg,#f5f6ff,#fff);border:1px solid var(--line)}.slide-view h2{font-size:26px;line-height:1.5}.adaptive-q{padding:14px;border:1px solid var(--line);border-radius:15px;margin:10px 0}.adaptive-q b{display:block;margin-bottom:9px}.adaptive-option{display:flex;gap:8px;align-items:flex-start;padding:8px;border-radius:10px}.adaptive-option input{width:auto;margin-top:4px}.lesson-tools{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}.lesson-tools .btn{flex:0 0 auto}.teaching-timeline{white-space:pre-wrap;line-height:1.75}.essay-box textarea{min-height:150px}.stage-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}@media(max-width:650px){.stage-grid{grid-template-columns:1fr}.lesson-tools{display:grid;grid-template-columns:1fr 1fr}.lesson-tools .btn{width:100%}.slide-view{min-height:230px}.slide-view h2{font-size:22px}}\n\n\n.reward-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.reward-card{position:relative}.reward-icon{font-size:36px}.point-positive{color:var(--green);font-weight:900}.point-negative{color:var(--red);font-weight:900}.rule-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.rule-btn{border:1px solid var(--line);background:#fff;border-radius:14px;padding:11px;text-align:left}.rule-btn.active{border-color:var(--primary);box-shadow:0 0 0 3px rgba(83,98,232,.10);background:var(--soft)}.check-card{display:flex;align-items:center;gap:10px}.check-card input{width:auto}.split-tabs{display:flex;gap:8px;flex-wrap:wrap}.split-tabs .btn.active{background:var(--primary);color:#fff}.ledger-row{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:start}.ledger-row small{display:block;color:var(--muted);margin-top:4px}@media(max-width:650px){.reward-grid{grid-template-columns:1fr 1fr}.rule-grid{grid-template-columns:1fr 1fr}}\n</style>\n</head>\n<body>\n<div id="toast" class="toast"></div><div id="networkBanner" class="network-banner hidden">当前处于离线模式，已显示本地应用界面。连接网络后可继续登录和同步数据。</div><div id="sessionCheck" class="hidden" style="position:fixed;inset:0;z-index:9998;background:rgba(244,246,251,.96);display:grid;place-items:center;text-align:center;padding:24px"><div><div style="font-size:42px">📚</div><h3>正在验证登录状态…</h3><p class="muted">请稍候</p></div></div>\n\n<section id="loginScreen" class="login-screen">\n  <div class="login-card">\n    <div class="logo">📚</div>\n    <h1>长缨辅学</h1>\n    <p class="muted">V9.2.5 商业版 C2.5</p>\n    <label>服务器地址（网址版保持默认即可）</label>\n    <input id="serverURL" placeholder="http://127.0.0.1:8000">\n    <label>账号</label>\n    <input id="username" placeholder="请输入账号" autocomplete="username">\n    <label>密码</label>\n    <input id="password" type="password" value="" placeholder="请输入密码" autocomplete="current-password">\n    <div style="display:grid;gap:8px;margin:10px 0 14px">\n      <label style="display:flex;align-items:center;gap:8px;margin:0;font-weight:500"><input id="showPwd" type="checkbox" style="width:auto">显示密码</label>\n      <label style="display:flex;align-items:center;gap:8px;margin:0;font-weight:500"><input id="rememberLogin" type="checkbox" style="width:auto">在此设备保持登录（个人设备）</label>\n      <small class="muted">共享、学校公共设备请不要勾选；未勾选时只在当前浏览器会话中保存登录。</small>\n    </div><button id="loginBtn" class="btn primary full">登录</button>\n    <button id="continueSessionBtn" class="btn secondary full hidden">继续上次登录</button>\n    <button id="offlineBtn" class="btn secondary full">离线学生体验</button>\n    <div class="actions" style="justify-content:center;margin-top:12px"><button id="loginPrivacy" class="btn secondary small">隐私政策</button><button id="loginTerms" class="btn secondary small">用户协议</button></div><button id="loginInstallBtn" class="btn secondary full hidden">安装到设备</button>\n    <div class="demo-box">请使用管理员或学校分配的账号登录。App 启动时不会主动连接服务器；登录、继续上次登录或同步操作时才会联网。首次登录如提示修改密码，请设置自己的安全密码。</div>\n  </div>\n</section>\n\n<div id="shell" class="shell hidden">\n  <aside id="sidebar" class="sidebar">\n    <div class="brand"><span>📚</span><div><b>长缨辅学</b><small>V9.2.5 商业版 C2.5</small></div></div>\n    <nav id="nav"></nav>\n    <div class="sidebar-foot">\n      <div id="userBadge" class="user-badge"></div>\n      <button id="logoutBtn" class="btn secondary full">退出登录</button>\n    </div>\n  </aside>\n  <main class="main">\n    <header class="mobile-header">\n      <button id="menuBtn" class="icon-btn">☰</button>\n      <b>长缨辅学 V9.2.5</b>\n      <span></span>\n    </header>\n    <div id="page"></div>\n  </main>\n  <nav id="bottomNav" class="bottom-nav"></nav>\n</div>\n\n<dialog id="modal">\n  <div class="modal-card">\n    <div class="modal-head"><h3 id="modalTitle"></h3><button id="modalClose" class="icon-btn">✕</button></div>\n    <div id="modalBody"></div>\n  </div>\n</dialog>\n\n<script>\n\nconst $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];\nconst defaultAPI=(location.protocol==="http:"||location.protocol==="https:")?location.origin:"http://127.0.0.1:8000";\n// V7.1.8: keep the V7.1.7 browser-session migration for backward compatibility.\nif(localStorage.getItem("v6Token") && !localStorage.getItem("v717Migrated")){\n sessionStorage.setItem("v717Token",localStorage.getItem("v6Token")||"");\n sessionStorage.setItem("v717User",localStorage.getItem("v6User")||"null");\n localStorage.removeItem("v6Token");localStorage.removeItem("v6User");\n localStorage.setItem("v717Migrated","1");\n}\nconst initialRemember=localStorage.getItem("v717Remember")==="1";\nconst state={\n api:localStorage.getItem("v6Server")||defaultAPI,\n token:(initialRemember?localStorage.getItem("v717Token"):sessionStorage.getItem("v717Token"))||"",\n user:JSON.parse((initialRemember?localStorage.getItem("v717User"):sessionStorage.getItem("v717User"))||"null"),\n remember:initialRemember,\n offline:false,page:"",pointsAdminTab:sessionStorage.getItem("v771PointsAdminTab")||"rules"\n};\nfunction saveAuth(){\n const store=state.remember?localStorage:sessionStorage;\n const other=state.remember?sessionStorage:localStorage;\n store.setItem("v717Token",state.token||"");store.setItem("v717User",JSON.stringify(state.user||null));\n other.removeItem("v717Token");other.removeItem("v717User");\n localStorage.setItem("v717Remember",state.remember?"1":"0");\n}\nfunction clearAuth(){\n state.token="";state.user=null;state.remember=false;\n localStorage.removeItem("v717Token");localStorage.removeItem("v717User");localStorage.removeItem("v717Remember");\n sessionStorage.removeItem("v717Token");sessionStorage.removeItem("v717User");sessionStorage.removeItem("v771PointsAdminTab");\n state.pointsAdminTab="rules";\n localStorage.removeItem("v6Token");localStorage.removeItem("v6User");\n}\nconst offlineBank=[\n {id:1,grade:1,subject:"数学",textbook:"人教版",semester:"上册",unit:"第一单元",knowledge:"20以内加法",text:"7 + 5 = ?",options:["10","11","12","13"],correctIndex:2,explanation:"7+5=12。"},\n {id:2,grade:3,subject:"数学",textbook:"人教版",semester:"上册",unit:"第一单元",knowledge:"时分秒",text:"1分钟等于多少秒？",options:["30","60","90","100"],correctIndex:1,explanation:"1分钟=60秒。"},\n {id:3,grade:3,subject:"语文",textbook:"人教版",semester:"上册",unit:"第一单元",knowledge:"词语",text:"“绚丽多彩”的近义词是？",options:["五颜六色","灰暗无光","一模一样","安安静静"],correctIndex:0,explanation:"与“五颜六色”意思相近。"},\n {id:4,grade:3,subject:"英语",textbook:"人教PEP",semester:"上册",unit:"Unit 1",knowledge:"单词",text:"“尺子”的英文是？",options:["book","ruler","pencil","bag"],correctIndex:1,explanation:"ruler=尺子。"},\n {id:5,grade:5,subject:"数学",textbook:"北师大版",semester:"下册",unit:"第三单元",knowledge:"分数",text:"1/2 + 1/4 = ?",options:["1/6","2/6","3/4","1"],correctIndex:2,explanation:"通分后为3/4。"}\n];\n\nconst menus={\n admin:[["admin","🛡️","平台总览"],["subscription","💳","套餐授权"],["users","👥","账号管理"],["pointsAdmin","⭐","积分奖励"],["teaching","🎯","定制教学"],["imports","📥","批量导入"],["catalog","📚","教材题库"],["adminAudit","🧾","全校审计"],["system","⚙️","系统设置"]],\n teacher:[["teacher","📊","教师工作台"],["classes","👥","班级学生"],["classPoints","⭐","课堂积分"],["teaching","🎯","定制教学"],["catalog","📚","教材题库"],["papers","📝","组卷作业"],["analytics","📈","学情分析"],["audit","🧾","操作记录"],["leaderboard","🏆","排行榜"],["account","👤","我的"]],\n student:[["student","🏠","学习首页"],["syncLearning","🎯","同步课堂"],["rewards","🎁","积分奖励"],["assignments","📝","我的作业"],["practice","✏️","自主练习"],["progress","📈","我的学情"],["leaderboard","🏆","班级排行"],["account","👤","我的"]],\n parent:[["parent","👨\u200d👩\u200d👧","家长首页"],["childLearning","🎯","孩子课程"],["childRewards","🎁","课堂表现"],["childProgress","📈","孩子学情"],["childAssignments","📝","孩子作业"],["account","👤","我的"]],\n offline:[["practice","✏️","离线练习"],["account","👤","本机设置"]]\n};\n\nfunction esc(v=""){return String(v).replace(/[&<>"\']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",\'"\':"&quot;","\'":"&#039;"}[m]))}\nfunction toast(msg){const t=$("#toast");t.textContent=msg;t.classList.add("show");setTimeout(()=>t.classList.remove("show"),2300)}\nfunction roleName(r){return ({admin:"管理员",teacher:"教师",student:"学生",parent:"家长"})[r]||r}\nfunction loginLegal(path){const base=($("#serverURL")?.value||state.api||location.origin).trim().replace(/\\/$/,"");window.open(base+path,"_blank","noopener")}\nlet deferredInstallPrompt=null;\nfunction isIOS(){return /iphone|ipad|ipod/i.test(navigator.userAgent||"")}\nfunction isStandalone(){return window.matchMedia?.("(display-mode: standalone)").matches===true || navigator.standalone===true}\nfunction clientModeLabel(){return isStandalone()?"App/主屏幕模式":"浏览器模式"}\nfunction notificationLabel(){if(!("Notification" in window))return "通知不支持";return Notification.permission==="granted"?"通知已允许":(Notification.permission==="denied"?"通知已拒绝":"通知未授权")}\nfunction installHelpText(){if(isStandalone())return "当前已按独立 App 模式运行。";if(deferredInstallPrompt)return "当前浏览器支持一键安装，可直接安装到设备。";if(isIOS())return "iPhone/iPad：Safari → 分享 → 添加到主屏幕。";return "可通过浏览器菜单选择“安装应用”或“添加到主屏幕”。"}\nlet networkHint=navigator.onLine!==false;\nfunction refreshNetworkBanner(){const b=$("#networkBanner");if(!b)return;b.classList.toggle("hidden",networkHint)}\nfunction friendlyNetworkError(err){\n const msg=String(err?.message||err||"").trim();\n if(!networkHint||navigator.onLine===false)return "当前处于离线模式，已显示本地应用界面。连接网络后可继续登录和同步数据。";\n if(/load failed|failed to fetch|networkerror|network request failed/i.test(msg))return "暂时无法连接服务器，请检查网络后重试。";\n return msg||"请求失败，请稍后重试。";\n}\nfunction markNetwork(ok){\n networkHint=!!ok;\n syncNetworkUI(false);\n}\nfunction updateContinueSessionButton(){\n const b=$("#continueSessionBtn");\n if(!b)return;\n const has=!!(state.token&&state.user&&!state.offline);\n b.classList.toggle("hidden",!has);\n if(has)b.textContent=`继续上次登录${state.user?.name?`（${state.user.name}）`:""}`;\n}\nfunction syncNetworkUI(showToast=false){\n const online=networkHint;\n refreshNetworkBanner();\n const btn=$("#loginBtn");\n if(btn&&!btn.dataset.busy){btn.disabled=!online;btn.textContent=online?"登录":"等待网络恢复";}\n const c=$("#continueSessionBtn");\n if(c&&!c.dataset.busy)c.disabled=!online;\n updateContinueSessionButton();\n if(showToast)toast(online?"网络已恢复，可以登录或继续上次登录。":"当前处于离线模式，已显示本地应用界面。连接网络后可继续登录和同步数据。");\n if(state.page==="account")account();\n}\nfunction syncInstallButtons(){const b=$("#loginInstallBtn");if(!b)return;b.classList.toggle("hidden",isStandalone());b.textContent=isStandalone()?"已安装":"安装到设备"}\nasync function promptInstall(){\n if(isStandalone()){toast("当前已在 App/主屏幕模式运行");return}\n if(deferredInstallPrompt){const p=deferredInstallPrompt;deferredInstallPrompt=null;await p.prompt();const c=await p.userChoice;toast(c.outcome==="accepted"?"已开始安装":"已取消安装");syncInstallButtons();return}\n if(isIOS()){modal("添加到主屏幕",`<div class="note">在 Safari 底部点“分享” → “添加到主屏幕” → “添加”。之后从主屏幕打开即可获得独立 App 体验。</div>`);return}\n toast("请使用浏览器菜单中的“安装应用/添加到主屏幕”")\n}\nasync function requestNotificationPermission(){\n if(!("Notification" in window)){toast("当前浏览器不支持通知权限");return}\n if(isIOS()&&!isStandalone()){toast("iPhone/iPad 请先添加到主屏幕，再开启通知权限");return}\n try{const p=await Notification.requestPermission();toast(p==="granted"?"通知权限已允许":"通知权限未开启");if(state.page==="account")account()}catch(_){toast("通知权限请求失败")}\n}\nfunction requestedDeepPage(){try{return new URL(location.href).searchParams.get("page")||""}catch(_){return ""}}\nfunction featureAvailable(name){\n const f=state.user?.subscription?.features;\n return !f || f[name]!==false;\n}\nfunction commercialMenuAllowed(id){\n const featureByPage={imports:"bulk_import",adminAudit:"school_audit"};\n const f=featureByPage[id];\n return !f || featureAvailable(f);\n}\nfunction roleAllowsPage(p){const key=state.offline?"offline":state.user?.role;return (menus[key]||[]).some(x=>x[0]===p&&commercialMenuAllowed(x[0]))}\nwindow.addEventListener("online",()=>{networkHint=true;syncNetworkUI(true)});\nwindow.addEventListener("offline",()=>{networkHint=false;syncNetworkUI(true)});\nwindow.addEventListener("beforeinstallprompt",e=>{e.preventDefault();deferredInstallPrompt=e;syncInstallButtons();if(state.page==="account")account()});\nwindow.addEventListener("appinstalled",()=>{deferredInstallPrompt=null;syncInstallButtons();toast("长缨辅学已安装到设备")});\nfunction head(t,s,a=""){return `<div class="page-head"><div><h1>${t}</h1><p>${s}</p></div><div class="actions">${a}</div></div>`}\n\nfunction searchKindName(k){return ({student:"学生",class:"班级",assignment:"作业",followup:"跟进",user:"账号"})[k]||k}\n\nfunction profileEventLabel(t){return ({point:"课堂积分",reward:"奖励",followup:"跟进事项",followup_log:"跟进记录",academic:"学习成绩"})[t]||"成长记录"}\nasync function growthProfileClassContext(cid){\n const d=await api(`/teacher/points/classes/${cid}`);\n return {cls:d.class,students:d.students||[]};\n}\nasync function openStudentGrowthProfile(sid,cid=null,name=""){\n try{\n  const d=await api(`/teacher/students/${sid}/growth-profile${cid?`?class_id=${cid}`:""}`);\n  const a=d.academic||{},p=d.points||{},f=d.followup||{},s=d.student||{};\n  const parentText=(s.parents||[]).length?(s.parents||[]).map(x=>`${esc(x.name)}（${esc(x.username)}）`).join("、"):"未绑定";\n  const weak=(a.weakKnowledge||[]).slice(0,6).map(x=>`<div class="knowledge-row"><small>${esc(x.knowledge)}</small><div class="knowledge-meter"><i style="width:${x.accuracy}%"></i></div><b>${x.accuracy}%</b></div>`).join("")||`<span class="muted">暂无知识点数据</span>`;\n  const assignments=(a.recentAssignments||[]).map(x=>`<div class="item"><div class="item-main"><b>${esc(x.title)}</b><small>${esc(x.subject||"")} · 截止 ${esc(x.dueDate||"")} ${x.completed&&x.score!==null?`· ${x.score}分`:""}</small></div><span class="badge ${statusClass(x.statusCode)}">${esc(x.status||"")}</span></div>`).join("")||`<span class="muted">暂无班级作业记录</span>`;\n  const submissions=(a.recentSubmissions||[]).map(x=>`<div class="item"><div class="item-main"><b>${esc(x.title)}</b><small>${esc(x.subject||"综合")} · ${esc(x.submittedAt||"")} · ${x.correct}/${x.total}</small></div><span class="badge ${x.score>=80?"green":x.score<60?"red":""}">${x.score}分</span></div>`).join("")||`<span class="muted">暂无学习提交记录</span>`;\n  const recentPoints=(p.recent||[]).slice(0,8).map(x=>`<div class="item"><div class="item-main"><b>${esc(x.reason||"课堂记录")}</b><small>${esc(x.createdAt||"")}${x.note?` · ${esc(x.note)}`:""}</small></div><b class="${x.points>=0?"point-positive":"point-negative"}">${x.points>0?"+":""}${x.points}</b></div>`).join("")||`<span class="muted">暂无课堂积分记录</span>`;\n  const followups=(f.cases||[]).map(x=>`<div class="item"><div class="item-main"><b>${esc(x.title)}</b><small>${esc(x.categoryName||"")} · ${esc(x.statusName||"")}${x.dueDate?` · ${esc(x.dueLabel||x.dueDate)}`:""}</small></div><span class="badge ${x.status==="done"?"green":x.overdue?"red":""}">${esc(x.statusName||"")}</span></div>`).join("")||`<span class="muted">暂无学生跟进事项</span>`;\n  const contacts=(f.parentContacts||[]).map(x=>`<div class="item"><div class="item-main"><b>💬 家长沟通</b><small>${esc(x.createdAt||"")} · ${esc(x.actorName||"教师")}<br>${esc(x.content||"")}</small></div></div>`).join("")||`<span class="muted">暂无家长沟通记录</span>`;\n  const timeline=(d.timeline||[]).slice(0,18).map(x=>`<div class="item"><div style="font-size:22px">${esc(x.icon||"•")}</div><div class="item-main" style="flex:1"><b>${esc(x.title||profileEventLabel(x.type))}</b><small>${esc(x.time||"")}<br>${esc(x.detail||"")}</small></div></div>`).join("")||`<span class="muted">暂无成长时间线</span>`;\n  const highlights=(d.highlights||[]).map(x=>`<div class="item"><div class="item-main"><small>✨ ${esc(x)}</small></div></div>`).join("");\n  const suggestions=(d.suggestions||[]).map(x=>`<div class="item"><div class="item-main"><small>📌 ${esc(x)}</small></div></div>`).join("");\n  const rawHistory=(d.classHistory||[]).slice().reverse();\n  const displayHistory=[],seenHistory=new Set();\n  rawHistory.forEach(x=>{\n   const joinedFull=x.joinedAt||"",leftFull=x.leftAt||"";\n   const status=x.current?"在读":(x.leaveReasonName||"已离班");\n   const k=[x.classID||x.className,joinedFull,leftFull,x.leaveReason||"",x.current?"1":"0"].join("|");\n   if(seenHistory.has(k))return;\n   seenHistory.add(k);\n   displayHistory.push({...x,_joinedFull:joinedFull,_leftFull:leftFull,_status:status});\n  });\n  const dayKey=v=>(v||"").slice(0,10);\n  const sameDayCounts={};\n  displayHistory.forEach(x=>{\n   const k=`${x.classID||x.className}|${dayKey(x._joinedFull)}|${dayKey(x._leftFull)}|${x._status}`;\n   sameDayCounts[k]=(sameDayCounts[k]||0)+1;\n  });\n  const fmtStamp=(v,showTime=false)=>{\n   if(!v)return "";\n   const day=v.slice(0,10),time=(v.split("T")[1]||v.split(" ")[1]||"").slice(0,5);\n   return showTime&&time?`${day} ${time}`:day;\n  };\n  const sameDayArchived=new Set(displayHistory.filter(x=>!x.current&&x._leftFull&&/毕业|归档/.test(x._status||"")).map(x=>`${x.classID||x.className}|${dayKey(x._leftFull)}`));\n  const history=displayHistory.map(x=>{\n   const countKey=`${x.classID||x.className}|${dayKey(x._joinedFull)}|${dayKey(x._leftFull)}|${x._status}`;\n   const showTime=(sameDayCounts[countKey]||0)>1 || (x._joinedFull&&x._leftFull&&dayKey(x._joinedFull)===dayKey(x._leftFull));\n   const joined=fmtStamp(x._joinedFull,showTime),left=fmtStamp(x._leftFull,showTime);\n   const period=joined?`${joined} → ${left||"至今"}`:(left?`至 ${left}`:"");\n   let status=x._status;\n   if(x.current && x._joinedFull && sameDayArchived.has(`${x.classID||x.className}|${dayKey(x._joinedFull)}`))status="恢复入班";\n   return `<div class="history-row ${x.current?"current":""}"><div class="history-title">${esc(x.className)} · ${esc(status)}</div><div class="history-period">${esc(period||"时间未记录")}</div></div>`\n  }).join("")||`<span class="muted">暂无班级历程</span>`;\n  const clsid=s.classID||cid||"";\n  modal(`${esc(s.name||name||"学生")} · 学生成长档案`,`\n   <div class="note">成长档案汇总学习、课堂表现、教师跟进和家校沟通，仅用于教师观察与教学支持，不作为自动处分或高风险决策的唯一依据。</div>\n   <div class="section card"><div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap"><div><h2 style="font-size:24px;margin-bottom:8px">${esc(s.name||"")}</h2><p class="muted" style="margin:0">${s.grade||"—"}年级 · ${esc(s.className||"未分班")} · 账号 ${esc(s.username||"")}</p><p class="muted" style="margin:6px 0 0">家长：${parentText}</p></div><span class="badge ${s.active?"green":"red"}">${s.active?"在读":"账号停用"}</span></div><div class="history-list">${history}</div><p class="muted" style="font-size:12px;margin:10px 0 0">班级历程按真实时间轴展示；只合并完全一致的重复事件。同一天内发生多次真实调班或恢复入班时，会显示具体时间并全部保留。</p></div>\n   <div class="grid4">${stat(a.avgScore??0,"累计平均分")}${stat((a.completionRate??0)+"%","班级作业完成率")}${stat((p.weekly?.net??0)>0?`+${p.weekly.net}`:(p.weekly?.net??0),"近7天课堂净表现")}${stat(f.open??0,"未完成跟进")}</div>\n   <div class="section grid2"><div class="card"><h2>成长亮点</h2><div class="list">${highlights}</div></div><div class="card"><h2>教学提示</h2><div class="list">${suggestions}</div></div></div>\n   <div class="section card"><h2>学习与作业</h2><div class="grid4">${stat(a.submissionCount??0,"累计提交")}${stat((a.accuracy??0)+"%","累计答题正确率")}${stat(a.pendingAssignments??0,"待完成作业")}${stat(a.overdueAssignments??0,"逾期未交")}</div><h3>近期班级作业</h3><div class="list">${assignments}</div><h3 style="margin-top:16px">近期学习成绩</h3><div class="list">${submissions}</div><h3 style="margin-top:16px">知识点掌握</h3><div class="knowledge">${weak}</div></div>\n   <div class="section card"><h2>课堂表现</h2><div class="grid4">${stat(p.summary?.available??0,"可用积分")}${stat(p.weekly?.activity??0,"近7天活动")}${stat(p.weekly?.discipline??0,"近7天守纪")}${stat(p.monthly?.net??0,"近30天净表现")}</div><div class="list" style="margin-top:12px">${recentPoints}</div></div>\n   <div class="section grid2"><div class="card"><h2>学生跟进</h2><div class="grid3">${stat(f.open??0,"未完成")}${stat(f.inProgress??0,"跟进中")}${stat(f.overdue??0,"已逾期")}</div><div class="list" style="margin-top:12px">${followups}</div></div><div class="card"><h2>家校沟通</h2><div class="list">${contacts}</div></div></div>\n   <div class="section card"><h2>成长时间线</h2><div class="list">${timeline}</div></div>\n   <div class="section actions">${featureAvailable("growth_report")?`<button id="profileGrowthReport" class="btn primary">导出成长报告</button>`:""}<button id="profileStudentReport" class="btn secondary">导出个人成绩单</button>${clsid?`<button id="profileFollowups" class="btn secondary">管理跟进事项</button><button id="profileNewFollowup" class="btn secondary">＋新建跟进</button>`:""}</div>\n  `);\n  if($("#profileGrowthReport"))$("#profileGrowthReport").onclick=async()=>{try{await downloadWithAuth(`/teacher/students/${sid}/growth-report.xlsx${clsid?`?class_id=${clsid}`:""}`,`${s.name||"学生"}_成长报告.xlsx`);toast("学生成长报告已导出")}catch(e){toast(e.message)}};\n  $("#profileStudentReport").onclick=async()=>{try{await downloadWithAuth(`/teacher/students/${sid}/report.xlsx`,`${s.name||"学生"}_个人成绩单.xlsx`);toast("学生成绩单已导出")}catch(e){toast(e.message)}};\n  if(clsid&&$("#profileFollowups"))$("#profileFollowups").onclick=async()=>{try{const ctx=await growthProfileClassContext(+clsid);openStudentFollowups(+clsid,ctx.cls,ctx.students,sid,s.name)}catch(e){toast(e.message)}};\n  if(clsid&&$("#profileNewFollowup"))$("#profileNewFollowup").onclick=async()=>{try{const ctx=await growthProfileClassContext(+clsid);createFollowUpForm(+clsid,ctx.cls,ctx.students,sid,s.name)}catch(e){toast(e.message)}};\n }catch(e){toast(e.message)}\n}\n\nfunction zhStatusText(s){return ({open:"待跟进",doing:"跟进中",in_progress:"跟进中",done:"已完成",pending:"待处理",completed:"已完成"})[s]||s}\nfunction openSearchResult(r){\n closeModal();\n if(r.kind==="student"&&r.studentID){setTimeout(()=>openStudentGrowthProfile(+r.studentID,r.classID?+r.classID:null,r.title||""),50);return}\n if(r.classID)state.pointClassID=+r.classID;\n if(r.target==="classPoints"){go("classPoints");return}\n if(r.target==="papers"){go("papers");return}\n if(r.target==="users"){go("users");return}\n}\nfunction globalSearchDialog(){\n modal("快捷搜索",`\n  <div class="note">教师可搜索学生、班级、作业和跟进事项；管理员可搜索账号和班级。</div>\n  <label>搜索关键词</label>\n  <input id="globalSearchInput" placeholder="例如：小明、三年级、课后练习" autocomplete="off">\n  <div id="globalSearchResult" class="list" style="margin-top:12px"><div class="empty">输入关键词开始搜索</div></div>`);\n const input=$("#globalSearchInput"),box=$("#globalSearchResult");let timer=null,seq=0;\n const run=async()=>{\n  const q=input.value.trim();\n  if(!q){box.innerHTML=`<div class="empty">输入关键词开始搜索</div>`;return}\n  const current=++seq;box.innerHTML=`<div class="empty">正在搜索…</div>`;\n  try{\n   const d=await api(`/global-search?q=${encodeURIComponent(q)}&limit=30`);\n   if(current!==seq)return;\n   const rows=d.results||[];\n   box.innerHTML=rows.length?rows.map((r,i)=>`<button class="item searchResult" data-i="${i}" style="width:100%;text-align:left;background:white;border:1px solid var(--line)"><div class="item-main"><b>${esc(r.title)}</b><small><span class="badge">${esc(searchKindName(r.kind))}</span> ${esc((r.subtitle||"").replace(/\\bin_progress\\b/g,"跟进中").replace(/\\bopen\\b/g,"待跟进").replace(/\\bdone\\b/g,"已完成"))}</small></div><span>›</span></button>`).join(""):`<div class="empty">没有匹配结果</div>`;\n   $$(".searchResult").forEach(b=>b.onclick=()=>openSearchResult(rows[+b.dataset.i]));\n  }catch(e){box.innerHTML=`<div class="empty">${esc(e.message||"搜索失败")}</div>`}\n };\n input.oninput=()=>{clearTimeout(timer);timer=setTimeout(run,220)};\n setTimeout(()=>input.focus(),60);\n}\n\nfunction stat(v,t){return `<div class="card stat"><b>${esc(v)}</b><small>${esc(t)}</small></div>`}\nfunction pointTrendHTML(rows=[]){if(!rows.length)return `<span class="muted">暂无趋势数据</span>`;const max=Math.max(1,...rows.map(x=>Math.abs(+x.net||0)));return `<div class="trend-list">${rows.map(x=>{const n=+x.net||0,p=Math.max(4,Math.round(Math.abs(n)/max*100));return `<div class="trend-row"><small>${esc(x.label)}</small><div><div class="trend-track"><i class="${n<0?"neg":""}" style="width:${p}%"></i></div><small class="muted">活动 ${x.activity||0} · 守纪 ${x.discipline||0} · 奖励 ${x.autoRewardCount||0}</small></div><b class="${n>=0?"point-positive":"point-negative"}">${n>0?"+":""}${n}</b></div>`}).join("")}</div>`}\nfunction empty(t){return `<div class="card empty">${esc(t)}</div>`}\nfunction updateVisualViewport(){\n const h=window.visualViewport?.height||window.innerHeight||document.documentElement.clientHeight;\n document.documentElement.style.setProperty("--visual-vh",`${Math.max(280,Math.round(h))}px`);\n}\nfunction ensureFocusedFieldVisible(target){\n if(!target||!$("#modal")?.open)return;\n setTimeout(()=>{\n  try{target.scrollIntoView({block:"center",inline:"nearest",behavior:"smooth"})}catch(_){target.scrollIntoView()}\n },120);\n}\nfunction modal(title,body){\n $("#modalTitle").textContent=title;\n $("#modalBody").innerHTML=body;\n document.body.classList.add("modal-open");\n updateVisualViewport();\n if(!$("#modal").open)$("#modal").showModal();\n requestAnimationFrame(()=>{\n  const card=$("#modal .modal-card");\n  if(card)card.scrollTop=0;\n });\n}\nfunction closeModal(){\n if($("#modal").open)$("#modal").close();\n document.body.classList.remove("modal-open");\n updateVisualViewport();\n}\nfunction pct(n,d){return d?Math.round(n/d*100):0}\nfunction statusClass(code){return code==="completed"?"green":(code==="pending"?"":(code==="late_completed"?"amber":"red"))}\nasync function downloadWithAuth(path,filename){\n if(!networkHint||navigator.onLine===false)throw new Error("当前处于离线模式，连接网络后再导出数据。");\n let r;try{r=await fetch(state.api+path,{headers:{Authorization:`Bearer ${state.token}`}});markNetwork(true)}catch(e){markNetwork(false);throw new Error(friendlyNetworkError(e))}\n if(!r.ok){let d={};try{d=await r.json()}catch{};throw new Error(d.detail||"下载失败")}\n const blob=await r.blob(),url=URL.createObjectURL(blob),a=document.createElement("a");\n a.href=url;a.download=filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1200)\n}\nasync function api(path,opt={}){\n if(state.offline)throw new Error("离线学生体验不连接服务器");\n if(!networkHint||navigator.onLine===false)throw new Error("当前处于离线模式，连接网络后可继续同步数据。");\n const h={"Content-Type":"application/json",...(opt.headers||{})}; if(state.token)h.Authorization=`Bearer ${state.token}`;\n let r;try{r=await fetch(state.api+path,{...opt,headers:h});markNetwork(true)}catch(e){markNetwork(false);throw new Error(friendlyNetworkError(e))}\n let d={};try{d=await r.json()}catch{}\n if(!r.ok){\n  if(r.status===401 && state.token){\n    const msg=d.detail||"登录已过期，请重新登录";\n    clearAuth();\n    $("#shell").classList.add("hidden");$("#loginScreen").classList.remove("hidden");\n    toast(msg);\n    throw new Error(msg);\n  }\n  if(r.status===428 && state.user){\n    state.user.mustChangePassword=true;saveAuth();\n    if(state.page!=="forcePassword") go("forcePassword");\n  }\n  throw new Error(d.detail||`请求失败 ${r.status}`)\n }\n return d\n}\nfunction renderNav(){\n const key=state.offline?"offline":state.user?.role;\n const visibleMenus=(!state.offline&&state.user?.mustChangePassword)?[]:(menus[key]||[]).filter(x=>commercialMenuAllowed(x[0]));\n $("#nav").innerHTML=visibleMenus.map(([id,ico,name])=>`<button class="nav-btn ${state.page===id?"active":""}" data-page="${id}"><span>${ico}</span>${name}</button>`).join("");\n $$(".nav-btn").forEach(b=>b.onclick=()=>go(b.dataset.page));\n const bottomIds={admin:["admin","users","pointsAdmin","teaching","system"],teacher:["teacher","classes","classPoints","teaching","account"],student:["student","syncLearning","rewards","assignments","account"],parent:["parent","childRewards","childAssignments","childProgress","account"],offline:["practice","account"]}[key]||[];\n const bottomMenus=visibleMenus.filter(x=>bottomIds.includes(x[0]));\n $("#bottomNav").style.setProperty("--bottom-count",Math.max(bottomMenus.length,1));\n $("#bottomNav").innerHTML=bottomMenus.map(([id,ico,name])=>`<button class="bottom-nav-btn ${state.page===id?"active":""}" data-page="${id}"><span>${ico}</span><b>${name}</b></button>`).join("");\n $$(".bottom-nav-btn").forEach(b=>b.onclick=()=>go(b.dataset.page));\n const sub=state.user?.subscription;\n $("#userBadge").innerHTML=state.offline?`<b>离线学生</b><span>本机体验</span>`:`<b>${esc(state.user?.name||"")}</b><span>${roleName(state.user?.role)}${sub?.planName?` · ${esc(sub.planName)}`:""}</span>`;\n}\nasync function go(p){\n state.page=p;renderNav();$("#sidebar").classList.remove("open");\n try{if(p!=="forcePassword"){const u=new URL(location.href);u.searchParams.set("page",p);history.replaceState(null,"",u.pathname+u.search+u.hash)}}catch(_){}\n const fn={admin,subscription,users,imports,catalog,adminAudit,system,pointsAdmin,teaching,teacher,classes,classPoints,papers,analytics,audit,leaderboard,student,syncLearning,syncLesson,rewards,assignments,practice,progress,parent,childLearning,childRewards,childProgress,childAssignments,account,forcePassword}[p]||practice;\n try{\n  await fn();\n  const resetTop=()=>{window.scrollTo({top:0,left:0,behavior:"instant"});document.documentElement.scrollTop=0;document.body.scrollTop=0};\n  resetTop();\n  requestAnimationFrame(resetTop);\n  setTimeout(resetTop,80);\n  setTimeout(resetTop,260);\n }catch(e){$("#page").innerHTML=empty(e.message)}\n}\n\n// Login\nasync function login(){\n state.api=$("#serverURL").value.trim().replace(/\\/$/,"");localStorage.setItem("v6Server",state.api);\n if(!networkHint||navigator.onLine===false){syncNetworkUI(true);return}\n const btn=$("#loginBtn"),oldText=btn.textContent;\n btn.dataset.busy="1";btn.disabled=true;btn.textContent="正在连接服务器…";\n try{\n  const remember=$("#rememberLogin").checked;\n  let r;try{r=await fetch(state.api+"/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:$("#username").value.trim(),password:$("#password").value,remember})});markNetwork(true)}catch(e){markNetwork(false);throw new Error(friendlyNetworkError(e))}\n  let d={};try{d=await r.json()}catch{}\n  if(!r.ok)throw new Error(d.detail||"登录失败");\n  state.token=d.token;state.user={id:d.userID,name:d.name,role:d.role,grade:d.grade,mustChangePassword:!!d.mustChangePassword,subscription:d.subscription||null};state.remember=remember;state.offline=false;\n  saveAuth();enter();\n }catch(e){toast(friendlyNetworkError(e))}finally{delete btn.dataset.busy;btn.disabled=false;btn.textContent=oldText;syncNetworkUI(false)}\n}\nfunction enter(){\n $("#loginScreen").classList.add("hidden");$("#shell").classList.remove("hidden");\n const d=state.offline?"practice":(state.user?.mustChangePassword?"forcePassword":({admin:"admin",teacher:"teacher",student:"student",parent:"parent"})[state.user.role]);\n const deep=(!state.user?.mustChangePassword&&roleAllowsPage(requestedDeepPage()))?requestedDeepPage():"";\n go(deep||d);\n}\nfunction logout(){\n if(!state.offline && !confirm("确定退出当前账号吗？"))return;\n clearAuth();state.offline=false;state.page="";\n $("#shell").classList.add("hidden");$("#loginScreen").classList.remove("hidden");\n $("#password").value="";toast("已退出登录");\n}\n\n\nasync function pointsAdmin(){\n const [rules,rewards,reds,dash,autoRules,autoGrants]=await Promise.all([api("/points/rules"),api("/admin/rewards"),api("/rewards/redemptions?limit=100"),api("/admin/points/dashboard?days=30"),api("/admin/auto-reward-rules"),api("/auto-reward-grants?limit=100")]);\n const pending=reds.filter(x=>x.status==="pending"),autoPending=autoGrants.filter(x=>x.status==="pending");\n const tabs=`<div class="split-tabs"><button class="btn secondary active" id="paRulesTab">积分规则</button><button class="btn secondary" id="paRewardsTab">奖品设置</button><button class="btn secondary" id="paAutoTab">自动奖励 ${autoPending.length?`(${autoPending.length})`:""}</button><button class="btn secondary" id="paRedeemTab">兑换处理 ${pending.length?`(${pending.length})`:""}</button><button class="btn secondary" id="paStatsTab">运营统计</button></div>`;\n const ruleCard=x=>`<div class="item"><div class="item-main"><b>${esc(x.name)} <span class="${x.points>0?"point-positive":"point-negative"}">${x.points>0?"+":""}${x.points}</span></b><small>${x.category==="activity"?"课堂活动":"守纪情况"}${x.requireNote?" · 必填备注":""} · ${x.active?"启用":"停用"}</small></div><button class="btn secondary small editRule" data-id="${x.id}">编辑</button></div>`;\n const rewardCard=x=>`<div class="card reward-card"><div class="reward-icon">${esc(x.icon)}</div><h2>${esc(x.name)}</h2><p class="muted">${esc(x.description||"暂无说明")}</p><div class="status-line"><span class="badge">${x.costPoints}积分</span><span class="badge ${x.active?"green":"red"}">${x.active?"上架":"下架"}</span><span class="badge">${x.unlimitedStock?"不限库存":"库存 "+x.stock}</span></div><button class="btn secondary full editReward" data-id="${x.id}">编辑奖品</button></div>`;\n const metricName=m=>({net:"净表现",issued:"发放积分",activity:"课堂活动净分",discipline:"守纪净分"})[m]||m;\n const autoCard=x=>`<div class="item"><div class="item-main"><b>${esc(x.name)} → ${esc(x.rewardIcon)} ${esc(x.rewardName)}</b><small>${x.period==="monthly"?"每月":"每周"} · ${metricName(x.metric)}达到 ${x.threshold} · ${x.active?"启用":"停用"}</small></div><button class="btn secondary small editAuto" data-id="${x.id}">编辑</button></div>`;\n function statsView(d){return `<div class="filters"><select id="opsDays"><option value="7">近7天</option><option value="30" selected>近30天</option><option value="90">近90天</option></select></div><div class="grid4">${stat(d.earned,"发放积分")}${stat(d.redeemedPoints,"兑换积分")}${stat(d.redemptionCount,"有效兑换")}${stat(d.pending,"待发放")}</div><div class="section grid2"><div class="card"><h2>积分结构</h2><div class="list"><div class="item"><b>课堂活动净积分</b><b class="point-positive">${d.activity}</b></div><div class="item"><b>守纪净积分</b><b class="${d.discipline>=0?"point-positive":"point-negative"}">${d.discipline}</b></div><div class="item"><b>在用学生</b><b>${d.studentCount}</b></div><div class="item"><b>已领取 / 已退回</b><b>${d.fulfilled} / ${d.rejected}</b></div></div></div><div class="card"><h2>热门奖品</h2><div class="list">${d.popularRewards.map(x=>`<div class="item"><div><b>${esc(x.rewardName)}</b><small>${x.points}积分</small></div><span class="badge">${x.count}次</span></div>`).join("")||`<span class="muted">暂无兑换数据</span>`}</div></div></div><div class="section card"><h2>低库存提醒</h2><div class="list">${d.lowStock.map(x=>`<div class="item"><div><b>${esc(x.icon)} ${esc(x.name)}</b><small>${x.costPoints}积分</small></div><span class="badge ${x.stock===0?"red":"amber"}">库存 ${x.stock}</span></div>`).join("")||`<span class="muted">暂无低库存奖品</span>`}</div></div>`}\n function draw(which){\n  state.pointsAdminTab=which;sessionStorage.setItem("v771PointsAdminTab",which);\n  $$(".split-tabs .btn").forEach(b=>b.classList.remove("active"));\n  if(which==="rules"){$("#paRulesTab").classList.add("active");$("#pointsAdminBody").innerHTML=`<div class="section"><div class="actions"><button id="newRule" class="btn primary">＋新增规则</button><button id="exportPoints" class="btn secondary">导出积分奖励报表</button></div></div><div class="section list">${rules.map(ruleCard).join("")||empty("暂无积分规则")}</div>`;bindRules()}\n  if(which==="rewards"){$("#paRewardsTab").classList.add("active");$("#pointsAdminBody").innerHTML=`<div class="section"><button id="newReward" class="btn primary">＋新增奖品</button></div><div class="section reward-grid">${rewards.map(rewardCard).join("")||empty("暂无奖品")}</div>`;bindRewards()}\n  if(which==="auto"){$("#paAutoTab").classList.add("active");$("#pointsAdminBody").innerHTML=`<div class="section"><div class="actions"><button id="newAuto" class="btn primary">＋新增自动奖励</button><button id="evalAuto" class="btn secondary">立即检测达标学生</button></div><div class="note" style="margin-top:10px">自动奖励不扣学生积分；达到规则后生成“待发放奖励”，并预占奖品库存。积分撤销导致未达标时，未发放奖励会自动取消并恢复库存。</div></div><div class="section card"><h2>自动奖励规则</h2><div class="list">${autoRules.map(autoCard).join("")||`<span class="muted">暂无自动奖励规则</span>`}</div></div><div class="section card"><h2>最近自动奖励</h2><div class="list">${autoGrants.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.studentName)} · ${esc(x.rewardIcon)} ${esc(x.rewardName)}</b><small>${esc(x.ruleName)} · ${x.metricValue}/${x.threshold} · ${esc(x.periodKey)}</small></div>${x.status==="pending"?`<div class="actions"><button class="btn primary small autoFulfill" data-id="${x.id}">确认发放</button><button class="btn danger small autoCancel" data-id="${x.id}">取消</button></div>`:`<span class="badge ${x.status==="fulfilled"?"green":"red"}">${x.status==="fulfilled"?"已发放":"已取消"}</span>`}</div>`).join("")||`<span class="muted">暂无自动奖励记录</span>`}</div></div>`;bindAuto()}\n  if(which==="redeem"){$("#paRedeemTab").classList.add("active");$("#pointsAdminBody").innerHTML=`<div class="section list">${reds.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.studentName)} · ${esc(x.rewardName)}</b><small>${x.costPoints}积分 · ${esc(x.requestedAt||"")} · ${x.status==="pending"?"待领取":x.status==="fulfilled"?"已领取":"已拒绝/退回"}</small></div>${x.status==="pending"?`<div class="actions"><button class="btn primary small fulfillRed" data-id="${x.id}">确认发放</button><button class="btn danger small rejectRed" data-id="${x.id}">拒绝退分</button></div>`:`<span class="badge ${x.status==="fulfilled"?"green":"red"}">${x.status==="fulfilled"?"已领取":"已退回"}</span>`}</div>`).join("")||empty("暂无兑换记录")}</div>`;bindRedeem()}\n  if(which==="stats"){$("#paStatsTab").classList.add("active");$("#pointsAdminBody").innerHTML=statsView(dash);const changeOpsDays=async()=>{try{const days=+$("#opsDays").value,d=await api(`/admin/points/dashboard?days=${days}`);Object.assign(dash,d);draw("stats")}catch(e){toast(e.message)}};$("#opsDays").value=String(dash.days||30);$("#opsDays").onchange=changeOpsDays}\n }\n function ruleForm(x={}){modal(x.id?"编辑积分规则":"新增积分规则",`<label>规则名称</label><input id="prName" value="${esc(x.name||"")}"><div class="form-grid"><div><label>类别</label><select id="prCat"><option value="activity" ${x.category==="activity"?"selected":""}>课堂活动</option><option value="discipline" ${x.category==="discipline"?"selected":""}>守纪情况</option></select></div><div><label>积分（可负数）</label><input id="prPts" type="number" value="${x.points??1}"></div></div><label style="display:flex;gap:8px;align-items:center"><input id="prNote" type="checkbox" style="width:auto" ${x.requireNote?"checked":""}>要求填写备注</label><label style="display:flex;gap:8px;align-items:center"><input id="prActive" type="checkbox" style="width:auto" ${x.active===false?"":"checked"}>启用</label><button id="saveRule" class="btn primary full">保存</button>`);$("#saveRule").onclick=async()=>{try{const body={name:$("#prName").value,category:$("#prCat").value,points:+$("#prPts").value,active:$("#prActive").checked,require_note:$("#prNote").checked,sort_order:x.sortOrder||0};await api(x.id?`/admin/points/rules/${x.id}`:"/admin/points/rules",{method:x.id?"PUT":"POST",body:JSON.stringify(body)});closeModal();toast("积分规则已保存");pointsAdmin()}catch(e){toast(e.message)}}}\n function rewardForm(x={}){modal(x.id?"编辑奖品":"新增奖品",`<div class="form-grid"><div><label>图标</label><input id="rwIcon" value="${esc(x.icon||"🎁")}"></div><div><label>奖品名称</label><input id="rwName" value="${esc(x.name||"")}"></div></div><label>奖品说明</label><textarea id="rwDesc">${esc(x.description||"")}</textarea><div class="form-grid"><div><label>所需积分</label><input id="rwCost" type="number" min="1" value="${x.costPoints||100}"></div><div><label>库存</label><input id="rwStock" type="number" min="0" value="${x.stock||0}"></div><div><label>每人限兑次数（0不限）</label><input id="rwLimit" type="number" min="0" value="${x.perStudentLimit||0}"></div><div><label>有效开始日期</label><input id="rwStart" type="date" value="${esc(x.startDate||"")}"></div><div><label>有效截止日期</label><input id="rwEnd" type="date" value="${esc(x.endDate||"")}"></div></div><label style="display:flex;gap:8px;align-items:center"><input id="rwUnlimited" type="checkbox" style="width:auto" ${x.unlimitedStock?"checked":""}>不限库存</label><label style="display:flex;gap:8px;align-items:center"><input id="rwActive" type="checkbox" style="width:auto" ${x.active===false?"":"checked"}>上架启用</label><button id="saveReward" class="btn primary full">保存奖品</button>`);$("#saveReward").onclick=async()=>{try{const body={name:$("#rwName").value,description:$("#rwDesc").value,icon:$("#rwIcon").value,cost_points:+$("#rwCost").value,stock:+$("#rwStock").value,unlimited_stock:$("#rwUnlimited").checked,per_student_limit:+$("#rwLimit").value,start_date:$("#rwStart").value,end_date:$("#rwEnd").value,active:$("#rwActive").checked};await api(x.id?`/admin/rewards/${x.id}`:"/admin/rewards",{method:x.id?"PUT":"POST",body:JSON.stringify(body)});closeModal();toast("奖品已保存");pointsAdmin()}catch(e){toast(e.message)}}}\n function autoForm(x={}){if(!rewards.length){toast("请先创建至少一个奖品");return}modal(x.id?"编辑自动奖励":"新增自动奖励",`<label>规则名称</label><input id="arName" value="${esc(x.name||"")}" placeholder="例如：每周课堂之星"><label>对应奖品</label><select id="arReward">${rewards.map(r=>`<option value="${r.id}" ${x.rewardID===r.id?"selected":""}>${esc(r.icon)} ${esc(r.name)}（库存 ${r.unlimitedStock?"不限":r.stock}）</option>`).join("")}</select><div class="form-grid"><div><label>周期</label><select id="arPeriod"><option value="weekly" ${x.period==="monthly"?"":"selected"}>每周</option><option value="monthly" ${x.period==="monthly"?"selected":""}>每月</option></select></div><div><label>达标口径</label><select id="arMetric"><option value="net" ${x.metric==="net"||!x.metric?"selected":""}>净表现</option><option value="issued" ${x.metric==="issued"?"selected":""}>发放积分</option><option value="activity" ${x.metric==="activity"?"selected":""}>课堂活动净分</option><option value="discipline" ${x.metric==="discipline"?"selected":""}>守纪净分</option></select></div></div><label>达标值</label><input id="arThreshold" type="number" min="1" value="${x.threshold||10}"><label style="display:flex;gap:8px;align-items:center"><input id="arActive" type="checkbox" style="width:auto" ${x.active===false?"":"checked"}>启用自动触发</label><button id="saveAuto" class="btn primary full">保存自动奖励</button>`);$("#saveAuto").onclick=async()=>{try{const body={name:$("#arName").value,reward_id:+$("#arReward").value,period:$("#arPeriod").value,metric:$("#arMetric").value,threshold:+$("#arThreshold").value,active:$("#arActive").checked};await api(x.id?`/admin/auto-reward-rules/${x.id}`:"/admin/auto-reward-rules",{method:x.id?"PUT":"POST",body:JSON.stringify(body)});closeModal();toast("自动奖励规则已保存");pointsAdmin()}catch(e){toast(e.message)}}}\n function bindRules(){if($("#newRule"))$("#newRule").onclick=()=>ruleForm();if($("#exportPoints"))$("#exportPoints").onclick=async()=>{try{await downloadWithAuth("/admin/points/export.xlsx","积分奖励报表.xlsx");toast("报表已导出")}catch(e){toast(e.message)}};$$(\'.editRule\').forEach(b=>b.onclick=()=>ruleForm(rules.find(x=>x.id==+b.dataset.id)))}\n function bindRewards(){if($("#newReward"))$("#newReward").onclick=()=>rewardForm();$$(\'.editReward\').forEach(b=>b.onclick=()=>rewardForm(rewards.find(x=>x.id==+b.dataset.id)))}\n function bindAuto(){if($("#newAuto"))$("#newAuto").onclick=()=>autoForm();if($("#evalAuto"))$("#evalAuto").onclick=async()=>{try{const r=await api("/admin/auto-rewards/evaluate",{method:"POST",body:"{}"});toast(`检测完成：新增/变更 ${r.changed} 条`);pointsAdmin()}catch(e){toast(e.message)}};$$(\'.editAuto\').forEach(b=>b.onclick=()=>autoForm(autoRules.find(x=>x.id==+b.dataset.id)));$$(\'.autoFulfill\').forEach(b=>b.onclick=async()=>{try{await api(`/auto-reward-grants/${+b.dataset.id}/handle`,{method:"POST",body:JSON.stringify({action:"fulfill",note:""})});toast("自动奖励已发放");pointsAdmin()}catch(e){toast(e.message)}});$$(\'.autoCancel\').forEach(b=>b.onclick=async()=>{try{await api(`/auto-reward-grants/${+b.dataset.id}/handle`,{method:"POST",body:JSON.stringify({action:"cancel",note:"管理员取消"})});toast("自动奖励已取消");pointsAdmin()}catch(e){toast(e.message)}})}\n function bindRedeem(){$$(\'.fulfillRed\').forEach(b=>b.onclick=async()=>{try{await api(`/rewards/redemptions/${+b.dataset.id}/handle`,{method:"POST",body:JSON.stringify({action:"fulfill",note:""})});toast("已确认发放");pointsAdmin()}catch(e){toast(e.message)}});$$(\'.rejectRed\').forEach(b=>b.onclick=async()=>{const note=prompt("填写拒绝/退回原因（可选）","")||"";try{await api(`/rewards/redemptions/${+b.dataset.id}/handle`,{method:"POST",body:JSON.stringify({action:"reject",note})});toast("已拒绝并退回积分");pointsAdmin()}catch(e){toast(e.message)}})}\n $("#page").innerHTML=head("积分奖励","积分规则、奖品库存、自动奖励、兑换核销与运营统计")+tabs+`<div id="pointsAdminBody"></div>`;$("#paRulesTab").onclick=()=>draw("rules");$("#paRewardsTab").onclick=()=>draw("rewards");$("#paAutoTab").onclick=()=>draw("auto");$("#paRedeemTab").onclick=()=>draw("redeem");$("#paStatsTab").onclick=()=>draw("stats");\n const restoreTab=["rules","rewards","auto","redeem","stats"].includes(state.pointsAdminTab)?state.pointsAdminTab:"rules";draw(restoreTab);\n}\n\nasync function admin(){\n const d=await api("/admin/overview");\n $("#page").innerHTML=head("平台总览","学校正式运营数据与安全状态",`<button class="btn primary" id="adminGlobalSearch">🔎 快捷搜索</button>`)+\n `<div class="grid4">${stat(d.teachers,"教师")}${stat(d.activeStudents,"在读学生")}${stat(d.archivedStudents,"毕业归档")}${stat(d.parents,"家长")}</div>\n <div class="section grid4">${stat(d.classes,"班级")}${stat(d.assignments,"作业")}${stat(d.assignmentRecipients,"作业接收记录")}${stat(d.submissions,"答题提交")}</div>\n <div class="section grid2"><div class="card"><h2>账号与安全</h2><div class="grid2">${stat(d.inactiveAccounts,"停用账号")}${stat(d.lockedAccounts,"登录锁定")}</div></div><div class="card"><h2>数据留痕</h2><p class="muted">班级历史 ${d.classHistoryRecords} 条 · 作业接收快照 ${d.assignmentRecipients} 条。V7.5.0 继续完整记录调班、毕业、作业、课堂积分与奖励兑换。</p></div></div>\n <div class="section card"><h2>快捷操作</h2><div class="actions"><button class="btn primary quickAdmin" data-page="users">账号管理</button><button class="btn secondary quickAdmin" data-page="pointsAdmin">积分奖励</button><button class="btn secondary quickAdmin" data-page="imports">批量导入</button><button class="btn secondary quickAdmin" data-page="system">系统设置</button></div></div>\n <div class="section card"><h2>教材覆盖</h2><p class="muted">${esc((d.textbooks||[]).join("、")||"暂无")}</p></div>`;\n $("#adminGlobalSearch").onclick=globalSearchDialog;\n $$(".quickAdmin").forEach(b=>b.onclick=()=>go(b.dataset.page));\n}\nasync function users(){\n const list=await api("/admin/users");\n const controls=`<div class="filters"><input id="userSearch" placeholder="搜索姓名或账号"><select id="userRole"><option value="">全部身份</option><option value="teacher">教师</option><option value="student">学生</option><option value="parent">家长</option><option value="admin">管理员</option></select><select id="userStatus"><option value="">全部状态</option><option value="active">已启用</option><option value="inactive">已停用</option><option value="archived">毕业归档</option><option value="password">待改密码</option></select></div>`;\n $("#page").innerHTML=head("账号管理","账号安全、毕业归档与恢复入班",`<button class="btn primary" id="newTeacher">＋教师</button><button class="btn secondary" id="newParent">＋家长</button>`)+controls+\n `<div class="card table-wrap desktop-only"><table class="table"><thead><tr><th>姓名</th><th>账号</th><th>身份</th><th>学籍/班级</th><th>账号</th><th>操作</th></tr></thead><tbody id="userTableBody"></tbody></table></div><div id="userCards" class="list mobile-only"></div>`;\n const pwdBadge=x=>x.mustChangePassword?`<span class="badge amber">待修改密码</span>`:`<span class="badge green">密码已设置</span>`;\n const activeBadge=x=>x.active?`<span class="badge green">已启用</span>`:`<span class="badge red">已停用</span>`;\n const lifeBadge=x=>x.role==="student"?`<span class="badge ${x.archived?"amber":""}">${esc(x.lifecycleStatus||"")}</span>`:"";\n const actions=x=>`<button class="btn secondary small resetPwd" data-id="${x.id}" data-name="${esc(x.name)}">重置密码</button>${x.role==="student"?`<button class="btn secondary small userHistory" data-id="${x.id}" data-name="${esc(x.name)}">班级历史</button>`:""}${x.archived?`<button class="btn primary small restoreStudent" data-id="${x.id}" data-name="${esc(x.name)}">恢复入班</button>`:`<button class="btn ${x.active?"danger":"secondary"} small toggleUser" data-id="${x.id}" data-active="${x.active?"1":"0"}" ${x.id===state.user?.id?"disabled":""}>${x.active?"停用":"启用"}</button>`}`;\n function bindUserActions(){\n  $$(".resetPwd").forEach(b=>b.onclick=()=>resetPasswordForm(+b.dataset.id,b.dataset.name));\n  $$(".toggleUser").forEach(b=>b.onclick=async()=>{const active=b.dataset.active==="1",id=+b.dataset.id;if(active&&!confirm("停用后该账号会立即无法继续使用，确定停用吗？"))return;try{await api(`/admin/users/${id}/active`,{method:"POST",body:JSON.stringify({active:!active})});toast(active?"账号已停用":"账号已启用");go("users")}catch(e){toast(e.message)}});\n  $$(".userHistory").forEach(b=>b.onclick=()=>showAdminHistory(+b.dataset.id,b.dataset.name));\n  $$(".restoreStudent").forEach(b=>b.onclick=()=>restoreStudentForm(+b.dataset.id,b.dataset.name));\n }\n function drawUsers(){\n  const q=$("#userSearch").value.trim().toLowerCase(),role=$("#userRole").value,status=$("#userStatus").value;\n  const rows=list.filter(x=>(!q||x.name.toLowerCase().includes(q)||x.username.toLowerCase().includes(q))&&(!role||x.role===role)&&(!status||(status==="active"&&x.active)||(status==="inactive"&&!x.active)||(status==="archived"&&x.archived)||(status==="password"&&x.mustChangePassword)));\n  $("#userTableBody").innerHTML=rows.map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.username)}</td><td>${roleName(x.role)}</td><td>${lifeBadge(x)} ${x.currentClassName?esc(x.currentClassName):""}</td><td>${activeBadge(x)} ${pwdBadge(x)} ${x.lockedUntil?`<span class="badge amber">登录锁定</span>`:""}</td><td>${actions(x)}</td></tr>`).join("")||`<tr><td colspan="6" class="muted">没有匹配账号</td></tr>`;\n  $("#userCards").innerHTML=rows.map(x=>`<div class="card account-card"><div><b>${esc(x.name)}</b><div class="muted" style="font-size:12px;margin-top:3px">${esc(x.username)} · ${roleName(x.role)}${x.currentClassName?` · ${esc(x.currentClassName)}`:""}</div></div><div class="status-line">${lifeBadge(x)}${activeBadge(x)}${pwdBadge(x)}</div><div class="account-actions">${actions(x)}</div></div>`).join("")||`<div class="card empty">没有匹配账号</div>`;bindUserActions();\n }\n $("#newTeacher").onclick=()=>userForm("teacher");$("#newParent").onclick=()=>userForm("parent");$("#userSearch").oninput=drawUsers;$("#userRole").onchange=drawUsers;$("#userStatus").onchange=drawUsers;drawUsers();\n}\nasync function showAdminHistory(id,name){\n try{const rows=await api(`/admin/students/${id}/history`);modal(`${esc(name)} · 班级历史`,rows.length?`<div class="list">${rows.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.className)}</b><small>${(x.joinedAt||"").slice(0,10)} → ${x.current?"当前":(x.leftAt||"").slice(0,10)} · ${esc(x.current?"在读":x.leaveReasonName)}</small></div></div>`).join("")}</div>`:"<div class=\'empty\'>暂无历史</div>")}catch(e){toast(e.message)}\n}\nasync function restoreStudentForm(id,name){\n try{const cs=await api("/admin/classes");if(!cs.length){toast("请先建立班级");return}modal("恢复学生入班",`<p>恢复 <b>${esc(name)}</b> 的账号，并安排到指定班级。</p><label>目标班级</label><select id="restoreClass">${cs.map(c=>`<option value="${c.id}">${esc(c.name)} · ${c.grade}年级 · ${esc(c.teacherName)}</option>`).join("")}</select><div class="note" style="margin-top:10px">恢复后旧登录令牌不会复活，学生需要重新登录。历史成绩与原班级记录保留。</div><button class="btn primary full" id="saveRestore">确认恢复</button>`);$("#saveRestore").onclick=async()=>{try{await api(`/admin/students/${id}/restore`,{method:"POST",body:JSON.stringify({class_id:+$("#restoreClass").value})});closeModal();toast("学生已恢复并重新入班");go("users")}catch(e){toast(e.message)}}}catch(e){toast(e.message)}\n}\nfunction userForm(role){\n modal(role==="teacher"?"创建教师":"创建家长",`<label>姓名</label><input id="nuName"><label>登录账号</label><input id="nuUser"><label>初始密码</label><input id="nuPass" type="password" placeholder="至少8位，包含字母和数字"><button class="btn primary full" id="saveUser">创建</button>`);\n $("#saveUser").onclick=async()=>{try{await api("/admin/users",{method:"POST",body:JSON.stringify({name:$("#nuName").value,username:$("#nuUser").value,password:$("#nuPass").value,role})});closeModal();toast("账号已创建");go("users")}catch(e){toast(e.message)}};\n}\nasync function imports(){\n const jobs=await api("/admin/import-jobs");\n $("#page").innerHTML=head("批量导入","题库、教师、学生均支持 Excel 批量导入",`<button class="btn secondary" id="downloadTemplate">下载模板</button><button class="btn primary" id="uploadXlsx">上传 XLSX</button>`)+\n `<div class="card"><div class="note">V7.4.0 可同时处理“题库导入”“教师导入”“学生导入”工作表。学生导入前请先在教师端建立对应班级。</div><details class="compact-help"><summary>查看模板填写规则</summary><p class="muted">教师/学生初始密码至少8位并包含字母和数字；学生的年级与班级必须匹配；家长账号可留空；重复账号不会覆盖原数据。</p></details><input type="file" id="xlsxFile" accept=".xlsx" class="hidden"></div>\n <div class="section"><h2>最近导入</h2><div class="list">${jobs.length?jobs.map(j=>`<div class="item"><div class="item-main"><b>${esc(j.filename)}</b><small>${esc(j.createdAt)} · ${esc(j.summary)}</small></div><span class="badge ${j.status==="成功"?"green":(j.status==="失败"?"red":"amber")}">${esc(j.status)}</span></div>`).join(""):"<div class=\'card empty\'>暂无导入记录</div>"}</div></div>`;\n $("#downloadTemplate").onclick=async()=>{try{const r=await fetch(state.api+"/admin/import-template",{headers:{Authorization:`Bearer ${state.token}`}});if(!r.ok){let d={};try{d=await r.json()}catch{};throw new Error(d.detail||"模板下载失败")}const blob=await r.blob(),url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="长缨辅学_V7.4.0_批量导入模板.xlsx";document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){toast(e.message)}};\n $("#uploadXlsx").onclick=()=>$("#xlsxFile").click();\n $("#xlsxFile").onchange=async()=>{\n  const f=$("#xlsxFile").files[0];if(!f)return;\n  const fd=new FormData();fd.append("file",f);\n  try{\n   const r=await fetch(state.api+"/admin/import-xlsx",{method:"POST",headers:{Authorization:`Bearer ${state.token}`},body:fd});const d=await r.json();if(!r.ok)throw new Error(d.detail||"导入失败");\n   if((d.errors||[]).length)modal("导入完成",`<div class="note">${esc(d.summary)}</div><div class="list" style="margin-top:10px">${d.errors.map(x=>`<div class="item"><small>${esc(x)}</small></div>`).join("")}</div><button class="btn primary full" id="importDone">知道了</button>`),setTimeout(()=>{$("#importDone").onclick=()=>{closeModal();go("imports")}},0);else{toast(d.summary);go("imports")}\n  }catch(e){toast(e.message)}\n };\n}\nasync function adminAudit(){\n const rows=await api("/admin/audit-logs?limit=200");\n $("#page").innerHTML=head("全校操作审计","管理员查看学校关键操作记录")+`<div class="filters"><input id="auditSearch" placeholder="搜索操作人或内容"><select id="auditType"><option value="">全部操作</option>${[...new Set(rows.map(x=>x.actionName))].map(x=>`<option>${esc(x)}</option>`).join("")}</select></div><div class="card"><div id="adminAuditList" class="list"></div></div>`;\n function draw(){const q=$("#auditSearch").value.trim().toLowerCase(),t=$("#auditType").value;const xs=rows.filter(x=>(!q||`${x.actorName} ${x.summary}`.toLowerCase().includes(q))&&(!t||x.actionName===t));$("#adminAuditList").innerHTML=xs.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.actionName)}</b><small>${esc((x.createdAt||"").slice(0,16).replace("T"," "))} · ${esc(x.actorName)} · ${esc(x.summary)}</small></div></div>`).join("")||"<div class=\'empty\'>没有匹配记录</div>"}$("#auditSearch").oninput=draw;$("#auditType").onchange=draw;draw();\n}\n\nfunction planLimitText(v){return v===null||v===undefined?"不限":String(v)}\nfunction planStatusClass(s){return s==="active"?"green":s==="trial"?"amber":s==="expired"?"red":"amber"}\nasync function subscription(){\n const [sub,plansData]=await Promise.all([api("/subscription/me"),api("/commercial/plans")]);\n state.user.subscription=sub;saveAuth();renderNav();\n const usage=sub.usage||{},limits=sub.limits||{},features=sub.features||{};\n const featureNames={growth_profile:"学生成长档案",growth_report:"成长报告导出",parent_communication:"家校沟通",bulk_import:"批量导入",school_backup:"学校数据备份",school_audit:"全校审计"};\n const usageCard=(label,key)=>`<div class="stat card"><b>${usage[key]??0} / ${planLimitText(limits[key])}</b><small>${label}</small></div>`;\n const planCards=(plansData.plans||[]).map(p=>{\n   const current=p.code===sub.planCode;\n   const price=p.annualPrice===null?"面议":(p.annualPrice===0?"免费":`¥${p.annualPrice}/年`);\n   const monthly=p.monthlyPrice?` · ¥${p.monthlyPrice}/月`:"";\n   const feats=Object.entries(p.features||{}).filter(x=>x[1]).map(([k])=>featureNames[k]||k).join("、");\n   return `<div class="card" style="${current?"border-color:#8f98f0;background:#f8f8ff":""}"><div style="display:flex;justify-content:space-between;gap:10px;align-items:center"><h2 style="margin:0">${esc(p.name)}</h2>${current?`<span class="badge green">当前套餐</span>`:""}</div><p style="font-size:22px;font-weight:900;color:var(--primary);margin:12px 0">${esc(price)}${monthly}</p><p class="muted">教师 ${planLimitText(p.limits?.teachers)} · 班级 ${planLimitText(p.limits?.classes)} · 学生 ${planLimitText(p.limits?.students)}</p><p class="muted" style="line-height:1.7">${esc(feats||"基础功能")}</p></div>`\n }).join("");\n const featureRows=Object.entries(featureNames).map(([k,n])=>`<div class="item"><b>${n}</b><span class="badge ${features[k]?"green":"amber"}">${features[k]?"已包含":"需升级"}</span></div>`).join("");\n const dateText=sub.status==="trial"?(sub.trialEndsAt?`试用至 ${sub.trialEndsAt}`:"试用中"):sub.status==="active"?(sub.periodEndsAt?`有效至 ${sub.periodEndsAt}`:"长期有效"):sub.status==="grace"?(sub.graceEndsAt?`宽限至 ${sub.graceEndsAt}`:"宽限期"):"已到期";\n $("#page").innerHTML=head("套餐授权","商业版 C2 · 套餐、容量、试用和到期控制")+\n `<div class="section card"><div style="display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap"><div><h2 style="margin:0">${esc(sub.planName)}</h2><p class="muted" style="margin:6px 0 0">${esc(sub.schoolName||"")} · ${esc(dateText)}</p></div><span class="badge ${planStatusClass(sub.status)}" style="font-size:13px;padding:8px 12px">${esc(sub.statusName)}</span></div>${sub.readOnly?`<div class="note" style="margin-top:12px;background:#fff0f2;color:var(--red)">当前已进入只读模式：历史数据可查看，但不能新增或修改。续费/升级后恢复写入。</div>`:""}</div>\n <div class="grid3 section">${usageCard("在用教师","teachers")}${usageCard("班级","classes")}${usageCard("在读学生","students")}</div>\n <div class="section grid2"><div class="card"><h2>当前套餐能力</h2><div class="list">${featureRows}</div></div><div class="card"><h2>试运营说明</h2><p class="muted" style="line-height:1.8">当前商业版采用“人工开通套餐”模式，先验证真实付费意愿，再接自动支付。套餐变更需要运营方授权，不允许学校管理员自行升级。</p><div class="note">${sub.contact?`开通/升级联系：${esc(sub.contact)}`:"尚未配置商业联系方式。可在 Render 环境变量设置 COMMERCIAL_CONTACT。"}</div><p class="muted">学校编号：${sub.schoolID} · 学校代码：${esc(sub.schoolCode||"")}</p></div></div>\n <div class="section"><h2>套餐方案</h2><div class="grid2">${planCards}</div></div>`;\n}\n\nasync function system(){\n const [h,requests,ready]=await Promise.all([api("/admin/system-health"),api("/admin/deletion-requests?limit=100"),api("/admin/release-readiness")]);\n const warn=h.warnings?.length?h.warnings.map(x=>`<div class="item"><span class="badge amber">待完善</span><div class="item-main"><b>${esc(x)}</b></div></div>`).join(""):`<div class="item"><span class="badge green">通过</span><div class="item-main"><b>当前自动检查未发现上线阻断项</b></div></div>`;\n const releaseItems=Object.entries(ready.checks||{}).map(([k,x])=>`<div class="item"><div class="item-main"><b>${esc(({databaseBackend:"生产数据库",jwtSecret:"JWT 密钥",schemaMigration:"数据库迁移",demoSeed:"演示数据",securityHeaders:"安全响应头",loginRateLimit:"登录频率限制",legacyPwaCache:"旧 PWA 缓存"})[k]||k)}</b><small>${esc(x.value||"")}</small></div><span class="badge ${x.ok?"green":"red"}">${x.ok?"通过":"阻断"}</span></div>`).join("");\n const releaseNotes=[...(ready.blockers||[]).map(x=>`<div class="note" style="background:#fff0f2;color:var(--red);margin-top:8px">阻断：${esc(x)}</div>`),...(ready.advisories||[]).map(x=>`<div class="note" style="margin-top:8px">建议：${esc(x)}</div>`)].join("");\n const reqHtml=requests.length?requests.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.userName)} · ${roleName(x.role)}</b><small>${esc(x.requestedAt||"")} · ${esc(x.reason||"未填写原因")} · ${x.status==="pending"?"待处理":x.status}</small></div>${x.status==="pending"?`<div class="actions"><button class="btn danger small resolveDeletion" data-id="${x.id}" data-action="approve">批准注销</button><button class="btn secondary small resolveDeletion" data-id="${x.id}" data-action="reject">驳回</button></div>`:`<span class="badge ${x.status==="approved"?"green":""}">${esc(x.status)}</span>`}</div>`).join(""):`<div class="empty">暂无账号注销申请</div>`;\n $("#page").innerHTML=head("系统设置","V9.2.0 正式上线收口、安全、备份与账号治理")+\n `<div class="section card"><div style="display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap"><div><h2 style="margin:0">上线就绪状态</h2><p class="muted" style="margin:5px 0 0">自动检查生产数据库、JWT、迁移、演示数据和基础安全项。</p></div><span class="badge ${ready.ready?"green":"red"}" style="font-size:13px;padding:8px 12px">${ready.ready?"V9.0 商业版 C2就绪":"仍有上线阻断项"}</span></div><div class="list" style="margin-top:14px">${releaseItems}</div>${releaseNotes}</div>\n <div class="grid4 section">${stat(h.databaseBackend,"数据库")}${stat(h.jwtConfigured?"已固定":"未固定","JWT密钥")}${stat(h.migrations?.[0]?.version||"-","迁移版本")}${stat(h.pendingDeletionRequests||0,"待处理注销")}</div>\n <div class="section grid2"><div class="card"><h2>上线检查</h2><div class="list">${warn}</div></div><div class="card"><h2>安全基线</h2><div class="list"><div class="item"><b>安全响应头</b><span class="badge green">已启用</span></div><div class="item"><b>登录频率限制</b><span class="badge green">${h.loginRateLimit.maxAttempts}/${Math.round(h.loginRateLimit.windowSeconds/60)}分钟</span></div><div class="item"><b>CORS</b><span class="badge ${h.corsOrigins==="*"?"amber":"green"}">${esc(h.corsOrigins)}</span></div></div></div></div>\n <div class="section card"><div style="display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap"><div><h2 style="margin:0">学校数据备份</h2><p class="muted">导出不含密码哈希的学校业务快照，用于留档和恢复准备。</p></div>${featureAvailable("school_backup")?`<button class="btn primary" id="downloadBackup">下载备份 JSON</button>`:`<span class="badge amber">当前套餐不含学校备份</span>`}</div><div class="note" style="margin-top:12px">本版先开放安全的只读备份导出；生产数据库自动恢复写入仍保持关闭，避免误覆盖。正式上线前建议再配置托管数据库的每日自动快照。</div></div>\n <div class="section card"><h2>数据库迁移记录</h2><div class="list">${(h.migrations||[]).map(x=>`<div class="item"><div class="item-main"><b>${esc(x.version)}</b><small>${esc(x.description)} · ${esc(x.appliedAt||"")}</small></div><span class="badge green">已应用</span></div>`).join("")||`<span class="muted">暂无迁移记录</span>`}</div></div>\n <div class="section card"><h2>账号注销申请</h2><div class="list">${reqHtml}</div></div>\n <div class="section card"><h2>当前服务器</h2><input id="sysURL" value="${esc(state.api)}"><button class="btn secondary full" id="saveSys">保存</button><p class="muted">服务器时间：${esc(h.serverTime||"")} · App ${esc(h.appVersion)} · Schema ${esc(h.schemaVersion)}</p></div>`;\n $("#saveSys").onclick=()=>{state.api=$("#sysURL").value.trim().replace(/\\/$/,"");localStorage.setItem("v6Server",state.api);toast("已保存")};\n if($("#downloadBackup"))$("#downloadBackup").onclick=async()=>{try{await downloadWithAuth("/admin/backup.json","school-backup-v910.json");toast("学校数据备份已导出")}catch(e){toast(e.message)}};\n $$(".resolveDeletion").forEach(b=>b.onclick=async()=>{const action=b.dataset.action,id=+b.dataset.id;if(!confirm(action==="approve"?"批准后该账号将立即停用并失效现有登录。确定继续？":"确定驳回这条注销申请？"))return;try{await api(`/admin/deletion-requests/${id}/resolve`,{method:"POST",body:JSON.stringify({action,note:"管理员在系统设置中处理"})});toast("注销申请已处理");system()}catch(e){toast(e.message)}});\n}\n\n\n// V7.4 customized teaching: 2026 autumn Grade 5 Chinese + Math\nfunction splitLines(v){return String(v||"").split(/\\n+/).map(x=>x.trim()).filter(Boolean)}\nfunction teachStatus(s){return ({not_started:"未开始",active:"进行中",passed:"已达标",completed:"已完成"})[s]||s}\nfunction levelBadge(l){return l?`<span class="level-badge level-${l}">${l}层</span>`:""}\nasync function teaching(){\n const p=await api("/teaching/program"),lessons=await api("/teaching/lessons");state.teachingSubject=state.teachingSubject||"语文";\n const subject=state.teachingSubject,rows=lessons.filter(x=>x.subject===subject),qc=p.questionCounts||{};\n const lessonQ=lessons.reduce((n,l)=>n,0),stageCount=(stage)=>Object.values(qc[stage]||{}).reduce((a,o)=>a+Object.values(o||{}).reduce((x,y)=>x+y,0),0);\n $("#page").innerHTML=head("五年级定制教学",`${p.academicYear}年${p.term} · ${p.grade}年级${p.semester} · 每课时120分钟`,\n `<button class="btn secondary" id="teachSettings">教学设置</button><button class="btn secondary" id="midtermBank">期中题库</button><button class="btn secondary" id="finalBank">期末题库</button>`)+\n `<div class="card teach-hero"><h2 style="margin-top:0">${esc(p.title)}</h2><p>语文 ${p.lessonCounts?.语文||8} 课时：阅读理解 + 同步作文 + 精简PPT + 错题巩固 + 作文复盘；数学 ${p.lessonCounts?.数学||16} 课时：完整教案 + 例题 + C/B/A分层练习 + 精简PPT。</p><div class="status-line"><span class="badge">语文已发布 ${p.publishedCounts?.语文||0}/8</span><span class="badge">数学已发布 ${p.publishedCounts?.数学||0}/16</span><span class="badge">分层通过线 ${p.passThreshold}%</span><span class="badge">期中题 ${stageCount("midterm")}</span><span class="badge">期末题 ${stageCount("final")}</span></div></div>\n <div class="section subject-tabs"><button class="btn ${subject==="语文"?"active":"secondary"}" id="teachChinese">语文 8课时</button><button class="btn ${subject==="数学"?"active":"secondary"}" id="teachMath">数学 16课时</button></div>\n <div class="section list">${rows.map(l=>`<div class="card"><div style="display:flex;justify-content:space-between;gap:10px"><div><b>${esc(l.title)}</b><div class="muted" style="margin-top:4px">第${l.lessonNo}课时 · ${esc(l.unit)}</div></div><span class="badge ${l.published?"green":"amber"}">${l.published?"已发布":"未发布"}</span></div><p class="muted">${esc(l.coreTarget||"尚未配置核心目标")}</p><div class="lesson-tools"><button class="btn primary small teachEdit" data-id="${l.id}">编辑课时</button><button class="btn secondary small teachSlides" data-id="${l.id}">课堂PPT</button><button class="btn secondary small teachQ" data-id="${l.id}" data-subject="${l.subject}">分层题库</button><button class="btn secondary small teachProgress" data-id="${l.id}">学习进度</button>${l.subject==="语文"?`<button class="btn secondary small teachEssays" data-id="${l.id}">作文复盘</button>`:""}</div></div>`).join("")}</div>`;\n $("#teachChinese").onclick=()=>{state.teachingSubject="语文";teaching()};$("#teachMath").onclick=()=>{state.teachingSubject="数学";teaching()};\n $("#teachSettings").onclick=()=>teachingSettings(p);$("#midtermBank").onclick=()=>stageQuestionBank("midterm");$("#finalBank").onclick=()=>stageQuestionBank("final");\n $$(".teachEdit").forEach(b=>b.onclick=()=>editTeachingLesson(+b.dataset.id));$$(".teachSlides").forEach(b=>b.onclick=()=>presentTeachingSlides(+b.dataset.id));$$(".teachQ").forEach(b=>b.onclick=()=>lessonQuestionBank(+b.dataset.id,b.dataset.subject));$$(".teachProgress").forEach(b=>b.onclick=()=>teachingProgress(+b.dataset.id));$$(".teachEssays").forEach(b=>b.onclick=()=>teachingEssays(+b.dataset.id));\n}\nfunction teachingSettings(p){\n modal("2026秋教学设置",`<label>方案名称</label><input id="tpTitle" value="${esc(p.title)}"><div class="form-grid"><div><label>语文教材版本</label><input id="tpChinese" value="${esc(p.chineseTextbook)}"></div><div><label>数学教材版本</label><input id="tpMath" value="${esc(p.mathTextbook)}"></div></div><label>C/B/A层通过线（%）</label><input id="tpThreshold" type="number" min="1" max="100" value="${p.passThreshold}"><div class="note" style="margin-top:10px">模块已固定创建语文8课时、数学16课时；具体单元语文要素与数学知识点请按学校2026秋实际教材版本校准后发布。</div><button class="btn primary full" id="saveTeachingSettings">保存</button>`);\n $("#saveTeachingSettings").onclick=async()=>{try{await api("/teaching/program",{method:"PUT",body:JSON.stringify({title:$("#tpTitle").value,chinese_textbook:$("#tpChinese").value,math_textbook:$("#tpMath").value,pass_threshold:+$("#tpThreshold").value})});closeModal();toast("教学设置已保存");teaching()}catch(e){toast(e.message)}};\n}\nasync function editTeachingLesson(id){\n try{const l=await api(`/teaching/lessons/${id}`);modal(`${l.subject}第${l.lessonNo}课时`,`<div class="form-grid"><div><label>课时名称</label><input id="tlTitle" value="${esc(l.title)}"></div><div><label>教材单元</label><input id="tlUnit" value="${esc(l.unit)}"></div></div><label>${l.subject==="语文"?"核心知识 / 单元语文要素":"核心知识点 / 本课目标"}</label><textarea id="tlTarget">${esc(l.coreTarget)}</textarea><label>120分钟完整教案</label><textarea id="tlPlan">${esc(l.teacherPlan)}</textarea>${l.subject==="语文"?`<label>阅读理解教案</label><textarea id="tlReading">${esc(l.readingPlan)}</textarea><label>同步作文教案</label><textarea id="tlWriting">${esc(l.writingPlan)}</textarea><label>作文修改复盘训练</label><textarea id="tlEssayReview">${esc(l.essayReview)}</textarea>`:`<label>课堂例题（每行1题/1组）</label><textarea id="tlExamples">${esc((l.examples||[]).join("\\n"))}</textarea>`}<label>错题闭环 / 巩固训练</label><textarea id="tlClosure">${esc(l.closureTraining)}</textarea><label>精简版课堂PPT（每行1页）</label><textarea id="tlPpt">${esc((l.ppt||[]).join("\\n"))}</textarea><label style="display:flex;gap:8px;align-items:center"><input id="tlPublished" type="checkbox" style="width:auto" ${l.published?"checked":""}>发布给学生</label><button class="btn primary full" id="saveTeachingLesson">保存课时</button>`);\n $("#saveTeachingLesson").onclick=async()=>{try{await api(`/teaching/lessons/${id}`,{method:"PUT",body:JSON.stringify({title:$("#tlTitle").value,unit:$("#tlUnit").value,core_target:$("#tlTarget").value,teacher_plan:$("#tlPlan").value,reading_plan:$("#tlReading")?.value||null,writing_plan:$("#tlWriting")?.value||null,essay_review:$("#tlEssayReview")?.value||null,examples:$("#tlExamples")?splitLines($("#tlExamples").value):null,closure_training:$("#tlClosure").value,ppt:splitLines($("#tlPpt").value),published:$("#tlPublished").checked})});closeModal();toast("课时已保存");teaching()}catch(e){toast(e.message)}}\n }catch(e){toast(e.message)}\n}\nasync function presentTeachingSlides(id){\n try{const l=await api(`/teaching/lessons/${id}`),slides=l.ppt?.length?l.ppt:["本课PPT尚未配置"];let i=0;modal(`${esc(l.title)} · 精简PPT`,`<div id="slideView"></div><div class="actions" style="margin-top:12px"><button class="btn secondary" id="slidePrev">上一页</button><button class="btn secondary" id="slideNext">下一页</button></div>`);const draw=()=>{$("#slideView").innerHTML=`<div class="slide-view"><div><span class="badge">${i+1}/${slides.length}</span><h2>${esc(slides[i])}</h2></div></div>`};draw();$("#slidePrev").onclick=()=>{i=Math.max(0,i-1);draw()};$("#slideNext").onclick=()=>{i=Math.min(slides.length-1,i+1);draw()}}catch(e){toast(e.message)}\n}\nasync function lessonQuestionBank(id,subject){return teachingQuestionBank({lesson_id:id,stage:"lesson",subject})}\nasync function stageQuestionBank(stage){\n modal(stage==="midterm"?"期中分层题库":"期末分层题库",`<p>选择科目后管理 A/B/C 三层题目。学生正式测评从 C 层开始，不达标自动降到 B，再降到 A。</p><div class="grid2"><button class="btn primary stageSubject" data-subject="语文">语文</button><button class="btn primary stageSubject" data-subject="数学">数学</button></div>`);$$(".stageSubject").forEach(b=>b.onclick=()=>teachingQuestionBank({lesson_id:null,stage,subject:b.dataset.subject}));\n}\nasync function teachingQuestionBank(cfg){\n try{const qs=await api(`/teaching/questions?stage=${cfg.stage}&subject=${encodeURIComponent(cfg.subject)}${cfg.lesson_id?`&lesson_id=${cfg.lesson_id}`:""}`),counts={A:0,B:0,C:0};qs.forEach(q=>counts[q.level]++);modal(`${cfg.subject} · ${cfg.stage==="lesson"?"课时练习":cfg.stage==="midterm"?"期中测试":"期末测试"}`,`<div class="status-line">${["C","B","A"].map(l=>`<span class="level-badge level-${l}">${l}层 ${counts[l]}题</span>`).join("")}</div><button class="btn primary full" id="newTeachingQuestion">＋新增分层题</button><div class="list" style="margin-top:12px">${qs.map(q=>`<div class="item"><div class="item-main"><b>${levelBadge(q.level)} ${esc(q.stem)}</b><small>${esc(q.knowledge)} · 正确：${esc(q.options[q.correctIndex])}</small></div><button class="btn danger small delTeachingQ" data-id="${q.id}">删除</button></div>`).join("")||"<div class=\'empty\'>尚未配置题目</div>"}</div>`);$("#newTeachingQuestion").onclick=()=>newTeachingQuestion(cfg);$$(".delTeachingQ").forEach(b=>b.onclick=async()=>{if(!confirm("确定删除这道分层题吗？"))return;try{await api(`/teaching/questions/${b.dataset.id}`,{method:"DELETE"});teachingQuestionBank(cfg)}catch(e){toast(e.message)}})}catch(e){toast(e.message)}\n}\nfunction newTeachingQuestion(cfg){\n modal("新增A/B/C分层题",`<div class="form-grid"><div><label>层级</label><select id="tqLevel"><option>C</option><option>B</option><option>A</option></select></div><div><label>知识点</label><input id="tqKnowledge"></div></div><label>题目</label><textarea id="tqStem"></textarea>${[0,1,2,3].map((x)=>`<label>选项 ${String.fromCharCode(65+x)}</label><input id="tqO${x}">`).join("")}<label>正确答案</label><select id="tqCorrect"><option value="0">A</option><option value="1">B</option><option value="2">C</option><option value="3">D</option></select><label>解析</label><textarea id="tqExplain"></textarea><button class="btn primary full" id="saveTeachingQ">保存题目</button>`);$("#saveTeachingQ").onclick=async()=>{try{await api("/teaching/questions",{method:"POST",body:JSON.stringify({lesson_id:cfg.lesson_id||null,stage:cfg.stage,subject:cfg.subject,level:$("#tqLevel").value,knowledge:$("#tqKnowledge").value,stem:$("#tqStem").value,options:[0,1,2,3].map(i=>$("#tqO"+i).value),correct_index:+$("#tqCorrect").value,explanation:$("#tqExplain").value})});toast("题目已保存");teachingQuestionBank(cfg)}catch(e){toast(e.message)}};\n}\nasync function teachingProgress(id){try{const rows=await api(`/teaching/lessons/${id}/progress`);modal("课时学习进度",`<div class="list">${rows.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.studentName)}</b><small>${teachStatus(x.status)}${x.level?` · ${x.level}层`:""}${x.score!==null?` · ${x.score}分`:""}</small></div><span class="badge ${x.active?"green":"red"}">${x.active?"在用":"停用"}</span></div>`).join("")||"<div class=\'empty\'>暂无五年级学生</div>"}</div>`)}catch(e){toast(e.message)}}\nasync function teachingEssays(id){try{const rows=await api(`/teaching/lessons/${id}/essays`);modal("作文提交与复盘",`<div class="list">${rows.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.studentName)}</b><small>${esc(x.status)} · ${(x.updatedAt||"").slice(0,16).replace("T"," ")}</small></div><button class="btn secondary small essayReviewBtn" data-id="${x.id}">批改</button></div>`).join("")||"<div class=\'empty\'>暂无作文提交</div>"}</div>`);$$(".essayReviewBtn").forEach(b=>b.onclick=()=>reviewEssay(+b.dataset.id,rows.find(x=>x.id===+b.dataset.id),id))}catch(e){toast(e.message)}}\nfunction reviewEssay(eid,e,lid){modal(`${esc(e.studentName)} · 作文复盘`, `<label>初稿</label><div class="card">${esc(e.draft||"暂无")}</div><label>学生修改稿</label><div class="card">${esc(e.revisedDraft||"暂无")}</div><label>教师反馈</label><textarea id="essayFeedback">${esc(e.teacherFeedback||"")}</textarea><button class="btn primary full" id="saveEssayFeedback">保存反馈</button>`);$("#saveEssayFeedback").onclick=async()=>{try{await api(`/teaching/essays/${eid}/feedback`,{method:"PUT",body:JSON.stringify({teacher_feedback:$("#essayFeedback").value,status:"reviewed"})});toast("作文反馈已保存");teachingEssays(lid)}catch(err){toast(err.message)}}}\n\nasync function syncLearning(){\n const d=await api("/student/teaching/overview"),p=d.program;const groups=s=>d.lessons.filter(x=>x.subject===s);\n $("#page").innerHTML=head("同步课堂",`${p.academicYear}年${p.term} · 五年级${p.semester} · C层优先，未达标自动进入B层，再进入A层`)+\n `<div class="card teach-hero"><h2 style="margin-top:0">${esc(p.title)}</h2><p>${d.gradeMatch?"当前账号年级与方案匹配。":"当前账号为"+esc(d.studentGrade||"未设置")+"年级；此处为五年级教学方案预览/学习入口。"}</p></div>`+\n ["语文","数学"].map(s=>`<div class="section"><h2>${s}同步课时</h2><div class="list">${groups(s).map(l=>`<div class="item"><div class="item-main"><b>第${l.lessonNo}课时 · ${esc(l.title)}</b><small>${esc(l.unit)} · ${esc(l.coreTarget)}</small><div class="status-line" style="margin-top:6px">${levelBadge(l.bestLevel)}<span class="badge">${teachStatus(l.studyStatus)}</span>${l.score!==null?`<span class="badge green">${l.score}分</span>`:""}</div></div><button class="btn primary small enterSyncLesson" data-id="${l.id}" ${d.gradeMatch?"":"disabled"}>${d.gradeMatch?"进入课堂":"仅限五年级"}</button></div>`).join("")||"<div class=\'card empty\'>教师尚未发布课时</div>"}</div></div>`).join("")+\n `<div class="section"><h2>阶段性测评</h2><div class="stage-grid">${d.tests.map(t=>`<div class="card"><b>${t.subject} · ${t.stageName}</b><p class="muted">C ${t.counts.C}题 / B ${t.counts.B}题 / A ${t.counts.A}题</p><div class="status-line">${levelBadge(t.level)}<span class="badge">${teachStatus(t.status)}</span></div><button class="btn primary full startStageTest" data-stage="${t.stage}" data-subject="${t.subject}" ${d.gradeMatch&&t.available&&t.status==="not_started"?"":"disabled"}>${!d.gradeMatch?"仅限五年级":t.available?(t.status==="not_started"?"开始测评":"已完成"):"教师尚未配置"}</button></div>`).join("")}</div></div>`;\n $$(".enterSyncLesson").forEach(b=>b.onclick=()=>{state.teachingLessonID=+b.dataset.id;go("syncLesson")});$$(".startStageTest").forEach(b=>b.onclick=()=>startTeachingAdaptive({stage:b.dataset.stage,subject:b.dataset.subject}));\n}\nasync function syncLesson(){\n const id=state.teachingLessonID;if(!id){go("syncLearning");return}const l=await api(`/student/teaching/lessons/${id}`);\n $("#page").innerHTML=head(l.title,`${l.subject} · 第${l.lessonNo}课时 · ${esc(l.unit)} · ${l.durationMin}分钟`, `<button class="btn secondary" id="backSync">返回课程</button>`)+\n `<div class="card"><h2>本课目标</h2><p class="muted">${esc(l.coreTarget)}</p><button class="btn secondary" id="studentSlides">课堂PPT</button><button class="btn primary" id="startLessonAdaptive">开始C层优先挑战</button></div>`+\n `${l.subject==="数学"&&l.examples?.length?`<div class="section card"><h2>课堂例题</h2><div class="list">${l.examples.map(x=>`<div class="item"><div class="item-main">${esc(x)}</div></div>`).join("")}</div></div>`:""}`+\n `${l.closureTraining?`<div class="section card"><h2>错题闭环训练</h2><p class="teaching-timeline">${esc(l.closureTraining)}</p></div>`:""}`+\n `${l.subject==="语文"?`<div class="section card essay-box"><h2>同步作文与修改复盘</h2><div class="note">${esc(l.essayReview||"完成当堂作文后，根据老师反馈进行二次修改。")}</div><label>当堂作文初稿</label><textarea id="essayDraft">${esc(l.essay?.draft||"")}</textarea><label>修改稿</label><textarea id="essayRevised">${esc(l.essay?.revisedDraft||"")}</textarea>${l.essay?.teacherFeedback?`<div class="card" style="margin-top:10px"><b>教师反馈</b><p>${esc(l.essay.teacherFeedback)}</p></div>`:""}<button class="btn primary full" id="saveEssay">保存作文/修改稿</button></div>`:""}`;\n $("#backSync").onclick=()=>go("syncLearning");$("#studentSlides").onclick=()=>studentSlideDeck(l);$("#startLessonAdaptive").onclick=()=>startTeachingAdaptive({stage:"lesson",lesson_id:id});\n if($("#saveEssay"))$("#saveEssay").onclick=async()=>{try{await api(`/student/teaching/lessons/${id}/essay`,{method:"POST",body:JSON.stringify({draft:$("#essayDraft").value,revised_draft:$("#essayRevised").value})});toast("作文已保存");syncLesson()}catch(e){toast(e.message)}};\n}\nfunction studentSlideDeck(l){const slides=l.ppt?.length?l.ppt:["本课PPT尚未配置"];let i=0;modal(`${esc(l.title)} · 学生PPT`,`<div id="studentSlide"></div><div class="actions" style="margin-top:12px"><button class="btn secondary" id="spPrev">上一页</button><button class="btn secondary" id="spNext">下一页</button></div>`);const draw=()=>$("#studentSlide").innerHTML=`<div class="slide-view"><div><span class="badge">${i+1}/${slides.length}</span><h2>${esc(slides[i])}</h2></div></div>`;draw();$("#spPrev").onclick=()=>{i=Math.max(0,i-1);draw()};$("#spNext").onclick=()=>{i=Math.min(slides.length-1,i+1);draw()}}\nasync function startTeachingAdaptive(payload){try{const d=await api("/student/teaching/adaptive/start",{method:"POST",body:JSON.stringify(payload)});renderAdaptive(d)}catch(e){toast(e.message)}}\nfunction renderAdaptive(d){\n modal(`${d.subject} · ${d.stage==="lesson"?"分层课堂":d.stage==="midterm"?"期中测评":"期末测评"} · ${d.level}层`,`<div class="note">优先挑战C层；本方案通过线 ${d.passThreshold}%。未达标时系统自动降层，不需要学生自己选择难度。</div><div id="adaptiveQuestions">${(d.questions||[]).map((q,n)=>`<div class="adaptive-q"><b>${n+1}. ${esc(q.stem)}</b>${q.options.map((o,i)=>`<label class="adaptive-option"><input type="radio" name="teachq_${q.id}" value="${i}"><span>${String.fromCharCode(65+i)}. ${esc(o)}</span></label>`).join("")}</div>`).join("")}</div><button class="btn primary full" id="submitAdaptive">提交${d.level}层</button>`);\n $("#submitAdaptive").onclick=async()=>{const answers=[];for(const q of d.questions||[]){const x=document.querySelector(`input[name="teachq_${q.id}"]:checked`);if(!x){toast("请完成当前层全部题目");return}answers.push({question_id:q.id,selected_index:+x.value})}try{const r=await api("/student/teaching/adaptive/submit",{method:"POST",body:JSON.stringify({session_id:d.sessionID,answers})});showAdaptiveResult(r)}catch(e){toast(e.message)}};\n}\nfunction showAdaptiveResult(r){\n const review=r.review||{},next=r.nextLevel;modal("分层结果",`<div class="grid3">${stat(r.score,"本层得分")}${stat(`${r.correct}/${r.total}`,"答对")}${stat(r.submittedLevel,"完成层级")}</div><div class="section note">${r.passed?`已达到${r.submittedLevel}层要求。`:next?`${r.submittedLevel}层暂未达标，系统将自动进入${next}层。`:"已完成A层基础巩固。"}</div>${review.wrongQuestions?.length?`<div class="section card"><h2>本次错题</h2>${review.wrongQuestions.map(x=>`<p><b>${esc(x.knowledge)}</b>：${esc(x.stem)}<br><span class="muted">${esc(x.explanation||"请结合课堂方法重新订正。")}</span></p>`).join("")}</div>`:""}${review.closureTraining?`<div class="section card"><h2>专属巩固训练</h2><p>${esc(review.closureTraining)}</p></div>`:""}${next?`<button class="btn primary full" id="continueAdaptive">进入${next}层</button>`:`<button class="btn primary full" id="finishAdaptive">完成</button>`}`);\n if(next)$("#continueAdaptive").onclick=()=>renderAdaptive({sessionID:r.sessionID,stage:r.stage,subject:r.subject,lessonID:null,level:next,status:"active",passThreshold:r.passThreshold,questions:r.questions});else $("#finishAdaptive").onclick=()=>{closeModal();if(state.page==="syncLesson")syncLesson();else syncLearning()};\n}\n\nasync function childLearning(){\n const c=await api("/parent/children");if(!c.length){$("#page").innerHTML=head("孩子课程","暂无绑定学生")+empty("请联系学校绑定孩子");return}const sid=(state.childID&&c.some(x=>x.id===state.childID))?state.childID:c[0].id;state.childID=sid;const d=await api(`/parent/children/${sid}/teaching`),chooser=c.length>1?`<select id="teachingChild">${c.map(x=>`<option value="${x.id}" ${x.id===sid?"selected":""}>${esc(x.name)}</option>`).join("")}</select>`:"";\n $("#page").innerHTML=head(`${esc(d.student.name)}的同步课程`,`${d.program.academicYear}年${d.program.term} · 五年级${d.program.semester}`,chooser)+`<div class="grid2">${stat(d.lessons.filter(x=>x.status!=="not_started").length,"已开始课时")}${stat(d.lessons.filter(x=>x.status==="passed"||x.status==="completed").length,"已完成课时")}</div><div class="section"><h2>课时学习</h2><div class="list">${d.lessons.map(x=>`<div class="item"><div class="item-main"><b>${x.subject}第${x.lessonNo}课时 · ${esc(x.title)}</b><small>${teachStatus(x.status)}${x.level?` · ${x.level}层`:""}${x.score!==null?` · ${x.score}分`:""}${x.essayStatus?` · 作文${esc(x.essayStatus)}`:""}</small></div></div>`).join("")||"<div class=\'card empty\'>暂无已发布课时</div>"}</div></div><div class="section"><h2>阶段测评</h2><div class="stage-grid">${d.tests.map(t=>`<div class="card"><b>${t.subject} · ${t.stageName}</b><p class="muted">${teachStatus(t.status)}${t.level?` · ${t.level}层`:""}${t.score!==null?` · ${t.score}分`:""}</p></div>`).join("")}</div></div>`;if($("#teachingChild"))$("#teachingChild").onchange=()=>{state.childID=+$("#teachingChild").value;childLearning()};\n}\n\n// Shared catalog\nasync function catalog(){\n const qs=await api("/questions");\n $("#page").innerHTML=head("教材题库",`共 ${qs.length} 道云端题目`,state.user?.role==="teacher"||state.user?.role==="admin"?`<button class="btn primary" id="addQ">＋新增题目</button>`:"")+\n `<div class="filters"><select id="fGrade"><option value="">全部年级</option>${[1,2,3,4,5,6].map(x=>`<option value="${x}">${x}年级</option>`).join("")}</select>\n <select id="fSubject"><option value="">全部科目</option><option>数学</option><option>语文</option><option>英语</option></select>\n <select id="fBook"><option value="">全部教材</option>${[...new Set(qs.map(q=>q.textbook))].map(x=>`<option>${esc(x)}</option>`).join("")}</select>\n <input id="fSearch" placeholder="搜索知识点或题目"></div><div id="catalogList"></div>`;\n const draw=()=>{\n  const g=$("#fGrade").value,s=$("#fSubject").value,b=$("#fBook").value,k=$("#fSearch").value.trim();\n  const list=qs.filter(q=>(!g||q.grade==g)&&(!s||q.subject===s)&&(!b||q.textbook===b)&&(!k||q.text.includes(k)||q.knowledge.includes(k)||q.unit.includes(k)));\n  $("#catalogList").innerHTML=`<div class="list">${list.map(q=>`<div class="item"><div class="item-main"><b>${esc(q.text)}</b><small>${q.grade}年级 · ${esc(q.subject)} · ${esc(q.textbook)} · ${esc(q.semester)} · ${esc(q.unit)} · ${esc(q.knowledge)}</small></div><span class="badge">${esc(q.options[q.correctIndex])}</span></div>`).join("")||"<div class=\'card empty\'>暂无题目</div>"}</div>`;\n };\n ["#fGrade","#fSubject","#fBook","#fSearch"].forEach(x=>$(x).oninput=draw);draw();\n if($("#addQ"))$("#addQ").onclick=()=>questionForm();\n}\nfunction questionForm(){\n modal("新增教材题目",`<div class="form-grid">\n <div><label>年级</label><select id="qg">${[1,2,3,4,5,6].map(x=>`<option>${x}</option>`).join("")}</select></div>\n <div><label>科目</label><select id="qs"><option>数学</option><option>语文</option><option>英语</option></select></div>\n <div><label>教材版本</label><input id="qb" value="人教版"></div><div><label>学期</label><select id="qsem"><option>上册</option><option>下册</option></select></div>\n <div><label>单元</label><input id="qu" placeholder="第一单元"></div><div><label>知识点</label><input id="qk"></div>\n </div><label>题目</label><textarea id="qt"></textarea>\n <div class="form-grid">${["A","B","C","D"].map((x,i)=>`<div><label>选项${x}</label><input id="qo${i}"></div>`).join("")}</div>\n <label>正确选项</label><select id="qc"><option value="0">A</option><option value="1">B</option><option value="2">C</option><option value="3">D</option></select>\n <label>解析</label><textarea id="qe"></textarea><button class="btn primary full" id="saveQ">保存题目</button>`);\n $("#saveQ").onclick=async()=>{try{\n  await api("/questions",{method:"POST",body:JSON.stringify({grade:+$("#qg").value,subject:$("#qs").value,textbook:$("#qb").value,semester:$("#qsem").value,unit:$("#qu").value,knowledge:$("#qk").value,text:$("#qt").value,options:[0,1,2,3].map(i=>$(`#qo${i}`).value),correct_index:+$("#qc").value,explanation:$("#qe").value})});\n  closeModal();toast("题目已保存");go("catalog")\n }catch(e){toast(e.message)}};\n}\n\n// Teacher\n\nasync function classPoints(){\n $("#page").innerHTML=head("课堂积分","正在加载班级、积分规则与周报…")+`<div class="card empty">正在加载课堂积分，请稍候…</div>`;\n let classes;\n try{classes=await api("/teacher/classes")}catch(e){\n  $("#page").innerHTML=head("课堂积分","课堂积分数据暂未载入")+`<div class="card empty">班级列表加载失败：${esc(e.message||"网络异常")}<br><button id="retryClassPoints" class="btn primary" style="margin-top:14px">重新加载</button></div>`;\n  $("#retryClassPoints").onclick=classPoints;return\n }\n if(!classes.length){$("#page").innerHTML=head("课堂积分","快速记录课堂活动与守纪情况")+empty("请先创建班级");return}\n const cid=state.pointClassID&&classes.some(x=>x.id===state.pointClassID)?state.pointClassID:classes[0].id;state.pointClassID=cid;\n const timed=async(path,ms=9000)=>{const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),ms);try{return {ok:true,value:await api(path,{signal:ctl.signal})}}catch(e){return {ok:false,error:(e?.name==="AbortError"?"请求超时，请稍后重试":(e?.message||"加载失败"))}}finally{clearTimeout(timer)}};\n const [dataR,rulesR,recentR,redsR,weeklyR,autoR,growthR,homeroomR,workbenchR]=await Promise.all([\n  timed(`/teacher/points/classes/${cid}`),timed("/points/rules?active_only=true"),timed(`/teacher/points/recent?class_id=${cid}&limit=30`),\n  timed("/rewards/redemptions?status=pending&limit=80"),timed(`/teacher/points/classes/${cid}/weekly?days=7`),timed(`/auto-reward-grants?status=pending&class_id=${cid}&limit=80`),\n  timed(`/teacher/points/classes/${cid}/growth-dashboard`),\n  timed(`/teacher/points/classes/${cid}/homeroom-dashboard`),\n  timed(`/teacher/points/classes/${cid}/workbench`)\n ]);\n if(!dataR.ok){$("#page").innerHTML=head("课堂积分","课堂积分数据暂未载入")+`<div class="card empty">学生积分数据加载失败：${esc(dataR.error)}<br><button id="retryClassPoints" class="btn primary" style="margin-top:14px">重新加载</button></div>`;$("#retryClassPoints").onclick=classPoints;return}\n const data=dataR.value,rules=rulesR.ok?rulesR.value:[],recent=recentR.ok?recentR.value:[],reds=redsR.ok?redsR.value:[],autoGrants=autoR.ok?autoR.value:[];\n const weekly=weeklyR.ok?weeklyR.value:{class:data.class,days:7,studentCount:data.students.length,totals:{earned:0,net:0,activity:0,discipline:0,redemptionCount:0,redeemedPoints:0},ranking:[]};\n const growth=growthR.ok?growthR.value:{groups:[],progressRanking:[],categoryStats:[]};\n const homeroom=homeroomR.ok?homeroomR.value:{today:{recordCount:0,studentCount:0,positiveStudents:0,negativeStudents:0,net:0},profiles:{week:{},month:{}},focusList:[],positiveAlerts:[],students:[],academicBehavior:[]};\n const workbench=workbenchR.ok?workbenchR.value:{summary:{reminders:0,overdue:0,dueToday:0,dueSoon:0,callbacks:0,stale:0,risk:0,progress:0,openTodos:0},urgent:[],stale:[],callbacks:[],riskAlerts:[],progressAlerts:[],todos:[]};\n const growthByStudent=new Map((growth.progressRanking||[]).map(x=>[x.studentID,x]));\n const homeroomByStudent=new Map((homeroom.students||[]).map(x=>[x.studentID,x]));\n if(!state.pointRuleID||!rules.some(x=>x.id===state.pointRuleID))state.pointRuleID=rules[0]?.id||null;\n const clsChooser=`<select id="pointClassSelect" style="width:auto">${classes.map(x=>`<option value="${x.id}" ${x.id===cid?"selected":""}>${esc(x.name)}</option>`).join("")}</select>`;\n const ruleButtons=rules.map(x=>`<button class="rule-btn ${state.pointRuleID===x.id?"active":""}" data-rule="${x.id}"><b>${esc(x.name)}</b><div class="${x.points>0?"point-positive":"point-negative"}">${x.points>0?"+":""}${x.points} 分</div><small class="muted">${x.category==="activity"?"课堂活动":"守纪情况"}</small></button>`).join("")||`<div class="muted">${rulesR.ok?"管理员尚未启用积分规则":"积分规则暂未载入"}</div>`;\n const cards=data.students.map(x=>{const g=growthByStudent.get(x.id)||{},h=homeroomByStudent.get(x.id)||{},badges=(g.badges||[]).slice(0,3).map(b=>`<span class="badge green">${esc(b.icon)} ${esc(b.name)}</span>`).join("");const risk=(h.riskFlags||[]).length?`<span class="badge red">需关注 ${(h.riskFlags||[]).length}</span>`:"";return `<div class="card check-card"><input class="pointStu" type="checkbox" value="${x.id}"><div style="flex:1"><b>${esc(x.name)}</b><div class="muted" style="font-size:12px">可用 ${x.available} · 累计发放 ${x.earned} · 活动 ${x.activity} · 守纪 ${x.discipline}</div>${badges||risk?`<div class="status-line" style="margin-top:7px">${badges}${risk}</div>`:""}</div><div class="actions"><button class="btn secondary small studentFollowup" data-id="${x.id}" data-name="${esc(x.name)}">跟进</button><button class="btn secondary small studentGrowthProfile" data-id="${x.id}" data-name="${esc(x.name)}">成长档案</button><button class="btn secondary small studentCommunication" data-id="${x.id}">沟通</button><button class="btn secondary small pointTrend" data-id="${x.id}" data-name="${esc(x.name)}">趋势</button><button class="btn primary small onePoint" data-id="${x.id}">记录</button></div></div>`}).join("")||empty("当前班级暂无在读学生");\n const weekRank=(weekly.ranking||[]).slice(0,10).map(x=>`<div class="item"><div class="item-main"><b>${x.rank}. ${esc(x.studentName)}</b><small>活动 ${x.activity} · 守纪 ${x.discipline} · 净表现 ${x.net}${x.redemptionCount?` · 兑换${x.redemptionCount}次`:""}</small></div><span class="badge green">本周发放 ${x.earned}</span></div>`).join("")||`<span class="muted">本周暂无积分记录</span>`;\n const starCards=(weekly.ranking||[]).slice(0,3).map((x,i)=>`<div class="star-card"><div class="medal">${["🥇","🥈","🥉"][i]||"⭐"}</div><b>${esc(x.studentName)}</b><small>净表现 ${x.net} · 活动 ${x.activity} · 守纪 ${x.discipline}<br>本周发放 ${x.earned}</small></div>`).join("")||`<span class="muted">本周暂无之星数据</span>`;\n const groupRank=(growth.groups||[]).map(x=>`<div class="item"><div class="item-main"><b>${x.rank?`${x.rank}. `:""}${esc(x.name)}</b><small>${x.memberCount}人 · 活动 ${x.activity} · 守纪 ${x.discipline}</small></div><span class="badge green">净表现 ${x.net>0?"+":""}${x.net}</span></div>`).join("")||`<span class="muted">尚未建立课堂小组</span>`;\n const progressRank=(growth.progressRanking||[]).slice(0,8).map(x=>`<div class="item"><div class="item-main"><b>${x.rank}. ${esc(x.studentName)}</b><small>本周 ${x.currentNet>0?"+":""}${x.currentNet} · 上周 ${x.previousNet>0?"+":""}${x.previousNet}</small></div><span class="badge ${x.change>=0?"green":"red"}">${x.change>0?"+":""}${x.change}</span></div>`).join("")||`<span class="muted">暂无进步数据</span>`;\n const categoryStats=(growth.categoryStats||[]).map(x=>`<div class="item"><div class="item-main"><b>${esc(x.reason)}</b><small>${x.category==="activity"?"课堂活动":"守纪情况"} · ${x.count}次</small></div><b class="${x.points>=0?"point-positive":"point-negative"}">${x.points>0?"+":""}${x.points}</b></div>`).join("")||`<span class="muted">本周暂无分类记录</span>`;\n const loadWarnings=[!rulesR.ok?`积分规则：${rulesR.error}`:"",!recentR.ok?`最近记录：${recentR.error}`:"",!redsR.ok?`积分兑换：${redsR.error}`:"",!weeklyR.ok?`班级周报：${weeklyR.error}`:"",!autoR.ok?`自动奖励：${autoR.error}`:"",!growthR.ok?`成长分析：${growthR.error}`:"",!homeroomR.ok?`班主任总览：${homeroomR.error}`:"",!workbenchR.ok?`今日工作台：${workbenchR.error}`:""].filter(Boolean);\n const warningHtml=loadWarnings.length?`<div class="note" style="margin-bottom:14px"><b>部分数据暂未载入</b><br>${loadWarnings.map(esc).join("<br>")}<br><button id="retryPartialPoint" class="btn secondary small" style="margin-top:8px">重新加载</button></div>`:"";\n const totals=weekly.totals||{earned:0,activity:0,discipline:0,redemptionCount:0};\n const normalPending=reds.filter(x=>data.students.some(s=>s.id===x.studentID)).map(x=>`<div class="item"><div class="item-main"><b>${esc(x.studentName)} · ${esc(x.rewardName)}</b><small>积分兑换 · ${x.costPoints}积分 · ${esc(x.requestedAt||"")}</small></div><div class="actions"><button class="btn primary small tFulfill" data-id="${x.id}">确认发放</button><button class="btn danger small tReject" data-id="${x.id}">拒绝退分</button></div></div>`).join("");\n const autoPending=autoGrants.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.studentName)} · ${esc(x.rewardIcon)} ${esc(x.rewardName)} <span class="badge green">自动奖励</span></b><small>${esc(x.ruleName)} · 达标 ${x.metricValue}/${x.threshold} · ${esc(x.periodKey)}</small></div><div class="actions"><button class="btn primary small aFulfill" data-id="${x.id}">确认发放</button><button class="btn danger small aCancel" data-id="${x.id}">取消奖励</button></div></div>`).join("");\n $("#page").innerHTML=head("课堂积分","批量快捷记分 + 班级周报",clsChooser)+warningHtml+`<div class="grid4">${stat(totals.earned||0,"本周发放")}${stat(totals.activity||0,"活动净分")}${stat(totals.discipline||0,"守纪净分")}${stat(totals.redemptionCount||0,"本周兑换")}</div><div class="section card"><div class="actions"><button id="openDailyWorkbench" class="btn primary small">今日工作台${workbench.summary.reminders?`（${workbench.summary.reminders}）`:""}</button><button id="openHomeroomDashboard" class="btn primary small">班主任总览</button><button id="openFollowupCenter" class="btn primary small">跟进中心</button><button id="managePointGroups" class="btn secondary small">小组管理</button><button id="exportMonthlyGrowth" class="btn secondary small">导出月度成长报告</button><button id="exportHomeroomReport" class="btn secondary small">导出班主任综合报告</button></div></div><div class="section card"><div class="actions"><button id="selectAllPoint" class="btn secondary small">全选学生</button><button id="clearPoint" class="btn secondary small">清空选择</button><button id="exportWeekPoint" class="btn secondary small" ${weeklyR.ok?"":"disabled"}>导出本周积分周报</button></div><h2 style="margin-top:14px">1. 选择规则</h2><div class="rule-grid">${ruleButtons}</div><label>备注（扣分规则通常要求填写）</label><input id="pointNote" placeholder="例如：主动举手并完整说明解题思路"><button id="batchPoint" class="btn primary full" ${rules.length?"":"disabled"}>给选中学生批量记录</button></div><div class="section"><h2>2. 选择学生</h2><div class="list">${cards}</div></div><div class="section card"><div style="display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap"><h2 style="margin:0">本周之星</h2><button id="openPointLeaderboard" class="btn secondary small">查看完整排行榜</button></div><div class="star-grid" style="margin-top:12px">${starCards}</div><div class="section"><h2>班级排行</h2><div class="list">${weekRank}</div></div></div><div class="section grid2"><div class="card"><div style="display:flex;justify-content:space-between;gap:8px;align-items:center"><h2 style="margin:0">小组排行榜</h2><span class="badge">本周</span></div><div class="list" style="margin-top:10px">${groupRank}</div></div><div class="card"><h2>个人进步榜</h2><div class="list">${progressRank}</div></div></div><div class="section card"><h2>课堂表现分类统计</h2><div class="list">${categoryStats}</div></div><div class="section card"><div style="display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap"><h2 style="margin:0">待发放奖励</h2>${autoGrants.length?`<button id="bulkFulfillAuto" class="btn primary small">一键发放本班自动奖励（${autoGrants.length}）</button>`:""}</div><div class="list" style="margin-top:12px">${normalPending+autoPending||`<span class="muted">暂无待发放奖励</span>`}</div></div><div class="section card"><h2>最近积分记录</h2><div class="list">${recent.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.studentName)} · ${esc(x.reason)} <span class="${x.points>0?"point-positive":"point-negative"}">${x.points>0?"+":""}${x.points}</span></b><small>${esc(x.createdAt||"")} · ${esc(x.note||x.actorName||"")}</small></div>${!x.reversed&&["classroom","adjustment"].includes(x.source)?`<button class="btn secondary small undoPoint" data-id="${x.id}">撤销</button>`:`<span class="badge">${x.reversed?"已撤销":"流水"}</span>`}</div>`).join("")||`<span class="muted">${recentR.ok?"暂无记录":"最近记录暂未载入"}</span>`}</div></div>`;\n if($("#retryPartialPoint"))$("#retryPartialPoint").onclick=classPoints;$("#pointClassSelect").onchange=()=>{state.pointClassID=+$("#pointClassSelect").value;classPoints()};\n $$(".rule-btn").forEach(b=>b.onclick=()=>{state.pointRuleID=+b.dataset.rule;classPoints()});\n async function record(ids){if(!state.pointRuleID){toast("请先选择积分规则");return}try{const r=await api("/teacher/points/record",{method:"POST",body:JSON.stringify({student_ids:ids,class_id:cid,rule_id:state.pointRuleID,note:$("#pointNote").value})});toast(r.autoRewards?.length?`已记录，并触发 ${r.autoRewards.length} 个自动奖励`:`已记录 ${ids.length} 名学生`);classPoints()}catch(e){toast(e.message)}}\n $$(".onePoint").forEach(b=>b.onclick=()=>record([+b.dataset.id]));$("#batchPoint").onclick=()=>{const ids=$$(".pointStu:checked").map(x=>+x.value);if(!ids.length){toast("请先勾选学生");return}record(ids)};$("#selectAllPoint").onclick=()=>$$(\'.pointStu\').forEach(x=>x.checked=true);$("#clearPoint").onclick=()=>$$(\'.pointStu\').forEach(x=>x.checked=false);\n $("#exportWeekPoint").onclick=async()=>{if(!weeklyR.ok){toast("周报数据暂未载入，请先重新加载");return}try{await downloadWithAuth(`/teacher/points/classes/${cid}/weekly.xlsx?days=7`,`${data.class.name}_本周课堂积分.xlsx`);toast("本周积分周报已导出")}catch(e){toast(e.message)}};\n $("#managePointGroups").onclick=()=>manageClassPointGroups(cid,data.students);\n if($("#openDailyWorkbench"))$("#openDailyWorkbench").onclick=()=>openDailyWorkbench(cid,data.class,data.students,null);\n if($("#openHomeroomDashboard"))$("#openHomeroomDashboard").onclick=()=>openHomeroomDashboard(homeroom,data.class);\n if($("#exportHomeroomReport"))$("#exportHomeroomReport").onclick=async()=>{try{await downloadWithAuth(`/teacher/points/classes/${cid}/homeroom-report.xlsx`,`${data.class.name}_班主任综合报告.xlsx`);toast("班主任综合报告已导出")}catch(e){toast(e.message)}};\n if($("#openFollowupCenter"))$("#openFollowupCenter").onclick=()=>openFollowUpCenter(cid,data.class,data.students);\n $$(".studentFollowup").forEach(b=>b.onclick=()=>openStudentFollowups(cid,data.class,data.students,+b.dataset.id,b.dataset.name));\n $$(".studentGrowthProfile").forEach(b=>b.onclick=()=>openStudentGrowthProfile(+b.dataset.id,cid,b.dataset.name));\n $$(".studentCommunication").forEach(b=>b.onclick=()=>{const x=homeroomByStudent.get(+b.dataset.id);if(!x){toast("沟通摘要暂未载入");return}openCommunicationSummary(x)});\n $("#exportMonthlyGrowth").onclick=async()=>{try{await downloadWithAuth(`/teacher/points/classes/${cid}/growth-monthly.xlsx`,`${data.class.name}_月度成长报告.xlsx`);toast("月度成长报告已导出")}catch(e){toast(e.message)}};\n if($("#openPointLeaderboard"))$("#openPointLeaderboard").onclick=()=>{state.rankMode="points";state.rankClassID=cid;state.rankDays=7;go("leaderboard")};\n $$(".pointTrend").forEach(b=>b.onclick=async()=>{try{const d=await api(`/teacher/points/students/${+b.dataset.id}/trend?weeks=4&class_id=${cid}`);const badges=(d.badges||[]).map(x=>`<span class="badge green">${esc(x.icon)} ${esc(x.name)}</span>`).join("")||`<span class="muted">本周暂无成长徽章</span>`;const advice=(d.growthAdvice||[]).map(x=>`<div class="item"><div class="item-main"><small>${esc(x)}</small></div></div>`).join("");modal(`${esc(d.student.name)} · 近4周成长趋势`,`<div class="grid3">${stat(d.summary.available,"可用积分")}${stat(d.summary.earned,"累计发放")}${stat((d.trend||[]).at(-1)?.net||0,"本周净表现")}</div><div class="section card"><h2>成长徽章</h2><div class="status-line">${badges}</div></div><div class="section card"><h2>每周净表现</h2>${pointTrendHTML(d.trend||[])}</div>${advice?`<div class="section card"><h2>成长建议</h2><div class="list">${advice}</div></div>`:""}`)}catch(e){toast(e.message)}});\n if($("#bulkFulfillAuto"))$("#bulkFulfillAuto").onclick=async()=>{if(!confirm(`确定一键发放本班 ${autoGrants.length} 条待发放自动奖励吗？`))return;try{const r=await api(`/teacher/points/classes/${cid}/auto-rewards/fulfill-pending`,{method:"POST",body:"{}"});toast(`已发放 ${r.count} 条自动奖励`);classPoints()}catch(e){toast(e.message)}};\n $$(".undoPoint").forEach(b=>b.onclick=async()=>{if(!confirm("确定撤销这条积分记录吗？系统会生成一条反向流水。"))return;try{await api(`/teacher/points/ledger/${+b.dataset.id}/undo`,{method:"POST",body:"{}"});toast("已撤销");classPoints()}catch(e){toast(e.message)}});\n $$(".tFulfill").forEach(b=>b.onclick=async()=>{try{await api(`/rewards/redemptions/${+b.dataset.id}/handle`,{method:"POST",body:JSON.stringify({action:"fulfill",note:""})});toast("已发放");classPoints()}catch(e){toast(e.message)}});$$(".tReject").forEach(b=>b.onclick=async()=>{const note=prompt("填写拒绝/退回原因（可选）","")||"";try{await api(`/rewards/redemptions/${+b.dataset.id}/handle`,{method:"POST",body:JSON.stringify({action:"reject",note})});toast("已退回积分");classPoints()}catch(e){toast(e.message)}});\n $$(".aFulfill").forEach(b=>b.onclick=async()=>{try{await api(`/auto-reward-grants/${+b.dataset.id}/handle`,{method:"POST",body:JSON.stringify({action:"fulfill",note:""})});toast("自动奖励已发放");classPoints()}catch(e){toast(e.message)}});$$(".aCancel").forEach(b=>b.onclick=async()=>{const note=prompt("填写取消原因（可选）","")||"";try{await api(`/auto-reward-grants/${+b.dataset.id}/handle`,{method:"POST",body:JSON.stringify({action:"cancel",note})});toast("自动奖励已取消，库存已恢复");classPoints()}catch(e){toast(e.message)}});\n}\n\n\nfunction openCommunicationSummary(x){\n const risk=(x.riskFlags||[]).map(v=>`<span class="badge red">${esc(v)}</span>`).join("");\n const positive=(x.positiveFlags||[]).map(v=>`<span class="badge green">${esc(v)}</span>`).join("");\n const score=x.academic?.avgScore===null||x.academic?.avgScore===undefined?"暂无":x.academic.avgScore;\n modal(`${esc(x.studentName)} · 家校沟通摘要`,`<div class="grid3">${stat(x.weekly?.net||0,"本周净表现")}${stat(x.monthly?.net||0,"本月净表现")}${stat(score,"近30天平均分")}</div><div class="section card"><h2>提醒与亮点</h2><div class="status-line">${risk}${positive||(!risk?`<span class="muted">暂无特别提醒</span>`:"")}</div></div><div class="section card"><h2>建议沟通摘要</h2><p id="communicationText" style="line-height:1.8;margin:0">${esc(x.communicationSummary||"暂无摘要")}</p><button id="copyCommunication" class="btn primary full">复制沟通摘要</button></div><div class="note section">该摘要用于帮助教师整理事实信息，建议发送前结合具体课堂情境进行人工确认。</div>`);\n $("#copyCommunication").onclick=async()=>{const text=x.communicationSummary||"";try{if(navigator.clipboard){await navigator.clipboard.writeText(text);toast("沟通摘要已复制")}else{prompt("复制沟通摘要",text)}}catch(e){prompt("复制沟通摘要",text)}};\n}\n\nfunction openHomeroomDashboard(d,cls){\n const today=d.today||{},week=d.profiles?.week||{},month=d.profiles?.month||{};\n const focus=(d.focusList||[]).map(x=>`<div class="item"><div class="item-main"><b>${esc(x.studentName)}</b><small>${(x.riskFlags||[]).map(esc).join(" · ")}</small></div><span class="badge red">本周 ${x.weekly?.net>0?"+":""}${x.weekly?.net||0}</span></div>`).join("")||`<span class="muted">暂无重点关注提醒</span>`;\n const positive=(d.positiveAlerts||[]).map(x=>`<div class="item"><div class="item-main"><b>${esc(x.studentName)}</b><small>${(x.positiveFlags||[]).map(esc).join(" · ")}</small></div><span class="badge green">进步</span></div>`).join("")||`<span class="muted">暂无连续进步提醒</span>`;\n const academic=(d.academicBehavior||[]).slice(0,12).map(x=>`<div class="item"><div class="item-main"><b>${esc(x.studentName)} · ${esc(x.linkLabel)}</b><small>近30天 ${x.academic?.count||0} 次练习 · 平均 ${x.academic?.avgScore===null||x.academic?.avgScore===undefined?"—":x.academic.avgScore} 分 · 本月课堂净表现 ${x.monthly?.net>0?"+":""}${x.monthly?.net||0}</small></div><button class="btn secondary small homeroomComm" data-id="${x.studentID}">沟通</button></div>`).join("")||`<span class="muted">暂无联动数据</span>`;\n const studentMap=new Map((d.students||[]).map(x=>[x.studentID,x]));\n modal(`${esc(cls?.name||"班级")} · 班主任综合总览`,`<div class="section card"><h2>今日班级表现</h2><div class="grid4">${stat(today.recordCount||0,"今日记录")}${stat(today.studentCount||0,"参与学生")}${stat(today.positiveStudents||0,"正向学生")}${stat(today.negativeStudents||0,"需关注学生")}</div><p class="muted">今日课堂活动 ${today.activity||0} · 守纪 ${today.discipline||0} · 净表现 ${today.net>0?"+":""}${today.net||0}</p></div><div class="section grid2"><div class="card"><h2>重点关注名单</h2><div class="list">${focus}</div></div><div class="card"><h2>连续进步提醒</h2><div class="list">${positive}</div></div></div><div class="section grid2"><div class="card"><h2>本周班级画像</h2><div class="grid2">${stat(`${week.participationRate||0}%`,"参与率")}${stat(week.net||0,"净表现")}</div><p class="muted">参与 ${week.activeStudents||0}/${week.studentCount||0} · 活动 ${week.activity||0} · 守纪 ${week.discipline||0} · 自动奖励 ${week.autoRewards||0}</p></div><div class="card"><h2>本月班级画像</h2><div class="grid2">${stat(`${month.participationRate||0}%`,"参与率")}${stat(month.net||0,"净表现")}</div><p class="muted">参与 ${month.activeStudents||0}/${month.studentCount||0} · 活动 ${month.activity||0} · 守纪 ${month.discipline||0} · 自动奖励 ${month.autoRewards||0}</p></div></div><div class="section card"><h2>学业成绩 × 课堂表现联动</h2><div class="note" style="margin-bottom:10px">仅用于教学观察与沟通参考，不作为自动评价或处分依据。</div><div class="list">${academic}</div></div>`);\n $$(".homeroomComm").forEach(b=>b.onclick=()=>{const x=studentMap.get(+b.dataset.id);if(x)openCommunicationSummary(x)});\n}\n\n\nasync function manageClassPointGroups(cid,students){\n try{\n  const groups=await api(`/teacher/points/classes/${cid}/groups`);\n  const memberSet=new Set(groups.flatMap(g=>(g.members||[]).map(m=>m.id)));\n  const groupBlocks=groups.map(g=>`<div class="card" style="margin-bottom:12px"><div style="display:flex;justify-content:space-between;gap:8px;align-items:center"><div><b>${esc(g.name)}</b><small>${g.memberCount}人 · 本周净表现 ${g.net>0?"+":""}${g.net}</small></div><button class="btn danger small deletePointGroup" data-id="${g.id}" data-name="${esc(g.name)}">删除</button></div><div class="list" style="margin-top:10px">${students.map(s=>`<label class="check-card" style="padding:9px 0"><input type="checkbox" class="groupMember" data-group="${g.id}" value="${s.id}" ${(g.members||[]).some(m=>m.id===s.id)?"checked":""}><span>${esc(s.name)}</span></label>`).join("")||`<span class="muted">暂无学生</span>`}</div><button class="btn primary full saveGroupMembers" data-id="${g.id}">保存成员</button></div>`).join("")||`<div class="empty">尚未建立小组</div>`;\n  modal("课堂小组管理",`<div class="note" style="margin-bottom:12px">每名学生在同一班级只加入一个激励小组；把学生加入新组会自动从原组移出。</div><div class="actions" style="margin-bottom:12px"><button id="createPointGroup" class="btn primary">＋新建小组</button></div>${groupBlocks}`);\n  $("#createPointGroup").onclick=async()=>{const name=(prompt("输入小组名称，例如：星光组","")||"").trim();if(!name)return;try{await api(`/teacher/points/classes/${cid}/groups`,{method:"POST",body:JSON.stringify({name,sort_order:groups.length})});toast("小组已创建");closeModal();classPoints()}catch(e){toast(e.message)}};\n  $$(".saveGroupMembers").forEach(b=>b.onclick=async()=>{const gid=+b.dataset.id,ids=$$(`.groupMember[data-group="${gid}"]:checked`).map(x=>+x.value);try{await api(`/teacher/points/classes/${cid}/groups/${gid}/members`,{method:"PUT",body:JSON.stringify({student_ids:ids})});toast("小组成员已保存");closeModal();classPoints()}catch(e){toast(e.message)}});\n  $$(".deletePointGroup").forEach(b=>b.onclick=async()=>{if(!confirm(`确定删除小组“${b.dataset.name}”吗？不会删除学生积分记录。`))return;try{await api(`/teacher/points/classes/${cid}/groups/${+b.dataset.id}`,{method:"DELETE"});toast("小组已删除");closeModal();classPoints()}catch(e){toast(e.message)}});\n }catch(e){toast(e.message)}\n}\n\n\n\nfunction wbDueClass(x){return x.dueState==="overdue"?"red":(x.dueState==="today"||x.dueState==="soon"?"amber":"")}\nasync function openDailyWorkbench(cid,cls,students,prefetched=null){\n try{\n  const d=prefetched||await api(`/teacher/points/classes/${cid}/workbench`),s=d.summary||{};\n  const urgent=(d.urgent||[]).map(x=>`<div class="item"><div class="item-main"><b>${x.kind==="todo"?"班级待办":"学生跟进"} · ${x.studentName?esc(x.studentName)+" · ":""}${esc(x.title)}</b><small>${esc(x.priorityName||"普通")}优先 · ${esc(x.dueLabel||"")}</small></div><div class="actions"><span class="badge ${wbDueClass(x)}">${esc(x.dueLabel||"提醒")}</span>${x.kind==="followup"?`<button class="btn secondary small wbFollowup" data-id="${x.id}">详情</button>`:`<button class="btn primary small wbTodoDone" data-id="${x.id}">完成</button>`}</div></div>`).join("")||`<span class="muted">未来3天暂无到期或逾期事项</span>`;\n  const stale=(d.stale||[]).map(x=>`<div class="item"><div class="item-main"><b>${esc(x.studentName)} · ${esc(x.title)}</b><small>${x.daysWithoutUpdate}天未更新 · ${esc(x.statusName||"")}</small></div><button class="btn secondary small wbFollowup" data-id="${x.id}">继续跟进</button></div>`).join("")||`<span class="muted">暂无7天以上未更新事项</span>`;\n  const callbacks=(d.callbacks||[]).map(x=>`<div class="item"><div class="item-main"><b>${esc(x.studentName)} · ${esc(x.title)}</b><small>最近家长沟通：${esc(x.contactAt||"")}<br>${esc(x.contactContent||"")}</small></div><button class="btn primary small wbFollowup" data-id="${x.followupID}">回访</button></div>`).join("")||`<span class="muted">暂无待回访家长沟通</span>`;\n  const risks=(d.riskAlerts||[]).map(x=>`<div class="item"><div class="item-main"><b>${esc(x.studentName)}</b><small>${(x.flags||[]).map(esc).join(" · ")}</small></div><button class="btn secondary small wbStudent" data-id="${x.studentID}" data-name="${esc(x.studentName)}">跟进</button></div>`).join("")||`<span class="muted">暂无异常提醒</span>`;\n  const progress=(d.progressAlerts||[]).map(x=>`<div class="item"><div class="item-main"><b>${esc(x.studentName)}</b><small>${(x.flags||[]).map(esc).join(" · ")}</small></div><span class="badge green">进步</span></div>`).join("")||`<span class="muted">暂无连续进步提醒</span>`;\n  const todos=(d.todos||[]).map(x=>`<div class="item"><div class="item-main"><b>${esc(x.title)}</b><small>${esc(x.priorityName)}优先 · ${esc(x.dueLabel||"未设截止")}</small></div><button class="btn primary small wbTodoDone" data-id="${x.id}">完成</button></div>`).join("")||`<span class="muted">暂无未完成班级待办</span>`;\n  modal(`${esc(cls?.name||d.class?.name||"班级")} · 今日工作台`,`<div class="grid4">${stat(s.reminders||0,"今日提醒")}${stat(s.overdue||0,"已逾期")}${stat(s.callbacks||0,"待回访")}${stat(s.openTodos||0,"班级待办")}</div><div class="note section">${esc(d.ruleNote||"")}</div><div class="section card"><h2>到期与逾期</h2><div class="list">${urgent}</div></div><div class="section card"><h2>长期未处理</h2><div class="list">${stale}</div></div><div class="section card"><h2>家长沟通待回访</h2><div class="list">${callbacks}</div></div><div class="section grid2"><div class="card"><h2>需要关注</h2><div class="list">${risks}</div></div><div class="card"><h2>进步提醒</h2><div class="list">${progress}</div></div></div><div class="section card"><h2>班级待办</h2><div class="list">${todos}</div></div>`);\n  $$(".wbFollowup").forEach(b=>b.onclick=()=>openFollowUpDetail(cid,cls,students,+b.dataset.id));\n  $$(".wbStudent").forEach(b=>b.onclick=()=>openStudentFollowups(cid,cls,students,+b.dataset.id,b.dataset.name));\n  $$(".wbTodoDone").forEach(b=>b.onclick=async()=>{try{await api(`/teacher/points/classes/${cid}/todos/${+b.dataset.id}/status`,{method:"PUT",body:JSON.stringify({status:"done"})});toast("班级待办已完成");openDailyWorkbench(cid,cls,students,null)}catch(e){toast(e.message)}});\n }catch(e){toast(e.message)}\n}\nasync function openStudentFollowups(cid,cls,students,sid,name){\n try{\n  const d=await api(`/teacher/points/classes/${cid}/followups`),rows=(d.cases||[]).filter(x=>+x.studentID===+sid);\n  const items=rows.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.title)}</b><small>${esc(x.categoryName)} · ${esc(x.priorityName)}优先 · ${esc(x.statusName)}${x.dueDate?` · ${esc(x.dueLabel)}`:""}${x.latestLog?`<br>最近：${esc(x.latestLog.content)}`:""}</small></div><button class="btn secondary small studentFollowupDetail" data-id="${x.id}">详情</button></div>`).join("")||`<span class="muted">暂无该学生跟进事项</span>`;\n  modal(`${esc(name||"学生")} · 跟进事项`,`<div class="actions" style="margin-bottom:12px"><button id="newStudentSpecificFollowup" class="btn primary">＋新建跟进</button><button id="allClassFollowups" class="btn secondary">班级跟进中心</button></div><div class="list">${items}</div>`);\n  $("#newStudentSpecificFollowup").onclick=()=>createFollowUpForm(cid,cls,students,sid,name);\n  $("#allClassFollowups").onclick=()=>openFollowUpCenter(cid,cls,students);\n  $$(".studentFollowupDetail").forEach(b=>b.onclick=()=>openFollowUpDetail(cid,cls,students,+b.dataset.id));\n }catch(e){toast(e.message)}\n}\n\nfunction followupBadgeClass(x){\n if(x.status==="done")return "green";\n if(x.overdue)return "red";\n if(x.priority==="high")return "amber";\n return "";\n}\nasync function openFollowUpCenter(cid,cls,students){\n try{\n  const d=await api(`/teacher/points/classes/${cid}/followups`),s=d.summary||{};\n  const cases=(d.cases||[]).map(x=>`<div class="item"><div class="item-main"><b>${esc(x.studentName)} · ${esc(x.title)}</b><small>${esc(x.categoryName)} · ${esc(x.priorityName)}优先 · ${esc(x.statusName)}${x.dueDate?` · 截止 ${esc(x.dueDate)}`:""} · ${esc(x.dueLabel||"")}${x.latestLog?`<br>最近：${esc(x.latestLog.content)}`:""}</small></div><div class="actions"><span class="badge ${followupBadgeClass(x)}">${esc(x.statusName)}</span><button class="btn secondary small followupDetail" data-id="${x.id}">详情</button></div></div>`).join("")||`<span class="muted">暂无学生跟进事项</span>`;\n  const todos=(d.todos||[]).map(x=>`<div class="item"><div class="item-main"><b>${esc(x.title)}</b><small>${esc(x.priorityName)}优先${x.dueDate?` · 截止 ${esc(x.dueDate)}`:""} · ${esc(x.dueLabel||"")}${x.note?`<br>${esc(x.note)}`:""}</small></div><button class="btn ${x.status==="done"?"secondary":"primary"} small todoToggle" data-id="${x.id}" data-status="${x.status}">${x.status==="done"?"重新打开":"完成"}</button></div>`).join("")||`<span class="muted">暂无班级待办</span>`;\n  modal(`${esc(cls?.name||"班级")} · 跟进中心`,`<div class="grid4">${stat(s.open||0,"待跟进")}${stat(s.inProgress||0,"跟进中")}${stat(s.overdue||0,"已逾期")}${stat(s.communications||0,"家长沟通")}</div><div class="section card"><div class="actions"><button id="newStudentFollowup" class="btn primary">＋学生跟进</button><button id="newClassTodo" class="btn secondary">＋班级待办</button><button id="exportFollowups" class="btn secondary">导出跟进报告</button></div></div><div class="section card"><h2>学生跟进事项</h2><div class="list">${cases}</div></div><div class="section card"><h2>班级待办 <span class="badge">${s.todoOpen||0}项未完成</span></h2><div class="list">${todos}</div></div>`);\n  $("#newStudentFollowup").onclick=()=>createFollowUpForm(cid,cls,students);\n  $("#newClassTodo").onclick=()=>createClassTodoForm(cid,cls,students);\n  $("#exportFollowups").onclick=async()=>{try{await downloadWithAuth(`/teacher/points/classes/${cid}/followups-report.xlsx`,`${cls?.name||"班级"}_学生跟进报告.xlsx`);toast("跟进报告已导出")}catch(e){toast(e.message)}};\n  $$(".followupDetail").forEach(b=>b.onclick=()=>openFollowUpDetail(cid,cls,students,+b.dataset.id));\n  $$(".todoToggle").forEach(b=>b.onclick=async()=>{try{await api(`/teacher/points/classes/${cid}/todos/${+b.dataset.id}/status`,{method:"PUT",body:JSON.stringify({status:b.dataset.status==="done"?"open":"done"})});toast("班级待办已更新");openFollowUpCenter(cid,cls,students)}catch(e){toast(e.message)}});\n }catch(e){toast(e.message)}\n}\nfunction createFollowUpForm(cid,cls,students,studentID=null,studentName=""){\n const options=(students||[]).map(s=>`<option value="${s.id}" ${+studentID===s.id?"selected":""}>${esc(s.name)}</option>`).join("");\n modal(studentID?`${esc(studentName)} · 新建跟进`:"新建学生跟进",`<label>学生</label><select id="fuStudent">${options}</select><label>跟进事项</label><input id="fuTitle" placeholder="例如：本周主动发言较少，持续观察课堂参与"><div class="form-grid"><div><label>类别</label><select id="fuCategory"><option value="growth">成长跟进</option><option value="learning">学习跟进</option><option value="classroom">课堂表现</option><option value="parent">家校沟通</option><option value="other">其他</option></select></div><div><label>优先级</label><select id="fuPriority"><option value="normal">普通</option><option value="high">高</option><option value="low">低</option></select></div></div><label>截止日期（可选）</label><input id="fuDue" type="date"><label>初始记录（可选）</label><textarea id="fuNote" placeholder="记录观察到的事实和下一步计划"></textarea><button id="saveFollowup" class="btn primary full">创建跟进事项</button>`);\n $("#saveFollowup").onclick=async()=>{try{const body={student_id:+$("#fuStudent").value,title:$("#fuTitle").value,category:$("#fuCategory").value,priority:$("#fuPriority").value,due_date:$("#fuDue").value,note:$("#fuNote").value,source:"manual"};await api(`/teacher/points/classes/${cid}/followups`,{method:"POST",body:JSON.stringify(body)});toast("跟进事项已创建");openFollowUpCenter(cid,cls,students)}catch(e){toast(e.message)}};\n}\nasync function openFollowUpDetail(cid,cls,students,fid){\n try{\n  const x=await api(`/teacher/points/classes/${cid}/followups/${fid}`);\n  const logs=(x.logs||[]).map(l=>`<div class="item"><div class="item-main"><b>${esc(l.typeName)}</b><small>${esc(l.createdAt||"")} · ${esc(l.actorName||"")}<br>${esc(l.content)}</small></div></div>`).join("")||`<span class="muted">暂无跟进记录</span>`;\n  modal(`${esc(x.studentName)} · ${esc(x.title)}`,`<div class="status-line"><span class="badge ${followupBadgeClass(x)}">${esc(x.statusName)}</span><span class="badge">${esc(x.categoryName)}</span><span class="badge">${esc(x.priorityName)}优先</span>${x.dueDate?`<span class="badge ${x.overdue?"red":""}">截止 ${esc(x.dueDate)} · ${esc(x.dueLabel)}</span>`:""}</div>${x.note?`<div class="note section">${esc(x.note)}</div>`:""}<div class="section card"><h2>处理状态</h2><select id="fuStatus"><option value="open" ${x.status==="open"?"selected":""}>待跟进</option><option value="in_progress" ${x.status==="in_progress"?"selected":""}>跟进中</option><option value="done" ${x.status==="done"?"selected":""}>已完成</option></select><button id="saveFuStatus" class="btn secondary full">保存状态</button></div><div class="section card"><h2>新增跟进记录</h2><label>记录类型</label><select id="fuLogType"><option value="note">跟进记录</option><option value="parent_contact">家长沟通（家长端可见）</option><option value="result">处理结果</option></select><label>内容</label><textarea id="fuLogContent" placeholder="记录实际跟进过程、沟通内容或处理结果"></textarea><button id="saveFuLog" class="btn primary full">添加记录</button></div><div class="section card"><h2>跟进历史</h2><div class="list">${logs}</div></div><div class="note section">只有标记为“家长沟通”的记录会展示给已绑定家长；教师内部跟进记录不会对家长公开。</div>`);\n  $("#saveFuStatus").onclick=async()=>{try{await api(`/teacher/points/classes/${cid}/followups/${fid}/status`,{method:"PUT",body:JSON.stringify({status:$("#fuStatus").value})});toast("跟进状态已更新");openFollowUpDetail(cid,cls,students,fid)}catch(e){toast(e.message)}};\n  $("#saveFuLog").onclick=async()=>{try{await api(`/teacher/points/classes/${cid}/followups/${fid}/logs`,{method:"POST",body:JSON.stringify({log_type:$("#fuLogType").value,content:$("#fuLogContent").value})});toast("跟进记录已添加");openFollowUpDetail(cid,cls,students,fid)}catch(e){toast(e.message)}};\n }catch(e){toast(e.message)}\n}\nfunction createClassTodoForm(cid,cls,students){\n modal("新建班级待办",`<label>待办事项</label><input id="todoTitle" placeholder="例如：周五前完成家长会材料"><div class="form-grid"><div><label>优先级</label><select id="todoPriority"><option value="normal">普通</option><option value="high">高</option><option value="low">低</option></select></div><div><label>截止日期</label><input id="todoDue" type="date"></div></div><label>备注（可选）</label><textarea id="todoNote"></textarea><button id="saveClassTodo" class="btn primary full">保存班级待办</button>`);\n $("#saveClassTodo").onclick=async()=>{try{await api(`/teacher/points/classes/${cid}/todos`,{method:"POST",body:JSON.stringify({title:$("#todoTitle").value,priority:$("#todoPriority").value,due_date:$("#todoDue").value,note:$("#todoNote").value})});toast("班级待办已创建");openFollowUpCenter(cid,cls,students)}catch(e){toast(e.message)}};\n}\nasync function openStudentGrowthTimeline(cid,sid,name){\n try{\n  const d=await api(`/teacher/points/students/${sid}/growth-timeline?class_id=${cid}&limit=80`);\n  const rows=(d.events||[]).map(x=>`<div class="timeline-item"><div class="timeline-icon">${esc(x.icon||"•")}</div><div class="timeline-main"><b>${esc(x.title)}</b><small>${esc(x.time||"")}<br>${esc(x.detail||"")}</small></div></div>`).join("")||`<div class="empty">暂无成长档案记录</div>`;\n  modal(`${esc(name||d.student?.name||"学生")} · 成长档案`,`<div class="note" style="margin-bottom:12px">成长档案按时间整合课堂积分、自动奖励、学习练习和教师跟进记录，便于回顾事实变化。</div><div class="timeline">${rows}</div>`);\n }catch(e){toast(e.message)}\n}\n\nasync function teacher(){\n const [d,w]=await Promise.all([api("/teacher/dashboard"),api("/teacher/workbench-summary").catch(()=>null)]);\n const ws=w?.summary||{};\n const workbench=w?`<div class="section card"><div style="display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap"><div><h2 style="margin:0">今日待办与主动提醒</h2><p class="muted" style="margin:5px 0 0">到期事项、长期未处理、家长沟通待回访与学生成长提醒</p></div><span class="badge ${ws.overdue?"red":(ws.reminders?"amber":"green")}">${ws.reminders||0} 条提醒</span></div><div class="grid4" style="margin-top:12px">${stat(ws.overdue||0,"已逾期")}${stat((ws.dueToday||0)+(ws.dueSoon||0),"即将到期")}${stat(ws.callbacks||0,"待回访")}${stat(ws.openTodos||0,"班级待办")}</div><div class="list" style="margin-top:12px">${(w.classes||[]).map(x=>`<div class="item"><div class="item-main"><b>${esc(x.class.name)}</b><small>提醒 ${x.summary.reminders||0} · 逾期 ${x.summary.overdue||0} · 待回访 ${x.summary.callbacks||0} · 待办 ${x.summary.openTodos||0}</small></div><button class="btn primary small openClassWorkbench" data-id="${x.class.id}">查看</button></div>`).join("")||`<span class="muted">暂无班级提醒</span>`}</div></div>`:"";\n $("#page").innerHTML=head("教师工作台","班级教学与学情概览",`<button class="btn primary" id="teacherGlobalSearch">🔎 快捷搜索</button>`)+\n `<div class="grid4">${stat(d.classes,"班级")}${stat(d.students,"学生")}${stat(d.assignments,"作业")}${stat(`${d.submissions}/${d.expectedSubmissions}`,"已交 / 应交")}</div>${workbench}\n <div class="section card"><h2>快捷操作</h2><div class="actions"><button class="btn primary quickTeacher" data-page="classPoints">课堂积分</button><button class="btn secondary quickTeacher" data-page="classes">班级学生</button><button class="btn secondary quickTeacher" data-page="papers">组卷作业</button><button class="btn secondary quickTeacher" data-page="analytics">学情分析</button></div></div>\n <div class="section grid2"><div class="card"><h2>班级平均分</h2><div style="font-size:42px;font-weight:900;color:var(--primary)">${d.avgScore}</div><p class="muted">整体正确率 ${d.avgAccuracy}% · 完成率 ${d.completionRate}%</p></div>\n <div class="card"><h2>薄弱知识点</h2><div class="knowledge">${(d.weakKnowledge||[]).slice(0,5).map(x=>`<div class="knowledge-row"><small>${esc(x.knowledge)}</small><div class="knowledge-meter"><i style="width:${x.accuracy}%"></i></div><b>${x.accuracy}%</b></div>`).join("")||"<span class=\'muted\'>暂无数据</span>"}</div></div></div>`;\n $("#teacherGlobalSearch").onclick=globalSearchDialog;\n $$(".quickTeacher").forEach(b=>b.onclick=()=>go(b.dataset.page));\n $$(".openClassWorkbench").forEach(b=>b.onclick=()=>{state.pointClassID=+b.dataset.id;go("classPoints")});\n}\nasync function classes(){\n const list=await api("/teacher/classes");\n $("#page").innerHTML=head("班级学生","学生全生命周期、成绩报表与家长绑定",`<button class="btn primary" id="newClass">＋新建班级</button>`)+\n `<div class="list">${list.map(c=>`<div class="item"><div class="item-main"><b>${esc(c.name)}</b><small>${c.grade}年级 · ${c.studentCount}名学生</small></div><div class="actions"><button class="btn secondary small showStudents" data-id="${c.id}">学生管理</button><button class="btn secondary small classReport" data-id="${c.id}" data-name="${esc(c.name)}">班级报表</button><button class="btn primary small addStudent" data-id="${c.id}" data-grade="${c.grade}">加学生</button></div></div>`).join("")||"<div class=\'card empty\'>暂无班级</div>"}</div>`;\n $("#newClass").onclick=()=>{modal("新建班级",`<label>班级名称</label><input id="cn"><label>年级</label><select id="cg">${[1,2,3,4,5,6].map(x=>`<option>${x}</option>`).join("")}</select><button id="saveClass" class="btn primary full">保存</button>`);$("#saveClass").onclick=async()=>{try{await api("/teacher/classes",{method:"POST",body:JSON.stringify({name:$("#cn").value||"新班级",grade:+$("#cg").value})});closeModal();toast("班级已创建");go("classes")}catch(e){toast(e.message)}}};\n $$(".showStudents").forEach(b=>b.onclick=()=>studentList(+b.dataset.id));$$(".addStudent").forEach(b=>b.onclick=()=>studentForm(+b.dataset.id,+b.dataset.grade));$$(".classReport").forEach(b=>b.onclick=async()=>{try{await downloadWithAuth(`/teacher/classes/${+b.dataset.id}/report.xlsx`,`${b.dataset.name}_成绩汇总.xlsx`);toast("班级报表已导出")}catch(e){toast(e.message)}});\n}\nasync function studentList(cid){\n const [a,classes]=await Promise.all([api(`/teacher/classes/${cid}/students`),api("/teacher/classes")]);\n modal("班级学生",a.length?`<div class="note" style="margin-bottom:10px">系统会永久记录班级历程；调班后原作业按接收快照保留，不会消失。</div><div class="list">${a.map(s=>`<div class="item"><div class="item-main"><b>${esc(s.name)}</b><small>${esc(s.username)} · 家长 ${s.parentName?esc(s.parentName):"未绑定"}</small></div><div class="actions"><button class="btn primary small studentGrowthProfileList" data-id="${s.id}" data-name="${esc(s.name)}">成长档案</button><button class="btn secondary small studentHistory" data-id="${s.id}" data-name="${esc(s.name)}">班级历史</button><button class="btn secondary small studentReport" data-id="${s.id}" data-name="${esc(s.name)}">成绩单</button><button class="btn secondary small bindParent" data-id="${s.id}" data-name="${esc(s.name)}" data-parent="${s.parentID||""}">${s.parentName?"更换家长":"绑定家长"}</button><button class="btn secondary small moveStudent" data-id="${s.id}" data-name="${esc(s.name)}">调班</button><button type="button" class="btn danger small archiveStudent" style="flex:1 0 100%;min-height:44px" data-id="${s.id}" data-name="${esc(s.name)}">毕业归档</button></div></div>`).join("")}</div>`:"<div class=\'empty\'>暂无学生</div>");\n $$(".studentGrowthProfileList").forEach(b=>b.onclick=()=>openStudentGrowthProfile(+b.dataset.id,cid,b.dataset.name));\n $$(".bindParent").forEach(b=>b.onclick=()=>parentBindForm(+b.dataset.id,b.dataset.name,cid,b.dataset.parent?+b.dataset.parent:null));\n $$(".moveStudent").forEach(b=>b.onclick=()=>transferStudentForm(+b.dataset.id,b.dataset.name,cid,classes));\n $$(".archiveStudent").forEach(b=>b.onclick=()=>archiveStudentForm(+b.dataset.id,b.dataset.name,cid));\n $$(".studentHistory").forEach(b=>b.onclick=async()=>{try{const rows=await api(`/teacher/students/${+b.dataset.id}/history`);modal(`${esc(b.dataset.name)} · 班级历史`,rows.length?`<div class="list">${rows.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.className)}</b><small>${(x.joinedAt||"").slice(0,10)} → ${x.current?"当前":(x.leftAt||"").slice(0,10)} · ${esc(x.current?"在读":x.leaveReasonName)}</small></div></div>`).join("")}</div>`:"<div class=\'empty\'>暂无历史</div>")}catch(e){toast(e.message)}});\n $$(".studentReport").forEach(b=>b.onclick=async()=>{try{await downloadWithAuth(`/teacher/students/${+b.dataset.id}/report.xlsx`,`${b.dataset.name}_个人成绩单.xlsx`);toast("学生成绩单已导出")}catch(e){toast(e.message)}});\n}\nfunction archiveStudentForm(sid,name,cid){\n modal(`${name} · 毕业归档`,`<div class="note" style="margin-bottom:12px">毕业归档后：学生账号会立即停用并退出当前班级；作业接收记录、成绩、积分、兑换记录和班级历史都会保留。家长绑定关系也会保留，便于继续查看历史记录。</div>\n <p style="line-height:1.7">确定将 <b>${esc(name)}</b> 毕业归档吗？</p>\n <div class="actions" style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px">\n   <button type="button" id="cancelArchive" class="btn secondary">取消</button>\n   <button type="button" id="confirmArchive" class="btn danger">确认毕业归档</button>\n </div>`);\n $("#cancelArchive").onclick=()=>studentList(cid);\n $("#confirmArchive").onclick=async()=>{\n   const btn=$("#confirmArchive");btn.disabled=true;btn.textContent="处理中…";\n   try{\n     await api(`/teacher/students/${sid}/archive`,{method:"POST"});\n     closeModal();toast("学生已毕业归档并停用账号");go("classes")\n   }catch(e){btn.disabled=false;btn.textContent="确认毕业归档";toast(e.message)}\n };\n}\nasync function parentBindForm(sid,name,cid,currentParentID){\n try{\n  const parents=await api("/teacher/parents");\n  if(!parents.length){toast("暂无可用家长账号，请先让管理员创建家长账号");return}\n  modal(`${name} · 家长绑定`,`<div class="note">绑定后，家长可查看该学生的学情、作业、课堂积分和奖励兑换记录。</div>\n  <label>选择家长账号</label>\n  <select id="bindParentSelect"><option value="">— 解除绑定 —</option>${parents.map(p=>`<option value="${p.id}" ${currentParentID===p.id?"selected":""}>${esc(p.name)}（${esc(p.username)}）</option>`).join("")}</select>\n  <button id="saveParentBind" class="btn primary full">保存家长绑定</button>`);\n  $("#saveParentBind").onclick=async()=>{const v=$("#bindParentSelect").value;try{await api(`/teacher/students/${sid}/parent`,{method:"POST",body:JSON.stringify({parent_id:v?+v:null})});closeModal();toast(v?"家长绑定已保存":"已解除家长绑定");studentList(cid)}catch(e){toast(e.message)}}\n }catch(e){toast(e.message)}\n}\nfunction transferStudentForm(sid,name,currentCid,classes){\n const targets=classes.filter(c=>c.id!==currentCid);\n if(!targets.length){toast("请先建立另一个目标班级");return}\n modal("学生调班",`<p>将 <b>${esc(name)}</b> 调整到：</p><label>目标班级</label><select id="targetClass">${targets.map(c=>`<option value="${c.id}">${esc(c.name)} · ${c.grade}年级</option>`).join("")}</select><div class="note" style="margin-top:10px">调班后学生年级会自动同步到目标班级，历史成绩不会删除。</div><button id="saveTransfer" class="btn primary full">确认调班</button>`);\n $("#saveTransfer").onclick=async()=>{try{await api(`/teacher/students/${sid}/transfer`,{method:"POST",body:JSON.stringify({target_class_id:+$("#targetClass").value})});closeModal();toast("调班完成");go("classes")}catch(e){toast(e.message)}};\n}\nfunction studentForm(cid,grade){\n modal("创建学生账号",`<div class="form-grid"><div><label>学生姓名</label><input id="sn"></div><div><label>学生账号</label><input id="su"></div><div><label>初始密码</label><input id="sp" type="password" placeholder="至少8位，包含字母和数字"></div><div><label>家长账号（可选）</label><input id="sparent" placeholder="已有家长登录账号"></div></div><button id="saveStudent" class="btn primary full">创建</button>`);\n $("#saveStudent").onclick=async()=>{try{await api("/teacher/students",{method:"POST",body:JSON.stringify({name:$("#sn").value,username:$("#su").value,password:$("#sp").value,grade,class_id:cid,parent_username:$("#sparent").value||null})});closeModal();toast("学生已创建");go("classes")}catch(e){toast(e.message)}};\n}\nasync function papers(){\n const [cs,as]=await Promise.all([api("/teacher/classes"),api("/teacher/assignments")]);\n $("#page").innerHTML=head("组卷与作业","作业接收快照、截止逾期和成绩报表统一管理",`<button class="btn primary" id="newAssignment">✨自动组卷</button>`)+\n `<div class="list">${as.map(a=>`<div class="item"><div class="item-main"><b>${esc(a.title)}</b><small>${esc(a.paper?.textbook||"")} · ${esc(a.paper?.unit||"综合")} · 截止 ${esc(a.dueDate)} · 已交 ${a.completedCount}/${a.studentCount} · 未交 ${a.pendingCount}</small><div class="status-line" style="margin-top:6px"><span class="badge ${a.deadlinePassed?"red":"green"}">${esc(a.deadlineStatus)}</span>${a.deadlinePassed&&a.pendingCount?`<span class="badge red">逾期未交 ${a.pendingCount}</span>`:""}</div></div><div class="actions"><button class="btn secondary small subs" data-id="${a.id}">完成情况</button><button class="btn secondary small exportAssignment" data-id="${a.id}" data-title="${esc(a.title)}">导出成绩</button></div></div>`).join("")||"<div class=\'card empty\'>暂无作业</div>"}</div>`;\n $("#newAssignment").onclick=()=>assignmentForm(cs);\n $$(".subs").forEach(b=>b.onclick=()=>submissionList(+b.dataset.id));\n $$(".exportAssignment").forEach(b=>b.onclick=async()=>{try{await downloadWithAuth(`/teacher/assignments/${+b.dataset.id}/export.xlsx`,`作业成绩_${b.dataset.title}.xlsx`);toast("成绩报表已导出")}catch(e){toast(e.message)}});\n}\nfunction assignmentForm(classes){\n if(!classes.length){toast("请先新建班级");return}\n modal("自动组卷",`<label>作业名称</label><input id="at" value="课后练习"><div class="form-grid">\n <div><label>班级</label><select id="ac">${classes.map(c=>`<option value="${c.id}" data-grade="${c.grade}" data-count="${c.studentCount||0}">${esc(c.name)} · ${c.grade}年级 · ${c.studentCount||0}人</option>`).join("")}</select></div>\n <div><label>科目</label><select id="as"><option>数学</option><option>语文</option><option>英语</option></select></div>\n <div><label>教材版本</label><input id="ab" value="人教版"></div><div><label>单元</label><input id="au" placeholder="留空=综合"></div>\n <div><label>题量</label><select id="an"><option>5</option><option>10</option><option>15</option><option>20</option></select></div><div><label>截止日期</label><input type="date" id="ad"></div>\n </div><div class="note" style="margin-top:10px">班级名称后会显示当前学生人数；系统会优先选中有学生的班级。截止日期按学校本地时间当天 23:59 计算；布置时会固定记录接收学生，之后调班或毕业也不会丢失该作业。</div><button id="saveAssignment" class="btn primary full">生成并布置</button>`);\n const firstNonEmpty=classes.find(c=>(c.studentCount||0)>0);if(firstNonEmpty)$("#ac").value=String(firstNonEmpty.id);\n $("#saveAssignment").onclick=async()=>{try{\n  const o=$("#ac").selectedOptions[0],grade=+o.dataset.grade,class_id=+o.value,studentCount=+o.dataset.count,subject=$("#as").value,textbook=$("#ab").value,unit=$("#au").value;\n  if(studentCount===0&&!confirm("当前班级暂无学生。继续布置将生成 0 名接收学生的作业，确定继续吗？"))return;\n  const params=new URLSearchParams({grade,subject});if(textbook)params.set("textbook",textbook);if(unit)params.set("unit",unit);\n  const qs=await api("/questions?"+params.toString());const ids=qs.sort(()=>Math.random()-.5).slice(0,+$("#an").value).map(q=>q.id);if(!ids.length)throw new Error("没有符合条件的题目");\n  const p=await api("/teacher/papers",{method:"POST",body:JSON.stringify({title:$("#at").value,grade,subject,textbook,unit,question_ids:ids})});\n  await api("/teacher/assignments",{method:"POST",body:JSON.stringify({title:$("#at").value,class_id,paper_id:p.id,due_date:$("#ad").value||new Date(Date.now()+7*86400000).toISOString().slice(0,10)})});\n  closeModal();toast("作业已布置");go("papers")\n }catch(e){toast(e.message)}};\n}\nasync function submissionList(id){\n const rows=await api(`/teacher/assignments/${id}/submissions`);\n const done=rows.filter(r=>r.completed).length,pending=rows.length-done,overdue=rows.filter(r=>r.statusCode==="overdue").length,late=rows.filter(r=>r.statusCode==="late_completed").length;\n modal("作业完成情况",rows.length?`<div class="note" style="margin-bottom:12px">已完成 ${done} 人 · 未完成 ${pending} 人${overdue?` · 逾期未交 ${overdue} 人`:""}${late?` · 逾期完成 ${late} 人`:""} <button class="btn secondary small" id="modalExport" style="margin-left:8px">导出成绩</button></div><div class="table-wrap"><table class="table"><thead><tr><th>学生</th><th>状态</th><th>分数</th><th>正确</th><th>提交时间</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.studentName)}</td><td><span class="badge ${statusClass(r.statusCode)}">${r.status}</span></td><td>${r.completed?`<b>${r.score}</b>`:"—"}</td><td>${r.completed?`${r.correct}/${r.total}`:"—"}</td><td>${r.submittedAt?esc(r.submittedAt.slice(0,16).replace("T"," ")):"—"}</td></tr>`).join("")}</tbody></table></div>`:"<div class=\'empty\'>班级暂无学生</div>");\n if($("#modalExport"))$("#modalExport").onclick=async()=>{try{await downloadWithAuth(`/teacher/assignments/${id}/export.xlsx`,`作业成绩_${id}.xlsx`);toast("成绩报表已导出")}catch(e){toast(e.message)}};\n}\nasync function analytics(){\n const d=await api("/teacher/analytics");\n $("#page").innerHTML=head("学情分析","班级平均分、知识点正确率与薄弱学生")+\n `<div class="grid4">${stat(d.avgScore,"平均分")}${stat(d.avgAccuracy+"%","正确率")}${stat(d.completionRate+"%","作业完成率")}${stat(d.pendingSubmissions,"未交份数")}</div>\n <div class="section card"><h2>班级表现</h2>${d.classStats.length?`<div class="table-wrap"><table class="table"><thead><tr><th>班级</th><th>平均分</th><th>正确率</th><th>完成率</th><th>未交</th></tr></thead><tbody>${d.classStats.map(c=>`<tr><td><b>${esc(c.className)}</b><br><small class="muted">${c.grade}年级 · ${c.students}人 · ${c.assignments}份作业</small></td><td>${c.avgScore}</td><td>${c.accuracy}%</td><td>${c.completionRate}%</td><td>${c.pendingSubmissions}</td></tr>`).join("")}</tbody></table></div>`:"<span class=\'muted\'>暂无班级作业数据</span>"}</div>\n <div class="section grid2"><div class="card"><h2>知识点正确率</h2><div class="knowledge">${d.knowledge.map(k=>`<div class="knowledge-row"><small>${esc(k.knowledge)}</small><div class="knowledge-meter"><i style="width:${k.accuracy}%"></i></div><b>${k.accuracy}%</b></div>`).join("")||"<span class=\'muted\'>暂无答题数据</span>"}</div></div>\n <div class="card"><h2>薄弱学生</h2><div class="list">${d.weakStudents.map(s=>`<div class="item"><div class="item-main"><b>${esc(s.studentName)}</b><small>${esc(s.className)} · 平均 ${s.avgScore}分 · 已交 ${s.completed}/${s.assigned}</small></div><div class="actions"><span class="badge ${s.pending?"red":""}">${s.pending?`未交${s.pending}`:`${s.avgScore}分`}</span><button class="btn secondary small weakGrowthProfile" data-id="${s.studentID}" data-name="${esc(s.studentName)}">成长档案</button></div></div>`).join("")||"<span class=\'muted\'>暂无需要重点关注的学生</span>"}</div></div></div>`;\n $$(".weakGrowthProfile").forEach(b=>b.onclick=()=>openStudentGrowthProfile(+b.dataset.id,null,b.dataset.name));\n}\nasync function audit(){\n const rows=await api("/teacher/audit-logs?limit=200");\n $("#page").innerHTML=head("操作记录","中文可读的关键教学管理操作")+`<div class="filters"><input id="teacherAuditSearch" placeholder="搜索操作内容"><select id="teacherAuditType"><option value="">全部类型</option>${[...new Set(rows.map(x=>x.actionName))].map(x=>`<option>${esc(x)}</option>`).join("")}</select></div><div class="card"><div class="list" id="teacherAuditList"></div></div>`;\n function draw(){const q=$("#teacherAuditSearch").value.trim().toLowerCase(),t=$("#teacherAuditType").value;const xs=rows.filter(x=>(!q||(x.summary||"").toLowerCase().includes(q))&&(!t||x.actionName===t));$("#teacherAuditList").innerHTML=xs.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.actionName||x.action)}</b><small>${esc((x.createdAt||"").slice(0,16).replace("T"," "))} · ${esc(x.summary||x.detail||"")}</small></div></div>`).join("")||"<div class=\'empty\'>没有匹配记录</div>"}$("#teacherAuditSearch").oninput=draw;$("#teacherAuditType").onchange=draw;draw();\n}\nasync function leaderboard(){\n state.rankMode=state.rankMode||"points";state.rankDays=state.rankDays||7;\n const teacherRole=state.user?.role==="teacher";\n let classes=[];if(teacherRole)classes=await api("/teacher/classes");\n if(teacherRole&&!classes.length){$("#page").innerHTML=head("班级排行榜","暂无班级")+empty("请先创建班级");return}\n const cid=teacherRole?(state.rankClassID&&classes.some(x=>x.id===state.rankClassID)?state.rankClassID:classes[0].id):null;if(cid)state.rankClassID=cid;\n let study=[],points={ranking:[],class:null};\n if(state.rankMode==="study")study=await api("/leaderboard");\n else points=await api(`/points/leaderboard?days=${state.rankDays}${cid?`&class_id=${cid}`:""}`);\n const actions=`<button id="rankPoints" class="btn ${state.rankMode==="points"?"primary":"secondary"}">课堂积分榜</button><button id="rankStudy" class="btn ${state.rankMode==="study"?"primary":"secondary"}">学习成绩榜</button>`;\n const filters=state.rankMode==="points"?`<div class="filters">${teacherRole?`<select id="rankClass">${classes.map(c=>`<option value="${c.id}" ${c.id===cid?"selected":""}>${esc(c.name)}</option>`).join("")}</select>`:""}<select id="rankDays"><option value="7" ${state.rankDays==7?"selected":""}>近7天</option><option value="30" ${state.rankDays==30?"selected":""}>近30天</option><option value="90" ${state.rankDays==90?"selected":""}>近90天</option></select></div>`:"";\n const body=state.rankMode==="points"?`<div class="card table-wrap"><table class="table"><thead><tr><th>排名</th><th>学生</th><th>净表现</th><th>发放积分</th><th>活动</th><th>守纪</th><th>可用积分</th></tr></thead><tbody>${(points.ranking||[]).map((r,i)=>`<tr><td class="${i===0?"rank1":""}">${r.rank}</td><td>${esc(r.studentName)}</td><td><b>${r.net}</b></td><td>${r.issued}</td><td>${r.activity}</td><td>${r.discipline}</td><td>${r.available}</td></tr>`).join("")||`<tr><td colspan="7" class="empty">暂无积分数据</td></tr>`}</tbody></table></div>`:`<div class="card table-wrap"><table class="table"><thead><tr><th>排名</th><th>学生</th><th>班级</th><th>平均分</th><th>提交次数</th></tr></thead><tbody>${study.map((r,i)=>`<tr><td class="${i===0?"rank1":""}">${i+1}</td><td>${esc(r.studentName)}</td><td>${esc(r.className)}</td><td><b>${r.avgScore}</b></td><td>${r.submissions}</td></tr>`).join("")||`<tr><td colspan="5" class="empty">暂无成绩数据</td></tr>`}</tbody></table></div>`;\n $("#page").innerHTML=head("班级排行榜",state.rankMode==="points"?"按净表现优先排列，发放积分作为次级排序": "按最近累计答题成绩计算",actions)+filters+body;\n $("#rankPoints").onclick=()=>{state.rankMode="points";leaderboard()};$("#rankStudy").onclick=()=>{state.rankMode="study";leaderboard()};if($("#rankClass"))$("#rankClass").onchange=()=>{state.rankClassID=+$("#rankClass").value;leaderboard()};if($("#rankDays"))$("#rankDays").onchange=()=>{state.rankDays=+$("#rankDays").value;leaderboard()};\n}\n\n// Student\nasync function student(){\n const [as,p]=await Promise.all([api("/student/assignments"),api("/student/progress")]);\n const pending=as.filter(a=>!a.completed),overdue=pending.filter(a=>a.statusCode==="overdue").length;\n $("#page").innerHTML=head("学习首页",`${esc(state.user.name)}，今天继续加油`)+\n `<div class="hero"><h2>今日学习</h2><p>完成老师布置的作业，并针对薄弱知识点进行专项练习。</p><button id="goPractice" class="btn secondary">开始自主练习</button></div>\n <div class="section grid4">${stat(pending.length,"待完成")}${stat(overdue,"逾期未交")}${stat(p.avgScore,"平均分")}${stat(p.totalAnswered,"累计答题")}</div>\n <div class="section"><h2>待完成作业</h2><div class="list">${pending.map(a=>`<div class="item"><div class="item-main"><b>${esc(a.title)}</b><small>${esc(a.paper?.subject||"")} · 截止 ${esc(a.dueDate)}</small></div><div class="actions"><span class="badge ${statusClass(a.statusCode)}">${a.status}</span><button class="btn primary small doA" data-id="${a.id}">${a.overdue?"补交":"开始"}</button></div></div>`).join("")||"<div class=\'card empty\'>当前没有待完成作业</div>"}</div></div>`;\n $("#goPractice").onclick=()=>go("practice");$$(".doA").forEach(b=>b.onclick=()=>startAssignment(+b.dataset.id));\n}\n\nasync function rewards(){\n const [shop,p]=await Promise.all([api("/student/rewards"),api("/student/points")]);const s=shop.summary;\n const w=p.weekly||{};\n const badgeHtml=(p.badges||[]).map(x=>`<span class="badge green">${esc(x.icon)} ${esc(x.name)}</span>`).join("")||`<span class="muted">本周暂无成长徽章</span>`;\n const adviceHtml=(p.growthAdvice||[]).map(x=>`<div class="item"><div class="item-main"><small>${esc(x)}</small></div></div>`).join("");\n const rewardRecords=[...(p.redemptions||[]).map(x=>({...x,recordType:"redemption",sortTime:x.requestedAt||""})),...(p.autoRewards||[]).map(x=>({...x,recordType:"auto",sortTime:x.createdAt||""}))].sort((a,b)=>String(b.sortTime||"").localeCompare(String(a.sortTime||"")));\n const rewardRows=rewardRecords.map(x=>{if(x.recordType==="auto"){const label=x.status==="pending"?"待发放":x.status==="fulfilled"?"已发放":"已取消",cls=x.status==="fulfilled"?"green":x.status==="canceled"?"red":"amber";return `<div class="item"><div class="item-main"><b>${esc(x.rewardIcon||"🎁")} ${esc(x.rewardName)}</b><small>自动奖励 · ${esc(x.ruleName||"自动奖励")} · 不扣积分 · ${esc(x.createdAt||"")}</small></div><span class="badge ${cls}">${label}</span></div>`}const label=x.status==="pending"?"待领取":x.status==="fulfilled"?"已领取":"已退回",cls=x.status==="fulfilled"?"green":x.status==="rejected"?"red":"amber";return `<div class="item"><div class="item-main"><b>${esc(x.icon)} ${esc(x.rewardName)}</b><small>积分兑换 · ${x.costPoints}积分 · ${esc(x.requestedAt||"")}</small></div><span class="badge ${cls}">${label}</span></div>`}).join("")||`<span class="muted">暂无奖励记录</span>`;\n $("#page").innerHTML=head("积分奖励","课堂表现积分、奖励商城与奖励记录；自动奖励不扣积分")+`<div class="grid4">${stat(s.available,"可用积分")}${stat(s.earned,"累计发放")}${stat(s.activity,"课堂活动")}${stat(s.discipline,"守纪积分")}</div><div class="section card"><h2>我的本周表现</h2><div class="grid4">${stat(w.earned||0,"本周发放")}${stat(w.net||0,"本周净表现")}${stat(w.activity||0,"本周活动")}${stat(w.discipline||0,"本周守纪")}</div><p class="muted" style="margin-bottom:0">本周自动奖励 ${w.autoRewardCount||0} 次 · 积分兑换 ${w.redemptionCount||0} 次</p></div><div class="section card"><h2>成长徽章</h2><div class="status-line">${badgeHtml}</div></div><div class="section card"><h2>近4周成长趋势</h2>${pointTrendHTML(p.trend||[])}</div>${adviceHtml?`<div class="section card"><h2>成长建议</h2><div class="list">${adviceHtml}</div></div>`:""}<div class="section"><h2>奖励商城</h2><div class="reward-grid">${shop.rewards.map(x=>`<div class="card reward-card"><div class="reward-icon">${esc(x.icon)}</div><h2>${esc(x.name)}</h2><p class="muted">${esc(x.description||"")}</p><div class="status-line"><span class="badge">${x.costPoints}积分</span><span class="badge">${x.unlimitedStock?"不限库存":"剩余 "+x.stock}</span>${x.perStudentLimit?`<span class="badge">限兑 ${x.perStudentLimit} 次</span>`:""}</div><button class="btn ${x.available&&s.available>=x.costPoints?"primary":"secondary"} full redeemReward" data-id="${x.id}" data-name="${esc(x.name)}" data-cost="${x.costPoints}" ${x.available&&s.available>=x.costPoints?"":"disabled"}>${!x.available?"暂不可兑":s.available<x.costPoints?"积分不足":"兑换"}</button></div>`).join("")||empty("管理员尚未上架奖品")}</div></div><div class="section card"><h2>我的奖励记录</h2><div class="list">${rewardRows}</div></div><div class="section card"><h2>积分流水</h2><div class="list">${p.ledger.slice(0,40).map(x=>`<div class="item ledger-row"><div><b>${esc(x.reason||"积分记录")}</b><small>${esc(x.createdAt||"")} ${x.note?"· "+esc(x.note):""}</small></div><b class="${x.points>0?"point-positive":"point-negative"}">${x.points>0?"+":""}${x.points}</b></div>`).join("")||`<span class="muted">暂无积分记录</span>`}</div></div>`;\n $$(\'.redeemReward\').forEach(b=>b.onclick=async()=>{const name=b.dataset.name,cost=+b.dataset.cost;if(!confirm(`确定用 ${cost} 积分兑换“${name}”吗？兑换后进入待领取状态。`))return;try{await api(`/student/rewards/${+b.dataset.id}/redeem`,{method:"POST",body:JSON.stringify({note:""})});toast("兑换成功，请等待领取");rewards()}catch(e){toast(e.message)}});\n}\n\nasync function assignments(){\n const as=await api("/student/assignments");\n $("#page").innerHTML=head("我的作业","正式作业由服务器判分；逾期后仍可补交并保留逾期标记")+\n `<div class="list">${as.map(a=>`<div class="item"><div class="item-main"><b>${esc(a.title)}</b><small>${esc(a.assignedClassName||"")} · ${esc(a.paper?.textbook||"")} · ${esc(a.paper?.unit||"综合")} · 截止 ${esc(a.dueDate)}${a.completed?` · 成绩 ${a.score}分`:""}</small></div><div class="actions"><span class="badge ${statusClass(a.statusCode)}">${a.status}</span>${a.completed?`<button class="btn secondary small" disabled>已提交</button>`:`<button class="btn primary small doA" data-id="${a.id}">${a.overdue?"补交":"开始答题"}</button>`}</div></div>`).join("")||"<div class=\'card empty\'>暂无作业</div>"}</div>`;\n $$(".doA").forEach(b=>b.onclick=()=>startAssignment(+b.dataset.id));\n}\nasync function practice(){\n const qs=state.offline?offlineBank:await api("/questions");\n $("#page").innerHTML=head(state.offline?"离线练习":"自主练习","按教材和知识点选择练习内容")+\n `<div class="card"><div class="form-grid">\n <div><label>年级</label><select id="pg">${[1,2,3,4,5,6].map(x=>`<option ${x==3?"selected":""}>${x}</option>`).join("")}</select></div>\n <div><label>科目</label><select id="ps"><option>数学</option><option>语文</option><option>英语</option></select></div>\n <div><label>教材</label><select id="pb"><option value="">全部</option>${[...new Set(qs.map(q=>q.textbook))].map(x=>`<option>${esc(x)}</option>`).join("")}</select></div>\n <div><label>题量</label><select id="pn"><option>5</option><option>10</option><option>15</option></select></div>\n </div><button class="btn primary full" id="startP">开始练习</button></div>`;\n $("#startP").onclick=()=>{\n  const g=+$("#pg").value,s=$("#ps").value,b=$("#pb").value,n=+$("#pn").value;\n  let list=qs.filter(q=>q.grade===g&&q.subject===s&&(!b||q.textbook===b));if(!list.length&&state.offline)list=qs;\n  startQuiz(list.sort(()=>Math.random()-.5).slice(0,n),`${g}年级${s}练习`,null);\n };\n}\nasync function startAssignment(id){\n const as=await api("/student/assignments"),a=as.find(x=>x.id===id);if(!a)return;\n const qs=await api(`/papers/${a.paperID}/questions`);startQuiz(qs,a.title,id)\n}\nfunction startQuiz(qs,title,aid){\n if(!qs.length){toast("没有可用题目");return}\n let i=0,sel=null,done=false,correct=0,answers=[];\n const onlineServerGraded=!state.offline;\n const render=()=>{\n  const q=qs[i];\n  $("#page").innerHTML=head(title,`第 ${i+1}/${qs.length} 题${onlineServerGraded?" · 服务器判分":""}`,`<button class="btn secondary" id="quitQuiz">退出</button>`)+\n  `<div class="card"><div class="progress"><i style="width:${pct(i+(done?1:0),qs.length)}%"></i></div>\n  <div style="margin-top:12px"><span class="badge">${esc(q.textbook)} · ${esc(q.unit)} · ${esc(q.knowledge)}</span></div>\n  <div class="question">${esc(q.text)}</div>\n  ${q.options.map((o,n)=>`<button class="option ${sel===n?"selected":""} ${!onlineServerGraded&&done&&n===q.correctIndex?"correct":""} ${!onlineServerGraded&&done&&sel===n&&n!==q.correctIndex?"wrong":""}" data-i="${n}"><span class="letter">${String.fromCharCode(65+n)}</span>${esc(o)}</button>`).join("")}\n  ${!onlineServerGraded&&done?`<div class="answer"><b>${sel===q.correctIndex?"✅ 正确":"❌ 错误"}</b><br>正确答案：${esc(q.options[q.correctIndex])}<br><span class="muted">${esc(q.explanation)}</span></div>`:""}\n  ${onlineServerGraded&&aid?`<div class="note">正式作业不会在提交前显示正确答案或解析。</div>`:""}\n  <button id="quizNext" class="btn primary full" ${sel===null&&!done?"disabled":""}>${onlineServerGraded?(i===qs.length-1?"提交整份答卷":"保存并下一题"):(done?(i===qs.length-1?"完成练习":"下一题"):"提交答案")}</button></div>`;\n  $("#quitQuiz").onclick=()=>go(aid?"assignments":"practice");\n  $$(".option").forEach(b=>b.onclick=()=>{if(done&&!onlineServerGraded)return;sel=+b.dataset.i;render()});\n  $("#quizNext").onclick=async()=>{\n   if(onlineServerGraded){\n    answers.push({question_id:q.id,selected_index:sel});\n    if(i<qs.length-1){i++;sel=null;render();return}\n    try{\n     const r=aid?await api(`/student/assignments/${aid}/submit`,{method:"POST",body:JSON.stringify({answers})}):await api("/student/practice-submit",{method:"POST",body:JSON.stringify({title,answers})});\n     $("#page").innerHTML=head(aid?"作业已提交":"练习完成",title)+`<div class="card empty"><div style="font-size:62px">🏆</div><h1 style="color:var(--primary)">${r.score}分</h1><p>答对 ${r.correct} 题，答错 ${r.total-r.correct} 题</p>${aid?"<p class=\'muted\'>成绩已回传教师端。</p>":""}<button id="backQuiz" class="btn primary">返回</button></div>`;\n     $("#backQuiz").onclick=()=>go(aid?"assignments":"practice");\n    }catch(e){answers.pop();toast(e.message)}\n    return\n   }\n   if(!done){done=true;const ok=sel===q.correctIndex;if(ok)correct++;answers.push({question_id:q.id,selected_index:sel,correct:ok});render();return}\n   if(i<qs.length-1){i++;sel=null;done=false;render();return}\n   const score=pct(correct,qs.length);\n   $("#page").innerHTML=head("练习完成",title)+`<div class="card empty"><div style="font-size:62px">🏆</div><h1 style="color:var(--primary)">${score}分</h1><p>答对 ${correct} 题，答错 ${qs.length-correct} 题</p><button id="backQuiz" class="btn primary">返回</button></div>`;\n   $("#backQuiz").onclick=()=>go("practice")\n  };\n };render()\n}\nasync function progress(){\n const p=await api("/student/progress");\n $("#page").innerHTML=head("我的学情","查看成绩趋势和薄弱知识点")+\n `<div class="grid3">${stat(p.avgScore,"平均分")}${stat(p.totalAnswered,"累计答题")}${stat(p.submissions,"练习次数")}</div>\n <div class="section card"><h2>知识点掌握</h2><div class="knowledge">${p.knowledge.map(k=>`<div class="knowledge-row"><small>${esc(k.knowledge)}</small><div class="knowledge-meter"><i style="width:${k.accuracy}%"></i></div><b>${k.accuracy}%</b></div>`).join("")||"<span class=\'muted\'>暂无数据</span>"}</div></div>\n <div class="section"><button id="goRewardsFromProgress" class="btn secondary full">查看课堂积分与奖励</button></div>`;\n if($("#goRewardsFromProgress"))$("#goRewardsFromProgress").onclick=()=>go("rewards");\n}\n\n// Parent\nasync function parent(){\n const c=await api("/parent/children");\n $("#page").innerHTML=head("家长首页","查看孩子成绩、待完成和逾期作业")+\n `<div class="list">${c.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.name)}</b><small>${x.grade}年级 · ${esc(x.className||"未分班")} · 平均 ${x.avgScore}分</small><div class="status-line" style="margin-top:6px"><span class="badge">${x.pendingAssignments}份待完成</span>${x.overdueAssignments?`<span class="badge red">${x.overdueAssignments}份逾期</span>`:""}</div></div><div class="actions"><button class="btn secondary small parentProgressBtn" data-id="${x.id}">学情</button><button class="btn primary small parentAssignmentsBtn" data-id="${x.id}">作业</button></div></div>`).join("")||"<div class=\'card empty\'>尚未绑定孩子</div>"}</div>`;\n $$(".parentProgressBtn").forEach(b=>b.onclick=()=>{state.childID=+b.dataset.id;go("childProgress")});\n $$(".parentAssignmentsBtn").forEach(b=>b.onclick=()=>{state.childID=+b.dataset.id;go("childAssignments")});\n}\n\nasync function childRewards(){\n const c=await api("/parent/children");if(!c.length){$("#page").innerHTML=head("课堂表现","暂无绑定学生")+empty("请联系教师或管理员绑定家长账号");return}\n const cid=(state.childID&&c.some(x=>x.id===state.childID))?state.childID:c[0].id;state.childID=cid;const [d,communicationHistory]=await Promise.all([api(`/parent/children/${cid}/points`),api(`/parent/children/${cid}/communication-history`).catch(()=>[])]);const s=d.summary,w=d.weekly||{};\n const badgeHtml=(d.badges||[]).map(x=>`<span class="badge green">${esc(x.icon)} ${esc(x.name)}</span>`).join("")||`<span class="muted">本周暂无成长徽章</span>`;\n const adviceHtml=(d.growthAdvice||[]).map(x=>`<div class="item"><div class="item-main"><small>${esc(x)}</small></div></div>`).join("")||`<span class="muted">暂无成长建议</span>`;\n const chooser=c.length>1?`<select id="parentPointChild" style="width:auto">${c.map(x=>`<option value="${x.id}" ${x.id===cid?"selected":""}>${esc(x.name)}</option>`).join("")}</select>`:"";\n const reasons=(w.topReasons||[]).map(x=>`<div class="item"><div><b>${esc(x.reason)}</b><small>${x.count}次</small></div><b class="${x.points>=0?"point-positive":"point-negative"}">${x.points>0?"+":""}${x.points}</b></div>`).join("")||`<span class="muted">本周暂无课堂积分记录</span>`;\n const rewardRecords=[...(d.redemptions||[]).map(x=>({...x,recordType:"redemption",sortTime:x.requestedAt||""})),...(d.autoRewards||[]).map(x=>({...x,recordType:"auto",sortTime:x.createdAt||""}))].sort((a,b)=>String(b.sortTime||"").localeCompare(String(a.sortTime||"")));\n const rewardRows=rewardRecords.map(x=>{if(x.recordType==="auto"){const label=x.status==="pending"?"待发放":x.status==="fulfilled"?"已发放":"已取消",cls=x.status==="fulfilled"?"green":x.status==="canceled"?"red":"amber";return `<div class="item"><div class="item-main"><b>${esc(x.rewardIcon||"🎁")} ${esc(x.rewardName)}</b><small>自动奖励 · ${esc(x.ruleName||"自动奖励")} · 不扣积分 · ${esc(x.createdAt||"")}</small></div><span class="badge ${cls}">${label}</span></div>`}const label=x.status==="pending"?"待领取":x.status==="fulfilled"?"已领取":"已退回",cls=x.status==="fulfilled"?"green":x.status==="rejected"?"red":"amber";return `<div class="item"><div class="item-main"><b>${esc(x.icon)} ${esc(x.rewardName)}</b><small>积分兑换 · ${x.costPoints}积分 · ${esc(x.requestedAt||"")}</small></div><span class="badge ${cls}">${label}</span></div>`}).join("")||`<span class="muted">暂无奖励记录</span>`;\n const weeklyText=`${d.student.name}近7天课堂周报：本周发放${w.earned||0}分，净表现${w.net||0}分，课堂活动${w.activity||0}分，守纪${w.discipline||0}分，自动奖励${w.autoRewardCount||0}次，积分兑换${w.redemptionCount||0}次。当前可用积分${s.available}分。`;\n const communicationRows=(communicationHistory||[]).map(x=>`<div class="item"><div class="item-main"><b>💬 ${esc(x.typeName||"家长沟通")}</b><small>${esc(x.createdAt||"")} · ${esc(x.actorName||"教师")}<br>${esc(x.content||"")}</small></div></div>`).join("")||`<span class="muted">暂无家校沟通记录</span>`;\n $("#page").innerHTML=head(`${esc(d.student.name)}的课堂表现`,"课堂积分、每周表现与奖励记录",chooser)+`<div class="grid4">${stat(s.available,"可用积分")}${stat(s.earned,"累计发放")}${stat(s.activity,"课堂活动")}${stat(s.discipline,"守纪积分")}</div><div class="section card"><div style="display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap"><h2 style="margin:0">近7天课堂周报</h2><div class="actions"><button id="shareWeekly" class="btn secondary small">分享周报</button><button id="exportParentWeekly" class="btn secondary small">导出周报</button></div></div><div class="grid4" style="margin-top:12px">${stat(w.earned||0,"本周发放")}${stat(w.net||0,"净表现")}${stat(w.activity||0,"活动积分")}${stat(w.discipline||0,"守纪积分")}</div><div class="section"><h2>主要表现</h2><div class="list">${reasons}</div></div><p class="muted">本周自动奖励 ${w.autoRewardCount||0} 次 · 积分兑换 ${w.redemptionCount||0} 次 · 使用 ${w.redeemedPoints||0} 积分</p></div><div class="section grid2"><div class="card"><h2>成长徽章</h2><div class="status-line">${badgeHtml}</div></div><div class="card"><h2>成长建议</h2><div class="list">${adviceHtml}</div></div></div><div class="section card"><h2>近4周成长趋势</h2>${pointTrendHTML(d.trend||[])}</div><div class="section card"><h2>最近课堂表现</h2><div class="list">${d.ledger.slice(0,50).map(x=>`<div class="item ledger-row"><div><b>${esc(x.reason||"积分记录")}</b><small>${esc(x.createdAt||"")} ${x.note?"· "+esc(x.note):""}</small></div><b class="${x.points>0?"point-positive":"point-negative"}">${x.points>0?"+":""}${x.points}</b></div>`).join("")||`<span class="muted">暂无积分记录</span>`}</div></div><div class="section card"><h2>奖励记录</h2><div class="list">${rewardRows}</div></div><div class="section card"><h2>家校沟通记录</h2><div class="note" style="margin-bottom:10px">仅展示教师明确标记为“家长沟通”的记录。</div><div class="list">${communicationRows}</div></div>`;\n if($("#parentPointChild"))$("#parentPointChild").onchange=()=>{state.childID=+$("#parentPointChild").value;childRewards()};\n $("#shareWeekly").onclick=async()=>{try{if(navigator.share){await navigator.share({title:`${d.student.name}课堂周报`,text:weeklyText})}else if(navigator.clipboard){await navigator.clipboard.writeText(weeklyText);toast("周报摘要已复制")}else{prompt("复制周报摘要",weeklyText)}}catch(e){if(e?.name!=="AbortError")toast("分享未完成")}};\n $("#exportParentWeekly").onclick=async()=>{try{await downloadWithAuth(`/parent/children/${cid}/points-weekly.xlsx?days=7`,`${d.student.name}_近7天课堂周报.xlsx`);toast("家长周报已导出")}catch(e){toast(e.message)}};\n}\n\nasync function childProgress(){\n const c=await api("/parent/children");\n if(!c.length){$("#page").innerHTML=head("孩子学情","暂无绑定学生")+empty("请联系教师或管理员绑定家长账号");return}\n const cid=(state.childID&&c.some(x=>x.id===state.childID))?state.childID:c[0].id;state.childID=cid;\n const p=await api(`/parent/children/${cid}/progress`);\n const chooser=c.length>1?`<select id="parentChildSelect" style="width:auto">${c.map(x=>`<option value="${x.id}" ${x.id===cid?"selected":""}>${esc(x.name)}</option>`).join("")}</select>`:"";\n $("#page").innerHTML=head(`${esc(p.studentName)}的学情`,`${p.grade}年级 · ${esc(p.className||"未分班")} · 最近学习概况`,chooser)+\n `<div class="grid3">${stat(p.avgScore,"平均分")}${stat(p.totalAnswered,"累计答题")}${stat(p.submissions,"练习次数")}</div>\n <div class="section card"><h2>薄弱知识点</h2><div class="knowledge">${p.knowledge.map(k=>`<div class="knowledge-row"><small>${esc(k.knowledge)}</small><div class="knowledge-meter"><i style="width:${k.accuracy}%"></i></div><b>${k.accuracy}%</b></div>`).join("")||"<span class=\'muted\'>暂无数据</span>"}</div></div>\n <div class="section card"><h2>班级历程</h2><div class="list">${(p.classHistory||[]).map(x=>`<div class="item"><div class="item-main"><b>${esc(x.className)}</b><small>${(x.joinedAt||"").slice(0,10)} → ${x.current?"当前":(x.leftAt||"").slice(0,10)} · ${esc(x.current?"在读":x.leaveReasonName)}</small></div></div>`).join("")||"<span class=\'muted\'>暂无班级历史</span>"}</div></div>`;\n if($("#parentChildSelect"))$("#parentChildSelect").onchange=()=>{state.childID=+$("#parentChildSelect").value;childProgress()};\n}\nasync function childAssignments(){\n const c=await api("/parent/children");\n if(!c.length){$("#page").innerHTML=head("孩子作业","暂无绑定学生")+empty("请联系教师或管理员绑定家长账号");return}\n const cid=(state.childID&&c.some(x=>x.id===state.childID))?state.childID:c[0].id;state.childID=cid;\n const child=c.find(x=>x.id===cid),rows=await api(`/parent/children/${cid}/assignments`);\n const chooser=c.length>1?`<select id="parentAssignmentChild" style="width:auto">${c.map(x=>`<option value="${x.id}" ${x.id===cid?"selected":""}>${esc(x.name)}</option>`).join("")}</select>`:"";\n $("#page").innerHTML=head(`${esc(child?.name||"孩子")}的作业`,"只读查看作业完成与逾期状态",chooser)+\n `<div class="list">${rows.map(a=>`<div class="item"><div class="item-main"><b>${esc(a.title)}</b><small>${esc(a.assignedClassName||"")} · ${esc(a.subject||"")} · 截止 ${esc(a.dueDate)}${a.score!==null?` · ${a.score}分`:""}</small></div><span class="badge ${statusClass(a.statusCode)}">${a.status}</span></div>`).join("")||"<div class=\'card empty\'>暂无作业</div>"}</div>`;\n if($("#parentAssignmentChild"))$("#parentAssignmentChild").onchange=()=>{state.childID=+$("#parentAssignmentChild").value;childAssignments()};\n}\nasync function account(){\n let deletion=null;if(!state.offline){try{deletion=(await api("/account/deletion-request")).request}catch(_){}}\n const deletionBlock=state.offline?`<p class="muted">离线体验不连接服务器，不提供账号数据导出或注销。</p>`:(deletion?.status==="pending"?`<div class="note">注销申请已提交：${esc(deletion.requestedAt||"")}。管理员处理前可以取消。</div><button id="cancelDeletion" class="btn secondary full">取消注销申请</button>`:(state.user?.role==="admin"?`<div class="note">管理员账号需要先移交管理权限，再进行注销。</div>`:`<button id="requestDeletion" class="btn danger full">申请注销账号</button>`));\n $("#page").innerHTML=head("我的","账号、安全、隐私与客户端设置")+\n `<div class="grid2"><div class="card"><h2>${esc(state.user?.name||"离线学生")}</h2><p class="muted">${state.offline?"离线体验":roleName(state.user?.role)}</p></div>\n <div class="card"><h2>服务器</h2><input id="accountURL" value="${esc(state.api)}" ${state.offline?"disabled":""}><button id="saveURL" class="btn secondary full" ${state.offline?"disabled":""}>保存</button></div></div>\n <div class="section card"><h2>修改密码</h2><label>当前密码</label><input id="oldPwd" type="password"><label>新密码</label><input id="newPwd" type="password" placeholder="至少8位，包含字母和数字"><label>确认新密码</label><input id="newPwd2" type="password"><button id="changePwdBtn" class="btn primary full">修改密码</button></div>\n <div class="section card"><h2>隐私与个人数据</h2><div class="actions"><button id="privacyPolicy" class="btn secondary">隐私政策</button><button id="termsPolicy" class="btn secondary">用户协议</button>${state.offline?"":`<button id="exportMyData" class="btn secondary">导出我的数据</button>`}</div><div style="margin-top:12px">${deletionBlock}</div></div>\n <div class="section card"><h2>登录会话</h2><p class="muted">${state.offline?"离线模式":(state.remember?"个人设备：保持登录约30天":"共享设备模式：仅当前浏览器会话")}</p>${state.offline?"":`<button id="accountLogoutBtn" class="btn secondary full">退出登录</button>`}</div>\n <div class="section card"><h2>网页版运行</h2><div class="app-runtime"><span class="badge">${clientModeLabel()}</span><span class="badge ${navigator.onLine!==false?"green":"amber"}">${navigator.onLine!==false?"网络在线":"当前离线"}</span></div><div class="actions"><button id="installAppBtn" class="btn secondary">添加主屏幕（可选）</button></div><p class="muted install-help">长缨辅学以网页版为正式主版本。${installHelpText()} 主屏幕入口仅作为访问快捷方式，核心教学功能需要联网使用。</p></div>\n <div class="section note safe-bottom">V9.2.5 商业版 C2.5：新增订单与收费台账、应收/实收、分次收款、退款/作废和运营收入统计。</div>`;\n if($("#saveURL"))$("#saveURL").onclick=()=>{state.api=$("#accountURL").value.trim().replace(/\\/$/,"");localStorage.setItem("v6Server",state.api);toast("已保存")};\n if($("#accountLogoutBtn"))$("#accountLogoutBtn").onclick=logout;\n if($("#installAppBtn"))$("#installAppBtn").onclick=promptInstall;\n if($("#notificationBtn"))$("#notificationBtn").onclick=requestNotificationPermission;\n if($("#privacyPolicy"))$("#privacyPolicy").onclick=()=>window.open(state.api+"/legal/privacy","_blank","noopener");\n if($("#termsPolicy"))$("#termsPolicy").onclick=()=>window.open(state.api+"/legal/terms","_blank","noopener");\n if($("#exportMyData"))$("#exportMyData").onclick=async()=>{try{await downloadWithAuth("/account/export.json","my-data-v920.json");toast("个人数据已导出")}catch(e){toast(e.message)}};\n if($("#requestDeletion"))$("#requestDeletion").onclick=()=>{modal("申请注销账号",`<div class="note">提交后账号暂不会立即删除。学校管理员会根据账号归属和教学档案保存要求处理；批准后账号将停用并使现有登录失效。</div><label>注销原因（可选）</label><textarea id="deleteReason" placeholder="例如：不再使用该账号"></textarea><button id="confirmDeletion" class="btn danger full">提交注销申请</button>`);setTimeout(()=>{$("#confirmDeletion").onclick=async()=>{try{await api("/account/deletion-request",{method:"POST",body:JSON.stringify({reason:$("#deleteReason").value})});closeModal();toast("注销申请已提交");account()}catch(e){toast(e.message)}}},0)};\n if($("#cancelDeletion"))$("#cancelDeletion").onclick=async()=>{if(!confirm("确定取消当前注销申请？"))return;try{await api("/account/deletion-request/cancel",{method:"POST",body:"{}"});toast("注销申请已取消");account()}catch(e){toast(e.message)}};\n if($("#changePwdBtn"))$("#changePwdBtn").onclick=async()=>{const old=$("#oldPwd").value,n=$("#newPwd").value,n2=$("#newPwd2").value;if(n!==n2){toast("两次新密码不一致");return}try{const r=await api("/change-password",{method:"POST",body:JSON.stringify({current_password:old,new_password:n,remember:state.remember})});if(r.token){state.token=r.token;saveAuth()}toast("密码修改成功");$("#oldPwd").value=$("#newPwd").value=$("#newPwd2").value=""}catch(e){toast(e.message)}};\n}\n\n\nfunction passwordOK(p){return p.length>=8 && /[A-Za-z]/.test(p) && /\\d/.test(p)}\nasync function forcePassword(){\n $("#page").innerHTML=head("首次登录安全设置","请先把初始密码修改成你自己的密码")+\n `<div class="card" style="max-width:620px;margin:auto">\n   <div class="note">新密码至少 8 位，并同时包含字母和数字。修改完成后才能进入系统。</div>\n   <label>当前初始密码</label><input id="fpOld" type="password">\n   <label>新密码</label><input id="fpNew" type="password" placeholder="例如 School2026!">\n   <label>再次输入新密码</label><input id="fpNew2" type="password">\n   <button id="fpSave" class="btn primary full">保存新密码并进入系统</button>\n </div>`;\n $("#fpSave").onclick=async()=>{\n   const old=$("#fpOld").value,n=$("#fpNew").value,n2=$("#fpNew2").value;\n   if(n!==n2){toast("两次新密码不一致");return}\n   if(!passwordOK(n)){toast("新密码至少8位，并同时包含字母和数字");return}\n   try{\n     const r=await api("/change-password",{method:"POST",body:JSON.stringify({current_password:old,new_password:n,remember:state.remember})});\n     if(r.token)state.token=r.token;\n     state.user.mustChangePassword=false;\n     saveAuth();\n     toast("密码修改成功");\n     go(({admin:"admin",teacher:"teacher",student:"student",parent:"parent"})[state.user.role]||"account");\n   }catch(e){toast(e.message)}\n };\n}\nfunction resetPasswordForm(id,name){\n modal("重置密码",`<p>为 <b>${esc(name)}</b> 设置临时密码。用户下次登录必须修改。</p>\n <label>临时密码</label><input id="tempPwd" type="password" placeholder="至少8位，包含字母和数字">\n <button id="saveResetPwd" class="btn primary full">确认重置</button>`);\n $("#saveResetPwd").onclick=async()=>{\n   try{\n     await api(`/admin/users/${id}/reset-password`,{method:"POST",body:JSON.stringify({new_password:$("#tempPwd").value})});\n     closeModal();toast("密码已重置，状态已改为待修改");go("users");\n   }catch(e){toast(e.message)}\n };\n}\n\nasync function validateSavedSession(){\n if(!state.token||!state.user)return false;\n if(!networkHint||navigator.onLine===false){syncNetworkUI(true);return false}\n const overlay=$("#sessionCheck");overlay.classList.remove("hidden");\n const b=$("#continueSessionBtn");if(b){b.dataset.busy="1";b.disabled=true;b.textContent="正在继续登录…"}\n try{\n   let r;\n   try{r=await fetch(state.api+"/session",{headers:{"Authorization":`Bearer ${state.token}`}});markNetwork(true)}\n   catch(e){markNetwork(false);toast(friendlyNetworkError(e));return false}\n   let d={};try{d=await r.json()}catch{}\n   if(!r.ok){\n     if(r.status===401||r.status===403){clearAuth();updateContinueSessionButton()}\n     toast(d.detail||"登录已过期，请重新登录");\n     return false;\n   }\n   state.user={id:d.userID,name:d.name,role:d.role,grade:d.grade,mustChangePassword:!!d.mustChangePassword,subscription:d.subscription||null};\n   saveAuth();enter();return true;\n }finally{\n   overlay.classList.add("hidden");\n   if(b){delete b.dataset.busy;b.disabled=false;updateContinueSessionButton()}\n }\n}\nasync function bootApp(){\n $("#serverURL").value=state.api;$("#rememberLogin").checked=state.remember;\n // V9.2.0：启动阶段只读取本地状态，不访问服务器。\n // iOS 主屏幕 App 在飞行模式下也能静默打开，不触发系统联网弹窗。\n syncNetworkUI(false);\n updateContinueSessionButton();\n}\n\n$("#serverURL").value=state.api;\n$("#loginBtn").onclick=login;\n$("#continueSessionBtn").onclick=validateSavedSession;\n$("#showPwd").onchange=()=>$("#password").type=$("#showPwd").checked?"text":"password";\n$("#offlineBtn").onclick=()=>{state.offline=true;state.user={name:"离线学生",role:"student"};enter()};\n$("#loginPrivacy").onclick=()=>loginLegal("/legal/privacy");\n$("#loginTerms").onclick=()=>loginLegal("/legal/terms");\n$("#loginInstallBtn").onclick=promptInstall;\n$("#logoutBtn").onclick=logout;\n$("#menuBtn").onclick=()=>$("#sidebar").classList.toggle("open");\n$("#modalClose").onclick=closeModal;\n$("#modal").addEventListener("close",()=>{document.body.classList.remove("modal-open");updateVisualViewport()});\ndocument.addEventListener("focusin",e=>{\n if($("#modal")?.open && e.target?.matches?.("input,textarea,select"))ensureFocusedFieldVisible(e.target);\n});\nif(window.visualViewport){\n window.visualViewport.addEventListener("resize",()=>{\n  updateVisualViewport();\n  const a=document.activeElement;\n  if($("#modal")?.open && a?.matches?.("input,textarea,select"))ensureFocusedFieldVisible(a);\n });\n window.visualViewport.addEventListener("scroll",updateVisualViewport);\n}\nwindow.addEventListener("resize",updateVisualViewport);\nupdateVisualViewport();\nasync function retireLegacyServiceWorkers(){\n try{\n   if("serviceWorker" in navigator){\n     const regs=await navigator.serviceWorker.getRegistrations();\n     await Promise.all(regs.map(r=>r.unregister()));\n   }\n   if("caches" in window){\n     const keys=await caches.keys();\n     await Promise.all(keys.filter(k=>k.startsWith("changying-fuxue-")).map(k=>caches.delete(k)));\n   }\n }catch(_){}\n}\nwindow.addEventListener("load",()=>{retireLegacyServiceWorkers()});\nsyncNetworkUI(false);syncInstallButtons();bootApp();\n\n</script>\n</body>\n</html>\n'
MANIFEST = '{\n  "name": "长缨辅学",\n  "short_name": "长缨辅学",\n  "id": "/",\n  "start_url": "/?source=pwa",\n  "scope": "/",\n  "display": "standalone",\n  "display_override": [\n    "standalone"\n  ],\n  "orientation": "any",\n  "background_color": "#f4f6fb",\n  "theme_color": "#5362e8",\n  "lang": "zh-CN",\n  "description": "长缨辅学 V9.2.4 商业版 C2.4：试用到期自动生效、续费登记、服务期延长、付款记录和商业运营工作台。",\n  "categories": [\n    "education",\n    "productivity"\n  ],\n  "icons": [\n    {\n      "src": "/icon-192.png?v=924",\n      "sizes": "192x192",\n      "type": "image/png",\n      "purpose": "any maskable"\n    },\n    {\n      "src": "/icon-512.png?v=924",\n      "sizes": "512x512",\n      "type": "image/png",\n      "purpose": "any maskable"\n    },\n    {\n      "src": "/icon.svg?v=924",\n      "sizes": "any",\n      "type": "image/svg+xml",\n      "purpose": "any"\n    }\n  ],\n  "shortcuts": [\n    {\n      "name": "我的",\n      "short_name": "我的",\n      "url": "/?page=account",\n      "icons": [\n        {\n          "src": "/icon-192.png?v=924",\n          "sizes": "192x192",\n          "type": "image/png"\n        }\n      ]\n    },\n    {\n      "name": "自主练习",\n      "short_name": "练习",\n      "url": "/?page=practice",\n      "icons": [\n        {\n          "src": "/icon-192.png?v=924",\n          "sizes": "192x192",\n          "type": "image/png"\n        }\n      ]\n    }\n  ]\n}'
ICON_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">\n<rect width="512" height="512" rx="112" fill="#5362e8"/>\n<path fill="#fff" d="M100 126c66-20 116-6 156 29v252c-41-30-92-40-156-21V126zm312 0c-66-20-116-6-156 29v252c41-30 92-40 156-21V126z"/>\n</svg>'

ICON_180_PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAALQAAAC0CAIAAACyr5FlAAABwklEQVR42u3dwRGCMBBAUXDSg4VhBdiCd8e7LdiBhUEXHvTk4AFkGLL7Xgckf5bklLbrhwamHCwB4kAciANxIA7EgTgQB+JAHCAOxIE4EAfiQByIA3EgDsQB4kAciANxIA7EgTgQB+JAHCAOxIE4EAfiQByIA3EgDsSBOEAciANxIA7EgTgQB+JAHIgDxIE4CBnH83FMsge7/dJS3aqdzqMOxFF3MQEmX2lC+LUTG0QT+PdXmtDWHTN5jkEp4lhcTLYOXGUxOZa63z7T4nIdrYbJgTgQB+JAHIgDcSAOxIE4EAeIA3EgDsSBOBAH4kAciANxgDgQB+JAHIgDcSAOxIE4EAeIA3EgDsSBOBAH4kAciANxIA4QB+JAHIgDcSAOxIE4EAfiAHEgDsSBOBAH+7HfF6m/Hpd/C/DE/OR3iSNdMRV1ECGOWXswN5rFT9jXHkHkOLYcM1E7SBfHn8Wk6mBS2/WDYzmusogDcSAOxIE4EAfiQByIA8SBOBAH4kAciANxIA7EgThAHIgDcSAOxIE4EAfiQByIA3GAOBAH4kAciANxIA7EgTgQB4gDcSAOxIE4EAfiQByIA3GAOBAH4mB1L+GqOVMw4pbwAAAAAElFTkSuQmCC')
ICON_192_PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAMAAAADACAIAAADdvvtQAAAB2ElEQVR42u3XsRWCMBRAUfCwA4PBBLACPcfeFdiAwcgWNpZQiIKYf29JRZJ3PqRsuqWAvW62AAEhIASEgEBACAgBISAQEAJCQAgIBISAEBACAgEhIASEgBAQCAgBISAEBAJCQAgIAYGAEBACQkAgIASEgBAQAgIBISAEhIBAQAgIASEgEBACQkAICASEgBAQAgIBISAEhICOMk912OO5/tqrv97Htk9CEVCgsPKbplWRo9VzOrmqIF/eqgjjoHEV+RctVkAfhhU8FNd4TKDTPe6vqTOMyW6YQAgIASEgEBACQkAICAGBgBAQAkJAICAEhIAQEAgIASEgBAQCQkAICAEhIBAQAkJACAgEhIAQEAICASEgBISAQEAICAEhIBAQAkJACAgBgYAQEAJCQCAgBISAEBAICAEhIAQEAkJA/F51/Vds+7T6fJ7qnE5ia5kCElYOoWQY0FsntK+qYUxaCRfQ+eMqQijRA/pKWJFD2VI23WIXcI1HQAgIAYGAEBACQkAgIASEgBAQCAgBISAEBAJCQAgIASEgEBACQkAICASEgBAQAgIBISAEhIBAQAgIASEgBAQCQkAICAGBgBAQAkJAICAEhIAQEAgIASEgBISAQEAICAERzhN2QTlrsibd+wAAAABJRU5ErkJggg==')
ICON_512_PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAgAAAAIACAIAAAB7GkOtAAAGWUlEQVR42u3dwQ2CQBRFUTH0QGFQAbTAnri3BTqgMKYLCzCsHJLx/3OWLkfn3RBj7Mb5fACQz9MRAAgAAAIAgAAAIAAACAAAAgCAAAAgAAAIAAACAIAAACAAAAgAAAIAgAAAIAAACAAAAgCAAAAgAAAIAAACAIAAAAgAAAIAgAAAIAAACAAAAgCAAAAgAAAIAAACAIAAACAAAAgAAAIAgAAAIAAACAAAAgCAAAAgAAAIAAACAIAAAAgAAAIAgAAAIAAACAAAAgCAAAAgAAAIAAACAIAAACAAAAgAAAIAgAAAIAAACAAAAgCAAAAgAAAIAAACAIAAACAAAAIAgAAAIAAACAAAAgCAAAAgAAAIAAACAIAAACAAAAgAAAIAgAAAIAAACAAAAgCAAAAgAAAIAAACAIAAACAAAAIAgAAAIAAACAAAAgCAAAAgAAAIAAACAIAAACAAAAgAAAIAgAAAIAAACAAAAgCAAAAgAAAIAAACAIAAACAAAAgAgAAAIAAACAAAAgCAAAAgAAAIAAACAIAAACAAAAgAAAIAgAAAIAAACAAAAgCAAAAgAAAIAAACAIAAACAAAAgAgAAAIAAACAAAAgCAAAAgAAAIAAACAIAAACAAAAgAAAIAgAAAIAAACAAAAgCAAKR27INDwOeTKnpHEOOOTUtxMth6BMBtVAVsPQLg3koC5h4BwIMCth4BQBW8yyAAqIKtRwBAFWw9AgA/bZAkmHsEADulCrYeAcCiqYKtRwAgbRVsPQIA8atg6xEAuGtPm0qCuUcAIP6Dgq1HACB+FWw9sfk/AAABAEAAABAAAGLyJTDpvF+XX+2um18m4wkAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABABAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABABAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABAEAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABAEAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABAOBC7wj+y7SU7xePfXAyNPJpRABQBWw9AkAzN1YSMPcIgFutCth6BMD9VwVbjwBAkiqsW8n5DoIAoAq2HgSAG9ZHEsw9AoCFUgVbjwBgy1TB1iMAkLwKth4BgPhVsPUIANRf0gaTYO4RAIj/oGDrEQCIXwVbT2DdOJ9OASAhfwgDIAAACAAAAgCAAAAgAAAIAAACAIAAACAAAAgAAAIAgAAAIAAACAAAAgCAAAAgAAAIAAACAIAAACAAAAgAAAIAIAAACAAAAgCAAAAgAAAIAAACAIAAACAAAAgAAAIAgAAAIAAACAAAAgCAAAAgAAAIAAACAIAAACAAAAgAAAIAIACOAEAAABAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAEAAABAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAEAAABAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABABAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABABAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAQAAAqOwD+ASWE8sPs+IAAAAASUVORK5CYII=')
SERVICE_WORKER = 'const RETIRE_VERSION="v925-commercial-retire-pwa-cache";\n\nself.addEventListener("install",event=>{\n  event.waitUntil(self.skipWaiting());\n});\n\nself.addEventListener("activate",event=>{\n  event.waitUntil((async()=>{\n    try{\n      const keys=await caches.keys();\n      await Promise.all(keys.filter(k=>k.startsWith("changying-fuxue-")).map(k=>caches.delete(k)));\n    }catch(_){}\n\n    try{await self.clients.claim()}catch(_){}\n\n    // 注销 Service Worker：V9.2.0 起网页版不再让 PWA 缓存拦截页面升级。\n    try{await self.registration.unregister()}catch(_){}\n\n    // 让当前旧页面重新从网络加载最新版本。\n    try{\n      const clientsList=await self.clients.matchAll({type:"window",includeUncontrolled:true});\n      for(const client of clientsList){\n        try{await client.navigate(client.url)}catch(_){}\n      }\n    }catch(_){}\n  })());\n});\n\n// 退休过程中如果仍控制着页面，请求一律走网络，不再读缓存。\nself.addEventListener("fetch",event=>{\n  event.respondWith(fetch(event.request));\n});\n'

OPERATOR_HTML = '<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#5362e8">\n<title>长缨辅学｜商业运营控制台</title>\n<style>\n:root{--p:#5362e8;--bg:#f4f6fb;--card:#fff;--line:#e5e8f0;--text:#1f2738;--muted:#778095;--green:#27835c;--red:#bb3145;--amber:#9a6a17}\n*{box-sizing:border-box}body{margin:0;background:var(--bg);font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;color:var(--text)}\nmain{max-width:1180px;margin:auto;padding:calc(22px + env(safe-area-inset-top)) 16px calc(70px + env(safe-area-inset-bottom))}.top{display:flex;gap:12px;justify-content:space-between;align-items:center;flex-wrap:wrap;margin-bottom:16px}.top h1{font-size:25px;margin:0}.top p{margin:5px 0 0;color:var(--muted)}\n.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:16px;box-shadow:0 4px 18px rgba(31,39,56,.04)}.grid{display:grid;gap:12px}.kpis{grid-template-columns:repeat(4,minmax(0,1fr));margin-bottom:14px}.kpi b{font-size:25px;color:var(--p)}.kpi small{display:block;color:var(--muted);margin-top:5px}\n.actions{display:flex;gap:8px;flex-wrap:wrap}.btn{border:0;border-radius:11px;padding:10px 13px;font-weight:700;background:#eef0ff;color:#4350d5;cursor:pointer}.btn.primary{background:var(--p);color:#fff}.btn.danger{background:#ffecef;color:var(--red)}.btn.green{background:#eaf8f2;color:var(--green)}\ninput,select,textarea{width:100%;border:1px solid #dfe3ee;border-radius:11px;padding:11px;font:inherit;background:white}textarea{min-height:76px;resize:vertical}label{display:grid;gap:5px;font-size:13px;color:var(--muted)}.formgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px}.wide{grid-column:1/-1}\n.badge{display:inline-flex;align-items:center;border-radius:999px;padding:5px 9px;font-size:12px;font-weight:800;background:#eef0ff;color:#4350d5}.badge.green{background:#eaf8f2;color:var(--green)}.badge.red{background:#ffecef;color:var(--red)}.badge.amber{background:#fff5df;color:var(--amber)}\n.toolbar{display:flex;gap:9px;flex-wrap:wrap;margin:14px 0}.toolbar input{max-width:320px}.toolbar select{width:auto;min-width:145px}.school{margin-bottom:12px}.school-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap}.school h3{margin:0 0 5px;font-size:19px}.muted{color:var(--muted)}.usage{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:12px 0}.usage div{background:#f8f9fc;border-radius:12px;padding:10px}.usage b{display:block;font-size:17px}.usage small{color:var(--muted)}\n.quick{display:flex;gap:7px;flex-wrap:wrap;border-top:1px solid var(--line);padding-top:12px;margin-top:12px}.quick .btn{font-size:12px;padding:8px 10px}#gate{max-width:520px;margin:14vh auto}.note{padding:11px 12px;border-radius:12px;background:#fff7e7;color:#7b5719;font-size:13px;line-height:1.6}.secret{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;background:#f7f8fb;border-radius:10px;padding:10px;overflow-wrap:anywhere}\n.overlay{position:fixed;inset:0;background:rgba(20,27,45,.42);display:none;align-items:flex-end;justify-content:center;z-index:99}.overlay.show{display:flex}.modal{background:#fff;width:min(760px,100%);max-height:88dvh;overflow:auto;border-radius:22px 22px 0 0;padding:18px 16px calc(24px + env(safe-area-inset-bottom))}.event{border-bottom:1px solid var(--line);padding:10px 0}.event:last-child{border:0}.json{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap;background:#f7f8fb;border-radius:10px;padding:9px;margin-top:6px;overflow-wrap:anywhere}.quota-grid{display:grid;grid-template-columns:110px 1fr 1fr;gap:8px;align-items:end}.quota-grid b{padding-bottom:11px}\n@media(max-width:720px){.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.formgrid{grid-template-columns:1fr}.usage{grid-template-columns:repeat(3,1fr)}.top h1{font-size:22px}.quota-grid{grid-template-columns:1fr}.quota-grid b{padding:4px 0 0}}\n</style></head>\n<body><main>\n<section id="gate" class="card"><h1 style="margin-top:0">商业运营控制台</h1><p class="muted">仅运营方使用。密钥只保存在当前浏览器会话中。</p><label>COMMERCIAL_ADMIN_KEY<input id="key" type="password" autocomplete="off" placeholder="输入 Render 中配置的商业运营密钥"></label><div class="actions" style="margin-top:12px"><button class="btn primary" onclick="connect()">进入控制台</button></div><p class="note">请勿把运营密钥发给学校管理员或客户，也不要在截图中显示。</p></section>\n<section id="app" style="display:none"><div class="top"><div><h1>长缨辅学 · 商业运营控制台</h1><p>V9.2.5 商业版 C2.5 · 订单 / 应收实收 / 分次收款 / 退款 / 续费</p></div><div class="actions"><button class="btn primary" onclick="openCreate()">＋新建试用客户</button><button class="btn green" onclick="showAllOrders()">订单台账</button><button class="btn" onclick="showAllRenewals()">续费记录</button><button class="btn" onclick="showOperations()">操作记录</button><button class="btn" onclick="reload()">刷新</button><button class="btn danger" onclick="logout()">退出</button></div></div><div id="kpis" class="grid kpis"></div><div class="toolbar"><input id="search" placeholder="搜索学校、代码、联系人、管理员账号" oninput="renderSchools()"><select id="statusFilter" onchange="renderSchools()"><option value="">全部状态</option><option value="active">已开通</option><option value="trial">试用中</option><option value="grace">宽限期</option><option value="expired">已到期</option><option value="paused">已暂停</option><option value="renewal">待续费 / 将到期</option><option value="receivable">有待收款</option><option value="followup">待跟进</option></select><select id="planFilter" onchange="renderSchools()"><option value="">全部套餐</option></select></div><div id="schools"></div></section>\n</main><div id="overlay" class="overlay" onclick="if(event.target===this)closeModal()"><div id="modal" class="modal"></div></div>\n<script>\nlet KEY=sessionStorage.getItem("commercialKey")||"",schools=[],plans=[],CREATED_CREDENTIAL="";\nconst $=s=>document.querySelector(s),esc=s=>String(s??"").replace(/[&<>"\']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","\'":"&#39;"}[c]));\nfunction headers(){return {"Content-Type":"application/json","X-Commercial-Key":KEY}}\nasync function op(path,opt={}){const r=await fetch(path,{...opt,headers:{...headers(),...(opt.headers||{})}});let d=null;try{d=await r.json()}catch{}if(!r.ok)throw new Error(d?.detail||`请求失败 ${r.status}`);return d}\nfunction toast(msg){alert(msg)} function statusClass(s){return s==="active"?"green":(s==="expired"||s==="paused")?"red":"amber"} function planName(code){return plans.find(x=>x.code===code)?.name||code}\nfunction dateOnly(v){return v?(v.includes("T")?v.slice(0,16).replace("T"," "):v):""} function dateInput(v){return v?v.slice(0,10):""}\nasync function connect(){KEY=$("#key").value.trim();if(!KEY)return toast("请输入运营密钥");sessionStorage.setItem("commercialKey",KEY);try{await reload();$("#gate").style.display="none";$("#app").style.display=""}catch(e){sessionStorage.removeItem("commercialKey");KEY="";toast(e.message)}}\nfunction logout(){sessionStorage.removeItem("commercialKey");location.reload()}\nasync function reload(){const [summary,rows,p]=await Promise.all([op("/operator/summary"),op("/operator/schools"),fetch("/commercial/plans").then(r=>r.json())]);schools=rows;plans=p.plans||[];const pf=$("#planFilter"),old=pf.value;pf.innerHTML=`<option value="">全部套餐</option>`+plans.map(x=>`<option value="${esc(x.code)}">${esc(x.name)}</option>`).join("");pf.value=old;renderSummary(summary);renderSchools()}\nfunction renderSummary(s){$("#kpis").innerHTML=[["客户学校",s.totalSchools],["已开通",s.active],["待收款订单",s.unpaidOrders],["应收未收",`¥${Number(s.receivableOutstandingYuan||0).toLocaleString()}`],["30天实收",`¥${Number(s.cashCollected30dYuan||0).toLocaleString()}`],["30天退款",`¥${Number(s.refund30dYuan||0).toLocaleString()}`],["30天净收入",`¥${Number(s.netRevenue30dYuan||0).toLocaleString()}`],["30天订单",s.orders30d],["7天内服务到期",s.serviceEnding7d],["待续费",s.renewalDue],["试用中",s.trial],["已到期",s.expired],["待跟进",s.followupDue],["在用教师",s.activeTeachers],["在读学生",s.activeStudents]].map(x=>`<div class="card kpi"><b>${x[1]??0}</b><small>${x[0]}</small></div>`).join("")}\nfunction planLimit(v){return v===null||v===undefined?"不限":v}\nfunction expiryText(s){if(s.status==="trial")return s.trialEndsAt?`试用至 ${dateOnly(s.trialEndsAt)}`:"试用中";if(s.status==="active")return s.periodEndsAt?`服务到期 ${dateOnly(s.periodEndsAt)}`:"长期有效";if(s.status==="grace")return s.graceEndsAt?`宽限至 ${dateOnly(s.graceEndsAt)}`:"宽限期";return "已到期"}\nfunction limitHint(s,k){const o=s.quotaOverrides||{},p=s.planLimits||{};if(!(k in o))return "";return ` · 套餐 ${planLimit(p[k])} → 人工 ${planLimit(o[k])}`}\nfunction renderSchools(){const q=$("#search").value.trim().toLowerCase(),f=$("#statusFilter").value,pf=$("#planFilter").value;const rows=schools.filter(s=>{if(pf&&s.planCode!==pf)return false;if(f==="followup"&&!s.followupDue)return false;if(f==="renewal"&&!s.renewalDue)return false;if(f==="receivable"&&!(Number(s.outstandingYuan||0)>0))return false;if(f&&f!=="followup"&&f!=="renewal"&&f!=="receivable"&&s.operatorStatus!==f)return false;const text=[s.schoolName,s.schoolCode,s.contactName,s.contactValue,s.planName,...(s.admins||[]).flatMap(x=>[x.name,x.username])].join(" ").toLowerCase();return !q||text.includes(q)});$("#schools").innerHTML=rows.length?rows.map(s=>`<div class="card school"><div class="school-head"><div><h3>${esc(s.schoolName)} <span class="badge">${esc(s.schoolCode||"")}</span></h3><div class="muted">${esc(s.contactName||"未填写联系人")}${s.contactValue?` · ${esc(s.contactValue)}`:""} · 学校ID ${s.schoolID}${(!s.contactName&&!s.contactValue)?` <span class="badge amber">联系资料待完善</span>`:""}</div></div><div><span class="badge ${statusClass(s.operatorStatus)}">${esc(s.operatorStatusName)}</span> <span class="badge">${esc(s.planName)}</span>${s.renewalDue&&s.schoolActive?` <span class="badge amber">待续费</span>`:""}${s.hasQuotaOverride?` <span class="badge amber">人工额度</span>`:""}${Number(s.outstandingYuan||0)>0?` <span class="badge red">待收 ¥${Number(s.outstandingYuan).toLocaleString()}</span>`:""}</div></div><div class="usage"><div><b>${s.usage?.teachers??0} / ${planLimit(s.limits?.teachers)}</b><small>教师${esc(limitHint(s,"teachers"))}</small></div><div><b>${s.usage?.classes??0} / ${planLimit(s.limits?.classes)}</b><small>班级${esc(limitHint(s,"classes"))}</small></div><div><b>${s.usage?.students??0} / ${planLimit(s.limits?.students)}</b><small>学生${esc(limitHint(s,"students"))}</small></div></div><div class="muted">${esc(expiryText(s))}${s.daysRemaining!==null&&s.daysRemaining!==undefined&&s.status!=="expired"?` · 剩余 ${s.daysRemaining} 天`:""}${s.admins?.length?` · 管理员 ${esc(s.admins.map(x=>x.username).join("、"))}`:""}</div>${s.latestRenewal?`<div class="note" style="margin-top:10px;background:#eaf8f2;color:var(--green)"><b>最近续费：</b>${esc(s.latestRenewal.createdAt||"")} · ¥${Number(s.latestRenewal.amountYuan||0).toLocaleString()} · 服务至 ${esc(dateOnly(s.latestRenewal.serviceEndAt)||"")}</div>`:""}${s.latestOrder?`<div class="note" style="margin-top:10px;background:#f5f6ff;color:#4b56c7"><b>最近订单：</b>${esc(s.latestOrder.orderNo||"")} · ${esc(s.latestOrder.statusName||"")} · 应收 ¥${Number(s.latestOrder.amountDueYuan||0).toLocaleString()} · 实收 ¥${Number(s.latestOrder.netPaidYuan||0).toLocaleString()}</div>`:""}${s.customerNote?`<div class="note" style="margin-top:10px">${esc(s.customerNote)}</div>`:""}${s.latestFollowUp?`<div class="note" style="margin-top:10px;${s.followupDue?"background:#ffecef;color:var(--red)":""}"><b>最近跟进：</b>${esc(s.latestFollowUp.content)}${s.nextFollowupDate?`<br><b>下次跟进：</b>${esc(s.nextFollowupDate)}${s.followupDue?"（待处理）":""}`:""}</div>`:""}<div class="quick"><button class="btn primary" onclick="openRenewal(${s.schoolID})">续费 / 转正式</button><button class="btn" onclick="showRenewals(${s.schoolID})">续费记录${s.renewalCount?`（${s.renewalCount}）`:""}</button><button class="btn green" onclick="openOrder(${s.schoolID})">新建订单</button><button class="btn" onclick="showOrders(${s.schoolID})">订单记录${s.orderCount?`（${s.orderCount}）`:""}</button><button class="btn" onclick="customPlan(${s.schoolID})">套餐 / 到期日</button><button class="btn" onclick="editQuota(${s.schoolID})">调整额度</button><button class="btn ${s.schoolActive?\'danger\':\'green\'}" onclick="toggleSchool(${s.schoolID},${s.schoolActive?\'false\':\'true\'})">${s.schoolActive?\'暂停学校\':\'恢复学校\'}</button><button class="btn primary" onclick="addFollowUp(${s.schoolID})">记录跟进</button><button class="btn" onclick="showFollowUps(${s.schoolID})">跟进历史</button><button class="btn" onclick="editCustomer(${s.schoolID})">编辑客户资料</button><button class="btn" onclick="copyLoginInfo(${s.schoolID})">复制登录信息</button><button class="btn" onclick="showOperations(${s.schoolID})">操作记录</button><button class="btn" onclick="showEvents(${s.schoolID})">商业历史</button><button class="btn" onclick="resetAdmin(${s.schoolID})">重置管理员密码</button><button class="btn" onclick="quick(${s.schoolID},\'teacher_pro\',\'trial\',14,365,7,\'14天教师专业版试用\')">14天专业版试用</button></div></div>`).join(""):`<div class="card muted">没有匹配客户</div>`}\nasync function quick(id,plan,status,trial,period,grace,note){if(!confirm(`确认：${note}？`))return;try{await op(`/operator/subscriptions/${id}`,{method:"POST",body:JSON.stringify({plan_code:plan,status,trial_days:trial,period_days:period,grace_days:grace,end_date:"",note})});await reload()}catch(e){toast(e.message)}}\nfunction openModal(html){$("#modal").innerHTML=html;$("#overlay").classList.add("show")} function closeModal(){$("#overlay").classList.remove("show")}\nfunction openCreate(){openModal(`<h2>新建试用客户</h2><div class="formgrid"><label>学校名称<input id="cSchool" placeholder="例如：长缨实验小学"></label><label>学校代码<input id="cCode" placeholder="例如：CY001"></label><label>管理员姓名<input id="cAdminName" value="管理员"></label><label>管理员账号<input id="cAdminUser" placeholder="例如：admin_cy001"></label><label>临时密码<input id="cPassword" placeholder="至少8位，含字母和数字"></label><label>联系人<input id="cContactName" placeholder="老师/校长姓名"></label><label class="wide">联系方式<input id="cContactValue" placeholder="手机号、微信工作号或邮箱"></label><label>初始套餐<select id="cPlan">${plans.map(p=>`<option value="${p.code}" ${p.code==="teacher_pro"?"selected":""}>${esc(p.name)}</option>`).join("")}</select></label><label>状态<select id="cStatus"><option value="trial">14天试用</option><option value="active">直接开通年付</option></select></label><label class="wide">备注<textarea id="cNote" placeholder="客户来源、沟通情况等"></textarea></label></div><div class="actions" style="margin-top:14px"><button class="btn primary" onclick="createSchool()">创建客户</button><button class="btn" onclick="closeModal()">取消</button></div>`)}\nasync function createSchool(){const body={school_name:$("#cSchool").value.trim(),school_code:$("#cCode").value.trim(),admin_name:$("#cAdminName").value.trim(),admin_username:$("#cAdminUser").value.trim(),admin_password:$("#cPassword").value,contact_name:$("#cContactName").value.trim(),contact_value:$("#cContactValue").value.trim(),source:"operator_console",plan_code:$("#cPlan").value,status:$("#cStatus").value,trial_days:14,period_days:365,grace_days:7,note:$("#cNote").value.trim()};try{const d=await op("/operator/schools/create",{method:"POST",body:JSON.stringify(body)});const c=d.temporaryCredential;CREATED_CREDENTIAL=`学校：${c.schoolName}\\n学校代码：${c.schoolCode}\\n账号：${c.username}\\n临时密码：${c.password}`;openModal(`<h2>客户创建成功</h2><p class="note">下面是一次性临时登录信息。请安全发送给客户，首次登录会要求修改密码。</p><div class="secret">学校：${esc(c.schoolName)}<br>学校代码：${esc(c.schoolCode)}<br>账号：${esc(c.username)}<br>临时密码：${esc(c.password)}</div><div class="actions" style="margin-top:12px"><button class="btn primary" onclick="copyCredential()">复制登录信息</button><button class="btn" onclick="closeModal();reload()">完成</button></div>`)}catch(e){toast(e.message)}}\nasync function copyCredential(){try{await navigator.clipboard.writeText(CREATED_CREDENTIAL);toast("已复制")}catch{toast("复制失败，请手动选择")}}\nfunction addFollowUp(id){const s=schools.find(x=>x.schoolID===id),tomorrow=new Date(Date.now()+86400000*3).toISOString().slice(0,10);openModal(`<h2>${esc(s.schoolName)} · 记录商业跟进</h2><div class="formgrid"><label>跟进类型<select id="fType"><option value="contact">联系沟通</option><option value="demo">产品演示</option><option value="quote">报价</option><option value="payment">付款/续费</option><option value="other">其他</option></select></label><label>下次跟进日期（可选）<input id="fNext" type="date" value="${tomorrow}"></label><label class="wide">本次跟进内容<textarea id="fContent" placeholder="例如：已演示成长档案与成长报告，客户希望下周确认试用名单。"></textarea></label></div><div class="actions" style="margin-top:14px"><button class="btn primary" onclick="saveFollowUp(${id})">保存跟进</button><button class="btn" onclick="closeModal()">取消</button></div>`)}\nasync function saveFollowUp(id){try{await op(`/operator/schools/${id}/followups`,{method:"POST",body:JSON.stringify({follow_type:$("#fType").value,content:$("#fContent").value.trim(),next_followup_date:$("#fNext").value})});closeModal();await reload();toast("跟进记录已保存")}catch(e){toast(e.message)}}\nasync function showFollowUps(id){const s=schools.find(x=>x.schoolID===id);try{const rows=await op(`/operator/schools/${id}/followups`);openModal(`<h2>${esc(s?.schoolName||"客户")} · 跟进历史</h2>${rows.length?rows.map(x=>`<div class="event"><b>${esc(x.typeName)}</b><div class="muted">${esc(x.createdAt||"")}${x.nextFollowupDate?` · 下次 ${esc(x.nextFollowupDate)}`:""}</div><div style="margin-top:5px">${esc(x.content)}</div></div>`).join(""):`<p class="muted">暂无跟进记录</p>`}<div class="actions"><button class="btn" onclick="closeModal()">关闭</button></div>`)}catch(e){toast(e.message)}}\nfunction editCustomer(id){const s=schools.find(x=>x.schoolID===id);openModal(`<h2>${esc(s.schoolName)} · 编辑客户资料</h2><div class="formgrid"><label>联系人<input id="eContactName" value="${esc(s.contactName||"")}" placeholder="老师/校长姓名"></label><label>联系方式<input id="eContactValue" value="${esc(s.contactValue||"")}" placeholder="手机号、工作微信或邮箱"></label><label class="wide">客户来源<input id="eSource" value="${esc(s.customerSource||"")}" placeholder="例如：教师转介绍、学校拜访、线上咨询"></label><label class="wide">客户备注<textarea id="eNote">${esc(s.customerNote||"")}</textarea></label></div><div class="actions" style="margin-top:14px"><button class="btn primary" onclick="saveCustomer(${id})">保存客户资料</button><button class="btn" onclick="closeModal()">取消</button></div>`)}\nasync function saveCustomer(id){try{await op(`/operator/schools/${id}/customer`,{method:"POST",body:JSON.stringify({contact_name:$("#eContactName").value.trim(),contact_value:$("#eContactValue").value.trim(),source:$("#eSource").value.trim(),note:$("#eNote").value.trim()})});closeModal();await reload();toast("客户资料已保存")}catch(e){toast(e.message)}}\nasync function copyLoginInfo(id){const s=schools.find(x=>x.schoolID===id),admin=s?.admins?.[0]?.username||"";const text=`长缨辅学登录地址：${location.origin}\\n学校：${s?.schoolName||""}\\n管理员账号：${admin}`;try{await navigator.clipboard.writeText(text);toast("登录信息已复制")}catch{toast("复制失败，请手动记录")}}\nfunction money(v){return `¥${Number(v||0).toLocaleString()}`}\nfunction orderStatusClass(s){return (s==="paid")?"green":((s==="void"||s==="refunded")?"red":"amber")}\nfunction openOrder(id){const s=schools.find(x=>x.schoolID===id);openModal(`<h2>${esc(s.schoolName)} · 新建收费订单</h2><div class="formgrid"><label>订单名称<input id="oTitle" placeholder="例如：2026-2027 学年标准版服务费"></label><label>订单类型<select id="oType"><option value="service">服务订单</option><option value="new">新签订单</option><option value="renewal">续费订单</option><option value="custom">其他订单</option></select></label><label>套餐<select id="oPlan">${plans.map(p=>`<option value="${p.code}" ${p.code===s.planCode?"selected":""}>${esc(p.name)}</option>`).join("")}</select></label><label>应收金额（元）<input id="oDue" type="number" min="0" step="0.01" placeholder="例如 6800"></label><label>本次实收（元，可为0）<input id="oPaid" type="number" min="0" step="0.01" value="0"></label><label>付款日期<input id="oDate" type="date"></label><label>付款方式<select id="oMethod"><option value="">未登记</option><option>银行转账</option><option>微信</option><option>支付宝</option><option>现金</option><option>其他</option></select></label><label>流水/凭证号<input id="oRef" placeholder="可选"></label><label class="wide">备注<textarea id="oNote" placeholder="合同编号、收费说明等"></textarea></label></div><p class="note">订单只记录商业收费，不会自动修改学校服务期。需要开通/延长服务时，请使用“续费 / 转正式”。</p><div class="actions"><button class="btn primary" onclick="saveOrder(${id})">创建订单</button><button class="btn" onclick="closeModal()">取消</button></div>`)}\nasync function saveOrder(id){try{const body={title:$("#oTitle").value.trim(),order_type:$("#oType").value,plan_code:$("#oPlan").value,amount_due_yuan:+$("#oDue").value||0,amount_paid_yuan:+$("#oPaid").value||0,payment_method:$("#oMethod").value,payment_reference:$("#oRef").value.trim(),payment_date:$("#oDate").value,note:$("#oNote").value.trim()};await op(`/operator/schools/${id}/orders`,{method:"POST",body:JSON.stringify(body)});closeModal();await reload();toast("订单已创建")}catch(e){toast(e.message)}}\nfunction txHtml(x){return (x.transactions||[]).map(t=>`<div class="muted" style="margin-top:5px">${esc(t.paymentAt||"")} · ${esc(t.typeName)} ${money(t.amountYuan)}${t.paymentMethod?` · ${esc(t.paymentMethod)}`:""}${t.paymentReference?` · ${esc(t.paymentReference)}`:""}${t.note?` · ${esc(t.note)}`:""}</div>`).join("")}\nfunction orderRowsHtml(rows){return rows.length?rows.map(x=>`<div class="event"><div><b>${esc(x.orderNo)} · ${esc(x.schoolName||"")}</b> <span class="badge ${orderStatusClass(x.status)}">${esc(x.statusName)}</span></div><div class="muted">${esc(x.title||x.orderTypeName||"")} · ${esc(x.planName||"")} · ${esc(x.createdAt||"")}</div><div style="margin-top:6px">应收 ${money(x.amountDueYuan)} · 实收 ${money(x.amountPaidYuan)} · 退款 ${money(x.amountRefundedYuan)} · <b>待收 ${money(x.outstandingYuan)}</b></div>${txHtml(x)}${x.note?`<div class="note" style="margin-top:7px">${esc(x.note)}</div>`:""}<div class="actions" style="margin-top:8px">${x.status!=="void"&&x.status!=="refunded"&&Number(x.outstandingYuan||0)>0?`<button class="btn green" onclick="addPayment(${x.id},${x.schoolID})">登记收款</button>`:""}${x.status!=="void"&&Number(x.netPaidYuan||0)>0?`<button class="btn danger" onclick="refundOrder(${x.id},${x.schoolID},${Number(x.netPaidYuan||0)})">登记退款</button>`:""}${x.status!=="void"&&Number(x.netPaidYuan||0)<=0?`<button class="btn danger" onclick="voidOrder(${x.id})">作废订单</button>`:""}</div></div>`).join(""):`<p class="muted">暂无订单</p>`}\nasync function showOrders(id){const s=schools.find(x=>x.schoolID===id);try{const rows=await op(`/operator/schools/${id}/orders`);openModal(`<h2>${esc(s?.schoolName||"客户")} · 订单记录</h2>${orderRowsHtml(rows)}<div class="actions"><button class="btn green" onclick="openOrder(${id})">新建订单</button><button class="btn" onclick="closeModal()">关闭</button></div>`)}catch(e){toast(e.message)}}\nasync function showAllOrders(){try{const rows=await op(`/operator/orders?limit=300`);openModal(`<h2>全部客户 · 订单与收费台账</h2>${orderRowsHtml(rows)}<div class="actions"><button class="btn" onclick="closeModal()">关闭</button></div>`)}catch(e){toast(e.message)}}\nfunction addPayment(orderId,schoolId){openModal(`<h2>登记收款</h2><div class="formgrid"><label>收款金额（元）<input id="pAmount" type="number" min="0.01" step="0.01"></label><label>付款日期<input id="pDate" type="date"></label><label>付款方式<select id="pMethod"><option value="">未登记</option><option>银行转账</option><option>微信</option><option>支付宝</option><option>现金</option><option>其他</option></select></label><label>流水/凭证号<input id="pRef"></label><label class="wide">备注<textarea id="pNote"></textarea></label></div><div class="actions"><button class="btn primary" onclick="savePayment(${orderId},${schoolId})">保存收款</button><button class="btn" onclick="closeModal()">取消</button></div>`)}\nasync function savePayment(orderId,schoolId){try{await op(`/operator/orders/${orderId}/payments`,{method:"POST",body:JSON.stringify({amount_yuan:+$("#pAmount").value||0,payment_method:$("#pMethod").value,payment_reference:$("#pRef").value.trim(),payment_date:$("#pDate").value,note:$("#pNote").value.trim()})});closeModal();await reload();toast("收款已登记")}catch(e){toast(e.message)}}\nfunction refundOrder(orderId,schoolId,available){openModal(`<h2>登记退款</h2><p class="muted">当前可退净实收：${money(available)}</p><div class="formgrid"><label>退款金额（元）<input id="fAmount" type="number" min="0.01" step="0.01" max="${available}"></label><label>退款日期<input id="fDate" type="date"></label><label>退款方式<select id="fMethod"><option value="">未登记</option><option>银行转账</option><option>微信</option><option>支付宝</option><option>现金</option><option>其他</option></select></label><label>退款流水/凭证号<input id="fRef"></label><label class="wide">退款原因<textarea id="fNote"></textarea></label></div><div class="actions"><button class="btn danger" onclick="saveRefund(${orderId},${schoolId})">确认退款</button><button class="btn" onclick="closeModal()">取消</button></div>`)}\nasync function saveRefund(orderId,schoolId){if(!confirm("确认登记这笔退款？"))return;try{await op(`/operator/orders/${orderId}/refunds`,{method:"POST",body:JSON.stringify({amount_yuan:+$("#fAmount").value||0,payment_method:$("#fMethod").value,payment_reference:$("#fRef").value.trim(),payment_date:$("#fDate").value,note:$("#fNote").value.trim()})});closeModal();await reload();toast("退款已登记")}catch(e){toast(e.message)}}\nasync function voidOrder(orderId){if(!confirm("确认作废这张订单？订单会保留用于审计。"))return;const note=prompt("作废原因（可选）","")||"";try{await op(`/operator/orders/${orderId}/void`,{method:"POST",body:JSON.stringify({note})});closeModal();await reload();toast("订单已作废")}catch(e){toast(e.message)}}\nfunction openRenewal(id){const s=schools.find(x=>x.schoolID===id);openModal(`<h2>${esc(s.schoolName)} · 续费 / 转正式</h2><p class="muted">当前：${esc(s.planName)} · ${esc(expiryText(s))}。未到期的正式服务按当前服务到期日继续顺延；已到期或试用客户从现在开始计算。</p><div class="formgrid"><label>续费后套餐<select id="nPlan">${plans.map(p=>`<option value="${p.code}" ${p.code===s.planCode?"selected":""}>${esc(p.name)}</option>`).join("")}</select></label><label>服务天数<input id="nDays" type="number" min="1" max="3650" value="365"></label><label>明确新到期日（可选，优先）<input id="nEnd" type="date"></label><label>宽限天数<input id="nGrace" type="number" min="0" max="60" value="7"></label><label>本次已收金额（元）<input id="nAmount" type="number" min="0" step="0.01" placeholder="例如 6800"></label><label>付款方式<select id="nMethod"><option value="">未登记</option><option value="银行转账">银行转账</option><option value="微信">微信</option><option value="支付宝">支付宝</option><option value="现金">现金</option><option value="其他">其他</option></select></label><label class="wide">付款流水/凭证号（可选）<input id="nRef" placeholder="仅记录编号，不要填写银行卡密码等敏感信息"></label><label class="wide">续费备注<textarea id="nNote" placeholder="例如：2026-2027 学年标准版年费；合同编号等"></textarea></label></div><p class="note">保存后订阅立即变为“已开通”，并自动生成一张“已收款”的续费订单；试用/已到期的只读限制会解除。若学校被人工“暂停”，仍需单独点击“恢复学校”。</p><div class="actions"><button class="btn primary" onclick="saveRenewal(${id})">确认续费并开通</button><button class="btn" onclick="closeModal()">取消</button></div>`)}\nasync function saveRenewal(id){if(!confirm("确认登记本次续费并立即开通服务？"))return;try{const body={plan_code:$("#nPlan").value,period_days:+$("#nDays").value||365,end_date:$("#nEnd").value,grace_days:+$("#nGrace").value||0,amount_yuan:+$("#nAmount").value||0,payment_method:$("#nMethod").value,payment_reference:$("#nRef").value.trim(),note:$("#nNote").value.trim()};await op(`/operator/schools/${id}/renewals`,{method:"POST",body:JSON.stringify(body)});closeModal();await reload();toast("续费已登记，服务已开通") }catch(e){toast(e.message)}}\nfunction renewalRowsHtml(rows){return rows.length?rows.map(x=>`<div class="event"><b>${esc(x.schoolName||"")} · ${esc(x.planName||x.planCode)}</b><div class="muted">登记 ${esc(x.createdAt||"")} · 服务 ${esc(dateOnly(x.serviceStartAt))} → ${esc(dateOnly(x.serviceEndAt))}</div><div style="margin-top:5px">金额：¥${Number(x.amountYuan||0).toLocaleString()}${x.paymentMethod?` · 付款方式：${esc(x.paymentMethod)}`:""}${x.paymentReference?` · 凭证：${esc(x.paymentReference)}`:""}</div>${x.note?`<div class="note" style="margin-top:7px">${esc(x.note)}</div>`:""}</div>`).join(""):`<p class="muted">暂无续费记录</p>`}\nasync function showRenewals(id){const s=schools.find(x=>x.schoolID===id);try{const rows=await op(`/operator/schools/${id}/renewals`);openModal(`<h2>${esc(s?.schoolName||"客户")} · 续费记录</h2>${renewalRowsHtml(rows)}<div class="actions"><button class="btn" onclick="closeModal()">关闭</button></div>`)}catch(e){toast(e.message)}}\nasync function showAllRenewals(){try{const rows=await op(`/operator/renewals?limit=300`);openModal(`<h2>全部客户 · 续费记录</h2>${renewalRowsHtml(rows)}<div class="actions"><button class="btn" onclick="closeModal()">关闭</button></div>`)}catch(e){toast(e.message)}}\nfunction customPlan(id){const s=schools.find(x=>x.schoolID===id);const currentEnd=s.status==="trial"?s.trialEndsAt:s.status==="grace"?s.graceEndsAt:s.periodEndsAt;openModal(`<h2>${esc(s.schoolName)} · 套餐与服务期</h2><div class="formgrid"><label>套餐<select id="uPlan">${plans.map(p=>`<option value="${p.code}" ${p.code===s.planCode?"selected":""}>${esc(p.name)}</option>`).join("")}</select></label><label>订阅状态<select id="uStatus"><option value="trial">试用中</option><option value="active">已开通</option><option value="grace">宽限期</option><option value="expired">已到期</option></select></label><label>明确到期日（优先）<input id="uEnd" type="date" value="${dateInput(currentEnd)}"></label><label>试用天数（未填到期日时）<input id="uTrial" type="number" value="14"></label><label>开通天数（未填到期日时）<input id="uPeriod" type="number" value="365"></label><label>宽限天数<input id="uGrace" type="number" value="7"></label><label class="wide">备注<textarea id="uNote">${esc(s.note||"")}</textarea></label></div><p class="note">填写“明确到期日”后，以该日期当天 23:59 为服务截止；不填则按天数计算。</p><div class="actions"><button class="btn primary" onclick="saveCustom(${id})">保存套餐与服务期</button><button class="btn" onclick="closeModal()">取消</button></div>`);$("#uStatus").value=s.status}\nasync function saveCustom(id){try{await op(`/operator/subscriptions/${id}`,{method:"POST",body:JSON.stringify({plan_code:$("#uPlan").value,status:$("#uStatus").value,trial_days:+$("#uTrial").value||14,period_days:+$("#uPeriod").value||365,grace_days:+$("#uGrace").value||7,end_date:$("#uEnd").value,note:$("#uNote").value.trim()})});closeModal();await reload();toast("套餐与服务期已保存")}catch(e){toast(e.message)}}\nfunction quotaMode(s,k){const o=s.quotaOverrides||{};if(!(k in o))return "inherit";return o[k]===null?"unlimited":"custom"} function quotaNumber(s,k){const o=s.quotaOverrides||{};return (k in o&&o[k]!==null)?o[k]:""}\nfunction quotaRow(label,prefix,resource,s){return `<div class="quota-grid"><b>${label}</b><label>模式<select id="q${prefix}Mode"><option value="inherit">跟随套餐</option><option value="custom">自定义</option><option value="unlimited">不限</option></select></label><label>自定义额度<input id="q${prefix}Num" type="number" min="1" value="${quotaNumber(s,resource)}" placeholder="正整数"></label></div>`}\nfunction editQuota(id){const s=schools.find(x=>x.schoolID===id);openModal(`<h2>${esc(s.schoolName)} · 调整额度</h2><p class="muted">当前套餐：${esc(s.planName)}。单独调整后会覆盖套餐默认额度。</p>${quotaRow("教师","T","teachers",s)}${quotaRow("班级","C","classes",s)}${quotaRow("学生","S","students",s)}<label style="margin-top:12px">备注<textarea id="qNote" placeholder="例如：签约赠送 10 个教师名额"></textarea></label><div class="actions" style="margin-top:14px"><button class="btn primary" onclick="saveQuota(${id})">保存额度</button><button class="btn" onclick="closeModal()">取消</button></div>`);[["T","teachers"],["C","classes"],["S","students"]].forEach(([p,k])=>{$(`#q${p}Mode`).value=quotaMode(s,k)})}\nfunction quotaValue(p){const m=$(`#q${p}Mode`).value;if(m!=="custom")return m;const n=$(`#q${p}Num`).value.trim();return n||"inherit"}\nasync function saveQuota(id){try{await op(`/operator/schools/${id}/quota`,{method:"POST",body:JSON.stringify({teachers:quotaValue("T"),classes:quotaValue("C"),students:quotaValue("S"),note:$("#qNote").value.trim()})});closeModal();await reload();toast("额度已保存")}catch(e){toast(e.message)}}\nasync function toggleSchool(id,active){const s=schools.find(x=>x.schoolID===id),verb=active?"恢复":"暂停";if(!confirm(`确认${verb}“${s.schoolName}”？${active?"恢复后用户可重新登录。":"暂停后学校全部账号将立即无法继续使用，但数据不会删除。"}`))return;const note=prompt(`${verb}原因/备注（可留空）`,"")||"";try{await op(`/operator/schools/${id}/state`,{method:"POST",body:JSON.stringify({active,note})});await reload();toast(`学校已${verb}`)}catch(e){toast(e.message)}}\nfunction compactJson(v){return esc(JSON.stringify(v||{},null,2))}\nasync function showOperations(id=null){try{const rows=await op(`/operator/operations?limit=200${id?`&school_id=${id}`:""}`),s=id?schools.find(x=>x.schoolID===id):null;openModal(`<h2>${esc(s?.schoolName||"全部客户")} · 运营操作记录</h2>${rows.length?rows.map(x=>`<div class="event"><b>${esc(x.actionName)}</b> <span class="badge">${esc(x.schoolName)}</span><div class="muted">${esc(x.createdAt||"")} · ${esc(x.actor||"")}</div>${x.detail?`<div style="margin-top:5px">${esc(x.detail)}</div>`:""}<details><summary class="muted">查看修改前 / 修改后</summary><div class="json">修改前\\n${compactJson(x.before)}\\n\\n修改后\\n${compactJson(x.after)}</div></details></div>`).join(""):`<p class="muted">暂无运营操作记录</p>`}<div class="actions"><button class="btn" onclick="closeModal()">关闭</button></div>`)}catch(e){toast(e.message)}}\nasync function showEvents(id){const s=schools.find(x=>x.schoolID===id);try{const rows=await op(`/operator/schools/${id}/events`);openModal(`<h2>${esc(s?.schoolName||"客户")} · 商业历史</h2>${rows.length?rows.map(x=>`<div class="event"><b>${esc(x.action)}</b> <span class="badge">${esc(planName(x.planCode))}</span> <span class="badge ${statusClass(x.status)}">${esc(x.status||"")}</span><div class="muted">${esc(x.createdAt||"")}</div><div>${esc(x.detail||"")}</div></div>`).join(""):`<p class="muted">暂无历史</p>`}<div class="actions"><button class="btn" onclick="closeModal()">关闭</button></div>`)}catch(e){toast(e.message)}}\nfunction resetAdmin(id){const s=schools.find(x=>x.schoolID===id),def=s.admins?.[0]?.username||"";openModal(`<h2>${esc(s.schoolName)} · 重置管理员密码</h2><p class="note">重置后管理员首次登录必须修改密码。</p><div class="formgrid"><label>管理员账号<input id="rUser" value="${esc(def)}"></label><label>新临时密码<input id="rPass" placeholder="至少8位，含字母和数字"></label></div><div class="actions" style="margin-top:14px"><button class="btn danger" onclick="doReset(${id})">确认重置</button><button class="btn" onclick="closeModal()">取消</button></div>`)}\nasync function doReset(id){const p=$("#rPass").value;if(!confirm("确认重置管理员密码？"))return;try{const d=await op(`/operator/schools/${id}/reset-admin`,{method:"POST",body:JSON.stringify({username:$("#rUser").value.trim(),new_password:p})});openModal(`<h2>重置成功</h2><div class="secret">账号：${esc(d.username)}<br>临时密码：${esc(p)}</div><p class="note">请安全发送给客户，首次登录会要求修改密码。</p><div class="actions"><button class="btn" onclick="closeModal()">完成</button></div>`)}catch(e){toast(e.message)}}\nif(KEY){$("#key").value=KEY;connect()}\n</script></body></html>\n'

OFFLINE_HTML = '<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n<meta name="theme-color" content="#5964E8">\n<title>长缨辅学 · 离线模式</title>\n<style>\n:root{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","PingFang SC","Microsoft YaHei",sans-serif;color:#1f2937;background:#eef1f8}\n*{box-sizing:border-box}\nbody{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:calc(24px + env(safe-area-inset-top)) 24px calc(24px + env(safe-area-inset-bottom))}\n.card{width:min(680px,100%);background:#fff;border-radius:28px;padding:34px 28px;box-shadow:0 16px 50px rgba(32,45,90,.10)}\n.icon{width:112px;height:112px;border-radius:28px;background:#6567e8;display:flex;align-items:center;justify-content:center;font-size:58px;margin:0 auto 20px}\nh1{text-align:center;font-size:40px;margin:0 0 10px}\n.sub{text-align:center;color:#7b8499;font-size:20px;margin-bottom:28px}\n.box{background:#f6f7fb;border-radius:20px;padding:22px;font-size:18px;line-height:1.7;margin:18px 0}\n.badge{display:inline-block;padding:7px 12px;border-radius:999px;background:#fff4dc;color:#9a6413;font-weight:700}\nbutton{width:100%;border:0;border-radius:18px;padding:18px;font-size:20px;font-weight:700;margin-top:12px}\n.primary{background:#5964e8;color:white}.secondary{background:#eef1f6;color:#374151}\n.note{font-size:15px;color:#7b8499;line-height:1.7;margin-top:18px}\n</style>\n</head>\n<body>\n<div class="card">\n <div class="icon">📚</div>\n <h1>长缨辅学</h1>\n <div class="sub">离线模式</div>\n <div class="box">\n  <span class="badge">当前无网络连接</span>\n  <p>应用已从本地缓存启动，没有访问服务器。</p>\n  <p>联网后可继续登录、同步课堂数据、查看作业和家校沟通记录。</p>\n </div>\n <button class="primary" onclick="location.reload()">重新尝试联网</button>\n <button class="secondary" onclick="location.href=\'/?offline=1\'">返回本地应用界面</button>\n <div class="note">飞行模式下出现这个页面，说明长缨辅学的 PWA 离线兜底已经生效。</div>\n</div>\n</body>\n</html>'

@app.get("/offline", response_class=HTMLResponse)
def offline_page():
    return OFFLINE_HTML


@app.get("/version")
def version():
    return {"version":APP_VERSION,"status":"ok","schema":f"commercial-v{APP_VERSION.replace('.', '')}-operator-console"}


@app.get("/probe-v925")
def probe_v925():
    return {
        "running":Path(__file__).name,"version":APP_VERSION,"ok":True,"brand":"长缨辅学",
        "releaseChannel":RELEASE_CHANNEL,"releaseName":RELEASE_NAME,"operatorConsole":True,
        "orderLedger":True,"receivables":True,"partialPayments":True,"paymentTransactions":True,
        "refunds":True,"voidOrders":True,"renewalOrderLink":True,"financialKPIs":True,
        "schemaVersion":SCHEMA_VERSION
    }

@app.get("/probe-v924")
def probe_v924():
    return {
        "running":Path(__file__).name,"version":APP_VERSION,"ok":True,"brand":"长缨辅学",
        "releaseChannel":RELEASE_CHANNEL,"releaseName":RELEASE_NAME,"operatorConsole":True,
        "automaticTrialExpiry":True,"automaticReadOnlyOnExpiry":True,"renewalRegistration":True,
        "renewalHistory":True,"serviceExtension":True,"renewalDueKPI":True,"paymentRecord":True,
        "schemaVersion":SCHEMA_VERSION
    }

@app.get("/probe-v923")
def probe_v923():
    return {"running":Path(__file__).name,"version":APP_VERSION,"ok":True,"brand":"长缨辅学","releaseChannel":RELEASE_CHANNEL,"releaseName":RELEASE_NAME,"operatorConsole":True,"schoolPauseResume":True,"quotaOverrides":True,"planFilter":True,"operationLogs":True,"exactServiceEndDate":True,"schemaVersion":SCHEMA_VERSION}

@app.get("/probe-v922")
def probe_v922():
    return {"running":"app_v770.py","version":APP_VERSION,"ok":True,"brand":"长缨辅学","releaseChannel":RELEASE_CHANNEL,"releaseName":RELEASE_NAME,"operatorConsole":True,"commercialFollowUps":True,"followupDueKPI":True,"schemaVersion":SCHEMA_VERSION}

@app.get("/probe-v921")
def probe_v921():
    return {"running":"app_v770.py","version":APP_VERSION,"ok":True,"brand":"长缨辅学","releaseChannel":RELEASE_CHANNEL,"releaseName":RELEASE_NAME,"operatorConsole":True,"customerProfileEdit":True,"missingContactKPI":True,"schemaVersion":SCHEMA_VERSION}

@app.get("/probe-v920")
def probe_v920():
    return {"running":"app_v770.py","version":APP_VERSION,"ok":True,"brand":"长缨辅学","releaseChannel":RELEASE_CHANNEL,"releaseName":RELEASE_NAME,"operatorConsole":True,"customerCreate":True,"trialActivation":True,"renewalManagement":True,"expiryManagement":True,"adminPasswordReset":True,"paymentAutomation":False,"schemaVersion":SCHEMA_VERSION}

@app.get("/probe-v910")
def probe_v910():
    return {
        "running":"app_v770.py","version":APP_VERSION,"ok":True,"brand":"长缨辅学",
        "releaseChannel":RELEASE_CHANNEL,"releaseName":RELEASE_NAME,
        "commercialPlans":True,"subscriptionStates":True,"planLimits":True,
        "featureGates":True,"manualActivation":True,"paymentAutomation":False,
        "schemaVersion":SCHEMA_VERSION
    }

@app.get("/probe-v900")
def probe_v900():
    return {
        "running":"app_v770.py",
        "version":APP_VERSION,
        "ok":True,
        "brand":"长缨辅学",
        "releaseChannel":RELEASE_CHANNEL,
        "releaseName":RELEASE_NAME,
        "webPrimary":True,
        "schemaVersion":SCHEMA_VERSION,
        "studentGrowthProfile":True,
        "growthReportXlsx":True,
        "releaseReadiness":True,
        "legacyServiceWorkerRetired":True
    }

@app.get("/release")
def public_release():
    return {
        "product":"长缨辅学",
        "version":APP_VERSION,
        "channel":RELEASE_CHANNEL,
        "name":RELEASE_NAME,
        "schemaVersion":SCHEMA_VERSION,
        "webPrimary":True
    }

@app.get("/probe-v890")
def probe_v890():
    return {"running":"app_v770.py","version":"9.2.0","ok":True,"brand":"长缨辅学","webPrimary":True,"growthReportLocalized":True,"releaseReadiness":True,"legacyServiceWorkerRetired":True,"schemaVersion":"8.3.0"}

@app.get("/probe-v880")
def probe_v880():
    return {"running":"app_v770.py","version":"9.2.0","ok":True,"brand":"长缨辅学","studentGrowthProfile":True,"growthReportXlsx":True,"growthReportSheets":5,"webPrimary":True,"schemaVersion":"8.3.0"}

@app.get("/probe-v874")
def probe_v874():
    return {"running":"app_v770.py","version":"9.2.0","ok":True,"brand":"长缨辅学","studentGrowthProfile":True,"classHistoryMobileLayout":True,"classHistoryTimeAware":True,"schemaVersion":"8.3.0"}

@app.get("/probe-v873")
def probe_v873():
    return {"running":"app_v770.py","version":"9.2.0","ok":True,"brand":"长缨辅学","studentGrowthProfile":True,"classHistoryExactDedupe":True,"sameDayEventsPreserved":True,"classHistoryTimeAware":True,"schemaVersion":"8.3.0"}

@app.get("/probe-v872")
def probe_v872():
    return {"running":"app_v770.py","version":"9.2.0","ok":True,"brand":"长缨辅学","studentGrowthProfile":True,"classHistoryDayDedupe":True,"sameDayRestoreLabel":True,"schemaVersion":"8.3.0"}

@app.get("/probe-v871")
def probe_v871():
    return {"running":"app_v770.py","version":"9.2.0","ok":True,"brand":"长缨辅学","studentGrowthProfile":True,"classHistoryDates":True,"dedupeExactClassHistory":True,"schemaVersion":"8.3.0"}

@app.get("/probe-v870")
def probe_v870():
    return {"running":"app_v770.py","version":"9.2.0","ok":True,"brand":"长缨辅学","webPrimary":True,"studentGrowthProfile":True,"growthProfileSearchEntry":True,"growthProfileClassEntry":True,"legacyServiceWorkerRetired":True,"schemaVersion":"8.3.0"}

@app.get("/probe-v863")
def probe_v863():
    return {"running":"app_v770.py","version":"9.2.0","ok":True,"brand":"长缨辅学","webPrimary":True,"legacyServiceWorkerRetired":True,"cacheUnlock":True,"modalHidesBottomNav":True,"visualViewportKeyboardFix":True,"schemaVersion":"8.3.0"}

@app.get("/probe-v862")
def probe_v862():
    return {"running":"app_v770.py","version":"9.2.0","ok":True,"brand":"长缨辅学","webPrimary":True,"modalHidesBottomNav":True,"visualViewportKeyboardFix":True,"focusedFieldAutoScroll":True,"schemaVersion":"8.3.0"}

@app.get("/probe-v861")
def probe_v861():
    return {"running":"app_v770.py","version":"9.2.0","ok":True,"brand":"长缨辅学","webPrimary":True,"searchStatusZh":True,"mobileModalSafeBottom":True,"mobileScrollReset":True,"schemaVersion":"8.3.0"}

@app.get("/probe-v860")
def probe_v860():
    return {"running":"app_v770.py","version":"9.2.0","ok":True,"brand":"长缨辅学","webPrimary":True,"globalSearch":True,"teacherQuickActions":True,"schemaVersion":"8.3.0"}

@app.get("/probe-v843")
def probe_v843():
    return {"running":"app_v770.py","version":"9.2.0","ok":True,"brand":"长缨辅学","pwaTakeover":True,"offlineFallback":True,"cacheFirstNavigation":True,"serviceWorkerClaim":True,"standaloneManifest":True,"schemaVersion":"8.3.0"}

@app.get("/probe-v842")
def probe_v842():
    return {"running":"app_v770.py","version":"9.2.0","ok":True,"brand":"长缨辅学","iosSilentStart":True,"startupNetworkRequests":False,"cacheFirstNavigation":True,"manualSessionResume":True,"pwaInstall":True,"safeArea":True,"offlineShell":True,"deepLinks":True,"nativeScaffold":True,"notificationPermission":True,"schemaVersion":"8.3.0"}

@app.get("/probe-v841")
def probe_v841():
    return {"running":"app_v770.py","version":"9.2.0","ok":True,"brand":"长缨辅学","friendlyOffline":True,"autoReconnect":True,"pwaInstall":True,"safeArea":True,"offlineShell":True,"deepLinks":True,"nativeScaffold":True,"notificationPermission":True,"schemaVersion":"8.3.0"}

@app.get("/probe-v840")
def probe_v840():
    return {"running":"app_v770.py","version":"9.2.0","ok":True,"pwaInstall":True,"safeArea":True,"offlineShell":True,"deepLinks":True,"nativeScaffold":True,"notificationPermission":True,"schemaVersion":"8.3.0"}

@app.get("/probe-v831")
def probe_v831():
    return {"running":"app_v770.py","version":"9.2.0","ok":True,"systemHealth":True,"backupExport":True,"accountDataExport":True,"deletionRequests":True,"legalPages":True,"securityHeaders":True,"schemaMigrations":True}

@app.get("/probe-v820")
def probe_v820():
    return {"running":"app_v770.py","version":"9.2.0","ok":True,"dailyWorkbench":True,"activeReminders":True,"callbackReminders":True,"staleFollowupReminders":True,"teacherHomeSummary":True,"followupCenter":True}

@app.get("/probe-v810")
def probe_v810():
    return {"running":"app_v770.py","version":"9.2.0","ok":True,"followupCenter":True,"classTodos":True,"growthTimeline":True,"parentCommunicationHistory":True,"followupExport":True,"dailyWorkbench":True,"activeReminders":True,"callbackReminders":True}

@app.get("/probe-v790")
def probe_v790():
    return {"running":"app_v770.py","version":"9.2.0","ok":True,"groups":True,"growthDashboard":True,"homeroomDashboard":True,"academicBehavior":True,"followupCenter":True,"growthTimeline":True,"parentCommunicationHistory":True,"dailyWorkbench":True,"activeReminders":True}

@app.get("/probe-v740")
def probe_v740():
    return {"running":"app_v740.py","version":"7.4.0","ok":True,"assignmentSnapshots":True,"classHistory":True,"customTeaching":True,"adaptiveABC":True,"stableFixes":True}

@app.get("/probe-v730")
def probe_v730_compat():
    return {"running":"app_v740.py","version":"7.4.0","ok":True,"compat":"v730"}

def fresh_html():
    return HTMLResponse(
        INDEX_HTML,
        headers={
            "Cache-Control":"no-store, no-cache, must-revalidate, max-age=0",
            "Pragma":"no-cache",
            "Expires":"0",
            "X-Changying-Version":APP_VERSION
        }
    )

@app.get("/", response_class=HTMLResponse)
def home():return fresh_html()

@app.get("/fresh-v820", response_class=HTMLResponse)
def fresh_v820():return fresh_html()

@app.get("/fresh-v770", response_class=HTMLResponse)
def fresh_v770():return fresh_html()

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

@app.get("/icon-180.png")
def icon_180():return Response(ICON_180_PNG,media_type="image/png",headers={"Cache-Control":"public, max-age=86400"})

@app.get("/icon-192.png")
def icon_192():return Response(ICON_192_PNG,media_type="image/png",headers={"Cache-Control":"public, max-age=86400"})

@app.get("/icon-512.png")
def icon_512():return Response(ICON_512_PNG,media_type="image/png",headers={"Cache-Control":"public, max-age=86400"})

@app.get("/sw.js")
def service_worker():
    return Response(
        SERVICE_WORKER,
        media_type="application/javascript",
        headers={
            "Cache-Control":"no-store, no-cache, must-revalidate, max-age=0",
            "Pragma":"no-cache",
            "Expires":"0",
            "Service-Worker-Allowed":"/",
            "X-Changying-SW":"retired-v924"
        }
    )
