from pathlib import Path


def test_audit_localization_is_registered_after_unified_session_bridge():
    source = Path("changying/compat/legacy.py").read_text(encoding="utf-8")

    assert "from changying.web.v1_audit_localization import install_v1_audit_localization" in source
    session_bridge = source.index("    install_v1_unified_tool_session_bridge()")
    audit_localization = source.index("    install_v1_audit_localization()")
    route_registration = source.index("    install_v1_unified_tool_route(implementation.app)")

    assert session_bridge < audit_localization < route_registration
