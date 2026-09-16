"""V1 read-only fast path for mobile networks.

The frozen V1 UI historically assembled a teacher roster by issuing one HTTP
request for the class list and then one request per class. On a mobile/VPN
connection that request fan-out is visible as UI lag even when the database is
small. This module adds aggregate GET endpoints and rewrites only V1 read
paths to use them.

No schema, student data, authentication rule, or write behavior changes here.
"""

from __future__ import annotations

import re
from types import ModuleType

from fastapi import Depends
from sqlalchemy import select

from changying.web import v1 as v1_module


V1_FAST_PATH_MARKER = "changying_v1_fast_path_v1"

_LOAD_PEOPLE = re.compile(
    r"    async function loadPeople\(\)\{.*?\n    async function workspace\(\)",
    re.DOTALL,
)
_CLASSES_AND_STUDENTS = re.compile(
    r"  async function classesAndStudents\(filter=''\)\{.*?\n  async function visibleStudents\(\)",
    re.DOTALL,
)
_STUDENT_PROFILES = re.compile(
    r"  async function studentProfiles\(\)\{.*?\n  function studentLink",
    re.DOTALL,
)
_HISTORY = re.compile(
    r"  async function enhanceHistory\(\)\{.*?\n  function transitionName",
    re.DOTALL,
)


def _student_json(student) -> dict:
    return {
        "id": student.id,
        "name": student.name,
        "username": student.username,
        "grade": student.grade,
        "active": bool(student.active),
    }


def _teacher_roster(implementation: ModuleType, db, user) -> tuple[dict, dict]:
    SchoolClass = implementation.SchoolClass
    ClassStudent = implementation.ClassStudent
    User = implementation.User

    classes = db.scalars(
        select(SchoolClass)
        .where(
            SchoolClass.school_id == user.school_id,
            SchoolClass.teacher_id == user.id,
        )
        .order_by(SchoolClass.id.desc())
    ).all()
    class_ids = [row.id for row in classes]

    members_by_class: dict[int, list] = {row.id: [] for row in classes}
    student_objects: dict[int, object] = {}
    if class_ids:
        memberships = db.execute(
            select(ClassStudent.class_id, User)
            .join(User, User.id == ClassStudent.student_id)
            .where(ClassStudent.class_id.in_(class_ids))
        ).all()
        for class_id, student in memberships:
            members_by_class.setdefault(class_id, []).append(student)
            student_objects[student.id] = student

    classes_json = []
    class_rows = []
    people: dict[str, dict] = {}
    for teaching_class in classes:
        members = members_by_class.get(teaching_class.id, [])
        class_json = {
            "id": teaching_class.id,
            "name": teaching_class.name,
            "grade": teaching_class.grade,
            "teacherID": teaching_class.teacher_id,
            "studentCount": len(members),
        }
        classes_json.append(class_json)
        students_json = [_student_json(student) for student in members]
        class_rows.append({"class": class_json, "students": students_json})
        for student in members:
            if student.active is False:
                continue
            key = str(student.id)
            if key not in people:
                people[key] = {
                    **_student_json(student),
                    "teachingAffiliations": [],
                    "classIDs": [],
                }
            item = people[key]
            if teaching_class.name not in item["teachingAffiliations"]:
                item["teachingAffiliations"].append(teaching_class.name)
            if teaching_class.id not in item["classIDs"]:
                item["classIDs"].append(teaching_class.id)

    return {
        "classes": classes_json,
        "classRows": class_rows,
        "people": list(people.values()),
    }, student_objects


def install_v1_fast_read_routes(implementation: ModuleType) -> None:
    """Install aggregate teacher GET endpoints used only by the V1 shell."""

    app = implementation.app
    if getattr(app.state, "v1_fast_read_routes_installed", False):
        return

    current_user = implementation.current_user
    get_db = implementation.get_db

    @app.get("/teacher/v1-roster", include_in_schema=False)
    def teacher_v1_roster(
        u=Depends(current_user),
        db=Depends(get_db),
    ):
        implementation.need(u, "teacher")
        roster, _ = _teacher_roster(implementation, db, u)
        return roster

    @app.get("/teacher/v1-bootstrap", include_in_schema=False)
    def teacher_v1_bootstrap(
        u=Depends(current_user),
        db=Depends(get_db),
    ):
        implementation.need(u, "teacher")
        roster, _ = _teacher_roster(implementation, db, u)
        # Keep one mobile round-trip for the initial workspace. These helpers
        # are the same read-only facts previously requested through separate
        # endpoints.
        roster["stats"] = implementation.teacher_analytics_data(db, u)
        roster["workbench"] = implementation.teacher_workbench_summary(u=u, db=db)
        return roster

    @app.get("/teacher/v1-profiles", include_in_schema=False)
    def teacher_v1_profiles(
        u=Depends(current_user),
        db=Depends(get_db),
    ):
        implementation.need(u, "teacher")
        roster, student_objects = _teacher_roster(implementation, db, u)
        records = []
        for person in roster["people"]:
            student = student_objects.get(person["id"])
            if student is None:
                continue
            profile = implementation.student_growth_profile_data(
                db, student, u.school_id, None
            )
            records.append({"student": person, "profile": profile})
        return {"records": records}

    app.state.v1_fast_read_routes_installed = True


def patch_v1_fast_path(html: str) -> str:
    """Replace mobile request fan-out with aggregate GET reads."""

    if V1_FAST_PATH_MARKER in html:
        return html

    load_people = """    async function loadPeople(){window.__cyV1PeopleLoadWarnings=[];if(session.role==='admin'){const users=await api('/admin/users');return users.filter(x=>x.role==='student'&&x.active!==false)}if(session.role==='teacher'){const endpoint=location.pathname==='/v1/workspace'?'/teacher/v1-bootstrap':'/teacher/v1-roster';const data=await api(endpoint);window.__cyV1Roster=data;if(data.stats)window.__cyV1Bootstrap=data;return data.people||[]}if(session.role==='parent')return (await api('/parent/children')).filter(x=>x.active!==false);return[{id:session.userID||session.id,name:session.name,grade:session.grade,role:'student'}]}
    async function workspace()"""
    html, count = _LOAD_PEOPLE.subn(lambda _match: load_people, html, count=1)
    if count != 1:
        raise RuntimeError("V1 fast path: loadPeople marker not found")

    old_teacher_workspace = "if(session.role==='teacher'){classes=await api('/teacher/classes');stats=await api('/teacher/dashboard')}"
    new_teacher_workspace = "if(session.role==='teacher'){const boot=window.__cyV1Bootstrap||await api('/teacher/v1-bootstrap');window.__cyV1Bootstrap=boot;window.__cyV1Roster=boot;classes=boot.classes||[];stats=boot.stats||{}}"
    if old_teacher_workspace not in html:
        raise RuntimeError("V1 fast path: workspace teacher-read marker not found")
    html = html.replace(old_teacher_workspace, new_teacher_workspace, 1)

    classes_and_students = r'''  async function fastRoster(){
    if(window.__cyV1Roster)return window.__cyV1Roster;const data=await readJson('/teacher/v1-roster');window.__cyV1Roster=data;return data;
  }
  async function fastWorkbench(){
    if(window.__cyV1Bootstrap?.workbench)return window.__cyV1Bootstrap.workbench;return await readJson('/teacher/workbench-summary',0);
  }
  async function classesAndStudents(filter=''){
    const data=await fastRoster(),rows=data.classRows||[],needle=filter.trim();if(!needle)return rows;const selected=rows.filter(x=>String(x.class?.name||'').includes(needle));return selected.length?selected:rows;
  }
  async function visibleStudents()'''
    html, count = _CLASSES_AND_STUDENTS.subn(classes_and_students, html, count=1)
    if count != 1:
        raise RuntimeError("V1 fast path: operational roster marker not found")

    profiles = """  async function studentProfiles(){const data=await readJson('/teacher/v1-profiles');return data.records||[]}
  function studentLink"""
    html, count = _STUDENT_PROFILES.subn(lambda _match: profiles, html, count=1)
    if count != 1:
        raise RuntimeError("V1 fast path: studentProfiles marker not found")

    history = r'''  async function enhanceHistory(){
    if(location.pathname!='/v1/history'||document.getElementById('cy-op-history'))return;
    try{
      const data=await readJson('/teacher/v1-profiles'),source=data.records||[],records=source.map(({student,profile})=>{if(!profile)return null;const h=profile.classHistory||[],t=profile.timeline||[],s=profile.student||{};return{id:student.id,name:s.name||student.name||'学生',history:h,last:h[0]||null,timeline:t}}).filter(Boolean);
      if(!records.length)return;
      const content=`<section class="section card" id="cy-op-history"><div class="section-head"><div><h2>真实历史摘要</h2><p>一次读取当前可见学生的连续档案摘要，避免手机端逐个请求。</p></div></div><div class="cy-feature-note">已读取 ${esc(records.length)} 名当前可见学生的连续档案摘要；历史事实仍只来自现有受保护数据。</div><div class="cy-op-list">${records.map(r=>`<a class="cy-op-row" href="/v1/student?id=${r.id}"><span><b>${esc(r.name)}</b><small>${r.history.length} 条班级历史 · ${r.timeline.length} 条时间线</small></span><small>${esc(r.last?.className||r.last?.name||'打开连续档案')}</small></a>`).join('')}</div></section>`;visibleScreen()?.insertAdjacentHTML('beforeend',content)
    }catch{}
  }
  function transitionName'''
    html, count = _HISTORY.subn(history, html, count=1)
    if count != 1:
        raise RuntimeError("V1 fast path: history marker not found")

    html = html.replace(
        "await readJson('/teacher/workbench-summary')",
        "await fastWorkbench()",
    )

    # The base student page already fetched this profile. Publish it so the
    # operational continuity card can reuse the same payload instead of issuing
    # a duplicate request after render. Keep the original if/else chain valid
    # by replacing the complete teacher/admin branch rather than only its body.
    profile_fetch = "if(session.role==='teacher'||session.role==='admin')profile=await api('/teacher/students/'+id+'/growth-profile')"
    if profile_fetch not in html:
        raise RuntimeError("V1 fast path: student detail marker not found")
    html = html.replace(
        profile_fetch,
        "if(session.role==='teacher'||session.role==='admin'){profile=await api('/teacher/students/'+id+'/growth-profile');window.__cyV1StudentProfile={id,profile}}",
        1,
    )
    html = html.replace(
        "const p=await readJson('/teacher/students/'+id+'/growth-profile')",
        "const p=(window.__cyV1StudentProfile?.id===id?window.__cyV1StudentProfile.profile:await readJson('/teacher/students/'+id+'/growth-profile'))",
        1,
    )

    return html.replace("</body>", f"<!-- {V1_FAST_PATH_MARKER} --></body>", 1)


def install_v1_fast_path_patch() -> None:
    """Install the final V1 read-path optimization exactly once."""

    if getattr(v1_module, "_fast_path_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_fast_path(original())

    v1_module.v1_html = patched_v1_html
    v1_module._fast_path_patch_installed = True


__all__ = [
    "V1_FAST_PATH_MARKER",
    "install_v1_fast_path_patch",
    "install_v1_fast_read_routes",
    "patch_v1_fast_path",
]
