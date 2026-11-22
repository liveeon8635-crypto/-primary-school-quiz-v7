from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("rich_slide_helpers", ROOT / "tests/test_homework_solve.py")
helpers = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = helpers
SPEC.loader.exec_module(helpers)


def test_clean_slide_rich_pedagogy_and_media_limits():
    from changying.services import weekend_courseware as cw

    tiny_jpeg = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP///8Q="
    tiny_mp3 = "data:audio/mpeg;base64,SUQzAwAAAAAA"
    big_mp3 = "data:audio/mpeg;base64," + ("A" * 900000)
    too_big_mp3 = "data:audio/mpeg;base64," + ("A" * 1850000)
    long_script = "每当夜幕降临。" * 150

    cleaned = cw.clean(
        "slide",
        {
            "title": "第2环节 · 短文精读",
            "teacherNotes": "仅教师可见的课堂提示",
            "slides": [
                {
                    "layout": "scene",
                    "badge": "写作背景",
                    "heading": "《母亲的那盏灯》情境导入",
                    "subtitle": "贴近日常深夜书桌",
                    "caption": "母爱守候场景",
                    "figure": {"type": "uploaded_image", "data_url": tiny_jpeg, "alt": "台灯插图"},
                    "gallery": [
                        {"data_url": tiny_jpeg, "caption": "分镜一：缝补校服"},
                        {"data_url": tiny_jpeg, "caption": "分镜二：换冷毛巾"},
                    ],
                    "body": ["第一段背景说明。"],
                    "audioLabel": "课文配音朗读",
                    "audioText": long_script,
                    "audioUrl": big_mp3,
                },
                {
                    "layout": "characters",
                    "heading": "文章人物分析",
                    "characters": [
                        {
                            "name": "母亲",
                            "role": "无私守候者",
                            "traits": ["勤劳", "温柔"],
                            "details": "微驼着背、粗糙的手指",
                            "emotion": "无私深沉的母爱",
                        }
                    ],
                },
                {
                    "layout": "plot",
                    "heading": "情节脉络图",
                    "plot": [
                        {"stage": "开端", "scene": "第①段", "event": "客厅台灯亮起", "feeling": "温暖日常"},
                        {"stage": "高潮", "scene": "第④段", "event": "雨夜晚归见灯光", "feeling": "踏实感动"},
                    ],
                    "qa": [{"q": "为什么灯一直亮着？", "a": "象征母亲始终牵挂守候。"}],
                    "highlight": "抓关键词句体会情感",
                    "audioUrl": tiny_mp3,
                },
            ],
        },
    )
    assert cleaned["slides"][0]["layout"] == "scene"
    assert cleaned["slides"][0]["caption"] == "母爱守候场景"
    assert cleaned["slides"][0]["audioLabel"] == "课文配音朗读"
    assert cleaned["slides"][0]["figure"]["type"] == "uploaded_image"
    assert len(cleaned["slides"][0]["gallery"]) == 2
    assert cleaned["slides"][0]["gallery"][1]["caption"] == "分镜二：换冷毛巾"
    assert len(cleaned["slides"][0]["audioText"]) > 600
    assert len(cleaned["slides"][1]["characters"]) == 1
    assert cleaned["slides"][1]["characters"][0]["traits"] == ["勤劳", "温柔"]
    assert len(cleaned["slides"][2]["plot"]) == 2
    assert cleaned["slides"][2]["qa"][0]["q"] == "为什么灯一直亮着？"

    pub = cw.public_params("slide", cleaned)
    assert "teacherNotes" not in pub
    assert len(pub["slides"]) == 3
    assert "audioText" not in pub["slides"][0]
    assert len(pub["slides"][0]["gallery"]) == 2

    try:
        cw.clean("slide", {"slides": [{"heading": "超长音频", "body": ["正文"], "audioUrl": too_big_mp3}]})
        raise AssertionError("expected ValueError for oversized audio")
    except ValueError as exc:
        assert "音频数据过大" in str(exc)


def test_courseware_slide_renderer_and_editor_preserves_rich_fields():
    from changying.web.weekend_courseware_pages import COURSEWARE_JS, COURSEWARE_PLAN_JS

    assert "speechSynthesis" not in COURSEWARE_JS
    assert "speechSynthesis" not in COURSEWARE_PLAN_JS
    assert "18000000" in COURSEWARE_PLAN_JS
    assert "media-src 'self' data: blob:;" in (ROOT / "changying/compat/legacy.py").read_text(encoding="utf-8")

    sample = {
        "title": "短文精读",
        "teacherNotes": "注意引导学生圈画细节",
        "slides": [
            {
                "layout": "scene",
                "badge": "写作背景",
                "heading": "背景与配音",
                "subtitle": "贴近生活",
                "caption": "暖灯插图说明",
                "figure": {"type": "uploaded_image", "data_url": "data:image/jpeg;base64,AAAA", "alt": "灯"},
                "gallery": [
                    {"data_url": "data:image/jpeg;base64,AAAB", "caption": "分镜1"},
                    {"data_url": "data:image/jpeg;base64,AAAC", "caption": "分镜2"},
                ],
                "audioLabel": "课文范读",
                "audioText": "示范逐字朗读原稿内容",
                "audioUrl": "data:audio/mpeg;base64,SUQz",
                "body": ["这是==重点细节==所在句子。"],
            },
            {
                "layout": "characters",
                "heading": "人物分析",
                "audioLabel": "人物讲读",
                "audioText": "第二页逐字稿",
                "audioUrl": "data:audio/mpeg;base64,SUQ0",
                "characters": [
                    {
                        "name": "母亲",
                        "role": "核心人物",
                        "traits": ["温柔", "操劳"],
                        "details": "==微驼着背==缝补校服",
                        "emotion": "无私母爱",
                    }
                ],
                "plot": [
                    {"stage": "开端", "scene": "夜晚", "event": "台灯亮起", "feeling": "温馨"}
                ],
                "cards": [{"tag": "考点14", "title": "细节描写", "text": "找动作神态"}],
                "steps": [{"label": "第一步", "desc": "点明方法"}],
                "qa": [{"q": "体会到什么？", "a": "母爱的无微不至。"}],
                "highlight": "记住三步答题法",
            },
        ],
    }

    js_script = rf'''
const assert = require('node:assert/strict');
const audioRegistry = [];
function makeNode(tag, attrs, children) {{
  const listeners = {{}};
  const n = {{
    tagName: String(tag || '').toUpperCase(),
    attrs: attrs || {{}},
    children: [],
    style: {{}},
    hidden: !!(attrs && attrs.hidden),
    value: (attrs && attrs.value) || '',
    textContent: (attrs && attrs.text) || '',
    _pausedCalls: 0,
    appendChild(c) {{ if (c) this.children.push(c); return c; }},
    insertBefore(c, ref) {{
      const cur = this.children.indexOf(c);
      if (cur >= 0) this.children.splice(cur, 1);
      const idx = this.children.indexOf(ref);
      if (idx >= 0) this.children.splice(idx, 0, c);
      else this.children.push(c);
      return c;
    }},
    addEventListener(ev, fn) {{ (listeners[ev] = listeners[ev] || []).push(fn); }},
    dispatchEvent(ev) {{ (listeners[ev] || []).forEach(fn => fn()); }},
    dispatchPlay() {{ (listeners.play || []).forEach(fn => fn()); }},
    play() {{ this.dispatchPlay(); return Promise.resolve(); }},
    pause() {{ this._pausedCalls++; }},
  }};
  Object.keys(n.attrs).forEach(k => {{
    if (k !== 'text' && k !== 'style' && k !== 'hidden') n[k] = n.attrs[k];
  }});
  if (n.tagName === 'AUDIO') audioRegistry.push(n);
  for (const c of children) if (c) n.children.push(c);
  return n;
}}
function el(tag, attrs, ...children) {{ return makeNode(tag, attrs, children); }}
const document = {{
  createTextNode(t) {{ return makeNode('#text', {{ text: String(t || '') }}, []); }},
  querySelectorAll(sel) {{ return sel === 'audio' ? audioRegistry : []; }}
}};
const window = {{}};
function all(node, pred, out = []) {{
  if (!node) return out;
  if (pred(node)) out.push(node);
  for (const c of node.children || []) all(c, pred, out);
  return out;
}}
let apiHandler = () => Promise.resolve({{}});
function api(p, o) {{ return apiHandler(p, o); }}

{COURSEWARE_JS}
{COURSEWARE_PLAN_JS}

// 1. Verify cwSlide renders <img> (single + gallery), <audio>, script toggle, mutual exclusion, characters, plot, qa, and highlight in showAllSlides mode.
const host = el('div');
cwRender(host, {{ kind: 'slide', params: {json.dumps(sample, ensure_ascii=False)} }}, {{ showAllSlides: true }}, false, true);
const imgs = all(host, n => n.tagName === 'IMG');
const audios = all(host, n => n.tagName === 'AUDIO');
assert.equal(imgs.length, 3);
assert.equal(audios.length, 2);
assert.equal(audios[0].controls, true);
audios[1].play();
assert.equal(audios[0]._pausedCalls, 1, 'playing second audio must pause first');
audios[0].dispatchEvent('error');
assert(all(host, n => !n.hidden && String(n.textContent).includes('音频加载失败')).length === 1, 'error event should surface audio load error');
audios[0].dispatchEvent('loadedmetadata');
assert.equal(all(host, n => !n.hidden && String(n.textContent).includes('音频加载失败')).length, 0, 'loadedmetadata should clear audio load error');

// Verify Blob URL resolution converts valid base64 audio data URLs when Blob/atob/URL.createObjectURL exist
const blobStub = class {{ constructor(parts, opts) {{ this.parts = parts; this.type = opts && opts.type; }} }};
const resolvedBlobUrl = (function() {{
  const Blob = blobStub;
  const atob = (b64) => Buffer.from(b64, 'base64').toString('binary');
  const URL = {{ createObjectURL: (b) => 'blob:mock/' + b.type + '/' + b.parts[0].length }};
  const fn = new Function('Blob', 'atob', 'URL', 'var CW_AUDIO_BLOB_CACHE={{}};' + cwResolveAudioSrc.toString() + ';return cwResolveAudioSrc("data:audio/mpeg;base64,SUQzAw==");');
  return fn(Blob, atob, URL);
}})();
assert.equal(resolvedBlobUrl, 'blob:mock/audio/mpeg/4');
const allTexts = all(host, () => true).map(n => n.textContent).join('\n');
assert(allTexts.includes('暖灯插图说明'), 'missing caption');
assert(allTexts.includes('分镜1') && allTexts.includes('分镜2'), 'missing gallery captions');
assert(allTexts.includes('课文范读'), 'missing audioLabel');
assert(allTexts.includes('示范逐字朗读原稿内容'), 'missing inline audioText script box');
const scriptBtn = all(host, n => n.tagName === 'BUTTON' && n.textContent === '对照朗读原稿')[0];
assert(scriptBtn, 'expected 对照朗读原稿 toggle');
const scriptDiv = all(host, n => n.textContent === '示范逐字朗读原稿内容')[0];
assert.equal(scriptDiv.hidden, true);
scriptBtn.onclick();
assert.equal(scriptDiv.hidden, false);
assert(allTexts.includes('细节描写：'), 'missing character details');
assert(allTexts.includes('无私母爱'), 'missing character emotion');
assert(allTexts.includes('情感：温馨'), 'missing plot feeling');
const toggles = all(host, n => n.tagName === 'BUTTON' && n.textContent === '查看点拨');
assert.equal(toggles.length, 1);

// 2. Verify Audio Audit Hub + openEditor preview-first + collect() preserves gallery and audioText.
let savedPayload = null;
apiHandler = (path, opts) => {{
  if (opts && opts.method === 'PUT') {{
    savedPayload = opts.json;
    return Promise.resolve({{ items: [] }});
  }}
  return Promise.resolve({{
    subject: '语文',
    courseType: 'reading',
    practiceStage: 5,
    stageOptions: [{{ no: 2, key: 'short_reading', name: '短文阅读', minutes: 20 }}],
    pages: {{ '2': ['测试页面'] }},
    kindLabels: {{ slide: '图文幻灯片', reading: '阅读依据', steps: '分步讲解' }},
    templates: ['slide', 'reading', 'steps'],
    items: [{{ stage: 2, page: 0, kind: 'slide', status: 'draft', writtenTask: false, params: {json.dumps(sample, ensure_ascii=False)} }}]
  }});
}};
(async () => {{
  const box = el('div');
  cwPlan(box, 12, () => {{}});
  await new Promise(r => setTimeout(r, 20));
  const auditBtn = all(box, n => n.tagName === 'BUTTON' && String(n.textContent).includes('核对音频配套（2/2）'))[0];
  assert(auditBtn, 'expected 核对音频配套（2/2） button');
  auditBtn.onclick();
  const auditTexts = all(box, () => true).map(n => n.textContent).join('\n');
  assert(auditTexts.includes('音频配套核对总表'), 'expected audit panel header');
  assert(all(box, n => n.tagName === 'BUTTON' && n.textContent === '替换 .mp3').length === 2, 'expected per-slide replace mp3 buttons');

  const editBtn = all(box, n => n.tagName === 'BUTTON' && n.textContent === '预览／修改')[0];
  assert(editBtn, 'expected 预览／修改 button');
  editBtn.onclick();
  const card = all(box, c =>
    c.children.some(ch => all(ch, n => n.tagName === 'DETAILS').length)
    && c.children.some(ch => all(ch, n => n.tagName === 'AUDIO' || n.tagName === 'IMG').length)
    && all(c, n => n.tagName === 'BUTTON' && String(n.textContent).includes('保存修改')).length
  ).slice(-1)[0];
  assert(card, 'expected editor card');
  const detailsIdx = card.children.findIndex(ch => all(ch, n => n.tagName === 'DETAILS').length);
  const previewIdx = card.children.findIndex(ch => all(ch, n => n.tagName === 'AUDIO' || n.tagName === 'IMG').length);
  assert(previewIdx >= 0 && detailsIdx > previewIdx, 'preview should appear before form details');
  const saveBtn = all(card, n => n.tagName === 'BUTTON' && String(n.textContent).includes('保存修改'))[0];
  saveBtn.onclick();
  await new Promise(r => setTimeout(r, 20));
  assert(savedPayload && savedPayload.kind === 'slide');
  const s0 = savedPayload.params.slides[0];
  const s1 = savedPayload.params.slides[1];
  assert.equal(s0.layout, 'scene');
  assert.equal(s0.caption, '暖灯插图说明');
  assert.equal(s0.audioLabel, '课文范读');
  assert.equal(s0.audioText, '示范逐字朗读原稿内容');
  assert.equal(s0.audioUrl, 'data:audio/mpeg;base64,SUQz');
  assert.equal(s0.figure.type, 'uploaded_image');
  assert.equal(s0.gallery.length, 2);
  assert.equal(s0.gallery[0].caption, '分镜1');
  assert.equal(s1.characters[0].name, '母亲');
  assert.equal(s1.plot[0].feeling, '温馨');
  assert.equal(s1.cards[0].tag, '考点14');
  assert.equal(s1.qa[0].a, '母爱的无微不至。');

  // 3. Verify renderWholePreview uses full it.params when it.status === 'approved' and _slim_response_item omits slides from it.approved.
  apiHandler = () => Promise.resolve({{
    subject: '语文',
    courseType: 'reading',
    practiceStage: 5,
    stageOptions: [{{ no: 2, key: 'short_reading', name: '短文阅读', minutes: 20 }}],
    pages: {{ '2': ['测试页面'] }},
    kindLabels: {{ slide: '图文幻灯片', reading: '阅读依据', steps: '分步讲解' }},
    templates: ['slide', 'reading', 'steps'],
    items: [{{
      stage: 2, page: 0, kind: 'slide', status: 'approved', writtenTask: false,
      params: {json.dumps(sample, ensure_ascii=False)},
      approved: {{ title: '短文精读' }}
    }}]
  }});
  const apBox = el('div');
  cwPlan(apBox, 12, () => {{}});
  await new Promise(r => setTimeout(r, 20));
  const wholeBtn = all(apBox, n => n.tagName === 'BUTTON' && n.textContent === '整体预览整套课件')[0];
  assert(wholeBtn, 'expected 整体预览整套课件 button');
  wholeBtn.onclick();
  const apImgs = all(apBox, n => n.tagName === 'IMG');
  const apAudios = all(apBox, n => n.tagName === 'AUDIO');
  assert.equal(apImgs.length, 3, 'approved slimmed item must still render all slide images');
  assert.equal(apAudios.length, 2, 'approved slimmed item must still render all slide audios');
}})().catch(e => {{ console.error(e); process.exitCode = 1; }});
'''
    res = subprocess.run(["node", "-"], input=js_script, text=True, capture_output=True, timeout=20)
    assert res.returncode == 0, res.stdout + res.stderr


def test_rich_chinese_bundle_multipart_import_approve_and_board(tmp_path):
    helpers.run_isolated(
        tmp_path,
        helpers.COMMON
        + r'''
tiny_jpeg = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP///8Q="
tiny_mp3 = "data:audio/mpeg;base64,SUQzAwAAAAAA"
bundle = {
    "schemaVersion": 1,
    "subject": "语文",
    "dryRun": False,
    "onConflict": "overwrite",
    "items": [
        {
            "lessonNo": 12,
            "title": "第12课：阅读——舐犊情深",
            "coreTarget": "掌握细节描写、反复词语与结尾段作用。",
            "teacherPlan": "一、短文阅读《母亲的那盏灯》\n二、长文阅读与考点精讲",
            "courseType": "reading",
            "readingPlan": "每当夜幕降临，客厅那盏暖黄的台灯总会亮起。直到我写完作业，那盏灯还一直亮着。",
            "writingPlan": "",
            "ppt": ["每当夜幕降临，客厅那盏暖黄的台灯总会亮起。直到我写完作业，那盏灯还一直亮着。"],
            "examples": ["【例题1】体会母爱细节。"],
            "closureTraining": "完成阅读巩固。",
            "questions": [
                {
                    "stem": "下列理解正确的是哪一项？",
                    "options": ["A. 灯象征母爱", "B. 与母爱无关"],
                    "correctIndex": 0,
                    "explanation": "台灯贯穿全文象征母爱守候。",
                    "knowledge": "细节描写",
                }
            ],
            "writtenQuestions": [],
        }
    ],
    "courseware": {
        "pages": [
            {
                "stageNo": 1,
                "page": None,
                "expectedPageText": "点名与回顾",
                "kind": "slide",
                "params": {"title": "1. 点名导入", "slides": [{"layout": "cover", "heading": "舐犊情深", "figure": {"type": "uploaded_image", "data_url": tiny_jpeg, "alt": "封面图"}}]},
                "writtenTask": False,
            },
            {
                "stageNo": 2,
                "page": 0,
                "expectedPageText": "每当夜幕降临，客厅那盏暖黄的台灯总会亮起。直到我写完作业，那盏灯还一直亮着。",
                "kind": "slide",
                "params": {
                    "title": "2. 短文精读",
                    "slides": [
                        {
                            "layout": "reading",
                            "heading": "《母亲的那盏灯》",
                            "audioLabel": "课文配音朗读",
                            "audioText": "大屏必须剔除的逐字朗读原稿",
                            "audioUrl": tiny_mp3,
                            "figure": {"type": "uploaded_image", "data_url": tiny_jpeg, "alt": "台灯"},
                            "gallery": [{"data_url": tiny_jpeg, "caption": "分镜图"}],
                            "body": ["每当夜幕降临，台灯==一直亮着==。"],
                        },
                        {
                            "layout": "characters",
                            "heading": "人物档案",
                            "characters": [{"name": "母亲", "role": "核心人物", "traits": ["温柔"], "details": "细细缝补", "emotion": "深沉母爱"}],
                        },
                        {
                            "layout": "plot",
                            "heading": "情节脉络",
                            "plot": [{"stage": "开端", "scene": "夜晚", "event": "台灯亮起", "feeling": "温馨"}],
                        },
                    ],
                },
                "writtenTask": False,
            },
            {
                "stageNo": 3,
                "page": None,
                "expectedPageText": "长文阅读",
                "kind": "slide",
                "params": {"title": "3. 长文导学", "slides": [{"heading": "《父亲的泥脚》", "body": ["情节梳理"]}]},
                "writtenTask": False,
            },
            {
                "stageNo": 4,
                "page": None,
                "expectedPageText": "考点总结",
                "kind": "slide",
                "params": {"title": "4. 考点总结", "slides": [{"heading": "三大公式", "body": ["方法+内容+情感"]}]},
                "writtenTask": False,
            },
            {
                "stageNo": 5,
                "page": None,
                "expectedPageText": "综合练习",
                "kind": "slide",
                "params": {"title": "5. 综合练习", "slides": [{"heading": "随堂任务", "body": ["完成阅读练习"]}]},
                "writtenTask": False,
            },
            {
                "stageNo": 6,
                "page": None,
                "expectedPageText": "课后反馈",
                "kind": "slide",
                "params": {"title": "6. 课后反馈", "slides": [{"heading": "课后复盘", "body": ["巩固模板"]}]},
                "writtenTask": False,
            },
        ]
    },
}

with TestClient(app) as client:
    th, sh, student_id, school_id = setup(client)
    plan_html = client.get('/v1/weekend-plan')
    assert plan_html.status_code == 200
    csp = plan_html.headers.get('content-security-policy', '')
    assert "media-src 'self' data: blob:;" in csp, csp
    imp = client.post(
        '/teacher/weekend/lessons/import',
        headers=th,
        data={'subject': '语文', 'lessonNo': '12', 'force': '1', 'courseType': 'reading'},
        files={'file': ('lesson12-reading-bundle.json', json.dumps(bundle, ensure_ascii=False).encode('utf-8'), 'application/json')},
    )
    assert imp.status_code == 200, imp.text
    lid = imp.json()['lessonId']

    cw = client.get(f'/teacher/weekend/lessons/{lid}/courseware', headers=th)
    assert cw.status_code == 200, cw.text
    items = cw.json()['items']
    assert len(items) == 6
    s2 = [x for x in items if x['stage'] == 2][0]
    assert s2['params']['slides'][0]['audioUrl'] == tiny_mp3
    assert s2['params']['slides'][1]['characters'][0]['name'] == '母亲'
    assert s2['params']['slides'][2]['plot'][0]['stage'] == '开端'

    for it in items:
        ap = client.post(f'/teacher/weekend/lessons/{lid}/courseware/approve', headers=th, json={'stageNo': it['stage'], 'page': it['page']})
        assert ap.status_code == 200, (it['stage'], ap.text)

    sess = client.post('/teacher/weekend/sessions', headers=th, json={'lessonId': lid})
    assert sess.status_code == 200, sess.text
    sid = sess.json()['id']
    assert client.post(f'/teacher/weekend/sessions/{sid}/start', headers=th).status_code == 200
    assert client.post(f'/teacher/weekend/sessions/{sid}/goto', headers=th, json={'stage': 2}).status_code == 200
    board = client.get(f'/teacher/weekend/sessions/{sid}/board', headers=th)
    assert board.status_code == 200, board.text
    b_cw = board.json().get('courseware') or {}
    assert b_cw.get('kind') == 'slide'
    assert b_cw['params']['slides'][0]['audioUrl'] == tiny_mp3
    assert b_cw['params']['slides'][0]['figure']['type'] == 'uploaded_image'
    assert b_cw['params']['slides'][0]['gallery'][0]['caption'] == '分镜图'
    assert 'audioText' not in b_cw['params']['slides'][0]
    assert b_cw['params']['slides'][1] == {}

    v1 = client.post(f'/teacher/weekend/sessions/{sid}/courseware/view', headers=th,
                     json={'stageNo': 2, 'page': 0, 'view': {'slideIndex': 1, 'audioPlaying': False}})
    assert v1.status_code == 200, v1.text
    b1 = client.get(f'/teacher/weekend/sessions/{sid}/board', headers=th).json()['courseware']
    assert b1['params']['slides'][0] == {}
    assert b1['params']['slides'][1]['characters'][0]['name'] == '母亲'

    v2 = client.post(f'/teacher/weekend/sessions/{sid}/courseware/view', headers=th,
                     json={'stageNo': 2, 'page': 0, 'view': {'slideIndex': 2, 'audioPlaying': False}})
    assert v2.status_code == 200, v2.text
    b2 = client.get(f'/teacher/weekend/sessions/{sid}/board', headers=th).json()['courseware']
    assert b2['params']['slides'][2]['plot'][0]['stage'] == '开端'
print('OK')
''',
    )


def test_chinese_overwrite_reimport_prunes_history_and_preserves_readiness(tmp_path):
    helpers.run_isolated(
        tmp_path,
        helpers.COMMON
        + r'''
from copy import deepcopy
from sqlalchemy import func, select
from changying.web.weekend_courseware import items_of, register_courseware_table

def make_bundle(tag: str, reading_text: str):
    tiny_jpeg = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP///8Q" + ("AAAA" if tag == "v1" else "BBBB") + "=="
    tiny_mp3 = "data:audio/mpeg;base64,SUQzAwAAAAAA" + ("CCCC" if tag == "v1" else "DDDD")
    return {
        "schemaVersion": 1,
        "subject": "语文",
        "dryRun": False,
        "onConflict": "overwrite",
        "items": [
            {
                "lessonNo": 12,
                "title": f"第12课-{tag}",
                "coreTarget": "把握细节描写。",
                "teacherPlan": f"教案-{tag}",
                "courseType": "reading",
                "readingPlan": reading_text,
                "writingPlan": "",
                "ppt": [reading_text],
                "examples": [],
                "closureTraining": "巩固练习。",
                "questions": [],
                "writtenQuestions": [],
            }
        ],
        "courseware": {
            "pages": [
                {"stageNo": 1, "page": None, "expectedPageText": "导入", "kind": "slide",
                 "params": {"title": f"1-{tag}", "slides": [{"heading": f"导入-{tag}", "body": ["热身"], "audioUrl": tiny_mp3}]}, "writtenTask": False},
                {"stageNo": 2, "page": 0, "expectedPageText": reading_text, "kind": "slide",
                 "params": {"title": f"2-{tag}", "slides": [{"heading": f"短文-{tag}", "body": [reading_text], "figure": {"type": "uploaded_image", "data_url": tiny_jpeg, "alt": "图"}}]}, "writtenTask": False},
                {"stageNo": 3, "page": None, "expectedPageText": "长文", "kind": "slide",
                 "params": {"title": f"3-{tag}", "slides": [{"heading": f"长文-{tag}", "body": ["精读"]}]}, "writtenTask": False},
                {"stageNo": 4, "page": None, "expectedPageText": "总结", "kind": "slide",
                 "params": {"title": f"4-{tag}", "slides": [{"heading": f"总结-{tag}", "body": ["公式"]}]}, "writtenTask": False},
                {"stageNo": 5, "page": None, "expectedPageText": "练习", "kind": "slide",
                 "params": {"title": f"5-{tag}", "slides": [{"heading": f"练习-{tag}", "body": ["迁移"]}]}, "writtenTask": False},
                {"stageNo": 6, "page": None, "expectedPageText": "反馈", "kind": "slide",
                 "params": {"title": f"6-{tag}", "slides": [{"heading": f"反馈-{tag}", "body": ["作业"]}]}, "writtenTask": False},
            ]
        },
    }

with TestClient(app) as client:
    th, sh, student_id, school_id = setup(client)
    b1 = make_bundle("v1", "短文原文一")
    r1 = client.post('/teacher/weekend/lessons/import', headers=th,
                     data={'subject': '语文', 'lessonNo': '12', 'force': '0', 'courseType': 'reading'},
                     files={'file': ('v1.json', json.dumps(b1, ensure_ascii=False).encode('utf-8'), 'application/json')})
    assert r1.status_code == 200, r1.text
    lid = r1.json()['lessonId']

    items = client.get(f'/teacher/weekend/lessons/{lid}/courseware', headers=th).json()['items']
    for it in items:
        ap = client.post(f'/teacher/weekend/lessons/{lid}/courseware/approve', headers=th, json={'stageNo': it['stage'], 'page': it['page']})
        assert ap.status_code == 200, ap.text

    # Unhydrated readiness check via schedule endpoint must report approved and canStart=True
    sched = client.get('/teacher/weekend/schedule?subject=语文', headers=th)
    assert sched.status_code == 200, sched.text
    row12 = [x for x in sched.json()['items'] if x['lessonNo'] == 12][0]
    assert row12['coursewareApproved'] is True
    assert row12['canStart'] is True

    # Three sequential overwrite imports must keep at most 2 latest undoable history rows and drop old previousDraft blobs
    b2 = make_bundle("v2", "短文原文二")
    r2 = client.post('/teacher/weekend/lessons/import', headers=th,
                     data={'subject': '语文', 'lessonNo': '12', 'force': '1', 'courseType': 'reading'},
                     files={'file': ('v2.json', json.dumps(b2, ensure_ascii=False).encode('utf-8'), 'application/json')})
    assert r2.status_code == 200, r2.text

    b3 = make_bundle("v3", "短文原文三")
    r3 = client.post('/teacher/weekend/lessons/import', headers=th,
                     data={'subject': '语文', 'lessonNo': '12', 'force': '1', 'courseType': 'reading'},
                     files={'file': ('v3.json', json.dumps(b3, ensure_ascii=False).encode('utf-8'), 'application/json')})
    assert r3.status_code == 200, r3.text

    b4 = make_bundle("v4", "短文原文四")
    r4 = client.post('/teacher/weekend/lessons/import', headers=th,
                     data={'subject': '语文', 'lessonNo': '12', 'force': '1', 'courseType': 'reading'},
                     files={'file': ('v4.json', json.dumps(b4, ensure_ascii=False).encode('utf-8'), 'application/json')})
    assert r4.status_code == 200, r4.text

    hist_table = legacy.Base.metadata.tables['weekend_plan_import_history']
    cw_table = register_courseware_table(legacy)
    with legacy.SessionLocal() as db:
        hist_rows = db.execute(select(hist_table.c.id).where(hist_table.c.lesson_id == lid).order_by(hist_table.c.id.asc())).all()
        assert len(hist_rows) == 2, f"expected bounded 2 history rows, got {len(hist_rows)}"
        cw_row = db.execute(select(cw_table).where(cw_table.c.lesson_id == lid)).first()
        unhydrated = items_of(cw_row, hydrate=False)
        assert all('previousDraft' not in x for x in unhydrated)
        assert all(x['approved'] is None and x['status'] == 'draft' for x in unhydrated)
        prev_vid, latest_vid = hist_rows[0][0], hist_rows[1][0]

    # Undo restore must still cleanly roll back v4 -> v3 and preserve previousImportId
    restored = client.post(f'/teacher/weekend/lessons/{lid}/import-history/{latest_vid}/restore', headers=th)
    assert restored.status_code == 200, restored.text
    assert restored.json()['title'] == '第12课-v3'
    after_restore = client.get(f'/teacher/weekend/lessons/{lid}', headers=th)
    assert after_restore.status_code == 200, after_restore.text
    assert after_restore.json()['previousImportId'] == prev_vid
print('OK')
''',
    )
