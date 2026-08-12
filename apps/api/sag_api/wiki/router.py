"""Wiki REST API 路由（含 CRUD 与自生长接口）。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from sag_api.wiki.auto_grow import global_auto_grow_engine
from sag_api.wiki.manager import get_wiki_manager

router = APIRouter(prefix="/wiki", tags=["wiki"])


class WikiPageSaveRequest(BaseModel):
    content: str
    source_refs: list[str] = Field(default_factory=list)


class AutoGrowRequest(BaseModel):
    query: str
    answer: str


@router.get("/pages")
async def list_pages(category: str = "concepts") -> list[dict[str, str]]:
    """列出 Wiki 指定分类下的页面。"""
    return get_wiki_manager().list_wiki_pages(category)


@router.get("/pages/{category}/{page_name}")
async def get_page(category: str, page_name: str) -> dict[str, Any]:
    """获取指定 Wiki 页面。"""
    page = get_wiki_manager().get_page(category, page_name)
    if not page:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Wiki 页面 {category}/{page_name} 不存在")
    return {
        "title": page.title,
        "path": page.path,
        "category": page.page_type,
        "content": page.content,
    }


@router.post("/pages/{category}/{page_name}")
async def save_page(category: str, page_name: str, req: WikiPageSaveRequest) -> dict[str, Any]:
    """创建或更新 Wiki 页面。"""
    page = get_wiki_manager().save_page(category, page_name, req.content, req.source_refs)
    return {
        "title": page.title,
        "path": page.path,
        "category": page.page_type,
    }


@router.delete("/pages/{category}/{page_name}")
async def delete_page(category: str, page_name: str) -> dict[str, Any]:
    """删除指定 Wiki 页面。"""
    success = get_wiki_manager().delete_page(category, page_name)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Wiki 页面 {category}/{page_name} 不存在")
    return {"status": "ok", "deleted": f"{category}/{page_name}"}


@router.post("/init")
async def init_wiki() -> dict[str, str]:
    """手动初始化 Wiki 目录结构。"""
    get_wiki_manager().initialize()
    return {"status": "ok", "message": "Wiki 结构已建立"}


@router.post("/rebuild")
async def rebuild_wiki() -> dict[str, Any]:
    """手动扫描知识库并全量重建自生长 Wiki 概念、实体、主题与信源页面。"""
    page_counts = await global_auto_grow_engine.rebuild_wiki_from_knowledge_base()
    return {"status": "ok", "message": "自生长 Wiki 重建完成", "counts": page_counts}


@router.post("/auto-grow")
async def trigger_auto_grow(req: AutoGrowRequest) -> dict[str, Any]:
    """触发 Wiki 知识自生长沉淀。"""
    updated_pages = await global_auto_grow_engine.auto_grow_from_interaction(req.query, req.answer)
    return {"status": "ok", "updated_pages": updated_pages}

