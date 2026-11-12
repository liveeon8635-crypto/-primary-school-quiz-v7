"""Temporary diagnostics for re-generating Safari 12 assets from pinned compiler.
This file is removed after the generated assets have been imported.
"""
import base64, gzip, json, os, subprocess
from pathlib import Path
import pytest


def test_safari12_asset_regeneration_diagnostic():
    from changying.compat_tools.build_safari12 import collect
    from changying.web.safari12 import ASSETS
    modules="/tmp/changying-safari12-babel"
    subprocess.run([
        "npm","install","--prefix",modules,"--no-audit","--no-fund","--silent",
        "@babel/core@7.28.5","@babel/preset-env@7.28.5","acorn@8.15.0"
    ],check=True,timeout=150,capture_output=True,text=True)
    old=json.loads((ASSETS/"manifest.json").read_text())
    os.environ["DATABASE_URL"]="sqlite:////tmp/changying-safari12-asset-build.sqlite3"
    sources,routes=collect()
    raw=json.dumps({"scripts":sources,"routes":routes})
    compiler=Path(__file__).parents[1]/"changying"/"compat_tools"/"compile_safari12.cjs"
    subprocess.run(["node",str(compiler),modules+"/node_modules"],
                   input=raw,text=True,check=True,timeout=90,capture_output=True)
    new=json.loads((ASSETS/"manifest.json").read_text())
    changed=set(old["scripts"])^set(new["scripts"])
    data={"manifest":new,
          "newAssets":{k:(ASSETS/(k+".js.gz.b64")).read_text()
             for k in changed if k in new["scripts"] and not new["scripts"][k]["unchanged"]},
          "oldKeys":sorted(set(old["scripts"])-set(new["scripts"])),
          "newKeys":sorted(set(new["scripts"])-set(old["scripts"]))}
    payload=base64.b64encode(gzip.compress(json.dumps(data,separators=(",",":")).encode(),compresslevel=9)).decode()
    chunks=[payload[i:i+3500] for i in range(0,len(payload),3500)]
    raise AssertionError("GENERATED_SAFARI_ASSETS_START\n"+
        "\n".join("SAFARI_CHUNK_%03d=%s"%(i,c) for i,c in enumerate(chunks))+
        "\nGENERATED_SAFARI_ASSETS_END")
