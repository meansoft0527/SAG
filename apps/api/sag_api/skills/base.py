"""Skill 基础基类与上下文数据模型。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SkillContext(BaseModel):
    """Skill 执行上下文。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    user_input: str
    conversation_id: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    sag_engine: Any = None
    llm: Any = None
    tool_runner: Any = None



class SkillResult(BaseModel):
    """Skill 执行输出。"""

    content: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseSkill(ABC):
    """Skill 抽象基类。"""

    def __init__(self, config: dict, skill_dir: str, is_builtin: bool = False):
        self.config = config
        self.skill_dir = skill_dir
        self.is_builtin = is_builtin
        self.name: str = config.get("name", "unnamed_skill")
        self.version: str = config.get("version", "1.0.0")
        self.description: str = config.get("description", "")
        self.skill_type: str = config.get("type", "prompt")  # prompt / tool / workflow / composite
        self.enabled: bool = config.get("enabled", True)

    @abstractmethod
    async def execute(self, ctx: SkillContext) -> AsyncIterator[str]:
        """流式输出执行结果。"""
        ...

    def match_score(self, user_input: str) -> float:
        """根据关键字和意图计算匹配得分 (0~1)。"""
        if not self.enabled:
            return 0.0
        score = 0.0
        clean_input = user_input.strip().lower()
        # 斜杠命令优先打满 1.0 分（如 /writer 或 /translator）
        if clean_input.startswith(f"/{self.name.lower()}") or f"/{self.name.lower()}" in clean_input:
            return 1.0
        triggers = self.config.get("triggers", {})
        keywords = triggers.get("keywords", [])
        for kw in keywords:
            if kw and kw in user_input:
                score = max(score, 0.85)
        return score

