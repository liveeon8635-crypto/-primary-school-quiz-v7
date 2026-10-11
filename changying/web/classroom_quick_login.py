"""Class code + seat number quick login for shared classroom tablets (feature flag, default OFF).

Enable with the environment variable ``CLASSROOM_QUICK_LOGIN=1`` (an operator action; this
module only *reads* it). When the flag is off nothing at all is registered: no tables, no
routes, no V1 patch, and the normal username/password login is untouched.

Flow
----
1. A teacher with an active classroom session opens ``/v1/classroom-join-code/{sid}`` which
   creates a temporary 6-digit class code (valid while the session is active/paused, and for
   at most ``CODE_TTL_MINUTES``). The code stores a snapshot of seat numbers 1..N for the
   class (ordered by user id); the seat -> student mapping is visible to the teacher only.
2. A student opens ``/join``, types the code and taps a seat number. The seat list contains
   numbers only (no names). Wrong codes are rate limited per client and globally.
3. A seat can be held by one device at a time (``UNIQUE(code_id, seat_no)`` row with a device
   hash). The same device may resume; another device gets 409 until the seat is released.
4. The token is a short-lived JWT (same claims as ``/login`` plus ``qjs``/``qjn``) that expires with
   the code and is revoked immediately on logout, seat release, code revoke/regeneration or end of
   class (checked per request by a middleware, so no existing auth code is modified). Students who still have an initial password (``must_change_password``) are refused:
   the existing security gate is not bypassed.
5. "一键退出" releases the seat and wipes the device (storage + cookies).
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError

from changying.security.login_rate import BoundedLoginRateLimiter, LoginRateLimitExceeded
from changying.web import v1 as v1_module

CLASSROOM_QUICK_LOGIN_MARKER = "changying_classroom_quick_login_v1"
CODE_TTL_MINUTES = 180
CODE_LENGTH = 6
QUICK_LOGIN_FLAG = "CLASSROOM_QUICK_LOGIN"

_REFRESH_BUTTON = '<button class="btn" id="cy-session-refresh">刷新状态</button>'
_CODE_LINK = (
    '<a class="btn" id="cy-session-join-code" href="/v1/classroom-join-code/\'+sid+\'" '
    'target="_blank">班级码</a>'
)


def quick_login_enabled() -> bool:
    return os.getenv(QUICK_LOGIN_FLAG, "").strip().lower() in {"1", "true", "yes", "on"}


class JoinLookupBody(BaseModel):
    code: str


class JoinLoginBody(BaseModel):
    code: str
    seat: int
    device_id: str


def _mapping(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    return dict(row._mapping) if hasattr(row, "_mapping") else dict(row)


def _utcnow() -> datetime:
    return datetime.utcnow()


def device_hash(device_id: str) -> str:
    return hashlib.sha256(str(device_id or "").encode("utf-8")).hexdigest()


def new_code_digits(taken: set[str]) -> str:
    for _ in range(50):
        code = f"{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}"
        if code not in taken:
            return code
    raise HTTPException(503, "暂时无法生成班级码，请稍后再试")


def register_classroom_join_tables(implementation: Any) -> dict[str, Table]:
    metadata = implementation.Base.metadata
    codes = metadata.tables.get("classroom_join_codes")
    if codes is None:
        codes = Table(
            "classroom_join_codes",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("class_id", Integer, nullable=False, index=True),
            Column("session_id", Integer, nullable=False, index=True),
            Column("teacher_id", Integer, nullable=False, index=True),
            Column("code", String(12), nullable=False, index=True),
            Column("seats_json", Text, nullable=False, default="[]"),
            Column("created_at", DateTime, nullable=False, default=_utcnow),
            Column("expires_at", DateTime, nullable=False, index=True),
            Column("revoked_at", DateTime, nullable=True),
        )
    seats = metadata.tables.get("classroom_seat_sessions")
    if seats is None:
        seats = Table(
            "classroom_seat_sessions",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("code_id", Integer, nullable=False, index=True),
            Column("seat_no", Integer, nullable=False),
            Column("student_id", Integer, nullable=False, index=True),
            Column("device_hash", String(64), nullable=False, default=""),
            Column("claim_nonce", String(32), nullable=False, default=""),
            Column("claimed_at", DateTime, nullable=False, default=_utcnow),
            Column("released_at", DateTime, nullable=True),
            UniqueConstraint("code_id", "seat_no", name="uq_classroom_seat_code_seat"),
        )
    return {"codes": codes, "seats": seats}


def patch_v1_classroom_quick_login_html(html: str) -> str:
    """Teacher link next to the refresh button + the student's one-tap exit button."""
    if CLASSROOM_QUICK_LOGIN_MARKER in html:
        return html
    if _REFRESH_BUTTON not in html:
        raise RuntimeError("classroom execution refresh button anchor not found")
    html = html.replace(_REFRESH_BUTTON, _CODE_LINK + _REFRESH_BUTTON, 1)
    snippet = (
        f"<!-- {CLASSROOM_QUICK_LOGIN_MARKER} -->"
        f"<script>{EXIT_BUTTON_JS}</script>"
    )
    return html.replace("</body>", snippet + "</body>", 1) if "</body>" in html else html + snippet


def install_classroom_quick_login_patch() -> None:
    if getattr(v1_module, "_classroom_quick_login_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_classroom_quick_login_html(original())

    v1_module.v1_html = patched_v1_html
    v1_module._classroom_quick_login_patch_installed = True


def install_classroom_quick_login(implementation: Any) -> bool:
    """Install everything, but only when the feature flag is on. Returns whether it did."""
    if not quick_login_enabled():
        return False
    app = implementation.app
    if getattr(app.state, "classroom_quick_login_installed", False):
        return True

    tables = register_classroom_join_tables(implementation)
    codes, seat_rows = tables["codes"], tables["seats"]
    sessions = implementation.Base.metadata.tables.get("classroom_sessions")
    if sessions is None:
        raise RuntimeError("classroom execution tables must be registered before quick login")

    User = implementation.User
    School = implementation.School
    SchoolClass = implementation.SchoolClass
    ClassStudent = implementation.ClassStudent
    current_user = implementation.current_user
    get_db = implementation.get_db
    router = APIRouter()

    ip_limiter = BoundedLoginRateLimiter(window_seconds=600, max_attempts=20)
    global_limiter = BoundedLoginRateLimiter(window_seconds=600, max_attempts=100)

    def rate_check(request: Request) -> str:
        key = implementation._client_ip(request)
        try:
            ip_limiter.check(key)
            global_limiter.check("global")
        except LoginRateLimitExceeded:
            raise HTTPException(429, "输入错误次数太多，请稍等几分钟再试")
        return key

    def rate_failure(key: str) -> None:
        for limiter, name in ((ip_limiter, key), (global_limiter, "global")):
            try:
                limiter.failure(name)
            except LoginRateLimitExceeded:
                pass

    def normalize_code(raw: str) -> str:
        code = "".join(ch for ch in str(raw or "") if ch.isdigit())
        return code if len(code) == CODE_LENGTH else ""

    def active_code_row(db: Any, code: str) -> dict[str, Any] | None:
        if not code:
            return None
        now = _utcnow()
        for raw in db.execute(
            select(codes).where(
                codes.c.code == code,
                codes.c.revoked_at.is_(None),
                codes.c.expires_at > now,
            )
        ).all():
            row = _mapping(raw)
            session_raw = db.execute(
                select(sessions).where(
                    sessions.c.id == row["session_id"],
                    sessions.c.status.in_(["active", "paused"]),
                )
            ).first()
            if session_raw:
                return row
        return None

    def seat_state(db: Any, row: dict[str, Any]) -> list[dict[str, Any]]:
        snapshot = json.loads(row["seats_json"] or "[]")
        taken = {
            int(_mapping(x)["seat_no"])
            for x in db.execute(
                select(seat_rows).where(
                    seat_rows.c.code_id == row["id"], seat_rows.c.released_at.is_(None)
                )
            ).all()
        }
        ids = [int(x["studentID"]) for x in snapshot]
        locked: set[int] = set()
        if ids:
            sec_model = implementation.UserSecurity
            for sec in db.scalars(select(sec_model).where(sec_model.user_id.in_(ids))).all():
                if sec.must_change_password:
                    locked.add(int(sec.user_id))
        return [
            {
                "seat": int(x["seat"]),
                "studentID": int(x["studentID"]),
                "taken": int(x["seat"]) in taken,
                "needsPassword": int(x["studentID"]) in locked,
            }
            for x in snapshot
        ]

    def teacher_session(db: Any, user: Any, sid: int) -> dict[str, Any]:
        implementation.need(user, "teacher")
        raw = db.execute(
            select(sessions).where(
                sessions.c.id == sid,
                sessions.c.school_id == user.school_id,
                sessions.c.teacher_id == user.id,
            )
        ).first()
        if not raw:
            raise HTTPException(404, "课堂不存在或无权限")
        return _mapping(raw)

    def current_teacher_code(db: Any, user: Any, sid: int) -> dict[str, Any] | None:
        raw = db.execute(
            select(codes)
            .where(
                codes.c.session_id == sid,
                codes.c.school_id == user.school_id,
                codes.c.revoked_at.is_(None),
                codes.c.expires_at > _utcnow(),
            )
            .order_by(codes.c.id.desc())
            .limit(1)
        ).first()
        return _mapping(raw) if raw else None

    def teacher_payload(db: Any, row: dict[str, Any] | None, session_row: dict[str, Any]) -> dict[str, Any]:
        if not row:
            return {"code": None, "sessionStatus": session_row["status"]}
        names = {
            int(u.id): str(u.name or "")
            for u in db.scalars(
                select(User).where(
                    User.id.in_([int(x["studentID"]) for x in json.loads(row["seats_json"] or "[]")] or [0])
                )
            ).all()
        }
        seats = seat_state(db, row)
        for item in seats:
            item["studentName"] = names.get(item.pop("studentID"), "")
        return {
            "code": row["code"],
            "expiresAt": row["expires_at"].isoformat(sep=" ", timespec="seconds"),
            "expiresInSec": max(0, int((row["expires_at"] - _utcnow()).total_seconds())),
            "sessionStatus": session_row["status"],
            "seats": seats,
        }

    @router.get("/teacher/classroom-sessions/{sid}/join-code")
    def get_join_code(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        session_row = teacher_session(db, u, sid)
        return teacher_payload(db, current_teacher_code(db, u, sid), session_row)

    @router.post("/teacher/classroom-sessions/{sid}/join-code")
    def create_join_code(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        session_row = teacher_session(db, u, sid)
        if session_row["status"] not in ("active", "paused"):
            raise HTTPException(400, "课堂开始后才能生成班级码")
        now = _utcnow()
        db.execute(
            update(codes)
            .where(codes.c.session_id == sid, codes.c.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        students = db.scalars(
            select(User)
            .join(ClassStudent, ClassStudent.student_id == User.id)
            .where(
                ClassStudent.class_id == session_row["class_id"],
                User.school_id == u.school_id,
                User.role == "student",
                User.active == True,  # noqa: E712 - SQLAlchemy expression
            )
            .order_by(User.id)
        ).all()
        if not students:
            raise HTTPException(400, "这个班级里还没有学生")
        taken = {
            str(_mapping(x)["code"])
            for x in db.execute(
                select(codes.c.code).where(
                    codes.c.revoked_at.is_(None), codes.c.expires_at > now
                )
            ).all()
        }
        snapshot = [{"seat": i + 1, "studentID": int(s.id)} for i, s in enumerate(students)]
        db.execute(
            codes.insert().values(
                school_id=u.school_id,
                class_id=session_row["class_id"],
                session_id=sid,
                teacher_id=u.id,
                code=new_code_digits(taken),
                seats_json=json.dumps(snapshot),
                created_at=now,
                expires_at=now + timedelta(minutes=CODE_TTL_MINUTES),
            )
        )
        implementation.audit(db, u, "classroom.join_code.create", f"session={sid}")
        db.commit()
        return teacher_payload(db, current_teacher_code(db, u, sid), session_row)

    @router.delete("/teacher/classroom-sessions/{sid}/join-code")
    def revoke_join_code(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        session_row = teacher_session(db, u, sid)
        db.execute(
            update(codes)
            .where(codes.c.session_id == sid, codes.c.revoked_at.is_(None))
            .values(revoked_at=_utcnow())
        )
        implementation.audit(db, u, "classroom.join_code.revoke", f"session={sid}")
        db.commit()
        return teacher_payload(db, None, session_row)

    @router.post("/teacher/classroom-sessions/{sid}/join-code/seats/{seat}/release")
    def release_seat(sid: int, seat: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        session_row = teacher_session(db, u, sid)
        row = current_teacher_code(db, u, sid)
        if not row:
            raise HTTPException(404, "当前没有有效的班级码")
        db.execute(
            update(seat_rows)
            .where(seat_rows.c.code_id == row["id"], seat_rows.c.seat_no == seat)
            .values(released_at=_utcnow())
        )
        implementation.audit(db, u, "classroom.join_code.release_seat", f"session={sid}:seat={seat}")
        db.commit()
        return teacher_payload(db, row, session_row)

    @router.post("/classroom-join/lookup")
    def lookup(body: JoinLookupBody, request: Request, db: Any = Depends(get_db)):
        key = rate_check(request)
        row = active_code_row(db, normalize_code(body.code))
        if not row:
            rate_failure(key)
            raise HTTPException(404, "班级码不对或已经失效，请问老师")
        class_row = db.get(SchoolClass, row["class_id"])
        return {
            "className": str(getattr(class_row, "name", "") or ""),
            "expiresInSec": max(0, int((row["expires_at"] - _utcnow()).total_seconds())),
            # Seat numbers only: no names and no student ids ever leave the server here.
            "seats": [
                {"seat": s["seat"], "taken": s["taken"], "needsPassword": s["needsPassword"]}
                for s in seat_state(db, row)
            ],
        }

    @router.post("/classroom-join/login")
    def join_login(body: JoinLoginBody, request: Request, db: Any = Depends(get_db)):
        key = rate_check(request)
        row = active_code_row(db, normalize_code(body.code))
        if not row:
            rate_failure(key)
            raise HTTPException(404, "班级码不对或已经失效，请问老师")
        snapshot = {int(x["seat"]): int(x["studentID"]) for x in json.loads(row["seats_json"] or "[]")}
        student_id = snapshot.get(int(body.seat))
        if not student_id:
            raise HTTPException(404, "没有这个座号")
        device = device_hash(body.device_id)
        if len(str(body.device_id or "")) < 8:
            raise HTTPException(400, "设备标识无效，请刷新页面重试")
        student = db.get(User, student_id)
        school = db.get(School, row["school_id"])
        if not student or not student.active or student.role != "student" or not school or not school.active:
            raise HTTPException(403, "这个座号现在不能登录，请问老师")
        if not db.scalar(
            select(ClassStudent).where(
                ClassStudent.class_id == row["class_id"], ClassStudent.student_id == student_id
            )
        ):
            raise HTTPException(403, "这个座号现在不能登录，请问老师")
        sec = implementation.security_for(db, student)
        if sec.must_change_password:
            raise HTTPException(
                403, "这个同学还没有设置自己的密码，请先请老师帮忙设置后再用座号登录"
            )

        now = _utcnow()
        nonce = secrets.token_hex(8)
        existing = db.execute(
            select(seat_rows).where(
                seat_rows.c.code_id == row["id"], seat_rows.c.seat_no == int(body.seat)
            )
        ).first()
        busy = "这个座号已经在另一台设备上登录了，请换一个座号或请老师释放座号"
        if existing is None:
            try:
                with db.begin_nested():
                    db.execute(
                        seat_rows.insert().values(
                            school_id=row["school_id"],
                            code_id=row["id"],
                            seat_no=int(body.seat),
                            student_id=student_id,
                            device_hash=device,
                            claim_nonce=nonce,
                            claimed_at=now,
                            released_at=None,
                        )
                    )
            except IntegrityError:
                raise HTTPException(409, busy)
        else:
            current = _mapping(existing)
            if current["released_at"] is None and current["device_hash"] != device:
                raise HTTPException(409, busy)
            claimed = db.execute(
                update(seat_rows)
                .where(
                    seat_rows.c.id == current["id"],
                    (seat_rows.c.released_at.is_not(None)) | (seat_rows.c.device_hash == device),
                )
                .values(
                    device_hash=device,
                    claim_nonce=nonce,
                    released_at=None,
                    claimed_at=now,
                    student_id=student_id,
                )
            )
            if claimed.rowcount != 1:
                raise HTTPException(409, busy)

        seat_id = db.scalar(
            select(seat_rows.c.id).where(
                seat_rows.c.code_id == row["id"], seat_rows.c.seat_no == int(body.seat)
            )
        )
        expires_at = row["expires_at"]
        token_exp = expires_at.replace(tzinfo=timezone.utc)
        token = jwt.encode(
            {
                "sub": str(student.id),
                "role": student.role,
                "school_id": student.school_id,
                "pwdv": implementation.password_version(sec),
                # Revocation handles: checked on every request by the middleware below.
                "qjs": int(seat_id),
                "qjn": nonce,
                "iat": datetime.now(timezone.utc),
                "exp": token_exp,
            },
            implementation.JWT_SECRET,
            algorithm=implementation.JWT_ALG,
        )
        implementation.audit(db, student, "classroom.quick_login", f"code={row['id']}:seat={int(body.seat)}")
        db.commit()
        class_row = db.get(SchoolClass, row["class_id"])
        return {
            "token": token,
            "role": student.role,
            "userID": student.id,
            "name": student.name,
            "grade": student.grade,
            "mustChangePassword": False,
            "subscription": implementation.subscription_payload(db, student.school_id),
            "seat": int(body.seat),
            "className": str(getattr(class_row, "name", "") or ""),
            "expiresInSec": max(0, int((expires_at - now).total_seconds())),
        }

    @router.post("/classroom-join/logout")
    def join_logout(
        request: Request,
        authorization: str | None = Header(default=None),
        db: Any = Depends(get_db),
    ):
        released = 0
        try:
            if authorization and authorization.startswith("Bearer "):
                payload = jwt.decode(
                    authorization[7:], implementation.JWT_SECRET, algorithms=[implementation.JWT_ALG]
                )
                student_id = int(payload["sub"])
                result = db.execute(
                    update(seat_rows)
                    .where(seat_rows.c.student_id == student_id, seat_rows.c.released_at.is_(None))
                    .values(released_at=_utcnow())
                )
                released = int(result.rowcount or 0)
                db.commit()
        except Exception:
            db.rollback()
        response = JSONResponse({"ok": True, "released": released})
        from changying.web.v1_auth_handoff import V1_AUTH_HANDOFF_COOKIE

        response.delete_cookie(V1_AUTH_HANDOFF_COOKIE, path="/")
        response.headers["Cache-Control"] = "no-store"
        response.headers["Clear-Site-Data"] = '"cache"'
        return response

    @router.get("/join", include_in_schema=False)
    def join_page():
        return HTMLResponse(
            JOIN_HTML.replace("__MARKER__", CLASSROOM_QUICK_LOGIN_MARKER),
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )

    @router.get("/v1/classroom-join-code/{sid}", include_in_schema=False)
    def join_code_page(sid: int):
        return HTMLResponse(
            TEACHER_CODE_HTML.replace("__SID__", str(int(sid))).replace("__MARKER__", CLASSROOM_QUICK_LOGIN_MARKER),
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )

    def seat_token_is_live(seat_id: int, nonce: str) -> bool:
        """A quick-login token is valid only while its exact seat claim, code and class are live."""
        with implementation.SessionLocal() as db:
            seat = db.execute(select(seat_rows).where(seat_rows.c.id == seat_id)).first()
            if not seat:
                return False
            seat = _mapping(seat)
            if seat["released_at"] is not None or not secrets.compare_digest(
                str(seat["claim_nonce"] or ""), str(nonce or "")
            ):
                return False
            code_raw = db.execute(select(codes).where(codes.c.id == seat["code_id"])).first()
            if not code_raw:
                return False
            code_row = _mapping(code_raw)
            if code_row["revoked_at"] is not None or code_row["expires_at"] <= _utcnow():
                return False
            session_raw = db.execute(
                select(sessions.c.status).where(sessions.c.id == code_row["session_id"])
            ).first()
            return bool(session_raw and session_raw[0] in ("active", "paused"))

    @app.middleware("http")
    async def quick_login_revocation(request: Request, call_next):
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            try:
                claims = jwt.decode(
                    auth[7:], implementation.JWT_SECRET, algorithms=[implementation.JWT_ALG]
                )
            except Exception:
                claims = None
            if claims and claims.get("qjs") is not None:
                live = await run_in_threadpool(
                    seat_token_is_live, int(claims["qjs"]), str(claims.get("qjn") or "")
                )
                if not live:
                    return JSONResponse(
                        {"detail": "座号登录已失效，请重新输入班级码"}, status_code=401
                    )
        return await call_next(request)

    app.include_router(router)
    install_classroom_quick_login_patch()
    app.state.classroom_quick_login_installed = True
    return True


EXIT_BUTTON_JS = r"""
(function(){
  try{if(sessionStorage.getItem('cyQuickJoin')!=='1')return}catch(e){return}
  function wipe(){
    var dev='';try{dev=localStorage.getItem('cyDeviceId')||''}catch(e){}
    try{localStorage.clear()}catch(e){}try{sessionStorage.clear()}catch(e){}
    try{if(dev)localStorage.setItem('cyDeviceId',dev)}catch(e){}
    try{document.cookie.split(';').forEach(function(c){var n=c.split('=')[0].trim();if(n)document.cookie=n+'=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/'})}catch(e){}
  }
  // Shared tablets: bigger touch targets and no pinch zoom while a quick-login student is signed in.
  try{
    var vp=document.querySelector('meta[name=viewport]');
    if(vp)vp.setAttribute('content','width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover');
    ['gesturestart','gesturechange','gestureend'].forEach(function(n){document.addEventListener(n,function(e){e.preventDefault()},{passive:false})});
    var st=document.createElement('style');
    st.textContent='html,body{touch-action:manipulation}.btn,button{min-height:52px}label.row{min-height:64px;font-size:20px}label.row input[type=radio]{width:28px;height:28px}';
    document.head.appendChild(st);
  }catch(e){}
  function mount(){
    if(document.getElementById('cy-quick-exit'))return;
    var b=document.createElement('button');b.id='cy-quick-exit';b.type='button';b.textContent='一键退出';
    b.style.cssText='position:fixed;top:112px;right:14px;z-index:2147483000;min-width:96px;min-height:48px;padding:0 18px;border:0;border-radius:24px;background:#dc2626;color:#fff;font:700 18px system-ui,sans-serif;touch-action:manipulation';
    b.onclick=function(){
      var t='';try{t=sessionStorage.getItem('v717Token')||''}catch(e){}
      b.disabled=true;b.textContent='正在退出…';
      var done=function(){wipe();location.replace('/join')};
      try{fetch('/classroom-join/logout',{method:'POST',headers:t?{Authorization:'Bearer '+t}:{},keepalive:true,cache:'no-store'}).then(done,done)}catch(e){done()}
    };
    document.body.appendChild(b);
  }
  if(document.body)mount();else document.addEventListener('DOMContentLoaded',mount);
})();
"""

JOIN_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<meta name="__MARKER__" content="1">
<title>课堂登录</title>
<style>
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;height:100%;background:#eef2ff;color:#0f172a;font-family:"PingFang SC","Microsoft YaHei",system-ui,sans-serif;touch-action:manipulation;overscroll-behavior:none}
body{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:2vh 3vw;font-size:clamp(20px,2.4vw,34px)}
h1{margin:0 0 1.5vh;font-size:1.3em}
.hint{color:#475569;margin-bottom:2vh;min-height:1.4em;text-align:center}
.err{color:#b91c1c;font-weight:700}
.slots{display:flex;gap:1.2vw;margin-bottom:2.5vh}
.slot{width:2.2em;height:2.6em;border-radius:.4em;background:#fff;border:2px solid #c7d2fe;display:flex;align-items:center;justify-content:center;font-size:1.5em;font-weight:700}
.pad{display:grid;grid-template-columns:repeat(3,minmax(5.5em,1fr));gap:1.2vw;width:min(92vw,27em)}
.pad button,.seat{min-height:3.4em;border:0;border-radius:.6em;background:#fff;font:inherit;font-weight:700;box-shadow:0 2px 0 #c7d2fe;color:#1e293b}
.pad button:active,.seat:active{background:#c7d2fe}
.seats{display:grid;grid-template-columns:repeat(auto-fit,minmax(4.6em,5.4em));justify-content:center;gap:1.4vw;width:min(94vw,40em)}
.seat.taken{background:#e2e8f0;color:#94a3b8;box-shadow:none}
.seat.locked{background:#fef3c7;color:#92400e}
.link{margin-top:2vh;background:none;border:0;color:#4338ca;font:inherit;text-decoration:underline;min-height:48px}
@media (orientation:landscape) and (max-height:620px){body{font-size:clamp(16px,2.2vw,26px)}.pad button{min-height:2.6em}}
</style>
</head>
<body>
<h1 id="title">输入班级码</h1>
<div class="hint" id="hint">请输入老师给你的 6 位数字</div>
<div id="stage1"><div class="slots" id="slots"></div><div class="pad" id="pad"></div></div>
<div id="stage2" hidden><div class="seats" id="seats"></div><button class="link" id="back" type="button">重新输入班级码</button></div>
<script>
(function(){
  var code='',seats=[],dev='';
  try{dev=localStorage.getItem('cyDeviceId')||''}catch(e){}
  if(!dev){dev='d'+(window.crypto&&crypto.getRandomValues?Array.prototype.map.call(crypto.getRandomValues(new Uint8Array(12)),function(x){return ('0'+x.toString(16)).slice(-2)}).join(''):String(Math.random()).slice(2)+String(Date.now()));try{localStorage.setItem('cyDeviceId',dev)}catch(e){}}
  // Tablets: block pinch zoom (iOS ignores user-scalable=no).
  ['gesturestart','gesturechange','gestureend'].forEach(function(n){document.addEventListener(n,function(e){e.preventDefault()},{passive:false})});
  var $=function(id){return document.getElementById(id)};
  function hint(t,err){var h=$('hint');h.textContent=t;h.className='hint'+(err?' err':'')}
  function draw(){var s='';for(var i=0;i<6;i++)s+='<div class="slot">'+(code[i]||'')+'</div>';$('slots').innerHTML=s}
  function pad(){
    var keys=['1','2','3','4','5','6','7','8','9','清除','0','←'],h='';
    keys.forEach(function(k){h+='<button type="button" data-k="'+k+'">'+k+'</button>'});$('pad').innerHTML=h;
    Array.prototype.forEach.call($('pad').querySelectorAll('button'),function(b){b.onclick=function(){key(b.getAttribute('data-k'))}});
  }
  function key(k){
    if(k==='清除')code='';else if(k==='←')code=code.slice(0,-1);else if(code.length<6)code+=k;
    draw();hint('请输入老师给你的 6 位数字');
    if(code.length===6)lookup();
  }
  function post(path,body){return fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),cache:'no-store'}).then(function(r){return r.json().catch(function(){return {}}).then(function(d){if(!r.ok){var e=new Error(d.detail||'出错了，请再试一次');e.status=r.status;throw e}return d})})}
  function lookup(){
    hint('正在查找…');
    post('/classroom-join/lookup',{code:code}).then(function(d){
      seats=d.seats||[];$('stage1').hidden=true;$('stage2').hidden=false;$('title').textContent='点你的座号';hint((d.className||'')+' · 点一下自己的号码');
      var h='';seats.forEach(function(s){var cls='seat'+(s.taken?' taken':'')+(s.needsPassword?' locked':'');h+='<button type="button" class="'+cls+'" data-s="'+s.seat+'"'+((s.taken||s.needsPassword)?' disabled':'')+'>'+s.seat+'</button>'});
      $('seats').innerHTML=h;
      Array.prototype.forEach.call($('seats').querySelectorAll('button'),function(b){b.onclick=function(){login(Number(b.getAttribute('data-s')))}});
    }).catch(function(e){code='';draw();hint(e.message,true)});
  }
  function login(seat){
    hint('正在进入…');
    post('/classroom-join/login',{code:code,seat:seat,device_id:dev}).then(function(d){
      var user={id:d.userID,name:d.name||'',role:d.role,grade:d.grade==null?null:d.grade,mustChangePassword:false,subscription:d.subscription||null};
      try{
        sessionStorage.setItem('v717Token',d.token);sessionStorage.setItem('v717User',JSON.stringify(user));
        sessionStorage.setItem('cyQuickJoin','1');sessionStorage.setItem('cyV1Identity','student');
        sessionStorage.setItem('cyV1RoleTutorialShownThisLoginV7','student');
        localStorage.setItem('v717Remember','0');localStorage.setItem('cyV1Identity','student');
      }catch(e){}
      location.replace('/v1/classroom-quick-checks');
    }).catch(function(e){
      hint(e.message,true);
      if(e.status===409||e.status===403){post('/classroom-join/lookup',{code:code}).then(function(d){seats=d.seats||[];var all=$('seats').querySelectorAll('button');Array.prototype.forEach.call(all,function(b){var s=seats.filter(function(x){return x.seat===Number(b.getAttribute('data-s'))})[0];if(s&&(s.taken||s.needsPassword)){b.disabled=true;b.className='seat taken'}})}).catch(function(){})}
    });
  }
  $('back').onclick=function(){code='';draw();$('stage2').hidden=true;$('stage1').hidden=false;$('title').textContent='输入班级码';hint('请输入老师给你的 6 位数字')};
  draw();pad();
})();
</script>
</body>
</html>
"""

TEACHER_CODE_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="__MARKER__" content="1">
<title>班级码</title>
<style>
*{box-sizing:border-box}
html,body{margin:0;min-height:100%;background:#0f172a;color:#f8fafc;font-family:"PingFang SC","Microsoft YaHei",system-ui,sans-serif}
body{padding:3vh 4vw;font-size:clamp(18px,2.2vw,34px);text-align:center}
.code{font-size:5.5em;letter-spacing:.18em;font-weight:800;font-variant-numeric:tabular-nums;margin:2vh 0}
.sub{color:#94a3b8}
button{font:inherit;min-height:52px;padding:0 1.2em;border:0;border-radius:.6em;background:#1e293b;color:#f8fafc;margin:.4em}
button.danger{background:#7f1d1d}
#map{display:none;text-align:left;max-width:38em;margin:2vh auto;background:#1e293b;border-radius:.6em;padding:1em 1.4em;font-size:.8em}
#map div{display:flex;justify-content:space-between;gap:1em;padding:.2em 0;border-bottom:1px solid #334155}
.msg{margin-top:12vh;color:#94a3b8}
a{color:#38bdf8}
</style>
</head>
<body>
<div id="root"><div class="msg">正在连接…</div></div>
<script>
(function(){
  var SID=__SID__,root=document.getElementById('root'),timer=null,showMap=false;
  function remembered(){try{return localStorage.getItem('v717Remember')==='1'}catch(e){return false}}
  function read(store,key){try{return store.getItem(key)||''}catch(e){return ''}}
  function token(){
    var rem=remembered(),v='',first=rem?[localStorage,sessionStorage]:[sessionStorage,localStorage];
    for(var i=0;i<first.length&&!v;i++){v=read(first[i],'v717Token')}
    if(!v)v=sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||'';
    return v&&v!=='demo'?v:'';
  }
  function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
  function api(method,path){
    var t=token();if(!t){stop('请先登录老师账号');return Promise.resolve(null)}
    return fetch(path,{method:method,headers:{Authorization:'Bearer '+t},cache:'no-store'}).then(function(r){
      if(r.status===401||r.status===403||r.status===404){stop(r.status===404?'找不到这堂课，或班级码功能没有开启':'登录已失效或不是老师账号');return null}
      return r.json().then(function(d){if(!r.ok)throw new Error(d.detail||'出错了');return d});
    });
  }
  function stop(text){clearInterval(timer);root.innerHTML='<div class="msg">'+esc(text)+'<br><br><a href="/v1">前往老师登录</a></div>'}
  function mins(s){return Math.floor(s/60)+' 分钟'}
  function render(d){
    if(!d)return;
    if(!d.code){root.innerHTML='<div class="msg">'+(d.sessionStatus==='active'||d.sessionStatus==='paused'?'正在生成班级码…':'课堂开始后才会生成班级码')+'</div>';return}
    var taken=(d.seats||[]).filter(function(s){return s.taken}).length,pw=(d.seats||[]).filter(function(s){return s.needsPassword}).length;
    var h='<div class="sub">学生在平板上打开 <b>/join</b> 输入班级码</div><div class="code">'+esc(d.code)+'</div>'+
      '<div class="sub">还可使用 '+mins(d.expiresInSec)+'；课堂结束后自动失效 · 已登录 '+taken+' / '+(d.seats||[]).length+' 人'+(pw?' · '+pw+' 位同学还需先设置密码':'')+'</div>'+
      '<div><button id="regen">重新生成</button><button id="revoke" class="danger">作废班级码</button><button id="toggle">'+(showMap?'隐藏':'显示')+'座号对照表（仅老师看）</button></div>';
    var map='<div id="map" style="display:'+(showMap?'block':'none')+'">';
    (d.seats||[]).forEach(function(s){map+='<div><span>'+s.seat+' 号 · '+esc(s.studentName)+(s.needsPassword?'（需先设置密码）':'')+'</span><span>'+(s.taken?'已登录 <button data-rel="'+s.seat+'">释放</button>':'未登录')+'</span></div>'});
    root.innerHTML=h+map+'</div>';
    document.getElementById('regen').onclick=function(){api('POST','/teacher/classroom-sessions/'+SID+'/join-code').then(render)};
    document.getElementById('revoke').onclick=function(){api('DELETE','/teacher/classroom-sessions/'+SID+'/join-code').then(render)};
    document.getElementById('toggle').onclick=function(){showMap=!showMap;load()};
    Array.prototype.forEach.call(root.querySelectorAll('[data-rel]'),function(b){b.onclick=function(){api('POST','/teacher/classroom-sessions/'+SID+'/join-code/seats/'+b.getAttribute('data-rel')+'/release').then(render)}});
  }
  var first=true;
  function load(){
    api('GET','/teacher/classroom-sessions/'+SID+'/join-code').then(function(d){
      if(d&&!d.code&&first&&(d.sessionStatus==='active'||d.sessionStatus==='paused')){first=false;return api('POST','/teacher/classroom-sessions/'+SID+'/join-code')}
      first=false;return d;
    }).then(render).catch(function(){});
  }
  load();timer=setInterval(load,5000);
})();
</script>
</body>
</html>
"""

__all__ = [
    "CLASSROOM_QUICK_LOGIN_MARKER",
    "CODE_TTL_MINUTES",
    "QUICK_LOGIN_FLAG",
    "install_classroom_quick_login",
    "install_classroom_quick_login_patch",
    "patch_v1_classroom_quick_login_html",
    "quick_login_enabled",
    "register_classroom_join_tables",
]
