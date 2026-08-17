"""智能写作与任务辅助 API —— 支持大纲结构化生成、多格式输出、知识库 Wiki 沉淀与信源归档。"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from sag_api.core.config import settings
from sag_api.core.db import get_session
from sag_api.core.deps import get_engine_manager, get_job_queue
from sag_api.core.logging import get_logger
from sag_api.jobs import JobQueue
from sag_api.sag import EngineManager
from sag_api.services.document_service import ingest_content
from sag_api.services.source_service import get_source
from sag_api.wiki.auto_grow import global_auto_grow_engine

log = get_logger("api.writer")
router = APIRouter(prefix="/writer", tags=["writer"])


class OutlineNode(BaseModel):
    title: str = Field(..., description="章节标题")
    summary: str | None = Field(default=None, description="要点要意")
    subsections: list[str] = Field(default_factory=list, description="子看点/小节列表")


class GenerateOutlineRequest(BaseModel):
    topic: str = Field(..., min_length=1, description="写作主题")
    requirements: str | None = Field(default=None, description="需求意图与额外要求")
    source_ids: list[str] = Field(default_factory=list, description="已选知识库信源 ID 列表")
    writer_mode: str = Field(default="deep_research", description="文章体裁类型")


class GenerateOutlineResponse(BaseModel):
    ok: bool = True
    topic: str
    outline: list[OutlineNode] = Field(default_factory=list)


class SaveToKBRequest(BaseModel):
    title: str = Field(..., min_length=1, description="文章标题")
    content: str = Field(..., min_length=1, description="文章 Markdown 内容")
    category: str = Field(default="topics", description="归档类别：sources / concepts / entities / topics")
    keywords: list[str] = Field(default_factory=list, description="关联关键词")


class SaveToKBResponse(BaseModel):
    ok: bool = True
    title: str
    category: str
    wiki_path: str
    message: str


class SaveToSourceRequest(BaseModel):
    source_id: str = Field(..., min_length=1, description="目标信源 ID")
    title: str = Field(..., min_length=1, description="文章标题")
    content: str = Field(..., min_length=1, description="文章 Markdown 内容")


class SaveToSourceResponse(BaseModel):
    ok: bool = True
    document_id: str
    source_id: str
    filename: str
    message: str


_OUTLINE_SYSTEM_PROMPT = """你是一位资深的出版与研报主编。请根据用户的主题、背景需求与关联知识库，设计一份层次分明、逻辑递进的经典 4-5 章节深度大纲。

请返回且仅返回符合以下 JSON 格式的数据：
{
  "topic": "文章主题",
  "outline": [
    {
      "title": "一、 章节名称",
      "summary": "本章核心思想与论述主线",
      "subsections": ["1.1 子要点", "1.2 子要点"]
    }
  ]
}
"""


@router.post("/outline", response_model=GenerateOutlineResponse)
async def generate_outline(
    req: GenerateOutlineRequest,
    request: Request,
):
    """根据写作主题、背景与选中知识库，生成交互式可确认大纲。"""
    llm: Any = getattr(request.app.state, "llm", None)
    clean_topic = req.topic.strip()

    if llm is not None:
        try:
            prompt_input = f"主题：{clean_topic}\n额外要求：{req.requirements or '无'}\n体裁：{req.writer_mode}"
            response = ""
            if hasattr(llm, "complete"):
                response = await llm.complete(
                    messages=[
                        {"role": "system", "content": _OUTLINE_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt_input},
                    ]
                )

            if response:
                clean_json = response.strip()
                if "```json" in clean_json:
                    clean_json = clean_json.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_json:
                    clean_json = clean_json.split("```")[1].split("```")[0].strip()

                parsed = json.loads(clean_json)
                nodes = []
                for item in parsed.get("outline", []):
                    nodes.append(
                        OutlineNode(
                            title=item.get("title", "未命名章节"),
                            summary=item.get("summary", ""),
                            subsections=item.get("subsections", []),
                        )
                    )
                if nodes:
                    return GenerateOutlineResponse(ok=True, topic=clean_topic, outline=nodes)
        except Exception as exc:  # noqa: BLE001
            log.warning("LLM 生成大纲解析异常，降级为规则结构大纲: %s", exc)

    # 规则回退大纲
    fallback_nodes = [
        OutlineNode(
            title="一、 背景与问题定位",
            summary=f"阐述{clean_topic}的技术或应用背景，定位行业核心痛点与需求。",
            subsections=["1.1 行业现状与发展动向", "1.2 核心痛点与知识背景分析"],
        ),
        OutlineNode(
            title="二、 核心原理与架构解析",
            summary=f"深度剖析{clean_topic}的技术设计、模块构成与工作流。",
            subsections=["2.1 基础架构与组件交互", "2.2 核心算法与关键机制"],
        ),
        OutlineNode(
            title="三、 落地实践与案例应用",
            summary="结合知识库案例与项目实践，展示应用方法论与成效数据。",
            subsections=["3.1 典型应用场景落地", "3.2 实践经验与指标对照"],
        ),
        OutlineNode(
            title="四、 总结展望与演进路线",
            summary="总结全篇核心观点，提出未来技术演进与建议。",
            subsections=["4.1 核心价值总结", "4.2 未来发展趋势与建议"],
        ),
    ]
    return GenerateOutlineResponse(ok=True, topic=clean_topic, outline=fallback_nodes)


@router.post("/save_to_kb", response_model=SaveToKBResponse)
async def save_article_to_kb(
    req: SaveToKBRequest,
    db: AsyncSession = Depends(get_session),
):
    """将生成或撰写的优质文章一键沉淀存入 SAG Wiki 知识库体系中。"""
    try:
        clean_title = req.title.strip()
        category = req.category if req.category in {"sources", "concepts", "entities", "topics"} else "topics"

        kw_tags = " ".join(f"`#{kw}`" for kw in req.keywords) if req.keywords else "`#智能写作沉淀`"
        wiki_md = f"# {clean_title}\n\n> 标签与领域: {kw_tags}\n\n## 文章正文\n\n{req.content}\n"

        global_auto_grow_engine.wiki_manager.save_page(category, clean_title, wiki_md)
        try:
            await global_auto_grow_engine.rebuild_wiki_from_knowledge_base(db)
        except Exception as rebuild_err:  # noqa: BLE001
            log.warning("Wiki 关联图谱全量更新跳过: %s", rebuild_err)

        wiki_rel_path = f"wiki/{category}/{clean_title}.md"
        log.info("文章成功沉淀至知识库: %s", wiki_rel_path)

        return SaveToKBResponse(
            ok=True,
            title=clean_title,
            category=category,
            wiki_path=wiki_rel_path,
            message="文章已成功同步并沉淀至 SAG Wiki 知识库！",
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("存入知识库失败: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"存入知识库失败: {exc}",
        ) from exc


@router.post("/save_to_source", response_model=SaveToSourceResponse)
async def save_article_to_source(
    req: SaveToSourceRequest,
    db: AsyncSession = Depends(get_session),
    job_queue: JobQueue = Depends(get_job_queue),
):
    """把定稿文章直接存入指定的 SAG 知识库信源中作为新文档。"""
    try:
        source = await get_source(db, req.source_id)
        doc = await ingest_content(
            db,
            source,
            text=req.content,
            title=req.title,
            upload_dir=settings.upload_dir,
            job_queue=job_queue,
        )
        return SaveToSourceResponse(
            ok=True,
            document_id=doc.id,
            source_id=source.id,
            filename=doc.filename,
            message=f"文章已成功存入信源「{source.name}」，文档处理队列已触发！",
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("存入信源失败: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"存入信源失败: {exc}",
        ) from exc
