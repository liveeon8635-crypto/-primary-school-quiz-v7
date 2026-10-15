"""One class and its pupil snapshot for a weekend classroom occurrence."""
from __future__ import annotations
import json
from typing import Any
from fastapi import HTTPException
from sqlalchemy import Column, Integer, String, Table, Text, insert, select, update


def register_roster_table(implementation: Any) -> Table:
    md=implementation.Base.metadata
    if 'weekend_class_rosters' not in md.tables:
        Table('weekend_class_rosters',md,
              Column('session_id',Integer,primary_key=True),
              Column('school_id',Integer,nullable=False,index=True),
              Column('teacher_id',Integer,nullable=False,index=True),
              Column('class_id',Integer,nullable=False),
              Column('class_name',String(120),nullable=False),
              Column('members_json',Text,nullable=False))
    return md.tables['weekend_class_rosters']


def class_members(implementation: Any, db: Any, u: Any, class_id: int) -> tuple[Any, dict[int, tuple[str,int]]]:
    SC,CS,User=implementation.SchoolClass,implementation.ClassStudent,implementation.User
    cls=db.scalar(select(SC).where(SC.id==class_id,SC.school_id==u.school_id,SC.teacher_id==u.id))
    if cls is None:
        raise HTTPException(404,'请选择你所带的班级')
    members={int(i):(str(n),int(cls.id)) for i,n in db.execute(select(User.id,User.name).join(CS,CS.student_id==User.id).where(
        CS.class_id==cls.id,User.school_id==u.school_id,User.role=='student')).all()}
    if not members:
        raise HTTPException(400,'这个班级还没有学生，请先在我的班级添加学生')
    return cls,members


def bind_class(implementation: Any, db: Any, row: Any, u: Any, class_id: int) -> None:
    cls,members=class_members(implementation,db,u,class_id)
    t=register_roster_table(implementation)
    values=dict(school_id=u.school_id,teacher_id=u.id,class_id=cls.id,class_name=cls.name,
                members_json=json.dumps([{'id':i,'name':n} for i,(n,_) in members.items()],ensure_ascii=False))
    if db.scalar(select(t.c.session_id).where(t.c.session_id==row.id)) is None:
        db.execute(insert(t).values(session_id=row.id,**values))
    else:
        db.execute(update(t).where(t.c.session_id==row.id,t.c.school_id==u.school_id,t.c.teacher_id==u.id).values(**values))


def session_class(implementation: Any, db: Any, row: Any) -> Any:
    t=register_roster_table(implementation)
    return db.execute(select(t).where(t.c.session_id==row.id,t.c.school_id==row.school_id,t.c.teacher_id==row.teacher_id)).first()


def session_roster(implementation: Any, db: Any, row: Any) -> dict[int, tuple[str,int]]:
    bound=session_class(implementation,db,row)
    if bound is not None:
        return {int(x['id']):(str(x['name']),int(bound.class_id)) for x in json.loads(bound.members_json)}
    # Historical unbound sessions retain their original interpretation; the UI
    # requires an explicit class for new sessions and offers binding old ones.
    SC,CS,User=implementation.SchoolClass,implementation.ClassStudent,implementation.User
    return {int(i):(str(n),int(c)) for i,n,c in db.execute(select(User.id,User.name,SC.id).join(CS,CS.student_id==User.id).join(SC,SC.id==CS.class_id).where(
        SC.teacher_id==row.teacher_id,SC.school_id==row.school_id,User.school_id==row.school_id)).all()}


def student_in_session(implementation: Any, db: Any, row: Any, student_id: int) -> bool:
    return student_id in session_roster(implementation,db,row)
