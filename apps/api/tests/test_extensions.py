"""测试新增的 Skill 注册表与 Wiki 管理器模块。"""

import pytest
from pathlib import Path
from sag_api.skills.registry import SkillRegistry
from sag_api.wiki.manager import WikiManager


def test_skill_registry_load(tmp_path: Path):
    builtin_dir = tmp_path / "builtin"
    writer_dir = builtin_dir / "writer"
    writer_dir.mkdir(parents=True)

    yaml_content = (
        'name: "writer"\n'
        'version: "1.0.0"\n'
        'description: "公文撰写"\n'
        'type: "prompt"\n'
        'triggers:\n'
        '  keywords: ["写文章", "撰写"]\n'
    )
    (writer_dir / "skill.yaml").write_text(yaml_content, encoding="utf-8")

    registry = SkillRegistry(builtin_dir=builtin_dir, custom_dir=tmp_path / "custom")
    import asyncio
    asyncio.run(registry.load_all())

    assert "writer" in registry.skills
    skill = registry.skills["writer"]
    assert skill.description == "公文撰写"
    assert skill.match_score("帮我撰写一份总结") > 0.5


def test_wiki_manager_init(tmp_path: Path):
    wiki_dir = tmp_path / "wiki_base"
    wm = WikiManager(base_dir=wiki_dir)
    wm.initialize()

    assert (wiki_dir / "AGENTS.md").exists()
    assert (wiki_dir / "wiki" / "concepts").exists()
    assert (wiki_dir / "raw" / "articles").exists()
