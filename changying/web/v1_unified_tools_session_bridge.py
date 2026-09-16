"""Production hotfix for the V1 unified tool iframe.

The V1 shell and the Classic app deliberately reuse the same backend token, but
Classic decides whether to read auth state from localStorage or sessionStorage
using its older ``v717Remember`` flag and also expects a cached ``v717User``.
The first unified shell did not bridge that browser state, so the Classic frame
could load successfully while rendering an uninitialised/blank application
surface.  The embedded CSS also forced ``.shell`` visible even while Classic
still marked it ``.hidden``.

This patch keeps authentication semantics unchanged: it copies the already
validated V1 token/user into whichever browser storage Classic is already
configured to use, and only shows the Classic shell after Classic itself removes
``hidden``.
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
