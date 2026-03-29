"""Тесты для модуля ml_classifier"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ml_classifier import SegmentMLClassifier, SKLEARN_AVAILABLE


class TestMLClassifier:
    """Тесты для ML классификатора сегментов"""

    def test_classifier_initialization(self):
        """Тест инициализации классификатора"""
        classifier = SegmentMLClassifier()
        assert isinstance(classifier, SegmentMLClassifier)
        assert hasattr(classifier, 'model')
        assert hasattr(classifier, 'scaler')
        assert hasattr(classifier, 'is_trained')

    def test_extract_features_empty_data(self):
        """Тест извлечения признаков из пустых данных"""
        classifier = SegmentMLClassifier()
        features = classifier._extract_features(b'')
        assert len(features) == 10
        assert all(f == 0.0 for f in features)

    def test_extract_features_text_data(self):
        """Тест извлечения признаков из текстовых данных"""
        classifier = SegmentMLClassifier()
        text_data = b'Hello World! This is test text.'
        features = classifier._extract_features(text_data)
        assert len(features) == 10
        assert all(isinstance(f, (int, float)) for f in features)

    def test_extract_features_binary_data(self):
        """Тест извлечения признаков из бинарных данных"""
        classifier = SegmentMLClassifier()
        binary_data = bytes(range(256))  # Все возможные байты
        features = classifier._extract_features(binary_data)
        assert len(features) == 10
        assert all(isinstance(f, (int, float)) for f in features)

    def test_heuristic_score_empty(self):
        """Тест эвристической оценки для пустых данных"""
        classifier = SegmentMLClassifier()
        score = classifier._heuristic_score(b'')
        assert score == 0.0

    def test_heuristic_score_text(self):
        """Тест эвристической оценки для текста"""
        classifier = SegmentMLClassifier()
        text_data = b'Hello World!'
        score = classifier._heuristic_score(text_data)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_heuristic_score_binary(self):
        """Тест эвристической оценки для бинарных данных"""
        classifier = SegmentMLClassifier()
        binary_data = b'\x00\x01\x02\x03\xFF\xFE\xFD'
        score = classifier._heuristic_score(binary_data)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_predict_without_sklearn(self):
        """Тест предсказания без sklearn"""
        # Мокаем SKLEARN_AVAILABLE
        original_available = SKLEARN_AVAILABLE
        try:
            import core.ml_classifier
            core.ml_classifier.SKLEARN_AVAILABLE = False
            classifier = SegmentMLClassifier()
            score = classifier.predict(b'Hello World!')
            assert isinstance(score, float)
            assert 0.0 <= score <= 1.0
        finally:
            core.ml_classifier.SKLEARN_AVAILABLE = original_available

    @pytest.mark.skipif(not SKLEARN_AVAILABLE, reason="scikit-learn not available")
    def test_predict_with_sklearn(self):
        """Тест предсказания с sklearn"""
        classifier = SegmentMLClassifier()
        score = classifier.predict(b'Hello World!')
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    @pytest.mark.skipif(not SKLEARN_AVAILABLE, reason="scikit-learn not available")
    def test_predict_binary_data(self):
        """Тест предсказания для бинарных данных"""
        classifier = SegmentMLClassifier()
        binary_data = bytes(range(32))  # Управляющие символы
        score = classifier.predict(binary_data)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_analyze_segments_empty_range(self):
        """Тест анализа сегментов для пустого диапазона"""
        classifier = SegmentMLClassifier()
        rom_data = b'Hello World!'
        results = classifier.analyze_segments(rom_data, 0, 0, block_size=8)
        assert isinstance(results, dict)
        assert 'segments' in results
        assert 'ml_scores' in results
        assert 'heuristic_scores' in results

    def test_analyze_segments_text_data(self):
        """Тест анализа сегментов с текстовыми данными"""
        classifier = SegmentMLClassifier()
        rom_data = b'Hello World! This is a test message.'
        results = classifier.analyze_segments(rom_data, 0, len(rom_data), block_size=8)
        assert isinstance(results, dict)
        assert len(results['segments']) >= 0
        assert len(results['ml_scores']) > 0
        assert len(results['heuristic_scores']) > 0

    def test_analyze_segments_binary_data(self):
        """Тест анализа сегментов с бинарными данными"""
        classifier = SegmentMLClassifier()
        rom_data = bytes(range(256)) * 2
        results = classifier.analyze_segments(rom_data, 0, len(rom_data), block_size=16)
        assert isinstance(results, dict)
        assert len(results['ml_scores']) > 0
        assert len(results['heuristic_scores']) > 0

    def test_classifier_trained_status(self):
        """Тест статуса обучения классификатора"""
        classifier = SegmentMLClassifier()
        if SKLEARN_AVAILABLE:
            assert classifier.is_trained == True
        else:
            assert classifier.is_trained == False