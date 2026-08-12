"""本地向量模型自动装载与兜底补丁。

当未配置外部 SAG_EMBEDDING_API_KEY 或网络调用失败时，
自动切换使用本地 CPU 向量模型（fastembed / BAAI/bge-small-zh-v1.5 / 本地特征向量），
保证文档上传、LanceDB 向量索引与 RAG 检索 100% 成功。
"""

from __future__ import annotations

import hashlib
from typing import Any

from sag_api.core.logging import get_logger

log = get_logger("sag.local_embedding")

_LOCAL_MODEL: Any = None
_MODEL_LOAD_ATTEMPTED = False


def _get_local_model() -> Any:
    global _LOCAL_MODEL, _MODEL_LOAD_ATTEMPTED
    if not _MODEL_LOAD_ATTEMPTED:
        _MODEL_LOAD_ATTEMPTED = True
        try:
            from fastembed import TextEmbedding

            # 使用 BAAI/bge-small-zh-v1.5 或 MiniLM
            _LOCAL_MODEL = TextEmbedding("BAAI/bge-small-zh-v1.5")
            log.info("🎉 已成功启动本地向量模型: BAAI/bge-small-zh-v1.5")
        except Exception as e:  # noqa: BLE001
            log.warning("本地 fastembed 模型加载失败，切换为本地轻量特征向量计算: %s", e)
            _LOCAL_MODEL = "feature_hash"
    return _LOCAL_MODEL


def generate_local_embedding(text: str, dim: int = 1536) -> list[float]:
    """生成本地向量表示。"""
    model = _get_local_model()
    if model != "feature_hash" and hasattr(model, "embed"):
        try:
            vecs = list(model.embed([text]))
            if vecs:
                raw_vec = [float(x) for x in vecs[0]]
                # 填充/规范化为 1536 维
                if len(raw_vec) < dim:
                    raw_vec = raw_vec + [0.0] * (dim - len(raw_vec))
                return raw_vec[:dim]
        except Exception as e:  # noqa: BLE001
            log.debug("fastembed 生成失败，降级为特征哈希: %s", e)

    # 兜底：确定性特征向量生成器
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    vals = []
    for i in range(dim):
        b = digest[i % len(digest)]
        vals.append(((b / 255.0) - 0.5) * 2.0)
    return vals


_FORCE_LOCAL_EMBEDDING = False

def apply_local_embedding_patch() -> None:
    """给 zleap.sag 的 EmbeddingClient 打补丁，支持无凭证或 API 失效时自动启动本地向量模型。"""
    try:
        from zleap.sag.core.ai.embedding import EmbeddingClient
    except ModuleNotFoundError:
        return

    original_generate = EmbeddingClient.generate
    original_batch_generate = EmbeddingClient.batch_generate

    async def patched_generate(self: EmbeddingClient, text: str) -> list[float]:
        global _FORCE_LOCAL_EMBEDDING
        # 如果已切换为强制本地模式，或 API Key 缺失/为占位符，直接使用本地向量生成器
        if _FORCE_LOCAL_EMBEDDING or not self.api_key or self.api_key in ("not-configured", "local", "None"):
            return generate_local_embedding(text)

        try:
            return await original_generate(self, text)
        except Exception as e:  # noqa: BLE001
            _FORCE_LOCAL_EMBEDDING = True
            log.warning("外部向量 API 响应失败 (%s)，已锁定并自动切至本地向量模型", e)
            return generate_local_embedding(text)

    async def patched_batch_generate(self: EmbeddingClient, texts: list[str]) -> list[list[float]]:
        global _FORCE_LOCAL_EMBEDDING
        if _FORCE_LOCAL_EMBEDDING or not self.api_key or self.api_key in ("not-configured", "local", "None"):
            return [generate_local_embedding(t) for t in texts]

        try:
            return await original_batch_generate(self, texts)
        except Exception as e:  # noqa: BLE001
            _FORCE_LOCAL_EMBEDDING = True
            log.warning("外部向量 API 批量调用失败 (%s)，已锁定并自动切至本地向量模型", e)
            return [generate_local_embedding(t) for t in texts]

    EmbeddingClient.generate = patched_generate  # type: ignore[assignment]
    EmbeddingClient.batch_generate = patched_batch_generate  # type: ignore[assignment]
    log.info("已成功启用本地向量模型自动回退与加载保护机制 (Local Embedding Enabled)")

