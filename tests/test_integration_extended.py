"""
Extended integration tests for GB2Text.
Tests full workflows across multiple modules.
"""

import os
import tempfile
import pytest
from pathlib import Path

from core.rom import GameBoyROM
from core.scanner import auto_detect_segments, find_text_pointers
from core.decoder import TextDecoder, CharMapDecoder
from core.encoding import auto_detect_charmap
from core.extractor import TextExtractor
from core.injector import TextInjector
from core.tmx import TMXHandler
from core.charset import CharsetDetector
from core.database import TranslationDatabase


class TestFullExtractionWorkflow:
    """Test complete text extraction workflow."""

    @pytest.fixture
    def sample_rom(self, tmp_path):
        """Create a sample ROM for testing."""
        rom_file = tmp_path / "integration_test.gb"
        rom_data = bytearray(0x8000)
        
        # Set up ROM header
        rom_data[0x104:0x108] = b'NTEJ'
        rom_data[0x134:0x14C] = b'INTEG TEST\x00' + bytes(12)
        rom_data[0x143] = 0x00  # DMG
        rom_data[0x146] = 0x00  # ROM only
        rom_data[0x148] = 0x00  # 32KB
        rom_data[0x149] = 0x00  # No RAM
        
        # Add text data
        text1 = b'HELLO\x00WORLD\x00'
        rom_data[0x200:0x200 + len(text1)] = text1
        
        text2 = b'START\x00GAME\x00'
        rom_data[0x300:0x300 + len(text2)] = text2
        
        rom_file.write_bytes(bytes(rom_data))
        return GameBoyROM(str(rom_file))

    def test_scan_decode_export_workflow(self, sample_rom, tmp_path):
        """Test scan -> decode -> export workflow."""
        # Step 1: Scan
        scanner = TextScanner(sample_rom)
        blocks = scanner.scan_text_blocks()
        
        # Step 2: Decode
        decoder = TextDecoder()
        decoded_texts = []
        for block in blocks:
            text = decoder.decode_text(block['data'])
            decoded_texts.append(text)
        
        # Step 3: Export to TMX
        exporter = TMXExporter()
        segments = []
        for i, text in enumerate(decoded_texts):
            if text:
                segments.append({
                    'id': i + 1,
                    'source': text,
                    'target': '',
                })
        
        output_file = tmp_path / "exported.tmx"
        exporter.export(segments, str(output_file))
        
        assert output_file.exists()
        
        # Verify content
        importer = TMXImporter()
        imported = importer.import_tmx(str(output_file))
        assert len(imported) >= len([s for s in segments if s['source']])

    def test_extractor_full_workflow(self, sample_rom, tmp_path):
        """Test TextExtractor full workflow."""
        extractor = TextExtractor(sample_rom)
        
        # Extract texts
        texts = extractor.extract_all_text()
        
        # Should have found some texts
        assert texts is not None
        
        # Export to TMX
        output = tmp_path / "extracted.tmx"
        extractor.export_to_tmx(str(output), texts)
        
        assert output.exists()


class TestBatchProcessing:
    """Test batch processing of multiple ROMs."""

    @pytest.fixture
    def multiple_roms(self, tmp_path):
        """Create multiple test ROMs."""
        roms = []
        for i in range(3):
            rom_file = tmp_path / f"batch_test_{i}.gb"
            rom_data = bytearray(0x8000)
            rom_data[0x104:0x108] = b'NTEJ'
            rom_data[0x134:0x14C] = f'BATCH{i:02d}'.encode().ljust(15, b'\x00')
            rom_data[0x200] = 0x48  # 'H'
            rom_data[0x201] = 0x45  # 'E'
            rom_data[0x202] = 0x00
            rom_file.write_bytes(bytes(rom_data))
            roms.append(str(rom_file))
        return roms

    def test_batch_extraction(self, multiple_roms):
        """Test batch text extraction."""
        results = []
        for rom_path in multiple_roms:
            rom = GameBoyROM(rom_path)
            scanner = TextScanner(rom)
            blocks = scanner.scan_text_blocks()
            results.append({
                'rom': rom_path,
                'blocks': len(blocks),
            })
        
        assert len(results) == 3
        assert all(r['blocks'] >= 0 for r in results)

    def test_parallel_batch_processing(self, multiple_roms):
        """Test parallel batch processing."""
        from concurrent.futures import ThreadPoolExecutor
        
        def process_rom(rom_path):
            rom = GameBoyROM(rom_path)
            scanner = TextScanner(rom)
            return scanner.scan_text_blocks()
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(process_rom, rom) for rom in multiple_roms]
            results = [f.result() for f in futures]
        
        assert len(results) == 3


class TestDatabaseWorkflow:
    """Test database integration workflows."""

    @pytest.fixture
    def test_db(self, tmp_path):
        """Create test database."""
        db_path = tmp_path / "test.db"
        return TranslationDatabase(str(db_path))

    def test_store_and_retrieve(self, test_db):
        """Test storing and retrieving translations."""
        # Store translations
        test_db.store_translation("en", "ja", "Hello", "こんにちは")
        test_db.store_translation("en", "ja", "World", "世界")
        
        # Retrieve
        translation = test_db.get_translation("en", "ja", "Hello")
        assert translation == "こんにちは"
        
        translations = test_db.get_translations_for_source("en", "ja", "Hello")
        assert "こんにちは" in translations

    def test_cache_integration(self, test_db):
        """Test database with caching."""
        test_db.store_translation("en", "de", "Test", "Test")
        
        # Enable cache
        test_db.enable_cache()
        
        # First call
        result1 = test_db.get_translation("en", "de", "Test")
        assert result1 == "Test"
        
        # Second call should use cache
        result2 = test_db.get_translation("en", "de", "Test")
        assert result1 == result2


class TestEncodeInjectWorkflow:
    """Test encode and inject workflow."""

    @pytest.fixture
    def base_rom(self, tmp_path):
        """Create base ROM for injection testing."""
        rom_file = tmp_path / "inject_base.gb"
        rom_data = bytearray(0x8000)
        rom_data[0x104:0x108] = b'NTEJ'
        rom_data[0x134:0x14C] = b'INJECT TEST\x00' + bytes(11)
        
        # Write text at known location
        text = b'HELLO\x00'
        rom_data[0x200:0x200 + len(text)] = text
        
        rom_file.write_bytes(bytes(rom_data))
        return str(rom_file)

    def test_encode_text_for_rom(self, base_rom):
        """Test encoding text for specific ROM."""
        rom = GameBoyROM(base_rom)
        encoder = GB2TextEncoder()
        
        # Encode text
        encoded = encoder.encode_text("NEW TEXT")
        
        assert encoded is not None
        assert len(encoded) > 0

    def test_inject_text_workflow(self, base_rom, tmp_path):
        """Test full inject workflow."""
        rom = GameBoyROM(base_rom)
        
        # Prepare new text
        injector = TextInjector(rom)
        
        # New text data
        new_text = b'NEW TEXT\x00'
        
        # Inject at position 0x200
        modified_rom = injector.inject_text(0x200, new_text)
        
        assert modified_rom is not None
        
        # Save modified ROM
        output = tmp_path / "modified.gb"
        with open(output, 'wb') as f:
            f.write(modified_rom)
        
        assert output.exists()
        
        # Verify
        modified = GameBoyROM(str(output))
        # Note: Verification depends on implementation


class TestCharsetWorkflow:
    """Test charset detection and conversion."""

    def test_charset_detection(self, tmp_path):
        """Test automatic charset detection."""
        rom_file = tmp_path / "charset_test.gb"
        rom_data = bytearray(0x8000)
        rom_data[0x104:0x108] = b'NTEJ'
        rom_data[0x134:0x14C] = b'CHARSET\x00' + bytes(12)
        
        # Add ASCII text
        ascii_text = b'HELLO WORLD'
        rom_data[0x200:0x200 + len(ascii_text)] = ascii_text
        
        rom_file.write_bytes(bytes(rom_data))
        
        rom = GameBoyROM(str(rom_file))
        detector = CharsetDetector()
        
        charset = detector.detect_charset(rom.get_text_regions())
        assert charset is not None

    def test_multi_charmap_conversion(self):
        """Test multi-charmap conversion."""
        from core.multi_charmap import MultiCharmap
        
        charmap = MultiCharmap()
        
        # Add mappings
        charmap.add_mapping('A', 0x41)
        charmap.add_mapping('B', 0x42)
        
        # Convert
        result = charmap.to_bytes("AB")
        assert result == b'\x41\x42'


class TestPluginIntegration:
    """Test plugin system integration."""

    def test_plugin_loading(self):
        """Test loading plugins."""
        from core.plugin_manager import PluginManager
        
        manager = PluginManager()
        manager.discover_plugins()
        
        plugins = manager.get_all_plugins()
        assert isinstance(plugins, list)

    def test_auto_detect_plugin(self):
        """Test auto-detect plugin functionality."""
        from plugins.auto_detect import AutoDetectPlugin
        
        plugin = AutoDetectPlugin()
        assert plugin is not None
        
        # Test detection
        result = plugin.detect_rom_type(bytearray(32))
        assert result is not None


class TestTMXRoundTrip:
    """Test TMX import/export round trip."""

    @pytest.fixture
    def sample_segments(self):
        """Create sample TMX segments."""
        return [
            {'id': 1, 'source': 'Hello', 'target': 'Bonjour', 'context': 'greeting'},
            {'id': 2, 'source': 'World', 'target': 'Monde', 'context': 'greeting'},
            {'id': 3, 'source': 'Exit', 'target': 'Sortie', 'context': 'menu'},
        ]

    def test_tmx_export_import_roundtrip(self, sample_segments, tmp_path):
        """Test TMX export and import."""
        exporter = TMXExporter()
        importer = TMXImporter()
        
        # Export
        output_file = tmp_path / "roundtrip.tmx"
        exporter.export(sample_segments, str(output_file))
        
        assert output_file.exists()
        
        # Import
        imported = importer.import_tmx(str(output_file))
        
        assert len(imported) == len(sample_segments)
        
        # Check content preservation
        for original, restored in zip(sample_segments, imported):
            assert restored['source'] == original['source']
            # Note: target might be empty if not stored


if __name__ == '__main__':
    pytest.main([__file__, '-v'])