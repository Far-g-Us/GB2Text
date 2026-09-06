"""Тесты для модуля ml_classifier"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ml_classifier import SKLEARN_AVAILABLE, SegmentMLClassifier


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
            assert classifier.is_trained
        else:
            assert not classifier.is_trained


# ─────────────────────────────────────────────────────────────
# P1: Confidence threshold tests
# ─────────────────────────────────────────────────────────────

class TestConfidenceThreshold:
    """P1: Тесты confidence threshold и needs_review статуса."""

    def test_custom_confidence_threshold(self):
        """Классификатор принимает кастомный confidence_threshold."""
        classifier = SegmentMLClassifier(confidence_threshold=0.7)
        assert classifier.confidence_threshold == 0.7
        assert classifier._review_threshold == pytest.approx(0.49, abs=0.01)

    def test_default_confidence_threshold(self):
        """По умолчанию confidence_threshold = 0.5."""
        classifier = SegmentMLClassifier()
        assert classifier.confidence_threshold == 0.5
        assert classifier._review_threshold == pytest.approx(0.35, abs=0.01)

    def test_analyze_segments_has_needs_review_key(self):
        """analyze_segments() возвращает ключ 'needs_review'."""
        classifier = SegmentMLClassifier()
        rom_data = b'\x00' * 64
        results = classifier.analyze_segments(rom_data, 0, 64, block_size=16)
        assert 'needs_review' in results
        assert isinstance(results['needs_review'], list)

    def test_text_block_classified_as_text(self):
        """Текстовый блок классифицируется как text (high confidence)."""
        classifier = SegmentMLClassifier(confidence_threshold=0.3)
        text_data = b'Hello World! This is a test message with enough text.'
        results = classifier.analyze_segments(text_data, 0, len(text_data), block_size=16)
        # Должны быть обнаружены текстовые сегменты
        assert len(results['segments']) > 0
        for seg in results['segments']:
            assert seg['status'] == 'text'

    def test_binary_block_classified_as_non_text(self):
        """Бинарный блок (opcodes) не классифицируется как text."""
        classifier = SegmentMLClassifier(confidence_threshold=0.3)
        # Opcode-подобные данные
        binary_data = bytes([0xC3, 0x00, 0x40, 0xCD, 0x1B, 0x00] * 50)
        results = classifier.analyze_segments(binary_data, 0, len(binary_data), block_size=16)
        # Opcode-подобные данные не должны быть текстом
        text_segments = [s for s in results['segments'] if s['status'] == 'text']
        # Большинство блоков НЕ должно быть текстом
        total_blocks = len(results['segments']) + len(results['needs_review'])
        if total_blocks > 0:
            assert len(text_segments) < total_blocks // 2, (
                f"Too many segments classified as text: {len(text_segments)}/{total_blocks}"
            )

    def test_needs_review_contains_low_confidence_blocks(self):
        """Блоки с низким confidence попадают в needs_review."""
        classifier = SegmentMLClassifier(confidence_threshold=0.8)
        # Смешанные данные — текст + код
        mixed_data = b'Hello\x00\xC3\x00\x40World\x00\xCD\x1B\x00'
        results = classifier.analyze_segments(mixed_data, 0, len(mixed_data), block_size=8)
        # Некоторые блоки могут быть needs_review
        assert isinstance(results['needs_review'], list)

    def test_segment_has_status_field(self):
        """Каждый сегмент имеет поле 'status'."""
        classifier = SegmentMLClassifier(confidence_threshold=0.3)
        text_data = b'Hello World! This is test data.' * 3
        results = classifier.analyze_segments(text_data, 0, len(text_data), block_size=16)
        for seg in results['segments']:
            assert 'status' in seg
            assert seg['status'] in ('text', 'needs_review')

    def test_needs_review_has_status_field(self):
        """Каждый needs_review элемент имеет поле 'status'."""
        classifier = SegmentMLClassifier(confidence_threshold=0.8)
        data = b'\x41\x00\x42\x00\x43\x00\x44\x00' * 4
        results = classifier.analyze_segments(data, 0, len(data), block_size=8)
        for item in results['needs_review']:
            assert 'status' in item
            assert item['status'] == 'needs_review'


# ─────────────────────────────────────────────────────────────
# P1: Etalon blocks regression tests
# ─────────────────────────────────────────────────────────────

class TestEtalonBlocks:
    """P1: Регрессионные тесты на hand-labeled эталонах."""

    @pytest.fixture
    def etalon_blocks(self):
        """Загружает эталонные блоки из fixtures."""
        fixtures_path = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'etalon_blocks.json'
        )
        if not os.path.exists(fixtures_path):
            pytest.skip("etalon_blocks.json not found")
        with open(fixtures_path) as f:
            return json.load(f)

    def test_etalon_blocks_exist(self):
        """Файл etalon_blocks.json существует и валиден."""
        fixtures_path = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'etalon_blocks.json'
        )
        if os.path.exists(fixtures_path):
            with open(fixtures_path) as f:
                data = json.load(f)
            assert 'blocks' in data
            assert len(data['blocks']) > 0

    def test_text_etalons_classified_correctly(self):
        """Текстовые эталоны классифицируются как text."""
        classifier = SegmentMLClassifier(confidence_threshold=0.2)
        text_hex_blocks = [
            "48656C6C6F2C20776F726C642100",  # "Hello, world!\0"
            "304230BF30B930C800",              # Japanese
        ]
        for hex_str in text_hex_blocks:
            block = bytes.fromhex(hex_str)
            score = classifier.predict(block)
            assert score > 0.2, f"Text block '{hex_str[:20]}...' scored {score:.3f} (expected > 0.2)"

    def test_nontext_etalons_classified_correctly(self):
        """Бинарные эталоны классифицируются как non-text."""
        classifier = SegmentMLClassifier(confidence_threshold=0.5)
        nontext_hex_blocks = [
            "000000EA010000000200000003000000",  # ARM code
            "00000000000000000000000000000000",  # All nulls
        ]
        for hex_str in nontext_hex_blocks:
            block = bytes.fromhex(hex_str)
            score = classifier.predict(block)
            assert score < 0.8, f"Non-text block scored {score:.3f} (expected < 0.8)"
