"""Skill 模块 API 完整路由。"""

from __future__ import annotations

import shutil
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from sag_api.skills.base import SkillContext
from sag_api.skills.executor import global_skill_executor
from sag_api.skills.registry import global_skill_registry

router = APIRouter(prefix="/skills", tags=["skills"])


class SkillSummary(BaseModel):
    name: str
    version: str
    description: str
    skill_type: str
    is_builtin: bool
    enabled: bool


class SkillRunRequest(BaseModel):
    input_text: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    conversation_id: str | None = None


class SkillCreateRequest(BaseModel):
    name: str
    version: str = "1.0.0"
    description: str
    skill_type: str = "prompt"
    keywords: list[str] = Field(default_factory=list)
    system_prompt: str = ""
    user_prompt: str = "{input}"


@router.get("", response_model=list[SkillSummary])
async def list_skills() -> list[SkillSummary]:
    """获取所有已安装并注册的 Skill 列表。"""
    res = []
    for skill in global_skill_registry.skills.values():
        res.append(
            SkillSummary(
                name=skill.name,
                version=skill.version,
                description=skill.description,
                skill_type=skill.skill_type,
                is_builtin=skill.is_builtin,
                enabled=skill.enabled,
            )
        )
    return res


@router.get("/{name}")
async def get_skill(name: str) -> dict[str, Any]:
    """获取指定 Skill 的详细配置。"""
    skill = global_skill_registry.get_skill(name)
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"技能 {name} 不存在")
    return skill.config


@router.post("/{name}/run")
async def run_skill(name: str, req: SkillRunRequest, request: Request):
    """执行指定技能。"""
    skill = global_skill_registry.get_skill(name)
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"技能 {name} 不存在")
    if not skill.enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"技能 {name} 已禁用")

    llm = getattr(request.app.state, "llm", None)
    engine_manager = getattr(request.app.state, "engine_manager", None)
    ctx = SkillContext(
        user_input=req.input_text,
        conversation_id=req.conversation_id,
        parameters=req.parameters,
        sag_engine=engine_manager,
        llm=llm,
    )

    async def generate():
        async for chunk in global_skill_executor.execute_skill(skill, ctx):
            yield chunk

    return StreamingResponse(generate(), media_type="text/plain")


@router.post("/{name}/toggle")
async def toggle_skill(name: str, enabled: bool) -> dict[str, Any]:
    """启用或禁用技能。"""
    skill = global_skill_registry.get_skill(name)
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"技能 {name} 不存在")
    skill.enabled = enabled
    skill.config["enabled"] = enabled
    return {"name": name, "enabled": skill.enabled}


@router.post("/create")
async def create_custom_skill(req: SkillCreateRequest) -> dict[str, Any]:
    """快捷创建自定义技能。"""
    custom_dir = global_skill_registry.custom_dir / req.name
    custom_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir = custom_dir / "prompts"
    prompts_dir.mkdir(exist_ok=True)

    yaml_content = f"""name: "{req.name}"
version: "{req.version}"
description: "{req.description}"
type: "{req.skill_type}"
enabled: true

triggers:
  keywords: {req.keywords}

prompts:
  system: "prompts/system.md"
  user: "prompts/user.md"
"""
    (custom_dir / "skill.yaml").write_text(yaml_content, encoding="utf-8")
    (prompts_dir / "system.md").write_text(req.system_prompt, encoding="utf-8")
    (prompts_dir / "user.md").write_text(req.user_prompt, encoding="utf-8")

    await global_skill_registry.load_all()
    return {"status": "ok", "name": req.name}


@router.delete("/{name}")
async def delete_custom_skill(name: str) -> dict[str, Any]:
    """删除自定义技能。"""
    skill = global_skill_registry.get_skill(name)
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"技能 {name} 不存在")
    if skill.is_builtin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="内置技能无法删除")

    shutil.rmtree(skill.skill_dir, ignore_errors=True)
    await global_skill_registry.load_all()
    return {"status": "ok", "deleted": name}
