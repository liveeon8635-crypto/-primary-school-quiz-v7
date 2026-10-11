"""Photo/screenshot text recognition for the after-school homework assistant.

Independent of the school AI settings and of the legacy model-name alias table
(``AI_DEEPSEEK_LEGACY_MODEL_ALIASES``): the model name configured here is sent exactly as given.
Everything comes from environment variables, so no key ever lives in the repository:

    HOMEWORK_VISION_PROVIDER   openai_compatible (default) | openai_responses
    HOMEWORK_VISION_BASE_URL   e.g. https://api.deepseek.com
    HOMEWORK_VISION_MODEL      model name, used verbatim
    HOMEWORK_VISION_API_KEY    secret, never logged

The image only ever exists in memory: it is never written to disk or the database and never
logged. Only length/token/latency metadata is recorded in ``ai_usage_logs``.
"""

from __future__ import annotations

import base64
import os
import re
import time
from typing import Any

import requests
from fastapi import HTTPException
from starlette.requests import Request

MAX_IMAGE_BYTES = 6 * 1024 * 1024
VISION_TIMEOUT_SECONDS = 25
VISION_PROVIDERS = ("openai_compatible", "openai_responses")

RECOGNIZE_PROMPT = (
    "请识别图片中的文字，只输出一个 JSON 对象，不要任何解释，格式："
    '{"text":"识别出的全部文字（题目或作业通知，保持原有顺序，公式用普通字符书写）",'
    '"hasFigure":图片中是否含有几何图形或示意图（true/false）,'
    '"confidence":0到1之间的小数，表示你对识别结果的把握}\n'
    "忽略聊天头像、昵称、手机号、人名、学号等与题目或作业无关的信息；看不清的地方不要猜。"
)


async def read_image_body(request: Request, limit: int = MAX_IMAGE_BYTES) -> bytes:
    """The picture is the raw request body (``Content-Type: image/jpeg``), never a multipart upload.

    A multipart upload makes the web framework spool anything over ~1 MB into a temporary file on
    disk, which would break the promise that the photo is never written anywhere. Reading the body
    ourselves keeps it in memory only, and the size limit is enforced while it streams in.
    """
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        raise HTTPException(413, "图片太大，请重新拍一张")
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise HTTPException(413, "图片太大，请重新拍一张")
        chunks.append(chunk)
    return b"".join(chunks)


def _sniff_mime(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return ""


def vision_config() -> dict[str, str] | None:
    """The configuration from the environment, or None when recognition is not configured."""
    provider = (os.getenv("HOMEWORK_VISION_PROVIDER") or "openai_compatible").strip()
    base = (os.getenv("HOMEWORK_VISION_BASE_URL") or "").strip().rstrip("/")
    model = (os.getenv("HOMEWORK_VISION_MODEL") or "").strip()
    key = (os.getenv("HOMEWORK_VISION_API_KEY") or "").strip()
    if provider not in VISION_PROVIDERS or not (base and model and key):
        return None
    return {"provider": provider, "base_url": base, "model": model, "api_key": key}


def vision_enabled() -> bool:
    return vision_config() is not None


def _usage(provider: str, data: Any) -> tuple[int, int]:
    usage = (data or {}).get("usage") if isinstance(data, dict) else None
    usage = usage or {}
    if provider == "openai_responses":
        return int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)
    return int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)


def recognize_image(
    implementation: Any,
    db: Any,
    user: Any,
    image: bytes,
    *,
    feature: str,
    timeout: int = VISION_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Recognise text in one image. Returns ``{"text", "hasFigure", "confidence"}``."""
    config = vision_config()
    if config is None:
        raise HTTPException(503, "拍照识别尚未配置，请直接输入文字")
    if not image:
        raise HTTPException(400, "没有收到图片")
    if len(image) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "图片太大，请重新拍一张")
    mime = _sniff_mime(image)
    if not mime:
        raise HTTPException(415, "只支持 JPG、PNG、WebP 图片")
    base = implementation._validate_ai_base_url(config["base_url"], runtime=True)
    data_uri = f"data:{mime};base64,{base64.b64encode(image).decode('ascii')}"
    del image
    provider, model = config["provider"], config["model"]
    headers = {"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"}
    started = time.time()
    status, error, out, data = "ok", "", "", {}
    try:
        if provider == "openai_responses":
            payload = {
                "model": model,
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": RECOGNIZE_PROMPT},
                            {"type": "input_image", "image_url": data_uri},
                        ],
                    }
                ],
            }
            response = requests.post(base + "/responses", headers=headers, json=payload, timeout=timeout)
        else:
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": RECOGNIZE_PROMPT},
                            {"type": "image_url", "image_url": {"url": data_uri}},
                        ],
                    }
                ],
                "temperature": 0,
            }
            response = requests.post(base + "/chat/completions", headers=headers, json=payload, timeout=timeout)
        try:
            data = response.json()
        except Exception:
            data = {}
        if not response.ok:
            code = ""
            err = data.get("error") if isinstance(data, dict) else None
            if isinstance(err, dict):
                raw_code = str(err.get("code") or err.get("type") or "")
                code = raw_code if re.fullmatch(r"[A-Za-z0-9_.-]{1,60}", raw_code) else ""
            raise HTTPException(502, f"识别服务暂时不可用（{response.status_code}{' ' + code if code else ''}），请直接输入文字")
        out = implementation._ai_extract_text(data)
        if not out:
            raise HTTPException(502, "识别服务没有返回内容，请重拍或直接输入文字")
        try:
            parsed = implementation._ai_json(out)
        except HTTPException:
            parsed = {"text": out, "confidence": None}
        if not isinstance(parsed, dict):
            parsed = {"text": out, "confidence": None}
        text = str(parsed.get("text") or "").strip()
        if not text:
            raise HTTPException(422, "没有识别出文字，请重拍或直接输入")
        try:
            confidence = float(parsed.get("confidence")) if parsed.get("confidence") is not None else None
        except (TypeError, ValueError):
            confidence = None
        return {
            "text": text[:4000],
            "hasFigure": bool(parsed.get("hasFigure")),
            "confidence": confidence,
        }
    except HTTPException as exc:
        status, error = "error", str(exc.detail)
        raise
    except requests.Timeout:
        status, error = "error", "timeout"
        raise HTTPException(504, "识别服务响应超时，请稍后重试或直接输入文字")
    except requests.RequestException:
        status, error = "error", "network"
        raise HTTPException(502, "无法连接识别服务，请稍后重试或直接输入文字")
    finally:
        in_tokens, out_tokens = _usage(provider, data)
        db.add(
            implementation.AIUsageLog(
                school_id=user.school_id,
                user_id=user.id,
                feature=feature,
                provider=provider,
                model=model,
                status=status,
                prompt_chars=len(RECOGNIZE_PROMPT),
                output_chars=len(out),
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                latency_ms=int((time.time() - started) * 1000),
                error=error[:1000],
            )
        )
        try:
            db.commit()
        except Exception:
            db.rollback()


__all__ = ["MAX_IMAGE_BYTES", "read_image_body", "recognize_image", "vision_config", "vision_enabled"]
