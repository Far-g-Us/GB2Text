"""
ML Classifier for text segment detection in ROM files
Uses scikit-learn for classifying whether a data block is likely to contain text
"""

from __future__ import annotations

import importlib.util
import logging
import os
from typing import TYPE_CHECKING, Any, cast

logger = logging.getLogger('gb2text.ml_classifier')

#: Переменная окружения для числа потоков ML-классификатора.
ML_JOBS_ENV = 'GB2TEXT_ML_JOBS'


def _resolve_n_jobs() -> int:
    """Число потоков для Random Forest: 1 по умолчанию, не «все ядра».

    Встроенный классификатор не должен захватывать все ядра: его
    экземпляры создаются внутри процесса (сканер, GUI, тесты), и при
    параллельном прогоге это приводит к workers x cores потоков и
    нативным крашам воркеров. Переопределяется переменной окружения.
    """
    raw = os.environ.get(ML_JOBS_ENV)
    if not raw:
        return 1
    try:
        value = int(raw)
    except ValueError:
        logger.warning('%s=%r не число — берём 1 поток', ML_JOBS_ENV, raw)
        return 1
    return value if 1 <= value <= 64 else 1

# Try to import numpy, fall back to None if not available
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:  # pragma: no cover - фолбэк отсутствия опциональной зависимости (проверен subprocess-тестом test_optional_import_fallbacks)
    np = None  # type: ignore[assignment,unused-ignore]
    NUMPY_AVAILABLE = False

# Scikit-learn НЕ импортируется на уровне модуля.
#
# `core.scanner` импортирует этот модуль, а `core.scanner` — из
# `core.plugin_manager`, который тянет `api.cli` и `main.py`. То есть
# `import sklearn.ensemble` на старте стоил 1.08 с КАЖДОГО запуска CLI/API
# (измерено: `python -m api.cli plugins` — 2.94 с, из них 1.26 с на
# sklearn). Наличие пакета проверяется через find_spec, который не
# исполняет модуль, а сам импорт уезжает в `_sklearn_types()` —
# в единственное место, где реально создаётся модель.
def _sklearn_available() -> bool:
    """Есть ли scikit-learn, БЕЗ его импорта."""
    if importlib.util.find_spec("sklearn") is None:
        return False
    return importlib.util.find_spec("sklearn.ensemble") is not None


SKLEARN_AVAILABLE = _sklearn_available()

if TYPE_CHECKING:  # pragma: no cover - только для типов
    from sklearn.ensemble import RandomForestClassifier as RandomForestClassifier
    from sklearn.preprocessing import StandardScaler as StandardScaler

_SKLEARN_TYPES: tuple | None = None


def _sklearn_types() -> tuple:
    """Ленивый импорт sklearn. Возвращает (RandomForest, StandardScaler)."""
    global _SKLEARN_TYPES
    if _SKLEARN_TYPES is None:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.preprocessing import StandardScaler
        _SKLEARN_TYPES = (RandomForestClassifier, StandardScaler)
    return _SKLEARN_TYPES


class SegmentMLClassifier:
    """
    ML-based classifier for detecting text segments in ROM data
    Uses Random Forest for binary classification (text vs non-text)

    Confidence thresholds:
    - >= confidence_threshold: text (high confidence)
    - >= confidence_threshold * 0.7: needs_review (low confidence, recommend manual check)
    - < confidence_threshold * 0.7: non-text
    """

    def __init__(self, confidence_threshold: float = 0.5):
        # Any, а не None: sklearn импортируется лениво (см. _sklearn_types),
        # поэтому конкретный тип класса известен только в TYPE_CHECKING, а
        # без аннотации mypy выводил бы here None и ругался на predict_proba.
        self.model: Any = None
        self.scaler: Any = None
        self.is_trained = False
        self.confidence_threshold = confidence_threshold
        self._review_threshold = confidence_threshold * 0.7
        self._initialize_model()

    def _initialize_model(self):
        """Initialize the ML model"""
        if not SKLEARN_AVAILABLE:
            logger.warning("scikit-learn not available, ML classification disabled")
            return

        forest_cls, scaler_cls = _sklearn_types()

        # Initialize Random Forest classifier
        #
        # n_jobs: НЕ -1. Классификатор встроенный (GUI/сканер работает в
        # том же процессе), и `-1` забирал ВСЕ ядра в каждом экземпляре.
        # Экземпляров много: 17 в тестах плюс по одному на анализ, и при
        # параллельном прогоге (pytest-xdist, CI на 2 ядрах) это давало
        # workers x cores потоков joblib и нативные краши воркеров —
        # ровно то, что было видно в CI как
        # "worker 'gw3' crashed while running ...". По умолчанию 1 поток;
        # число берётся из GB2TEXT_ML_JOBS, если переменная задана и
        # разумна.
        self.model = forest_cls(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=_resolve_n_jobs()
        )
        self.scaler = scaler_cls()

        # Train on initial dataset
        self._train_initial_model()

    def _extract_features(self, data: bytes) -> np.ndarray:
        """
        Extract features from a block of data for ML classification
        Features:
        - ASCII printable ratio
        - Special character ratio (terminators, control codes)
        - Byte entropy
        - Repetition ratio
        - Null byte ratio
        - High byte ratio (>0x80)
        """
        if len(data) == 0:
            return np.zeros(10)

        features = []

        # 1. ASCII printable ratio (0x20-0x7E)
        printable = sum(1 for b in data if 0x20 <= b <= 0x7E)
        features.append(printable / len(data))

        # 2. Extended ASCII ratio (0xA0-0xFF)
        extended = sum(1 for b in data if 0xA0 <= b <= 0xFF)
        features.append(extended / len(data))

        # 3. Null byte ratio
        nulls = data.count(0x00)
        features.append(nulls / len(data))

        # 4. Control characters ratio (0x01-0x1F except TAB=0x09, LF=0x0A, CR=0x0D)
        control = sum(1 for b in data if 0x01 <= b <= 0x1F and b not in [0x09, 0x0A, 0x0D])
        features.append(control / len(data))

        # 5. Known terminators ratio (common text terminators in GB games)
        terminators = [0x00, 0x0A, 0x0D, 0xFF, 0x50]  # NULL, LF, CR, FF, common terminator
        term_count = sum(1 for b in data if b in terminators)
        features.append(term_count / len(data))

        # 6. Byte entropy (simplified)
        byte_counts = [0] * 256
        for b in data:
            byte_counts[b] += 1
        entropy = 0
        for count in byte_counts:
            if count > 0:
                p = count / len(data)
                entropy -= p * np.log2(p)
        features.append(entropy / 8.0)  # Normalize to 0-1

        # 7. Repetition ratio (consecutive identical bytes)
        repetitions = 0
        for i in range(1, len(data)):
            if data[i] == data[i-1]:
                repetitions += 1
        features.append(repetitions / max(1, len(data) - 1))

        # 8. Unique byte ratio
        unique = len(set(data))
        features.append(unique / 256.0)

        # 9. Text-like pattern score (sequences of printable chars)
        text_sequences = 0
        in_sequence = False
        for b in data:
            if 0x20 <= b <= 0x7E:
                if not in_sequence:
                    text_sequences += 1
                    in_sequence = True
            else:
                in_sequence = False
        features.append(text_sequences / max(1, len(data) // 4))

        # 10. Average byte value
        avg_byte = sum(data) / len(data) / 255.0
        features.append(avg_byte)

        return cast("np.ndarray", np.array(features))

    def _train_initial_model(self):
        """Train on synthetic labeled data with better diversity"""
        if not SKLEARN_AVAILABLE:
            return

        logger.info("Training initial ML model with synthetic data...")

        import random

        text_samples = []
        for _ in range(500):
            length = random.randint(8, 64)
            # Build directly
            buf = bytearray(length)
            for i in range(length):
                r = random.random()
                if r < 0.75:
                    buf[i] = random.randint(0x20, 0x7E)
                elif r < 0.85:
                    buf[i] = 0x20  # space
                elif r < 0.92:
                    buf[i] = random.choice([0x00, 0x0A, 0x0D, 0xFF])
                else:
                    buf[i] = random.randint(0xA0, 0xFF)  # extended
            features = self._extract_features(bytes(buf))
            text_samples.append(features)

        nontext_samples = []
        for _ in range(500):
            length = random.randint(8, 64)
            # Simulate code: many jumps, low values, high entropy
            buf = bytearray(length)
            for i in range(length):
                r = random.random()
                if r < 0.3:
                    buf[i] = random.randint(0x00, 0x1F)  # control codes
                elif r < 0.6:
                    buf[i] = random.randint(0xC0, 0xFF)  # high bytes (opcodes)
                else:
                    buf[i] = random.randint(0x00, 0xFF)  # random
            features = self._extract_features(bytes(buf))
            nontext_samples.append(features)

        x = np.array(text_samples + nontext_samples)
        y = np.array([1] * 500 + [0] * 500)

        x_scaled = self.scaler.fit_transform(x)

        self.model.fit(x_scaled, y)
        self.is_trained = True

        logger.info("Initial ML model trained successfully")

    def predict(self, data: bytes) -> float:
        """
        Predict if a block of data is likely text
        Returns probability (0-1)
        """
        if not SKLEARN_AVAILABLE or not self.is_trained:
            # Fall back to heuristic
            return self._heuristic_score(data)

        features = self._extract_features(data).reshape(1, -1)
        features_scaled = self.scaler.transform(features)

        # Get probability of being text
        prob: float = float(self.model.predict_proba(features_scaled)[0][1])

        return prob

    def _heuristic_score(self, data: bytes) -> float:
        """Fallback heuristic scoring when ML is not available"""
        if len(data) == 0:
            return 0.0

        # Basic readability score
        printable = sum(1 for b in data if 0x20 <= b <= 0x7E)
        readability = printable / len(data)

        # Penalize nulls
        nulls = data.count(0x00) / len(data)

        # Penalize high control character ratio
        control = sum(1 for b in data if 0x01 <= b <= 0x1F and b not in [0x09, 0x0A, 0x0D])
        control_ratio = control / len(data)

        score = readability - (nulls * 0.5) - (control_ratio * 0.3)

        return max(0.0, min(1.0, score))

    def analyze_segments(self, rom_data: bytes, start: int, end: int, block_size: int = 16) -> dict:
        """
        Analyze a range of ROM data and return segment quality scores

        Returns dict with:
        - segments: list of detected text segments
        - ml_scores: list of ML scores per block
        - heuristic_scores: list of heuristic scores per block
        - needs_review: list of blocks below confidence threshold (require manual check)
        """
        results: dict = {
            'segments': [],
            'ml_scores': [],
            'heuristic_scores': [],
            'needs_review': []
        }

        i = start
        while i + block_size <= end:
            block = rom_data[i:i + block_size]

            # Get ML prediction
            ml_score = self.predict(block)
            results['ml_scores'].append(ml_score)

            # Get heuristic score
            heuristic = self._heuristic_score(block)
            results['heuristic_scores'].append(heuristic)

            # Combined score (weighted average)
            if SKLEARN_AVAILABLE and self.is_trained:
                combined = ml_score * 0.7 + heuristic * 0.3
            else:
                combined = heuristic

            if combined >= self.confidence_threshold:
                # High confidence text
                results['segments'].append({
                    'start': i,
                    'end': i + block_size,
                    'score': combined,
                    'ml_score': ml_score,
                    'heuristic': heuristic,
                    'status': 'text'
                })
            elif combined >= self._review_threshold:
                # Low confidence — needs manual review
                results['needs_review'].append({
                    'start': i,
                    'end': i + block_size,
                    'score': combined,
                    'ml_score': ml_score,
                    'heuristic': heuristic,
                    'status': 'needs_review'
                })

            i += block_size

        return results

    def save_model(self, path: str):
        """Сохраняет модель и скейлер в файл"""
        if not SKLEARN_AVAILABLE or not self.is_trained:
            logger.warning("Модель не обучена, сохранение невозможно")
            return False
        try:
            import pickle
            model_data = {
                'model': self.model,
                'scaler': self.scaler,
                'is_trained': self.is_trained,
            }
            with open(path, 'wb') as f:
                pickle.dump(model_data, f)
            logger.info(f"Модель сохранена в {path}")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения модели: {e}")
            return False

    def load_model(self, path: str) -> bool:
        """Загружает модель и скейлер из файла"""
        if not SKLEARN_AVAILABLE:
            return False
        try:
            import pickle
            with open(path, 'rb') as f:
                model_data = pickle.load(f)
            self.model = model_data['model']
            self.scaler = model_data['scaler']
            self.is_trained = model_data.get('is_trained', True)
            logger.info(f"Модель загружена из {path}")
            return True
        except Exception as e:
            logger.error(f"Ошибка загрузки модели: {e}")
            return False


# Глобальный экземпляр — ЛЕНИВЫЙ.
#
# Раньше он создавался на импорте модуля, а `SegmentMLClassifier.__init__`
# поднимает Random Forest. Поскольку `core.scanner` импортирует этот модуль,
# а `core.scanner` тянет `core.plugin_manager` → `api.cli`/`main.py`, каждый
# запуск CLI/API платил ~1.0 с за sklearn (измерено: `python -m api.cli
# plugins` — 2.94 с, из них 0.99 с sklearn). Теперь экземпляр создаётся
# при первом `get_ml_classifier()`, то есть когда ML действительно нужен.
_ml_classifier: SegmentMLClassifier | None = None


def get_ml_classifier() -> SegmentMLClassifier:
    """Глобальный ML-классификатор (создаётся при первом обращении)."""
    global _ml_classifier
    if _ml_classifier is None:
        _ml_classifier = SegmentMLClassifier()
    return _ml_classifier
