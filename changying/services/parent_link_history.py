"""Read-only parent-link history service for the continuous student record."""

from __future__ import annotations

from typing import Any


class ParentLinkHistoryService:
    def __init__(self, *, select_fn: Any, audit_log_model: Any, parent_student_model: Any, user_model: Any, local_iso: Any) -> None:
        self.select=select_fn; self.AuditLog=audit_log_model; self.ParentStudent=parent_student_model; self.User=user_model; self.local_iso=local_iso

    def _iso(self, value):
        return self.local_iso(value) if value is not None else None

    def history(self, db, *, student_id: int, school_id: int) -> list[dict[str, Any]]:
        logs=db.scalars(self.select(self.AuditLog).where(
            self.AuditLog.school_id==school_id,
            self.AuditLog.action.in_(["parent.bind","parent.unbind"]),
            self.AuditLog.detail.like(f"{student_id}:%"),
        ).order_by(self.AuditLog.created_at.asc(),self.AuditLog.id.asc())).all()
        intervals=[]; open_row=None
        for log in logs:
            detail=log.detail or ""
            if log.action=="parent.bind":
                parts=detail.split(":",3)
                if len(parts)<4: continue
                try: parent_id=int(parts[2])
                except (TypeError,ValueError): continue
                if open_row is not None:
                    open_row["endedAt"]=self._iso(log.created_at);open_row["endReason"]="replaced";open_row["current"]=False;intervals.append(open_row)
                open_row={"parentID":parent_id,"parentName":parts[3].strip() or f"家长#{parent_id}","startedAt":self._iso(log.created_at),"endedAt":None,"endReason":"","current":False,"source":"audit","startKnown":True,"endKnown":False}
            elif log.action=="parent.unbind" and open_row is not None:
                open_row["endedAt"]=self._iso(log.created_at);open_row["endReason"]="unbind";open_row["current"]=False;open_row["endKnown"]=True;intervals.append(open_row);open_row=None
        current_links=db.scalars(self.select(self.ParentStudent).where(self.ParentStudent.student_id==student_id)).all()
        current_ids={int(link.parent_id) for link in current_links}
        if open_row is not None:
            if open_row["parentID"] in current_ids: open_row["current"]=True;open_row["endKnown"]=True
            else: open_row["endReason"]="ended_time_unknown"
            intervals.append(open_row)
        represented={row["parentID"] for row in intervals if row.get("current") is True}
        for link in current_links:
            parent_id=int(link.parent_id)
            if parent_id in represented: continue
            parent=db.get(self.User,parent_id)
            intervals.append({"parentID":parent_id,"parentName":parent.name if parent is not None else f"家长#{parent_id}","startedAt":None,"endedAt":None,"endReason":"","current":True,"source":"current_link","startKnown":False,"endKnown":True})
        intervals.sort(key=lambda row:(row["startedAt"] or "",row["parentID"]),reverse=True)
        return intervals


__all__=["ParentLinkHistoryService"]
