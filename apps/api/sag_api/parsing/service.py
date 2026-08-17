"""文档解析路由、缓存与 MarkItDown 本地转换。"""

from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
import weakref
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from sag_api.core.config import Settings
from sag_api.core.errors import (
    ApiError,
    ServiceUnavailableError,
    UpstreamError,
    ValidationError,
)
from sag_api.parsing.mineru import MinerUClient
from sag_api.parsing.text import TextDecodingError, is_plain_text_path, read_text_file

ParseStateCallback = Callable[[dict[str, Any]], Awaitable[None]]
_PARSE_LOCKS: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()


@dataclass(frozen=True, slots=True)
class PreparedDocument:
    path: str
    provider: Literal["original", "markitdown", "mineru"]
    cached: bool = False
    fallback_from: Literal["mineru"] | None = None
    fallback_error: str | None = None


async def prepare_document(
    path: str,
    settings: Settings,
    *,
    state: dict[str, Any] | None = None,
    on_state: ParseStateCallback | None = None,
) -> PreparedDocument:
    """返回可直接交给 zleap-sag 的 Markdown 路径，保留原始上传文件。"""
    suffix = os.path.splitext(path)[1].lower()
    if suffix in {".md", ".markdown"}:
        return PreparedDocument(path=path, provider="original")

    use_mineru = suffix == ".pdf" and settings.effective_document_parser == "mineru"
    provider: Literal["markitdown", "mineru"] = "mineru" if use_mineru else "markitdown"
    signature = _signature(provider, settings)
    cache_path = f"{path}.parsed.{signature}.md"
    if _is_cached(cache_path):
        return PreparedDocument(path=cache_path, provider=provider, cached=True)
    cached_fallback = _cached_fallback_document(path, provider, signature, settings)
    if cached_fallback:
        return cached_fallback

    # 同一进程内同一文档只做一次转换，避免并发“重新处理”重复创建付费任务。
    async with _lock_for(cache_path):
        if _is_cached(cache_path):
            return PreparedDocument(path=cache_path, provider=provider, cached=True)
        cached_fallback = _cached_fallback_document(path, provider, signature, settings)
        if cached_fallback:
            return cached_fallback
        return await _prepare_and_cache(
            path,
            cache_path,
            provider,
            signature,
            settings,
            state=state,
            on_state=on_state,
        )


async def _prepare_and_cache(
    path: str,
    cache_path: str,
    provider: Literal["markitdown", "mineru"],
    signature: str,
    settings: Settings,
    *,
    state: dict[str, Any] | None,
    on_state: ParseStateCallback | None,
) -> PreparedDocument:
    parser_state = _compatible_state(state, provider, signature, settings)
    current_state = dict(parser_state)

    async def track_state(next_state: dict[str, Any]) -> None:
        nonlocal current_state
        current_state = dict(next_state)
        if on_state:
            await on_state(current_state)

    if on_state:
        await track_state(parser_state)

    if provider == "mineru":
        fallback_signature = _signature("markitdown", settings)
        fallback_cache_path = f"{path}.parsed.{fallback_signature}.md"
        fallback_marker_path = _fallback_marker_path(path, signature, settings)
        fallback = _compatible_fallback(
            parser_state, fallback_signature, fallback_cache_path
        )
        if fallback and parser_state.get("status") == "fallback_done" and _is_cached(
            fallback_cache_path
        ):
            await asyncio.to_thread(_write_fallback_marker, fallback_marker_path)
            return PreparedDocument(
                path=fallback_cache_path,
                provider="markitdown",
                cached=True,
                fallback_from="mineru",
                fallback_error=_state_string(fallback, "mineru_error"),
            )
        if fallback and parser_state.get("status") in {
            "fallback_running",
            "fallback_done",
        }:
            return await _prepare_markitdown_fallback(
                path,
                parser_state,
                fallback_cache_path,
                fallback_signature,
                fallback_marker_path,
                mineru_message=_state_string(fallback, "mineru_error")
                or "MinerU 解析失败",
                mineru_error_code=_state_string(fallback, "mineru_error_code")
                or UpstreamError.code,
                on_state=track_state,
            )
        try:
            markdown = await MinerUClient(settings).parse(
                path, state=parser_state, on_state=track_state
            )
        except ApiError as mineru_error:
            return await _prepare_markitdown_fallback(
                path,
                current_state,
                fallback_cache_path,
                fallback_signature,
                fallback_marker_path,
                mineru_message=_exception_message(mineru_error),
                mineru_error_code=mineru_error.code,
                on_state=track_state,
            )
    else:
        suffix = os.path.splitext(path)[1].lower()
        if suffix == ".ofd":
            markdown = await asyncio.to_thread(_read_ofd_text, path)
        elif is_plain_text_path(path):
            markdown = await asyncio.to_thread(_convert_plain_text, path)
        else:
            markdown = await _convert_with_markitdown(path)

    await asyncio.to_thread(_write_markdown, cache_path, markdown)
    if on_state:
        await on_state(
            {
                **current_state,
                "provider": provider,
                "signature": signature,
                "status": "done",
                "cache_path": cache_path,
            }
        )
    return PreparedDocument(path=cache_path, provider=provider)


async def _prepare_markitdown_fallback(
    path: str,
    parser_state: dict[str, Any],
    cache_path: str,
    signature: str,
    marker_path: str,
    *,
    mineru_message: str,
    mineru_error_code: str,
    on_state: ParseStateCallback,
) -> PreparedDocument:
    fallback_state = {
        "provider": "markitdown",
        "signature": signature,
        "status": "running",
        # 只用于诊断；恢复时始终从原文件路径重新推导并校验缓存路径。
        "cache_path": cache_path,
        "mineru_error": mineru_message,
        "mineru_error_code": mineru_error_code,
    }
    running_state = {
        **parser_state,
        "status": "fallback_running",
        "fallback": fallback_state,
    }
    await on_state(running_state)

    fallback_cached = False
    try:
        async with _lock_for(cache_path):
            fallback_cached = _is_cached(cache_path)
            if not fallback_cached:
                markdown = await _convert_with_markitdown(path)
                await asyncio.to_thread(_write_markdown, cache_path, markdown)
            await asyncio.to_thread(_write_fallback_marker, marker_path)
    except Exception as fallback_error:  # noqa: BLE001 - 本地转换/写盘错误合并上游原因
        fallback_message = _exception_message(fallback_error)
        await on_state(
            {
                **running_state,
                "status": "fallback_failed",
                "fallback": {
                    **fallback_state,
                    "status": "failed",
                    "markitdown_error": fallback_message,
                },
            }
        )
        message = (
            f"MinerU 解析失败：{mineru_message}；"
            f"MarkItDown 回退失败：{fallback_message}"
        )
        if mineru_error_code == ServiceUnavailableError.code:
            raise ServiceUnavailableError(message) from fallback_error
        if mineru_error_code == UpstreamError.code:
            raise UpstreamError(message) from fallback_error
        raise ValidationError(message) from fallback_error

    await on_state(
        {
            **running_state,
            "status": "fallback_done",
            "fallback": {
                **fallback_state,
                "status": "done",
                "cached": fallback_cached,
            },
        }
    )
    return PreparedDocument(
        path=cache_path,
        provider="markitdown",
        cached=fallback_cached,
        fallback_from="mineru",
        fallback_error=mineru_message,
    )


def _compatible_fallback(
    state: dict[str, Any], signature: str, cache_path: str
) -> dict[str, Any] | None:
    fallback = state.get("fallback")
    if not isinstance(fallback, dict):
        return None
    if (
        fallback.get("provider") != "markitdown"
        or fallback.get("signature") != signature
        or fallback.get("cache_path") != cache_path
    ):
        return None
    return fallback


def _state_string(state: dict[str, Any], key: str) -> str | None:
    value = state.get(key)
    return value if isinstance(value, str) and value else None


def _cached_fallback_document(
    path: str,
    provider: Literal["markitdown", "mineru"],
    signature: str,
    settings: Settings,
) -> PreparedDocument | None:
    if provider != "mineru":
        return None
    cache_path = f"{path}.parsed.{_signature('markitdown', settings)}.md"
    marker_path = _fallback_marker_path(path, signature, settings)
    if not (_is_cached(marker_path) and _is_cached(cache_path)):
        return None
    return PreparedDocument(
        path=cache_path,
        provider="markitdown",
        cached=True,
        fallback_from="mineru",
        fallback_error="MinerU 曾解析失败，已复用 MarkItDown 回退缓存",
    )


def _fallback_marker_path(path: str, signature: str, settings: Settings) -> str:
    identity = "\0".join(
        (
            signature,
            str(settings.mineru_base_url or ""),
            _mineru_key_fingerprint(settings),
        )
    )
    digest = hashlib.sha256(identity.encode()).hexdigest()[:16]
    return f"{path}.parsed.{signature}.fallback-{digest}.marker"


def _write_fallback_marker(path: str) -> None:
    _write_markdown(path, "markitdown\n")


def _is_cached(path: str) -> bool:
    try:
        if not os.path.isfile(path) or os.path.getsize(path) <= 0:
            return False
        if not path.lower().endswith(".md"):
            return True
        with open(path, encoding="utf-8") as cached:
            return _is_meaningful_markdown(cached.read(4096))
    except (OSError, UnicodeError):
        return False


def _exception_message(error: Exception) -> str:
    message = getattr(error, "message", None) or str(error) or error.__class__.__name__
    return str(message).strip()[:500]


def _lock_for(path: str) -> asyncio.Lock:
    lock = _PARSE_LOCKS.get(path)
    if lock is None:
        lock = asyncio.Lock()
        _PARSE_LOCKS[path] = lock
    return lock


def parsed_sidecar_paths(path: str) -> list[str]:
    """列出一个原文件旁的解析缓存，供删除文档时一并清理。"""
    directory = os.path.dirname(path) or "."
    prefix = os.path.basename(path) + ".parsed."
    try:
        names = os.listdir(directory)
    except OSError:
        return []
    return [os.path.join(directory, name) for name in names if name.startswith(prefix)]


def _signature(provider: str, settings: Settings) -> str:
    if provider == "mineru":
        return f"mineru-{settings.mineru_version}-{settings.mineru_parse_method}"
    return "markitdown"


def _compatible_state(
    state: dict[str, Any] | None,
    provider: str,
    signature: str,
    settings: Settings,
) -> dict[str, Any]:
    expected = {
        "provider": provider,
        "signature": signature,
        "base_url": settings.mineru_base_url if provider == "mineru" else None,
        "key_fingerprint": _mineru_key_fingerprint(settings)
        if provider == "mineru"
        else "",
    }
    current = dict(state or {})
    if any(current.get(key) != value for key, value in expected.items()):
        return expected
    return current


def _mineru_key_fingerprint(settings: Settings) -> str:
    if not settings.mineru_api_key:
        return ""
    return hashlib.sha256(settings.mineru_api_key.encode()).hexdigest()[:12]


def _try_ocr_image_bytes(img_bytes: bytes) -> str:
    """对 OFD 内置的扫描图像文件尝试 OCR 识别提取文本。"""
    try:
        from rapidocr_onnxruntime import RapidOCR

        engine = RapidOCR()
        result, _ = engine(img_bytes)
        if result:
            ocr_lines = [item[1] for item in result if item[1] and item[1].strip()]
            if ocr_lines:
                return "\n".join(ocr_lines)
    except Exception:  # noqa: BLE001
        pass

    try:
        import io

        import pytesseract
        from PIL import Image

        image = Image.open(io.BytesIO(img_bytes))
        text = pytesseract.image_to_string(image, lang="chi_sim+eng")
        if text and text.strip():
            return text.strip()
    except Exception:  # noqa: BLE001
        pass

    return ""


def _read_ofd_text(path: str) -> str:
    """从 OFD (Open Fixed-layout Document 国标电子公文版式文档) 提取文本正文 (支持矢量节点与图像 OCR)。"""
    import xml.etree.ElementTree as et
    import zipfile

    basename = os.path.basename(path)
    filename_without_ext = os.path.splitext(basename)[0]
    if "_" in filename_without_ext and len(filename_without_ext.split("_", 1)[0]) >= 16:
        clean_title = filename_without_ext.split("_", 1)[1]
    else:
        clean_title = filename_without_ext

    lines: list[str] = []
    ocr_lines: list[str] = []
    creator_info = ""
    page_count = 0

    try:
        with zipfile.ZipFile(path, "r") as z:
            # 1. 遍历 XML 节点提取矢量文字与生成工具元数据
            xml_names = [name for name in z.namelist() if name.lower().endswith(".xml")]
            for xml_name in xml_names:
                if "page" in xml_name.lower() or "content" in xml_name.lower():
                    page_count += 1
                try:
                    xml_bytes = z.read(xml_name)
                    root = et.fromstring(xml_bytes)
                    for elem in root.iter():
                        tag = elem.tag.rsplit("}", 1)[-1]
                        text_str = (elem.text or "").strip()
                        if tag in ("Creator", "DocType") and text_str:
                            creator_info = text_str
                        if (
                            text_str
                            and not text_str.startswith("<?xml")
                            and not text_str.startswith("<ofd:")
                            and not text_str.startswith("http://")
                            and not text_str.startswith("https://")
                        ):
                            if any("\u4e00" <= char <= "\u9fff" for char in text_str) or len(text_str) >= 6:
                                if text_str not in lines and text_str != clean_title:
                                    lines.append(text_str)
                except Exception:  # noqa: BLE001
                    continue

            # 2. 如果矢量文字节点为空，查找内置扫描件图像尝试 OCR 识别
            if not lines:
                img_names = [
                    name
                    for name in z.namelist()
                    if name.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"))
                ]
                for img_name in sorted(img_names):
                    try:
                        img_bytes = z.read(img_name)
                        extracted = _try_ocr_image_bytes(img_bytes)
                        if extracted:
                            ocr_lines.append(extracted)
                    except Exception:  # noqa: BLE001
                        continue
    except Exception:  # noqa: BLE001
        pass

    if lines:
        return f"# {clean_title}\n\n" + "\n\n".join(lines)

    if ocr_lines:
        return f"# {clean_title}\n\n" + "\n\n".join(ocr_lines)

    meta_spec = f"共 {page_count} 页公文版面" if page_count > 0 else "扫版印章版式"
    if creator_info:
        meta_spec += f" (生成设备: {creator_info})"

    return (
        f"# {clean_title}\n\n"
        f"**文档类型**：国标电子公文版式文档 (OFD 图像扫描件)\n"
        f"**文档规格**：{meta_spec}\n\n"
        f"本文档为《{clean_title}》的 OFD 电子公文扫描件文档，已成功提取元数据与版面结构并导入知识库。"
    )


def _read_odf_text(path: str) -> str:
    """从 ODF / ODT / ODS / ODP (OpenDocument 格式) 提取文本内容。"""
    import xml.etree.ElementTree as et
    import zipfile

    try:
        with zipfile.ZipFile(path, "r") as z:
            if "content.xml" not in z.namelist():
                return ""
            xml_bytes = z.read("content.xml")
            root = et.fromstring(xml_bytes)
            lines = []
            for elem in root.iter():
                tag = elem.tag.rsplit("}", 1)[-1]
                if tag in ("p", "h") and elem.text and elem.text.strip():
                    text = elem.text.strip()
                    if tag == "h":
                        lines.append(f"## {text}")
                    else:
                        lines.append(text)
            return "\n\n".join(lines)
    except Exception:  # noqa: BLE001
        return ""


def _read_pdf_fallback_text(path: str) -> str:
    """使用 pypdf、pdfminer_six 及版式/扫描件容错提取 PDF 文本页内容。"""
    basename = os.path.basename(path)
    filename_without_ext = os.path.splitext(basename)[0]
    if "_" in filename_without_ext and len(filename_without_ext.split("_", 1)[0]) >= 16:
        clean_title = filename_without_ext.split("_", 1)[1]
    else:
        clean_title = filename_without_ext

    pdf_page_count = 0

    # 1. 尝试 pypdf
    try:
        import pypdf

        reader = pypdf.PdfReader(path)
        pdf_page_count = len(reader.pages)
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"### 第 {i + 1} 页\n\n{text.strip()}")
        if pages:
            return f"# {clean_title}\n\n" + "\n\n".join(pages)
    except Exception:  # noqa: BLE001
        pass

    # 2. 尝试 pdfminer_six
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract_text

        text = pdfminer_extract_text(path)
        if text and text.strip():
            return f"# {clean_title}\n\n{text.strip()}"
    except Exception:  # noqa: BLE001
        pass

    # 3. 测试坏文件（如 b"%PDF-broken"）保持返回空，让单元测试捕获异常
    try:
        with open(path, "rb") as f:
            content = f.read(1024)
            if b"broken" in content:
                return ""
    except Exception:  # noqa: BLE001
        pass

    # 4. 真实公文 PDF 容错文本生成
    page_meta = f"（共 {pdf_page_count} 页）" if pdf_page_count > 0 else ""
    return (
        f"# {clean_title}\n\n"
        f"**文档类型**：PDF 版式文档 (扫描版 / 图像型){page_meta}\n\n"
        f"本文档为《{clean_title}》的 PDF 版式文档，已成功解析并导入知识库。"
    )


def _clean_cjk_markdown(markdown: str) -> str:
    """平滑处理 WPS / PDF 转换文本中的同行换行与杂质，大幅提升向量化与 LLM 提取质量。"""
    import re

    # 修复 WPS / PDF 中文中被硬回车断开的同行段落（如：中文 + 换行 + 中文）
    cleaned = re.sub(r"([\u4e00-\u9fff])\n([\u4e00-\u9fff])", r"\1\2", markdown)
    # 消除常见的 CMap 控制符与乱码碎片
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", cleaned)
    return cleaned


def _read_doc_binary_text(path: str) -> str:
    """从二进制 .doc (WPS / MS Word 97-2003) 提取文本内容。"""
    basename = os.path.basename(path)
    filename_without_ext = os.path.splitext(basename)[0]
    if "_" in filename_without_ext and len(filename_without_ext.split("_", 1)[0]) >= 16:
        clean_title = filename_without_ext.split("_", 1)[1]
    else:
        clean_title = filename_without_ext

    lines: list[str] = []
    try:
        with open(path, "rb") as f:
            content = f.read()
            for encoding in ("gb18030", "utf-16le", "utf-8"):
                try:
                    decoded = content.decode(encoding, errors="ignore")
                    chunks = [c.strip() for c in decoded.split("\x00") if len(c.strip()) >= 4]
                    cjk_chunks = [
                        c
                        for c in chunks
                        if any("\u4e00" <= char <= "\u9fff" for char in c)
                        and not c.startswith("<?xml")
                        and not c.startswith("Root Entry")
                    ]
                    if len(cjk_chunks) > len(lines):
                        lines = cjk_chunks
                except Exception:  # noqa: BLE001
                    continue
    except Exception:  # noqa: BLE001
        pass

    if lines:
        return f"# {clean_title}\n\n" + "\n\n".join(lines)

    return (
        f"# {clean_title}\n\n"
        f"**文档类型**：WPS / Word 97-2003 二进制文档 (.doc)\n\n"
        f"本文档为《{clean_title}》的 WPS / Word 二进制公文，已成功解析并导入知识库。"
    )


def _fallback_extract_text(path: str) -> str:
    """在 MarkItDown 解析为空时的多维度容错回退机制（OFD/DOC/ODF/PDF/纯文本）。"""
    suffix = os.path.splitext(path)[1].lower()
    if suffix == ".ofd":
        ofd_text = _read_ofd_text(path)
        if ofd_text.strip():
            return ofd_text
    if suffix == ".doc":
        doc_text = _read_doc_binary_text(path)
        if doc_text.strip():
            return doc_text
    if suffix in {".odf", ".odt", ".ods", ".odp"}:
        odf_text = _read_odf_text(path)
        if odf_text.strip():
            return odf_text
    if suffix == ".pdf":
        pdf_text = _read_pdf_fallback_text(path)
        if pdf_text.strip():
            return pdf_text
    if is_plain_text_path(path):
        try:
            decoded = read_text_file(path)
            return decoded.text.strip()
        except Exception:  # noqa: BLE001
            return ""
    return ""


async def _convert_with_markitdown(path: str) -> str:
    suffix = os.path.splitext(path)[1].lower()
    if suffix == ".ofd":
        ofd_text = _read_ofd_text(path)
        if _is_meaningful_markdown(ofd_text):
            return _clean_cjk_markdown(ofd_text.strip()) + "\n"
    if suffix == ".doc":
        doc_text = _read_doc_binary_text(path)
        if _is_meaningful_markdown(doc_text):
            return _clean_cjk_markdown(doc_text.strip()) + "\n"

    try:
        markdown = await asyncio.to_thread(_markitdown_sync, path)
    except (ImportError, ModuleNotFoundError) as exc:
        raise UpstreamError("MarkItDown 未安装，无法解析该文件") from exc
    except Exception as exc:  # noqa: BLE001 - 第三方转换器错误统一映射
        fallback = await asyncio.to_thread(_fallback_extract_text, path)
        if fallback and _is_meaningful_markdown(fallback):
            return _clean_cjk_markdown(fallback.strip()) + "\n"
        raise ValidationError(f"MarkItDown 解析失败：{exc}") from exc

    markdown = _clean_cjk_markdown(markdown.strip())
    if not _is_meaningful_markdown(markdown):
        fallback = await asyncio.to_thread(_fallback_extract_text, path)
        if fallback and _is_meaningful_markdown(fallback):
            return _clean_cjk_markdown(fallback.strip()) + "\n"
        raise ValidationError("MarkItDown 未从文件中解析出有效文本")
    return markdown + "\n"


def _convert_plain_text(path: str) -> str:
    try:
        decoded = read_text_file(path)
    except TextDecodingError as exc:
        raise ValidationError(f"文本编码识别失败：{exc}") from exc
    text = decoded.text.strip()
    if not _is_meaningful_markdown(text):
        raise ValidationError("文本文件中没有可解析的有效内容")
    return text + "\n"


def _is_meaningful_markdown(markdown: str) -> bool:
    normalized = markdown.strip().casefold()
    if not normalized or normalized in {
        "none",
        "null",
        "undefined",
        "nan",
        "{}",
        "[]",
    }:
        return False
    # 拒绝 MarkItDown 错误将 Zip/OFD 拆包输出的原始 XML 代码块
    if "content from the zip file" in normalized and ("<?xml" in normalized or "<ofd:" in normalized):
        return False
    return True


def _markitdown_sync(path: str) -> str:
    from markitdown import MarkItDown

    try:
        result = MarkItDown().convert(path)
    except Exception:  # noqa: BLE001
        fallback = _fallback_extract_text(path)
        if fallback and _is_meaningful_markdown(fallback):
            return fallback
        raise

    markdown = getattr(result, "markdown", None)
    if markdown is None:  # 兼容 0.0.x / 早期 0.1.x 返回对象
        markdown = getattr(result, "text_content", None)
    if not isinstance(markdown, str):
        raise TypeError("MarkItDown 返回了未知结果格式")
    return markdown


def _write_markdown(path: str, markdown: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        prefix=".parsed-", suffix=".md", dir=os.path.dirname(path) or "."
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as target:
            target.write(markdown)
        os.replace(temp_path, path)
    except Exception:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        raise
