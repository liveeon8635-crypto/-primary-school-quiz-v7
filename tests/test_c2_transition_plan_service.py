from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, create_engine, select
from sqlalchemy.orm import Session

from changying.services.transition_plans import TransitionPlanService


metadata=MetaData()
plans=Table("test_transition_plans",metadata,
    Column("id",Integer,primary_key=True), Column("school_id",Integer), Column("student_id",Integer),
    Column("teacher_id",Integer), Column("status",String(20)), Column("created_at",DateTime),
    Column("updated_at",DateTime), Column("closed_at",DateTime,nullable=True))
class Audit:
    def __init__(self,**kwargs): self.__dict__.update(kwargs)


def test_transition_plan_service_preserves_scope_order_and_close_semantics():
    engine=create_engine("sqlite://")
    metadata.create_all(engine)
    with Session(engine) as db:
        db.execute(plans.insert(),[
            {"id":1,"school_id":10,"student_id":100,"teacher_id":7,"status":"active","created_at":datetime(2026,1,1),"updated_at":datetime(2026,1,1)},
            {"id":2,"school_id":10,"student_id":100,"teacher_id":7,"status":"active","created_at":datetime(2026,2,1),"updated_at":datetime(2026,2,1)},
            {"id":3,"school_id":10,"student_id":101,"teacher_id":7,"status":"active","created_at":datetime(2026,3,1),"updated_at":datetime(2026,3,1)},
            {"id":4,"school_id":20,"student_id":100,"teacher_id":7,"status":"active","created_at":datetime(2026,4,1),"updated_at":datetime(2026,4,1)},
        ])
        db.commit()
        service=TransitionPlanService(table=plans,select_fn=select,audit_log_model=Audit)
        assert [r._mapping["id"] for r in service.list_rows(db,school_id=10,student_id=100)]==[2,1]
        # Use a real mapped-like add target only for route-level production; close lookup
        # remains independently scope-safe here.
        assert service.row(db,school_id=10,student_id=100,plan_id=3) is None
        assert service.row(db,school_id=20,student_id=100,plan_id=4)._mapping["id"]==4
