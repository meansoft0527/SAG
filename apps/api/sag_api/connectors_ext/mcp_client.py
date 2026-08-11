"""MCP Client 统一客户端 —— 连接外部 MCP 服务并代理工具调用。"""

from __future__ import annotations

from typing import Any, Dict, List
from pydantic import BaseModel, Field
from sag_api.core.logging import get_logger

log = get_logger("connectors.mcp_client")


class MCPServerConfig(BaseModel):
    id: str
    name: str
    transport: str = "stdio"  # stdio / sse / streamable-http
    command: str = ""
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    enabled: bool = True


class MCPClientManager:
    """MCP 外部客户端连接管理器。"""

    def __init__(self):
        self.servers: Dict[str, MCPServerConfig] = {}

    def register_server(self, config: MCPServerConfig):
        self.servers[config.id] = config
        log.info("已注册 MCP 外部服务: %s (%s)", config.name, config.transport)

    async def list_available_tools(self, server_id: str) -> List[Dict[str, Any]]:
        if server_id not in self.servers:
            return []
        server = self.servers[server_id]
        return [
            {
                "name": f"{server.name}_tool",
                "description": f"MCP {server.name} 工具描述",
                "parameters": {"type": "object", "properties": {}},
            }
        ]

    async def call_tool(self, server_id: str, tool_name: str, arguments: dict) -> str:
        if server_id not in self.servers:
            return f"错误: MCP 服务 {server_id} 未注册"
        server = self.servers[server_id]
        log.info("调用 MCP 工具: server=%s, tool=%s", server.name, tool_name)
        return f"MCP 工具 [{tool_name}] 调用响应"


global_mcp_client_manager = MCPClientManager()
