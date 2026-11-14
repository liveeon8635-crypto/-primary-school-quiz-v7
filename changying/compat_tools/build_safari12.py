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


def collect_variant():
    # Startup feature flags must be set before app import in this fresh process.
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


def collect():
    sources, coverage = {}, {}
    for homework, quick_login in [('0','0'),('0','1'),('1','0'),('1','1')]:
        env = dict(os.environ, HOMEWORK_ASSISTANT=homework, CLASSROOM_QUICK_LOGIN=quick_login, KNOWLEDGE_MAP='1')
        result = subprocess.run(
            [sys.executable, '-m', 'changying.compat_tools.build_safari12', '--collect'],
            env=env, text=True, capture_output=True, check=True, timeout=90,
        )
        variant = json.loads(result.stdout)
        sources.update(variant['scripts'])
        for path, keys in variant['routes'].items():
            merged = coverage.setdefault(path, [])
            merged.extend(key for key in keys if key not in merged)
    return sources, coverage


if __name__ == '__main__':
    if not os.environ.get('DATABASE_URL','').startswith('sqlite:'):
        raise SystemExit('Use an isolated SQLite DATABASE_URL')
    if len(sys.argv) > 1 and sys.argv[1] == '--collect':
        sources, coverage = collect_variant()
        print(json.dumps({'scripts': sources, 'routes': coverage}))
        raise SystemExit(0)
    if len(sys.argv) > 1 and sys.argv[1] == '--check':
        # Report drift without compiling: exit 1 when any inline script is missing
        # from, or stale in, the committed manifest.
        sources, coverage = collect()
        manifest_path = Path(__file__).resolve().parents[1] / 'web' / 'safari12_assets' / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        missing = sorted(set(sources) - set(manifest['scripts']))
        extra = sorted(set(manifest['scripts']) - set(sources))
        print(json.dumps({'scripts': len(sources), 'routes': len(coverage), 'missing': missing, 'extra': extra}))
        raise SystemExit(1 if missing or extra else 0)
    # The toolchain directory stays outside the repository so a stale working copy
    # never has to reinstall it: pass it as argv[1], set SAFARI12_NODE_MODULES, or
    # rely on the per-user default below (created once by the npm command).
    modules = os.environ.get('SAFARI12_NODE_MODULES') or (sys.argv[1] if len(sys.argv) > 1 else '')
    if not modules:
        for candidate in (Path(os.environ.get('LOCALAPPDATA','/tmp')) / 'ios12-build' / 'node_modules', Path('/tmp/ios12-build/node_modules')):
            if (candidate / '@babel' / 'core').exists():
                modules = str(candidate)
                break
        else:
            modules = str(Path(os.environ.get('LOCALAPPDATA','/tmp')) / 'ios12-build' / 'node_modules')
    if not (Path(modules) / '@babel' / 'core').exists():
        raise SystemExit(
            'Safari 12 toolchain missing at {0}. Install it once: npm install --prefix "{1}" '
            '--no-audit --no-fund @babel/core@7.28.5 @babel/preset-env@7.28.5 acorn@8.15.0'.format(modules, Path(modules).parent)
        )
    sources, coverage = collect()
    subprocess.run(['node',str(Path(__file__).with_name('compile_safari12.cjs')),modules],input=json.dumps({'scripts':sources,'routes':coverage}),text=True,check=True)
