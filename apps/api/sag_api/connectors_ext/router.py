"""数据源扩展 (Web 抓取, RSS, MCP Client) REST API 路由。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from sag_api.connectors_ext.mcp_client import MCPServerConfig, global_mcp_client_manager
from sag_api.connectors_ext.rss_feed import global_rss_manager
from sag_api.connectors_ext.web_crawler import global_web_crawler

router = APIRouter(prefix="/connectors-ext", tags=["connectors-ext"])


class WebCrawlRequest(BaseModel):
    url: str


class SitemapCrawlRequest(BaseModel):
    sitemap_url: str
    limit: int = 10


class RSSFetchRequest(BaseModel):
    feed_url: str
    limit: int = 10


@router.post("/crawl-url")
async def crawl_url(req: WebCrawlRequest) -> dict[str, Any]:
    """抓取单个网页内容。"""
    res = await global_web_crawler.crawl_url(req.url)
    if not res["success"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=res.get("error", "网页抓取失败"))
    return res


@router.post("/crawl-sitemap")
async def crawl_sitemap(req: SitemapCrawlRequest) -> list[str]:
    """抓取 Sitemap 获取链接。"""
    return await global_web_crawler.crawl_sitemap(req.sitemap_url, limit=req.limit)


@router.post("/rss-fetch")
async def fetch_rss(req: RSSFetchRequest) -> list[dict[str, Any]]:
    """抓取并解析 RSS 条目。"""
    return await global_rss_manager.fetch_feed(req.feed_url, limit=req.limit)


@router.post("/mcp-servers")
async def add_mcp_server(config: MCPServerConfig) -> dict[str, str]:
    """注册/更新外部 MCP 服务。"""
    global_mcp_client_manager.register_server(config)
    return {"status": "ok", "name": config.name}


@router.get("/mcp-servers")
async def list_mcp_servers() -> list[dict[str, Any]]:
    """获取所有已注册的外部 MCP 服务。"""
    res = []
    for s in global_mcp_client_manager.servers.values():
        res.append({
            "id": s.id,
            "name": s.name,
            "transport": s.transport,
            "enabled": s.enabled,
        })
    return res
