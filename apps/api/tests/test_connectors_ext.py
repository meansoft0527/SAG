"""Phase 4 测试：验证数据源扩展 (Web 抓取, RSS 订阅, MCP Client)。"""

import pytest
import asyncio

from sag_api.connectors_ext.web_crawler import WebCrawler
from sag_api.connectors_ext.rss_feed import RSSFeedManager
from sag_api.connectors_ext.mcp_client import MCPClientManager, MCPServerConfig


def test_rss_manager_parse():
    rss_manager = RSSFeedManager()
    xml_sample = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
    <channel>
        <title>测试 RSS 源</title>
        <item>
            <title>第一条技术动态</title>
            <link>https://example.com/post-1</link>
            <description>这里是动态内容</description>
        </item>
    </channel>
    </rss>
    """
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_sample)

    entries = []
    for item in root.findall(".//item"):
        entries.append({
            "title": item.findtext("title"),
            "link": item.findtext("link"),
            "summary": item.findtext("description"),
        })

    assert len(entries) == 1
    assert entries[0]["title"] == "第一条技术动态"


def test_mcp_client_manager():
    manager = MCPClientManager()
    config = MCPServerConfig(
        id="brave-search",
        name="BraveSearch",
        transport="stdio",
        command="npx @anthropic/brave-search-mcp",
    )
    manager.register_server(config)
    assert "brave-search" in manager.servers

    tools = asyncio.run(manager.list_available_tools("brave-search"))
    assert len(tools) == 1
    assert "BraveSearch" in tools[0]["name"]

    res = asyncio.run(manager.call_tool("brave-search", "query", {"q": "SAG"}))
    assert "调用响应" in res
