from __future__ import annotations

import json
import subprocess

from changying.web.knowledge_map_pages import KNOWLEDGE_MAP_JS


HARNESS = r'''
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

const source = JSON.parse(fs.readFileSync(0, 'utf8'));

function el(tag, attrs) {
  const node = { tag, attrs: attrs || {}, children: [] };
  for (let i = 2; i < arguments.length; i += 1) {
    const child = arguments[i];
    if (child != null) node.children.push(child);
  }
  if (attrs && attrs.onclick) node.onclick = attrs.onclick;
  return node;
}

const context = {
  console,
  el,
  boot: () => {},
  document: { getElementById: () => null },
  window: {},
};
vm.createContext(context);
vm.runInContext(source, context);

const node = {
  key: '2-2', name: '小数乘小数', unit: 'U1', kind: 'core', assessed: true, enabled: true,
  detail: '', prereqs: [], bankKeys: ['小数乘小数'], bankCount: 0,
  coverage: { counts: { basic: 0, medium: 0, hard: 0 }, total: 0, ready: false },
};
const km = {
  id: 1,
  levels: { basic: '基础', medium: '中等', hard: '提高' },
  nodeKinds: { core: '核心' },
  map: { nodes: [node] },
  dependents: {},
};
vm.runInContext('KM = ' + JSON.stringify(km) + '; KNOTE = {}; KSEQ = {}; KM_OPEN_SEQ = 0; QPANEL = {};', context);

function response(imported) {
  return Object.assign({}, km, { imported });
}

let renders = 0;
let reveals = 0;
context.kmRender = () => { renders += 1; };
context.kmRevealNode = () => { reveals += 1; };
context.confirm = () => true;

const pending = [];
context.api = () => new Promise((resolve, reject) => pending.push({ resolve, reject }));

function findAll(current, predicate, found) {
  if (!current) return found;
  if (predicate(current)) found.push(current);
  (current.children || []).forEach((child) => findAll(child, predicate, found));
  return found;
}
function importButton(row) {
  const found = findAll(row, (item) => item.attrs && item.attrs.text === '导入预置题目草稿', []);
  assert.equal(found.length, 1);
  return found[0];
}
function tick() {
  return new Promise((resolve) => setImmediate(resolve));
}

(async () => {
  const row = context.kmNodeRow(node, { key: 'U1', learned: false });
  const button = importButton(row);
  assert.equal(typeof button.onclick, 'function');

  // 提示在节点标题之后、折叠体之外。
  context.KNOTE['1|2-2'] = '已导入 2 题';
  const withNote = context.kmNodeRow(node, { key: 'U1', learned: false });
  const note = withNote.children.find((child) => child.attrs && child.attrs['data-note'] === '2-2');
  assert(note, 'note element missing');
  assert.equal(withNote.children.indexOf(note), 1);
  const body = withNote.children.find((child) => child.attrs && child.attrs.class === 'km-node-b');
  assert(body && !body.children.includes(note), 'note must stay outside the collapsible body');

  // 开始导入：先显示进度，并展开所属单元。
  context.KNOTE = {};
  context.KSEQ = {};
  button.onclick();
  assert.equal(context.KNOTE['1|2-2'], '正在导入预置草稿…');
  assert(renders >= 1 && reveals >= 1);

  // 成功回调更新提示。
  pending.shift().resolve(response({ added: 2, reused: 1 }));
  await tick();
  assert.equal(context.KNOTE['1|2-2'], '已导入 2 题，跳过已有的 1 题');

  // A -> B -> A：旧的导入请求不能再写回提示或覆盖 KM。
  context.KNOTE = {};
  context.KSEQ = {};
  context.KM_OPEN_SEQ += 1;
  const oldRow = context.kmNodeRow(node, { key: 'U1', learned: false });
  importButton(oldRow).onclick();
  const oldRequest = pending.shift();
  context.KM_OPEN_SEQ += 1;
  context.KNOTE = {};
  context.KSEQ = {};
  const before = context.KM;
  oldRequest.resolve(response({ added: 9, reused: 0 }));
  await tick();
  assert.equal(context.KNOTE['1|2-2'], undefined);
  assert.strictEqual(context.KM, before);

  // 同一节点重复导入：先返回的旧请求不能覆盖新请求。
  context.KNOTE = {};
  context.KSEQ = {};
  const firstRow = context.kmNodeRow(node, { key: 'U1', learned: false });
  importButton(firstRow).onclick();
  const first = pending.shift();
  const secondRow = context.kmNodeRow(node, { key: 'U1', learned: false });
  importButton(secondRow).onclick();
  const second = pending.shift();
  first.resolve(response({ added: 1, reused: 0 }));
  await tick();
  assert.equal(context.KNOTE['1|2-2'], '正在导入预置草稿…');
  second.resolve(response({ added: 3, reused: 0 }));
  await tick();
  assert.equal(context.KNOTE['1|2-2'], '已导入 3 题，跳过已有的 0 题');

  console.log('OK');
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
'''


def test_draft_import_note_is_visible_and_stale_requests_are_ignored():
    result = subprocess.run(
        ['node', '-e', HARNESS],
        input=json.dumps(KNOWLEDGE_MAP_JS),
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'OK' in result.stdout
