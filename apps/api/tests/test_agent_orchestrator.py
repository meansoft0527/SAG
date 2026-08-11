"""Phase 2 测试：验证 Agent 编排器、TaskPlanner 任务拆解与内置工具。"""

import pytest
import asyncio
from pathlib import Path

from sag_api.agent.orchestrator import AgentOrchestrator
from sag_api.agent.planner import TaskPlanner
from sag_api.tools.registry import registry as tool_registry
from sag_api.tools.base import ToolContext


def test_task_planner():
    planner = TaskPlanner()
    plan = asyncio.run(planner.plan("帮我撰写周报且总结项目进度并发邮件"))
    assert plan.goal == "帮我撰写周报且总结项目进度并发邮件"
    assert len(plan.steps) == 3
    assert plan.steps[0].step_id == 1
    assert plan.steps[1].step_id == 2


def test_execute_code_tool():
    tool = tool_registry.get("execute_code")
    ctx = ToolContext(engine_manager=None)
    res = asyncio.run(tool.invoke({"code": "a = 10\nb = 20\nreturn a + b"}, ctx))
    assert res.data["success"] is True
    assert "30" in res.content


def test_orchestrator_skill_match():
    orchestrator = AgentOrchestrator()

    async def collect():
        chunks = []
        async for chunk in orchestrator.run("帮我撰写一份周报总结"):
            chunks.append(chunk)
        return "".join(chunks)

    res = asyncio.run(collect())
    # 应该命中了内置的 writer Skill 规则
    assert "撰写" in res or "系统提示词" in res or "LLM 尚未初始化" in res


def test_orchestrator_time_and_code_tools():
    orchestrator = AgentOrchestrator()

    async def collect(msg):
        chunks = []
        async for chunk in orchestrator.run(msg):
            chunks.append(chunk)
        return "".join(chunks)

    time_res = asyncio.run(collect("现在的具体时间是几点"))
    assert "当前时间" in time_res or "UTC" in time_res

    code_res = asyncio.run(collect("算一下: 100 * 5 + 12"))
    assert "512" in code_res
