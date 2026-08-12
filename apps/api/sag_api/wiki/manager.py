"""Wiki 三层架构（Raw / Wiki / Schema）管理器（含 CRUD 与页面存储）。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from sag_api.core.logging import get_logger
from sag_api.wiki.schema import WikiSchema

log = get_logger("wiki.manager")


@dataclass
class WikiPage:
    path: str
    title: str
    content: str
    page_type: str  # source / concept / entity / topic
    source_refs: list[str] = field(default_factory=list)


class WikiManager:
    """管理个人知识库三层数据形态（Raw, Wiki, Schema）。"""

    def __init__(self, base_dir: Path | None = None):
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            from sag_api.core.config import settings
            self.base_dir = Path(settings.data_dir) / "knowledge_wiki"

    def initialize(self):
        """确保三层目录形态与 AGENTS.md 规范就绪。"""
        subdirs = [
            "raw/articles",
            "raw/papers",
            "raw/books",
            "raw/chats",
            "raw/notes",
            "raw/meetings",
            "wiki/sources",
            "wiki/concepts",
            "wiki/entities",
            "wiki/topics",
        ]
        for sd in subdirs:
            os.makedirs(self.base_dir / sd, exist_ok=True)

        agents_md = self.base_dir / "AGENTS.md"
        if not agents_md.exists():
            agents_md.write_text(WikiSchema.render_agents_md(), encoding="utf-8")
        log.info("Wiki 三层架构初始化完毕 base_dir=%s", self.base_dir)

    def list_wiki_pages(self, category: str = "concepts") -> list[dict[str, str]]:
        cat_dir = self.base_dir / "wiki" / category
        if not cat_dir.exists():
            return []
        pages = []
        for file in cat_dir.glob("*.md"):
            pages.append({"name": file.stem, "path": str(file.relative_to(self.base_dir))})
        return pages

    def get_page(self, category: str, page_name: str) -> WikiPage | None:
        file_path = self.base_dir / "wiki" / category / f"{page_name}.md"
        if not file_path.exists():
            return None
        content = file_path.read_text(encoding="utf-8")
        return WikiPage(
            path=str(file_path.relative_to(self.base_dir)),
            title=page_name,
            content=content,
            page_type=category,
        )

    def save_page(self, category: str, page_name: str, content: str, source_refs: list[str] | None = None) -> WikiPage:
        cat_dir = self.base_dir / "wiki" / category
        os.makedirs(cat_dir, exist_ok=True)
        file_path = cat_dir / f"{page_name}.md"
        file_path.write_text(content, encoding="utf-8")
        return WikiPage(
            path=str(file_path.relative_to(self.base_dir)),
            title=page_name,
            content=content,
            page_type=category,
            source_refs=source_refs or [],
        )

    def delete_page(self, category: str, page_name: str) -> bool:
        file_path = self.base_dir / "wiki" / category / f"{page_name}.md"
        if file_path.exists():
            file_path.unlink()
            return True
        return False


_global_wiki_manager: WikiManager | None = None


def get_wiki_manager() -> WikiManager:
    global _global_wiki_manager
    if _global_wiki_manager is None:
        _global_wiki_manager = WikiManager()
    return _global_wiki_manager


class _WikiManagerProxy:
    def __getattr__(self, name):
        return getattr(get_wiki_manager(), name)


global_wiki_manager = _WikiManagerProxy()

