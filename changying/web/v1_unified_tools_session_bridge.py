"""Session bridge for the V1 unified Classic tool surface.

The parent V1 page mirrors the already-validated session into Classic's existing
browser cache.  Classic itself now owns embedded-session startup from inside the
iframe; the parent only listens for readiness messages.  This avoids fragile
direct ``contentWindow`` calls on mobile Safari.
"""

from __future__ import annotations

from changying.web import v1_unified_tools

V1_UNIFIED_SESSION_BRIDGE_MARKER = "changying_v1_unified_session_bridge_v1"


def patch_unified_tool_session_bridge(html: str) -> str:
    if V1_UNIFIED_SESSION_BRIDGE_MARKER in html:
        return html

    html = html.replace(
        ".shell{display:block!important;min-height:100%!important}",
        ".shell:not(.hidden){display:block!important;min-height:100%!important}",
    )

    anchor = """  picker.onchange=()=>open(picker.value,false);\n  async function start(){\n    const t=token();\n"""
    replacement = """  picker.onchange=()=>open(picker.value,false);\n  function bridgeClassicSession(t,s){\n    if(!t||!s)return;\n    const legacyUser={\n      id:s.userID??s.id??null,\n      name:s.name||'',\n      role:s.role||'teacher',\n      grade:s.grade??null,\n      mustChangePassword:!!s.mustChangePassword,\n      subscription:s.subscription||null\n    };\n    const remember=localStorage.getItem('v717Remember')==='1';\n    const store=remember?localStorage:sessionStorage;\n    store.setItem('v717Token',t);\n    store.setItem('v717User',JSON.stringify(legacyUser));\n  }\n  async function start(){\n    const t=token();\n"""
    if anchor not in html:
        raise RuntimeError("V1 unified session bridge: start anchor not found")
    html = html.replace(anchor, replacement, 1)

    session_anchor = """if(r.ok){const s=await r.json();role=String(s.role||'teacher');identity.textContent="""
    session_replacement = """if(r.ok){const s=await r.json();bridgeClassicSession(t,s);role=String(s.role||'teacher');identity.textContent="""
    if session_anchor not in html:
        raise RuntimeError("V1 unified session bridge: session anchor not found")
    html = html.replace(session_anchor, session_replacement, 1)

    load_anchor = """  frame.addEventListener('load',()=>{\n    try{\n      const doc=frame.contentDocument;embeddedPolish(doc);\n      const continueBtn=doc?.getElementById('continueSessionBtn');\n      if(continueBtn&&!continueBtn.classList.contains('hidden')){continueBtn.click();setTimeout(()=>embeddedPolish(frame.contentDocument),250)}\n      setTimeout(()=>embeddedPolish(frame.contentDocument),700);\n    }catch{}\n    loading.classList.add('hidden');\n  });\n"""
    load_replacement = """  frame.addEventListener('load',()=>{\n    loading.classList.remove('hidden');\n    notice.classList.remove('show');\n    setTimeout(()=>loading.classList.add('hidden'),1800);\n  });\n  window.addEventListener('message',event=>{\n    if(event.origin!==location.origin||event.source!==frame.contentWindow)return;\n    const data=event.data||{};if(data.source!=='changying-classic')return;\n    loading.classList.add('hidden');\n    if(data.type==='ready'){notice.classList.remove('show');return}\n    notice.textContent=data.detail||'旧版功能暂未就绪，请返回后重试。';notice.classList.add('show');\n  });\n"""
    if load_anchor not in html:
        raise RuntimeError("V1 unified session bridge: iframe load anchor not found")
    html = html.replace(load_anchor, load_replacement, 1)

    return html.replace(
        "</body>",
        f"<!-- {V1_UNIFIED_SESSION_BRIDGE_MARKER} --></body>",
        1,
    )


def install_v1_unified_tool_session_bridge() -> None:
    if getattr(v1_unified_tools, "_session_bridge_installed", False):
        return
    v1_unified_tools._TOOL_HTML = patch_unified_tool_session_bridge(  # noqa: SLF001
        v1_unified_tools._TOOL_HTML  # noqa: SLF001
    )
    v1_unified_tools._session_bridge_installed = True


__all__ = [
    "V1_UNIFIED_SESSION_BRIDGE_MARKER",
    "install_v1_unified_tool_session_bridge",
    "patch_unified_tool_session_bridge",
]
