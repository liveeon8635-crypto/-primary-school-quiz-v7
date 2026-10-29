from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from changying.web.weekend_pages import BOARD_JS, BOARD_LAYOUT_JS, board_page_html

TEXT = ("课题：用字母表示数和数量关系\n考点一：省略乘号的四条规则\n数与字母相乘，乘号省略，数写在字母前面：5×m＝5m，8×a×b＝8ab。\n"
        "1与字母相乘，1不写：a×1＝a，1×b＝b。\n易错：2a表示a＋a，a²表示a×a。\n"
        "示例：例题1 | 省略乘号：5×m＝（　　　）　a×1＝（　　　）　b×7.8＝（　　　）　还要说出理由。")

NODE = r'''
function el(tag,attrs,...kids){const n={tag,attrs:attrs||{},children:[],style:{},appendChild(c){if(c)this.children.push(c);return c}};kids.forEach(k=>n.appendChild(k));return n}
function all(n){return [n,...n.children.flatMap(all)]}
''' + BOARD_LAYOUT_JS + r'''
const blocks=blParse([TEXT]);
const body=el('div');const wide=boardLayout(body,[TEXT],true);const narrow=boardLayout(el('div'),[TEXT],false);
const texts=all(body).map(n=>n.attrs.text).filter(Boolean);
console.log(JSON.stringify({blocks:blocks.map(b=>[b.kind,b.title,b.lines.length]),items:blItems(blocks[2].lines[0]),wide,narrow,
  grid:all(body).some(n=>(n.attrs.style||'').includes('grid-template-columns:1fr 1fr')),
  warn:texts.filter(t=>t.startsWith('⚠')),numbers:texts.filter(t=>/^[0-9]$/.test(t)),cyan:all(body).filter(n=>(n.attrs.style||'').includes('#7dd3fc')).map(n=>n.attrs.text),
  plainItems:blItems('没有空括号的一句话')}));
'''


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_board_layout_separates_points_rules_examples_and_warnings():
    out = subprocess.run(["node", "-e", f"const TEXT={json.dumps(TEXT, ensure_ascii=False)};" + NODE], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout)
    assert r["blocks"] == [["plain", "", 1], ["know", "考点一　省略乘号的四条规则", 3], ["example", "例题1　省略乘号", 1]]
    # One item per blank: a question never breaks in the middle; text after the last blank stays as text.
    assert r["items"] == {"lead": "", "items": ["5×m＝", "a×1＝", "b×7.8＝"], "tail": "还要说出理由。"}
    assert r["plainItems"] is None
    assert r["wide"] == {"know": 1, "examples": 1} and r["grid"] is True
    assert r["warn"] == ["⚠ 易错：2a表示a＋a，a²表示a×a。"] and r["numbers"] == ["1", "2"]
    assert r["cyan"] == ["5×m＝5m，8×a×b＝8ab。", "a×1＝a，1×b＝b。"]


def test_board_page_uses_the_layout_and_draws_text_only():
    assert "boardLayout(body,d.content" in BOARD_JS and "boardLayout(top,d.content" in BOARD_JS
    assert "innerHTML" not in BOARD_LAYOUT_JS and "insertAdjacentHTML" not in BOARD_LAYOUT_JS
    html = board_page_html()
    assert "function boardLayout(" in html and html.index("function boardLayout(") < html.index("function board(")


ROUTE = r'''
with TestClient(app) as client:
    page = client.get("/v1/weekend-board")
    assert page.status_code == 200 and "function boardLayout(" in page.text and "boardLayout(body,d.content" in page.text
    plan = client.get("/v1/weekend-plan").text
    assert "function startReason(" in plan and "data-start-reason" in plan
print("OK")
'''


def test_board_route_serves_the_layout(tmp_path):
    import importlib.util
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("weekend_board_layout_helpers", root / "tests" / "test_homework_solve.py")
    helpers = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = helpers
    spec.loader.exec_module(helpers)
    helpers.run_isolated(tmp_path, helpers.COMMON + ROUTE)


CASE2 = ("考点二：代入求值\n四步走：写式子（或抄原式）；把字母换成数，并把省略的乘号补回来：a＝2.5时，1.2a就是1.2×2.5；按先乘除后加减的顺序算出结果；结果带单位：长度用cm。\n"
         "示例：例题2 | 代值计算：（1）当a＝2.5时，求下面各式的值：5×a＝（　　）　1.2a＝（　　）　9－a＝（　　）　a÷4＝（　　）；"
         "（2）当a＝7.5、b＝2.5时，求4a＋b的值；（3）已知n＝m÷4，当n＝24时，m等于多少？")

NODE2 = r'''
function el(tag,attrs,...kids){const n={tag,attrs:attrs||{},children:[],style:{},appendChild(c){if(c)this.children.push(c);return c}};kids.forEach(k=>n.appendChild(k));return n}
function all(n){return [n,...n.children.flatMap(all)]}
''' + BOARD_LAYOUT_JS + r'''
const body=el('div');boardLayout(body,[TEXT],true);const nodes=all(body);
const line=blParse([TEXT])[1].lines[0];
console.log(JSON.stringify({parts:blParts(line),first:blItems(blParts(line)[0]),sentence:blItems('小明说：一个数的（　）倍等于这个数加上（　）。'),
  steps:nodes.map(n=>n.attrs.text).filter(t=>t&&t.startsWith('· ')),
  nowrapLong:nodes.filter(n=>(n.attrs.style||'').includes('white-space:nowrap')).map(n=>n.children.map(c=>c.attrs.text||'').join('')).filter(t=>t.length>14)}));
'''


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_sub_questions_and_long_rules_do_not_overlap():
    out = subprocess.run(["node", "-e", f"const TEXT={json.dumps(CASE2, ensure_ascii=False)};" + NODE2], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout)
    # （1）（2）（3） each start a row; the lead-in stays text; only the four short calculations go in the grid.
    assert [p[:3] for p in r["parts"]] == ["（1）", "（2）", "（3）"]
    assert r["first"] == {"lead": "（1）当a＝2.5时，求下面各式的值：", "items": ["5×a＝", "1.2a＝", "9－a＝", "a÷4＝"], "tail": ""}
    assert r["sentence"] is None                       # a sentence with blanks wraps as text, never in a no-wrap cell
    assert r["nowrapLong"] == []
    assert r["steps"] == ["· 写式子（或抄原式）", "· 把字母换成数，并把省略的乘号补回来：a＝2.5时，1.2a就是1.2×2.5",
                          "· 按先乘除后加减的顺序算出结果", "· 结果带单位：长度用cm"]
