import re
import subprocess
from pathlib import Path

from changying.web.v1 import v1_html
from changying.web.v2_learning_evidence_recording_view import (
    V2_EVIDENCE_RECORDER_MARKER,
    patch_v2_learning_evidence_recorder,
)


def test_v2_recorder_exposes_only_manual_evidence_dimensions():
    html = patch_v2_learning_evidence_recorder(v1_html())

    assert V2_EVIDENCE_RECORDER_MARKER in html
    assert "教师学习证据记录" in html
    assert 'value="independent"' in html
    assert 'value="retention"' in html
    assert 'value="transfer"' in html
    assert 'value="performance"' not in html
    assert "学习表现继续由作业/测验自动形成" in html
    assert "追加式记录" in html


def test_v2_recorder_uses_shared_auth_and_append_only_actions():
    html = patch_v2_learning_evidence_recorder(v1_html())
    marker = f'<script id="{V2_EVIDENCE_RECORDER_MARKER}-script">'
    fragment = html[html.index(marker):html.index("</script>", html.index(marker))]

    assert "v717Remember" in fragment
    assert "sessionStorage.getItem('v717Token')" in fragment
    assert "localStorage.getItem('v717Token')" in fragment
    assert "/v2/students/" in fragment
    assert "/learning-evidence/manual" in fragment
    assert "/retract" in fragment
    assert "原记录不会删除" in fragment
    assert "method:'POST'" in fragment
    for forbidden in ("method:'DELETE'", "method:'PUT'", "method:'PATCH'"):
        assert forbidden not in fragment


def test_v2_recorder_script_is_valid_javascript():
    html = patch_v2_learning_evidence_recorder(v1_html())
    match = re.search(
        rf'<script id="{V2_EVIDENCE_RECORDER_MARKER}-script">(?P<script>.*?)</script>',
        html,
        re.S,
    )
    assert match
    result = subprocess.run(
        ["node", "--check", "-"],
        input=match.group("script"),
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_v2_recorder_patch_is_idempotent():
    once = patch_v2_learning_evidence_recorder(v1_html())
    twice = patch_v2_learning_evidence_recorder(once)
    assert once == twice


def test_v2_backend_source_never_physically_deletes_evidence_events():
    source = (
        Path(__file__).resolve().parents[1]
        / "changying"
        / "web"
        / "v2_learning_evidence_recording.py"
    ).read_text(encoding="utf-8")

    assert "db.delete(" not in source
    assert 'event_kind="retract"' in source
    assert "target_event_id=int(record.id)" in source


def test_production_v1_contains_v2_teacher_recorder():
    from app import app  # noqa: F401
    from changying.web import v1 as v1_module

    html = v1_module.v1_html()
    assert V2_EVIDENCE_RECORDER_MARKER in html
    assert "教师学习证据记录" in html
    assert "/v2/students/" in html
