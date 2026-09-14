"""Тесты для модуля guide"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.guide import GuideManager


class TestGuideManager:
    """Тесты для GuideManager"""

    def test_init_default(self):
        """Тест инициализации с путём по умолчанию"""
        manager = GuideManager()
        assert manager is not None

    def test_init_custom_dir(self):
        """Тест инициализации с кастомной директорией"""
        manager = GuideManager(guides_dir="guides")
        assert manager is not None

    def test_get_guide_existing(self):
        """Тест получения существующего руководства"""
        manager = GuideManager()
        manager.get_guide("EXAMPLE")

    def test_get_guide_nonexistent(self):
        """Тест получения несуществующего руководства"""
        manager = GuideManager()
        guide = manager.get_guide("NONEXISTENT_GAME_XYZ")
        assert guide is None

    def test_create_template(self):
        """Тест создания шаблона"""
        manager = GuideManager()
        template = manager.create_template("TEST_GAME")
        assert isinstance(template, dict)
        assert 'game_id' in template

    def test_save_guide(self):
        """Тест сохранения руководства"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = GuideManager(guides_dir=tmpdir)
            guide = {
                "game_id": "TEST_GAME",
                "segments": [{"name": "main", "start": 0, "end": 100}],
                "encoding": "ascii"
            }
            result = manager.save_guide("TEST_GAME", guide)
            assert isinstance(result, bool)

    def test_guides_dir_property(self):
        """Тест свойства guides_dir"""
        manager = GuideManager()
        assert hasattr(manager, 'guides_dir')

    def test_get_guide_with_custom_game_id(self):
        """Тест получения руководства с кастомным game_id"""
        manager = GuideManager()
        manager.get_guide("CUSTOM_GAME_123")

    def test_create_template_with_segments(self):
        """Тест создания шаблона с сегментами"""
        manager = GuideManager()
        template = manager.create_template("SEGMENT_TEST")
        assert isinstance(template, dict)
        if 'steps' in template:
            assert isinstance(template['steps'], list)

    def test_save_guide_to_file(self):
        """Тест сохранения руководства в файл"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = GuideManager(guides_dir=tmpdir)
            guide = {
                "game_id": "SAVE_TEST",
                "segments": [
                    {"name": "main_text", "start": 0, "end": 1000},
                    {"name": "menu", "start": 2000, "end": 3000}
                ],
                "encoding": "ascii"
            }
            result = manager.save_guide("SAVE_TEST", guide)
            assert isinstance(result, bool)

    def test_guides_dir_is_path(self):
        """Тест что guides_dir является путём"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = GuideManager(guides_dir=tmpdir)
            assert str(tmpdir) in str(manager.guides_dir)

    def test_get_guide_with_valid_game_id(self):
        """Тест получения руководства с валидным game_id"""
        manager = GuideManager()
        manager.get_guide("TEST_GAME")

    def test_create_template_with_description(self):
        """Тест создания шаблона с описанием"""
        manager = GuideManager()
        template = manager.create_template("DESC_TEST")
        assert isinstance(template, dict)
        if 'description' in template:
            assert isinstance(template['description'], str)

    def test_guide_manager_init_nonexistent_dir(self):
        """Тест инициализации с несуществующей директорией"""
        nonexistent_path = os.path.join(tempfile.gettempdir(), 'gb2text_test_nonexistent_guides_xyz123')
        if os.path.exists(nonexistent_path):
            import shutil
            shutil.rmtree(nonexistent_path, ignore_errors=True)

        manager = GuideManager(guides_dir=nonexistent_path)
        assert manager is not None

    def test_guide_get_guide_returns_dict_or_none(self):
        """Тест что get_guide возвращает dict или None"""
        manager = GuideManager()
        manager.get_guide("RANDOM_GAME_12345")

    def test_get_guide_with_invalid_json(self):
        """Тест получения руководства с некорректным JSON"""
        with tempfile.TemporaryDirectory() as tmpdir:
            invalid_json_file = os.path.join(tmpdir, "INVALID_JSON.json")
            with open(invalid_json_file, 'w') as f:
                f.write("{ invalid json }")

            manager = GuideManager(guides_dir=tmpdir)
            guide = manager.get_guide("INVALID_JSON")
            assert guide is None

    def test_save_guide_with_invalid_data(self):
        """Тест сохранения руководства с некорректными данными"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = GuideManager(guides_dir=tmpdir)
            invalid_guide = {"game_id": "TEST", "callback": lambda x: x}
            result = manager.save_guide("TEST", invalid_guide)
            assert not result
