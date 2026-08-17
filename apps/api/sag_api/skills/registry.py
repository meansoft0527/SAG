"""Skill 注册表 —— 支持发现、动态加载、热更新与匹配。"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    class _YamlFallback:
        @staticmethod
        def safe_load(text: str) -> dict:
            res: dict = {}
            for line in text.splitlines():
                line = line.strip()
                if line and not line.startswith("#") and ":" in line:
                    k, v = line.split(":", 1)
                    res[k.strip()] = v.strip().strip('"').strip("'")
            return res
    yaml = _YamlFallback()


from sag_api.core.logging import get_logger
from sag_api.skills.base import BaseSkill, SkillContext

log = get_logger("skills.registry")


class PromptSkill(BaseSkill):
    """基于提示词模板的声明式 Skill。"""

    async def execute(self, ctx: SkillContext):
        if self.skill_type == "workflow":
            from sag_api.skills.executor import global_skill_executor
            async for chunk in global_skill_executor._execute_workflow(self, ctx):
                yield chunk
            return

        prompts = self.config.get("prompts", {})
        sys_file = prompts.get("system")
        user_file = prompts.get("user")

        sys_prompt = ""
        if sys_file:
            path = Path(self.skill_dir) / sys_file
            if path.exists():
                sys_prompt = path.read_text(encoding="utf-8")

        user_template = "{input}"
        if user_file:
            path = Path(self.skill_dir) / user_file
            if path.exists():
                user_template = path.read_text(encoding="utf-8")

        user_content = user_template.format(input=ctx.user_input, **ctx.parameters)

        if ctx.llm:
            async for chunk in ctx.llm.astream_chat(system=sys_prompt, prompt=user_content):
                yield chunk
        else:
            yield f"[{self.name}] LLM 尚未初始化。系统提示词: {sys_prompt[:30]}..."


class SkillRegistry:
    """Skill 集中注册管理。"""

    def __init__(self, builtin_dir: Path | None = None, custom_dir: Path | None = None):
        # PyInstaller 冻结时 __file__ 指向内存中的 .pyc，需改用 sys._MEIPASS 定位磁盘资源
        # PyInstaller 6.x 将 datas 放在 {_MEIPASS}/_internal/，旧版直接在 _MEIPASS 下
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            meipass = Path(sys._MEIPASS)
            # 优先尝试 PyInstaller 6.x 的 _internal 子目录布局
            candidate = meipass / "_internal" / "sag_api" / "skills"
            root = candidate if candidate.exists() else meipass / "sag_api" / "skills"
        else:
            root = Path(__file__).parent
        self.builtin_dir = builtin_dir or (root / "builtin")
        self.custom_dir = custom_dir or (root / "custom")
        self.skills: dict[str, BaseSkill] = {}

    async def load_all(self):
        """扫描并加载所有技能。"""
        self.skills.clear()
        if self.builtin_dir.exists():
            await self._scan_dir(self.builtin_dir, is_builtin=True)
        if self.custom_dir.exists():
            await self._scan_dir(self.custom_dir, is_builtin=False)
        log.info("Skill 注册表加载完毕，共注册 %d 个技能", len(self.skills))

    async def _scan_dir(self, target_dir: Path, is_builtin: bool):
        for item in target_dir.iterdir():
            if item.is_dir():
                yaml_file = item / "skill.yaml"
                if yaml_file.exists():
                    try:
                        content = yaml_file.read_text(encoding="utf-8")
                        config = yaml.safe_load(content) or {}
                        skill = PromptSkill(config, str(item), is_builtin=is_builtin)
                        self.skills[skill.name] = skill
                    except Exception as e:  # noqa: BLE001
                        log.warning("加载 Skill 失败 path=%s: %s", item, e)

    def match(self, user_input: str) -> list[BaseSkill]:
        """根据输入文本评分并返回候选 Skill。"""
        scored = []
        for skill in self.skills.values():
            score = skill.match_score(user_input)
            if score > 0.3:
                scored.append((score, skill))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored]

    def get_skill(self, name: str) -> BaseSkill | None:
        return self.skills.get(name)


global_skill_registry = SkillRegistry()
