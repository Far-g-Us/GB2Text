"""Fixture-модуль: тестовый плагин, регистрируемый через entry_points.

Используется тестами test_plugin_manager.py для проверки auto-discovery
плагинов через setuptools entry_points (группа "gb2text.plugins").
"""

from core.plugin import GamePlugin


class FakeSpecificEP(GamePlugin):
    """Специфичный плагин из entry point (по контракту регистрируется в specific_plugins)."""

    @property
    def game_id_pattern(self) -> str:
        return r'^FAKE_EP_GAME$'

    def get_text_segments(self, rom):
        return []

    def validate_rom(self, rom) -> bool:
        return True


class NotAPlugin:
    """Класс, не наследующий GamePlugin (должен игнорироваться)."""
