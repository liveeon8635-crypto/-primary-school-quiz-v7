from __future__ import annotations

import io
import zipfile

from changying.services import lesson_import
from changying.web.weekend_plan_views import _attach_figures, _question_figure, _valid_questions

# Smallest readable JPEG header/trailer pair; the extractor only needs the magic bytes.
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32 + b"\xff\xd9"


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
