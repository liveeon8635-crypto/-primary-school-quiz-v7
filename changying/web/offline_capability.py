"""A minimal, safe offline entry for the web app.

The 2026-11-10 production audit found 断网完全不能用: ``/sw.js`` had been retired to a
350-byte stub that only unregisters itself, so opening the app without a network gave the
browser error page, and the "离线体验" button still needed a live login page first.

This module restores the smallest useful piece only:

* ``/offline-sw.js`` — a service worker that precaches **one** page (``/offline-practice``)
  and, for page navigations, tries the network first and falls back to that cached page.
  It never caches API responses or authenticated pages, so no student, parent or class data
  is ever stored on a shared device.
* ``/offline-practice`` — a self-contained practice page (ES5 on purpose, iOS 12 Safari is a
  supported client) with a handful of built-in questions; it grades locally and needs no
  network at all.

The v1 shell only gets a registration snippet, so no page markup is rewritten.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from changying.web import v1 as v1_module

OFFLINE_SW_PATH = "/offline-sw.js"
OFFLINE_PRACTICE_PATH = "/offline-practice"
OFFLINE_SW_VERSION = "offline-v1"
V1_OFFLINE_MARKER = "changying_v1_offline_capability_v1"

# ES5 only: iOS 12 Safari still runs this worker without a transpiled copy.
OFFLINE_SW_JS = r"""
/* 长缨辅学 offline entry: cache one practice page, never touch API data. */
var CACHE = 'changying-offline-v1';
var FALLBACK = '/offline-practice';
var PRECACHE = [FALLBACK];

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(CACHE).then(function (cache) {
      return cache.addAll(PRECACHE);
    }).then(function () {
      return self.skipWaiting();
    })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.map(function (key) {
        if (key !== CACHE && key.indexOf('changying-offline-') === 0) return caches.delete(key);
        return null;
      }));
    }).then(function () {
      return self.clients.claim();
    })
  );
});

self.addEventListener('fetch', function (event) {
  var request = event.request;
  if (request.method !== 'GET') return;
  var isNavigation = request.mode === 'navigate';
  if (!isNavigation) {
    // Only the precached offline page is ever served from the cache.
    if (new URL(request.url).pathname === FALLBACK) {
      event.respondWith(
        caches.match(FALLBACK).then(function (cached) {
          return cached || fetch(request);
        })
      );
    }
    return;
  }
  event.respondWith(
    fetch(request).catch(function () {
      return caches.match(FALLBACK).then(function (cached) {
        return cached || new Response('离线且没有缓存页面', {
          status: 503,
          headers: { 'Content-Type': 'text/plain; charset=utf-8' }
        });
      });
    })
  );
});
"""

OFFLINE_PRACTICE_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#5964E8">
<title>长缨辅学 · 离线练习</title>
<style>
:root{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;color:#1f2937;background:#eef1f8}
*{box-sizing:border-box}
body{margin:0;padding:16px 14px 40px}
.wrap{max-width:720px;margin:0 auto}
.head{background:#5964e8;color:#fff;border-radius:20px;padding:18px 20px;margin-bottom:14px}
.head h1{margin:0 0 6px;font-size:22px}
.head p{margin:0;font-size:14px;line-height:1.6;opacity:.92}
.card{background:#fff;border-radius:18px;padding:18px;margin-bottom:12px;box-shadow:0 8px 26px rgba(32,45,90,.07)}
.q{font-size:18px;font-weight:700;line-height:1.5;margin:0 0 12px}
.opt{display:block;width:100%;text-align:left;border:1px solid #e3e7f2;background:#fbfcff;border-radius:12px;padding:14px;font-size:16px;margin-bottom:8px;color:#1f2937}
.opt.on{border-color:#5964e8;background:#eef0ff}
.opt.ok{border-color:#18855d;background:#e9f7f1}
.opt.no{border-color:#d6485e;background:#fdecef}
.note{font-size:14px;line-height:1.7;color:#5b6478;margin:10px 0 0}
.badge{display:inline-block;padding:5px 10px;border-radius:999px;background:#fff4dc;color:#9a6413;font-weight:700;font-size:13px}
.btn{width:100%;border:0;border-radius:14px;padding:15px;font-size:17px;font-weight:700;background:#5964e8;color:#fff;margin-top:8px}
.btn.sec{background:#e7eaf5;color:#374151}
.score{font-size:34px;font-weight:900;color:#5964e8;margin:4px 0}
.foot{font-size:13px;color:#7b8499;line-height:1.7;text-align:center;margin-top:18px}
</style>
</head>
<body>
<div class="wrap">
  <div class="head">
    <h1>离线练习</h1>
    <p>当前没有网络，也能做题。题目是内置的，不连接服务器，也不会保存任何学习记录；联网后请回到长缨辅学正常登录，成绩和积分以老师端看到的为准。</p>
  </div>
  <div id="quiz"></div>
  <div class="foot">这份练习只用于保持手感，不计入课堂成绩。</div>
</div>
<script>
(function () {
  var BANK = [
    { q: '0.4 × 3 = ?', options: ['0.12', '1.2', '12', '120'], answer: 1 },
    { q: '一个数是 24，它的 1/4 是多少？', options: ['4', '6', '8', '12'], answer: 1 },
    { q: '长方形长 8 厘米、宽 5 厘米，面积是多少平方厘米？', options: ['13', '26', '40', '80'], answer: 2 },
    { q: '把 0.25 化成分数是？', options: ['1/2', '1/4', '1/5', '1/8'], answer: 1 },
    { q: '3.6 ÷ 0.9 = ?', options: ['0.4', '4', '40', '0.04'], answer: 1 },
    { q: '一个三角形两个角分别是 45° 和 55°，第三个角是多少度？', options: ['70°', '80°', '90°', '100°'], answer: 1 }
  ];
  var state = { index: 0, picked: -1, locked: false, correct: 0, done: false };
  var box = document.getElementById('quiz');

  function esc(value) {
    return String(value === null || value === undefined ? '' : value).replace(/[&<>"']/g, function (ch) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch];
    });
  }

  function render() {
    if (state.done) {
      var total = BANK.length;
      var pct = Math.round(state.correct * 100 / total);
      box.innerHTML =
        '<div class="card"><span class="badge">离线练习完成</span>' +
        '<div class="score">' + pct + ' 分</div>' +
        '<p class="note">答对 ' + state.correct + ' / ' + total + ' 题。这份成绩不会上传，也不会记入档案。</p>' +
        '<button class="btn" id="again">再来一组</button>' +
        '<button class="btn sec" id="retry">重新联网并返回长缨辅学</button></div>';
      document.getElementById('again').onclick = function () {
        state = { index: 0, picked: -1, locked: false, correct: 0, done: false };
        render();
      };
      document.getElementById('retry').onclick = function () {
        location.href = '/v1';
      };
      return;
    }
    var item = BANK[state.index];
    var options = '';
    for (var i = 0; i < item.options.length; i++) {
      var cls = 'opt';
      if (state.locked) {
        if (i === item.answer) cls += ' ok';
        else if (i === state.picked) cls += ' no';
      } else if (i === state.picked) {
        cls += ' on';
      }
      options += '<button class="' + cls + '" data-i="' + i + '">' +
        String.fromCharCode(65 + i) + '. ' + esc(item.options[i]) + '</button>';
    }
    var feedback = '';
    if (state.locked) {
      feedback = state.picked === item.answer
        ? '<p class="note">答对了。</p>'
        : '<p class="note">正确答案是 ' + String.fromCharCode(65 + item.answer) + '。先想一想再做下一题。</p>';
    }
    box.innerHTML =
      '<div class="card"><span class="badge">第 ' + (state.index + 1) + ' / ' + BANK.length + ' 题</span>' +
      '<p class="q">' + esc(item.q) + '</p>' + options + feedback +
      '<button class="btn" id="next"' + (state.picked < 0 ? ' disabled' : '') + '>' +
      (state.locked ? (state.index === BANK.length - 1 ? '看结果' : '下一题') : '确定') + '</button></div>';

    var buttons = box.querySelectorAll('.opt');
    for (var b = 0; b < buttons.length; b++) {
      buttons[b].onclick = function (event) {
        if (state.locked) return;
        state.picked = Number(event.currentTarget.getAttribute('data-i'));
        render();
      };
    }
    document.getElementById('next').onclick = function () {
      if (!state.locked) {
        state.locked = true;
        if (state.picked === item.answer) state.correct += 1;
        render();
        return;
      }
      if (state.index === BANK.length - 1) {
        state.done = true;
      } else {
        state.index += 1;
        state.picked = -1;
        state.locked = false;
      }
      render();
    };
  }

  render();
})();
</script>
</body>
</html>
"""

_REGISTER_SNIPPET = """
<script id="changying_v1_offline_capability_v1-script">
if('serviceWorker' in navigator){window.addEventListener('load',function(){navigator.serviceWorker.register('/offline-sw.js',{scope:'/'}).catch(function(){});});}
</script>
"""


def patch_v1_offline_capability(html: str) -> str:
    """Add the service-worker registration snippet to the v1 shell."""
    if V1_OFFLINE_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V1 offline capability patch: closing body marker not found")
    return html.replace("</body>", _REGISTER_SNIPPET + f"<!-- {V1_OFFLINE_MARKER} --></body>", 1)


def install_offline_capability(implementation) -> bool:
    """Register the offline routes and patch the v1 shell (idempotent)."""
    if getattr(implementation, "_offline_capability_installed", False):
        return True

    router = APIRouter()

    @router.get(OFFLINE_SW_PATH, include_in_schema=False)
    def offline_service_worker() -> Response:
        response = Response(OFFLINE_SW_JS, media_type="application/javascript; charset=utf-8")
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Service-Worker-Allowed"] = "/"
        response.headers["X-Changying-SW"] = OFFLINE_SW_VERSION
        return response

    @router.get(OFFLINE_PRACTICE_PATH, include_in_schema=False)
    def offline_practice_page() -> HTMLResponse:
        response = HTMLResponse(OFFLINE_PRACTICE_HTML)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Changying-Offline"] = OFFLINE_SW_VERSION
        return response

    implementation.app.include_router(router)

    if not getattr(v1_module, "_offline_capability_patch_installed", False):
        original = v1_module.v1_html

        def patched_v1_html() -> str:
            return patch_v1_offline_capability(original())

        v1_module.v1_html = patched_v1_html
        v1_module._offline_capability_patch_installed = True

    implementation._offline_capability_installed = True
    return True


__all__ = [
    "OFFLINE_PRACTICE_HTML",
    "OFFLINE_PRACTICE_PATH",
    "OFFLINE_SW_JS",
    "OFFLINE_SW_PATH",
    "OFFLINE_SW_VERSION",
    "V1_OFFLINE_MARKER",
    "install_offline_capability",
    "patch_v1_offline_capability",
]
