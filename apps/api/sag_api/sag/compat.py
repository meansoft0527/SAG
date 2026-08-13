"""Compatibility shims for dependency-owned zleap-sag behavior.

These patches live at the application boundary so we can keep user workflows
working while waiting for upstream package releases.
"""

from __future__ import annotations

import copy
from typing import Any

from sag_api.core.logging import get_logger

log = get_logger("sag.compat")





def _llm_model_name(client: Any) -> str:
    current = client
    while current is not None:
        model = getattr(getattr(current, "config", None), "model", None)
        if isinstance(model, str) and model:
            return model
        current = getattr(current, "client", None)
    return ""


def _uses_deepseek(client: Any) -> bool:
    return "deepseek" in _llm_model_name(client).rsplit("/", 1)[-1].casefold()


def _is_json_schema_response_format_unsupported(error: Exception) -> bool:
    """Only downgrade the known structured-output capability rejection."""
    message = str(error).casefold()
    return "response_format" in message and (
        "unavailable" in message or "not support" in message or "unsupported" in message
    )


def _validate_response_schema(result: Any, schema: dict[str, Any]) -> None:
    """Keep local validation when the provider only guarantees a JSON object."""
    try:
        import jsonschema
    except ImportError:
        expected_type = schema.get("type")
        if expected_type == "object" and not isinstance(result, dict):
            raise ValueError("响应类型不符合Schema: 期望 object") from None
        if expected_type == "array" and not isinstance(result, list):
            raise ValueError("响应类型不符合Schema: 期望 array") from None
        return
    jsonschema.validate(instance=result, schema=schema)


def _without_required_field(node: dict[str, Any], field: str) -> bool:
    required = node.get("required")
    if not isinstance(required, list) or field not in required:
        return False
    node["required"] = [item for item in required if item != field]
    return True


def _looks_like_extract_response_schema(schema: Any) -> bool:
    if not isinstance(schema, dict):
        return False
    data = schema.get("properties", {}).get("data")
    if not isinstance(data, dict):
        return False
    data_props = data.get("properties")
    return (
        schema.get("type") == "object"
        and schema.get("properties", {}).get("type", {}).get("const") == "response"
        and isinstance(data_props, dict)
        and "items" in data_props
        and "meta" in data_props
    )


# Event fields upstream marks required but validates as warning-only in
# ``_validate_output``.  Enforcing them as a strict structured-output schema
# makes providers reject otherwise-usable chunks and retry to the limit, so a
# single omitted field discards the whole chunk.  We relax them to match what
# upstream actually tolerates, then backfill defaults in ``_repair_extract_response``.
_SOFT_EVENT_FIELDS = ("references", "title", "content", "is_valid")


def _relax_extract_schema(schema: dict[str, Any]) -> dict[str, Any]:
    relaxed = copy.deepcopy(schema)
    data = relaxed.get("properties", {}).get("data")
    if isinstance(data, dict):
        _without_required_field(data, "meta")
        meta = data.get("properties", {}).get("meta")
        if isinstance(meta, dict):
            _without_required_field(meta, "reason")
    event = relaxed.get("definitions", {}).get("event")
    if isinstance(event, dict):
        for field in _SOFT_EVENT_FIELDS:
            _without_required_field(event, field)
        # Drop the ``minItems: 1`` floor on references: upstream only warns on
        # empty references, it never fails validation on them.
        references = event.get("properties", {}).get("references")
        if isinstance(references, dict):
            references.pop("minItems", None)
    return relaxed


def _repair_extract_response(result: Any) -> set[str]:
    repaired: set[str] = set()
    if not isinstance(result, dict) or result.get("type") != "response":
        return repaired
    data = result.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return repaired
    meta = data.get("meta")
    if not isinstance(meta, dict):
        data["meta"] = {"reason": "model omitted data.meta; filled by SAG compatibility layer"}
        meta = data["meta"]
        repaired.add("data.meta")
    reason = meta.get("reason")
    if not isinstance(reason, str):
        meta["reason"] = ""
        repaired.add("data.meta.reason")

    def repair_item(item: Any) -> None:
        if not isinstance(item, dict):
            return
        if "is_valid" not in item:
            item["is_valid"] = True
            repaired.add("data.items[].is_valid")
        # Backfill the warning-only fields so the item stays schema-shaped for
        # the downstream parser even when the model dropped them.
        if not isinstance(item.get("references"), list):
            item["references"] = []
            repaired.add("data.items[].references")
        if not isinstance(item.get("title"), str):
            item["title"] = ""
            repaired.add("data.items[].title")
        if not isinstance(item.get("content"), str):
            item["content"] = ""
            repaired.add("data.items[].content")
        children = item.get("children")
        if isinstance(children, list):
            for child in children:
                repair_item(child)

    for item in data["items"]:
        repair_item(item)
    return repaired


def _matches_filter(row: dict[str, Any], filter_query: dict[str, Any] | None) -> bool:
    if not filter_query or not isinstance(filter_query, dict):
        return True
    if "terms" in filter_query:
        for f, vals in filter_query["terms"].items():
            key = f.removesuffix(".keyword")
            if key == "_id":
                key = "id"
            if key in row:
                val = row[key]
                if isinstance(vals, (list, tuple, set)):
                    if val not in vals:
                        return False
                elif val != vals:
                    return False
    if "term" in filter_query:
        for f, v in filter_query["term"].items():
            key = f.removesuffix(".keyword")
            if key == "_id":
                key = "id"
            target_val = v.get("value") if isinstance(v, dict) else v
            if key in row and row[key] != target_val:
                return False
    return True


async def _numpy_pyarrow_vector_search(
    store: Any,
    index: str,
    field: str,
    vector: list[float],
    size: int = 10,
    filter_query: dict[str, Any] | None = None,
    include_vector: bool = False,
) -> list[dict[str, Any]]:
    import numpy as np

    tbl = await store._open_table(index)
    if tbl is None:
        return []
    await store._cache_schema(tbl)

    try:
        arrow_table = await tbl.to_arrow()
    except Exception as e:
        log.warning("PyArrow 读取 LanceDB 表 '%s' 失败：%s", index, e)
        return []

    if arrow_table.num_rows == 0:
        return []

    col_name = store._ident(field) if store._ident(field) in store._vector_columns(tbl) else None
    if not col_name:
        vec_cols = sorted(store._vector_columns(tbl))
        if vec_cols:
            col_name = vec_cols[0]

    if not col_name or col_name not in arrow_table.column_names:
        return []

    raw_vecs = arrow_table[col_name].to_pylist()
    valid_indices = [i for i, v in enumerate(raw_vecs) if v is not None and len(v) > 0]
    if not valid_indices:
        return []

    matrix = np.array([raw_vecs[i] for i in valid_indices], dtype=np.float32)
    q = np.array(vector, dtype=np.float32)

    q_norm = np.linalg.norm(q)
    if q_norm > 0:
        q = q / q_norm

    m_norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    m_norms[m_norms == 0] = 1.0
    matrix_normed = matrix / m_norms

    scores = np.dot(matrix_normed, q)
    ranked_order = np.argsort(scores)[::-1]

    schema_fields = [n for n, _ in store._schema_fields(tbl)]
    vector_cols = store._vector_columns(tbl)
    pydict = arrow_table.to_pydict()

    results: list[dict[str, Any]] = []
    for rank_idx in ranked_order:
        real_idx = valid_indices[rank_idx]
        score = float(scores[rank_idx])
        row = {}
        for col in schema_fields:
            if not include_vector and col in vector_cols:
                continue
            row[col] = pydict[col][real_idx]
        if not _matches_filter(row, filter_query):
            continue
        row["_score"] = score
        results.append(row)
        if len(results) >= int(size):
            break

    return results


def install_lancedb_safe_vector_search_compat() -> None:
    """使用纯 Python PyArrow/NumPy 余弦计算替代 LanceDB 原生 C SIMD 检索，
    消除 STATUS_ILLEGAL_INSTRUCTION 崩溃硬杀。"""
    try:
        from zleap.sag.core.storage.lancedb_store import LanceDBStore
    except ImportError:
        return

    original_search = getattr(LanceDBStore, "vector_search", None)
    if getattr(original_search, "_sag_api_safe_vector_search", False):
        return

    async def _safe_vector_search(
        self: Any,
        index: str,
        field: str,
        vector: list[float],
        size: int = 10,
        filter_query: dict[str, Any] | None = None,
        routing: str | None = None,
        include_vector: bool = False,
    ) -> list[dict[str, Any]]:
        return await _numpy_pyarrow_vector_search(
            self,
            index,
            field,
            vector,
            size=size,
            filter_query=filter_query,
            include_vector=include_vector,
        )

    _safe_vector_search._sag_api_safe_vector_search = True  # type: ignore[attr-defined]
    LanceDBStore.vector_search = _safe_vector_search
    log.info("🎉 已成功激活 LanceDB 硬件安全向量检索补丁 (PyArrow + NumPy Cosine Search Engine Enabled)")


def install_zleap_sag_extract_compat() -> None:
    """Allow event extraction to accept minor omissions in model output."""

    install_lancedb_safe_vector_search_compat()

    from zleap.sag.modules.extract.processor import EventProcessor

    current = EventProcessor._call_llm_with_retry
    if getattr(current, "_sag_api_extract_meta_compat", False):
        return

    async def _patched_call_llm_with_retry(self, messages, schema):  # type: ignore[no-untyped-def]
        active_schema = schema
        if _looks_like_extract_response_schema(schema):
            active_schema = _relax_extract_schema(schema)
        if _uses_deepseek(self.llm_client):
            log.info("DeepSeek 固定使用 response_format=json_object")
            result = await self.llm_client.chat_with_schema(
                messages,
                response_schema=None,
                response_format={"type": "json_object"},
            )
            _validate_response_schema(result, active_schema)
        else:
            try:
                result = await current(self, messages, active_schema)
            except Exception as error:
                if not _is_json_schema_response_format_unsupported(error):
                    raise
                log.warning("模型不支持 response_format=json_schema，降级为 json_object")
                result = await self.llm_client.chat_with_schema(
                    messages,
                    response_schema=None,
                    response_format={"type": "json_object"},
                )
                _validate_response_schema(result, active_schema)
        repaired = _repair_extract_response(result)
        if repaired:
            log.info("已兼容补齐 zleap-sag 事项抽取响应字段：%s", ", ".join(sorted(repaired)))
        return result

    _patched_call_llm_with_retry._sag_api_extract_meta_compat = True  # type: ignore[attr-defined]
    EventProcessor._call_llm_with_retry = _patched_call_llm_with_retry
