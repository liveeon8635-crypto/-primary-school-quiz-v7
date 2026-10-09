"""Cinematic title sequence: 哪吒用混天绫束缚苍龙.

Every 30 seconds a letterboxed "screen" drops from under the fixed header,
pushes the camera into the painting, whips the 混天绫 out toward the viewer,
flashes and closes again, leaving only the shimmering silk in the header.

Pure CSS animation (transform/opacity/clip-path); the script only restarts it.
The painting is served from ``/v1/assets/cinematic-nezha.webp`` so it is cached
by the browser instead of being inlined into every page.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, FastAPI, Response

from changying.web import v1 as v1_module

V1_CINEMATIC_MARKER = "changying_v1_cinematic_v1"
CINEMATIC_ASSET_PATH = "/v1/assets/cinematic-nezha.webp"
_ASSET_FILE = Path(__file__).with_name("assets") / "cinematic_nezha.webp"

_SNIPPET = r'''
<style id="changying_v1_cinematic_v1-style">
#cy-cine{position:fixed;left:0;right:0;top:88px;height:min(66vh,600px);z-index:40;pointer-events:none;overflow:hidden;visibility:hidden;clip-path:inset(0 0 100% 0);background:#0b1522;box-shadow:0 18px 50px rgba(0,0,0,.35)}
#cy-cine.play{visibility:visible;animation:cyCineOpen 9s linear both}
@keyframes cyCineOpen{0%{clip-path:inset(0 0 100% 0)}7%{clip-path:inset(0 0 0 0)}88%{clip-path:inset(0 0 0 0)}100%{clip-path:inset(0 0 100% 0)}}
#cy-cine .cy-cine-view{position:absolute;inset:0;overflow:hidden;perspective:900px}
#cy-cine .cy-cine-img,#cy-cine .cy-cine-fg{position:absolute;left:-4%;top:-4%;width:108%;height:108%;object-fit:cover;object-position:30% 22%;will-change:transform}
#cy-cine .cy-cine-img{transform-origin:46% 40%}
#cy-cine .cy-cine-fg{transform-origin:50% 100%;-webkit-mask-image:linear-gradient(to top,#000 24%,transparent 46%);mask-image:linear-gradient(to top,#000 24%,transparent 46%)}
#cy-cine.play .cy-cine-img{animation:cyCineCam 9s cubic-bezier(.45,0,.3,1) both}
#cy-cine.play .cy-cine-fg{animation:cyCineFg 9s cubic-bezier(.45,0,.3,1) both}
@keyframes cyCineCam{0%{transform:scale(1) translate(0,0) rotate(-.6deg)}74%{transform:scale(1.3) translate(-2%,0) rotate(.4deg)}77%{transform:scale(1.32) translate(-2.4%,-.4%) rotate(.4deg)}80%{transform:scale(1.3) translate(-1.6%,.2%) rotate(.4deg)}100%{transform:scale(1.36) translate(-2%,0) rotate(.4deg)}}
@keyframes cyCineFg{0%{transform:scale(1) translateY(0)}74%{transform:scale(1.7) translateY(-5%)}100%{transform:scale(1.85) translateY(-6%)}}
#cy-cine .cy-cine-vig{position:absolute;inset:0;background:radial-gradient(120% 95% at 50% 45%,transparent 52%,rgba(0,0,0,.6))}
#cy-cine .cy-cine-bar{position:absolute;left:0;right:0;height:8%;background:#000;z-index:6}
#cy-cine .cy-cine-bar.t{top:0}#cy-cine .cy-cine-bar.b{bottom:0}
#cy-cine .cy-cine-rib{position:absolute;inset:0;width:100%;height:100%;z-index:4;opacity:0;transform-origin:34% 40%}
#cy-cine.play .cy-cine-rib{animation:cyCineRib 9s cubic-bezier(.5,0,.8,.4) both}
@keyframes cyCineRib{0%,52%{opacity:0;transform:scale(.15)}62%{opacity:.95;transform:scale(.7)}80%{opacity:1;transform:scale(1.6)}91%{opacity:0;transform:scale(3.6)}100%{opacity:0;transform:scale(3.6)}}
#cy-cine .cy-cine-flash{position:absolute;inset:0;background:#fff;opacity:0;z-index:5}
#cy-cine.play .cy-cine-flash{animation:cyCineFlash 9s linear both}
@keyframes cyCineFlash{0%,78%{opacity:0}81%{opacity:.85}90%{opacity:0}100%{opacity:0}}
#cy-cine .cy-cine-title{position:absolute;left:0;right:0;top:50%;z-index:7;text-align:center;color:#fff;font-family:CyBrand,'STXingkai','Xingkai SC','Kaiti SC',KaiTi,serif;font-size:clamp(40px,8vw,92px);letter-spacing:.3em;text-indent:.3em;text-shadow:0 4px 22px rgba(120,0,10,.85);opacity:0;transform:translateY(-50%) scale(.92)}
#cy-cine.play .cy-cine-title{animation:cyCineTitle 9s ease-out both}
@keyframes cyCineTitle{0%,66%{opacity:0;transform:translateY(-50%) scale(.92)}74%,86%{opacity:1;transform:translateY(-50%) scale(1)}92%,100%{opacity:0;transform:translateY(-50%) scale(1.08)}}
@media(max-width:720px){#cy-cine{top:68px;height:min(58vh,480px)}#cy-cine .cy-cine-img,#cy-cine .cy-cine-fg{object-position:24% 28%}}
@media(prefers-reduced-motion:reduce){#cy-cine{display:none!important}}
</style>
<div id="cy-cine" aria-hidden="true"><div class="cy-cine-view">
<img class="cy-cine-img" src="__ASSET__" alt="" decoding="async">
<img class="cy-cine-fg" src="__ASSET__" alt="" decoding="async">
<svg class="cy-cine-rib" viewBox="0 0 100 60" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg" focusable="false">
<g fill="none" stroke-linecap="round" stroke="#e11d2a">
<path d="M34 40C48 18 70 10 104 -4" stroke-width="2.4"/><path d="M34 40C52 30 78 22 106 22" stroke-width="2"/>
<path d="M34 40C50 44 76 50 106 62" stroke-width="2.6"/><path d="M34 40C30 46 14 54 -6 64" stroke-width="2.2"/>
<path d="M34 40C28 24 12 14 -6 8" stroke-width="2"/><path d="M34 40C44 52 52 64 56 70" stroke-width="2.4"/></g>
<g fill="none" stroke-linecap="round" stroke="#ff9a8a" stroke-opacity=".7">
<path d="M34 40C48 18 70 10 104 -4" stroke-width=".7"/><path d="M34 40C50 44 76 50 106 62" stroke-width=".8"/><path d="M34 40C30 46 14 54 -6 64" stroke-width=".7"/></g>
</svg>
<div class="cy-cine-vig"></div><div class="cy-cine-flash"></div>
<div class="cy-cine-title">长缨辅学</div>
</div><div class="cy-cine-bar t"></div><div class="cy-cine-bar b"></div></div>
<script id="changying_v1_cinematic_v1-script">
(function(){
 if(window.__cyCine)return;window.__cyCine=true;
 var el=document.getElementById('cy-cine');if(!el)return;
 if(window.matchMedia&&matchMedia('(prefers-reduced-motion:reduce)').matches)return;
 function play(){if(document.hidden)return;el.classList.remove('play');void el.offsetWidth;el.classList.add('play')}
 el.addEventListener('animationend',function(e){if(e.target===el)el.classList.remove('play')});
 var img=el.querySelector('img'),started=false;
 function go(){if(started)return;started=true;setTimeout(play,700);setInterval(play,30000)}
 if(img.complete&&img.naturalWidth)go();else img.addEventListener('load',go,{once:true});
})();
</script>
'''


def cinematic_snippet() -> str:
    return _SNIPPET.replace("__ASSET__", CINEMATIC_ASSET_PATH)


def patch_v1_cinematic(html: str) -> str:
    """Add the 30-second title sequence to a page that has the fixed ribbon header."""
    if V1_CINEMATIC_MARKER in html:
        return html
    snippet = cinematic_snippet() + f"\n<!-- {V1_CINEMATIC_MARKER} -->"
    return html.replace("</body>", snippet + "</body>", 1) if "</body>" in html else html + snippet


def install_v1_cinematic_routes(app: FastAPI) -> None:
    if getattr(app.state, "v1_cinematic_routes_installed", False):
        return
    router = APIRouter()

    @router.get(CINEMATIC_ASSET_PATH, include_in_schema=False)
    def cinematic_asset() -> Response:
        return Response(
            _ASSET_FILE.read_bytes(),
            media_type="image/webp",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    app.include_router(router)
    app.state.v1_cinematic_routes_installed = True


def install_v1_cinematic_patch() -> None:
    if getattr(v1_module, "_cinematic_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_cinematic(original())

    v1_module.v1_html = patched_v1_html
    v1_module._cinematic_patch_installed = True


__all__ = [
    "CINEMATIC_ASSET_PATH",
    "V1_CINEMATIC_MARKER",
    "cinematic_snippet",
    "install_v1_cinematic_patch",
    "install_v1_cinematic_routes",
    "patch_v1_cinematic",
]
