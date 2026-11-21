"""Paired teacher+student .docx extraction and deterministic binding helpers."""

from __future__ import annotations

import base64
import hashlib
import io
import re
import zipfile
from typing import Any
from xml.etree import ElementTree as ET

_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_IMAGE_MIMES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def extract_docx_inventory(raw: bytes, filename: str) -> dict[str, Any]:
    """Read paragraphs, tables and embedded images from a .docx buffer without mutating it."""
    digest = sha256_hex(raw)
    blocks: list[dict[str, Any]] = []
    media: list[dict[str, Any]] = []
    table_count = 0

    with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
        if "word/document.xml" in zf.namelist():
            root = ET.fromstring(zf.read("word/document.xml"))
            body = root.find(f"{_W_NS}body")
            if body is not None:
                for idx, child in enumerate(list(body)):
                    tag = child.tag.rsplit("}", 1)[-1]
                    if tag == "p":
                        text = "".join(t.text or "" for t in child.iter(f"{_W_NS}t")).strip()
                        if text:
                            blocks.append({
                                "part": "word/document.xml",
                                "bodyIndex": idx,
                                "type": "paragraph",
                                "text": text,
                            })
                    elif tag == "tbl":
                        table_count += 1
                        rows: list[list[str]] = []
                        for tr in child.findall(f"{_W_NS}tr"):
                            row_cells = [
                                "".join(t.text or "" for t in tc.iter(f"{_W_NS}t")).strip()
                                for tc in tr.findall(f"{_W_NS}tc")
                            ]
                            if any(row_cells):
                                rows.append(row_cells)
                        if rows:
                            blocks.append({
                                "part": "word/document.xml",
                                "bodyIndex": idx,
                                "type": "table",
                                "rows": rows,
                                "text": "\n".join(" | ".join(r) for r in rows),
                            })
        for name in sorted(zf.namelist()):
            if not name.startswith("word/media/"):
                continue
            ext = ("." + name.rsplit(".", 1)[-1]).lower() if "." in name else ""
            mime = _IMAGE_MIMES.get(ext, "")
            if not mime:
                continue
            data = zf.read(name)
            media.append({
                "part": name,
                "sha256": sha256_hex(data),
                "bytes": len(data),
                "mime": mime,
                "dataUrl": f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}",
            })

    return {
        "file": filename,
        "sha256": digest,
        "tableCount": table_count,
        "blocks": blocks,
        "media": media,
    }


def _classify_block(text: str) -> tuple[str, int, str, str]:
    """Return (item_type, recommended_stage, confidence, pending_reason)."""
    t = text.strip()
    if any(k in t for k in ("参考答案：", "参考答案:", "答案：", "答案:")):
        return "answer", 5, "medium", "需确认答案对应的具体题目"
    if any(k in t for k in ("解析：", "解析:", "答题模板")):
        return "explanation", 4, "medium", "需确认解析/模板绑定的题目或考点"
    if re.match(r"^(?:题目?\s*\d+|\d+\s*[.、．]|（\d+）|\(\d+\))", t):
        return "question", 5, "high", ""
    if t.startswith("《") or "短文阅读" in t or "阅读理解" in t or len(t) >= 120:
        stage = 2 if "短文" in t or len(t) < 450 else 3
        return "article", stage, "high", ""
    return "article", 2, "low", "低置信度文本块，需教师确认环节与归属"


def pair_teacher_and_student_docs(
    teacher_bytes: bytes,
    teacher_name: str,
    student_bytes: bytes,
    student_name: str,
) -> dict[str, Any]:
    """Extract and pair teacher + student .docx into reviewable binding items."""
    t_inv = extract_docx_inventory(teacher_bytes, teacher_name)
    s_inv = extract_docx_inventory(student_bytes, student_name)
    student_texts = {re.sub(r"\s+", "", b["text"]) for b in s_inv["blocks"]}
    student_media_hashes = {m["sha256"] for m in s_inv["media"]}

    bindings: list[dict[str, Any]] = []
    last_question_key = ""
    seq = 0

    for blk in t_inv["blocks"]:
        seq += 1
        key = f"blk-{seq}"
        if blk["type"] == "table":
            bindings.append({
                "itemKey": key,
                "stageNo": 4 if "考点" in blk["text"] else 3,
                "itemType": "table",
                "targetKey": last_question_key,
                "sourceFile": teacher_name,
                "sourcePart": f"{blk['part']}#body:{blk['bodyIndex']}",
                "confidence": "high" if re.sub(r"\s+", "", blk["text"]) in student_texts else "medium",
                "status": "confirmed" if re.sub(r"\s+", "", blk["text"]) in student_texts else "pending",
                "pendingReason": "" if re.sub(r"\s+", "", blk["text"]) in student_texts else "表格未在学生版中完全匹配，请核对归属",
                "payload": {"rows": blk["rows"], "text": blk["text"]},
            })
            continue

        item_type, stage_no, confidence, pending_reason = _classify_block(blk["text"])
        norm = re.sub(r"\s+", "", blk["text"])
        in_student = norm in student_texts
        if item_type == "question":
            last_question_key = key
        target_key = last_question_key if item_type in ("answer", "explanation", "hint") else ""
        if item_type in ("answer", "explanation") and not target_key:
            confidence = "low"
            pending_reason = "未找到前置题目，需手动绑定到具体题目"
        status = "confirmed" if (confidence == "high" and (in_student or item_type in ("article", "question"))) else "pending"
        if item_type in ("answer", "explanation") and target_key:
            status = "pending"  # 答案/解析需教师核对确认后才绑定完成
        bindings.append({
            "itemKey": key,
            "stageNo": stage_no,
            "itemType": item_type,
            "targetKey": target_key,
            "sourceFile": teacher_name,
            "sourcePart": f"{blk['part']}#body:{blk['bodyIndex']}",
            "confidence": confidence,
            "status": status,
            "pendingReason": pending_reason,
            "payload": {"text": blk["text"], "teacherOnly": item_type in ("answer", "explanation", "hint")},
        })

    for m_idx, media in enumerate(t_inv["media"], 1):
        key = f"img-{m_idx}"
        shared = media["sha256"] in student_media_hashes
        bindings.append({
            "itemKey": key,
            "stageNo": 3,
            "itemType": "image",
            "targetKey": "",
            "sourceFile": teacher_name,
            "sourcePart": media["part"],
            "confidence": "medium" if shared else "low",
            "status": "pending",
            "pendingReason": "图片需绑定到具体文章或题目（用途标签不能替代实际绑定）",
            "payload": {
                "sha256": media["sha256"],
                "bytes": media["bytes"],
                "mime": media["mime"],
                "dataUrl": media["dataUrl"],
                "sharedWithStudent": shared,
            },
        })

    return {
        "teacherFile": teacher_name,
        "teacherSha256": t_inv["sha256"],
        "studentFile": student_name,
        "studentSha256": s_inv["sha256"],
        "teacherMediaCount": len(t_inv["media"]),
        "studentMediaCount": len(s_inv["media"]),
        "bindings": bindings,
    }


__all__ = ["extract_docx_inventory", "pair_teacher_and_student_docs", "sha256_hex"]
