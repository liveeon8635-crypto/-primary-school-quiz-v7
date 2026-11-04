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
  draftNodes: ['小数乘小数'],
};

const unitBody = { hidden: true };
const unitCaret = { textContent: '▸' };
const unitHead = {
  attrs: {},
  setAttribute(name, value) { this.attrs[name] = value; },
  querySelector(selector) { return selector === '.km-caret' ? unitCaret : null; },
};
const unit = {
  opened: false,
  classList: { add(name) { if (name === 'open') unit.opened = true; } },
  querySelector(selector) {
    if (selector === '.km-unit-b') return unitBody;
    if (selector === '.km-unit-t') return unitHead;
    return null;
  },
};

context.document = { getElementById: (id) => (id === 'unit-U1' ? unit : null) };
vm.runInContext('KM = ' + JSON.stringify(km) + '; KNOTE = {}; KSEQ = {}; KM_OPEN_SEQ = 0; QPANEL = {};', context);

function fullMap(id, imported) {
  const map = Object.assign({}, km, { id });
  if (imported) map.imported = imported;
  return map;
}

let renders = 0;
context.kmRender = () => { renders += 1; };
context.kmSave = () => {};
context.confirm = () => true;

const pending = [];
context.api = () => new Promise((resolve, reject) => pending.push({ resolve, reject }));

function findAll(current, predicate, found) {
  if (!current) return found;
  if (predicate(current)) found.push(current);
  (current.children || []).forEach((child) => findAll(child, predicate, found));
  return found;
}
function nodeRow() {
  return context.kmNodeRow(node, { key: 'U1', learned: false });
}
function button(row, text) {
  const found = findAll(row, (item) => item.attrs && item.attrs.text === text, []);
  assert.equal(found.length, 1, text + ' button missing');
  return found[0];
}
function tick() {
  return new Promise((resolve) => setImmediate(resolve));
}
async function openMap(id) {
  context.kmOpen(id);
  pending.shift().resolve(fullMap(id));
  await tick();
  assert.equal(context.KM.id, id);
}

(async () => {
  const row = nodeRow();
  const button0 = button(row, '导入预置题目草稿');
  assert.equal(typeof button0.onclick, 'function');

  // 提示在节点标题之后、折叠体之外。
  context.KNOTE['1|2-2'] = '已导入 2 题';
  const withNote = nodeRow();
  const note = withNote.children.find((child) => child.attrs && child.attrs['data-note'] === '2-2');
  assert(note, 'note element missing');
  assert.equal(withNote.children.indexOf(note), 1);
  const body = withNote.children.find((child) => child.attrs && child.attrs.class === 'km-node-b');
  assert(body && !body.children.includes(note), 'note must stay outside the collapsible body');

  // 开始导入：提示出现，真实展开函数打开所属单元。
  context.KNOTE = {};
  context.KSEQ = {};
  button0.onclick();
  assert.equal(context.KNOTE['1|2-2'], '正在导入预置草稿…');
  assert.equal(unitBody.hidden, false);
  assert.equal(unit.opened, true);
  assert.equal(unitHead.attrs['aria-expanded'], 'true');
  assert.equal(unitCaret.textContent, '▾');
  assert(renders >= 1);

  // 成功回调更新提示。
  pending.shift().resolve(fullMap(1, { added: 2, reused: 1 }));
  await tick();
  assert.equal(context.KNOTE['1|2-2'], '已导入 2 题，跳过已有的 1 题');

  // 真实 A→B→A：旧导入请求不能写回提示或覆盖 KM。
  button(nodeRow(), '导入预置题目草稿').onclick();
  const oldRequest = pending.shift();
  await openMap(2);
  await openMap(1);
  button(nodeRow(), '导入预置题目草稿').onclick();
  const newRequest = pending.shift();
  oldRequest.resolve(fullMap(1, { added: 9, reused: 0 }));
  await tick();
  assert.equal(context.KNOTE['1|2-2'], '正在导入预置草稿…');
  newRequest.resolve(fullMap(1, { added: 4, reused: 0 }));
  await tick();
  assert.equal(context.KNOTE['1|2-2'], '已导入 4 题，跳过已有的 0 题');

  // 导入期间删除节点：旧请求不能回写提示。
  const deleteRow = nodeRow();
  button(deleteRow, '导入预置题目草稿').onclick();
  const deletedRequest = pending.shift();
  button(deleteRow, '删除').onclick();
  assert.equal(context.KNOTE['1|2-2'], undefined);
  deletedRequest.resolve(fullMap(1, { added: 7, reused: 0 }));
  await tick();
  assert.equal(context.KNOTE['1|2-2'], undefined);

  // 同一节点重复导入：旧请求不能覆盖新请求。
  button(nodeRow(), '导入预置题目草稿').onclick();
  const first = pending.shift();
  button(nodeRow(), '导入预置题目草稿').onclick();
  const second = pending.shift();
  first.resolve(fullMap(1, { added: 1, reused: 0 }));
  await tick();
  assert.equal(context.KNOTE['1|2-2'], '正在导入预置草稿…');
  second.resolve(fullMap(1, { added: 3, reused: 0 }));
  await tick();
  assert.equal(context.KNOTE['1|2-2'], '已导入 3 题，跳过已有的 0 题');

  // 失败回调也要显示，并且同样受请求有效性保护。
  button(nodeRow(), '导入预置题目草稿').onclick();
  pending.shift().reject(new Error('boom'));
  await tick();
  assert.equal(context.KNOTE['1|2-2'], '导入失败：boom');

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
