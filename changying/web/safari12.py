"""Serve precompiled Safari 12 scripts on the existing HTML routes.

Compilation happens offline, never on the old iPad or in the Python web worker.
Modern responses retain their original scripts. Both representations vary by UA.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

from fastapi import Request, Response

ASSETS = Path(__file__).with_name('safari12_assets')
SCRIPTS = re.compile(r'(<script\b[^>]*>)([\s\S]*?)(</script\s*>)', re.I)
SESSION_ID = re.compile(r'(var SID\s*=)\s*(\d+)')
BUILD = re.compile(r'(const PAGE_BUILD\s*=)\s*("[^"\n]*"|\'[^\'\n]*\')\s*;')


def normalize_script(source: str) -> tuple[str, str | None]:
    match = BUILD.search(source)
    value = match.group(2) if match else None
    normalized = BUILD.sub(r'\1"__CY_BUILD__";', source)
    return SESSION_ID.sub(r'\1"__CY_SESSION__"', normalized).rstrip(), value


def script_key(source: str) -> str:
    return hashlib.sha256(normalize_script(source)[0].encode()).hexdigest()


def safari12_agent(agent: str) -> bool:
    return bool(re.search(r'(?:CPU(?: iPhone)? OS 12[_\d]*|Version/12\.[\d.]+.*Safari/)', agent))


@lru_cache(maxsize=1)
def _manifest() -> dict:
    return json.loads((ASSETS/'manifest.json').read_text())


@lru_cache(maxsize=128)
def _compiled(key: str) -> str:
    return gzip.decompress(base64.b64decode((ASSETS/(key+'.js.gz.b64')).read_bytes())).decode()


def compatible_html(html: str) -> str:
    manifest = _manifest()
    def script(match):
        tag, source, end = match.groups()
        if re.search(r'\bsrc\s*=', tag, re.I) or re.search(r'type\s*=\s*["\'](?:application/(?:ld\+)?json|importmap)', tag, re.I):
            return match.group(0)
        key = script_key(source)
        if key not in manifest['scripts']:
            # Coverage tests require every shipped inline executable script.
            # An explicit error is preferable to silently shipping stale code.
            raise ValueError('Safari 12 assets need regeneration: '+key)
        _, build = normalize_script(source)
        code = source if manifest['scripts'][key]['unchanged'] else _compiled(key)
        session_id = SESSION_ID.search(source)
        if session_id is not None and not manifest['scripts'][key]['unchanged']:
            code = code.replace('"__CY_SESSION__"', session_id.group(2)).replace("'__CY_SESSION__'", session_id.group(2))
        if build is not None:
            code = code.replace('"__CY_BUILD__"', build).replace("'__CY_BUILD__'", build)
        return tag+code+end
    html = SCRIPTS.sub(script, html)
    runtime = (ASSETS/'runtime.js').read_text(encoding='utf-8')
    css = (ASSETS/'fallback.css').read_text()
    return html.replace('</head>', '<style id="cy-safari12-css">'+css+'</style><script id="cy-safari12-runtime">'+runtime+'</script></head>', 1)


async def safari12_response(request: Request, response: Response) -> Response:
    if request.method != 'GET' or response.status_code != 200 or 'text/html' not in response.headers.get('content-type', ''):
        return response
    vary = response.headers.get('vary', '')
    if 'user-agent' not in vary.lower():
        response.headers['Vary'] = (vary+', ' if vary else '')+'User-Agent'
    if not safari12_agent(request.headers.get('user-agent', '')):
        return response
    if hasattr(response, 'body_iterator'):
        body = b''.join([part.encode() if isinstance(part, str) else part async for part in response.body_iterator])
    else:
        body = response.body
    encoding = response.headers.get('content-encoding', '')
    raw = gzip.decompress(body) if encoding == 'gzip' else body
    rewritten = compatible_html(raw.decode()).encode()
    body = gzip.compress(rewritten, mtime=0) if encoding == 'gzip' else rewritten
    rebuilt = Response(body, status_code=response.status_code, background=response.background)
    rebuilt.raw_headers = [(k,v) for k,v in response.raw_headers if k.lower() not in (b'content-length', b'etag')]
    rebuilt.headers['Content-Length'] = str(len(body))
    rebuilt.headers['X-Changying-Safari12'] = 'compiled-v1'
    return rebuilt
