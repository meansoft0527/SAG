"""Phase 2.5 测试：验证完整的 Skill 扩展系统。"""

import asyncio
from pathlib import Path

from sag_api.skills.base import SkillContext
from sag_api.skills.executor import SkillExecutor
from sag_api.skills.registry import global_skill_registry


def test_builtin_skills_loaded():
    asyncio.run(global_skill_registry.load_all())
    skills = global_skill_registry.skills

    # 验证 6 个内置 Skill 均成功注册
    for expected in ["writer", "translator", "summarizer", "data_analyst", "code_runner", "web_researcher"]:
        assert expected in skills, f"内置技能 {expected} 应该存在"

    # 验证匹配打分
    translator = skills["translator"]
    assert translator.match_score("帮我翻译这段英文") > 0.5

    summarizer = skills["summarizer"]
    assert summarizer.match_score("生成摘要") > 0.5


def test_skill_executor_workflow(tmp_path: Path):
    executor = SkillExecutor()
    skill = global_skill_registry.get_skill("code_runner")
    assert skill is not None

    ctx = SkillContext(
        user_input="代码计算",
        parameters={"code": "return 42 * 2"},
    )

    async def run():
        output = []
        async for chunk in executor.execute_skill(skill, ctx):
            output.append(chunk)
        return "".join(output)

    result = asyncio.run(run())
    assert "84" in result


def test_custom_skill_dynamic_creation(tmp_path: Path):
    custom_dir = tmp_path / "custom"
    registry = global_skill_registry
    registry.custom_dir = custom_dir

    # 创建一个新的自定义技能
    my_skill_dir = custom_dir / "my_custom_skill"
    my_skill_dir.mkdir(parents=True)
    yaml_content = (
        'name: "my_custom_skill"\n'
        'version: "1.0.0"\n'
        'description: "自定义技能"\n'
        'type: "prompt"\n'
        'triggers:\n'
        '  keywords: ["自定义魔法"]\n'
    )
    (my_skill_dir / "skill.yaml").write_text(yaml_content, encoding="utf-8")

    asyncio.run(registry.load_all())
    assert "my_custom_skill" in registry.skills
    matched = registry.match("运行自定义魔法")
    assert len(matched) > 0
    assert matched[0].name == "my_custom_skill"
