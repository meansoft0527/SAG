"""智能 Agent 编排器（包含 Skill 匹配、TaskPlanner 任务分解与工具调度）。"""

from __future__ import annotations

from typing import Any, AsyncIterator
from sag_api.agent.planner import global_task_planner
from sag_api.core.logging import get_logger
from sag_api.skills.base import SkillContext
from sag_api.skills.registry import global_skill_registry
from sag_api.tools.base import ToolContext
from sag_api.tools.registry import registry as global_tool_registry
from sag_api.wiki.manager import get_wiki_manager

log = get_logger("agent.orchestrator")


class AgentOrchestrator:
    """智能体编排核心入口。"""

    def __init__(
        self,
        skill_registry=None,
        tool_registry=None,
        planner=None,
    ):
        self.skill_registry = skill_registry or global_skill_registry
        self.tool_registry = tool_registry or global_tool_registry
        self.planner = planner or global_task_planner

    async def run(
        self,
        message: str,
        conversation_id: str | None = None,
        llm: Any = None,
        engine_manager: Any = None,
    ) -> AsyncIterator[str]:
        """运行编排处理逻辑，流式返回输出。"""
        # 1. 尝试优先匹配 Skill 技能
        matched_skills = self.skill_registry.match(message)
        if matched_skills:
            top_skill = matched_skills[0]
            log.info("用户请求匹配至技能: %s (score=%.2f)", top_skill.name, top_skill.match_score(message))
            ctx = SkillContext(user_input=message, conversation_id=conversation_id, llm=llm)
            async for chunk in top_skill.execute(ctx):
                yield chunk
            return

        # 2. 检查特定内置工具逻辑（例如时间、数学代码计算）
        msg_strip = message.strip()
        if "时间" in msg_strip or "几点" in msg_strip or "日期" in msg_strip:
            time_tool = self.tool_registry.get("get_time")
            tool_ctx = ToolContext(engine_manager=engine_manager)
            res = await time_tool.invoke({}, tool_ctx)
            yield res.content
            return

        if "计算" in msg_strip or "算一下" in msg_strip or "代码" in msg_strip:
            code_tool = self.tool_registry.get("execute_code")
            tool_ctx = ToolContext(engine_manager=engine_manager)
            # 简单提取表达
            code = msg_strip.replace("计算", "").replace("算一下", "").replace("代码", "").strip()
            if code.startswith(":") or code.startswith("："):
                code = code[1:].strip()
            res = await code_tool.invoke({"code": f"return {code}"}, tool_ctx)
            yield res.content
            return

        # 3. 进行任务规划与分解
        plan = await self.planner.plan(message, llm=llm)
        if len(plan.steps) > 1:
            yield f"【任务规划】已为需求「{plan.goal}」拆解 {len(plan.steps)} 个步骤：\n"
            for step in plan.steps:
                yield f"- 步骤 {step.step_id}: {step.title}\n"
            yield "\n"

        # 4. LLM 生成回答
        if llm is not None:
            async for token in llm.astream_chat(
                system="你是一个高效、友好的个人智能助手，请清晰准确地回答用户的问题。",
                prompt=message,
            ):
                yield token
        else:
            yield f"已处理需求：「{message}」。"
