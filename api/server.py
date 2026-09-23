"""HTTP/JSON-сервис для GB2Text (stdlib http.server).

Контракт: {"ok": true, "data": ...} | {"ok": false, "error": {"code", "message"}}.
Contract-ошибки (PLUGIN_NOT_FOUND и т.п.) -> HTTP 200 + ok:false.
Wire-ошибки (400/401/404/405/408/413/415/503) -> соответствующий HTTP-статус.

Безопасность (по security-ревью):
- bind по умолчанию 127.0.0.1; non-loopback host требует api-token,
  иначе serve() отказывается стартовать;
- опциональный Bearer-токен (env GB2TEXT_API_TOKEN или аргумент api_token):
  все endpoint'ы, кроме /health, требуют Authorization: Bearer <token>;
  сравнение токена — через hmac.compare_digest (timing-safe);
  при неверном токене с non-loopback клиента — фиксированная задержка ~0.5s
  ДО входа в semaphore (защита от DoS через сон занятых воркеров);
- только Content-Type: application/json (иначе 415, защита от form-CSRF);
- лимиты body на эндпоинт (413 до чтения);
- timeout только на чтение body (10s) -> 408; после чтения settimeout(None);
- единовременно максимум max_workers запросов (Semaphore) -> 503 BUSY;
- per-path lock на output для /inject (анти-гонка);
- traceback никуда не отдаётся; логируются только method/path/status.
"""

import hmac
import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import cast

from api import _core
from core.rom import MAX_ROM_SIZE

logger = logging.getLogger("gb2text.api.server")

READ_BODY_TIMEOUT = 10.0
BODY_LIMIT_DETECT_EXTRACT = 1 << 20  # 1 MB
BODY_LIMIT_INJECT = MAX_ROM_SIZE + (1 << 20)  # 64 MB + отдельный буфер
AUTH_FAIL_DELAY = 0.5  # задержка при неверном токене с non-loopback клиента
_LOCKS_CACHE_LIMIT = 128  # кэш локов на выходные файлы до прунинга
_LOCKS_LRU_AGE = 10.0  # секунды: lock считается «свежим», пока запрашивался недавно


def _is_loopback(host: str) -> bool:
    return host in ("127.0.0.1", "localhost", "::1") or host.startswith("127.")


def _read_api_token(cli_token: str | None) -> str | None:
    """Приоритет env GB2TEXT_API_TOKEN над CLI-флагом (--api-token)."""
    env_token = os.environ.get("GB2TEXT_API_TOKEN", "")
    if env_token:
        return env_token
    return cli_token or None


class ApiServer(ThreadingHTTPServer):
    """ThreadingHTTPServer с контекстом (plugin_dir, semaphore, locks, token)."""

    def __init__(self, addr, *, plugin_dir=None, max_workers=4, api_token=None):
        super().__init__(addr, ApiHandler)
        self.daemon_threads = True
        self.plugin_dir = plugin_dir
        self.semaphore = threading.Semaphore(max_workers)
        self._locks_guard = threading.Lock()
        self.output_locks: dict[str, threading.Lock] = {}
        self._locks_lru: dict[str, float] = {}
        self.api_token = api_token

    def lock_for_output(self, path: str) -> threading.Lock:
        with self._locks_guard:
            lock = self.output_locks.get(path)
            if lock is None:
                self._prune_output_locks()
                lock = threading.Lock()
                self.output_locks[path] = lock
            self._locks_lru[path] = time.monotonic()
            return lock

    def _prune_output_locks(self) -> None:
        """Удаляет свободные локи из кэша, когда он перерос лимит.

        Удаляются только локи, которые никто не держит (acquire без блокировки
        успешен) и которые давно не запрашивались (старше _LOCKS_LRU_AGE):
        так lock, только что выданный потоком, но ещё не захваченный, не
        теряется в пользу нового конкурентного потока на тот же путь.
        """
        if len(self.output_locks) < _LOCKS_CACHE_LIMIT:
            return
        now = time.monotonic()
        for path, lock in list(self.output_locks.items()):
            if len(self.output_locks) < _LOCKS_CACHE_LIMIT:
                break
            if now - self._locks_lru.get(path, 0.0) < _LOCKS_LRU_AGE:
                continue
            if lock.acquire(blocking=False):
                lock.release()
                del self.output_locks[path]
                self._locks_lru.pop(path, None)


class ApiHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = f"GB2TextApi/{_core.get_version()}"
    sys_version = ""

    def __init__(self, request, client_address, srv):
        self.api_server = cast(ApiServer, srv)
        super().__init__(request, client_address, srv)

    def log_message(self, fmt, *args):
        logger.info("http %s", fmt % args)

    # ── аутентификация ────────────────────────────────────────────
    def _require_auth(self) -> bool:
        """Проверяет Bearer-токен, если сервер настроен с api_token.

        /health всегда открыт. При неверном/отсутствующем токене с
        non-loopback клиента — платит фиксированную задержку ДО выхода
        из semaphore. Один и тот же 401 для «токен не настроен» и
        «токен неверный» — не раскрываем конфигурацию сервера.
        """
        token = self.api_server.api_token
        if not token:
            return True

        header = self.headers.get("Authorization", "")
        if header.lower().startswith("bearer "):
            supplied = header[7:].strip()
            if hmac.compare_digest(supplied.encode("utf-8"),
                                   token.encode("utf-8")):
                return True

        host = self.client_address[0]
        if not _is_loopback(host):
            time.sleep(AUTH_FAIL_DELAY)
        self._wire(401, "UNAUTHORIZED", "Требуется авторизация: Authorization: Bearer <token>")
        return False

    # ── роутинг ────────────────────────────────────────────────────
    def do_GET(self):
        if self.path == "/health":
            self._handle(lambda: {"version": _core.get_version(), "status": "ok"})
            return
        if not self._require_auth():
            return
        if self.path in ("/detect", "/extract", "/inject", "/diff"):
            self._wire(405, "METHOD_NOT_ALLOWED", "Эндпоинт принимает только POST")
            return
        if self.path == "/plugins":
            self._handle(lambda: _core.list_plugins(self.api_server.plugin_dir))
        else:
            self._wire(404, "NOT_FOUND", "Неизвестный endpoint")

    def do_POST(self):
        if self.path not in ("/detect", "/extract", "/inject", "/diff"):
            self._wire(404, "NOT_FOUND", "Неизвестный endpoint")
            return
        if not self._require_auth():
            return
        self._handle_post()

    # ── обработка POST ─────────────────────────────────────────────
    def _handle_post(self):
        data = self._read_json_body()
        if data is None:
            return
        body = data
        if self.path == "/detect":
            if not self._require(body, "rom"):
                return
            self._handle(lambda: _core.detect(body["rom"], self.api_server.plugin_dir))
        elif self.path == "/extract":
            if not self._require(body, "rom"):
                return
            max_segments = body.get("max_segments")
            if max_segments is not None and not isinstance(max_segments, int):
                self._wire(400, "BAD_REQUEST", "'max_segments' должен быть целым числом")
                return
            self._handle(
                lambda: _core.extract(
                    body["rom"],
                    plugin_dir=self.api_server.plugin_dir,
                    max_segments=max_segments,
                    language=body.get("lang", "en"),
                )
            )
        elif self.path == "/diff":
            if not self._require(body, "rom1", "rom2"):
                return
            self._handle(
                lambda: _core.diff_roms(
                    body["rom1"],
                    body["rom2"],
                    plugin_dir=self.api_server.plugin_dir,
                )
            )
        elif self.path == "/inject":
            if not self._require(body, "rom", "translations"):
                return
            try:
                resolved_rom = _core.resolve_rom(body["rom"])
                target = _core.resolve_output(resolved_rom, body.get("output"))
            except _core.SDKError as exc:
                self._contract_error(exc)
                return
            try:
                lock = self.api_server.lock_for_output(target)
                acquired = lock.acquire(timeout=10)
            except Exception:
                logger.exception("Ошибка захвата lock output")
                self._reply(
                    {"ok": False, "error": {"code": "INTERNAL", "message": "Внутренняя ошибка сервера"}},
                    status=500,
                )
                return
            if not acquired:
                self._wire(409, "CONFLICT", "Занят другой инъекцией в этот файл")
                return
            try:
                self._handle(
                    lambda: _core.inject(
                        body["rom"],
                        body["translations"],
                        output_path=body.get("output"),
                        plugin_dir=self.api_server.plugin_dir,
                    )
                )
            finally:
                lock.release()

    # ── общее ──────────────────────────────────────────────────────
    def _handle(self, fn):
        """Выполняет fn в semaphore; contract-ошибки -> 200 ok:false."""
        if not self.api_server.semaphore.acquire(blocking=False):
            self._wire(503, "BUSY", "Достигнут лимит параллельных операций")
            return
        start = time.monotonic()
        try:
            result = fn()
            self._reply({"ok": True, "data": result})
        except _core.SDKError as exc:
            self._contract_error(exc)
        except Exception:
            logger.exception("Необработанная ошибка обработки запроса")
            self._reply(
                {"ok": False, "error": {"code": "INTERNAL", "message": "Внутренняя ошибка сервера"}},
                status=500,
            )
        finally:
            self.api_server.semaphore.release()
            elapsed = (time.monotonic() - start) * 1000
            logger.info("done %s %.0fms", self.path, elapsed)

    def _read_json_body(self):
        """Читает body с проверкой Content-Type, лимитом и таймаутом на чтение."""
        content_type = self.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            self._wire(415, "UNSUPPORTED_MEDIA_TYPE", "Ожидается Content-Type: application/json")
            return None

        limit = (
            BODY_LIMIT_INJECT if self.path == "/inject" else BODY_LIMIT_DETECT_EXTRACT
        )
        raw = None
        try:
            cl_header = self.headers.get("Content-Length")
            length = int(cl_header) if cl_header is not None else None
            self.connection.settimeout(READ_BODY_TIMEOUT)
            try:
                if length is not None:
                    if not (0 <= length <= limit):
                        self._wire(413, "PAYLOAD_TOO_LARGE", "Тело запроса слишком велико")
                        return None
                    raw = self.rfile.read(length)
                else:
                    raw = self.rfile.read(limit + 1)
            finally:
                self.connection.settimeout(None)
        except TimeoutError:
            self._wire(408, "TIMEOUT", "Таймаут чтения тела запроса")
            return None
        except (ValueError, OSError):
            logger.debug("Ошибка чтения тела запроса", exc_info=True)
            self._wire(400, "BAD_REQUEST", "Ошибка чтения тела запроса")
            return None

        if raw is None:
            self._wire(400, "BAD_REQUEST", "Пустое тело")
            return None
        if length is None and len(raw) > limit:
            self._wire(413, "PAYLOAD_TOO_LARGE", "Тело запроса слишком велико")
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.debug("Некорректный JSON в теле запроса", exc_info=True)
            self._wire(400, "BAD_REQUEST", "Некорректный JSON")
            return None
        if not isinstance(parsed, dict):
            self._wire(400, "BAD_REQUEST", "Тело запроса должно быть JSON-объектом")
            return None
        return parsed

    def _require(self, body: dict, *keys) -> bool:
        missing = [key for key in keys if key not in body]
        if missing:
            self._wire(
                400,
                "BAD_REQUEST",
                f"Отсутствуют обязательные поля: {', '.join(missing)}",
            )
            return False
        return True

    def _contract_error(self, exc: _core.SDKError):
        message = exc.message
        if exc.code == _core.C_INTERNAL:
            logger.warning("SDKError INTERNAL: %s", exc.message)
            message = "Внутренняя ошибка сервера"
        self._reply({"ok": False, "error": {"code": exc.code, "message": message}})

    def _wire(self, status: int, code: str, message: str):
        self._reply({"ok": False, "error": {"code": code, "message": message}}, status=status)

    def _reply(self, payload: dict, status: int = 200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (ConnectionError, BrokenPipeError):
            logger.debug("Клиент закрыл соединение до отправки ответа")
        self.close_connection = True


def serve(host: str = "127.0.0.1", port: int = 8765, *, plugin_dir=None,
          max_workers: int = 4, api_token: str | None = None) -> None:
    """Запускает HTTP-сервис (blocking).

    Токен берётся из env GB2TEXT_API_TOKEN, если он задан, иначе из аргумента
    api_token. Для non-loopback хоста токен обязателен — без него сервис
    отказывается стартовать.
    """
    token = _read_api_token(api_token)

    if not _is_loopback(host) and not token:
        raise ValueError(
            "Сервер доступен из сети — требуется API-токен. "
            "Задайте env GB2TEXT_API_TOKEN или запустите serve с api_token."
        )

    server = ApiServer(
        (host, port), plugin_dir=plugin_dir, max_workers=max_workers,
        api_token=token,
    )
    logger.info("API-сервер запущен на http://%s:%d", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
