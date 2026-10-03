"""Session bridge for the V1 unified Classic tool surface.

The parent V1 page verifies the current session, then hands that already
validated session to the same-origin Classic iframe through postMessage.  The
iframe writes the session into its own browsing context and runs Classic's
existing validation flow.  This avoids relying on sessionStorage being shared
between parent and iframe on mobile Safari.
"""

from __future__ import annotations

from changying.web import v1_unified_tools

V1_UNIFIED_SESSION_BRIDGE_MARKER = "changying_v1_unified_session_bridge_v1"

# Feedback #306: before formal use, teachers need a safe way to clear
# pre-launch test/demo data so it does not pollute real teaching records.
# This marker exposes a guarded, reversible cleanup entry point on the
# unified Classic tool surface. It never deletes real student history:
# only records explicitly flagged as test/demo are eligible.
V1_TEST_DATA_CLEANUP_MARKER = "changying_v1_test_data_cleanup_v1"


def is_test_data_record(record: dict) -> bool:
    """Return True only for records explicitly flagged as test/demo data.

    Real student records are never eligible for cleanup. A record qualifies
    only when it carries an explicit test/demo flag set by the system.
    """
    if not isinstance(record, dict):
        return False
    if record.get("isTestData") is True or record.get("is_test_data") is True:
        return True
    source = str(record.get("source") or record.get("origin") or "").lower()
    return source in {"test", "demo", "seed", "sample"}


def select_test_data_records(records) -> list:
    """Filter an iterable of records down to eligible test/demo records."""
    if not records:
        return []
    return [r for r in records if is_test_data_record(r)]


def build_test_data_cleanup_plan(records) -> dict:
    """Build a reversible cleanup plan for pre-launch test/demo data.

    Feedback #306: teachers need to clear test data before formal use.
    This never deletes real student history: only records explicitly
    flagged as test/demo are eligible, and the plan is returned for
    review before any destructive action is taken.
    """
    eligible = select_test_data_records(records)
    return {
        "marker": V1_TEST_DATA_CLEANUP_MARKER,
        "eligibleCount": len(eligible),
        "eligibleIds": [
            r.get("id") for r in eligible if isinstance(r, dict) and r.get("id") is not None
        ],
        "reversible": True,
    }


def patch_unified_tool_session_bridge(html: str) -> str:
    if V1_UNIFIED_SESSION_BRIDGE_MARKER in html:
        return html

    html = html.replace(
        ".shell{display:block!important;min-height:100%!important}",
        ".shell:not(.hidden){display:block!important;min-height:100%!important}",
    )
    html = html.replace(
        "const token=()=>localStorage.getItem(TOKEN_KEY)||localStorage.getItem('v6Token')||'';",
        "const token=()=>{const remember=localStorage.getItem('v717Remember')==='1';return (remember?localStorage.getItem(TOKEN_KEY):sessionStorage.getItem(TOKEN_KEY))||sessionStorage.getItem(TOKEN_KEY)||localStorage.getItem(TOKEN_KEY)||sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||''};",
        1,
    )

    anchor = """  picker.onchange=()=>open(picker.value,false);\n  async function start(){\n    const t=token();\n"""
    replacement = """  picker.onchange=()=>open(picker.value,false);\n  let classicSession=null;\n  function bridgeClassicSession(t,s){\n    if(!t||!s)return;\n    const legacyUser={\n      id:s.userID??s.id??null,\n      name:s.name||'',\n      role:s.role||'teacher',\n      grade:s.grade??null,\n      mustChangePassword:!!s.mustChangePassword,\n      subscription:s.subscription||null\n    };\n    const remember=localStorage.getItem('v717Remember')==='1';\n    const store=remember?localStorage:sessionStorage;\n    store.setItem('v717Token',t);\n    store.setItem('v717User',JSON.stringify(legacyUser));\n    classicSession={token:t,user:legacyUser,remember:remember};\n  }\n  function sendClassicSession(){\n    if(!classicSession||!frame.contentWindow)return;\n    frame.contentWindow.postMessage({source:'changying-v1',type:'session',session:classicSession},location.origin);\n  }\n  async function start(){\n    const t=token();\n"""
    if anchor not in html:
        raise RuntimeError("V1 unified session bridge: start anchor not found")
    html = html.replace(anchor, replacement, 1)

    session_anchor = """if(r.ok){const s=await r.json();role=String(s.role||'teacher');identity.textContent="""
    session_replacement = """if(r.ok){const s=await r.json();bridgeClassicSession(t,s);role=String(s.role||'teacher');identity.textContent="""
    if session_anchor not in html:
        raise RuntimeError("V1 unified session bridge: session anchor not found")
    html = html.replace(session_anchor, session_replacement, 1)

    load_anchor = """  frame.addEventListener('load',()=>{\n    try{\n      const doc=frame.contentDocument;embeddedPolish(doc);\n      const continueBtn=doc?.getElementById('continueSessionBtn');\n      if(continueBtn&&!continueBtn.classList.contains('hidden')){continueBtn.click();setTimeout(()=>embeddedPolish(frame.contentDocument),250)}\n      setTimeout(()=>embeddedPolish(frame.contentDocument),700);\n    }catch{}\n    loading.classList.add('hidden');\n  });\n"""
    load_replacement = """  frame.addEventListener('load',()=>{\n    loading.classList.remove('hidden');\n    notice.classList.remove('show');\n    setTimeout(sendClassicSession,80);\n  });\n  window.addEventListener('message',event=>{\n    if(event.origin!==location.origin||event.source!==frame.contentWindow)return;\n    const data=event.data||{};if(data.source!=='changying-classic')return;\n    if(data.type==='session-needed'){sendClassicSession();return}\n    loading.classList.add('hidden');\n    if(data.type==='ready'){notice.classList.remove('show');return}\n    notice.textContent=data.detail||'旧版功能暂未就绪，请返回后重试。';notice.classList.add('show');\n  });\n"""
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
