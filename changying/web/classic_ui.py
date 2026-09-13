"""Non-invasive UI polish for the legacy 长缨辅学 app.

The legacy monolith still owns the complete internal feature set. This module
only enhances the HTML shell returned from /classic: it injects a small brand
ribbon and conservative CSS tokens so the old interface feels closer to the new
workbench without touching database, auth, or business logic.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

CLASSIC_UI_MARKER = "changying_classic_ui_v1"
CLASSIC_UI_PATHS = {"/classic"}

CLASSIC_UI_SNIPPET = f"""
<style id="{CLASSIC_UI_MARKER}-style">
  :root{{
    --cy-brand:#3047ff;
    --cy-brand-soft:#eef2ff;
    --cy-green:#10a874;
    --cy-ink:#172033;
    --cy-muted:#68738a;
    --cy-line:#e6eaf3;
    --cy-radius:14px;
  }}
  body.cy-classic-enhanced{{
    background:linear-gradient(180deg,#f7f9ff 0%,#f4f7ff 44%,#f8fafc 100%) !important;
    color:var(--cy-ink);
    -webkit-font-smoothing:antialiased;
  }}
  .cy-classic-ribbon{{
    position:sticky;
    top:0;
    z-index:2147483000;
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:12px;
    padding:10px 14px;
    margin:0;
    background:rgba(255,255,255,.94);
    border-bottom:1px solid var(--cy-line);
    box-shadow:0 10px 28px rgba(23,32,51,.08);
    backdrop-filter:blur(12px);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
  }}
  .cy-classic-ribbon__brand{{display:flex;align-items:center;gap:10px;min-width:0}}
  .cy-classic-ribbon__logo{{width:32px;height:32px;border-radius:11px;display:grid;place-items:center;background:linear-gradient(145deg,#3047ff,#6b7cff);color:#fff;font-weight:900}}
  .cy-classic-ribbon__text{{font-weight:900;color:var(--cy-ink);white-space:nowrap}}
  .cy-classic-ribbon__hint{{color:var(--cy-muted);font-size:12px;margin-left:6px}}
  .cy-classic-ribbon__actions{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
  .cy-classic-ribbon a{{text-decoration:none}}
  .cy-classic-btn{{border:1px solid var(--cy-line);background:#fff;color:var(--cy-ink);padding:8px 11px;border-radius:999px;font-size:12px;font-weight:800;box-shadow:0 6px 18px rgba(23,32,51,.06)}}
  .cy-classic-btn--primary{{background:var(--cy-brand);border-color:var(--cy-brand);color:#fff}}
  body.cy-classic-enhanced button,
  body.cy-classic-enhanced .btn,
  body.cy-classic-enhanced input[type="button"],
  body.cy-classic-enhanced input[type="submit"]{{
    border-radius:12px;
    transition:transform .16s ease,box-shadow .16s ease,background .16s ease;
  }}
  body.cy-classic-enhanced button:hover,
  body.cy-classic-enhanced .btn:hover{{
    transform:translateY(-1px);
    box-shadow:0 10px 24px rgba(23,32,51,.12);
  }}
  body.cy-classic-enhanced input,
  body.cy-classic-enhanced select,
  body.cy-classic-enhanced textarea{{
    border-radius:12px;
    border-color:var(--cy-line);
  }}
  body.cy-classic-enhanced table{{
    border-radius:14px;
    overflow:hidden;
  }}
  body.cy-classic-enhanced .card,
  body.cy-classic-enhanced .panel,
  body.cy-classic-enhanced .box,
  body.cy-classic-enhanced section{{
    border-radius:var(--cy-radius);
  }}
  @media(max-width:720px){{
    .cy-classic-ribbon{{align-items:flex-start;flex-direction:column}}
    .cy-classic-ribbon__hint{{display:block;margin-left:0;margin-top:2px}}
    .cy-classic-ribbon__actions{{width:100%}}
    .cy-classic-btn{{flex:1;text-align:center}}
  }}
</style>
<script id="{CLASSIC_UI_MARKER}-script">
(function(){{
  if(document.getElementById('{CLASSIC_UI_MARKER}-ribbon')) return;
  document.documentElement.classList.add('cy-classic-enhanced-root');
  function mount(){{
    if(document.getElementById('{CLASSIC_UI_MARKER}-ribbon')) return;
    document.body.classList.add('cy-classic-enhanced');
    var ribbon=document.createElement('div');
    ribbon.id='{CLASSIC_UI_MARKER}-ribbon';
    ribbon.className='cy-classic-ribbon';
    ribbon.innerHTML='<div class="cy-classic-ribbon__brand"><span class="cy-classic-ribbon__logo">长</span><span><span class="cy-classic-ribbon__text">长缨辅学完整系统</span><span class="cy-classic-ribbon__hint">内部功能已保留，正在逐步统一新版 UI</span></span></div><div class="cy-classic-ribbon__actions"><a class="cy-classic-btn cy-classic-btn--primary" href="/workbench">新版工作台</a><a class="cy-classic-btn" href="/classic">完整系统首页</a></div>';
    document.body.insertBefore(ribbon,document.body.firstChild);
  }}
  if(document.readyState==='loading'){{document.addEventListener('DOMContentLoaded',mount);}}else{{mount();}}
}})();
</script>
"""


def is_classic_html_path(path: str) -> bool:
    """Return whether a request path should receive the classic UI enhancement."""
    return path in CLASSIC_UI_PATHS


def inject_classic_ui(html: str) -> str:
    """Inject the classic UI enhancement into an HTML document once."""
    if CLASSIC_UI_MARKER in html:
        return html
    if "</body>" in html:
        return html.replace("</body>", CLASSIC_UI_SNIPPET + "\n</body>", 1)
    return html + CLASSIC_UI_SNIPPET


async def _body_bytes(response: Response) -> bytes:
    chunks = []
    async for chunk in response.body_iterator:  # type: ignore[attr-defined]
        if isinstance(chunk, str):
            chunk = chunk.encode(response.charset or "utf-8")
        chunks.append(chunk)
    return b"".join(chunks)


def install_classic_ui_patch(app: FastAPI) -> None:
    """Install a small HTML-only enhancement for the legacy /classic page."""
    if getattr(app.state, "classic_ui_patch_installed", False):
        return

    @app.middleware("http")
    async def classic_ui_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        if request.method != "GET" or not is_classic_html_path(request.url.path):
            return response
        if response.status_code != 200:
            return response
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type:
            return response

        raw = await _body_bytes(response)
        charset = response.charset or "utf-8"
        html = raw.decode(charset, errors="replace")
        enhanced = inject_classic_ui(html).encode(charset)
        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers["X-Changying-Classic-UI"] = CLASSIC_UI_MARKER
        return Response(
            enhanced,
            status_code=response.status_code,
            headers=headers,
            media_type="text/html",
        )

    app.state.classic_ui_patch_installed = True


__all__ = [
    "CLASSIC_UI_MARKER",
    "CLASSIC_UI_PATHS",
    "inject_classic_ui",
    "install_classic_ui_patch",
    "is_classic_html_path",
]
