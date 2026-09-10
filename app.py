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

def get_db():
    d=SessionLocal()
    try: yield d
    finally: d.close()

# ---------------- Authentication ----------------
JWT_SECRET=os.getenv("JWT_SECRET","CHANGE-ME-IN-PRODUCTION-"+secrets.token_urlsafe(24))
JWT_ALG="HS256"
ACCESS_HOURS=int(os.getenv("ACCESS_TOKEN_HOURS","12"))

def hash_password(password,salt=None):
    salt=salt or secrets.token_hex(16)
    digest=hashlib.scrypt(password.encode(),salt=salt.encode(),n=2**14,r=8,p=1,dklen=32).hex()
    return f"scrypt${salt}${digest}"

def verify_password(password,stored):
    try:
        alg,salt,digest=stored.split("$",2)
        return alg=="scrypt" and secrets.compare_digest(hash_password(password,salt).split("$",2)[2],digest)
    except: return False

def make_token(u):
    now=datetime.now(timezone.utc)
    return jwt.encode({"sub":str(u.id),"role":u.role,"school_id":u.school_id,"iat":now,"exp":now+timedelta(hours=ACCESS_HOURS)},JWT_SECRET,algorithm=JWT_ALG)

def current_user(authorization:Optional[str]=Header(default=None),db:Session=Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "): raise HTTPException(401,"未登录")
    try: uid=int(jwt.decode(authorization[7:],JWT_SECRET,algorithms=[JWT_ALG])["sub"])
    except jwt.ExpiredSignatureError: raise HTTPException(401,"登录已过期，请重新登录")
    except: raise HTTPException(401,"登录令牌无效")
    u=db.get(User,uid)
    if not u or not u.active: raise HTTPException(401,"账号不可用")
    return u

def need(u,*roles):
    if u.role not in roles: raise HTTPException(403,"无权限")

# ---------------- Schemas ----------------
class LoginBody(BaseModel): username:str;password:str
class UserCreate(BaseModel): name:str;username:str;password:str;role:str
class ClassCreate(BaseModel): name:str;grade:int
class StudentCreate(BaseModel): name:str;username:str;password:str;grade:int;class_id:int;parent_username:Optional[str]=None
class QuestionCreate(BaseModel): grade:int;subject:str;textbook:str;semester:str;unit:str;knowledge:str;text:str;options:list[str];correct_index:int;explanation:str=""
class PaperCreate(BaseModel): title:str;grade:int;subject:str;textbook:str="";unit:str="";question_ids:list[int]
class AssignmentCreate(BaseModel): title:str;class_id:int;paper_id:int;due_date:str
class AnswerItem(BaseModel): question_id:int;selected_index:int;correct:bool
class SubmitBody(BaseModel): title:Optional[str]=None;correct:int;total:int;score:int;answers:list[AnswerItem]=[]

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
def uj(u): return {"id":u.id,"username":u.username,"name":u.name,"role":u.role,"grade":u.grade}
def qj(q): return {"id":q.id,"grade":q.grade,"subject":q.subject,"textbook":q.textbook,"semester":q.semester,"unit":q.unit,"knowledge":q.knowledge,"text":q.text,"options":json.loads(q.options_json),"correctIndex":q.correct_index,"explanation":q.explanation}
def pj(p): return {"id":p.id,"title":p.title,"grade":p.grade,"subject":p.subject,"textbook":p.textbook,"unit":p.unit,"questionIDs":json.loads(p.question_ids_json)}
def audit(db,u,action,detail=""):
    db.add(AuditLog(school_id=u.school_id,user_id=u.id,action=action,detail=detail))
def aj(db,a):
    p=db.get(Paper,a.paper_id);n=db.scalar(select(func.count()).select_from(Submission).where(Submission.assignment_id==a.id)) or 0
    return {"id":a.id,"title":a.title,"classID":a.class_id,"paperID":a.paper_id,"dueDate":a.due_date,"paper":pj(p) if p else None,"submissionCount":n}
def progress_for(db,sid,school_id):
    subs=db.scalars(select(Submission).where(Submission.school_id==school_id,Submission.student_id==sid).order_by(Submission.submitted_at.desc())).all()
    avg=round(sum(x.score for x in subs)/len(subs)) if subs else 0
    ans=[]
    for s in subs:
        try: ans += json.loads(s.answers_json or "[]")
        except: pass
    know={}
    for a in ans:
        q=db.get(Question,a.get("question_id"))
        if q and q.school_id==school_id:
            hit,total=know.get(q.knowledge,(0,0));know[q.knowledge]=(hit+(1 if a.get("correct") else 0),total+1)
    items=[{"knowledge":k,"accuracy":round(v[0]/v[1]*100) if v[1] else 0,"answered":v[1]} for k,v in know.items()]
    items.sort(key=lambda x:x["accuracy"])
    return {"avgScore":avg,"totalAnswered":len(ans),"submissions":len(subs),"knowledge":items}

# ---------------- App ----------------
app=FastAPI(title="小学题库 V7 iPhone上传版",version="7.1")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=False,allow_methods=["*"],allow_headers=["*"])

@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
    with SessionLocal() as db: seed(db)

@app.get("/health")
def health(db:Session=Depends(get_db)):
    db.scalar(select(func.count()).select_from(School))
    return {"status":"ok","database":"connected"}

@app.post("/login")
def login(b:LoginBody,db:Session=Depends(get_db)):
    u=db.scalar(select(User).where(User.username==b.username))
    if not u or not verify_password(b.password,u.password_hash): raise HTTPException(401,"账号或密码错误")
    return {"token":make_token(u),"role":u.role,"userID":u.id,"name":u.name,"grade":u.grade}

@app.get("/questions")
def questions(grade:int|None=None,subject:str|None=None,textbook:str|None=None,unit:str|None=None,u:User=Depends(current_user),db:Session=Depends(get_db)):
    s=select(Question).where(Question.school_id==u.school_id)
    if grade is not None:s=s.where(Question.grade==grade)
    if subject:s=s.where(Question.subject==subject)
    if textbook:s=s.where(Question.textbook==textbook)
    if unit:s=s.where(Question.unit==unit)
    return [qj(x) for x in db.scalars(s.order_by(Question.id)).all()]

@app.post("/questions")
def addq(b:QuestionCreate,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin","teacher")
    q=Question(school_id=u.school_id,grade=b.grade,subject=b.subject,textbook=b.textbook,semester=b.semester,unit=b.unit,knowledge=b.knowledge,text=b.text,options_json=json.dumps(b.options,ensure_ascii=False),correct_index=b.correct_index,explanation=b.explanation,creator_id=u.id)
    db.add(q);db.flush();audit(db,u,"question.create",str(q.id));db.commit();return qj(q)

@app.get("/admin/overview")
def admin_overview(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");sid=u.school_id
    cnt=lambda m,*c: db.scalar(select(func.count()).select_from(m).where(*c)) or 0
    books=db.scalars(select(Question.textbook).where(Question.school_id==sid).distinct()).all()
    return {"teachers":cnt(User,User.school_id==sid,User.role=="teacher"),"students":cnt(User,User.school_id==sid,User.role=="student"),"parents":cnt(User,User.school_id==sid,User.role=="parent"),"classes":cnt(SchoolClass,SchoolClass.school_id==sid),"questions":cnt(Question,Question.school_id==sid),"papers":cnt(Paper,Paper.school_id==sid),"assignments":cnt(Assignment,Assignment.school_id==sid),"submissions":cnt(Submission,Submission.school_id==sid),"textbooks":list(books)}

@app.get("/admin/users")
def admin_users(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");return [uj(x) for x in db.scalars(select(User).where(User.school_id==u.school_id).order_by(User.id.desc())).all()]

@app.post("/admin/users")
def admin_user(b:UserCreate,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin")
    if b.role not in ("teacher","parent"):raise HTTPException(400,"仅可创建教师或家长")
    if db.scalar(select(User).where(User.username==b.username)):raise HTTPException(400,"账号已存在")
    x=User(school_id=u.school_id,username=b.username,password_hash=hash_password(b.password),name=b.name,role=b.role);db.add(x);db.commit();db.refresh(x);return uj(x)

@app.get("/admin/import-jobs")
def jobs(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin");rows=db.scalars(select(ImportJob).where(ImportJob.school_id==u.school_id).order_by(ImportJob.id.desc()).limit(20)).all()
    return [{"id":x.id,"filename":x.filename,"status":x.status,"summary":x.summary,"createdAt":x.created_at.isoformat()} for x in rows]

@app.post("/admin/import-xlsx")
async def import_xlsx(file:UploadFile=File(...),u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"admin")
    if not (file.filename or "").lower().endswith(".xlsx"):raise HTTPException(400,"请上传 XLSX")
    from openpyxl import load_workbook
    try:wb=load_workbook(io.BytesIO(await file.read()),data_only=True)
    except:raise HTTPException(400,"Excel 无法读取")
    qcount=scount=tcount=skipped=0
    if "题库导入" in wb.sheetnames:
        for row in wb["题库导入"].iter_rows(min_row=2,values_only=True):
            if not row or not row[0]:continue
            try:
                grade=int(row[0]);sub=str(row[1]).strip();opts=[str(row[i]).strip() for i in range(7,11)];correct=int(row[11])-1
                db.add(Question(school_id=u.school_id,grade=grade,subject=sub,textbook=str(row[2]).strip(),semester=str(row[3]).strip(),unit=str(row[4]).strip(),knowledge=str(row[5]).strip(),text=str(row[6]).strip(),options_json=json.dumps(opts,ensure_ascii=False),correct_index=correct,explanation=str(row[12] or ""),creator_id=u.id));qcount+=1
            except:skipped+=1
    summary=f"题库 {qcount} 道，教师 {tcount} 名，学生 {scount} 名，跳过 {skipped} 行"
    db.add(ImportJob(school_id=u.school_id,filename=file.filename or "upload.xlsx",status="成功",summary=summary,user_id=u.id));db.commit()
    return {"summary":summary}

@app.get("/teacher/classes")
def tclasses(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher");rows=db.scalars(select(SchoolClass).where(SchoolClass.school_id==u.school_id,SchoolClass.teacher_id==u.id).order_by(SchoolClass.id.desc())).all()
    return [{"id":c.id,"name":c.name,"grade":c.grade,"teacherID":c.teacher_id,"studentCount":db.scalar(select(func.count()).select_from(ClassStudent).where(ClassStudent.class_id==c.id)) or 0} for c in rows]

@app.post("/teacher/classes")
def addclass(b:ClassCreate,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher");c=SchoolClass(school_id=u.school_id,name=b.name,grade=b.grade,teacher_id=u.id);db.add(c);db.commit();db.refresh(c);return {"id":c.id,"name":c.name,"grade":c.grade,"teacherID":c.teacher_id,"studentCount":0}

@app.get("/teacher/classes/{cid}/students")
def cstudents(cid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher")
    c=db.scalar(select(SchoolClass).where(SchoolClass.id==cid,SchoolClass.school_id==u.school_id,SchoolClass.teacher_id==u.id))
    if not c:raise HTTPException(404,"班级不存在")
    rows=db.scalars(select(User).join(ClassStudent,ClassStudent.student_id==User.id).where(ClassStudent.class_id==cid)).all()
    out=[]
    for s in rows:
        p=db.scalar(select(User).join(ParentStudent,ParentStudent.parent_id==User.id).where(ParentStudent.student_id==s.id).limit(1))
        d=uj(s);d["parentName"]=p.name if p else None;out.append(d)
    return out

@app.post("/teacher/students")
def addstudent(b:StudentCreate,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher")
    if db.scalar(select(User).where(User.username==b.username)):raise HTTPException(400,"学生账号已存在")
    s=User(school_id=u.school_id,username=b.username,password_hash=hash_password(b.password),name=b.name,role="student",grade=b.grade);db.add(s);db.flush();db.add(ClassStudent(class_id=b.class_id,student_id=s.id))
    if b.parent_username:
        p=db.scalar(select(User).where(User.school_id==u.school_id,User.username==b.parent_username,User.role=="parent"))
        if p:db.add(ParentStudent(parent_id=p.id,student_id=s.id))
    db.commit();return uj(s)

@app.post("/teacher/papers")
def addpaper(b:PaperCreate,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher");p=Paper(school_id=u.school_id,title=b.title,grade=b.grade,subject=b.subject,textbook=b.textbook,unit=b.unit,question_ids_json=json.dumps(b.question_ids),teacher_id=u.id);db.add(p);db.commit();db.refresh(p);return pj(p)

@app.post("/teacher/assignments")
def addassignment(b:AssignmentCreate,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher");a=Assignment(school_id=u.school_id,title=b.title,class_id=b.class_id,paper_id=b.paper_id,due_date=b.due_date);db.add(a);db.commit();db.refresh(a);return aj(db,a)

@app.get("/teacher/assignments")
def tassign(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher");rows=db.scalars(select(Assignment).join(SchoolClass,Assignment.class_id==SchoolClass.id).where(Assignment.school_id==u.school_id,SchoolClass.teacher_id==u.id).order_by(Assignment.id.desc())).all();return [aj(db,a) for a in rows]

@app.get("/teacher/assignments/{aid}/submissions")
def tsubs(aid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher");rows=db.execute(select(Submission,User).join(User,Submission.student_id==User.id).where(Submission.assignment_id==aid).order_by(Submission.score.desc())).all()
    return [{"id":s.id,"studentName":stu.name,"score":s.score,"correct":s.correct,"total":s.total,"submittedAt":s.submitted_at.isoformat()} for s,stu in rows]

@app.get("/teacher/dashboard")
def tdashboard(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher");classes=db.scalars(select(SchoolClass).where(SchoolClass.school_id==u.school_id,SchoolClass.teacher_id==u.id)).all();cids=[c.id for c in classes]
    sids=db.scalars(select(ClassStudent.student_id).where(ClassStudent.class_id.in_(cids))).all() if cids else []
    subs=db.scalars(select(Submission).where(Submission.school_id==u.school_id,Submission.student_id.in_(sids))).all() if sids else []
    avg=round(sum(x.score for x in subs)/len(subs)) if subs else 0
    return {"classes":len(classes),"students":len(set(sids)),"assignments":len(db.scalars(select(Assignment).where(Assignment.school_id==u.school_id,Assignment.class_id.in_(cids))).all()) if cids else 0,"submissions":len(subs),"avgAccuracy":avg,"weakKnowledge":[]}

@app.get("/teacher/analytics")
def tanalytics(u:User=Depends(current_user),db:Session=Depends(get_db)):
    d=tdashboard(u,db);return {"totalSubmissions":d["submissions"],"avgScore":d["avgAccuracy"],"avgAccuracy":d["avgAccuracy"],"knowledge":[]}

@app.get("/student/assignments")
def sassign(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"student");rows=db.scalars(select(Assignment).join(ClassStudent,Assignment.class_id==ClassStudent.class_id).where(Assignment.school_id==u.school_id,ClassStudent.student_id==u.id).order_by(Assignment.id.desc())).all();return [aj(db,a) for a in rows]

@app.get("/papers/{pid}/questions")
def paperq(pid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    p=db.scalar(select(Paper).where(Paper.id==pid,Paper.school_id==u.school_id))
    if not p:raise HTTPException(404,"试卷不存在")
    return [qj(q) for qid in json.loads(p.question_ids_json) if (q:=db.get(Question,qid)) and q.school_id==u.school_id]

def save_sub(db,u,aid,title,b):
    answers=json.dumps([x.model_dump() for x in b.answers],ensure_ascii=False)
    if aid is not None:
        old=db.scalar(select(Submission).where(Submission.assignment_id==aid,Submission.student_id==u.id))
        if old:
            old.title=title;old.score=b.score;old.correct=b.correct;old.total=b.total;old.answers_json=answers;old.submitted_at=datetime.utcnow();return old
    s=Submission(school_id=u.school_id,assignment_id=aid,student_id=u.id,title=title,score=b.score,correct=b.correct,total=b.total,answers_json=answers);db.add(s);db.flush();return s

@app.post("/student/assignments/{aid}/submit")
def ssubmit(aid:int,b:SubmitBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"student");a=db.get(Assignment,aid)
    if not a or a.school_id!=u.school_id:raise HTTPException(403,"不能提交")
    s=save_sub(db,u,aid,a.title,b);db.commit();return {"id":s.id,"score":s.score}

@app.post("/student/practice-submit")
def psubmit(b:SubmitBody,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"student");s=save_sub(db,u,None,b.title or "自主练习",b);db.commit();return {"id":s.id,"score":s.score}

@app.get("/student/progress")
def sprogress(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"student");return progress_for(db,u.id,u.school_id)

@app.get("/leaderboard")
def leaderboard(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"teacher","student")
    cids=db.scalars(select(ClassStudent.class_id).where(ClassStudent.student_id==u.id)).all() if u.role=="student" else db.scalars(select(SchoolClass.id).where(SchoolClass.school_id==u.school_id,SchoolClass.teacher_id==u.id)).all()
    out=[]
    for cid in cids:
        c=db.get(SchoolClass,cid)
        for sid in db.scalars(select(ClassStudent.student_id).where(ClassStudent.class_id==cid)).all():
            stu=db.get(User,sid);rows=db.scalars(select(Submission).where(Submission.school_id==u.school_id,Submission.student_id==sid)).all()
            if rows and stu:out.append({"studentName":stu.name,"className":c.name if c else "","avgScore":round(sum(x.score for x in rows)/len(rows)),"submissions":len(rows)})
    out.sort(key=lambda x:(-x["avgScore"],-x["submissions"]));return out

@app.get("/parent/children")
def children(u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"parent");rows=db.scalars(select(User).join(ParentStudent,ParentStudent.student_id==User.id).where(ParentStudent.parent_id==u.id,User.school_id==u.school_id)).all();out=[]
    for s in rows:
        p=progress_for(db,s.id,u.school_id);out.append({"id":s.id,"name":s.name,"grade":s.grade,"className":"","avgScore":p["avgScore"]})
    return out

@app.get("/parent/children/{sid}/progress")
def child_progress(sid:int,u:User=Depends(current_user),db:Session=Depends(get_db)):
    need(u,"parent")
    if not db.scalar(select(ParentStudent).where(ParentStudent.parent_id==u.id,ParentStudent.student_id==sid)):raise HTTPException(403,"未绑定")
    s=db.get(User,sid);p=progress_for(db,sid,u.school_id);p.update({"studentName":s.name,"grade":s.grade});return p

# ---------------- Embedded frontend ----------------
INDEX_HTML = '<!doctype html>\n<html lang="zh-CN">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n  <meta name="theme-color" content="#5362e8">\n  <meta name="apple-mobile-web-app-capable" content="yes">\n  <meta name="apple-mobile-web-app-title" content="小学题库">\n  <title>小学题库 V7</title>\n  \n  \n  <style>\n\n:root{\n  --bg:#f4f6fb;--card:#fff;--text:#1f2738;--muted:#778095;--line:#e5e8f0;\n  --primary:#5362e8;--soft:#eef0ff;--green:#18855d;--red:#d6485e;--amber:#d98b25;\n  --shadow:0 14px 38px rgba(38,48,95,.10)\n}\n*{box-sizing:border-box}\nhtml,body{margin:0;min-height:100%;font-family:Inter,"PingFang SC","Microsoft YaHei",system-ui,sans-serif;background:var(--bg);color:var(--text)}\nbutton,input,select,textarea{font:inherit} button{cursor:pointer}\n.hidden{display:none!important}.muted{color:var(--muted)}\n.login-screen{min-height:100vh;display:grid;place-items:center;padding:20px;background:linear-gradient(135deg,#edf0ff,#fafbff)}\n.login-card{width:min(430px,100%);background:#fff;border:1px solid var(--line);border-radius:28px;padding:28px;box-shadow:var(--shadow)}\n.logo{width:84px;height:84px;border-radius:26px;display:grid;place-items:center;font-size:42px;margin:auto;background:linear-gradient(135deg,var(--primary),#8b75ef)}\n.login-card h1{text-align:center;margin:12px 0 3px}.login-card>p{text-align:center;margin:0 0 22px}\nlabel{display:block;font-size:12px;font-weight:800;margin:12px 0 6px}\ninput,select,textarea{width:100%;padding:11px 12px;border:1px solid var(--line);border-radius:12px;background:#fff;color:var(--text);outline:none}\ninput:focus,select:focus,textarea:focus{border-color:#9ba5f1;box-shadow:0 0 0 3px rgba(83,98,232,.10)}\ntextarea{min-height:100px;resize:vertical}\n.btn{border:0;border-radius:12px;padding:10px 13px}.primary{background:var(--primary);color:#fff;font-weight:800}.secondary{background:#eef1f6;color:#3b455e;font-weight:700}.danger{background:#fff0f2;color:var(--red)}.full{width:100%;margin-top:11px}\n.demo-box{margin-top:16px;padding:12px;background:#f7f8fc;border-radius:12px;color:var(--muted);font-size:12px;line-height:1.7}\n\n.shell{display:grid;grid-template-columns:258px minmax(0,1fr);min-height:100vh}\n.sidebar{height:100vh;position:sticky;top:0;background:#fff;border-right:1px solid var(--line);padding:17px;display:flex;flex-direction:column;z-index:30}\n.brand{display:flex;align-items:center;gap:10px;padding:5px 5px 18px}.brand>span{font-size:24px;background:var(--soft);padding:9px;border-radius:14px}.brand b,.brand small{display:block}.brand small{color:var(--muted);font-size:11px;margin-top:2px}\nnav{display:grid;gap:5px}.nav-btn{border:0;background:transparent;color:#626c81;border-radius:12px;padding:11px 12px;display:flex;gap:10px;align-items:center;text-align:left}.nav-btn.active{background:var(--soft);color:var(--primary);font-weight:800}\n.sidebar-foot{margin-top:auto}.user-badge{font-size:13px;padding:10px 4px}.user-badge b,.user-badge span{display:block}.user-badge span{color:var(--muted);font-size:12px}\n.main{padding:28px;min-width:0}.mobile-header{display:none}\n.page-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;margin-bottom:18px}.page-head h1{margin:0 0 5px;font-size:26px}.page-head p{margin:0;color:var(--muted)}\n.actions{display:flex;gap:8px;flex-wrap:wrap}\n.card{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:18px;box-shadow:0 8px 24px rgba(38,48,95,.05)}\n.hero{border-radius:23px;padding:24px;background:linear-gradient(135deg,#5362e8,#8a72ec);color:#fff}.hero p{color:#e7e9ff;max-width:760px}\n.grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.grid3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.grid4{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}\n.stat b{display:block;font-size:28px;color:var(--primary)}.stat small{color:var(--muted)}\n.section{margin-top:18px}.section h2{font-size:17px;margin:0 0 11px}\n.list{display:grid;gap:9px}.item{background:#fff;border:1px solid var(--line);border-radius:15px;padding:13px 14px;display:flex;justify-content:space-between;align-items:center;gap:10px}.item-main{min-width:0}.item-main b{display:block;margin-bottom:4px}.item-main small{color:var(--muted)}\n.badge{display:inline-flex;border-radius:999px;padding:4px 8px;background:var(--soft);color:var(--primary);font-size:11px;font-weight:800}.badge.green{background:#eaf8f2;color:var(--green)}.badge.red{background:#fff0f2;color:var(--red)}\n.filters{display:flex;gap:9px;flex-wrap:wrap;margin-bottom:12px}.filters>*{width:auto;min-width:130px;flex:0 1 auto}\n.small{font-size:12px;padding:7px 9px}.empty{text-align:center;color:var(--muted);padding:36px}\n.table-wrap{overflow:auto}.table{width:100%;border-collapse:collapse;min-width:720px}.table th,.table td{padding:11px;border-bottom:1px solid var(--line);font-size:13px;text-align:left}.table th{color:var(--muted);font-weight:700}\n.progress{height:9px;border-radius:999px;background:#eaedf4;overflow:hidden}.progress i{height:100%;display:block;background:var(--primary)}\n.question{font-size:22px;line-height:1.6;font-weight:800;margin:18px 0}.option{width:100%;display:flex;align-items:center;gap:10px;text-align:left;padding:13px;margin:9px 0;background:#fff;border:1px solid var(--line);border-radius:14px}.option.selected{background:var(--soft);border-color:#a5adf3}.option.correct{background:#edf9f4;border-color:#75cfaa}.option.wrong{background:#fff1f3;border-color:#ef929e}.letter{width:31px;height:31px;border-radius:50%;display:grid;place-items:center;background:#f0f2f7;font-weight:800;flex:none}.answer{margin-top:14px;padding:13px;border-radius:14px;background:#f6f7fb;line-height:1.6}\n.chart-row{display:grid;grid-template-columns:repeat(10,1fr);align-items:end;height:180px;gap:8px;padding:10px 4px 0}.bar{background:linear-gradient(180deg,#7580ef,#5362e8);border-radius:8px 8px 2px 2px;min-height:4px;position:relative}.bar span{position:absolute;bottom:-24px;left:50%;transform:translateX(-50%);font-size:10px;color:var(--muted);white-space:nowrap}\n.knowledge{display:grid;gap:9px}.knowledge-row{display:grid;grid-template-columns:minmax(110px,1fr) 3fr 55px;gap:10px;align-items:center}.knowledge-row small{overflow:hidden;text-overflow:ellipsis}.knowledge-meter{height:9px;background:#edf0f5;border-radius:999px;overflow:hidden}.knowledge-meter i{display:block;height:100%;background:var(--primary)}\n.toast{position:fixed;top:18px;right:18px;z-index:100;background:#252b3e;color:#fff;padding:11px 15px;border-radius:12px;box-shadow:var(--shadow);opacity:0;transform:translateY(-10px);transition:.2s;pointer-events:none}.toast.show{opacity:1;transform:none}\ndialog{border:0;background:transparent;padding:16px;width:min(700px,100%)}dialog::backdrop{background:rgba(22,27,42,.47)}.modal-card{background:#fff;border-radius:22px;padding:18px;max-height:88vh;overflow:auto;box-shadow:var(--shadow)}.modal-head{display:flex;align-items:center;justify-content:space-between}.modal-head h3{margin:0}.icon-btn{border:0;background:transparent;padding:8px}\n.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}\n.note{font-size:12px;background:#fff7e7;color:#7b5719;padding:10px 12px;border-radius:12px}\n.rank1{font-weight:900;color:#b37511}\n@media(max-width:960px){\n .shell{grid-template-columns:1fr}.sidebar{position:fixed;left:-270px;width:258px;transition:.2s;box-shadow:var(--shadow)}.sidebar.open{left:0}\n .main{padding:0 14px 25px}.mobile-header{display:flex;position:sticky;top:0;z-index:20;margin:0 -14px 18px;padding:12px 14px;align-items:center;justify-content:space-between;background:rgba(255,255,255,.96);border-bottom:1px solid var(--line)}\n .grid4{grid-template-columns:repeat(2,1fr)}\n}\n@media(max-width:650px){\n .grid2,.grid3{grid-template-columns:1fr}.page-head{display:block}.page-head .actions{margin-top:10px}\n .form-grid{grid-template-columns:1fr}.filters>*{flex:1}.question{font-size:19px}\n .knowledge-row{grid-template-columns:100px 1fr 45px}\n}\n\n</style>\n</head>\n<body>\n<div id="toast" class="toast"></div>\n\n<section id="loginScreen" class="login-screen">\n  <div class="login-card">\n    <div class="logo">📚</div>\n    <h1>小学题库</h1>\n    <p class="muted">V7 正式云端版</p>\n    <label>服务器地址（网址版保持默认即可）</label>\n    <input id="serverURL" placeholder="http://127.0.0.1:8000">\n    <label>账号</label>\n    <input id="username" value="admin" autocomplete="username">\n    <label>密码</label>\n    <input id="password" type="password" value="123456" autocomplete="current-password">\n    <button id="loginBtn" class="btn primary full">登录</button>\n    <button id="offlineBtn" class="btn secondary full">离线学生体验</button>\n    <div class="demo-box">\n      管理员：admin / 123456<br>\n      教师：teacher1 / 123456<br>\n      学生：student1 / 123456<br>\n      家长：parent1 / 123456\n    </div>\n  </div>\n</section>\n\n<div id="shell" class="shell hidden">\n  <aside id="sidebar" class="sidebar">\n    <div class="brand"><span>📚</span><div><b>小学题库</b><small>V7 云端版</small></div></div>\n    <nav id="nav"></nav>\n    <div class="sidebar-foot">\n      <div id="userBadge" class="user-badge"></div>\n      <button id="logoutBtn" class="btn secondary full">退出</button>\n    </div>\n  </aside>\n  <main class="main">\n    <header class="mobile-header">\n      <button id="menuBtn" class="icon-btn">☰</button>\n      <b>小学题库 V7</b>\n      <span></span>\n    </header>\n    <div id="page"></div>\n  </main>\n</div>\n\n<dialog id="modal">\n  <div class="modal-card">\n    <div class="modal-head"><h3 id="modalTitle"></h3><button id="modalClose" class="icon-btn">✕</button></div>\n    <div id="modalBody"></div>\n  </div>\n</dialog>\n\n<script>\n\nconst $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];\nconst defaultAPI=(location.protocol==="http:"||location.protocol==="https:")?location.origin:"http://127.0.0.1:8000";\nconst state={\n api:localStorage.getItem("v6Server")||defaultAPI,\n token:localStorage.getItem("v6Token")||"",\n user:JSON.parse(localStorage.getItem("v6User")||"null"),\n offline:false,page:""\n};\nconst offlineBank=[\n {id:1,grade:1,subject:"数学",textbook:"人教版",semester:"上册",unit:"第一单元",knowledge:"20以内加法",text:"7 + 5 = ?",options:["10","11","12","13"],correctIndex:2,explanation:"7+5=12。"},\n {id:2,grade:3,subject:"数学",textbook:"人教版",semester:"上册",unit:"第一单元",knowledge:"时分秒",text:"1分钟等于多少秒？",options:["30","60","90","100"],correctIndex:1,explanation:"1分钟=60秒。"},\n {id:3,grade:3,subject:"语文",textbook:"人教版",semester:"上册",unit:"第一单元",knowledge:"词语",text:"“绚丽多彩”的近义词是？",options:["五颜六色","灰暗无光","一模一样","安安静静"],correctIndex:0,explanation:"与“五颜六色”意思相近。"},\n {id:4,grade:3,subject:"英语",textbook:"人教PEP",semester:"上册",unit:"Unit 1",knowledge:"单词",text:"“尺子”的英文是？",options:["book","ruler","pencil","bag"],correctIndex:1,explanation:"ruler=尺子。"},\n {id:5,grade:5,subject:"数学",textbook:"北师大版",semester:"下册",unit:"第三单元",knowledge:"分数",text:"1/2 + 1/4 = ?",options:["1/6","2/6","3/4","1"],correctIndex:2,explanation:"通分后为3/4。"}\n];\n\nconst menus={\n admin:[["admin","🛡️","平台总览"],["users","👥","账号管理"],["imports","📥","批量导入"],["catalog","📚","教材题库"],["system","⚙️","系统设置"]],\n teacher:[["teacher","📊","教师工作台"],["classes","👥","班级学生"],["catalog","📚","教材题库"],["papers","📝","组卷作业"],["analytics","📈","学情分析"],["leaderboard","🏆","排行榜"],["account","👤","我的"]],\n student:[["student","🏠","学习首页"],["assignments","📝","我的作业"],["practice","✏️","自主练习"],["progress","📈","我的学情"],["leaderboard","🏆","班级排行"],["account","👤","我的"]],\n parent:[["parent","👨\u200d👩\u200d👧","家长首页"],["childProgress","📈","孩子学情"],["account","👤","我的"]],\n offline:[["practice","✏️","离线练习"],["account","👤","本机设置"]]\n};\n\nfunction esc(v=""){return String(v).replace(/[&<>"\']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",\'"\':"&quot;","\'":"&#039;"}[m]))}\nfunction toast(msg){const t=$("#toast");t.textContent=msg;t.classList.add("show");setTimeout(()=>t.classList.remove("show"),2300)}\nfunction roleName(r){return ({admin:"管理员",teacher:"教师",student:"学生",parent:"家长"})[r]||r}\nfunction head(t,s,a=""){return `<div class="page-head"><div><h1>${t}</h1><p>${s}</p></div><div class="actions">${a}</div></div>`}\nfunction stat(v,t){return `<div class="card stat"><b>${esc(v)}</b><small>${esc(t)}</small></div>`}\nfunction empty(t){return `<div class="card empty">${esc(t)}</div>`}\nfunction modal(title,body){$("#modalTitle").textContent=title;$("#modalBody").innerHTML=body;$("#modal").showModal()}\nfunction closeModal(){$("#modal").close()}\nfunction pct(n,d){return d?Math.round(n/d*100):0}\nasync function api(path,opt={}){\n if(state.offline)throw new Error("离线模式无法访问服务器");\n const h={"Content-Type":"application/json",...(opt.headers||{})}; if(state.token)h.Authorization=`Bearer ${state.token}`;\n const r=await fetch(state.api+path,{...opt,headers:h});let d={};try{d=await r.json()}catch{}\n if(!r.ok)throw new Error(d.detail||`请求失败 ${r.status}`);return d\n}\nfunction renderNav(){\n const key=state.offline?"offline":state.user?.role;\n $("#nav").innerHTML=(menus[key]||[]).map(([id,ico,name])=>`<button class="nav-btn ${state.page===id?"active":""}" data-page="${id}"><span>${ico}</span>${name}</button>`).join("");\n $$(".nav-btn").forEach(b=>b.onclick=()=>go(b.dataset.page));\n $("#userBadge").innerHTML=state.offline?`<b>离线学生</b><span>本机体验</span>`:`<b>${esc(state.user?.name||"")}</b><span>${roleName(state.user?.role)}</span>`;\n}\nasync function go(p){\n state.page=p;renderNav();$("#sidebar").classList.remove("open");\n const fn={admin,users,imports,catalog,system,teacher,classes,papers,analytics,leaderboard,student,assignments,practice,progress,parent,childProgress,account}[p]||practice;\n try{await fn()}catch(e){$("#page").innerHTML=empty(e.message)}\n}\n\n// Login\nasync function login(){\n state.api=$("#serverURL").value.trim().replace(/\\/$/,"");localStorage.setItem("v6Server",state.api);\n $("#loginBtn").disabled=true;\n try{\n  const r=await fetch(state.api+"/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:$("#username").value.trim(),password:$("#password").value})});\n  const d=await r.json();if(!r.ok)throw new Error(d.detail||"登录失败");\n  state.token=d.token;state.user={id:d.userID,name:d.name,role:d.role,grade:d.grade};state.offline=false;\n  localStorage.setItem("v6Token",state.token);localStorage.setItem("v6User",JSON.stringify(state.user));enter();\n }catch(e){toast(e.message)}finally{$("#loginBtn").disabled=false}\n}\nfunction enter(){\n $("#loginScreen").classList.add("hidden");$("#shell").classList.remove("hidden");\n const d=state.offline?"practice":({admin:"admin",teacher:"teacher",student:"student",parent:"parent"})[state.user.role];\n go(d);\n}\nfunction logout(){\n state.token="";state.user=null;state.offline=false;localStorage.removeItem("v6Token");localStorage.removeItem("v6User");\n $("#shell").classList.add("hidden");$("#loginScreen").classList.remove("hidden")\n}\n\n// Admin\nasync function admin(){\n const d=await api("/admin/overview");\n $("#page").innerHTML=head("平台总览","学校题库平台运营数据")+\n `<div class="grid4">${stat(d.teachers,"教师")}${stat(d.students,"学生")}${stat(d.parents,"家长")}${stat(d.classes,"班级")}</div>\n <div class="section grid4">${stat(d.questions,"题目")}${stat(d.papers,"试卷")}${stat(d.assignments,"作业")}${stat(d.submissions,"答题提交")}</div>\n <div class="section grid2"><div class="card"><h2>教材覆盖</h2><p class="muted">${esc((d.textbooks||[]).join("、")||"暂无")}</p></div><div class="card"><h2>平台架构</h2><p class="muted">PWA + Capacitor + Electron；后端 FastAPI，可部署到云服务器。</p></div></div>`;\n}\nasync function users(){\n const list=await api("/admin/users");\n $("#page").innerHTML=head("账号管理","管理员创建教师、家长账号",`<button class="btn primary" id="newTeacher">＋教师</button><button class="btn secondary" id="newParent">＋家长</button>`)+\n `<div class="card table-wrap"><table class="table"><thead><tr><th>姓名</th><th>账号</th><th>身份</th><th>年级</th></tr></thead><tbody>${list.map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.username)}</td><td>${roleName(x.role)}</td><td>${x.grade||"-"}</td></tr>`).join("")}</tbody></table></div>`;\n $("#newTeacher").onclick=()=>userForm("teacher");$("#newParent").onclick=()=>userForm("parent");\n}\nfunction userForm(role){\n modal(role==="teacher"?"创建教师":"创建家长",`<label>姓名</label><input id="nuName"><label>登录账号</label><input id="nuUser"><label>初始密码</label><input id="nuPass" value="123456"><button class="btn primary full" id="saveUser">创建</button>`);\n $("#saveUser").onclick=async()=>{try{await api("/admin/users",{method:"POST",body:JSON.stringify({name:$("#nuName").value,username:$("#nuUser").value,password:$("#nuPass").value,role})});closeModal();toast("账号已创建");go("users")}catch(e){toast(e.message)}};\n}\nasync function imports(){\n const jobs=await api("/admin/import-jobs");\n $("#page").innerHTML=head("批量导入","使用 V6 Excel 模板批量导入题库、学生和教师",`<button class="btn primary" id="uploadXlsx">上传 XLSX</button>`)+\n `<div class="card"><div class="note">Excel 模板已随项目提供：docs/V6_批量导入模板.xlsx。后端会识别“题库导入 / 学生导入 / 教师导入”三个工作表。</div>\n <input type="file" id="xlsxFile" accept=".xlsx" class="hidden"></div>\n <div class="section"><h2>最近导入</h2><div class="list">${jobs.length?jobs.map(j=>`<div class="item"><div class="item-main"><b>${esc(j.filename)}</b><small>${esc(j.createdAt)} · ${esc(j.summary)}</small></div><span class="badge ${j.status==="成功"?"green":"red"}">${esc(j.status)}</span></div>`).join(""):"<div class=\'card empty\'>暂无导入记录</div>"}</div></div>`;\n $("#uploadXlsx").onclick=()=>$("#xlsxFile").click();\n $("#xlsxFile").onchange=async()=>{\n  const f=$("#xlsxFile").files[0];if(!f)return;\n  const fd=new FormData();fd.append("file",f);\n  try{\n   const r=await fetch(state.api+"/admin/import-xlsx",{method:"POST",headers:{Authorization:`Bearer ${state.token}`},body:fd});const d=await r.json();if(!r.ok)throw new Error(d.detail||"导入失败");\n   toast(d.summary);go("imports");\n  }catch(e){toast(e.message)}\n };\n}\nasync function system(){\n $("#page").innerHTML=head("系统设置","部署、备份和客户端安装说明")+\n `<div class="grid2"><div class="card"><h2>跨平台客户端</h2><p class="muted">Web/PWA、iOS、Android、Windows、macOS、Linux 共用一套业务前端。</p></div>\n <div class="card"><h2>生产环境建议</h2><p class="muted">正式上线建议启用 HTTPS、PostgreSQL、对象存储、每日备份和学校多租户隔离。</p></div></div>\n <div class="section card"><h2>当前服务器</h2><input id="sysURL" value="${esc(state.api)}"><button class="btn secondary full" id="saveSys">保存</button></div>`;\n $("#saveSys").onclick=()=>{state.api=$("#sysURL").value.trim().replace(/\\/$/,"");localStorage.setItem("v6Server",state.api);toast("已保存")};\n}\n\n// Shared catalog\nasync function catalog(){\n const qs=await api("/questions");\n $("#page").innerHTML=head("教材题库",`共 ${qs.length} 道云端题目`,state.user?.role==="teacher"||state.user?.role==="admin"?`<button class="btn primary" id="addQ">＋新增题目</button>`:"")+\n `<div class="filters"><select id="fGrade"><option value="">全部年级</option>${[1,2,3,4,5,6].map(x=>`<option value="${x}">${x}年级</option>`).join("")}</select>\n <select id="fSubject"><option value="">全部科目</option><option>数学</option><option>语文</option><option>英语</option></select>\n <select id="fBook"><option value="">全部教材</option>${[...new Set(qs.map(q=>q.textbook))].map(x=>`<option>${esc(x)}</option>`).join("")}</select>\n <input id="fSearch" placeholder="搜索知识点或题目"></div><div id="catalogList"></div>`;\n const draw=()=>{\n  const g=$("#fGrade").value,s=$("#fSubject").value,b=$("#fBook").value,k=$("#fSearch").value.trim();\n  const list=qs.filter(q=>(!g||q.grade==g)&&(!s||q.subject===s)&&(!b||q.textbook===b)&&(!k||q.text.includes(k)||q.knowledge.includes(k)||q.unit.includes(k)));\n  $("#catalogList").innerHTML=`<div class="list">${list.map(q=>`<div class="item"><div class="item-main"><b>${esc(q.text)}</b><small>${q.grade}年级 · ${esc(q.subject)} · ${esc(q.textbook)} · ${esc(q.semester)} · ${esc(q.unit)} · ${esc(q.knowledge)}</small></div><span class="badge">${esc(q.options[q.correctIndex])}</span></div>`).join("")||"<div class=\'card empty\'>暂无题目</div>"}</div>`;\n };\n ["#fGrade","#fSubject","#fBook","#fSearch"].forEach(x=>$(x).oninput=draw);draw();\n if($("#addQ"))$("#addQ").onclick=()=>questionForm();\n}\nfunction questionForm(){\n modal("新增教材题目",`<div class="form-grid">\n <div><label>年级</label><select id="qg">${[1,2,3,4,5,6].map(x=>`<option>${x}</option>`).join("")}</select></div>\n <div><label>科目</label><select id="qs"><option>数学</option><option>语文</option><option>英语</option></select></div>\n <div><label>教材版本</label><input id="qb" value="人教版"></div><div><label>学期</label><select id="qsem"><option>上册</option><option>下册</option></select></div>\n <div><label>单元</label><input id="qu" placeholder="第一单元"></div><div><label>知识点</label><input id="qk"></div>\n </div><label>题目</label><textarea id="qt"></textarea>\n <div class="form-grid">${["A","B","C","D"].map((x,i)=>`<div><label>选项${x}</label><input id="qo${i}"></div>`).join("")}</div>\n <label>正确选项</label><select id="qc"><option value="0">A</option><option value="1">B</option><option value="2">C</option><option value="3">D</option></select>\n <label>解析</label><textarea id="qe"></textarea><button class="btn primary full" id="saveQ">保存题目</button>`);\n $("#saveQ").onclick=async()=>{try{\n  await api("/questions",{method:"POST",body:JSON.stringify({grade:+$("#qg").value,subject:$("#qs").value,textbook:$("#qb").value,semester:$("#qsem").value,unit:$("#qu").value,knowledge:$("#qk").value,text:$("#qt").value,options:[0,1,2,3].map(i=>$(`#qo${i}`).value),correct_index:+$("#qc").value,explanation:$("#qe").value})});\n  closeModal();toast("题目已保存");go("catalog")\n }catch(e){toast(e.message)}};\n}\n\n// Teacher\nasync function teacher(){\n const d=await api("/teacher/dashboard");\n $("#page").innerHTML=head("教师工作台","班级教学与学情概览")+\n `<div class="grid4">${stat(d.classes,"班级")}${stat(d.students,"学生")}${stat(d.assignments,"作业")}${stat(d.submissions,"已提交")}</div>\n <div class="section grid2"><div class="card"><h2>平均正确率</h2><div style="font-size:42px;font-weight:900;color:var(--primary)">${d.avgAccuracy}%</div></div>\n <div class="card"><h2>薄弱知识点</h2><div class="knowledge">${(d.weakKnowledge||[]).slice(0,5).map(x=>`<div class="knowledge-row"><small>${esc(x.knowledge)}</small><div class="knowledge-meter"><i style="width:${x.accuracy}%"></i></div><b>${x.accuracy}%</b></div>`).join("")||"<span class=\'muted\'>暂无数据</span>"}</div></div></div>`;\n}\nasync function classes(){\n const list=await api("/teacher/classes");\n $("#page").innerHTML=head("班级学生","班级、学生和家长绑定",`<button class="btn primary" id="newClass">＋新建班级</button>`)+\n `<div class="list">${list.map(c=>`<div class="item"><div class="item-main"><b>${esc(c.name)}</b><small>${c.grade}年级 · ${c.studentCount}名学生</small></div><div class="actions"><button class="btn secondary small showStudents" data-id="${c.id}">学生</button><button class="btn primary small addStudent" data-id="${c.id}" data-grade="${c.grade}">加学生</button></div></div>`).join("")||"<div class=\'card empty\'>暂无班级</div>"}</div>`;\n $("#newClass").onclick=()=>{modal("新建班级",`<label>班级名称</label><input id="cn"><label>年级</label><select id="cg">${[1,2,3,4,5,6].map(x=>`<option>${x}</option>`).join("")}</select><button id="saveClass" class="btn primary full">保存</button>`);$("#saveClass").onclick=async()=>{try{await api("/teacher/classes",{method:"POST",body:JSON.stringify({name:$("#cn").value||"新班级",grade:+$("#cg").value})});closeModal();go("classes")}catch(e){toast(e.message)}}};\n $$(".showStudents").forEach(b=>b.onclick=()=>studentList(+b.dataset.id));\n $$(".addStudent").forEach(b=>b.onclick=()=>studentForm(+b.dataset.id,+b.dataset.grade));\n}\nasync function studentList(cid){\n const a=await api(`/teacher/classes/${cid}/students`);\n modal("班级学生",a.length?`<div class="list">${a.map(s=>`<div class="item"><div class="item-main"><b>${esc(s.name)}</b><small>${esc(s.username)} · 家长 ${s.parentName?esc(s.parentName):"未绑定"}</small></div></div>`).join("")}</div>`:"<div class=\'empty\'>暂无学生</div>");\n}\nfunction studentForm(cid,grade){\n modal("创建学生账号",`<div class="form-grid"><div><label>学生姓名</label><input id="sn"></div><div><label>学生账号</label><input id="su"></div><div><label>密码</label><input id="sp" value="123456"></div><div><label>家长账号（可选）</label><input id="sparent" placeholder="parent1"></div></div><button id="saveStudent" class="btn primary full">创建</button>`);\n $("#saveStudent").onclick=async()=>{try{await api("/teacher/students",{method:"POST",body:JSON.stringify({name:$("#sn").value,username:$("#su").value,password:$("#sp").value,grade,class_id:cid,parent_username:$("#sparent").value||null})});closeModal();toast("学生已创建");go("classes")}catch(e){toast(e.message)}};\n}\nasync function papers(){\n const [cs,as]=await Promise.all([api("/teacher/classes"),api("/teacher/assignments")]);\n $("#page").innerHTML=head("组卷与作业","可按教材、单元、知识点自动组卷",`<button class="btn primary" id="newAssignment">✨自动组卷</button>`)+\n `<div class="list">${as.map(a=>`<div class="item"><div class="item-main"><b>${esc(a.title)}</b><small>${esc(a.paper?.textbook||"")} · ${esc(a.paper?.unit||"综合")} · 截止 ${esc(a.dueDate)} · 已交 ${a.submissionCount}</small></div><button class="btn secondary small subs" data-id="${a.id}">成绩</button></div>`).join("")||"<div class=\'card empty\'>暂无作业</div>"}</div>`;\n $("#newAssignment").onclick=()=>assignmentForm(cs);\n $$(".subs").forEach(b=>b.onclick=()=>submissionList(+b.dataset.id));\n}\nfunction assignmentForm(classes){\n modal("自动组卷",`<label>作业名称</label><input id="at" value="课后练习"><div class="form-grid">\n <div><label>班级</label><select id="ac">${classes.map(c=>`<option value="${c.id}" data-grade="${c.grade}">${esc(c.name)}</option>`).join("")}</select></div>\n <div><label>科目</label><select id="as"><option>数学</option><option>语文</option><option>英语</option></select></div>\n <div><label>教材版本</label><input id="ab" value="人教版"></div><div><label>单元</label><input id="au" placeholder="留空=综合"></div>\n <div><label>题量</label><select id="an"><option>5</option><option>10</option><option>15</option><option>20</option></select></div><div><label>截止日期</label><input type="date" id="ad"></div>\n </div><button id="saveAssignment" class="btn primary full">生成并布置</button>`);\n $("#saveAssignment").onclick=async()=>{try{\n  const o=$("#ac").selectedOptions[0],grade=+o.dataset.grade,class_id=+o.value,subject=$("#as").value,textbook=$("#ab").value,unit=$("#au").value;\n  const params=new URLSearchParams({grade,subject});if(textbook)params.set("textbook",textbook);if(unit)params.set("unit",unit);\n  const qs=await api("/questions?"+params.toString());const ids=qs.sort(()=>Math.random()-.5).slice(0,+$("#an").value).map(q=>q.id);if(!ids.length)throw new Error("没有符合条件的题目");\n  const p=await api("/teacher/papers",{method:"POST",body:JSON.stringify({title:$("#at").value,grade,subject,textbook,unit,question_ids:ids})});\n  await api("/teacher/assignments",{method:"POST",body:JSON.stringify({title:$("#at").value,class_id,paper_id:p.id,due_date:$("#ad").value||new Date(Date.now()+7*86400000).toISOString().slice(0,10)})});\n  closeModal();toast("作业已布置");go("papers")\n }catch(e){toast(e.message)}};\n}\nasync function submissionList(id){\n const rows=await api(`/teacher/assignments/${id}/submissions`);\n modal("作业成绩",rows.length?`<div class="table-wrap"><table class="table"><thead><tr><th>学生</th><th>分数</th><th>正确</th><th>提交时间</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.studentName)}</td><td><b>${r.score}</b></td><td>${r.correct}/${r.total}</td><td>${esc(r.submittedAt.slice(0,16).replace("T"," "))}</td></tr>`).join("")}</tbody></table></div>`:"<div class=\'empty\'>暂无提交</div>");\n}\nasync function analytics(){\n const d=await api("/teacher/analytics");\n $("#page").innerHTML=head("学情分析","按知识点识别班级薄弱环节")+\n `<div class="grid3">${stat(d.totalSubmissions,"累计提交")}${stat(d.avgScore,"平均分")}${stat(d.avgAccuracy+"%","平均正确率")}</div>\n <div class="section card"><h2>知识点掌握度</h2><div class="knowledge">${d.knowledge.map(k=>`<div class="knowledge-row"><small>${esc(k.knowledge)}</small><div class="knowledge-meter"><i style="width:${k.accuracy}%"></i></div><b>${k.accuracy}%</b></div>`).join("")||"<span class=\'muted\'>暂无答题数据</span>"}</div></div>`;\n}\nasync function leaderboard(){\n const rows=await api("/leaderboard");\n $("#page").innerHTML=head("班级排行榜","按最近累计答题成绩计算")+\n `<div class="card table-wrap"><table class="table"><thead><tr><th>排名</th><th>学生</th><th>班级</th><th>平均分</th><th>提交次数</th></tr></thead><tbody>${rows.map((r,i)=>`<tr><td class="${i===0?"rank1":""}">${i+1}</td><td>${esc(r.studentName)}</td><td>${esc(r.className)}</td><td><b>${r.avgScore}</b></td><td>${r.submissions}</td></tr>`).join("")}</tbody></table></div>`;\n}\n\n// Student\nasync function student(){\n const [as,p]=await Promise.all([api("/student/assignments"),api("/student/progress")]);\n $("#page").innerHTML=head("学习首页",`${esc(state.user.name)}，今天继续加油`)+\n `<div class="hero"><h2>今日学习</h2><p>完成老师布置的作业，并针对薄弱知识点进行专项练习。</p><button id="goPractice" class="btn secondary">开始自主练习</button></div>\n <div class="section grid3">${stat(as.length,"作业")}${stat(p.avgScore,"平均分")}${stat(p.totalAnswered,"累计答题")}</div>\n <div class="section"><h2>待完成作业</h2><div class="list">${as.map(a=>`<div class="item"><div class="item-main"><b>${esc(a.title)}</b><small>${esc(a.paper?.subject||"")} · 截止 ${esc(a.dueDate)}</small></div><button class="btn primary small doA" data-id="${a.id}">开始</button></div>`).join("")||"<div class=\'card empty\'>暂无作业</div>"}</div></div>`;\n $("#goPractice").onclick=()=>go("practice");$$(".doA").forEach(b=>b.onclick=()=>startAssignment(+b.dataset.id));\n}\nasync function assignments(){\n const as=await api("/student/assignments");\n $("#page").innerHTML=head("我的作业","完成后成绩会自动回传给老师")+\n `<div class="list">${as.map(a=>`<div class="item"><div class="item-main"><b>${esc(a.title)}</b><small>${esc(a.paper?.textbook||"")} · ${esc(a.paper?.unit||"综合")} · 截止 ${esc(a.dueDate)}</small></div><button class="btn primary small doA" data-id="${a.id}">答题</button></div>`).join("")||"<div class=\'card empty\'>暂无作业</div>"}</div>`;\n $$(".doA").forEach(b=>b.onclick=()=>startAssignment(+b.dataset.id));\n}\nasync function practice(){\n const qs=state.offline?offlineBank:await api("/questions");\n $("#page").innerHTML=head(state.offline?"离线练习":"自主练习","按教材和知识点选择练习内容")+\n `<div class="card"><div class="form-grid">\n <div><label>年级</label><select id="pg">${[1,2,3,4,5,6].map(x=>`<option ${x==3?"selected":""}>${x}</option>`).join("")}</select></div>\n <div><label>科目</label><select id="ps"><option>数学</option><option>语文</option><option>英语</option></select></div>\n <div><label>教材</label><select id="pb"><option value="">全部</option>${[...new Set(qs.map(q=>q.textbook))].map(x=>`<option>${esc(x)}</option>`).join("")}</select></div>\n <div><label>题量</label><select id="pn"><option>5</option><option>10</option><option>15</option></select></div>\n </div><button class="btn primary full" id="startP">开始练习</button></div>`;\n $("#startP").onclick=()=>{\n  const g=+$("#pg").value,s=$("#ps").value,b=$("#pb").value,n=+$("#pn").value;\n  let list=qs.filter(q=>q.grade===g&&q.subject===s&&(!b||q.textbook===b));if(!list.length&&state.offline)list=qs;\n  startQuiz(list.sort(()=>Math.random()-.5).slice(0,n),`${g}年级${s}练习`,null);\n };\n}\nasync function startAssignment(id){\n const as=await api("/student/assignments"),a=as.find(x=>x.id===id);if(!a)return;\n const qs=await api(`/papers/${a.paperID}/questions`);startQuiz(qs,a.title,id)\n}\nfunction startQuiz(qs,title,aid){\n if(!qs.length){toast("没有可用题目");return}\n let i=0,sel=null,done=false,correct=0,answers=[];\n const render=()=>{\n  const q=qs[i];\n  $("#page").innerHTML=head(title,`第 ${i+1}/${qs.length} 题`,`<button class="btn secondary" id="quitQuiz">退出</button>`)+\n  `<div class="card"><div class="progress"><i style="width:${pct(i+(done?1:0),qs.length)}%"></i></div>\n  <div style="margin-top:12px"><span class="badge">${esc(q.textbook)} · ${esc(q.unit)} · ${esc(q.knowledge)}</span></div>\n  <div class="question">${esc(q.text)}</div>\n  ${q.options.map((o,n)=>`<button class="option ${sel===n?"selected":""} ${done&&n===q.correctIndex?"correct":""} ${done&&sel===n&&n!==q.correctIndex?"wrong":""}" data-i="${n}"><span class="letter">${String.fromCharCode(65+n)}</span>${esc(o)}</button>`).join("")}\n  ${done?`<div class="answer"><b>${sel===q.correctIndex?"✅ 正确":"❌ 错误"}</b><br>正确答案：${esc(q.options[q.correctIndex])}<br><span class="muted">${esc(q.explanation)}</span></div>`:""}\n  <button id="quizNext" class="btn primary full" ${sel===null&&!done?"disabled":""}>${done?(i===qs.length-1?"完成练习":"下一题"):"提交答案"}</button></div>`;\n  $("#quitQuiz").onclick=()=>go(aid?"assignments":"practice");\n  $$(".option").forEach(b=>b.onclick=()=>{if(done)return;sel=+b.dataset.i;render()});\n  $("#quizNext").onclick=async()=>{\n   if(!done){done=true;const ok=sel===q.correctIndex;if(ok)correct++;answers.push({question_id:q.id,selected_index:sel,correct:ok});render();return}\n   if(i<qs.length-1){i++;sel=null;done=false;render();return}\n   const score=pct(correct,qs.length);\n   if(!state.offline){\n    try{\n     if(aid)await api(`/student/assignments/${aid}/submit`,{method:"POST",body:JSON.stringify({correct,total:qs.length,score,answers})});\n     else await api("/student/practice-submit",{method:"POST",body:JSON.stringify({title,correct,total:qs.length,score,answers})});\n    }catch(e){toast(e.message)}\n   }\n   $("#page").innerHTML=head("练习完成",title)+`<div class="card empty"><div style="font-size:62px">🏆</div><h1 style="color:var(--primary)">${score}分</h1><p>答对 ${correct} 题，答错 ${qs.length-correct} 题</p><button id="backQuiz" class="btn primary">返回</button></div>`;\n   $("#backQuiz").onclick=()=>go(aid?"assignments":"practice")\n  };\n };render()\n}\nasync function progress(){\n const p=await api("/student/progress");\n $("#page").innerHTML=head("我的学情","查看成绩趋势和薄弱知识点")+\n `<div class="grid3">${stat(p.avgScore,"平均分")}${stat(p.totalAnswered,"累计答题")}${stat(p.submissions,"练习次数")}</div>\n <div class="section card"><h2>知识点掌握</h2><div class="knowledge">${p.knowledge.map(k=>`<div class="knowledge-row"><small>${esc(k.knowledge)}</small><div class="knowledge-meter"><i style="width:${k.accuracy}%"></i></div><b>${k.accuracy}%</b></div>`).join("")||"<span class=\'muted\'>暂无数据</span>"}</div></div>`;\n}\n\n// Parent\nasync function parent(){\n const c=await api("/parent/children");\n $("#page").innerHTML=head("家长首页","查看孩子近期学习情况")+\n `<div class="list">${c.map(x=>`<div class="item"><div class="item-main"><b>${esc(x.name)}</b><small>${x.grade}年级 · ${esc(x.className||"")}</small></div><span class="badge">${x.avgScore}分</span></div>`).join("")||"<div class=\'card empty\'>尚未绑定孩子</div>"}</div>`;\n}\nasync function childProgress(){\n const c=await api("/parent/children");\n if(!c.length){$("#page").innerHTML=head("孩子学情","暂无绑定学生")+empty("请联系教师或管理员绑定家长账号");return}\n const cid=c[0].id,p=await api(`/parent/children/${cid}/progress`);\n $("#page").innerHTML=head(`${esc(p.studentName)}的学情`,`${p.grade}年级 · 最近学习概况`)+\n `<div class="grid3">${stat(p.avgScore,"平均分")}${stat(p.totalAnswered,"累计答题")}${stat(p.submissions,"练习次数")}</div>\n <div class="section card"><h2>薄弱知识点</h2><div class="knowledge">${p.knowledge.map(k=>`<div class="knowledge-row"><small>${esc(k.knowledge)}</small><div class="knowledge-meter"><i style="width:${k.accuracy}%"></i></div><b>${k.accuracy}%</b></div>`).join("")||"<span class=\'muted\'>暂无数据</span>"}</div></div>`;\n}\nasync function account(){\n $("#page").innerHTML=head("我的","账号与客户端设置")+\n `<div class="grid2"><div class="card"><h2>${esc(state.user?.name||"离线学生")}</h2><p class="muted">${state.offline?"离线体验":roleName(state.user?.role)}</p></div>\n <div class="card"><h2>服务器</h2><input id="accountURL" value="${esc(state.api)}" ${state.offline?"disabled":""}><button id="saveURL" class="btn secondary full" ${state.offline?"disabled":""}>保存</button></div></div>\n <div class="section note">iPhone/iPad：Safari → 分享 → 添加到主屏幕；Android/Windows：Chrome/Edge → 安装应用。也可用项目中的 Capacitor / Electron 配置封装为商店 App。</div>`;\n if($("#saveURL"))$("#saveURL").onclick=()=>{state.api=$("#accountURL").value.trim().replace(/\\/$/,"");localStorage.setItem("v6Server",state.api);toast("已保存")};\n}\n\n$("#serverURL").value=state.api;\n$("#loginBtn").onclick=login;\n$("#offlineBtn").onclick=()=>{state.offline=true;state.user={name:"离线学生",role:"student"};enter()};\n$("#logoutBtn").onclick=logout;\n$("#menuBtn").onclick=()=>$("#sidebar").classList.toggle("open");\n$("#modalClose").onclick=closeModal;\nif("serviceWorker" in navigator)window.addEventListener("load",()=>navigator.serviceWorker.register("./sw.js").catch(()=>{}));\nif(state.token&&state.user)enter();\n\n</script>\n</body>\n</html>\n'
MANIFEST = '{\n  "name": "小学题库 V7 商用全平台版",\n  "short_name": "小学题库",\n  "start_url": "./",\n  "scope": "./",\n  "display": "standalone",\n  "background_color": "#f4f6fb",\n  "theme_color": "#5362e8",\n  "lang": "zh-CN",\n  "icons": [\n    {\n      "src": "icon.svg",\n      "sizes": "any",\n      "type": "image/svg+xml",\n      "purpose": "any maskable"\n    }\n  ]\n}'
ICON_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">\n<rect width="512" height="512" rx="112" fill="#5362e8"/>\n<path fill="#fff" d="M100 126c66-20 116-6 156 29v252c-41-30-92-40-156-21V126zm312 0c-66-20-116-6-156 29v252c41-30 92-40 156-21V126z"/>\n</svg>'
SERVICE_WORKER = 'const C="quiz-v6-url-shell-1";\nconst A=["./","./index.html","./styles.css","./app.js","./manifest.webmanifest","./icon.svg"];\nself.addEventListener("install",e=>e.waitUntil(caches.open(C).then(c=>c.addAll(A))));\nself.addEventListener("activate",e=>e.waitUntil(\n  caches.keys().then(k=>Promise.all(k.filter(x=>x!==C).map(x=>caches.delete(x))))\n));\nself.addEventListener("fetch",e=>{\n  if(e.request.method!=="GET") return;\n  const u=new URL(e.request.url);\n  if(u.origin!==location.origin) return;\n  const apiPrefixes=[\n    "/login","/questions","/admin","/teacher","/student",\n    "/papers","/leaderboard","/parent","/health","/docs","/openapi.json"\n  ];\n  if(apiPrefixes.some(p=>u.pathname===p||u.pathname.startsWith(p+"/"))) return;\n  e.respondWith(\n    caches.match(e.request).then(hit=>hit||fetch(e.request).then(r=>{\n      const copy=r.clone();\n      caches.open(C).then(cache=>cache.put(e.request,copy));\n      return r;\n    }).catch(()=>caches.match("./index.html")))\n  );\n});\n'

@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(INDEX_HTML)

@app.get("/manifest.webmanifest")
def manifest():
    return Response(MANIFEST, media_type="application/manifest+json")

@app.get("/icon.svg")
def icon():
    return Response(ICON_SVG, media_type="image/svg+xml")

@app.get("/sw.js")
def service_worker():
    return Response(SERVICE_WORKER, media_type="application/javascript")
