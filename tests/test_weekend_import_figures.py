from __future__ import annotations

import io
import zipfile

from changying.services import lesson_import
from changying.services.lesson_written import replace_written_drafts, template_meta, valid_written_questions
from changying.web.weekend_courseware import match_figure
from changying.web.weekend_plan_views import _attach_figures, _question_figure, _valid_questions

# Smallest readable JPEG header/trailer pair; the extractor only needs the magic bytes.
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32 + b"\xff\xd9"
FIG_URL = "data:image/jpeg;base64," + "A" * 40
PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 40


def docx_with_picture() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", "<w:document><w:p><w:r><w:t>第10课 教案</w:t></w:r></w:p></w:document>")
        z.writestr("word/media/image1.jpg", JPEG)
    return buf.getvalue()


def docx_with_png(payload: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", "<w:document><w:p><w:r><w:t>阅读文章</w:t></w:r></w:p></w:document>")
        z.writestr("word/media/image1.png", payload)
    return buf.getvalue()


def test_a_word_lesson_keeps_the_pictures_inside_it():
    got = lesson_import.extract(".docx", docx_with_picture())

    assert "第10课" in got["text"]
    assert len(got["images"]) == 1
    assert got["images"][0]["data_url"].startswith("data:image/jpeg;base64,")


def test_a_word_lesson_keeps_small_png_pictures_and_reports_oversized_ones():
    def docx_with_png(payload: bytes) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("[Content_Types].xml", "<Types/>")
            z.writestr("word/document.xml", "<w:document><w:p><w:r><w:t>阅读文章</w:t></w:r></w:p></w:document>")
            z.writestr("word/media/image1.png", payload)
        return buf.getvalue()

    small = lesson_import.extract(".docx", docx_with_png(PNG))
    assert len(small["images"]) == 1
    assert small["images"][0]["data_url"].startswith("data:image/png;base64,")
    assert small["omittedImages"] == 0

    large = lesson_import.extract(".docx", docx_with_png(b"\x89PNG\r\n\x1a\n" + b"x" * 800_000))
    assert large["images"] == [] and large["omittedImages"] == 1


def test_large_valid_docx_picture_gets_a_bounded_review_preview_with_source_hash():
    import hashlib
    import random
    from PIL import Image

    pixels = Image.new("RGB", (600, 600))
    rng = random.Random(12)
    pixels.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(600 * 600)])
    source = io.BytesIO()
    pixels.save(source, format="PNG", optimize=False)
    original = source.getvalue()
    assert len(original) > 450_000

    got = lesson_import.extract(".docx", docx_with_png(original))

    assert len(got["images"]) == 1 and got["omittedImages"] == 0
    image = got["images"][0]
    assert image["data_url"].startswith("data:image/jpeg;base64,")
    assert len(image["data_url"]) <= lesson_import.MAX_FIGURE_CHARS
    assert image["source_name"] == "image1.png"
    assert image["source_sha256"] == hashlib.sha256(original).hexdigest()
    assert image["source_format"] == "png"


def test_unsupported_and_corrupt_docx_media_are_counted_as_omitted():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", "<w:document><w:p><w:r><w:t>正文</w:t></w:r></w:p></w:document>")
        z.writestr("word/media/image1.gif", b"GIF89a")
        z.writestr("word/media/image2.jpg", b"invalid-jpeg")
    result = lesson_import.extract(".docx", buf.getvalue())
    assert result["images"] == []
    assert result["omittedImages"] == 2


def test_model_image_indexes_are_ignored_and_text_geometry_selects_the_picture():
    image7 = "data:image/jpeg;base64," + "A" * 40
    image8 = "data:image/jpeg;base64," + "B" * 40
    source7 = "第 7 题 方桌人数规律 1 张方桌可坐 8 人，2 张方桌拼在一起可坐 12 人。"
    source8 = "第 8 题 连续正方形与小棒 摆 1 个正方形用 4 根小棒，摆 2 个用 7 根。"
    data = {"questions": [
        {"stem": "方桌人数规律 1 张方桌可坐 8 人，2 张方桌拼在一起可坐 12 人。", "options": ["A", "B"], "correctIndex": 0, "figureImage": 2},
        {"stem": "连续正方形与小棒 摆 1 个正方形用 4 根小棒，摆 2 个用 7 根。", "options": ["A", "B"], "correctIndex": 0, "figureImage": 1},
    ]}
    figures = [
        {"page": 3, "question_no": 7, "question_source_text": source7, "data_url": image7},
        {"page": 3, "question_no": 8, "question_source_text": source8, "data_url": image8},
    ]

    assert _attach_figures(data, figures) == 2
    qs = _valid_questions(data["questions"])
    assert qs[0]["fig"]["data_url"] == image7
    assert qs[1]["fig"]["data_url"] == image8


def test_picture_is_not_attached_when_question_text_or_source_geometry_is_ambiguous():
    data = {"questions": [
        {"stem": "另一道不相关的题目内容", "options": ["A", "B"], "correctIndex": 0, "figureImage": 1,
         "figure": {"type": "uploaded_image", "data_url": FIG_URL}},
    ]}
    figures = [
        {"page": 3, "question_no": None, "question_source_text": "", "data_url": FIG_URL},
        {"page": 3, "question_no": 7, "question_source_text": "原题：方桌人数规律，有 8 人和 12 人", "data_url": FIG_URL},
    ]

    assert _attach_figures(data, figures) == 0
    assert "figure" not in data["questions"][0]


def test_an_out_of_range_image_number_is_ignored_and_bad_urls_are_dropped():
    data = {"questions": [{"stem": "题目", "options": ["A", "B"], "correctIndex": 0, "figureImage": 9}]}
    _attach_figures(data, [{"page": 1, "data_url": "data:image/jpeg;base64," + "A" * 40}])
    assert "figure" not in data["questions"][0]

    assert _question_figure({"type": "uploaded_image", "data_url": "https://example.com/x.jpg"}) == {}
    assert _question_figure({"type": "geometry"}) == {}


def test_pdf_images_are_matched_by_their_position_inside_a_numbered_question():
    from types import SimpleNamespace

    class Image:
        def get(self, key):
            return {"/Subtype": "/Image", "/Filter": "/DCTDecode"}.get(key)

        def get_object(self):
            return self

        def get_data(self):
            return JPEG

    class Page(dict):
        mediabox = SimpleNamespace(height=100)

        def extract_text(self, visitor_operand_before=None, visitor_text=None):
            if visitor_text:
                for x, part, y in ((0, "第", 10), (10, "7", 10), (20, "题", 10), (0, "第 8 题", 70)):
                    visitor_text(part, None, [1, 0, 0, 1, x, y], None, 10)
            if visitor_operand_before:
                visitor_operand_before(b"Do", ["/pic"], [10, 0, 0, 10, 10, 80], None)

    page = Page({"/Resources": {"/XObject": {"/pic": Image()}}})
    page_text = "第 7 题 原题：方桌人数规律\n第 8 题 原题：连续正方形与小棒"
    regions = lesson_import._pdf_question_regions(page, page_text)
    figures = lesson_import._pdf_page_figures(page, 3, regions)

    assert [(r["question_no"], r["source_text"]) for r in regions] == [
        (7, "第 7 题 原题：方桌人数规律"), (8, "第 8 题 原题：连续正方形与小棒")]
    assert len(figures) == 1
    assert figures[0]["question_no"] == 7
    assert figures[0]["page"] == 3


def test_the_weekend_page_renders_the_imported_picture():
    from changying.web.weekend_pages import COMMON_JS, PLAN_JS

    for script in (COMMON_JS, PLAN_JS):
        assert "questionFigureImg" in script, "both the review page and the student page must show it"
    assert "data:image\\/(jpeg|png);base64," in COMMON_JS


def test_chinese_workbench_exposes_teacher_only_material_review():
    from changying.web.weekend_pages import PLAN_JS
    from changying.web.weekend_plan_views import ImportedMaterialReviewBody

    assert "导入素材审核" in PLAN_JS
    assert "reviewImportedMaterials(r,detail,refreshRow)" in PLAN_JS
    assert "api('/teacher/weekend/lessons/'+r.lessonId+'/imported-materials')" in PLAN_JS
    assert "expectedRevision" in ImportedMaterialReviewBody.model_fields


def test_material_review_uses_authenticated_page_api_and_saves_revision():
    import json
    import subprocess
    from changying.web.weekend_pages import PLAN_JS

    review = PLAN_JS.split("  function reviewImportedMaterials(", 1)[1].split("  function startReason(", 1)[0]
    script = r'''
const assert=require('assert');
let calls=[], saved=null, refreshed=null;
function el(tag,attrs,...children){let n={tag,attrs:attrs||{},children:children.filter(Boolean),value:(attrs||{}).value||'',textContent:(attrs||{}).text||'',disabled:false,events:{},appendChild(c){this.children.push(c)},addEventListener(k,f){this.events[k]=f}};return n}
function questionFigureImg(fig){return el('img',{src:fig.data_url})}
function api(path,opts){calls.push({path,opts});if(opts){saved=opts.json;return Promise.resolve({})}if(path.includes('schedule?'))return Promise.resolve({items:[{lessonId:12,pendingMaterials:0}]});return Promise.resolve({items:[{id:4,sourceFile:'teacher.docx',sourcePart:'image1.png',sourceSha256:'abc',status:'pending',dataUrl:'data:image/png;base64,AAAA',sortOrder:1,revision:3}]})}
const SUBJ='语文';
''' + "function reviewImportedMaterials(" + review + r'''
let box=el('div',{});reviewImportedMaterials({lessonId:12,courseType:'reading'},box,function(x){refreshed=x});
setTimeout(function(){let card=box.children[2].children[0],row=card.children[3];let confirm=row.children[3];confirm.events.click();setTimeout(function(){assert.equal(calls[0].path,'/teacher/weekend/lessons/12/imported-materials');assert.equal(saved.status,'confirmed');assert.equal(saved.expectedRevision,3);assert.equal(refreshed.pendingMaterials,0);console.log('OK')},0)},0);
'''
    result = subprocess.run(["node", "-e", script], text=True, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_a_written_question_keeps_its_picture_in_the_stored_metadata():
    import json

    from sqlalchemy import Column, Integer, MetaData, Table, Text, create_engine, select
    from sqlalchemy.orm import Session

    md = MetaData()
    table = Table("written_probe", md,
                  Column("id", Integer, primary_key=True), Column("school_id", Integer), Column("teacher_id", Integer),
                  Column("lesson_id", Integer), Column("session_id", Integer), Column("stem", Text),
                  Column("reference", Text), Column("hints_json", Text))
    engine = create_engine("sqlite://")
    md.create_all(engine)
    figure = {"type": "uploaded_image", "data_url": FIG_URL, "alt": "原卷插图", "question_no": 13}
    with Session(engine) as db:
        replace_written_drafts(db, table, 1, 2, 3, [
            {"stem": "第7题：方桌人数规律", "reference": "答案", "hints": [], "type": "short_answer", "figure": figure}])
        db.commit()
        row = db.execute(select(table)).first()
    assert json.loads(row.hints_json)["figure"]["data_url"] == FIG_URL
    assert json.loads(row.hints_json)["figure"]["question_no"] == 13


def test_courseware_uses_the_imported_picture_instead_of_a_drawing():
    figures = [{"number": 7, "key": "第7题方桌人数规律", "figure": {"type": "uploaded_image", "data_url": FIG_URL, "alt": "原卷插图"}}]

    # The screen labels the page “第 7 题 …”; the stem may use different separators, so the number decides.
    assert match_figure(figures, "第 7 题 原题｜方桌人数规律 1 张方桌坐 4 人")["data_url"] == FIG_URL
    assert match_figure(figures, "第 3 题 平方与乘 2") == {}


def test_the_courseware_screen_can_show_an_imported_picture():
    from changying.web.weekend_courseware_pages import COURSEWARE_JS

    assert "uploaded_image" in COURSEWARE_JS


def test_pdf_verified_question_number_survives_storage_and_courseware_rewording():
    import json
    from types import SimpleNamespace
    from sqlalchemy import Column, Integer, MetaData, Table, Text
    from sqlalchemy.orm import registry

    from changying.services.lesson_written import valid_written_questions
    from changying.web.weekend_courseware import lesson_figures, match_figure
    from changying.web.weekend_plan_views import _attach_figures

    figure = {
        "page": 5,
        "question_no": 13,
        "question_source_text": "\u7b2c13\u9898 \u6708\u5386\u5341\u5b57\u6846\u4e2d\u7684\u5b57\u6bcd\u8868\u793a\u4e0e\u6c42\u503c\uff1a\u7528\u5341\u5b57\u6846\u5728\u6708\u5386\u4e2d\u6846\u51fa\u4e94\u4e2a\u6570\u3002",
        "data_url": FIG_URL,
    }
    data = {"writtenQuestions": [{
        "stem": "\u7528\u5341\u5b57\u6846\u5728\u6708\u5386\u4e2d\u6846\u51fa\u4e94\u4e2a\u6570\u3002",
        "figureImage": 8,
    }]}
    assert _attach_figures(data, [figure]) == 1
    written = valid_written_questions(data["writtenQuestions"])
    saved_figure = written[0]["figure"]
    assert saved_figure["question_no"] == 13

    metadata = MetaData()
    questions = Table("question_probe", metadata, Column("id", Integer, primary_key=True),
                      Column("lesson_id", Integer), Column("stage", Text))
    mapper = registry()

    class TeachingQuestion:
        pass

    mapper.map_imperatively(TeachingQuestion, questions)
    written_table = Table("written_probe", metadata, Column("id", Integer, primary_key=True),
                          Column("lesson_id", Integer), Column("session_id", Integer), Column("hints_json", Text))

    class Result:
        def __init__(self, rows):
            self.rows = rows

        def all(self):
            return self.rows

    class DB:
        def scalars(self, _statement):
            return Result([])

        def execute(self, _statement):
            return Result([SimpleNamespace(hints_json=json.dumps({"figure": saved_figure}),
                                           stem="AI rewritten title without a question number")])

    candidates = lesson_figures(SimpleNamespace(TeachingQuestion=TeachingQuestion), DB(),
                                SimpleNamespace(id=3), written_table)
    assert candidates[0]["number"] == 13
    assert match_figure(candidates, "\u7b2c 13 \u9898 \u6708\u5386\u5341\u5b57\u6846\u4e2d\u7684\u5b57\u6bcd\u8868\u793a\u4e0e\u6c42\u503c")["data_url"] == FIG_URL


def test_courseware_writing_image_gallery_links_to_material_review():
    from changying.web.weekend_courseware_pages import COURSEWARE_JS
    assert "作文素材与审核" in COURSEWARE_JS
    assert "/v1/weekend-writing?lesson=" in COURSEWARE_JS
    assert "尚未确认" in COURSEWARE_JS
