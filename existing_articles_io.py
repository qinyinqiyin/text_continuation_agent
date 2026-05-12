# -*- coding: utf-8 -*-
"""已有文章合并 Markdown 的读写逻辑（与 tools 切段规则一致：行首「第N章」）。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Tuple

from config import EXISTING_ARTICLES_MD_PATH, logger


def _normalize_newlines(raw: str) -> str:
    return (raw or "").replace("\r\n", "\n")


def read_existing_articles_text() -> str:
    """读取合并稿全文；不含文件则返回空串。"""
    path = Path(EXISTING_ARTICLES_MD_PATH)
    if not path.is_file():
        return ""
    return _normalize_newlines(path.read_text(encoding="utf-8"))


def max_chapter_index_in_content(text: str) -> int:
    """返回文中出现过最大章节序号；无章标题则为 0。"""
    nums = [
        int(m.group(1))
        for m in re.finditer(r"^第\s*(\d+)\s*章", (text or ""), flags=re.MULTILINE)
    ]
    return max(nums) if nums else 0


def get_existing_articles_meta() -> Dict[str, object]:
    """供前端载入「前文」与展示当前进度。"""
    path = Path(EXISTING_ARTICLES_MD_PATH)
    exists = path.is_file()
    txt = ""
    if exists:
        try:
            txt = read_existing_articles_text()
        except OSError as e:
            logger.warning("读取合并稿失败：%s", e)
            txt = ""
            exists = False
    mx = max_chapter_index_in_content(txt)
    return {
        "content": txt,
        "path": str(path.resolve()),
        "file_exists": exists,
        "max_chapter": mx,
        "next_chapter": mx + 1,
    }


def append_continuation_as_next_chapter(continuation_plain: str) -> Tuple[int, str]:
    """在文末追加「第 next 章」与正文（UTF-8）。返回 (章节号, 提示语)。"""
    continuation_plain = (continuation_plain or "").strip()
    if not continuation_plain:
        raise ValueError("接续正文不能为空")

    path = Path(EXISTING_ARTICLES_MD_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)

    existing = read_existing_articles_text() if path.is_file() else ""
    next_n = max_chapter_index_in_content(existing) + 1

    sep = ""
    if existing.strip():
        sep = "\n" if existing.endswith("\n") else "\n\n"

    block = f"{sep}第{next_n}章\n\n{continuation_plain.rstrip()}\n"
    path.write_text(existing + block, encoding="utf-8")
    return next_n, f"已追加第 {next_n} 章至 {path.name}"
