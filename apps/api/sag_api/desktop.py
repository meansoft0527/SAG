"""Desktop sidecar entry point."""

from __future__ import annotations

import io
import os
import sys

import uvicorn


def _force_utf8_stdio() -> None:
    """Windows 下强制 stdout/stderr 使用 UTF-8，防止 emoji/中文日志触发 UnicodeEncodeError。"""
    os.environ.setdefault("PYTHONUTF8", "1")
    if sys.platform == "win32":
        for stream_name in ("stdout", "stderr"):
            stream = getattr(sys, stream_name, None)
            if stream is not None and hasattr(stream, "buffer"):
                try:
                    wrapped = io.TextIOWrapper(
                        stream.buffer, encoding="utf-8", errors="replace", line_buffering=True
                    )
                    setattr(sys, stream_name, wrapped)
                except Exception:
                    pass


def _port() -> int:
    value = os.getenv("SAG_DESKTOP_PORT", "8000")
    try:
        port = int(value)
    except ValueError as error:
        raise RuntimeError("SAG_DESKTOP_PORT must be an integer") from error
    if not 1 <= port <= 65535:
        raise RuntimeError("SAG_DESKTOP_PORT must be between 1 and 65535")
    return port


def main() -> None:
    _force_utf8_stdio()
    uvicorn.run(
        "sag_api.main:app",
        host=os.getenv("SAG_DESKTOP_HOST", "127.0.0.1"),
        port=_port(),
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
