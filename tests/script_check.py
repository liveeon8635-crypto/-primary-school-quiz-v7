"""Parse-check inline page scripts with Node when it is available.

The signup page once shipped a script that was syntactically broken by
unescaped quotes, so the whole page stayed on "加载中…". A regex assertion
cannot catch that class of bug; a real parser can.

Node is only used when present (CI installs it for workbench tests). Without
Node the caller's structural assertions still apply.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def node_path() -> str | None:
    return shutil.which("node")


def assert_parses(source: str) -> None:
    """Raise AssertionError if Node says the snippet is not valid JavaScript."""
    node = node_path()
    if not node:
        return
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "inline.js"
        target.write_text(source, encoding="utf-8")
        result = subprocess.run(
            [node, "--check", str(target)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    if result.returncode != 0:
        raise AssertionError(
            "inline script is not valid JavaScript:\n"
            + (result.stderr or result.stdout)[:1500]
        )


def _selftest() -> None:
    assert_parses("var a=1;")
    try:
        assert_parses('var a="x""y";')
    except AssertionError:
        print(json.dumps({"selftest": "ok"}))
        return
    raise SystemExit("broken script was not detected")


if __name__ == "__main__":
    _selftest()
