"""Temporary, isolated CI-only exporter for regenerated Safari 12 script assets.
Removed before merge. Never uses production DB.
"""
import json
import os
import subprocess
from pathlib import Path


def test_export_safari12_assets_after_example15_change():
    from changying.compat_tools.build_safari12 import collect
    from changying.web.safari12 import ASSETS

    modules="/tmp/cy-example15-babel"
    subprocess.run([
        "npm", "install", "--prefix", modules, "--no-audit", "--no-fund", "--silent",
        "@babel/core@7.28.5", "@babel/preset-env@7.28.5", "acorn@8.15.0",
    ], check=True, capture_output=True, text=True, timeout=150)
    os.environ["DATABASE_URL"] = "sqlite:////tmp/cy-example15-safari12-build.sqlite3"
    before = json.loads((ASSETS / "manifest.json").read_text())
    scripts, routes = collect()
    subprocess.run(
        ["node", str(Path(__file__).parents[1] / "changying" / "compat_tools" / "compile_safari12.cjs"), modules + "/node_modules"],
        input=json.dumps({"scripts": scripts, "routes": routes}),
        capture_output=True, text=True, timeout=90, check=True,
    )
    after = json.loads((ASSETS / "manifest.json").read_text())
    changed = set(before["scripts"]) ^ set(after["scripts"])
    data = {
        "manifest": after,
        "newAssets": {
            key: (ASSETS / (key + ".js.gz.b64")).read_text()
            for key in changed if key in after["scripts"] and not after["scripts"][key]["unchanged"]
        },
        "newKeys": sorted(set(after["scripts"]) - set(before["scripts"])),
        "oldKeys": sorted(set(before["scripts"]) - set(after["scripts"])),
    }
    raw = json.dumps(data, ensure_ascii=True, separators=(",", ":"))
    chunks = [raw[i:i+3500] for i in range(0, len(raw), 3500)]
    raise AssertionError(
        "GENERATED_SAFARI_ASSETS_START\n"
        + "\n".join("SAFARI_CHUNK_%03d=%s" % (i, chunk) for i, chunk in enumerate(chunks))
        + "\nGENERATED_SAFARI_ASSETS_END"
    )
