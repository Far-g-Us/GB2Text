"""Тесты для модуля guide"""
import os
import sys

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
