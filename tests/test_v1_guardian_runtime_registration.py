from pathlib import Path

from changying.web.v1 import v1_html
from changying.web.v1_guardian_visibility import (
    V1_GUARDIAN_VISIBILITY_MARKER,
    patch_v1_guardian_visibility,
)


def test_legacy_runtime_registers_guardian_visibility_after_student_detail_patch():
    source = Path("changying/compat/legacy.py").read_text(encoding="utf-8")

    assert "from changying.web.v1_guardian_visibility import install_v1_guardian_visibility_patch" in source
    student_detail = source.index("    install_v1_student_detail_visibility_patch()")
    guardian = source.index("    install_v1_guardian_visibility_patch()")
    routes = source.index("    install_v1_routes(implementation.app)")
    assert student_detail < guardian < routes


def test_registered_guardian_patch_remains_read_only_and_student_scoped():
    html = patch_v1_guardian_visibility(v1_html())
    marker = f'<script id="{V1_GUARDIAN_VISIBILITY_MARKER}-script">'
    start = html.index(marker)
    fragment = html[start : html.index("</script>", start)]

    assert "location.pathname!='/v1/student'" in fragment
    assert "growth-profile" in fragment
    assert "method:'POST'" not in fragment
    assert "method:'PUT'" not in fragment
    assert "method:'PATCH'" not in fragment
    assert "method:'DELETE'" not in fragment
