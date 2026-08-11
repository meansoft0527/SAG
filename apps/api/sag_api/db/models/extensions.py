"""新增模块的数据库模型（Skill、Wiki、Connectors、Agent Tasks、MCP Servers）。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from sag_api.db.base import Base


class SkillModel(Base):
    """Skill 注册与持久化配置"""

    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    skill_type: Mapped[str] = mapped_column(String(32), nullable=False)  # prompt/tool/workflow/composite
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[str] = mapped_column(Text, nullable=False)  # JSON 副本
    install_path: Mapped[str] = mapped_column(String(512), nullable=False)
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WikiPageModel(Base):
    """Wiki 结构化页面"""

    __tablename__ = "wiki_pages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    path: Mapped[str] = mapped_column(String(256), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_type: Mapped[str] = mapped_column(String(32), nullable=False)  # source/concept/entity/topic
    source_refs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON 字符串
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WikiChangelogModel(Base):
    """Wiki 变更历史日志"""

    __tablename__ = "wiki_changelog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    page_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)  # create/update/link
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConnectorModel(Base):
    """数据源连接器（RSS / 网页抓取 / API / MCP）"""

    __tablename__ = "connectors"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)  # rss/web_crawl/api/mcp
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    config: Mapped[str] = mapped_column(Text, nullable=False)  # JSON 配置
    source_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_sync: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_interval: Mapped[int] = mapped_column(Integer, default=3600)  # 秒
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class AgentTaskModel(Base):
    """Agent 后台异步与规划任务"""

    __tablename__ = "agent_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/running/done/failed
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class MCPServerModel(Base):
    """客户端可连接的外部 MCP 服务器列表"""

    __tablename__ = "mcp_servers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    transport: Mapped[str] = mapped_column(String(32), nullable=False)  # stdio/sse/streamable-http
    config: Mapped[str] = mapped_column(Text, nullable=False)  # JSON 配置
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
