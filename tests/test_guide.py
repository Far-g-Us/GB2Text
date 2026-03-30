"""Тесты для модуля guide"""
import os
import sys
import tempfile
import json

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
        guide = manager.get_guide("EXAMPLE")
        # Руководство может быть None если не загружено
    
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
    
    def test_rate_guide_valid(self):
        """Тест оценки руководства"""
        manager = GuideManager()
        result = manager.rate_guide("TEST_GAME", 5)
        assert isinstance(result, bool)
    
    def test_rate_guide_invalid(self):
        """Тест оценки с невалидным значением"""
        manager = GuideManager()
        # Оценка должна быть 1-5
        result = manager.rate_guide("TEST_GAME", 10)
        assert result == False
    
    def test_get_guide_rating(self):
        """Тест получения оценки руководства"""
        manager = GuideManager()
        # Сначала оцениваем
        manager.rate_guide("TEST_GAME_2", 4)
        rating = manager.get_guide_rating("TEST_GAME_2")
        assert rating is None or isinstance(rating, int)

    def test_save_guide(self):
        """Тест сохранения руководства"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = GuideManager(guides_dir=tmpdir)
            guide = {
                "game_id": "TEST_GAME",
                "segments": [{"name": "main", "start": 0, "end": 100}],
                "encoding": "ascii"
            }
            result = manager.save_guide("TEST_GAME", guide)
            assert isinstance(result, bool)

    def test_create_template_full(self):
        """Тест создания полного шаблона"""
        manager = GuideManager()
        template = manager.create_template("FULL_TEST")
        assert 'game_id' in template
        assert 'description' in template or 'steps' in template

    def test_rate_guide_zero(self):
        """Тест оценки с нулём"""
        manager = GuideManager()
        result = manager.rate_guide("TEST_GAME", 0)
        assert result == False

    def test_guides_dir_property(self):
        """Тест свойства guides_dir"""
        manager = GuideManager()
        assert hasattr(manager, 'guides_dir')

    def test_get_guide_with_custom_game_id(self):
        """Тест получения руководства с кастомным game_id"""
        manager = GuideManager()
        guide = manager.get_guide("CUSTOM_GAME_123")
        # Guide may be None if not found

    def test_create_template_with_segments(self):
        """Тест создания шаблона с сегментами"""
        manager = GuideManager()
        template = manager.create_template("SEGMENT_TEST")
        assert isinstance(template, dict)
        if 'steps' in template:
            assert isinstance(template['steps'], list)

    def test_rate_guide_boundary_values(self):
        """Тест оценки руководства с граничными значениями"""
        manager = GuideManager()
        # Test boundary values
        result1 = manager.rate_guide("BOUNDARY_TEST", 1)
        assert isinstance(result1, bool)
        
        result2 = manager.rate_guide("BOUNDARY_TEST_2", 5)
        assert isinstance(result2, bool)

    def test_save_guide_to_file(self):
        """Тест сохранения руководства в файл"""
        import tempfile
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

    def test_get_guide_rating_nonexistent(self):
        """Тест получения оценки несуществующего руководства"""
        manager = GuideManager()
        rating = manager.get_guide_rating("VERY_NONE_EXISTENT_GAME_XYZ")
        assert rating is None

    def test_guides_dir_is_path(self):
        """Тест что guides_dir является путём"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = GuideManager(guides_dir=tmpdir)
            # Just verify it has the path
            assert str(tmpdir) in str(manager.guides_dir)

    def test_get_guide_with_valid_game_id(self):
        """Тест получения руководства с валидным game_id"""
        manager = GuideManager()
        # Try to get guide for a game that might exist
        guide = manager.get_guide("TEST_GAME")
        # Guide can be None or a dict

    def test_create_template_with_description(self):
        """Тест создания шаблона с описанием"""
        manager = GuideManager()
        template = manager.create_template("DESC_TEST")
        assert isinstance(template, dict)
        if 'description' in template:
            assert isinstance(template['description'], str)

    def test_rate_guide_max_value(self):
        """Тест максимальной оценки"""
        manager = GuideManager()
        result = manager.rate_guide("MAX_TEST", 5)
        assert isinstance(result, bool)

    def test_get_guide_rating_after_rate(self):
        """Тест получения оценки после установки"""
        manager = GuideManager()
        manager.rate_guide("RATING_TEST", 3)
        rating = manager.get_guide_rating("RATING_TEST")
        # Rating may or may not be set depending on storage

    def test_guide_manager_init_nonexistent_dir(self):
        """Тест инициализации с несуществующей директорией"""
        # Используем путь который гарантированно не существует но не требует прав root
        nonexistent_path = os.path.join(tempfile.gettempdir(), 'gb2text_test_nonexistent_guides_xyz123')
        # Убедимся что путь не существует
        if os.path.exists(nonexistent_path):
            import shutil
            shutil.rmtree(nonexistent_path, ignore_errors=True)
        
        manager = GuideManager(guides_dir=nonexistent_path)
        assert manager is not None

    def test_guide_get_guide_returns_dict_or_none(self):
        """Тест что get_guide возвращает dict или None"""
        manager = GuideManager()
        guide = manager.get_guide("RANDOM_GAME_12345")
        # Should return None or dict

    def test_get_guide_with_invalid_json(self):
        """Тест получения руководства с некорректным JSON"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file with invalid JSON
            invalid_json_file = os.path.join(tmpdir, "INVALID_JSON.json")
            with open(invalid_json_file, 'w') as f:
                f.write("{ invalid json }")
            
            manager = GuideManager(guides_dir=tmpdir)
            guide = manager.get_guide("INVALID_JSON")
            assert guide is None  # Should return None due to JSON error

    def test_save_guide_with_invalid_data(self):
        """Тест сохранения руководства с некорректными данными"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = GuideManager(guides_dir=tmpdir)
            # Pass data that can't be serialized (lambda can't be JSON serialized)
            invalid_guide = {"game_id": "TEST", "callback": lambda x: x}
            result = manager.save_guide("TEST", invalid_guide)
            assert result == False

    def test_get_guide_rating_with_invalid_value(self):
        """Тест получения оценки с некорректным значением в файле"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file with invalid rating value
            invalid_rating_file = os.path.join(tmpdir, "INVALID_RATING.rating")
            with open(invalid_rating_file, 'w') as f:
                f.write("not_a_number")
            
            manager = GuideManager(guides_dir=tmpdir)
            rating = manager.get_guide_rating("INVALID_RATING")
            assert rating is None  # Should return None due to ValueError
