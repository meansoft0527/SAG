"""Skill 执行引擎 —— 负责工具、工作流与模板求值。"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator
from sag_api.core.logging import get_logger
from sag_api.skills.base import BaseSkill, SkillContext
from sag_api.tools.base import ToolContext
from sag_api.tools.registry import registry as global_tool_registry

log = get_logger("skills.executor")


class SkillExecutor:
    """Skill 统一执行引擎。"""

    def __init__(self, tool_registry=global_tool_registry):
        self.tool_registry = tool_registry

    async def execute_skill(self, skill: BaseSkill, ctx: SkillContext) -> AsyncIterator[str]:
        """执行指定 Skill 并流式产生输出。"""
        # 如果是 WorkflowSkill
        if skill.skill_type == "workflow":
            async for chunk in self._execute_workflow(skill, ctx):
                yield chunk
            return

        # 如果是 ToolSkill
        if skill.skill_type == "tool":
            tool_name = skill.config.get("tool")
            if tool_name and self.tool_registry.has(tool_name):
                tool = self.tool_registry.get(tool_name)
                tool_ctx = ToolContext(engine_manager=ctx.sag_engine)
                params = {"code": ctx.user_input, "input_text": ctx.user_input, **ctx.parameters}
                res = await tool.invoke(params, tool_ctx)
                yield res.content
            else:
                yield f"[{skill.name}] 未找到对应底层工具: {tool_name}"
            return


        # 默认调用 Skill 自身的 execute 方法
        async for chunk in skill.execute(ctx):
            yield chunk

    async def _execute_workflow(self, skill: BaseSkill, ctx: SkillContext) -> AsyncIterator[str]:
        steps = skill.config.get("workflow", [])
        step_outputs: dict[str, Any] = {}

        yield f"🚀 开始执行工作流技能 [{skill.name}]，共 {len(steps)} 个步骤：\n\n"

        for step in steps:
            step_name = step.get("step", "unnamed")
            tool_name = step.get("tool")
            prompt_template = step.get("prompt")

            yield f"▶ **步骤 [{step_name}]**..."

            if tool_name and self.tool_registry.has(tool_name):
                tool = self.tool_registry.get(tool_name)
                tool_ctx = ToolContext(engine_manager=ctx.sag_engine)
                # 简单解析入参引用 {{query}}
                args = step.get("input", {})
                resolved_args = {}
                for k, v in args.items():
                    if isinstance(v, str) and v.startswith("{{") and v.endswith("}}"):
                        param_key = v[2:-2].strip()
                        resolved_args[k] = ctx.parameters.get(param_key, ctx.user_input)
                    else:
                        resolved_args[k] = v

                res = await tool.invoke(resolved_args, tool_ctx)
                step_outputs[step_name] = res.content
                yield f" 完成。\n```\n{res.content[:200]}\n```\n\n"

            elif prompt_template and ctx.llm:
                prompt_content = prompt_template.format(input=ctx.user_input, **step_outputs)
                result_tokens = []
                async for token in ctx.llm.astream_chat(system="请执行以下工作流环节:", prompt=prompt_content):
                    result_tokens.append(token)
                step_outputs[step_name] = "".join(result_tokens)
                yield f" 完成。\n\n"

        yield f"✅ 工作流 [{skill.name}] 执行完毕。\n"


global_skill_executor = SkillExecutor()
