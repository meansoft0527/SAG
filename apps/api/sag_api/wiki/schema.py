"""AGENTS.md Schema 规范管理。"""

from __future__ import annotations


class WikiSchema:
    """Wiki 三层数据规范与规则约束。"""

    DEFAULT_RULES: list[str] = [
        "raw/ 保持原始输入资料，只读禁止任何修改。",
        "wiki/ 用于保存 Agent 抽取的结构化沉淀，包含 sources/概念 concepts/实体 entities/主题 topics。",
        "处理新资料前优先搜索 wiki/ 已有页面，避免重复创建同一概念。",
        "每份 raw 资料必须在 wiki/sources/ 建立来源摘要页，并双向引用。",
        "Wiki 页面必须清晰保留来源、更新时间和适用边界限制。",
        "遇到观点矛盾或分歧时，保留原始出处和时间维度，不直接覆盖旧结论。",
        "每次 Wiki 变更需向 changelog 记入摘要。",
    ]

    @classmethod
    def render_agents_md(cls) -> str:
        rules_rendered = "\n".join(f"{idx}. {rule}" for idx, rule in enumerate(cls.DEFAULT_RULES, start=1))
        return f"# Wiki Schema & Agent 操作规范\n\n{rules_rendered}\n"
