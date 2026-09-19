"""
GB Text Extraction Framework

ПРЕДУПРЕЖДЕНИЕ ОБ АВТОРСКИХ ПРАВАХ:
Этот программный инструмент предназначен ТОЛЬКО для анализа ROM-файлов,
законно принадлежащих пользователю. Использование этого инструмента для
нелегального копирования, распространения или модификации защищенных
авторским правом материалов строго запрещено.

Этот проект НЕ содержит и НЕ распространяет никакие ROM-файлы или
защищенные авторским правом материалы. Все ROM-файлы должны быть
законно приобретены пользователем самостоятельно.

Этот инструмент разработан исключительно для исследовательских целей,
обучения и реверс-инжиниринга в рамках, разрешенных законодательством.
"""

"""
Каталог общедоступных плагинов (Community Plugin Registry).

Получает статический JSON с GitHub Pages, скачивает и устанавливает
плагины (JSON-конфиги и Python-модули) в локальную директорию.

Безопасность: plugin_id валидируется (защита от path traversal),
download_url ограничивается HTTPS и доверенными хостами, целостность
контента проверяется по SHA-256 из registry.
"""

import hashlib
import json
import logging
import os
import re
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from urllib.parse import urljoin, urlparse

import requests

logger = logging.getLogger("gb2text.community_registry")

REGISTRY_URL = "https://far-g-us.github.io/GB2Text/registry.json"

_PLUGIN_ID_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}$")
_WINDOWS_RESERVED_RE = re.compile(
    r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)", re.IGNORECASE
)
_MAX_FILE_SIZE = 5 * 1024 * 1024
_ALLOWED_DOWNLOAD_HOSTS = ("far-g-us.github.io", "raw.githubusercontent.com")

_PLUGINS_DIR = Path("plugins")
_SETTINGS_DIR = Path("settings")


def _parse_version(version: object) -> tuple[int, ...]:
    """Преобразует строку версии '1.4.0' в кортеж (1, 4, 0)."""
    if not isinstance(version, str):
        return (0,)
    parts: list[int] = []
    for part in version.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            break
    return tuple(parts) if parts else (0,)


class CommunityRegistryError(Exception):
    pass


class CommunityRegistry:
    """Каталог общедоступных плагинов на GitHub Pages.

    Fetch registry → compare versions → download+install → update local state.
    """

    def __init__(
        self,
        plugins_dir: Path | str = _PLUGINS_DIR,
        settings_dir: Path | str = _SETTINGS_DIR,
        registry_url: str = REGISTRY_URL,
        allowed_hosts: tuple[str, ...] = _ALLOWED_DOWNLOAD_HOSTS,
    ) -> None:
        self.plugins_dir = Path(plugins_dir)
        self.config_dir = self.plugins_dir / "config"
        self.settings_dir = Path(settings_dir)
        self.registry_url = registry_url
        self.allowed_hosts = allowed_hosts
        self._installed_file = self.settings_dir / "community_plugins.json"
        self._cache_file = self.settings_dir / "community_registry_cache.json"
        self._lock = threading.Lock()

    def fetch_registry(self) -> list[dict]:
        """GET registry.json → список метаданных плагинов.

        Валидирует каждую запись (id, тип, sha256) — и из сети, и из кэша.
        """
        try:
            resp = requests.get(self.registry_url, timeout=15)
            resp.raise_for_status()
            data = cast(dict, resp.json())
            plugins = cast(list[dict], data.get("plugins", []))
            self._validate_plugins(plugins)
            self._cache_registry(plugins)
            return plugins
        except CommunityRegistryError:
            logger.error("Ошибка валидации registry: %s", exc_info=True)
            cached = self._load_cache(validate=True)
            if cached is not None:
                return cached
            raise
        except Exception as exc:
            logger.error("Ошибка загрузки registry: %s", exc)
            cached = self._load_cache(validate=True)
            if cached is not None:
                return cached
            raise CommunityRegistryError(
                f"Не удалось загрузить каталог: {exc}"
            ) from exc

    def get_installed(self) -> dict[str, dict]:
        """Читает локальный реестр установленных плагинов."""
        if not self._installed_file.exists():
            return {}
        try:
            with open(self._installed_file, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as exc:
            logger.warning("Ошибка чтения community_plugins.json: %s", exc)
            return {}
        if not isinstance(data, dict):
            logger.warning(
                "community_plugins.json повреждён (не объект) — игнорирован")
            return {}
        return cast(dict[str, dict], data)

    def get_local_version(self, plugin_id: str) -> str | None:
        """Версия установленного плагина или None."""
        installed = self.get_installed()
        entry = installed.get(plugin_id)
        if not isinstance(entry, dict):
            return None
        return entry.get("version")

    def is_installed(self, plugin_id: str) -> bool:
        return self.get_local_version(plugin_id) is not None

    def has_update(self, plugin: dict, installed: dict[str, dict] | None = None) -> bool:
        """Проверяет, есть ли обновление для плагина."""
        local_map = installed if installed is not None else self.get_installed()
        entry = local_map.get(plugin.get("id", ""))
        if not isinstance(entry, dict):
            return False
        local = entry.get("version")
        if not isinstance(local, str):
            return False
        remote = plugin.get("version")
        return _parse_version(remote) > _parse_version(local)

    def install(self, plugin: dict) -> Path:
        """Скачивает плагин из registry и устанавливает локально.

        Возвращает путь к установленному файлу.
        """
        plugin_id = self._validate_plugin_id(plugin.get("id"))
        if not plugin_id:
            raise CommunityRegistryError("Плагин без id не может быть установлен")
        plugin_type = plugin.get("type", "json")
        download_url = plugin.get("download_url", "")
        version = plugin.get("version", "0.0.0")

        if not download_url:
            raise CommunityRegistryError(
                f"Плагин {plugin_id}: не указан download_url"
            )

        if not self._check_gb2text_version(plugin):
            raise CommunityRegistryError(
                f"Плагин {plugin_id} требует GB2Text "
                f">= {plugin.get('min_gb2text_version', '?')}"
            )

        resolved_url = self._resolve_download_url(download_url)
        content = self._download_file(resolved_url)
        self._verify_sha256(plugin, content)

        if plugin_type == "json":
            try:
                self._validate_json_plugin(content.decode("utf-8"))
            except UnicodeDecodeError as exc:
                raise CommunityRegistryError(
                    "JSON-плагин не в UTF-8") from exc
            dest = self.config_dir / f"{plugin_id}.json"
            self.config_dir.mkdir(parents=True, exist_ok=True)
        elif plugin_type == "python":
            dest = self.plugins_dir / f"{plugin_id}.py"
            self.plugins_dir.mkdir(parents=True, exist_ok=True)
        else:
            raise CommunityRegistryError(
                f"Неизвестный тип плагина: {plugin_type}"
            )

        self._atomic_write(dest, content)
        with self._lock:
            self._record_install(plugin_id, version, plugin_type, resolved_url)
        logger.info("Плагин %s установлен: %s", plugin_id, dest)
        return dest

    def uninstall(self, plugin_id: str) -> bool:
        """Удаляет установленный плагин и обновляет реестр."""
        plugin_id = self._validate_plugin_id(plugin_id)
        if not plugin_id:
            return False

        with self._lock:
            installed = self.get_installed()
            entry = installed.get(plugin_id)
            if not isinstance(entry, dict):
                return False

            plugin_type = entry.get("type", "json")
            if plugin_type == "json":
                path = self.config_dir / f"{plugin_id}.json"
            else:
                path = self.plugins_dir / f"{plugin_id}.py"

            if path.exists():
                if path.is_symlink():
                    path.unlink()  # unlink удаляет сам symlink, не цель
                    logger.info("Символическая ссылка плагина удалена: %s",
                                path)
                else:
                    path.unlink()
                    logger.info("Файл плагина удалён: %s", path)

            del installed[plugin_id]
            self._write_installed(installed)
        return True

    def check_updates(self, registry: list[dict]) -> list[dict]:
        """Возвращает список плагинов с доступными обновлениями."""
        installed = self.get_installed()
        return [
            plugin for plugin in registry
            if self.has_update(plugin, installed=installed)
        ]

    def _validate_plugins(self, plugins: object) -> None:
        """Валидирует список записей реестра."""
        if not isinstance(plugins, list):
            raise CommunityRegistryError("registry['plugins'] должен быть списком")
        seen: set[str] = set()
        for entry in plugins:
            if not isinstance(entry, dict):
                raise CommunityRegistryError("Запись плагина должна быть объектом")
            plugin_id = self._validate_plugin_id(entry.get("id"), raise_on_empty=False)
            if not plugin_id:
                raise CommunityRegistryError("Запись плагина без valid id")
            if plugin_id in seen:
                raise CommunityRegistryError(f"Дубликат id плагина: {plugin_id}")
            seen.add(plugin_id)
            if entry.get("type") not in ("json", "python"):
                raise CommunityRegistryError(
                    f"Плагин {plugin_id}: неизвестный тип '{entry.get('type')}'"
                )
            if not entry.get("download_url"):
                raise CommunityRegistryError(
                    f"Плагин {plugin_id}: не указан download_url"
                )
            sha256 = entry.get("sha256")
            if not isinstance(sha256, str) or not re.fullmatch(
                r"[0-9a-fA-F]{64}", sha256
            ):
                raise CommunityRegistryError(
                    f"Плагин {plugin_id}: невалидный sha256"
                )
            if not isinstance(entry.get("version"), str):
                raise CommunityRegistryError(
                    f"Плагин {plugin_id}: version должна быть строкой"
                )

    def _validate_plugin_id(
        self, plugin_id: object, raise_on_empty: bool = True
    ) -> str:
        """Проверяет plugin_id и возвращает его, либо пустую строку."""
        if not isinstance(plugin_id, str):
            if raise_on_empty:
                raise CommunityRegistryError("plugin_id должен быть строкой")
            return ""
        pid = plugin_id.strip()
        if not _PLUGIN_ID_RE.fullmatch(pid) or _WINDOWS_RESERVED_RE.match(pid):
            if raise_on_empty:
                raise CommunityRegistryError(
                    f"Недопустимый plugin_id: {plugin_id!r}"
                )
            return ""
        return pid

    def _resolve_download_url(self, download_url: str) -> str:
        """Резолвит относительный URL и проверяет scheme/host."""
        if not isinstance(download_url, str):
            raise CommunityRegistryError("download_url должен быть строкой")
        if urlparse(download_url).netloc == "":
            download_url = urljoin(self.registry_url, download_url)
        parsed = urlparse(download_url)
        if parsed.scheme != "https":
            raise CommunityRegistryError(
                f"download_url должен быть HTTPS: {download_url}"
            )
        if parsed.hostname not in self.allowed_hosts:
            raise CommunityRegistryError(
                f"Недопустимый хост загрузки: {parsed.hostname}"
            )
        return download_url

    def _download_file(self, url: str) -> bytes:
        """Скачивает файл, следуя редиректам только на доверенные хосты."""
        try:
            current = url
            for _ in range(5):
                resp = requests.get(current, timeout=15, stream=True,
                                    allow_redirects=False)
                resp.raise_for_status()
                if resp.is_redirect or resp.is_permanent_redirect:
                    next_url = resp.headers.get("Location", "")
                    if not next_url:
                        raise CommunityRegistryError(
                            f"Редирект без Location: {current}"
                        )
                    current = self._resolve_download_url(next_url)
                    continue
                chunks: list[bytes] = []
                size = 0
                for chunk in resp.iter_content(chunk_size=64 * 1024):
                    size += len(chunk)
                    if size > _MAX_FILE_SIZE:
                        raise CommunityRegistryError(
                            f"Файл слишком большой (>{_MAX_FILE_SIZE} байт): {url}"
                        )
                    chunks.append(chunk)
                return b"".join(chunks)
            raise CommunityRegistryError(
                f"Слишком много редиректов при скачивании: {url}"
            )
        except CommunityRegistryError:
            raise
        except Exception as exc:
            raise CommunityRegistryError(
                f"Ошибка скачивания {url}: {exc}"
            ) from exc

    def _verify_sha256(self, plugin: dict, content: bytes) -> None:
        """Проверяет SHA-256 скачанного контента."""
        expected = plugin.get("sha256")
        plugin_id = plugin.get("id", "")
        if not isinstance(expected, str) or not expected:
            raise CommunityRegistryError(
                f"Плагин {plugin_id}: не указан sha256"
            )
        actual = hashlib.sha256(content).hexdigest()
        if actual.lower() != expected.lower():
            raise CommunityRegistryError(
                f"Плагин {plugin_id}: SHA-256 не совпадает"
            )

    def _validate_json_plugin(self, content: str) -> dict:
        """Валидирует JSON-содержимое плагина."""
        try:
            config = json.loads(content)
        except json.JSONDecodeError as exc:
            raise CommunityRegistryError(f"Невалидный JSON: {exc}") from exc
        if not isinstance(config, dict):
            raise CommunityRegistryError(
                "JSON-плагин повреждён (не объект)")

        if not isinstance(config.get("game_id_pattern"), str):
            raise CommunityRegistryError(
                "JSON-плагин не содержит game_id_pattern"
            )

        if not isinstance(config.get("segments"), list):
            raise CommunityRegistryError(
                "JSON-плагин не содержит segments[]"
            )

        for seg in config["segments"]:
            if not isinstance(seg, dict):
                raise CommunityRegistryError("segment должен быть объектом")
            for field in ("name", "start", "end"):
                if field not in seg:
                    raise CommunityRegistryError(
                        f"segment не содержит поле '{field}'"
                    )
            for field in ("start", "end"):
                value = seg[field]
                valid = isinstance(value, int) or (
                    isinstance(value, str)
                    and re.fullmatch(r"0x[0-9A-Fa-f]+", value) is not None
                )
                if not valid:
                    raise CommunityRegistryError(
                        f"segment.{field} должен быть числом или '0x...'"
                    )

        return config

    def _check_gb2text_version(self, plugin: dict) -> bool:
        """Проверяет минимальную версию GB2Text для плагина."""
        min_ver = plugin.get("min_gb2text_version")
        if min_ver is None:
            return True
        try:
            version_file = Path(__file__).resolve().parent.parent / "VERSION"
            if version_file.exists():
                current = version_file.read_text(encoding="utf-8").strip()
            else:
                current = "0.0.0"
            return _parse_version(current) >= _parse_version(min_ver)
        except (OSError, ValueError):
            return True

    def _record_install(
        self,
        plugin_id: str,
        version: str,
        plugin_type: str,
        download_url: str,
    ) -> None:
        """Записывает факт установки плагина."""
        installed = self.get_installed()
        installed[plugin_id] = {
            "version": version,
            "type": plugin_type,
            "download_url": download_url,
            "installed_at": datetime.now(UTC).isoformat(),
        }
        self._write_installed(installed)

    def _write_installed(self, data: dict) -> None:
        """Атомарно записывает community_plugins.json."""
        self.settings_dir.mkdir(parents=True, exist_ok=True)
        self._atomic_write_json(self._installed_file, data)

    def _cache_registry(self, plugins: list[dict]) -> None:
        """Кэширует registry для работы без интернета."""
        self.settings_dir.mkdir(parents=True, exist_ok=True)
        self._atomic_write_json(self._cache_file, {
            "plugins": plugins,
            "fetched_at": datetime.now(UTC).isoformat(),
        })

    def _load_cache(self, validate: bool = False) -> list[dict] | None:
        """Загружает кэшированный registry."""
        if not self._cache_file.exists():
            return None
        try:
            with open(self._cache_file, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                logger.warning(
                    "Кэш-реестр повреждён (не объект) — игнорирован")
                return None
            plugins = cast(list[dict], data.get("plugins", []))
            if validate:
                self._validate_plugins(plugins)
            return plugins
        except (OSError, ValueError, CommunityRegistryError):
            logger.warning("Ошибка чтения/валидации кэша registry", exc_info=True)
            return None

    @staticmethod
    def _atomic_write(path: Path, content: bytes | str) -> None:
        """Атомарно записывает файл."""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=path.parent)
        try:
            os.close(fd)
            if isinstance(content, bytes):
                with open(tmp_path, "wb") as f:
                    f.write(content)
            else:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    f.write(content)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    @staticmethod
    def _atomic_write_json(path: Path, data: dict) -> None:
        """Атомарно записывает JSON-файл."""
        content = json.dumps(data, indent=2, ensure_ascii=False)
        CommunityRegistry._atomic_write(path, content)
