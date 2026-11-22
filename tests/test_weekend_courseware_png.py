"""Tests for lossless PNG support in weekend courseware, backup, and Word handouts."""
import base64
import io
import zipfile

import pytest
from fastapi import HTTPException
from PIL import Image

from changying.services.weekend_backup import _uploaded_figure
from changying.services.weekend_courseware import clean_figure
from changying.services.weekend_handouts import _figure_image, question_document


def _sample_png_data_url(width: int = 320, height: int = 180) -> str:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (240, 248, 255)).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def test_clean_figure_accepts_png_and_rejects_svg():
    url = _sample_png_data_url()
    cleaned = clean_figure({"type": "uploaded_image", "data_url": url, "alt": "梯形高清图"})
    assert cleaned == {"type": "uploaded_image", "data_url": url, "alt": "梯形高清图"}

    with pytest.raises(ValueError, match="原卷图片格式不正确"):
        clean_figure({"type": "uploaded_image", "data_url": "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4="})


def test_weekend_backup_accepts_valid_png_and_rejects_corrupt_png():
    url = _sample_png_data_url()
    cleaned = _uploaded_figure({"type": "uploaded_image", "data_url": url, "alt": "高清几何图"})
    assert cleaned["data_url"] == url

    bad_png = "data:image/png;base64," + base64.b64encode(b"not-a-real-png").decode("ascii")
    with pytest.raises(HTTPException) as exc:
        _uploaded_figure({"type": "uploaded_image", "data_url": bad_png})
    assert exc.value.status_code == 409


def test_weekend_handouts_embeds_png_in_docx():
    url = _sample_png_data_url(1920, 1016)
    img = _figure_image({"type": "uploaded_image", "data_url": url, "alt": "高清课件图"})
    assert img is not None
    assert img["ext"] == "png"
    assert img["cx"] > img["cy"]

    material = {
        "sessionId": 1,
        "version": "v1",
        "title": "第12课随堂练习",
        "lesson": {"core_target": "梯形面积"},
        "questions": [
            {
                "kind": "written",
                "points": 10,
                "stem": "求梯形面积。",
                "figure": {"type": "uploaded_image", "data_url": url, "alt": "高清课件图"},
                "reference": "25 cm²",
                "explanation": "(4+6)×5÷2=25",
            }
        ],
    }
    docx_bytes = question_document(material, "student")
    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as zf:
        names = set(zf.namelist())
        assert "word/media/image1.png" in names
        content_types = zf.read("[Content_Types].xml").decode("utf-8")
        assert 'Extension="png" ContentType="image/png"' in content_types
