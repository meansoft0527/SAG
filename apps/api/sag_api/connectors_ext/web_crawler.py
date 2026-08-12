"""网页抓取器 —— 单页抓取与 Sitemap 链接提取。"""

from __future__ import annotations

from typing import Any

import httpx

from sag_api.connectors.web import extract_web_markdown, extract_web_title
from sag_api.core.logging import get_logger

log = get_logger("connectors.web_crawler")


class WebCrawler:
    """网页与 XML Sitemap 抓取器。"""

    async def crawl_url(self, url: str) -> dict[str, Any]:
        """抓取单个网页并转为 Markdown。"""
        log.info("开始抓取网页: %s", url)
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "MyAgent-Bot/1.0"})
                resp.raise_for_status()
                html = resp.text
                title = extract_web_title(html) or url
                markdown = extract_web_markdown(html)
                return {
                    "url": url,
                    "title": title,
                    "content": markdown,
                    "success": True,
                }
        except Exception as error:  # noqa: BLE001
            log.warning("网页抓取失败 %s: %s", url, error)
            return {"url": url, "title": "", "content": "", "success": False, "error": str(error)}

    async def crawl_sitemap(self, sitemap_url: str, limit: int = 10) -> list[str]:
        """简易 Sitemap 链接提取。"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(sitemap_url)
                resp.raise_for_status()
                text = resp.text
                import re
                urls = re.findall(r"<loc>(.*?)</loc>", text)
                return urls[:limit]
        except Exception as error:  # noqa: BLE001
            log.warning("Sitemap 抓取失败 %s: %s", sitemap_url, error)
            return []


global_web_crawler = WebCrawler()
