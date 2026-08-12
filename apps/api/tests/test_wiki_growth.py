"""Phase 3 测试：验证 LLM Wiki 三层架构、CRUD 与自生长引擎。"""

import asyncio
from pathlib import Path

from sag_api.wiki.auto_grow import AutoGrowEngine
from sag_api.wiki.manager import WikiManager


def test_wiki_schema_and_init(tmp_path: Path):
    wm = WikiManager(base_dir=tmp_path)
    wm.initialize()

    agents_md = tmp_path / "AGENTS.md"
    assert agents_md.exists()
    content = agents_md.read_text(encoding="utf-8")
    assert "Wiki Schema" in content
    assert "raw/" in content


def test_wiki_crud(tmp_path: Path):
    wm = WikiManager(base_dir=tmp_path)
    wm.initialize()

    # 1. 创建页面
    page = wm.save_page("concepts", "SAG架构", "# SAG 架构说明\n\n一种高效率 RAG 方案。")
    assert page.title == "SAG架构"
    assert "wiki/concepts/SAG架构.md" in page.path

    # 2. 获取页面
    fetched = wm.get_page("concepts", "SAG架构")
    assert fetched is not None
    assert "高效率 RAG" in fetched.content

    # 3. 页面列表
    pages = wm.list_wiki_pages("concepts")
    assert len(pages) == 1
    assert pages[0]["name"] == "SAG架构"

    # 4. 删除页面
    deleted = wm.delete_page("concepts", "SAG架构")
    assert deleted is True
    assert wm.get_page("concepts", "SAG架构") is None


def test_auto_grow_engine(tmp_path: Path):
    wm = WikiManager(base_dir=tmp_path)
    wm.initialize()
    engine = AutoGrowEngine(wiki_manager=wm)

    # 第一次问答：触发自动创建概念页
    res1 = asyncio.run(engine.auto_grow_from_interaction("什么是 SAG 检索", "SAG 是 SQL 驱动的超边检索技术。"))
    assert "SAG 检索" in res1

    created_page = wm.get_page("concepts", "SAG 检索")
    assert created_page is not None
    assert "超边检索" in created_page.content

    # 第二次问答：触发增量更新
    res2 = asyncio.run(engine.auto_grow_from_interaction("什么是 SAG 检索", "它在 Recall 指标上达到了 SOTA。"))
    assert "SAG 检索" in res2

    updated_page = wm.get_page("concepts", "SAG 检索")
    assert "超边检索" in updated_page.content
    assert "SOTA" in updated_page.content
