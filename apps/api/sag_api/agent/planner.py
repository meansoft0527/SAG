"""任务规划器 —— 将复杂的复合需求分解为有顺序的 TaskStep。"""

from __future__ import annotations

from typing import Any, List
from pydantic import BaseModel, Field


class TaskStep(BaseModel):
    """单个规划步骤。"""

    step_id: int
    title: str
    action_type: str = "tool"  # skill / tool / qa / write
    action_name: str  # 例如 writer / search_context / execute_code
    input_text: str
    condition: str | None = None


class TaskPlan(BaseModel):
    """总体任务规划方案。"""

    goal: str
    steps: List[TaskStep] = Field(default_factory=list)


class TaskPlanner:
    """任务规划分解器。"""

    async def plan(self, user_request: str, llm: Any = None) -> TaskPlan:
        """分析用户请求并分解步骤。"""
        # 简单规则或 LLM 生成步骤
        req_clean = user_request.strip()
        steps = []

        # 示例：如果需求包含复合词汇，建立多步拆解
        if "且" in req_clean or "然后" in req_clean or "并" in req_clean:
            sub_parts = [p.strip() for p in req_clean.replace("且", ";").replace("然后", ";").replace("并", ";").split(";") if p.strip()]
            for idx, part in enumerate(sub_parts, start=1):
                steps.append(
                    TaskStep(
                        step_id=idx,
                        title=f"执行子任务 {idx}: {part[:15]}",
                        action_type="tool",
                        action_name="auto",
                        input_text=part,
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
