"""
GB Text Extraction Framework

ПРЕДУПРЕЖДЕНИЕ ОБ АВТОРСКИХ ПРАВАХ:
Этот программный инструмент предназначен ТОЛЬКО для анализа ROM-файлов,
законно принадлежащих пользователю. Использование этого инструмента для
нелегального копирования, распространения или модификации защищенных
авторским правом материалов строго запрещено.
"""

import hashlib
import json
from unittest.mock import MagicMock, patch

import pytest

from core.community_registry import (
    CommunityRegistry,
    CommunityRegistryError,
    _parse_version,
)


@pytest.fixture
def tmp_dirs(tmp_path):
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    settings_dir = tmp_path / "settings"
    settings_dir.mkdir()
    return plugins_dir, settings_dir


@pytest.fixture
def registry(tmp_dirs):
    plugins_dir, settings_dir = tmp_dirs
    return CommunityRegistry(
        plugins_dir=plugins_dir,
        settings_dir=settings_dir,
        registry_url="https://example.com/registry.json",
        allowed_hosts=("example.com",),
    )


def _json_content():
    return json.dumps({
        "game_id_pattern": "^GBA_TEST$",
        "segments": [{"name": "text", "start": 0, "end": 100}],
    }).encode("utf-8")


def _make_plugin(
    plugin_id="gba_test_game",
    version="1.0.0",
    plugin_type="json",
    download_url="https://example.com/test.json",
    min_gb2text_version=None,
    content: bytes | None = None,
    sha256: str | None = None,
):
    payload = content if content is not None else _json_content()
    plugin = {
        "id": plugin_id,
        "name": "Test Game",
        "author": "test_author",
        "version": version,
        "game_id_pattern": "^GBA_TEST$",
        "platform": "GBA",
        "description": "Test plugin",
        "type": plugin_type,
        "download_url": download_url,
        "sha256": sha256 if sha256 is not None
            else hashlib.sha256(payload).hexdigest(),
    }
    if min_gb2text_version is not None:
        plugin["min_gb2text_version"] = min_gb2text_version
    return plugin


class TestParseVersion:
    def test_normal(self):
        assert _parse_version("1.4.0") == (1, 4, 0)

    def test_two_parts(self):
        assert _parse_version("1.4") == (1, 4)

    def test_non_numeric(self):
        assert _parse_version("1.4.beta") == (1, 4)

    def test_empty(self):
        assert _parse_version("") == (0,)

    def test_none(self):
        assert _parse_version(None) == (0,)

    def test_non_string(self):
        assert _parse_version(42) == (0,)


class TestGetInstalled:
    def test_empty(self, registry):
        assert registry.get_installed() == {}

    def test_reads_file(self, registry, tmp_dirs):
        _, settings_dir = tmp_dirs
        data = {"gba_test": {"version": "1.0.0", "type": "json"}}
        (settings_dir / "community_plugins.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        assert registry.get_installed() == data

    def test_corrupt_file(self, registry, tmp_dirs):
        _, settings_dir = tmp_dirs
        (settings_dir / "community_plugins.json").write_text(
            "NOT JSON", encoding="utf-8"
        )
        assert registry.get_installed() == {}


class TestGetLocalVersion:
    def test_not_installed(self, registry):
        assert registry.get_local_version("gba_test") is None

    def test_installed(self, registry, tmp_dirs):
        _, settings_dir = tmp_dirs
        data = {"gba_test": {"version": "2.0.0", "type": "json"}}
        (settings_dir / "community_plugins.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        assert registry.get_local_version("gba_test") == "2.0.0"


class TestHasUpdate:
    def test_not_installed(self, registry):
        plugin = _make_plugin(version="1.0.0")
        assert registry.has_update(plugin) is False

    def test_same_version(self, registry, tmp_dirs):
        _, settings_dir = tmp_dirs
        data = {"gba_test_game": {"version": "1.0.0", "type": "json"}}
        (settings_dir / "community_plugins.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        plugin = _make_plugin(version="1.0.0")
        assert registry.has_update(plugin) is False

    def test_newer_version(self, registry, tmp_dirs):
        _, settings_dir = tmp_dirs
        data = {"gba_test_game": {"version": "1.0.0", "type": "json"}}
        (settings_dir / "community_plugins.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        plugin = _make_plugin(version="1.1.0")
        assert registry.has_update(plugin) is True

    def test_null_remote_version(self, registry, tmp_dirs):
        _, settings_dir = tmp_dirs
        data = {"gba_test_game": {"version": "1.0.0", "type": "json"}}
        (settings_dir / "community_plugins.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        plugin = _make_plugin(version=None)
        assert registry.has_update(plugin) is False


class TestCheckGb2textVersion:
    def test_no_requirement(self, registry):
        assert registry._check_gb2text_version({}) is True

    def test_meets_requirement(self, registry):
        assert registry._check_gb2text_version(
            {"min_gb2text_version": "1.0.0"}
        ) is True


class TestValidateJsonPlugin:
    def test_valid(self, registry):
        content = json.dumps({
            "game_id_pattern": "^GBA_TEST$",
            "segments": [{"name": "text", "start": 0, "end": 100}],
        })
        result = registry._validate_json_plugin(content)
        assert result["game_id_pattern"] == "^GBA_TEST$"

    def test_no_pattern(self, registry):
        content = json.dumps({"segments": [{"name": "x", "start": 0, "end": 1}]})
        with pytest.raises(CommunityRegistryError, match="game_id_pattern"):
            registry._validate_json_plugin(content)

    def test_no_segments(self, registry):
        content = json.dumps({"game_id_pattern": "^GBA_TEST$"})
        with pytest.raises(CommunityRegistryError, match="segments"):
            registry._validate_json_plugin(content)

    def test_invalid_json(self, registry):
        with pytest.raises(CommunityRegistryError, match="Невалидный JSON"):
            registry._validate_json_plugin("not json")

    def test_bad_segment(self, registry):
        content = json.dumps({
            "game_id_pattern": "^GBA_TEST$",
            "segments": [{"name": "x"}],
        })
        with pytest.raises(CommunityRegistryError, match="start"):
            registry._validate_json_plugin(content)

    def test_segment_not_dict(self, registry):
        content = json.dumps({
            "game_id_pattern": "^GBA_TEST$",
            "segments": [42],
        })
        with pytest.raises(CommunityRegistryError, match="segment"):
            registry._validate_json_plugin(content)


class TestValidatePluginId:
    def test_valid(self, registry):
        assert registry._validate_plugin_id("gba_test_game") == "gba_test_game"

    def test_path_traversal(self, registry):
        with pytest.raises(CommunityRegistryError, match="Недопустимый"):
            registry._validate_plugin_id("../../evil")

    def test_absolute_windows_path(self, registry):
        with pytest.raises(CommunityRegistryError, match="Недопустимый"):
            registry._validate_plugin_id("C:/evil")

    def test_non_string(self, registry):
        with pytest.raises(CommunityRegistryError):
            registry._validate_plugin_id(42)

    def test_empty_raises(self, registry):
        with pytest.raises(CommunityRegistryError, match="Недопустимый"):
            registry._validate_plugin_id("")

    def test_return_empty_when_raise_disabled(self, registry):
        assert registry._validate_plugin_id("../../evil",
                                            raise_on_empty=False) == ""


class TestResolveDownloadUrl:
    def test_absolute_allowed_host(self, registry):
        url = registry._resolve_download_url(
            "https://example.com/plugins/test.json")
        assert url == "https://example.com/plugins/test.json"

    def test_relative_resolved(self, registry):
        url = registry._resolve_download_url("plugins/test.json")
        assert url == "https://example.com/plugins/test.json"

    def test_http_rejected(self, registry):
        with pytest.raises(CommunityRegistryError, match="HTTPS"):
            registry._resolve_download_url("http://example.com/x.json")

    def test_bad_host_rejected(self, registry):
        with pytest.raises(CommunityRegistryError, match="хост"):
            registry._resolve_download_url("https://evil.com/x.json")


class TestVerifySha256:
    def test_match(self, registry):
        content = b"hello"
        plugin = _make_plugin(content=content)
        registry._verify_sha256(plugin, content)

    def test_mismatch(self, registry):
        plugin = _make_plugin(content=b"hello")
        with pytest.raises(CommunityRegistryError, match="SHA-256"):
            registry._verify_sha256(plugin, b"tampered")

    def test_missing(self, registry):
        plugin = _make_plugin(sha256="")
        with pytest.raises(CommunityRegistryError, match="sha256"):
            registry._verify_sha256(plugin, b"hello")


class TestInstall:
    def test_install_json_plugin(self, registry, tmp_dirs):
        plugins_dir, _ = tmp_dirs
        payload = _json_content()
        plugin = _make_plugin(plugin_type="json", content=payload)

        with patch.object(registry, "_download_file", return_value=payload):
            dest = registry.install(plugin)

        assert dest.name == "gba_test_game.json"
        assert dest.parent == plugins_dir / "config"
        assert dest.exists()
        assert json.loads(dest.read_text(encoding="utf-8"))["game_id_pattern"] == "^GBA_TEST$"
        assert registry.is_installed("gba_test_game")

    def test_install_python_plugin(self, registry, tmp_dirs):
        plugins_dir, _ = tmp_dirs
        py_content = b"class TestPlugin: pass"
        plugin = _make_plugin(plugin_type="python", content=py_content)

        with patch.object(registry, "_download_file", return_value=py_content):
            dest = registry.install(plugin)

        assert dest.name == "gba_test_game.py"
        assert dest.parent == plugins_dir
        assert dest.exists()
        assert dest.read_bytes() == py_content

    def test_install_no_url(self, registry):
        plugin = _make_plugin(download_url="")
        with pytest.raises(CommunityRegistryError, match="download_url"):
            registry.install(plugin)

    def test_install_no_id(self, registry):
        plugin = _make_plugin(plugin_id="")
        with pytest.raises(CommunityRegistryError, match="id"):
            registry.install(plugin)

    def test_install_bad_json(self, registry):
        plugin = _make_plugin(content=b"not json")
        with patch.object(registry, "_download_file", return_value=b"not json"):
            with pytest.raises(CommunityRegistryError, match="Невалидный JSON"):
                registry.install(plugin)

    def test_install_path_traversal_id(self, registry, tmp_dirs):
        plugins_dir, _ = tmp_dirs
        plugin = _make_plugin(plugin_id="../../evil")
        with pytest.raises(CommunityRegistryError, match="Недопустимый"):
            registry.install(plugin)
        assert not plugins_dir.exists() or not list(plugins_dir.rglob("*"))

    def test_install_sha256_mismatch(self, registry):
        payload = _json_content()
        plugin = _make_plugin(content=payload, sha256="0" * 64)
        with patch.object(registry, "_download_file", return_value=payload):
            with pytest.raises(CommunityRegistryError, match="SHA-256"):
                registry.install(plugin)

    def test_install_bad_host(self, registry):
        plugin = _make_plugin(download_url="https://evil.com/x.json")
        with pytest.raises(CommunityRegistryError, match="хост"):
            registry.install(plugin)

    def test_install_cyrillic_json(self, registry, tmp_dirs):
        content = json.dumps({
            "name": "Плагин с кириллицей",
            "game_id_pattern": "^GBA_TEST$",
            "segments": [{"name": "text", "start": 0, "end": 100}],
        }, ensure_ascii=False).encode("utf-8")
        plugin = _make_plugin(content=content)

        with patch.object(registry, "_download_file", return_value=content):
            dest = registry.install(plugin)

        decoded = json.loads(dest.read_text(encoding="utf-8"))
        assert decoded["name"] == "Плагин с кириллицей"


class TestUninstall:
    def test_uninstall_json(self, registry, tmp_dirs):
        plugins_dir, _ = tmp_dirs
        config_dir = plugins_dir / "config"
        config_dir.mkdir()
        plugin_file = config_dir / "gba_test_game.json"
        plugin_file.write_text("{}", encoding="utf-8")

        installed = {"gba_test_game": {"version": "1.0.0", "type": "json"}}
        (tmp_dirs[1] / "community_plugins.json").write_text(
            json.dumps(installed), encoding="utf-8"
        )

        assert registry.uninstall("gba_test_game") is True
        assert not plugin_file.exists()
        assert registry.get_installed() == {}

    def test_uninstall_not_installed(self, registry):
        assert registry.uninstall("gba_nonexistent") is False

    def test_uninstall_bad_id(self, registry):
        with pytest.raises(CommunityRegistryError, match="Недопустимый"):
            registry.uninstall("../evil")


class TestCheckUpdates:
    def test_finds_updates(self, registry, tmp_dirs):
        _, settings_dir = tmp_dirs
        data = {"gba_test_game": {"version": "1.0.0", "type": "json"}}
        (settings_dir / "community_plugins.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        registry_list = [_make_plugin(version="1.1.0")]
        updates = registry.check_updates(registry_list)
        assert len(updates) == 1
        assert updates[0]["id"] == "gba_test_game"

    def test_no_updates(self, registry, tmp_dirs):
        _, settings_dir = tmp_dirs
        data = {"gba_test_game": {"version": "1.1.0", "type": "json"}}
        (settings_dir / "community_plugins.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        registry_list = [_make_plugin(version="1.1.0")]
        assert registry.check_updates(registry_list) == []


class TestFetchRegistry:
    def test_success(self, registry):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"plugins": [_make_plugin()]}
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_resp):
            result = registry.fetch_registry()

        assert len(result) == 1
        assert result[0]["id"] == "gba_test_game"

    def test_network_error_fallback_to_cache(self, registry, tmp_dirs):
        _, settings_dir = tmp_dirs
        payload = _json_content()
        cached = {
            "plugins": [_make_plugin(version="0.9.0", content=payload)],
            "fetched_at": "2025-01-01T00:00:00",
        }
        (settings_dir / "community_registry_cache.json").write_text(
            json.dumps(cached), encoding="utf-8"
        )

        with patch("requests.get", side_effect=Exception("Network error")):
            result = registry.fetch_registry()

        assert len(result) == 1
        assert result[0]["version"] == "0.9.0"

    def test_network_error_no_cache(self, registry):
        with patch("requests.get", side_effect=Exception("Network error")):
            with pytest.raises(CommunityRegistryError, match="Не удалось загрузить каталог"):
                registry.fetch_registry()

    def test_invalid_plugins_type(self, registry):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"plugins": "not a list"}
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp):
            with pytest.raises(CommunityRegistryError, match="списком"):
                registry.fetch_registry()

    def test_duplicate_id_rejected(self, registry):
        plugin = _make_plugin()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"plugins": [plugin, plugin]}
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp):
            with pytest.raises(CommunityRegistryError, match="Дубликат"):
                registry.fetch_registry()

    def test_missing_sha256_rejected(self, registry):
        plugin = _make_plugin()
        del plugin["sha256"]
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"plugins": [plugin]}
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp):
            with pytest.raises(CommunityRegistryError, match="sha256"):
                registry.fetch_registry()

    def test_empty_registry_ok(self, registry):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"plugins": []}
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp):
            assert registry.fetch_registry() == []
