"""Session bridge for the V1 unified Classic tool surface.

V1 and Classic reuse the same backend token.  The bridge mirrors the already
validated V1 session into the legacy browser cache, preserves Classic's hidden
state, and actively starts Classic's own saved-session validation after the
same-origin iframe loads.  This is important on mobile Safari: Classic starts
with its network hint false, so merely clicking its "continue session" button
returns before making a request and leaves the embedded surface blank.
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
    load_replacement = """  frame.addEventListener('load',()=>{\n    try{\n      const doc=frame.contentDocument,win=frame.contentWindow;embeddedPolish(doc);\n      if(win&&typeof win.markNetwork==='function')win.markNetwork(true);\n      if(win&&typeof win.validateSavedSession==='function'){\n        Promise.resolve(win.validateSavedSession()).then(ok=>{\n          if(!ok){notice.textContent='旧版功能登录状态尚未就绪，请返回后重试。';notice.classList.add('show')}\n          setTimeout(()=>embeddedPolish(frame.contentDocument),80);\n        }).catch(()=>{notice.textContent='旧版功能加载失败，请返回后重试。';notice.classList.add('show')});\n      }else{\n        const continueBtn=doc?.getElementById('continueSessionBtn');\n        if(continueBtn&&!continueBtn.classList.contains('hidden'))continueBtn.click();\n      }\n      setTimeout(()=>embeddedPolish(frame.contentDocument),700);\n    }catch{notice.textContent='旧版功能加载失败，请返回后重试。';notice.classList.add('show')}\n    loading.classList.add('hidden');\n  });\n"""
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
