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


def docx_with_picture() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", "<w:document><w:p><w:r><w:t>第10课 教案</w:t></w:r></w:p></w:document>")
        z.writestr("word/media/image1.jpg", JPEG)
    return buf.getvalue()


def test_a_word_lesson_keeps_the_pictures_inside_it():
    got = lesson_import.extract(".docx", docx_with_picture())

    assert "第10课" in got["text"]
    assert len(got["images"]) == 1
    assert got["images"][0]["data_url"].startswith("data:image/jpeg;base64,")


def test_pictures_map_back_to_the_question_the_model_named():
    figure = {"type": "uploaded_image", "data_url": "data:image/jpeg;base64," + "A" * 40, "alt": "原卷插图"}
    data = {"questions": [
        {"stem": "一个两位数，十位是 m，个位是 n，这个两位数是？", "options": ["mn", "m+n", "10m+n"], "correctIndex": 2,
         "explanation": "", "knowledge": "位值", "figureImage": 1},
        {"stem": "下面说法正确的是？", "options": ["A", "B"], "correctIndex": 0, "explanation": "", "knowledge": "判断"},
    ]}
    _attach_figures(data, [{"page": 3, "data_url": figure["data_url"]}])

    qs = _valid_questions(data["questions"])
    assert len(qs) == 2
    assert qs[0]["fig"]["data_url"] == figure["data_url"]
    assert qs[1]["fig"] == {}


def test_an_out_of_range_image_number_is_ignored_and_bad_urls_are_dropped():
    data = {"questions": [{"stem": "题目", "options": ["A", "B"], "correctIndex": 0, "figureImage": 9}]}
    _attach_figures(data, [{"page": 1, "data_url": "data:image/jpeg;base64," + "A" * 40}])
    assert "figure" not in data["questions"][0]

    assert _question_figure({"type": "uploaded_image", "data_url": "https://example.com/x.jpg"}) == {}
    assert _question_figure({"type": "geometry"}) == {}


def test_the_weekend_page_renders_the_imported_picture():
    from changying.web.weekend_pages import COMMON_JS, PLAN_JS

    for script in (COMMON_JS, PLAN_JS):
        assert "questionFigureImg" in script, "both the 审改 page and the student page must show it"
    assert "data:image\\/jpeg;base64," in COMMON_JS


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
    figure = {"type": "uploaded_image", "data_url": FIG_URL, "alt": "原卷插图"}
    with Session(engine) as db:
        replace_written_drafts(db, table, 1, 2, 3, [
            {"stem": "第7题：方桌人数规律", "reference": "答案", "hints": [], "type": "short_answer", "figure": figure}])
        db.commit()
        row = db.execute(select(table)).first()
    assert json.loads(row.hints_json)["figure"]["data_url"] == FIG_URL


def test_courseware_uses_the_imported_picture_instead_of_a_drawing():
    figures = [{"number": 7, "key": "第7题方桌人数规律", "figure": {"type": "uploaded_image", "data_url": FIG_URL, "alt": "原卷插图"}}]

    # The screen labels the page “第 7 题 …”; the stem may use different separators, so the number decides.
    assert match_figure(figures, "第 7 题 原题｜方桌人数规律 1 张方桌坐 4 人")["data_url"] == FIG_URL
    assert match_figure(figures, "第 3 题 平方与乘 2") == {}


def test_the_courseware_screen_can_show_an_imported_picture():
    from changying.web.weekend_courseware_pages import COURSEWARE_JS

    assert "uploaded_image" in COURSEWARE_JS

