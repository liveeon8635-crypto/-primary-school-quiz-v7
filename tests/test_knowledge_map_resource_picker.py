from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("km_resource_picker_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_knowledge_map_generation_can_reference_teaching_resources(tmp_path):
    """The AI panel offers an optional resource picker and sends resource_ids."""
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)

    page = client.get("/v1/knowledge-map", headers=th)
    assert page.status_code == 200, page.status_code
    body = page.text
    assert "参考资料（可选）" in body
    assert "resource_ids:refIds" in body
    assert "/teaching/resources?grade=" in body
    # 宽屏适配：共用 980px 容器在桌面上会挤成窄栏；平板起两列、宽屏三列
    assert "max-width:1440px" in body
    assert "km-grid" in body
    assert "@media (min-width:760px)" in body

    # The picker reads the existing school resource endpoint.
    r = client.get("/teaching/resources", headers=th)
    assert r.status_code == 200, r.text
    assert "items" in r.json()

    # The generation route accepts the field and ignores an empty list.
    replies.append(json.dumps({"questions": [{
        "question_type": "choice",
        "text": "0.75 × 4 的结果是多少？",
        "options": ["0.3", "3", "30", "300"],
        "correct_index": 1,
        "explanation": "0.75 × 4 = 3",
        "knowledge": "小数乘整数",
    }]}, ensure_ascii=False))
    r = client.post("/ai/questions/generate", headers=th, json={
        "grade": 5, "subject": "数学", "textbook": "人教版", "semester": "上册",
        "unit": "小数乘法", "knowledge": "小数乘整数", "count": 1,
        "question_type": "choice", "notes": "", "difficulty": "基础", "resource_ids": [],
    })
    assert r.status_code in (200, 502), r.text
print('OK')
''', extra_env={"KNOWLEDGE_MAP": "1"})
