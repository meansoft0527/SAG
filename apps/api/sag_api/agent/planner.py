"""任务规划器 —— 将复杂的复合需求分解为有顺序的 TaskStep。"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from sag_api.core.logging import get_logger

log = get_logger("agent.planner")


class TaskStep(BaseModel):
    """单个规划步骤。"""

    step_id: int
    title: str
    action_type: str = "tool"  # skill / tool / qa / write / search
    action_name: str  # 例如 writer / search_context / web_search / deep_research_writer / auto
    input_text: str
    condition: str | None = None


class TaskPlan(BaseModel):
    """总体任务规划方案。"""

    goal: str
    steps: list[TaskStep] = Field(default_factory=list)


_PLANNER_SYSTEM_PROMPT = """你是一个智能任务规划专家。根据用户的需求，将其拆解为 1 到 5 个有顺序的子步骤 TaskStep。

可用的 Action 类型包括:
- search_context: 检索本地知识库资料
- web_search: 联网搜索最新事实或信息
- deep_research_writer: 深度研报/长文写作
- writer: 写作排版或文章起草
- execute_code: 执行 Python 代码或数据计算
- qa: 综合思考与问答解答

请返回且仅返回符合以下 JSON 格式的数据：
{
  "goal": "用户核心目标",
  "steps": [
    {
      "step_id": 1,
      "title": "步骤简短标题",
      "action_type": "tool",
      "action_name": "search_context 或 web_search 或 writer 或 deep_research_writer",
      "input_text": "该步骤的具体输入指令"
    }
  ]
}
"""


class TaskPlanner:
    """任务规划分解器（支持 LLM 结构化规划与规则降级）。"""

    async def plan(self, user_request: str, llm: Any = None) -> TaskPlan:
        """分析用户请求并分解步骤。"""
        req_clean = user_request.strip()

        # 1. 尝试使用 LLM 进行结构化规划
        if llm is not None and len(req_clean) > 8:
            try:
                response = ""
                if hasattr(llm, "astream_chat"):
                    async for token in llm.astream_chat(
                        system=_PLANNER_SYSTEM_PROMPT,
                        prompt=f"请为以下需求生成 TaskPlan：\n{req_clean}",
                    ):
                        response += token
                elif hasattr(llm, "complete"):
                    response = await llm.complete(
                        messages=[
                            {"role": "system", "content": _PLANNER_SYSTEM_PROMPT},
                            {"role": "user", "content": f"请为以下需求生成 TaskPlan：\n{req_clean}"},
                        ]
                    )

                if response:
                    clean_json = response.strip()
                    if "```json" in clean_json:
                        clean_json = clean_json.split("```json")[1].split("```")[0].strip()
                    elif "```" in clean_json:
                        clean_json = clean_json.split("```")[1].split("```")[0].strip()

                    parsed = json.loads(clean_json)
                    steps = []
                    for idx, item in enumerate(parsed.get("steps", []), start=1):
                        steps.append(
                            TaskStep(
                                step_id=idx,
                                title=item.get("title", f"步骤 {idx}"),
                                action_type=item.get("action_type", "tool"),
                                action_name=item.get("action_name", "auto"),
                                input_text=item.get("input_text", req_clean),
                            )
                        )
                    if steps:
                        return TaskPlan(goal=parsed.get("goal", req_clean), steps=steps)
            except Exception as exc:  # noqa: BLE001
                log.warning("LLM 规划步骤解析失败，降级为规则匹配: %s", exc)

        # 2. 规则逻辑降级
        steps = []
        if "且" in req_clean or "然后" in req_clean or "并" in req_clean:
            sub_parts = [
                p.strip()
                for p in req_clean.replace("并且", ";")
                .replace("且", ";")
                .replace("然后", ";")
                .replace("并发", ";发")
                .replace("并", ";")
                .split(";")
                if p.strip()
            ]
            for idx, part in enumerate(sub_parts, start=1):
                action = "writer" if ("写" in part or "周报" in part) else ("search_context" if ("查" in part or "搜" in part) else "auto")
                steps.append(
                    TaskStep(
                        step_id=idx,
                        title=f"执行子任务 {idx}: {part[:15]}",
                        action_type="tool",
                        action_name=action,
                        input_text=part,
                    )
                )
        elif "写" in req_clean or "文章" in req_clean or "报告" in req_clean:
            steps.append(
                TaskStep(
                    step_id=1,
                    title="检索知识库与相关资料",
                    action_type="tool",
                    action_name="search_context",
                    input_text=f"检索关于：{req_clean}",
                )
            )
            steps.append(
                TaskStep(
                    step_id=2,
                    title="深度写作与文章撰写",
                    action_type="skill",
                    action_name="writer",
                    input_text=req_clean,
                )
            )
        else:
            steps.append(
                TaskStep(
                    step_id=1,
                    title="执行主任务",
                    action_type="tool",
                    action_name="auto",
                    input_text=req_clean,
                )
            )

        return TaskPlan(goal=req_clean, steps=steps)


global_task_planner = TaskPlanner()
