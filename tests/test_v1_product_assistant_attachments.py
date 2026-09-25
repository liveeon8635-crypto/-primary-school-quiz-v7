import base64

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import app
from changying.web.v1_product_assistant import (
    ProductAssistantAttachment,
    _attachment_context_and_images,
)


def _data_url(mime_type: str, raw: bytes) -> str:
    return f"data:{mime_type};base64,{base64.b64encode(raw).decode('ascii')}"


def test_product_assistant_attachment_button_and_supported_types_render():
    html = TestClient(app).get("/v1").text

    assert 'id="cy-pa-attach"' in html
    assert 'id="cy-pa-file-input"' in html
    assert "添加照片或文件" in html
    assert "image/jpeg,image/png,image/webp,.txt,.md,.pdf,.docx,.pptx" in html
    assert "pendingAttachments.length>=3" in html
    assert "file.size>5*1024*1024" in html
    assert "{question:text,attachments,...askContext}" in html


def test_text_attachment_becomes_ephemeral_prompt_context():
    attachment = ProductAssistantAttachment(
        name="说明.txt",
        mime_type="text/plain",
        data_url=_data_url("text/plain", "这是一份课堂说明。".encode("utf-8")),
    )

    context, images = _attachment_context_and_images([attachment])

    assert "【文件附件：说明.txt】" in context
    assert "这是一份课堂说明。" in context
    assert images == []


def test_image_attachment_is_forwarded_as_model_image_without_persistence():
    data_url = _data_url("image/png", b"not-a-real-image-but-bounded-test-bytes")
    attachment = ProductAssistantAttachment(
        name="截图.png",
        mime_type="image/png",
        data_url=data_url,
    )

    context, images = _attachment_context_and_images([attachment])

    assert "【图片附件：截图.png】" in context
    assert images == [data_url]


def test_attachment_type_mismatch_is_rejected():
    attachment = ProductAssistantAttachment(
        name="截图.png",
        mime_type="image/jpeg",
        data_url=_data_url("image/png", b"bounded"),
    )

    try:
        _attachment_context_and_images([attachment])
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "类型与内容不一致" in str(exc.detail)
    else:
        raise AssertionError("mismatched attachment type must be rejected")


def test_unsupported_attachment_extension_is_rejected():
    attachment = ProductAssistantAttachment(
        name="脚本.exe",
        mime_type="application/octet-stream",
        data_url=_data_url("application/octet-stream", b"bounded"),
    )

    try:
        _attachment_context_and_images([attachment])
    except HTTPException as exc:
        assert exc.status_code == 415
        assert "暂不支持这种文件" in str(exc.detail)
    else:
        raise AssertionError("unsupported attachment type must be rejected")
