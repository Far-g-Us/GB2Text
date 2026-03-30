"""
Tests for plugins/generic.py module
"""

import pytest
from unittest.mock import Mock, MagicMock
from plugins.generic import GenericGBPlugin, GenericGBCPlugin, GenericGBAPlugin


class TestGenericGBPlugin:
    """Tests for GenericGBPlugin class"""

    def test_init(self):
        """Test GenericGBPlugin initialization"""
        plugin = GenericGBPlugin()
        assert plugin is not None

    def test_game_id_pattern(self):
        """Test game_id_pattern property"""
        plugin = GenericGBPlugin()
        assert plugin.game_id_pattern == r'^GAME_[0-9A-F]{2}$'

    def test_get_text_segments_no_pointers(self):
        """Test get_text_segments with no pointers found"""
        plugin = GenericGBPlugin()
        
        # Create mock ROM
        mock_rom = Mock()
        mock_rom.data = bytes(0x8000)  # 32KB ROM
        # Add empty pointer data
        mock_rom.data = bytes([0xFF] * 0x100) + bytes([0x00] * (0x8000 - 0x100))
        
        segments = plugin.get_text_segments(mock_rom)
        # Should return default segment when no pointers found
        assert isinstance(segments, list)
        assert len(segments) >= 1

    def test_get_text_segments_with_pointers(self):
        """Test get_text_segments with pointers"""
        plugin = GenericGBPlugin()
        
        # Create ROM with pointer data
        rom_data = bytearray(0x8000)
        # Add text at address 0x4200
        text = b'HELLO\x00'
        rom_data[0x4200:0x4200 + len(text)] = text
        # Add pointer to text at 0x200
        rom_data[0x200] = 0x00  # Low byte
        rom_data[0x201] = 0x42  # High byte
        
        mock_rom = Mock()
        mock_rom.data = bytes(rom_data)
        
        segments = plugin.get_text_segments(mock_rom)
        assert isinstance(segments, list)

    def test_estimate_segment_length(self):
        """Test _estimate_segment_length method"""
        plugin = GenericGBPlugin()
        rom_data = bytearray(0x100)
        # Put terminator at offset 0x10
        rom_data[0x00:0x10] = bytes([0x41] * 0x10)  # 'A' characters
        rom_data[0x10] = 0x00  # Terminator at offset 0x10
        
        length = plugin._estimate_segment_length(bytes(rom_data), 0)
        assert length == 17  # 16 chars + terminator

    def test_estimate_segment_length_no_terminator(self):
        """Test _estimate_segment_length when no terminator found"""
        plugin = GenericGBPlugin()
        rom_data = bytearray(0x100)  # Fill with 0x00
        
        length = plugin._estimate_segment_length(bytes(rom_data), 0)
        # Will find terminator at first byte
        assert length >= 1


class TestGenericGBCPlugin:
    """Tests for GenericGBCPlugin class"""

    def test_init(self):
        """Test GenericGBCPlugin initialization"""
        plugin = GenericGBCPlugin()
        assert plugin is not None

    def test_inherits_from_generic_gb(self):
        """Test that GBC plugin inherits from GB plugin"""
        plugin = GenericGBCPlugin()
        # Should have same methods as GB plugin
        assert hasattr(plugin, 'get_text_segments')
        assert hasattr(plugin, '_estimate_segment_length')
        assert hasattr(plugin, 'game_id_pattern')

    def test_get_text_segments(self):
        """Test get_text_segments for GBC"""
        plugin = GenericGBCPlugin()
        mock_rom = Mock()
        mock_rom.data = bytes(0x8000)
        
        segments = plugin.get_text_segments(mock_rom)
        assert isinstance(segments, list)


class TestGenericGBAPlugin:
    """Tests for GenericGBAPlugin class"""

    def test_init(self):
        """Test GenericGBAPlugin initialization"""
        plugin = GenericGBAPlugin()
        assert plugin is not None

    def test_get_text_segments_no_pointers(self):
        """Test get_text_segments with no pointers found"""
        plugin = GenericGBAPlugin()
        
        mock_rom = Mock()
        mock_rom.data = bytes(0x200000)  # 2MB GBA ROM
        
        segments = plugin.get_text_segments(mock_rom)
        assert isinstance(segments, list)
        # Should have fallback segments
        assert len(segments) >= 1

    def test_get_text_segments_with_gba_addresses(self):
        """Test get_text_segments converts GBA addresses to file offsets"""
        plugin = GenericGBAPlugin()
        
        # Create ROM with data at GBA address space
        rom_data = bytearray(0x200000)
        # Add text in typical GBA text area (converted from 0x08xxxxxx)
        text = b'PLAYER\x00'
        rom_data[0x3D0000 - 0x08000000:0x3D0000 - 0x08000000 + len(text)] = text
        
        mock_rom = Mock()
        mock_rom.data = bytes(rom_data)
        
        segments = plugin.get_text_segments(mock_rom)
        assert isinstance(segments, list)

    def test_inherits_from_generic_gb(self):
        """Test that GBA plugin inherits from GB plugin"""
        plugin = GenericGBAPlugin()
        assert hasattr(plugin, '_estimate_segment_length')


class TestGenericPluginEdgeCases:
    """Edge case tests for generic plugins"""

    def test_empty_rom_data(self):
        """Test with empty or very small ROM data"""
        plugin = GenericGBPlugin()
        mock_rom = Mock()
        mock_rom.data = bytes(0x100)
        
        segments = plugin.get_text_segments(mock_rom)
        assert isinstance(segments, list)

    def test_rom_with_only_zeros(self):
        """Test ROM data that is all zeros"""
        plugin = GenericGBPlugin()
        mock_rom = Mock()
        mock_rom.data = bytes([0x00] * 0x8000)
        
        segments = plugin.get_text_segments(mock_rom)
        assert isinstance(segments, list)

    def test_rom_with_only_ff(self):
        """Test ROM data that is all 0xFF"""
        plugin = GenericGBPlugin()
        mock_rom = Mock()
        mock_rom.data = bytes([0xFF] * 0x8000)
        
        segments = plugin.get_text_segments(mock_rom)
        assert isinstance(segments, list)

    def test_gba_rom_with_small_size(self):
        """Test GBA plugin with small ROM size"""
        plugin = GenericGBAPlugin()
        mock_rom = Mock()
        mock_rom.data = bytes(0x1000)  # Only 4KB
        
        segments = plugin.get_text_segments(mock_rom)
        assert isinstance(segments, list)

    def test_gbc_rom_edge_case(self):
        """Test GBC plugin edge cases"""
        plugin = GenericGBCPlugin()
        mock_rom = Mock()
        mock_rom.data = bytes(0x8000)
        
        # Should work without errors
        segments = plugin.get_text_segments(mock_rom)
        assert isinstance(segments, list)