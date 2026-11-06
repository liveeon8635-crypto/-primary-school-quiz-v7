"""Run a JavaScript snippet with Node from a temp file.

Passing the script through ``node -e`` breaks on Windows once the source grows past the
32k command-line limit (WinError 206), which the weekend page scripts easily exceed.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def run_node(script: str, *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="dsh-node-") as tmp:
        path = Path(tmp) / "script.js"
        path.write_text(script, encoding="utf-8")
        return subprocess.run(
            ["node", str(path)], text=True, capture_output=True, timeout=timeout, encoding="utf-8"
        )


def test_run_node_executes_a_script_file():
    result = run_node("console.log(JSON.stringify({ok:true}))")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '{"ok":true}'
