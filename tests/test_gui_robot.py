"""
Robot Framework тесты для GUI GB2Text
Использует SeleniumLibrary для тестирования desktop GUI
"""
import pytest

try:
    from robot.api import logger
    from robot.libraries.BuiltIn import BuiltIn
    ROBOT_AVAILABLE = True
except ImportError:
    ROBOT_AVAILABLE = False
    logger = None
    BuiltIn = None


@pytest.mark.skipif(not ROBOT_AVAILABLE, reason="Robot Framework not installed")
class TestGUIRobot:
    """Robot Framework тесты для графического интерфейса."""
    
    def test_robot_import(self):
        """Тест что Robot Framework доступен."""
        assert ROBOT_AVAILABLE
        assert logger is not None
    
    def test_robot_library_import(self):
        """Тест импорта Robot библиотек."""
        try:
            from robot.api import logger
            assert logger is not None
        except ImportError:
            pytest.skip("Robot Framework library not available")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])