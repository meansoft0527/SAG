"""测试 /writer API 端点：大纲生成、知识库 Wiki 沉淀与信源归档。"""

import pytest
from fastapi.testclient import TestClient

from sag_api.main import app

client = TestClient(app)


def test_writer_outline_endpoint():
    response = client.post(
        "/api/v1/writer/outline",
        json={
            "topic": "SAG 知识库向量索引与图谱检索性能剖析",
            "requirements": "受众：CTO；意图：技术剖析；字数：3000字 深度长文",
            "writer_mode": "deep_research",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "topic" in data
    assert len(data["outline"]) >= 3
    assert "title" in data["outline"][0]


def test_writer_save_to_kb_endpoint():
    response = client.post(
        "/api/v1/writer/save_to_kb",
        json={
            "title": "测试文章标题",
            "content": "# 测试文章正文\n\n测试内容沉淀。",
            "category": "topics",
            "keywords": ["单元测试", "智能写作"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["title"] == "测试文章标题"
    assert "wiki/topics/" in data["wiki_path"]
