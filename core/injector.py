from core.plugin import GamePlugin
from core.rom import GameBoyROM
from typing import List

class TextInjector:
    """Внедрение измененного текста обратно в ROM"""

    def __init__(self, rom_path: str):
        self.rom = GameBoyROM(rom_path)
        self.backup = bytearray(self.rom.data)

    def inject_segment(self, segment_name: str, new_texts: List[str], plugin: GamePlugin) -> bool:
        """Внедрение измененных текстов в указанный сегмент"""
        segments = plugin.get_text_segments(self.rom)
        target_segment = next((s for s in segments if s['name'] == segment_name), None)

        if not target_segment:
            return False

        # Реализация внедрения с учетом сжатия и кодировки
        # ...

        return True

    def save(self, output_path: str) -> bool:
        """Сохранение измененной ROM"""
        with open(output_path, 'wb') as f:
            f.write(self.rom.data)
        return True

    def revert(self):
        """Возврат к оригинальной ROM"""
        self.rom.data = bytearray(self.backup)