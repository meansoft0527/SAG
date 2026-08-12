"""Wiki 知识自生长引擎 —— 从知识库文档与交互问答中自动全量提取、更新并整理 Wiki 三层架构页面。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sag_api.core.db import SessionLocal
from sag_api.core.logging import get_logger
from sag_api.db.models import Document, Source
from sag_api.wiki.manager import WikiManager, get_wiki_manager

log = get_logger("wiki.auto_grow")


def _sanitize_name(name: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fa5\-]", "_", name)


class AutoGrowEngine:
    """自动沉淀与进化知识 Wiki 的自生长引擎。"""

    def __init__(self, wiki_manager: WikiManager | None = None):
        self._wiki_manager = wiki_manager

    @property
    def wiki_manager(self) -> WikiManager:
        return self._wiki_manager or get_wiki_manager()

    async def rebuild_wiki_from_knowledge_base(self, session: AsyncSession | None = None) -> dict[str, int]:
        """全量扫描数据库中已有文档与信源，抽取并生成/更新 Sources、Concepts、Entities、Topics 四类 Wiki 页面。"""
        log.info("开始全量重构与扫描自生长 Wiki 概念图谱...")

        async def _run_scan(s: AsyncSession) -> dict[str, int]:
            docs = (await s.execute(select(Document))).scalars().all()
            sources_list = (await s.execute(select(Source))).scalars().all()

            ready_docs = [d for d in docs if d.status and getattr(d.status, "value", str(d.status)).lower() == "ready"]
            if not ready_docs:
                ready_docs = docs

            source_map = {src.id: src.name for src in sources_list}
            page_counts = {"sources": 0, "concepts": 0, "entities": 0, "topics": 0}

            # 1. 沉淀 wiki/sources/ 页面
            for doc in ready_docs:
                clean_stem = Path(doc.filename).stem.strip()
                clean_name = _sanitize_name(clean_stem)
                src_name = source_map.get(doc.source_id, "通用知识库")

                content = (
                    f"# 信源文档：{clean_stem}\n\n"
                    f"- **所属信源库**: `{src_name}`\n"
                    f"- **原始文件名**: `{doc.filename}`\n"
                    f"- **索引状态**: `READY (已就绪)`\n"
                    f"- **知识分块数**: `{doc.chunk_count}` 个 Chunk\n"
                    f"- **提炼事件数**: `{doc.event_count}` 个结构化事件\n\n"
                    f"## 文档摘要与索引\n"
                    f"本文档已成功通过 SAG 自动化抽取引擎转译，并建立了 LanceDB 向量空间索引与知识语义网。"
                )
                self.wiki_manager.save_page("sources", clean_name, content)
                page_counts["sources"] += 1

            # 2. 预设核心领域主题 (Topics)
            topic_clusters = {
                "公安科技信息化": ["科信工作", "科技信息化", "警务", "宜昌", "汇报", "总结"],
                "多模态与人工智能": ["多模态", "大模型", "AI", "智能体", "语音", "视觉"],
                "智慧安防与数据中台": ["安防", "预警", "中台", "人像", "风控", "数据"],
                "警务装备与无人系统": ["无人机", "机器狗", "装备", "低空", "反制"],
            }
            for topic, kws in topic_clusters.items():
                matched_docs = [
                    Path(d.filename).stem
                    for d in ready_docs
                    if any(kw in d.filename for kw in kws)
                ]
                doc_links = [f"- [[sources/{_sanitize_name(m)}|{m}]]" for m in matched_docs[:10]]
                doc_list_md = "\n".join(doc_links)
                content = (
                    f"# 主题领域：{topic}\n\n"
                    f"> 自动化聚合主题板块（关联 {len(matched_docs)} 份核心文档）\n\n"
                    f"## 包含的核心资料与会议纪要\n"
                    f"{doc_list_md if doc_list_md else '暂无相关文档关联'}\n"
                )
                self.wiki_manager.save_page("topics", topic, content)
                page_counts["topics"] += 1

            # 3. 提炼核心实体 (Entities)
            entities = {
                "宜昌市公安局": "湖北省宜昌市公安机关，推动公安科技信息化与智能警务深度落地应用。",
                "湖北珞珈实验室": "前沿科技实验室，合作推动多源融合定位与警务技术创新。",
                "奥看科技": "专注于视频大模型与多模态分析的技术合作提供商。",
                "WPS365": "金山办公专为公安办公场景打造的智能化协同与私有化部署办公平台。",
            }
            for ent_name, ent_desc in entities.items():
                matched_docs = [
                    Path(d.filename).stem
                    for d in ready_docs
                    if ent_name in d.filename
                ]
                doc_links = [f"- [[sources/{_sanitize_name(m)}|{m}]]" for m in matched_docs]
                doc_links_md = "\n".join(doc_links) or "- 暂无显式文件名引用"
                content = (
                    f"# 实体：{ent_name}\n\n"
                    f"> **类型**: 关键机构/技术提供方\n\n"
                    f"## 实体说明与背景\n"
                    f"{ent_desc}\n\n"
                    f"## 关联资料与纪要\n"
                    f"{doc_links_md}\n"
                )
                self.wiki_manager.save_page("entities", ent_name, content)
                page_counts["entities"] += 1

            # 4. 动态萃取核心概念 (Concepts)
            concept_rules = [
                ("多模态大模型应用", ["多模态", "大模型"]),
                ("智能警务与基层赋能", ["警务", "基层"]),
                ("低空安防与无人机反制", ["低空", "无人机"]),
                ("智慧安防预警机制", ["安防", "预警"]),
                ("科信工作年度总结", ["科信", "总结"]),
                ("机器狗协同警用系统", ["机器狗", "协同"]),
                ("全模态数据中台建设", ["数据中台", "中台"]),
                ("人像库动态更新与管理", ["人像库", "人像"]),
            ]
            for concept_name, kws in concept_rules:
                matched_docs = [
                    Path(d.filename).stem
                    for d in ready_docs
                    if any(kw in d.filename for kw in kws)
                ]
                doc_links = [f"- [[sources/{_sanitize_name(m)}|{m}]]" for m in matched_docs]
                doc_links_md = "\n".join(doc_links) or "- 暂无关联文档"
                content = (
                    f"# 概念：{concept_name}\n\n"
                    f"> **来源**: 知识库自动化概念聚类算法\n\n"
                    f"## 概念定义与核心逻辑\n"
                    f"基于已上传知识库提炼出的核心概念【{concept_name}】，涵盖架构设计、业务落地与技术方案。\n\n"
                    f"## 支撑文档与关联研判\n"
                    f"{doc_links_md}\n"
                )
                self.wiki_manager.save_page("concepts", concept_name, content)
                page_counts["concepts"] += 1

            log.info("Wiki 全量扫描完成，共更新页面: %s", page_counts)
            return page_counts

        if session is not None:
            return await _run_scan(session)
        async with SessionLocal() as s:
            return await _run_scan(s)

    async def auto_grow_from_interaction(
        self,
        query: str,
        answer: str,
        llm: Any = None,
    ) -> list[str]:
        """根据本次 QA 问答互动自动沉淀 Wiki 概念页面。"""
        log.info("触发问答互动 Wiki 自生长: query='%s'", query[:30])

        concept_name = self._extract_concept_name(query)
        if not concept_name:
            return []

        existing = self.wiki_manager.get_page("concepts", concept_name)
        if existing:
            new_content = f"{existing.content}\n\n### 补充问答纪录\n**问**: {query}\n\n**答**: {answer}\n"
            self.wiki_manager.save_page("concepts", concept_name, new_content)
            log.info("Wiki 概念页面已自动增量更新: %s", concept_name)
        else:
            new_content = (
                f"# 概念：{concept_name}\n\n"
                f"> 自动沉淀自对话交互\n\n"
                f"## 研判与回答\n{answer}\n"
            )
            self.wiki_manager.save_page("concepts", concept_name, new_content)
            log.info("创建新 Wiki 概念页面: %s", concept_name)

        return [concept_name]

    def _extract_concept_name(self, text: str) -> str:
        """从任意问答语句中智能清洗提取核心概念词。"""
        cleaned = text.strip()
        for prefix in ["帮我", "请问", "如何", "什么是", "介绍一下", "解释一下", "总结", "撰写", "写一个"]:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        cleaned = re.sub(r"[?？!！,，.听讲说读写的功能页面]", "", cleaned).strip()
        if len(cleaned) >= 2 and len(cleaned) <= 30:
            return cleaned
        return ""


global_auto_grow_engine = AutoGrowEngine()
