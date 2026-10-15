from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("import_integrity_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_full_reading_material_and_all_five_homework_questions_survive_import_and_save(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
import io, zipfile
from html import escape
story = '阅读原文《山里的承诺》\n' + ('这是必须保留的阅读文章，不能只剩题目。' * 700) + '\n文章结束标记。'
homework = '作业：《山里的承诺》\n' + story + '\n' + '\n'.join(f'{i}.第{i}题：'+('联系原文回答，保留题目细节。'*20) for i in range(1,6)) + '\n第五题结束标记。\n作业参考答案：教师另行批改。'
source = '第六课 民间故事\n本节目标：概括故事内容。\n' + story + '\n课后练习\n' + homework
example = '长例题完整结尾。' * 90
slide = '这是一页需要完整保存的PPT文字。' * 50
reply = json.dumps({'title':'民间故事','coreTarget':'概括故事','teacherPlan':'组织学生阅读并回答问题。','examples':[example], 'ppt':[slide],
                    'closureTraining':'AI只返回了两道题的摘要。','questions':[]},ensure_ascii=False)
buf = io.BytesIO()
with zipfile.ZipFile(buf,'w') as z:
    z.writestr('[Content_Types].xml','<Types/>')
    z.writestr('word/document.xml','<w:document>'+''.join('<w:p><w:r><w:t>'+escape(line)+'</w:t></w:r></w:p>' for line in source.splitlines())+'</w:document>')
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    replies.append(reply)
    r = client.post('/teacher/weekend/lessons/import',headers=th,data={'subject':'语文','lessonNo':'17'},files={'file':('lesson.docx',buf.getvalue(),'application/octet-stream')})
    assert r.status_code == 200,r.text
    lid=r.json()['lessonId'];assert r.json()['sourceChars'] == len(source)
    url=f'/teacher/weekend/lessons/{lid}'
    got=client.get(url,headers=th).json()
    assert got['sourceText'] == source and got['closureTraining'] == homework
    assert all(f'{i}.第{i}题：' in got['closureTraining'] for i in range(1,6))
    assert got['examples'] == [example] and got['ppt'] == [slide]
    # Saving the editable summary must not trim homework or erase the original document.
    r=client.put(url,headers=th,json={'title':got['title'],'coreTarget':got['coreTarget'],'teacherPlan':got['teacherPlan'],
        'closureTraining':got['closureTraining'],'examples':got['examples'],'ppt':got['ppt']})
    assert r.status_code == 200,r.text
    after=client.get(url,headers=th).json()
    assert after['sourceText'] == source and after['closureTraining'] == homework
    assert after['examples'] == [example] and after['ppt'] == [slide]
    assert client.get(url,headers=sh).status_code == 403
    # Over-limit paste is explicitly refused before calling AI; no partial overwrite.
    r=client.post('/teacher/weekend/lessons/import',headers=th,data={'subject':'语文','lessonNo':'17','force':'1','text':'x'*200001})
    assert r.status_code == 413, (r.status_code,r.text)
    assert client.get(url,headers=th).json() == after
    page=client.get('/v1/weekend-plan').text
    assert '导入原文（含阅读文章、全部题目，完整保留）' in page and 'source.value=L.sourceText' in page
    assert '教案已保存，已核对服务器内容' in page and 'box.appendChild(saveStatus)' in page
    print('OK')
''')


def test_import_does_not_silently_clip_text_or_slide_content():
    import io
    import zipfile
    import pytest
    from changying.services.lesson_import import MAX_TEXT_CHARS, extract

    original = '原文' * 8000 + '最后第五题'
    assert extract('.txt', original.encode())['text'] == original
    with pytest.raises(ValueError):
        extract('.txt', ('字' * (MAX_TEXT_CHARS + 1)).encode())
    buf = io.BytesIO()
    slide = '页面正文' * 300 + '页面末尾'
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('ppt/slides/slide1.xml', '<a:t>' + slide + '</a:t>')
    assert extract('.pptx', buf.getvalue())['slides'] == [slide]


def test_textarea_grows_on_initial_display_and_after_edit():
    from changying.web.weekend_pages import COMMON_JS

    source = COMMON_JS.split('var el=')[0].replace('__PAGE_AUTH__', '')
    script = source + r'''
const assert = require('node:assert/strict');
let field={isConnected:true,style:{},scrollHeight:500};growTextarea(field);
assert.equal(field.style.height,'502px');assert.equal(field.style.overflowY,'hidden');
field.scrollHeight=1000;growTextarea(field);assert.equal(field.style.height,'1002px');
console.log('OK');
'''
    result = subprocess.run(['node', '-e', script], text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
