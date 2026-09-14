"""GB2Text Agent API — программный доступ к core без GUI.

REPL/Jupyter-first интерфейс:
    import api
    info = api.detect("rom.gba")
    result = api.extract("rom.gba")
    report = api.inject("rom.gba", result["segments"])

Все функции валидируют пути (resolve/симлинки/размер/расширение) и поднимают
`api.SDKError` с кодом контракта (PLUGIN_NOT_FOUND, IO_ERROR, ...).
"""

from api._core import (
    C_INTERNAL,
    C_IO_ERROR,
    C_PLUGIN_NOT_FOUND,
    C_ROM_ERROR,
    C_UNSUPPORTED_SYSTEM,
    C_VALIDATION_ERROR,
    SDKError,
    detect,
    extract,
    get_version,
    inject,
    list_plugins,
)

__all__ = [
    "C_INTERNAL",
    "C_IO_ERROR",
    "C_PLUGIN_NOT_FOUND",
    "C_ROM_ERROR",
    "C_UNSUPPORTED_SYSTEM",
    "C_VALIDATION_ERROR",
    "SDKError",
    "detect",
    "extract",
    "get_version",
    "inject",
    "list_plugins",
]


def serve(host: str = "127.0.0.1", port: int = 8765, *, plugin_dir=None,
          max_workers: int = 4, api_token: str | None = None) -> None:
    """Запускает HTTP/JSON-сервис (blocking).

    non-loopback host требует api_token (env GB2TEXT_API_TOKEN или аргумент).
    """
    from api import server

    server.serve(host, port, plugin_dir=plugin_dir, max_workers=max_workers,
                 api_token=api_token)
