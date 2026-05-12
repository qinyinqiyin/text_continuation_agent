# -*- coding: utf-8 -*-
"""创作阶段可调用的本地 Markdown 与联网检索工具（LangChain @tool）。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from langchain_core.tools import tool

from config import (
    ARTICLE_MARKDOWN_ROOT,
    EXISTING_ARTICLES_MD_PATH,
    REFERENCE_TEMPLATE_MARKDOWN_ROOT,
    logger,
)


def _sanitize_stem(identifier: str) -> Optional[str]:
    """取安全文件名主干，禁止路径穿越。"""
    if not identifier or not str(identifier).strip():
        return None
    name = Path(str(identifier).strip().replace("\\", "/")).name
    if not name or ".." in name:
        return None
    if name.lower().endswith(".md"):
        name = name[:-3]
    return name.strip() or None


def _is_strictly_under(child: Path, root: Path) -> bool:
    """child 是否位于 root 之下（防目录穿越）。"""
    try:
        child.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _read_markdown_file(path: Path) -> str:
    """按 UTF-8 读取；失败时尝试系统默认编码。"""
    data = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(enc).strip()
        except UnicodeDecodeError:
            continue
    return data.decode(errors="replace").strip()


def _find_markdown_in_root(identifier: str, root: Path) -> Optional[Path]:
    """先精确匹配 `{stem}.md`，再文件名主干忽略大小写匹配，最后再单目录内模糊包含。"""
    stem = _sanitize_stem(identifier)
    if stem is None:
        return None
    root = root.resolve()
    if not root.is_dir():
        return None

    exact = root / f"{stem}.md"
    if exact.is_file() and _is_strictly_under(exact, root):
        return exact

    lower_needle = stem.lower()
    stems: List[str] = []
    for p in root.iterdir():
        if not p.is_file() or p.suffix.lower() != ".md":
            continue
        if not _is_strictly_under(p, root):
            continue
        st = p.stem
        stems.append(st)
        if st.lower() == lower_needle:
            return p

    # 模糊：标识为子串
    for p in root.iterdir():
        if not p.is_file() or p.suffix.lower() != ".md":
            continue
        if not _is_strictly_under(p, root):
            continue
        if lower_needle in p.stem.lower():
            return p
    return None


def _list_md_stems(root: Path) -> str:
    """供错误提示：告知当前目录下有哪些 .md 主干名。"""
    root = root.resolve()
    if not root.is_dir():
        return f"（目录不存在：{root}）"
    names = sorted(p.stem for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".md")
    if not names:
        return "（当前无 .md 文件；请将章节/模板以 UTF-8 保存为 .md 放入对应目录。）"
    return "、".join(names[:40]) + (" …" if len(names) > 40 else "")


def _parse_chapter_number(identifier: str) -> Optional[int]:
    """从章节标识中提取阿拉伯章节号：纯数字、`第12章`、`Chapter 7` 等。"""
    s = (identifier or "").strip()
    if not s:
        return None
    if re.fullmatch(r"\d+", s):
        return int(s)
    m = re.search(r"第\s*(\d+)\s*章", s)
    if m:
        return int(m.group(1))
    m = re.match(r"(?i)chapters?\s*[_\s-]*(\d+)\s*$", s)
    if m:
        return int(m.group(1))
    return None


def _split_merged_article_by_cn_headings(full_text: str) -> Dict[int, str]:
    """按中文「第N章」在行首出现的切点拆块（适用于合并稿 existing articles.md）。"""
    stripped = full_text.strip()
    if not stripped:
        return {}
    # 不改变章节内部换行：只在「下一章标题」前行切分
    chunks = re.split(r"(?=^第\s*\d+\s*章)", stripped, flags=re.MULTILINE)
    index: Dict[int, str] = {}
    for ch in chunks:
        raw = ch.strip()
        if not raw:
            continue
        m = re.match(r"^第\s*(\d+)\s*章", raw)
        if not m:
            continue
        n = int(m.group(1))
        if n in index:
            logger.warning("合并稿中存在多个「第%s章」，后文覆盖前文（仅保留最后一次）", n)
        index[n] = raw
    return index


def _extract_chapter_from_existing_articles_md(chapter_num: int) -> Tuple[Optional[str], str]:
    """从 EXISTING_ARTICLES_MD_PATH 读取合并稿并返回某一章正文；错误或缺章时 body 为 None。"""
    path = Path(EXISTING_ARTICLES_MD_PATH)
    if not path.is_file():
        return None, f"合并稿不存在：{path.resolve()}"

    try:
        full_text = _read_markdown_file(path)
    except OSError as e:
        return None, str(e)

    index = _split_merged_article_by_cn_headings(full_text)
    if not index:
        return None, "合并稿未解析出任何「第N章」标题（须在行首使用「第1章」「第2章」等格式）"

    body = index.get(chapter_num)
    if body is None:
        avail = sorted(index.keys())
        return None, (
            f"合并稿无第 {chapter_num} 章。当前可读章节号："
            + (", ".join(str(x) for x in avail) or "（无）")
        )
    return body, ""


@tool
def query_article_chapter_markdown(chapter_identifier: str) -> str:
    """查询既有正文章节（不进向量库）。默认从合并稿读取。

    **推荐**：传入章节序号即可自动切分——如 `2`、`12`、`第2章`、`chapter 7`；
    合并稿路径见配置项 `EXISTING_ARTICLES_MD_PATH`（默认 `markdown/existing articles.md`），正文按文中行首「第N章」划分。

    **兼容**：若不是纯章节号语义，则在 `markdown/`（STORY_ARTICLE_MD_DIR）下按 `.md` 文件名主干查找单文件全文。
    """
    n = _parse_chapter_number(chapter_identifier)
    if n is not None:
        body, err = _extract_chapter_from_existing_articles_md(n)
        if body is not None:
            path = Path(EXISTING_ARTICLES_MD_PATH)
            return f"【章节】第{n}章（来源 {path.name}）\n\n{body}"
        return f"读取章节失败：{err}"

    root = Path(ARTICLE_MARKDOWN_ROOT)
    path = _find_markdown_in_root(chapter_identifier, root)
    if path is None:
        return (
            f"未找到章节 Markdown：标识={chapter_identifier!r}，检索根目录={root}。"
            f"可选主干名示例：{_list_md_stems(root)}"
        )
    try:
        body = _read_markdown_file(path)
    except OSError as e:
        logger.warning("读取章节 Markdown 失败：%s", e)
        return f"读取文件失败：{path}，{e}"
    return f"【文件】{path.name}\n\n{body}"


@tool
def query_reference_template_markdown(template_name: str) -> str:
    """查询参考模板 Markdown（文风、结构范例等）。

    参数 template_name：项目 `markdown/` 下模板 `.md` 的主干名（如 `reference template`），
    可带 `.md`；含空格时请与文件名一致。
    """
    root = Path(REFERENCE_TEMPLATE_MARKDOWN_ROOT)
    path = _find_markdown_in_root(template_name, root)
    if path is None:
        return (
            f"未找到模板 Markdown：标识={template_name!r}，检索根目录={root}。"
            f"可选主干名示例：{_list_md_stems(root)}"
        )
    try:
        body = _read_markdown_file(path)
    except OSError as e:
        logger.warning("读取模板 Markdown 失败：%s", e)
        return f"读取文件失败：{path}，{e}"
    return f"【模板】{path.name}\n\n{body}"


@tool
def web_search_story_assistance(query: str) -> str:
    """联网检索（DuckDuckGo），用于辅助创作：背景知识、专有名词、时代设定等简要事实核查。

    参数 query：简短中文或英文检索词；勿上传隐私。结果仅供启发，请勿大段照搬。
    """
    q = (query or "").strip()
    if not q:
        return "检索词为空。"
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
    except ImportError:
        return "未安装 langchain_community，无法使用联网检索。"
    try:
        runner = DuckDuckGoSearchRun()
        out = runner.invoke(q)
        return (out or "").strip() or "（无返回摘要）"
    except Exception as e:
        logger.warning("DuckDuckGo 检索失败：%s", e)
        return (
            f"联网检索失败：{e}。若环境未安装依赖，请执行：pip install duckduckgo-search"
        )


def get_story_creation_tools():
    """返回 Outline / Planning / Writing 共用的创作辅助工具。"""
    return [
        query_article_chapter_markdown,
        query_reference_template_markdown,
        web_search_story_assistance,
    ]
