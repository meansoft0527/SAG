"""智能 Agent 编排器（包含 Skill 匹配、TaskPlanner 任务分解与工具调度闭环）。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sag_api.agent.planner import global_task_planner
from sag_api.core.logging import get_logger
from sag_api.skills.base import SkillContext
from sag_api.skills.registry import global_skill_registry
from sag_api.tools.base import ToolContext
from sag_api.tools.registry import registry as global_tool_registry

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
        sources: list[Any] | None = None,
    ) -> AsyncIterator[str]:
        """运行编排处理逻辑，流式返回输出。"""
        # 1. 尝试优先匹配高分精确 Skill 技能
        matched_skills = self.skill_registry.match(message)
        if matched_skills and matched_skills[0].match_score(message) >= 0.8:
            top_skill = matched_skills[0]
            log.info("用户请求匹配至高分技能: %s (score=%.2f)", top_skill.name, top_skill.match_score(message))
            ctx = SkillContext(
                user_input=message,
                conversation_id=conversation_id,
                llm=llm,
                sag_engine=engine_manager,
            )
            async for chunk in top_skill.execute(ctx):
                yield chunk
            return

        # 2. 检查特定内置工具逻辑（时间、数学代码计算）
        msg_strip = message.strip()
        if "时间" in msg_strip or "几点" in msg_strip or "日期" in msg_strip:
            time_tool = self.tool_registry.get("get_time")
            if time_tool:
                tool_ctx = ToolContext(engine_manager=engine_manager, sources=sources)
                res = await time_tool.invoke({}, tool_ctx)
                yield res.content
                return

        if "计算" in msg_strip or "算一下" in msg_strip or "代码" in msg_strip:
            code_tool = self.tool_registry.get("execute_code")
            if code_tool:
                tool_ctx = ToolContext(engine_manager=engine_manager, sources=sources)
                code = msg_strip.replace("计算", "").replace("算一下", "").replace("代码", "").strip()
                if code.startswith(":") or code.startswith("："):
                    code = code[1:].strip()
                res = await code_tool.invoke({"code": f"return {code}"}, tool_ctx)
                yield res.content
                return

        # 3. 匹配中等分 Skill 技能
        if matched_skills:
            top_skill = matched_skills[0]
            log.info("用户请求匹配至技能: %s (score=%.2f)", top_skill.name, top_skill.match_score(message))
            ctx = SkillContext(
                user_input=message,
                conversation_id=conversation_id,
                llm=llm,
                sag_engine=engine_manager,
            )
            async for chunk in top_skill.execute(ctx):
                yield chunk
            return

        # 4. 进行任务规划与分解
        plan = await self.planner.plan(message, llm=llm)
        step_outputs: dict[int, str] = {}

        if len(plan.steps) > 1:
            yield f"📌 **【任务规划】** 已为您拆解 {len(plan.steps)} 个执行步骤：\n"
            for step in plan.steps:
                yield f"- 步骤 {step.step_id}: {step.title}\n"
            yield "\n---\n"

            for step in plan.steps:
                yield f"\n▶ **步骤 {step.step_id}：{step.title}**\n"
                step_result = ""

                action_name = step.action_name
                if self.tool_registry.has(action_name):
                    tool = self.tool_registry.get(action_name)
                    tool_ctx = ToolContext(engine_manager=engine_manager, sources=sources)
                    res = await tool.invoke({"query": step.input_text}, tool_ctx)
                    step_result = res.content
                    yield f"```text\n{step_result[:300]}...\n```\n"
                elif self.skill_registry.get_skill(action_name) is not None:
                    skill = self.skill_registry.get_skill(action_name)
                    ctx = SkillContext(
                        user_input=step.input_text,
                        conversation_id=conversation_id,
                        llm=llm,
                        sag_engine=engine_manager,
                    )
                    chunks = []
                    async for chunk in skill.execute(ctx):
                        chunks.append(chunk)
                    step_result = "".join(chunks)
                    yield f"{step_result[:300]}...\n"
                elif llm is not None:
                    accum = []
                    async for token in llm.astream_chat(
                        system="请根据上文信息执行该子任务步骤，并给出简短扼要的结果。",
                        prompt=f"子任务需求：{step.input_text}\n背景信息：{step_outputs.get(step.step_id - 1, '')}",
                    ):
                        accum.append(token)
                        yield token
                    step_result = "".join(accum)
                else:
                    step_result = f"已完成步骤 {step.step_id}"
                    yield f"{step_result}\n"

                step_outputs[step.step_id] = step_result

            yield "\n---\n🎯 **【总结与交付】**\n"
            if llm is not None:
                context_combined = "\n\n".join(
                    f"步骤 {s.step_id} ({s.title}) 结果：\n{step_outputs.get(s.step_id, '')}"
                    for s in plan.steps
                )
                async for token in llm.astream_chat(
                    system="你是一个高效的个人智能助手。请结合各子步骤的执行结果，为用户梳理一份条理清晰、准确完整的最终回答。",
                    prompt=f"原始用户需求：{message}\n\n各步骤执行结果：\n{context_combined}",
                ):
                    yield token
            else:
                yield f"需求「{message}」已成功处理完成。"
            return

        # 5. 单步骤默认回答逻辑
        if llm is not None:
            async for token in llm.astream_chat(
                system="你是一个高效、友好的个人智能助手，请清晰准确地回答用户的问题。",
                prompt=message,
            ):
                yield token
        else:
            yield f"已处理需求：「{message}」。"


global_agent_orchestrator = AgentOrchestrator()
