import re
import subprocess
from pathlib import Path

from changying.web.v1 import v1_html
from changying.web.v2_learning_evidence_recording_view import (
    V2_EVIDENCE_RECORDER_MARKER,
    patch_v2_learning_evidence_recorder,
)


def test_recorder_shows_append_only_event_history():
    html = patch_v2_learning_evidence_recorder(v1_html())
    assert "/learning-evidence/events" in html
    assert "查看完整记录历史" in html
    assert "撤回事件" in html
    assert "当前有效" in html
    assert "已撤回" in html
    assert "历史只用于追溯记录与撤回" in html
    assert "已撤回记录不会重新参与当前学习证据状态" in html


def test_history_ui_adds_no_new_write_method():
    html = patch_v2_learning_evidence_recorder(v1_html())
    marker = f'<script id="{V2_EVIDENCE_RECORDER_MARKER}-script">'
    fragment = html[html.index(marker):html.index("</script>", html.index(marker))]
    assert "/learning-evidence/events" in fragment
    assert "method:'DELETE'" not in fragment
    assert "method:'PUT'" not in fragment
    assert "method:'PATCH'" not in fragment


def test_final_recorder_script_is_valid_javascript():
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


def test_backend_still_never_physically_deletes_evidence_events():
    source = (
        Path(__file__).resolve().parents[1]
        / "changying"
        / "web"
        / "v2_learning_evidence_recording.py"
    ).read_text(encoding="utf-8")
    assert "db.delete(" not in source
    assert "includesRetracted" in source
    assert '"effectiveStatus"] = "retracted"' in source
