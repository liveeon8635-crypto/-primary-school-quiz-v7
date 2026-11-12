"""Regression checks: measurement diagrams must keep an independently verifiable source image."""
from changying.web.weekend_courseware import (
    attach_original_figure,
    match_figure,
    requires_original_geometry_image,
)


def test_measurement_geometry_requires_original_scan():
    question = "第5题：想办法求出下面各个平行四边形的面积，先在图上画高，再用直尺测量底和对应的高"
    assert requires_original_geometry_image(question)
    assert not requires_original_geometry_image("平行四边形的面积公式是什么？")
    assert not requires_original_geometry_image("测量一段绳子的长度")


def test_scan_can_be_restored_after_generation_without_replacing_teaching_figure():
    original = {"type": "uploaded_image", "data_url": "data:image/jpeg;base64,QUJD"}
    data = {"figure": {"type": "shape", "shape": "parallelogram"}, "sourceFigure": {}}
    figures = [{"number": 5, "key": "平行四边形", "figure": original}]
    fixed = attach_original_figure(data, figures, "第5题 画高测量")
    assert fixed["sourceFigure"] == original
    assert fixed["figure"] == data["figure"]
    assert data["sourceFigure"] == {}


def test_ambiguous_scan_match_must_not_guess():
    a = {"type": "uploaded_image", "data_url": "one"}
    b = {"type": "uploaded_image", "data_url": "two"}
    figures = [
        {"number": 5, "key": "first", "figure": a},
        {"number": 5, "key": "second", "figure": b},
    ]
    assert match_figure(figures, "第5题 画高测量") == {}
    assert attach_original_figure({"figure": {}}, figures, "第5题 画高测量") == {}


def test_existing_source_is_not_overwritten():
    original = {"type": "uploaded_image", "data_url": "old"}
    saved = {"sourceFigure": original, "figure": {"type": "shape"}}
    assert attach_original_figure(saved, [], "第5题 画高测量") is saved
