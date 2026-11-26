from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from changying.services import exam_prep as ep
from changying.web.exam_prep_pages import EXAM_PREP_JS, PAPER_JS, REPORT_JS

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("exam_prep_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)

MAP = {"units": [{"key": "U1"}, {"key": "U2"}],
       "nodes": [{"key": "1-1", "unit": "U1", "kind": "core", "enabled": True},
                 {"key": "1-2", "unit": "U1", "kind": "display", "enabled": True},
                 {"key": "1-3", "unit": "U1", "kind": "optional", "enabled": False},
                 {"key": "2-1", "unit": "U2", "kind": "core", "enabled": True}]}


def test_scope_keeps_question_bearing_points_of_the_chosen_units():
    assert [n["key"] for n in ep.scope_nodes(MAP, ["U1"])] == ["1-1"]
    assert [n["key"] for n in ep.scope_nodes(MAP, ["U1", "U2"])] == ["1-1", "2-1"]


def test_compose_spreads_over_points_and_cycles_levels():
    nodes = ep.scope_nodes(MAP, ["U1", "U2"])
    pools = {"1-1": [(1, "basic"), (2, "medium"), (3, "hard"), (4, "medium"), (9, "basic")],
             "2-1": [(5, "medium"), (6, "basic"), (9, "medium")]}           # 9 sits under both points: used once
    plan = ep.compose(nodes, pools, 6)
    assert [k for k, _ in plan] == ["1-1", "2-1", "1-1", "2-1", "1-1", "2-1"]
    assert plan[0] == ("1-1", 2) and plan[1] == ("2-1", 5)                # medium first
    assert plan[2] == ("1-1", 1) and plan[3] == ("2-1", 6)                # then basic
    qids = [q for _, q in plan]
    assert len(set(qids)) == len(qids)
    assert len(ep.compose(nodes, pools, 40)) == 7                          # stops when every pool is used up
    assert 2 not in {q for _, q in ep.compose(nodes, pools, 40, avoid={2})}


def test_a_sample_paper_sets_the_type_mix():
    assert ep.type_targets(["single_choice"] * 4 + ["fill_blank"] * 3 + ["short_answer"] * 3, 7) == {
        "single_choice": 3, "fill_blank": 2, "short_answer": 2}
    assert ep.type_targets(["non_choice"], 5) == {}
    nodes = ep.scope_nodes(MAP, ["U1", "U2"])
    pools = {"1-1": [(1, "medium", "single_choice"), (2, "medium", "single_choice"), (3, "basic", "fill_blank")],
             "2-1": [(5, "medium", "single_choice"), (6, "medium", "fill_blank")]}
    plan = ep.compose(nodes, pools, 4, {"single_choice": 2, "fill_blank": 2})
    kinds = {1: "c", 2: "c", 3: "f", 5: "c", 6: "f"}
    assert sorted(kinds[q] for _, q in plan) == ["c", "c", "f", "f"]


def test_losses_weigh_marks_and_pick_three_points():
    plan = [("a", 1), ("a", 2), ("b", 3), ("b", 4), ("c", 5), ("d", 6), ("d", 7), ("d", 8)]
    answers = {1: True, 2: False, 3: False, 4: False, 5: False, 6: False, 7: True}      # 8 left unanswered
    per = ep.losses(plan, answers)
    assert {k: (v["asked"], v["lost"]) for k, v in per.items()} == {"a": (2, 1), "b": (2, 2), "c": (1, 1), "d": (3, 2)}
    # Most marks lost first; tie broken by the share lost (b 2/2 before d 2/3); then c (1/1) before a (1/2).
    assert ep.top_losses(per, ["a", "b", "c", "d"]) == ["b", "d", "c"]
    assert ep.score(plan, answers) == 25
    # With marks, one 5-mark question lost outweighs two 1-mark questions.
    marks = {1: 1, 2: 1, 3: 1, 4: 1, 5: 5, 6: 1, 7: 1, 8: 1}
    weighted = ep.losses(plan, answers, marks)
    assert ep.top_losses(weighted, list("abcd"))[0] == "c" and weighted["c"]["lostMarks"] == 5
    assert ep.score(plan, answers, marks) == round(100 * 2 / 12)
    assert ep.top_losses(ep.losses(plan, {q: True for _, q in plan}), list("abcd")) == []
    assert ep.class_points(plan, [answers, {q: True for _, q in plan}])["d"]["lost"] == 2


def test_drill_and_retest_use_fresh_questions():
    pools = {"a": [(1, "hard"), (2, "basic"), (3, "medium"), (4, "basic")], "b": [(5, "medium"), (6, "basic")]}
    assert ep.drill_picks(["a", "b"], pools, {2}, 2) == [("a", 4), ("a", 3), ("b", 6), ("b", 5)]     # basic first
    base = [("a", 1), ("a", 2), ("b", 5)]
    again = ep.retest_plan(base, pools, {1, 2, 5})
    assert [k for k, _ in again] == ["a", "a", "b"] and not {q for _, q in again} & {1, 2, 5}


def test_compare_and_countdown():
    before = {"a": {"asked": 2, "lost": 2, "marks": 4, "lostMarks": 4}, "b": {"asked": 2, "lost": 1, "marks": 4, "lostMarks": 2}}
    after = {"a": {"asked": 2, "lost": 0, "marks": 4, "lostMarks": 0}, "b": {"asked": 2, "lost": 1, "marks": 4, "lostMarks": 2}}
    got = {c["key"]: c["verdict"] for c in ep.compare(before, after, ["a", "b", "c"])}
    assert got == {"a": "已补上", "b": "还要练", "c": "未再测"}
    assert [ep.countdown(d)["stage"] for d in (30, 14, 5, 2, 0, -1)] == ["摸底", "专项", "冲刺", "考前三天", "考试日", "考后"]


def test_report_states_only_recorded_results():
    r = ep.report("小明", "期末 · 再测卷 1", {"score": 80}, {"score": 65}, [{"name": "梯形的面积", "lost": 2, "asked": 4}],
                  {"questionCount": 6, "handedIn": True, "correct": 5}, ep.countdown(10), "期末")
    text = " ".join(r["lines"])
    assert "80 分" in text and "提高了 15 分" in text and "梯形的面积（2/4" in text and "做对 5 题" in text
    assert r["stage"] == "专项" and "排名" not in text


def test_page_scripts_parse():
    for js in (EXAM_PREP_JS, PAPER_JS, REPORT_JS):
        subprocess.run(["node", "-e", "new Function(require('fs').readFileSync(0,'utf8'))"], input=js, check=True, capture_output=True, text=True)


GRADE_FORM_JS = r'''
const assert=require('assert'),vm=require('vm'),payload=JSON.parse(require('fs').readFileSync(0,'utf8'));
function el(tag,attrs,...children){
  const e={tag,attrs:attrs||{},children:[],listeners:{},disabled:false,_value:undefined,_text:'',
    appendChild(child){this.children.push(child);return child},
    addEventListener(name,fn){this.listeners[name]=fn},
    querySelectorAll(name){return this.children.reduce((out,c)=>out.concat(c&&c.tag===name?[c]:[],c&&c.querySelectorAll?c.querySelectorAll(name):[]),[])}};
  Object.defineProperty(e,'textContent',{get(){return this._text},set(v){this._text=v;this.children=[];if(this.tag==='select')this._value=undefined}});
  Object.defineProperty(e,'value',{get(){return this._value===undefined?(this.tag==='select'&&this.children.length?String(this.children[0].value):''):this._value},set(v){this._value=String(v)}});
  if(attrs)for(const k of Object.keys(attrs)){if(k==='text')e.textContent=attrs[k];else e[k]=attrs[k]}
  for(const child of children)if(child!=null)e.appendChild(child);
  return e;
}
const calls=[],ctx={el,api:(url,opts)=>{calls.push({url,opts});return Promise.resolve({id:1})},console};
vm.createContext(ctx);vm.runInContext(payload.script.replace(/epBoot\('teacher',epStart\);\s*$/,''),ctx);
ctx.EPDATA=payload.data;ctx.EPMSG=el('div');ctx.epGoal=function(){};
const box=el('div');ctx.epNewForm(box);
const select=(label)=>box.querySelectorAll('select').filter(x=>x.attrs['aria-label']===label)[0];
const cls=select('班级'),map=select('知识地图'),create=box.querySelectorAll('button').filter(x=>x.textContent==='创建')[0];
const note=box.children[0].children.filter(x=>x.attrs.role==='status')[0];
const five=payload.data.classes.filter(x=>x.grade===5);
assert.equal(cls.value,String(five[0].id));assert.deepEqual(cls.children.map(x=>x.value),five.map(x=>String(x.id)));
assert.equal(create.disabled,false);
map.value=String(payload.third.id);map.listeners.change();
assert.equal(cls.value,String(payload.thirdClass.id));assert.deepEqual(cls.children.map(x=>x.value),[String(payload.thirdClass.id)]);
map.value=String(payload.fifth.id);map.listeners.change();
assert.equal(cls.value,String(five[0].id));
map.value=String(payload.unmatched.id);map.listeners.change();
assert.equal(cls.disabled,true);assert.equal(create.disabled,true);
assert.match(note.textContent,/没有同年级班级/);assert.equal(cls.value,'');
create.onclick();assert.equal(calls.length,0);assert.match(ctx.EPMSG.textContent,/同年级/);
console.log('OK');
'''


GRADE_FORM_FLOW = r'''
import subprocess
with TestClient(app) as client:
    teacher, _, _, school_id = setup(client)
    with legacy.SessionLocal() as db:
        owner = db.scalar(select(legacy.User).where(legacy.User.username == 'teacher1'))
        first = db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id == school_id))
        first.grade = 1
        third = legacy.SchoolClass(school_id=school_id, teacher_id=owner.id, name='三年级班', grade=3)
        fifth = legacy.SchoolClass(school_id=school_id, teacher_id=owner.id, name='五年级班', grade=5)
        db.add_all([third, fifth]);db.commit();third_id=third.id
    fifth_map = client.post('/teacher/knowledge-maps', headers=teacher, json={'template':'rj2026-g5-math-up'}).json()
    response = client.get('/v1/exam-prep')
    assert response.status_code == 200 and 'function epNewForm(box)' in response.text
    page_script = 'function epTable(' + response.text.split('function epTable(', 1)[1].split("epBoot('teacher',epStart);", 1)[0] + "epBoot('teacher',epStart);"
    data = client.get('/teacher/exam-goals', headers=teacher).json()
    assert [c['grade'] for c in data['classes']] == [1, 3, 5]
    assert data['maps'][0]['id'] == fifth_map['id'] and not data['maps'][0]['published']
    third_map = {'id': -3, 'title': '三年级地图', 'grade': 3, 'published': True, 'units': [{'key':'U1', 'name':'一单元'}]}
    unmatched = {'id': -6, 'title': '六年级地图', 'grade': 6, 'published': True, 'units': [{'key':'U1', 'name':'一单元'}]}
    data['maps'].extend([third_map, unmatched])
    result = subprocess.run(['node', '-e', %r], input=json.dumps({'script': page_script, 'data': data, 'fifth': data['maps'][0],
        'third': third_map, 'thirdClass': next(c for c in data['classes'] if c['id'] == third_id), 'unmatched': unmatched}),
        text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'OK' in result.stdout
print('OK')
'''


def test_exam_goal_form_selects_matching_class_and_explains_missing_grade(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + GRADE_FORM_FLOW.replace('%r', repr(GRADE_FORM_JS)), {'KNOWLEDGE_MAP': '1'})


FLOW = r'''
from datetime import datetime, timedelta
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    ph = {"Authorization": "Bearer " + login_and_change(client, "parent1", "123456", "Parent1234")}
    with legacy.SessionLocal() as db:
        db.get(legacy.User, sid).grade = 5
        db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id == school_id)).grade = 5
        db.commit()
    for path in ("/v1/exam-prep", "/v1/exam-paper", "/v1/exam-report"):
        assert client.get(path).status_code == 200, path
    assert "href='/v1/exam-prep'" in client.get("/v1/workspace").text
    assert "student-exam-papers" in client.get("/classic?legacy=1&unified=1&page=syncLearning").text
    assert "cy-exr-band" in client.get("/classic?legacy=1&unified=1&page=childProgress").text
    d = client.post("/teacher/knowledge-maps", headers=th, json={"template": "rj2026-g5-math-up"}).json()
    mid, rev = d["id"], d["revision"]
    base = f"/teacher/knowledge-maps/{mid}/nodes"
    items = {}
    for key in ("6-1", "6-2", "6-3", "6-4"):
        for level in ("basic", "medium"):
            got = client.post(base + f"/{key}/visual", headers=th, json={"level": level, "count": 4}).json()
            r = client.post(base + f"/{key}/visual/save", headers=th, json={"level": level, "revision": rev, "questions": got["items"]}).json()
            rev = r["revision"]
            for qid, q in zip(r["saved"], got["items"]):
                items[qid] = (key, q)
    lst = client.get("/teacher/exam-goals", headers=th).json()
    assert lst["items"] == []
    assert len(lst["maps"]) == 1 and lst["maps"][0]["id"] == mid and not lst["maps"][0]["published"]
    assert any(u["key"] == "U6" for u in lst["maps"][0]["units"])  # teachers can plan before student publication
    client.post(f"/teacher/knowledge-maps/{mid}/publish", headers=th, json={"revision": rev})
    # A sample paper (for example an imported past paper): half fill-in, half choice.
    fills = [q for q, (_, it) in items.items() if it["question_type"] == "fill_blank"][:2]
    chos = [q for q, (_, it) in items.items() if it["question_type"] == "single_choice"][:2]
    with legacy.SessionLocal() as db:
        teacher = db.scalar(select(legacy.User).where(legacy.User.username == "teacher1"))
        sample = legacy.Paper(school_id=school_id, title="往年期末卷", grade=5, subject="数学", textbook="人教版", unit="真题",
                              question_ids_json=json.dumps(fills + chos), teacher_id=teacher.id)
        db.add(sample); db.commit(); sample_id = sample.id
    lst = client.get("/teacher/exam-goals", headers=th).json()
    cid = lst["classes"][0]["id"]
    assert any(p["id"] == sample_id for p in lst["samplePapers"])
    goal = {"mapId": mid, "classId": cid, "title": "期末", "examDate": (datetime.now() + timedelta(days=12)).strftime("%Y-%m-%d"), "unitKeys": ["U6"]}
    assert client.post("/teacher/exam-goals", headers=th, json={**goal, "unitKeys": ["U99"]}).status_code == 400
    assert client.post("/teacher/exam-goals", headers=th, json={**goal, "examDate": "2027-02-30"}).status_code == 400
    assert client.post("/teacher/exam-goals", headers=sh, json=goal).status_code == 403
    g = client.post("/teacher/exam-goals", headers=th, json=goal).json()
    assert g["plan"]["stage"] == "专项" and {p["key"] for p in g["points"]} >= {"6-1", "6-2", "6-3", "6-4"}
    gb = f"/teacher/exam-goals/{g['id']}"

    # Mock paper following the sample's type mix.
    mock = client.post(gb + "/mock", headers=th, json={"count": 8, "timeLimit": 60, "samplePaperId": sample_id}).json()
    assert mock["questionCount"] == 8 and mock["typeTargets"] == {"fill_blank": 4, "single_choice": 4}
    with legacy.SessionLocal() as db:
        a = db.get(legacy.Assignment, mock["assignmentId"])
        qids = json.loads(db.get(legacy.Paper, a.paper_id).question_ids_json)
    assert sorted(items[q][1]["question_type"] for q in qids) == ["fill_blank"] * 4 + ["single_choice"] * 4
    assert [items[q][0] for q in qids[:4]] == ["6-1", "6-2", "6-3", "6-4"]

    # The pupil sees it on the timed page, starts the clock once, and hands in late.
    mine = client.get("/student/exam-papers", headers=sh).json()["items"]
    assert [x["assignmentId"] for x in mine] == [mock["assignmentId"]] and mine[0]["startedAt"] is None
    s1 = client.post(f"/student/exam-papers/{mock['assignmentId']}/start", headers=sh).json()
    assert client.post(f"/student/exam-papers/{mock['assignmentId']}/start", headers=sh).json()["startedAt"] == s1["startedAt"]
    assert client.post(f"/student/exam-papers/{mock['assignmentId']}/start", headers=th).status_code == 403
    att = legacy.Base.metadata.tables["exam_attempts"]
    with legacy.SessionLocal() as db:
        db.execute(att.update().values(started_at=datetime.utcnow() - timedelta(minutes=70))); db.commit()
    assert client.get(f"/papers/{a.paper_id}/questions", headers=sh).status_code == 200

    def answer(q, bad):
        it = items[q][1]
        if it["question_type"] == "fill_blank":
            return {"question_id": q, "text_answer": "99999" if bad else it["answer"]}
        return {"question_id": q, "selected_index": (it["correct_index"] + 1) % 4 if bad else it["correct_index"]}

    sub = [answer(q, items[q][0] == "6-3") for q in qids]                 # all of 6-3 wrong
    assert client.post(f"/student/assignments/{mock['assignmentId']}/submit", headers=sh, json={"answers": sub}).status_code == 200
    an = client.get(gb + f"/papers/{mock['id']}/analysis", headers=th).json()
    me = an["pupils"][0]
    assert an["paper"]["totalMarks"] == 16 and me["score"] == round(100 * 12 / 16)
    assert [f["key"] for f in me["focus"]] == ["6-3"] and me["focus"][0]["lostMarks"] == 4
    assert me["minutes"] >= 70 and me["overtime"] >= 10
    assert client.post(f"/student/exam-papers/{mock['assignmentId']}/start", headers=sh).status_code == 409

    # Practice on the lost point: fresh 6-3 questions, basic first, never the mock's own.
    dr = client.post(gb + f"/papers/{mock['id']}/drill", headers=th, json={"perPoint": 3}).json()["results"]
    assert dr[0]["ok"] and dr[0]["questionCount"] == 3
    with legacy.SessionLocal() as db:
        da = db.get(legacy.Assignment, dr[0]["assignmentId"])
        dq = json.loads(db.get(legacy.Paper, da.paper_id).question_ids_json)
    assert all(items[q][0] == "6-3" for q in dq) and not set(dq) & set(qids) and "梯形的面积" in da.title
    assert not client.post(gb + f"/papers/{mock['id']}/drill", headers=th, json={}).json()["results"][0]["ok"]
    assert client.post(f"/student/assignments/{dr[0]['assignmentId']}/submit", headers=sh, json={"answers": [answer(q, False) for q in dq]}).status_code == 200
    me = client.get(gb + f"/papers/{mock['id']}/analysis", headers=th).json()["pupils"][0]
    assert me["drill"] == {"assignmentId": dr[0]["assignmentId"], "questionCount": 3, "handedIn": True, "correct": 3}

    # Retest: same number of questions per point, none used before; now 6-3 is right.
    rt = client.post(gb + f"/papers/{mock['id']}/retest", headers=th, json={"timeLimit": 40}).json()
    with legacy.SessionLocal() as db:
        rq = json.loads(db.get(legacy.Paper, db.get(legacy.Assignment, rt["assignmentId"]).paper_id).question_ids_json)
    assert sorted(items[q][0] for q in rq) == sorted(items[q][0] for q in qids) and not set(rq) & (set(qids) | set(dq))
    assert client.post(gb + f"/papers/{rt['id']}/retest", headers=th, json={}).status_code == 409
    client.post(f"/student/exam-papers/{rt['assignmentId']}/start", headers=sh)
    assert client.post(f"/student/assignments/{rt['assignmentId']}/submit", headers=sh, json={"answers": [answer(q, False) for q in rq]}).status_code == 200
    an2 = client.get(gb + f"/papers/{rt['id']}/analysis", headers=th).json()
    me2 = an2["pupils"][0]
    assert an2["paper"]["basePaperId"] == mock["id"] and me2["score"] == 100 and me2["before"] == 75
    assert me2["change"] == [{"key": "6-3", "before": 100, "after": 0, "verdict": "已补上", "name": me["focus"][0]["name"]}]
    tr = client.get(gb + "/trend", headers=th).json()
    assert [p["kind"] for p in tr["papers"]] == ["mock", "retest"] and tr["pupils"][0]["scores"] == [75, 100]

    # Parent report: drafted from the records, the teacher adds a note, publishes; later edits wait for a new publish.
    reps = client.post(gb + f"/papers/{rt['id']}/reports", headers=th).json()["items"]
    r = reps[0]
    text = " ".join(r["draft"]["lines"])
    assert "100 分" in text and "提高了 25 分" in text and r["draft"]["change"][0]["verdict"] == "已补上" and not r["published"]
    assert client.get(f"/parent/children/{sid}/exam-reports", headers=ph).json()["items"] == []
    client.put(f"/teacher/exam-reports/{r['id']}", headers=th, json={"note": "进步很大，继续保持"})
    pub = client.post(f"/teacher/exam-reports/{r['id']}/publish", headers=th).json()
    assert pub["published"] and not pub["changedSincePublish"]
    seen = client.get(f"/parent/children/{sid}/exam-reports", headers=ph).json()
    assert seen["items"][0]["note"] == "进步很大，继续保持" and "100 分" in " ".join(seen["items"][0]["lines"])
    assert client.put(f"/teacher/exam-reports/{r['id']}", headers=th, json={"note": "改过的话"}).json()["changedSincePublish"]
    assert client.get(f"/parent/children/{sid}/exam-reports", headers=ph).json()["items"][0]["note"] == "进步很大，继续保持"
    assert client.get(f"/parent/children/{sid + 999}/exam-reports", headers=ph).status_code == 404
    assert client.get(f"/parent/children/{sid}/exam-reports", headers=sh).status_code == 403

    # Out of reach: other goals; and everything hides behind the knowledge-map flag.
    assert client.get("/teacher/exam-goals/999", headers=th).status_code == 404
    os.environ["KNOWLEDGE_MAP"] = "0"
    assert client.get("/teacher/exam-goals", headers=th).status_code == 404
    assert client.get("/student/exam-papers", headers=sh).status_code == 404
    assert client.get("/v1/exam-paper").status_code == 404
print("OK")
'''


def test_the_whole_loop_through_the_routes(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + FLOW, {"KNOWLEDGE_MAP": "1"})
