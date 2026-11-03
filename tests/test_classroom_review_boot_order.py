"""课堂复盘页的启动顺序：调用必须在定义之后。

页面脚本里 ``renderReview`` 是 ``const`` 定义（不提升），一旦在定义前调用就是 ReferenceError，
整页打不开。这条是静态顺序检查——能挡住这次的错，但不等于真的执行了 JS。
"""
from __future__ import annotations

from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "changying" / "web" / "v1_classroom_review.py"


def _text() -> str:
    return PAGE.read_text(encoding="utf-8")


def test_render_review_is_defined_before_it_is_called():
    text = _text()
    assert text.index("const renderReview=") < text.index("await pickTarget();"), (
        "renderReview 在定义前被调用，页面会 ReferenceError"
    )


def test_bootstrap_runs_after_every_const_definition():
    text = _text()
    called = text.index("await pickTarget();")
    for name in ("const load=", "const renderReview=", "const draftEditor="):
        assert text.index(name) < called, f"{name} 必须在启动调用之前定义"


def test_empty_state_returns_before_loading():
    text = _text()
    empty = text.index("if(!assignments.length){")
    call = text.index("await pickTarget();")
    assert empty < call
    # 空列表分支里必须有 return，否则还会去 load(0)
    assert "return" in text[empty:call]
