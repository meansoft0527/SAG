"""RSS / Atom 订阅抓取与解析器。"""

from __future__ import annotations

import httpx
import xml.etree.ElementTree as ET
from typing import Any, Dict, List
from sag_api.core.logging import get_logger

log = get_logger("connectors.rss")


class RSSFeedManager:
    """RSS / Atom 订阅解析与轮询。"""

    async def fetch_feed(self, feed_url: str, limit: int = 10) -> List[Dict[str, Any]]:
        """抓取并解析 RSS/Atom xml 内容。"""
        log.info("开始拉取 RSS: %s", feed_url)
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(feed_url, headers={"User-Agent": "MyAgent-RSS/1.0"})
                resp.raise_for_status()
                xml_text = resp.text

            root = ET.fromstring(xml_text)
            entries = []

            # 兼容 RSS 2.0 (<channel><item>)
            for item in root.findall(".//item")[:limit]:
                title = item.findtext("title") or "无标题"
                link = item.findtext("link") or ""
                description = item.findtext("description") or ""
                entries.append({
                    "title": title,
                    "link": link,
                    "summary": description,
                })

            # 兼容 Atom (<feed><entry>)
            if not entries:
                for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry")[:limit]:
                    title = entry.findtext("{http://www.w3.org/2005/Atom}title") or "无标题"
                    link_elem = entry.find("{http://www.w3.org/2005/Atom}link")
                    link = link_elem.get("href") if link_elem is not None else ""
                    summary = entry.findtext("{http://www.w3.org/2005/Atom}summary") or ""
                    entries.append({
                        "title": title,
                        "link": link,
                        "summary": summary,
                    })

            return entries
        except Exception as error:  # noqa: BLE001
            log.warning("RSS 抓取失败 %s: %s", feed_url, error)
            return []


global_rss_manager = RSSFeedManager()
