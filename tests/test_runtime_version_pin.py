from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_render_python_runtime_is_pinned_to_production_verified_version():
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.14.3"
    render = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "runtime: python" in render
    assert "buildCommand: pip install -r requirements.txt" in render
