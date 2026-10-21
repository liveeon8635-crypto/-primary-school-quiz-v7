"""Offline builder: python -m changying.compat_tools.build_safari12 /tmp/ios12-build/node_modules.

Dev tools are pinned in the adjacent compiler; no production Node/npm dependency.
Run with an isolated SQLite DATABASE_URL, never a production database.
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from fastapi.testclient import TestClient


def collect():
    os.environ['HOMEWORK_ASSISTANT'] = '1'
    os.environ['CLASSROOM_QUICK_LOGIN'] = '1'
    from app import app
    from changying.web.safari12 import SCRIPTS, script_key, normalize_script
    paths = {'/v1/homework','/join','/v1/classroom-board/1','/v1/classroom-join-code/1','/','/classic?legacy=1','/classic?legacy=1&unified=1&page=syncLearning','/classic?legacy=1&embedded=1'}
    def routes(router):
        for route in router.routes:
            nested = getattr(route, 'original_router', None)
            if nested is not None:
                yield from routes(nested)
            else:
                yield route
    for route in routes(app):
        path = getattr(route,'path','')
        if 'GET' in getattr(route,'methods',[]) and '{' not in path and (path.startswith('/v1') or path.startswith('/homework') or path.startswith('/legal')):
            paths.add(path)
    sources, coverage = {}, {}
    with TestClient(app) as client:
        for homework, quick_login in [('0','0'),('0','1'),('1','0'),('1','1')]:
            os.environ['HOMEWORK_ASSISTANT'] = homework
            os.environ['CLASSROOM_QUICK_LOGIN'] = quick_login
            for path in sorted(paths):
                response = client.get(path, headers={'User-Agent':'Safari12-build-modern'}, follow_redirects=True)
                if response.status_code != 200 or 'text/html' not in response.headers.get('content-type',''):continue
                keys = coverage.setdefault(path, [])
                for match in SCRIPTS.finditer(response.text):
                    tag, source, _ = match.groups()
                    if 'src=' in tag or 'application/json' in tag or 'ld+json' in tag:continue
                    key = script_key(source);sources[key]=normalize_script(source)[0]
                    if key not in keys: keys.append(key)
    return sources, coverage


if __name__ == '__main__':
    if not os.environ.get('DATABASE_URL','').startswith('sqlite:'):
        raise SystemExit('Use an isolated SQLite DATABASE_URL')
    sources, coverage = collect()
    subprocess.run(['node',str(Path(__file__).with_name('compile_safari12.cjs')),sys.argv[1]],input=json.dumps({'scripts':sources,'routes':coverage}),text=True,check=True)
