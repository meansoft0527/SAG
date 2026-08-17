"""MCP 工具适配器 —— 将外部 MCP Server 工具动态包装注册为 Agent 可调用的 Tool。"""

from __future__ import annotations

from typing import Any

from sag_api.connectors_ext.mcp_client import global_mcp_client_manager
from sag_api.core.logging import get_logger
from sag_api.tools.base import Tool, ToolContext, ToolMeta, ToolResult
from sag_api.tools.registry import registry as global_tool_registry

log = get_logger("tools.mcp_adapter")


class ExternalMCPTool(Tool):
    """包装外部 MCP 工具的代理 Tool 类。"""

    def __init__(self, server_id: str, tool_name: str, description: str, parameters: dict[str, Any]):
        self.server_id = server_id
        self.meta = ToolMeta(
            name=f"mcp_{server_id}_{tool_name}",
            description=f"[MCP {server_id}] {description}",
            parameters=parameters or {"type": "object", "properties": {}},
        )
        self.raw_tool_name = tool_name

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        del ctx
        try:
            res_content = await global_mcp_client_manager.call_tool(
                server_id=self.server_id,
                tool_name=self.raw_tool_name,
                arguments=args,
            )
            return ToolResult(content=res_content, data={"server_id": self.server_id, "tool_name": self.raw_tool_name})
        except Exception as exc:  # noqa: BLE001
            log.warning("MCP 工具调用失败 server=%s, tool=%s: %s", self.server_id, self.raw_tool_name, exc)
            return ToolResult(content=f"MCP 工具 [{self.raw_tool_name}] 调用失败: {exc}")


async def sync_mcp_tools_to_registry(tool_registry=global_tool_registry):
    """扫描并同步已注册的外部 MCP Server 工具至 ToolRegistry。"""
    registered_count = 0
    for server_id in list(global_mcp_client_manager.servers.keys()):
        tools = await global_mcp_client_manager.list_available_tools(server_id)
        for tspec in tools:
            name = tspec.get("name", "unnamed")
            desc = tspec.get("description", "")
            params = tspec.get("parameters", {})
            mcp_tool = ExternalMCPTool(
                server_id=server_id,
                tool_name=name,
                description=desc,
                parameters=params,
            )
            tool_registry.register(mcp_tool)
            registered_count += 1
    log.info("同步外部 MCP 工具完毕，共挂载 %d 个 MCP 工具", registered_count)
    return registered_count
