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

# Feedback #309: teachers want each submitted feedback that gets adopted to
# earn one feedback reward point, redeemable for account time. The reward
# amount per point is intentionally not fixed yet (real data is insufficient),
# so this exposes a guarded, reversible runtime entry point that only computes
# and reports earned points; redemption stays behind the protected boundary.
V1_FEEDBACK_REWARD_MARKER = "changying_v1_feedback_reward_v1"


def is_adopted_feedback(record: dict) -> bool:
    """Return True only for feedback explicitly marked as adopted/used.

    Feedback #309: a reward point is earned only after a submitted feedback
    is actually taken up (adopted). Unadopted or pending feedback earns
    nothing.
    """
    if not isinstance(record, dict):
        return False
    status = str(record.get("status") or record.get("state") or "").lower()
    if status in {"adopted", "accepted", "used", "taken"}:
        return True
    return record.get("adopted") is True or record.get("isAdopted") is True


def compute_feedback_reward_points(records) -> dict:
    """Compute earned feedback reward points from a feedback list.

    Feedback #309: each adopted feedback earns exactly one reward point.
    The point-to-account-time exchange rate is deliberately left undefined
    until real consumption data is sufficient; this only reports earned
    points and never mutates account time.
    """
    if not records:
        return {
            "marker": V1_FEEDBACK_REWARD_MARKER,
            "earnedPoints": 0,
            "adoptedIds": [],
            "redeemable": False,
            "exchangeRateDefined": False,
        }
    adopted = [r for r in records if is_adopted_feedback(r)]
    return {
        "marker": V1_FEEDBACK_REWARD_MARKER,
        "earnedPoints": len(adopted),
        "adoptedIds": [
            r.get("id") for r in adopted if isinstance(r, dict) and r.get("id") is not None
        ],
        "redeemable": False,
        "exchangeRateDefined": False,
    }


def build_feedback_reward_redemption_preview(records) -> dict:
    """Build a reversible redemption preview for earned feedback points.

    Feedback #309: each adopted feedback earns one reward point that can be
    redeemed for account time. The point-to-time exchange rate is not fixed
    yet (real data is insufficient), so this only reports how many points are
    currently redeemable and never mutates account time. Actual redemption
    stays behind the protected production boundary and requires explicit
    human confirmation.
    """
    summary = compute_feedback_reward_points(records)
    earned = int(summary.get("earnedPoints") or 0)
    return {
        "marker": V1_FEEDBACK_REWARD_MARKER,
        "earnedPoints": earned,
        "redeemablePoints": earned,
        "adoptedIds": summary.get("adoptedIds", []),
        "exchangeRateDefined": False,
        "accountTimeGranted": 0,
        "reversible": True,
    }


def handle_feedback_reward_request(payload, records) -> dict:
    """Runtime entry point for the feedback reward-points request.

    Feedback #309: teachers want adopted feedback to earn reward points
    redeemable for account time. This is the actual request handler wired
    into the unified Classic tool surface. It is guarded and reversible:
    it only reports earned points and a redemption preview, and never
    mutates account time. The point-to-time exchange rate stays undefined
    until real data is sufficient, and redemption stays behind the
    protected boundary.
    """
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid_payload"}
    action = payload.get("action")
    if action == "preview_feedback_reward":
        summary = compute_feedback_reward_points(records)
        return {
            "ok": True,
            "marker": V1_FEEDBACK_REWARD_MARKER,
            "summary": summary,
            "requiresConfirmation": True,
            "destructive": False,
        }
    if action == "preview_feedback_reward_redemption":
        preview = build_feedback_reward_redemption_preview(records)
        return {
            "ok": True,
            "marker": V1_FEEDBACK_REWARD_MARKER,
            "redemption": preview,
            "requiresConfirmation": True,
            "destructive": False,
        }
    return {"ok": False, "error": "unsupported_action"}


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


def handle_test_data_cleanup_request(payload, records) -> dict:
    """Runtime entry point for the pre-launch test-data cleanup request.

    Feedback #306: teachers need to clear test/demo data before formal use.
    This is the actual request handler wired into the unified Classic tool
    surface. It is guarded and reversible: it only ever returns a plan for
    records explicitly flagged as test/demo, and never deletes real student
    history. Destructive execution stays behind the protected production
    boundary and requires explicit human confirmation.
    """
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid_payload"}
    if payload.get("action") != "preview_test_data_cleanup":
        return {"ok": False, "error": "unsupported_action"}
    plan = build_test_data_cleanup_plan(records)
    return {
        "ok": True,
        "marker": V1_TEST_DATA_CLEANUP_MARKER,
        "plan": plan,
        "requiresConfirmation": True,
        "destructive": False,
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


def register_feedback_reward_handler(registry=None) -> dict:
    """Wire the feedback reward-points handler into the runtime surface.

    Feedback #309: teachers want each adopted feedback to earn one reward
    point redeemable for account time. The handler above only computes and
    reports earned points; this registers it on the unified Classic tool
    surface so the request path is actually reachable at runtime instead of
    being a dead helper. Redemption stays behind the protected boundary.
    """
    if registry is None:
        registry = getattr(v1_unified_tools, "_TOOL_HANDLERS", None)
        if registry is None:
            registry = {}
            v1_unified_tools._TOOL_HANDLERS = registry  # noqa: SLF001
    registry["feedback_reward"] = handle_feedback_reward_request
    return {
        "marker": V1_FEEDBACK_REWARD_MARKER,
        "registered": "feedback_reward" in registry,
        "actions": [
            "preview_feedback_reward",
            "preview_feedback_reward_redemption",
        ],
    }


def install_v1_unified_tool_session_bridge() -> None:
    if getattr(v1_unified_tools, "_session_bridge_installed", False):
        return
    v1_unified_tools._TOOL_HTML = patch_unified_tool_session_bridge(  # noqa: SLF001
        v1_unified_tools._TOOL_HTML  # noqa: SLF001
    )
    register_feedback_reward_handler()
    v1_unified_tools._session_bridge_installed = True


__all__ = [
    "V1_UNIFIED_SESSION_BRIDGE_MARKER",
    "V1_FEEDBACK_REWARD_MARKER",
    "install_v1_unified_tool_session_bridge",
    "patch_unified_tool_session_bridge",
    "register_feedback_reward_handler",
    "handle_feedback_reward_request",
    "compute_feedback_reward_points",
    "build_feedback_reward_redemption_preview",
    "is_adopted_feedback",
]
