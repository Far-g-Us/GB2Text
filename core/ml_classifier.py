"""
ML Classifier for text segment detection in ROM files
Uses scikit-learn for classifying whether a data block is likely to contain text
"""

import logging
from typing import List, Dict, Tuple
import numpy as np

logger = logging.getLogger('gb2text.ml_classifier')

# Try to import scikit-learn, fall back to None if not available
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    RandomForestClassifier = None
    StandardScaler = None


class SegmentMLClassifier:
    """
    ML-based classifier for detecting text segments in ROM data
    Uses Random Forest for binary classification (text vs non-text)
    """
    
    def __init__(self):
        self.model = None
        self.scaler = None
        self.is_trained = False
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize the ML model"""
        if not SKLEARN_AVAILABLE:
            logger.warning("scikit-learn not available, ML classification disabled")
            return
        
        # Initialize Random Forest classifier
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
        self.scaler = StandardScaler()
        
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
        
        return np.array(features)
    
    def _train_initial_model(self):
        """Train on synthetic labeled data"""
        if not SKLEARN_AVAILABLE:
            return
        
        logger.info("Training initial ML model with synthetic data...")
        
        # Generate synthetic training data
        # Positive examples (text-like)
        text_samples = []
        for _ in range(500):
            # Generate random text-like bytes
            text_data = bytes([0x20 + (i % 94) for i in range(16)])  # ASCII printable
            # Add some variation
            text_data = bytes(b ^ (i % 256) for i, b in enumerate(text_data))
            features = self._extract_features(text_data)
            text_samples.append(features)
        
        # Negative examples (non-text)
        nontext_samples = []
        for _ in range(500):
            # Random bytes (code-like)
            import random
            code_data = bytes([random.randint(0, 255) for _ in range(16)])
            features = self._extract_features(code_data)
            nontext_samples.append(features)
        
        # Combine
        X = np.array(text_samples + nontext_samples)
        y = np.array([1] * 500 + [0] * 500)
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train
        self.model.fit(X_scaled, y)
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
        prob = self.model.predict_proba(features_scaled)[0][1]
        
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
    
    def analyze_segments(self, rom_data: bytes, start: int, end: int, block_size: int = 16) -> Dict:
        """
        Analyze a range of ROM data and return segment quality scores
        """
        results = {
            'segments': [],
            'ml_scores': [],
            'heuristic_scores': []
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
            
            if combined > 0.5:  # Threshold for text-like
                results['segments'].append({
                    'start': i,
                    'end': i + block_size,
                    'score': combined,
                    'ml_score': ml_score,
                    'heuristic': heuristic
                })
            
            i += block_size
        
        return results


# Global instance
ml_classifier = SegmentMLClassifier()


def get_ml_classifier() -> SegmentMLClassifier:
    """Get the global ML classifier instance"""
    return ml_classifier
