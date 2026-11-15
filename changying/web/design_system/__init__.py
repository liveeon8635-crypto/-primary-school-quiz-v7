"""Scoped presentation layer for existing Changying HTML renderers."""

import os
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _stylesheet() -> str:
    return Path(__file__).with_name("surfaces.css").read_text(encoding="utf-8")


def apply_surface(html: str, surface: str) -> str:
    """Apply a surface to an existing document without replacing its scripts."""
    if os.getenv("CHANGYING_UI_REFRESH", "1") == "0":
        return html
    root = '<html lang="zh-CN">'
    if root not in html or "</head>" not in html:
        return html
    html = html.replace(root, f'<html lang="zh-CN" data-cy-ui="{surface}">', 1)
    return html.replace("</head>", f'<style id="cy-ui-surfaces">{_stylesheet()}</style>\n</head>', 1)
