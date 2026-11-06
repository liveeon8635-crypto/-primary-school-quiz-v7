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
import time
from typing import Any

import requests
from fastapi import HTTPException
from starlette.requests import Request

MAX_IMAGE_BYTES = 6 * 1024 * 1024
VISION_TIMEOUT_SECONDS = 25
# 识别文本上限：超过会被截断，调用方据此提示老师核对
RECOGNIZED_CHAR_LIMIT = 4000
VISION_PROVIDERS = ("openai_compatible", "openai_responses")

# Only these fixed categories may cross into classroom messages or runtime logs.
VISION_FAILURE_MESSAGES = {
    "upstream_auth": "识别服务验证失败（401），请管理员检查识别授权；仍可手工批改",
    "upstream_billing": "识别服务返回计费限制（402），请管理员核查额度；仍可手工批改",
    "upstream_forbidden": "识别服务拒绝访问（403），请管理员核查服务权限；仍可手工批改",
    "upstream_not_found": "识别接口或模型未找到（404），请管理员核查设置；仍可手工批改",
    "upstream_request": "识别请求被服务商拒绝，请管理员核查接口与模型设置；仍可手工批改",
    "upstream_busy": "识别服务商限流（429），请稍后重试；仍可手工批改",
    "upstream_server": "识别服务商返回服务器错误，请稍后重试；仍可手工批改",
    "upstream_error": "识别服务返回异常状态，请稍后重试；仍可手工批改",
    "network": "无法连接识别服务，请稍后重试；仍可手工批改",
    "timeout": "本次识别超时，请重试；仍可手工批改",
    "empty_response": "识别服务未返回内容，请稍后重试；仍可手工批改",
    "unreadable_response": "识别结果没有可读取的文字，请核对照片或手工批改",
    "invalid_transcription": "识别结果格式不符合预批要求，请重试或手工批改",
}


class VisionFailure(HTTPException):
    """HTTP-compatible failure with fixed, safe diagnostic categories."""

    def __init__(self, status_code: int, detail: str, reason: str, upstream_status: int | None = None):
        if reason not in VISION_FAILURE_MESSAGES:
            raise ValueError("Unknown recognition failure category")
        super().__init__(status_code, detail)
        self.reason = reason
        self.upstream_status = upstream_status if isinstance(upstream_status, int) and 100 <= upstream_status <= 599 else None

RECOGNIZE_PROMPT = (
    "请识别图片中的文字，只输出一个 JSON 对象，不要任何解释，格式："
    '{"text":"识别出的全部文字（题目或作业通知，保持原有顺序，公式用普通字符书写）",'
    '"hasFigure":图片中是否含有几何图形或示意图（true/false）,'
    '"confidence":0到1之间的小数，表示你对识别结果的把握}\n'
    "忽略聊天头像、昵称、手机号、人名、学号等与题目或作业无关的信息；看不清的地方不要猜。"
)

# The student photographs one question: keep that question only, not the page around it.
QUESTION_PROMPT = (
    "图片是学生拍下的一道作业题。请只识别学生要问的这一道题，只输出一个 JSON 对象，不要任何解释，格式："
    '{"text":"这一道题的完整题目文字（题干、选项；阅读理解则包含文章和这道题的提问；公式用普通字符书写）",'
    '"hasFigure":这道题是否含有几何图形或示意图（true/false）,'
    '"confidence":0到1之间的小数，表示你对识别结果的把握}\n'
    "如果图片里有好几道题，只取位于画面中央、最完整的那一道，其余题目不要识别。"
    "不要识别页眉页脚、页码、书名、栏目标题、批改痕迹、学生手写的答案和草稿、手机号、人名、学号、聊天头像和昵称。"
    "看不清的地方不要猜。"
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
    prompt: str = RECOGNIZE_PROMPT,
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
                            {"type": "input_text", "text": prompt},
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
                            {"type": "text", "text": prompt},
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
            upstream = response.status_code
            reason = {401: "upstream_auth", 402: "upstream_billing", 403: "upstream_forbidden",
                      404: "upstream_not_found", 400: "upstream_request", 422: "upstream_request",
                      429: "upstream_busy"}.get(upstream, "upstream_server" if 500 <= upstream <= 599 else "upstream_error")
            # Never expose provider error strings, even if they resemble short codes.
            raise VisionFailure(502, f"识别服务暂时不可用（{upstream}），请直接输入文字", reason, upstream)
        out = implementation._ai_extract_text(data)
        if not out:
            raise VisionFailure(502, "识别服务没有返回内容，请重拍或直接输入文字", "empty_response")
        try:
            parsed = implementation._ai_json(out)
        except (HTTPException, ValueError):
            raise VisionFailure(502, "识别结果格式异常或可能不完整，请核对重拍或直接输入文字", "invalid_transcription") from None
        if not isinstance(parsed, dict):
            raise VisionFailure(502, "识别结果格式异常或可能不完整，请核对重拍或直接输入文字", "invalid_transcription")
        raw_text = str(parsed.get("text") or "").strip()
        if not raw_text:
            raise VisionFailure(422, "没有识别出文字，请重拍或直接输入", "unreadable_response")
        try:
            confidence = float(parsed.get("confidence")) if parsed.get("confidence") is not None else None
        except (TypeError, ValueError):
            confidence = None
        truncated = len(raw_text) >= RECOGNIZED_CHAR_LIMIT
        return {
            "text": raw_text[:RECOGNIZED_CHAR_LIMIT],
            "hasFigure": bool(parsed.get("hasFigure")),
            "confidence": confidence,
            "truncated": truncated,
            "warning": "识别内容已达 4000 字上限，可能不完整，请核对" if truncated else "",
        }
    except HTTPException as exc:
        status, error = "error", str(exc.detail)
        raise
    except requests.Timeout:
        status, error = "error", "timeout"
        raise VisionFailure(504, "识别服务响应超时，请稍后重试或直接输入文字", "timeout")
    except requests.RequestException:
        status, error = "error", "network"
        raise VisionFailure(502, "无法连接识别服务，请稍后重试或直接输入文字", "network")
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
                prompt_chars=len(prompt),
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


__all__ = ["MAX_IMAGE_BYTES", "RECOGNIZED_CHAR_LIMIT", "VISION_FAILURE_MESSAGES", "VisionFailure", "read_image_body", "recognize_image", "vision_config", "vision_enabled"]

