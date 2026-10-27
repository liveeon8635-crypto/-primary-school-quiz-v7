from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from changying.services import grid_figures as gf
from changying.services import tiling_figures as tl
from changying.services import visual_questions as vq

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tiling_figure_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def shape_key(pts):
    mx, my = min(p[0] for p in pts), min(p[1] for p in pts)
    return frozenset((x - mx, y - my) for x, y in pts)


def test_the_patterns_are_what_they_claim():
    for name, pattern in tl.TILES.items():
        assert tl.coverage(tl.lay(pattern, (-1, 0)))[1:] == (0, 0), name           # no gap, no overlap
    for bad in (tl.OCTAGON, tl.ONE_WAY, tl._spread(tl.TILES["六边形"])):
        _, gaps, over = tl.coverage(tl.lay(bad, (0, 0)))
        assert gaps > 0 and over == 0


@pytest.mark.parametrize("level", ["basic", "medium", "hard"])
def test_which_picture_is_a_tiling(level):
    qs = tl.generate("T-1", level, 6, 7)
    assert len(qs) == 6
    for q in qs:
        fig = q["figure"]
        assert gf.sanitize(fig) == fig and len(fig["panels"]) == 4
        tiled = [tl.coverage(p["shapes"])[1:] == (0, 0) for p in fig["panels"]]
        assert all(tl.coverage(p["shapes"])[2] == 0 for p in fig["panels"])          # nothing overlaps anywhere
        want = not q["text"].startswith("下面哪幅图不是")
        assert [i for i, t in enumerate(tiled) if t == want] == [q["correct_index"]], q["text"]


@pytest.mark.parametrize("level", ["basic", "medium", "hard"])
def test_only_one_piece_fills_the_gap(level):
    qs = tl.generate("T-2", level, 6, 9)
    assert len(qs) == 6
    for q in qs:
        fig = q["figure"]
        assert gf.sanitize(fig) == fig
        _, gaps, over = tl.coverage(fig["shapes"])
        assert gaps > 0 and over == 0
        pieces = [p["shapes"][0]["points"] for p in fig["panels"]]
        assert len({shape_key(p) for p in pieces}) == 4
        # Where the gap is: the paper points no tile covers.
        holes = [((i + 0.13) / 4, (j + 0.21) / 4) for i in range(tl.W * 4) for j in range(tl.H * 4)
                 if not any(tl._inside((i + 0.13) / 4, (j + 0.21) / 4, s["points"]) for s in fig["shapes"])]
        gx, gy = int(min(x for x, _ in holes)), int(min(y for _, y in holes))
        fits = []
        for i, piece in enumerate(pieces):
            # Put the piece's corner box at the gap's: it must close the gap with no overlap.
            moved = gf.translate(piece, gx - min(p[0] for p in piece), gy - min(p[1] for p in piece))
            if tl.coverage(fig["shapes"] + [{"points": moved, "tone": "a", "label": ""}])[1:] == (0, 0):
                fits.append(i)
        assert fits == [q["correct_index"]]


def test_dispatcher_serves_the_tiling_points():
    assert "密铺" in vq.NODE_LABELS["T-1"] and "密铺" in vq.NODE_LABELS["T-2"]
    assert vq.generate("T-2", "medium", 1, 2)[0]["figure"]["type"] == "gridshape"


FLOW = r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    d = client.post("/teacher/knowledge-maps", headers=th, json={"template": "rj2026-g5-math-up"}).json()
    mid, rev = d["id"], d["revision"]
    base = f"/teacher/knowledge-maps/{mid}/nodes"
    saved = {}
    for key in ("T-1", "T-2"):
        got = client.post(base + f"/{key}/visual", headers=th, json={"level": "medium", "count": 2}).json()
        r = client.post(base + f"/{key}/visual/save", headers=th, json={"level": "medium", "revision": rev, "questions": got["items"]})
        assert r.status_code == 200, r.text
        rev = r.json()["revision"]
        saved.update(zip(r.json()["saved"], got["items"]))
    with legacy.SessionLocal() as db:
        rows = {q.id: q for q in db.scalars(select(legacy.Question).where(legacy.Question.id.in_(list(saved))))}
    assert len(rows) == 4
    for qid, q in saved.items():
        assert json.loads(rows[qid].figure_json) == q["figure"]          # every tile survives saving
        assert rows[qid].unit == "有趣的密铺" and rows[qid].correct_index == q["correct_index"]
print("OK")
'''


def test_teacher_saves_tiling_questions(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + FLOW, {"KNOWLEDGE_MAP": "1"})
