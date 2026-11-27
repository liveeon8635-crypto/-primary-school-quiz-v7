"""离线批量生成语文知识地图与应试专项的静态普通话 MP3 音频资产（基于 edge-tts）.

用法：
    python scripts/build_chinese_arena_audio.py
    python scripts/build_chinese_arena_audio.py --force
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import edge_tts  # noqa: E402

from changying.services import chinese_builtin_map as cbm  # noqa: E402

OUT_DIR = ROOT / "changying" / "web" / "chinese_audio"
MANIFEST_PATH = OUT_DIR / "manifest.json"


async def _gen_one(spec: dict[str, str], sem: asyncio.Semaphore, force: bool) -> dict[str, object]:
    aid = spec["audioId"]
    text = spec["text"]
    voice = spec.get("voice", "zh-CN-XiaoxiaoNeural")
    rate = "-12%" if "Yunxi" in voice else "-6%"
    target = OUT_DIR / f"{aid}.mp3"
    if target.exists() and target.stat().st_size > 256 and not force:
        return {"audioId": aid, "file": target.name, "text": text, "voice": voice, "size": target.stat().st_size, "skipped": True}
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None
    async with sem:
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                comm = edge_tts.Communicate(text=text, voice=voice, rate=rate, proxy=proxy)
                await comm.save(str(target))
                last_err = None
                break
            except Exception as exc:
                last_err = exc
                await asyncio.sleep(0.8 * (attempt + 1))
        if last_err is not None:
            raise last_err
    return {"audioId": aid, "file": target.name, "text": text, "voice": voice, "size": target.stat().st_size, "skipped": False}


async def main(force: bool = False) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    specs = cbm.collect_audio_specs()
    sem = asyncio.Semaphore(4)
    results = await asyncio.gather(*[_gen_one(s, sem, force) for s in specs])
    manifest = {
        r["audioId"]: {
            "file": r["file"],
            "text": r["text"],
            "voice": r["voice"],
            "size": r["size"],
        }
        for r in results
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    created = sum(1 for r in results if not r["skipped"])
    skipped = sum(1 for r in results if r["skipped"])
    print(f"Chinese audio ready: total={len(results)}, generated={created}, skipped={skipped}, dir={OUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build static MP3 assets for Chinese Star Map & Sprints")
    parser.add_argument("--force", action="store_true", help="Regenerate existing MP3 files")
    args = parser.parse_args()
    asyncio.run(main(force=args.force))
