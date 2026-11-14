import os, runpy, threading
from concurrent.futures import ThreadPoolExecutor
# Run against a newly created isolated PostgreSQL database.
url = os.environ.get('TEST_HOMEWORK_POSTGRES_URL')
if not url:
    raise RuntimeError('Set TEST_HOMEWORK_POSTGRES_URL to an empty isolated PostgreSQL database')
os.environ['DATABASE_URL'] = url
os.environ['HOMEWORK_ASSISTANT']='1'
os.environ['ENABLE_DEMO_SEED']='1'
common=runpy.run_path('tests/test_homework_notices.py')['COMMON']
common = common.replace('from app import app', 'legacy.Base.metadata.create_all(bind=legacy.engine)\nfrom app import app')
exec(common)
from sqlalchemy import text
with TestClient(app) as client:
    th, sh, sid = teacher_student_headers(client)
    nid = client.post('/teacher/homework/notices',headers=th,json=json.loads(NOTICE_JSON)).json()['id']
    assert client.post(f'/teacher/homework/notices/{nid}/publish',headers=th,json={'studentIDs':[sid]}).status_code == 200
    for iteration in range(30):
        with legacy.SessionLocal() as db:
            db.execute(text("UPDATE homework_recipients SET done_json='[]',started_at=NULL,completed_at=NULL WHERE notice_id=:n"),{'n':nid})
            db.commit()
        barrier=threading.Barrier(2)
        def tick(n):
            barrier.wait()
            r=client.post(f'/student/homework/items/{nid}/{n}/done',headers=sh,json={'done':True})
            return r.status_code, r.text
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(tick,[1,2]))
        assert all(x[0]==200 for x in results), results
        row=client.get('/student/homework/today',headers=sh).json()[0]
        assert all(item['done'] for item in row['items']), row
    nid2 = client.post('/teacher/homework/notices',headers=th,json=json.loads(NOTICE_JSON)).json()['id']
    barrier = threading.Barrier(2)
    def publish(_):
        barrier.wait()
        r = client.post(f'/teacher/homework/notices/{nid2}/publish', headers=th, json={'studentIDs':[sid]})
        return r.status_code, r.text
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(publish, range(2)))
    assert all(x[0] == 200 for x in results), results
    with legacy.SessionLocal() as db:
        assert db.execute(text('select count(*) from homework_recipients where notice_id=:n'), {'n': nid2}).scalar_one() == 1
    from sqlalchemy import event
    nid3 = client.post('/teacher/homework/notices', headers=th, json=json.loads(NOTICE_JSON)).json()['id']
    entered, release = threading.Event(), threading.Event()
    def pause_edit(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith('UPDATE homework_notices SET group_label='):
            entered.set()
            assert release.wait(15)
    event.listen(legacy.engine, 'before_cursor_execute', pause_edit)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(client.put, f'/teacher/homework/notices/{nid3}', headers=th, json=json.loads(NOTICE_JSON))
        assert entered.wait(15)
        published = client.post(f'/teacher/homework/notices/{nid3}/publish', headers=th, json={'studentIDs':[sid]})
        release.set()
        edited = pending.result(timeout=15)
    event.remove(legacy.engine, 'before_cursor_execute', pause_edit)
    assert published.status_code == 200 and edited.status_code == 409, (published.text, edited.text)
    allow_ai(school_of(sid))
    request = client.post('/student/homework/help', headers=sh, json={'questionText':'3+5=?','grade':3})
    assert request.status_code == 200, request.text
    hid = request.json()['id']
    assert client.post(f'/student/homework/help/{hid}/escalate',headers=sh,json={}).status_code == 200
    barrier = threading.Barrier(2)
    seen = threading.local()
    def pause_resolve(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith('UPDATE help_requests SET state=') and 'teacher_note' in statement and not getattr(seen, 'waited', False):
            seen.waited = True
            barrier.wait(timeout=15)
    event.listen(legacy.engine, 'before_cursor_execute', pause_resolve)
    def resolve(note):
        r = client.post(f'/teacher/homework/help/{hid}/resolve',headers=th,json={'note':note})
        return r.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(resolve,['备注甲','备注乙']))
    event.remove(legacy.engine, 'before_cursor_execute', pause_resolve)
    assert sorted(results) == [200, 409], results
    print('PostgreSQL: 30 concurrent ticks; concurrent publish; edit/publish race; concurrent resolve passed')
