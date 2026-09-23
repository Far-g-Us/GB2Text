"""Защищённое хранение секретов (API-ключи машинного перевода).

Windows: DPAPI (CryptProtectData/CryptUnprotectData) через ctypes, без внешних
зависимостей (PyInstaller-friendly). Зашифрованные BLOB'ы хранятся в
settings/secrets.dat (JSON + base64). Каждый BLOB привязан к учётной записи
Windows текущего пользователя — перенос файла на другую машину/аккаунт
расшифровать нельзя (load вернёт None).

Linux/macOS: если доступен keyring — секреты в системном хранилище ключей;
иначе секреты не сохраняются: store_secret возвращает False, а пустые поля
в settings.json не заполняются (пользователь перевводит ключ заново).

Гарантии:
- секрет никогда не пишется в settings.json и не попадает в логи;
- запись файла атомарна (temp + os.replace);
- delete_secret при очистке поля в GUI удаляет значение из хранилища;
- при недоступном хранилище миграция из открытого settings.json всё равно
  вычищает ключ из файла (лучше переввести, чем хранить открытым текстом).
"""

import base64
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import cast

logger = logging.getLogger("gb2text.secret_store")

SERVICE_NAME = "gb2text"
DEFAULT_PATH = Path("settings") / "secrets.dat"


def _dpapi_protect(data: bytes) -> bytes:
    import ctypes
    import ctypes.wintypes as wt

    class DPDataBlob(ctypes.Structure):
        _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    crypt32 = ctypes.windll.crypt32
    buffer = ctypes.create_string_buffer(data, len(data))
    blob_in = DPDataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    blob_out = DPDataBlob()
    if not crypt32.CryptProtectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise OSError(ctypes.get_last_error() or "CryptProtectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _dpapi_unprotect(blob: bytes) -> bytes:
    import ctypes
    import ctypes.wintypes as wt

    class DPDataBlob(ctypes.Structure):
        _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    crypt32 = ctypes.windll.crypt32
    buffer = ctypes.create_string_buffer(blob, len(blob))
    blob_in = DPDataBlob(len(blob), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    blob_out = DPDataBlob()
    if not crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise OSError(ctypes.get_last_error() or "CryptUnprotectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


class _DpapiBackend:
    """Windows: файл secrets.dat с DPAPI-зашифрованными значениями."""

    def __init__(self, path=DEFAULT_PATH):
        self.path = Path(path)

    def _read(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = cast(dict, json.load(f))
            secrets = data.get("secrets") if isinstance(data, dict) else None
            if isinstance(secrets, dict):
                return data
        except (OSError, ValueError):
            pass
        return {"version": 1, "secrets": {}}

    def _write(self, data: dict) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=self.path.parent)
            os.close(fd)
            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                os.replace(tmp_path, self.path)
                return True
            except Exception:  # pragma: no cover
                try:  # pragma: no cover
                    os.unlink(tmp_path)  # pragma: no cover
                except OSError:  # pragma: no cover
                    pass
                raise
        except (OSError, TypeError):
            logger.warning("Не удалось сохранить secrets.dat: %s", self.path)
            return False

    def store(self, name: str, value: str) -> bool:
        try:
            encrypted = _dpapi_protect(value.encode("utf-8"))
        except (OSError, AttributeError):
            logger.warning("DPAPI недоступен — секрет '%s' не сохранён", name)
            return False
        data = self._read()
        data["secrets"][name] = base64.b64encode(encrypted).decode("ascii")
        return self._write(data)

    def load(self, name: str) -> str | None:
        data = self._read()
        encoded = data["secrets"].get(name)
        if not encoded:
            return None
        try:
            decrypted = _dpapi_unprotect(base64.b64decode(encoded))
            return decrypted.decode("utf-8")
        except (OSError, ValueError):
            logger.warning("Не удалось расшифровать секрет '%s'", name)
            return None

    def delete(self, name: str) -> bool:
        data = self._read()
        if name in data["secrets"]:
            del data["secrets"][name]
            return self._write(data)
        return True


class _KeyringBackend:
    """Linux/macOS: системное хранилище ключей через keyring."""

    def __init__(self):
        import keyring  # pragma: no cover

        self._keyring = keyring  # pragma: no cover

    def store(self, name: str, value: str) -> bool:
        try:  # pragma: no cover
            self._keyring.set_password(SERVICE_NAME, name, value)  # pragma: no cover
            return True  # pragma: no cover
        except Exception:  # pragma: no cover
            logger.warning("keyring вернул ошибку при сохранении '%s'", name)  # pragma: no cover
            return False  # pragma: no cover

    def load(self, name: str) -> str | None:
        try:  # pragma: no cover
            return cast(str | None, self._keyring.get_password(SERVICE_NAME, name))  # pragma: no cover
        except Exception:  # pragma: no cover
            return None  # pragma: no cover

    def delete(self, name: str) -> bool:
        try:  # pragma: no cover
            try:  # pragma: no cover
                self._keyring.delete_password(SERVICE_NAME, name)  # pragma: no cover
            except self._keyring.errors.PasswordDeleteError:  # pragma: no cover
                pass  # pragma: no cover
            return True  # pragma: no cover
        except Exception:  # pragma: no cover
            return False  # pragma: no cover


class _NullBackend:
    """Хранилище недоступно — секреты не сохраняем."""

    def store(self, name, value) -> bool:
        logger.warning(
            "Защищённое хранилище недоступно — секрет '%s' не сохранён", name
        )
        return False

    def load(self, name) -> str | None:
        return None

    def delete(self, name) -> bool:
        return False


def create_backend(path=DEFAULT_PATH):
    """Выбирает backend по платформе."""
    if sys.platform.startswith("win"):
        return _DpapiBackend(path)
    try:  # pragma: no cover
        import keyring  # pragma: no cover

        keyring.get_keyring()  # pragma: no cover
    except Exception:  # pragma: no cover
        return _NullBackend()  # pragma: no cover
    return _KeyringBackend()  # pragma: no cover


_backend = None


def _get_backend():
    global _backend
    if _backend is None:
        _backend = create_backend()
    return _backend


def store_secret(name: str, value: str) -> bool:
    """Сохраняет секрет. Пустое значение удаляет секрет."""
    if not value:
        return delete_secret(name)
    return cast(bool, _get_backend().store(name, value))


def load_secret(name: str) -> str | None:
    """Возвращает секрет или None (включая случай недоступного хранилища)."""
    return cast(str | None, _get_backend().load(name))


def delete_secret(name: str) -> bool:
    """Удаляет секрет из хранилища."""
    return cast(bool, _get_backend().delete(name))
