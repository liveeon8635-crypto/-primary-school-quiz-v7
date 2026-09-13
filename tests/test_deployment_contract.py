from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _string_assignment(source: str, name: str) -> str:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    value = ast.literal_eval(node.value)
                    assert isinstance(value, str)
                    return value
    raise AssertionError(f"missing string assignment: {name}")


def test_render_uses_permanent_entrypoint():
    render_yaml = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "startCommand: uvicorn app:app --host 0.0.0.0 --port $PORT" in render_yaml
    assert "healthCheckPath: /health" in render_yaml
    assert "uvicorn app_v" not in render_yaml


def test_app_py_stays_thin_and_version_agnostic():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert len(source.splitlines()) <= 12
    assert "from changying.production import app" in source
    assert "app_v" not in source


def test_production_module_and_asset_version_move_together():
    source = (ROOT / "changying" / "production.py").read_text(encoding="utf-8")
    production_module = _string_assignment(source, "PRODUCTION_MODULE")
    asset_version = _string_assignment(source, "ASSET_VERSION")

    assert production_module.startswith("app_v")
    assert asset_version == production_module.removeprefix("app_v")
    assert (ROOT / f"{production_module}.py").is_file()
