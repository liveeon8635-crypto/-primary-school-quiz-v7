"""Temporary CI-only Safari12 asset exporter; removed before merge.
Rebuild uses pinned Babel in isolated SQLite without production credentials.
"""
import json
import os
import subprocess
from pathlib import Path


def test_export_safari12_21_22_manifest():
    from changying.compat_tools.build_safari12 import collect
    from changying.web.safari12 import ASSETS
    modules="/tmp/cy-21-22-babel"
    subprocess.run(
        ["npm","install","--prefix",modules,"--no-audit","--no-fund","--silent",
         "@babel/core@7.28.5","@babel/preset-env@7.28.5","acorn@8.15.0"],
        check=True,capture_output=True,text=True,timeout=150
    )
    os.environ["DATABASE_URL"]="sqlite:////tmp/cy-21-22-safari.sqlite3"
    old=json.loads((ASSETS/"manifest.json").read_text())
    scripts,routes=collect()
    compiler=Path(__file__).parents[1]/"changying"/"compat_tools"/"compile_safari12.cjs"
    subprocess.run(
        ["node",str(compiler),modules+"/node_modules"],
        input=json.dumps({"scripts":scripts,"routes":routes}),
        check=True,capture_output=True,text=True,timeout=90
    )
    new=json.loads((ASSETS/"manifest.json").read_text())
    changed=set(old["scripts"])^set(new["scripts"])
    data={
        "manifest":new,
        "newAssets":{
            key:(ASSETS/(key+".js.gz.b64")).read_text()
            for key in changed if key in new["scripts"] and not new["scripts"][key]["unchanged"]
        },
        "newKeys":sorted(set(new["scripts"])-set(old["scripts"])),
        "oldKeys":sorted(set(old["scripts"])-set(new["scripts"]))
    }
    raw=json.dumps(data,ensure_ascii=True,separators=(",",":"))
    chunks=[raw[i:i+3500] for i in range(0,len(raw),3500)]
    raise AssertionError("GENERATED_SAFARI_ASSETS_START\n"
       +"\n".join("SAFARI_CHUNK_%03d=%s"%(i,chunk) for i,chunk in enumerate(chunks))
       +"\nGENERATED_SAFARI_ASSETS_END")
