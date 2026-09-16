"""Clarify V1 identity UX when a real account has only one usable identity.

V1 currently maps each real account to one authorized identity. Demo accounts may
show multiple modes, but real accounts should not be forced through a redundant
identity picker or see a misleading "switch identity" button when there is
nothing to switch to.
"""

from __future__ import annotations

from changying.web import v1 as v1_module


V1_IDENTITY_CLARITY_MARKER = "changying_v1_identity_clarity_v1"


def patch_v1_identity_clarity(html: str) -> str:
    if V1_IDENTITY_CLARITY_MARKER in html:
        return html

    choose_marker = "function chooseIdentity(){const choices=identitiesFor(session);identity=null;"
    choose_replacement = (
        "function chooseIdentity(){const choices=identitiesFor(session);"
        "if(choices.length===1){identity=choices[0];localStorage.setItem(IDENTITY_KEY,identity.key);"
        "chip.textContent=identity.label+' · '+(session.name||'');identityButton.hidden=true;"
        "navigate(identity.mode==='family'||identity.mode==='student'?'/v1/student':'/v1/workspace?mode='+identity.mode);return}"
        "identity=null;"
    )
    if choose_marker not in html:
        raise RuntimeError("V1 identity clarity: chooseIdentity marker not found")
    html = html.replace(choose_marker, choose_replacement, 1)

    button_marker = "identityButton.hidden=false;const path=location.pathname;"
    button_replacement = "identityButton.hidden=choices.length<=1;const path=location.pathname;"
    if button_marker not in html:
        raise RuntimeError("V1 identity clarity: identity button marker not found")
    html = html.replace(button_marker, button_replacement, 1)

    return html.replace(
        "</body>", f"<!-- {V1_IDENTITY_CLARITY_MARKER} --></body>", 1
    )


def install_v1_identity_clarity_patch() -> None:
    if getattr(v1_module, "_identity_clarity_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_identity_clarity(original())

    v1_module.v1_html = patched_v1_html
    v1_module._identity_clarity_patch_installed = True


__all__ = [
    "V1_IDENTITY_CLARITY_MARKER",
    "install_v1_identity_clarity_patch",
    "patch_v1_identity_clarity",
]
