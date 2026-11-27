"""语文阅读简答题与微片段写作大模型 AI 实时批改（带本地规则自动兜底）.

优先复用项目现有学校/全局 AI 配置（DeepSeek / OpenAI 兼容接口）进行单次批量 JSON 批改；
若未配置 API Key、测试环境禁用外网或请求超时，则自动平滑降级为本地关键词+字数规则判分，绝不阻塞交卷。
"""
from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib import request as urllib_request

from changying.services import chinese_builtin_map as cbm


def _resolve_ai_config(implementation: Any | None, db: Any | None, school_id: int | None) -> tuple[str, str, str] | None:
    """按学校级配置 -> 环境变量顺序解析 (base_url, api_key, model)."""
    # 1. 尝试复用学校已保存的 AI 配置（如有）
    if implementation is not None and db is not None and school_id is not None:
        cfg_fn = getattr(implementation, "get_school_ai_config", None) or getattr(implementation, "_school_ai_config", None)
        if callable(cfg_fn):
            try:
                cfg = cfg_fn(db, int(school_id))
                if isinstance(cfg, dict) and cfg.get("api_key") and cfg.get("base_url"):
                    return (
                        str(cfg["base_url"]).rstrip("/"),
                        str(cfg["api_key"]).strip(),
                        str(cfg.get("model") or "deepseek-chat").strip(),
                    )
            except Exception:
                pass

    # 2. 尝试读取全局环境变量（兼容 DeepSeek / OpenAI）
    api_key = (
        os.environ.get("CHINESE_AI_API_KEY")
        or os.environ.get("DEEPSEEK_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or ""
    ).strip()
    if not api_key:
        return None
    base_url = (
        os.environ.get("CHINESE_AI_BASE_URL")
        or os.environ.get("DEEPSEEK_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or "https://api.deepseek.com/v1"
    ).rstrip("/")
    model = (
        os.environ.get("CHINESE_AI_MODEL")
        or os.environ.get("DEEPSEEK_MODEL")
        or "deepseek-chat"
    ).strip()
    return base_url, api_key, model


def _extract_json_block(raw: str) -> dict[str, Any] | None:
    txt = str(raw or "").strip()
    m = re.search(r"\{[\s\S]*\}", txt)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _call_chat_completions(base_url: str, api_key: str, model: str, payload_items: list[dict[str, Any]], timeout: float = 15.0) -> dict[str, dict[str, Any]] | None:
    sys_prompt = (
        "你是小学五年级语文特级教师，正在实时批改学生的阅读简答题与微片段写作。"
        "请严格按每题的满分(maxMarks)、参考要点(reference)和学生作答(studentAnswer)给出客观公平的分数与简明鼓励式点评（每题点评 25~60 字，包含1个亮点和1条具体改进建议）。"
        "仅输出合法 JSON，格式为："
        '{"results":[{"id":"题号","earnedMarks":整数,"comment":"简明点评"}]}'
    )
    user_content = json.dumps({"items": payload_items}, ensure_ascii=False)
    body = json.dumps(
        {
            "model": model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_content},
            ],
        },
        ensure_ascii=False,
    ).encode("utf-8")

    endpoint = base_url + ("/chat/completions" if not base_url.endswith("/chat/completions") else "")
    req = urllib_request.Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib_request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    choices = data.get("choices") or []
    if not choices:
        return None
    msg = (choices[0].get("message") or {}).get("content") or ""
    parsed = _extract_json_block(msg)
    if not parsed or not isinstance(parsed.get("results"), list):
        return None
    out: dict[str, dict[str, Any]] = {}
    for row in parsed["results"]:
        if isinstance(row, dict) and row.get("id"):
            out[str(row["id"])] = row
    return out


def grade_subjective_items(
    items: list[tuple[dict[str, Any], str]],
    *,
    implementation: Any | None = None,
    db: Any | None = None,
    school_id: int | None = None,
    ai_caller: Any | None = None,
) -> dict[str, dict[str, Any]]:
    """批量批改主观题（阅读简答/微写作），优先走大模型 AI，失败或未配 Key 自动规则兜底."""
    results: dict[str, dict[str, Any]] = {}
    if not items:
        return results

    non_empty: list[tuple[dict[str, Any], str]] = []
    for q, ans in items:
        raw = str(ans or "").strip()
        if not raw:
            max_m = int(q.get("marks", cbm.TYPE_POINTS.get(q.get("questionType", ""), 4)))
            results[q["id"]] = {
                "earnedMarks": 0,
                "maxMarks": max_m,
                "passed": False,
                "gradingMode": "rule_fallback",
                "comment": "本题未作答，建议结合题干与参考范文补写练习。",
            }
        else:
            non_empty.append((q, raw))

    if not non_empty:
        return results

    ai_map: dict[str, dict[str, Any]] | None = None
    payload = [
        {
            "id": q["id"],
            "type": q.get("typeLabel", q.get("questionType", "")),
            "maxMarks": int(q.get("marks", 4)),
            "question": q["text"],
            "passage": q.get("passage", ""),
            "reference": q.get("sampleAnswer") or q.get("answer", ""),
            "studentAnswer": ans,
        }
        for q, ans in non_empty
    ]

    try:
        if callable(ai_caller):
            ai_map = ai_caller(payload)
        else:
            cfg = _resolve_ai_config(implementation, db, school_id)
            if cfg is not None:
                base_url, api_key, model = cfg
                ai_map = _call_chat_completions(base_url, api_key, model, payload)
    except Exception:
        ai_map = None

    for q, ans in non_empty:
        qid = q["id"]
        max_m = int(q.get("marks", cbm.TYPE_POINTS.get(q.get("questionType", ""), 4)))
        if ai_map and qid in ai_map:
            row = ai_map[qid]
            try:
                earned = max(0, min(max_m, int(round(float(row.get("earnedMarks", 0))))))
                comment = str(row.get("comment") or "").strip() or "AI 已完成批改，请结合参考范文复盘细节。"
                results[qid] = {
                    "earnedMarks": earned,
                    "maxMarks": max_m,
                    "passed": earned >= max(1, int(round(max_m * 0.6))),
                    "gradingMode": "ai",
                    "comment": comment,
                }
                continue
            except Exception:
                pass
        results[qid] = cbm.grade_subjective_rule_fallback(q, ans)

    return results


__all__ = ["grade_subjective_items"]
