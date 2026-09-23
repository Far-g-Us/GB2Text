"""
GB Text Extraction Framework

ПРЕДУПРЕЖДЕНИЕ ОБ АВТОРСКИХ ПРАВАХ:
Этот программный инструмент предназначен ТОЛЬКО для анализа ROM-файлов,
законно принадлежащих пользователю. Использование этого инструмента для
нелегального копирования, распространения или модификации защищенных
авторским правом материалов строго запрещено.

Этот проект НЕ содержит и НЕ распространяет никакие ROM-файлы или
защищенные авторским правом материалы. Все ROM-файлы должны быть
законно приобретены пользователем самостоятельно.

Этот инструмент разработан исключительно для исследовательских целей,
обучения и реверс-инжиниринга в рамках, разрешенных законодательством.
"""

"""
Plugin for The Legend of Zelda: The Minish Cap (GBA)

Game codes: BZME (USA), AGZJ (Japan), AGZE (Europe)

Text structure (established by reverse-engineering an actually owned ROM):
- Text is stored in "banks": each bank = a table of N u32 LE offsets
  followed by record data. The first table element is always N*4
  (table size), so records start right after the table.
- Address of record k = table address + offset[k].
- Records are terminated by 0x00; between banks there is 0xFF padding.
- USA text zone: 0x9B0000-0x9FB000.
- Dialog text is not compressed (verified by scanner).

Control codes (number of byte parameters):
  01:2 02:1 03:2 04:2 05:2 06:1 07:2 08:1 0C:1 0F:1

Decoder/encoder token grammar (compatible with core.extractor):
  [END]        - 0x00 (end of record)
  [LINEBREAK]  - 0x0A (line break inside a record)
  [TAB]        - 0x09
  [CC PP ...]  - control code with parameters (atomic)
  [MENUSEP]    - 0xFF: menu item separator inside a record (NOT a terminator)
  [UNK XX]     - unknown byte (should not occur with a complete table)

  NOTE about 0xFF: it is a byte parameter/separator, not end of record.
  The named token [MENUSEP] (instead of [FF]) deliberately does not match
  the [XX] hex pattern, otherwise core.extractor._split_messages would
  split a record into two.

NOTE: This plugin contains ONLY factual technical information.
Copyrighted dialogue and story content are not included.
"""

import logging
import re
import struct

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.zelda_tmc')

# Чармап Zelda: The Minish Cap. Байты ROM — tile-индексы шрифта игры,
# для латиницы совместимые с ASCII.
CHARMAP_ZELDA_TMC: dict[int, str] = {
    0x09: '\t',
    0x0A: '\n',
    0x20: ' ', 0x21: '!', 0x22: '"', 0x23: '#', 0x24: '$',
    0x25: '%', 0x26: '&', 0x27: '\'', 0x28: '(', 0x29: ')',
    0x2A: '*', 0x2B: '+', 0x2C: ',', 0x2D: '-', 0x2E: '.',
    0x2F: '/', 0x30: '0', 0x31: '1', 0x32: '2', 0x33: '3',
    0x34: '4', 0x35: '5', 0x36: '6', 0x37: '7', 0x38: '8',
    0x39: '9', 0x3A: ':', 0x3B: ';', 0x3C: '<', 0x3D: '=',
    0x3E: '>', 0x3F: '?', 0x40: '@', 0x41: 'A', 0x42: 'B',
    0x43: 'C', 0x44: 'D', 0x45: 'E', 0x46: 'F', 0x47: 'G',
    0x48: 'H', 0x49: 'I', 0x4A: 'J', 0x4B: 'K', 0x4C: 'L',
    0x4D: 'M', 0x4E: 'N', 0x4F: 'O', 0x50: 'P', 0x51: 'Q',
    0x52: 'R', 0x53: 'S', 0x54: 'T', 0x55: 'U', 0x56: 'V',
    0x57: 'W', 0x58: 'X', 0x59: 'Y', 0x5A: 'Z', 0x5B: '[',
    0x5C: '\\', 0x5D: ']', 0x5E: '^', 0x5F: '_', 0x60: '`',
    0x61: 'a', 0x62: 'b', 0x63: 'c', 0x64: 'd', 0x65: 'e',
    0x66: 'f', 0x67: 'g', 0x68: 'h', 0x69: 'i', 0x6A: 'j',
    0x6B: 'k', 0x6C: 'l', 0x6D: 'm', 0x6E: 'n', 0x6F: 'o',
    0x70: 'p', 0x71: 'q', 0x72: 'r', 0x73: 's', 0x74: 't',
    0x75: 'u', 0x76: 'v', 0x77: 'w', 0x78: 'x', 0x79: 'y',
    0x7A: 'z', 0x7B: '{', 0x7C: '|', 0x7D: '}', 0x7E: '~',
    0xE9: 'é',
}

TMC_CONTROL_CODE_PARAMS: dict[int, int] = {
    0x01: 2, 0x02: 1, 0x03: 2, 0x04: 2, 0x05: 2,
    0x06: 1, 0x07: 2, 0x08: 1, 0x0C: 1, 0x0F: 1,
}

# Текстовая зона (USA-ROM). Отдельный проход сканером подтверждает формат.
TMC_SCAN_RANGE = (0x9B0000, 0x9FB000)

TMC_MIN_ENTRIES = 4
TMC_MAX_OFFSET = 0x4000
TMC_MAX_ROWS = 512
TMC_MAX_RELOC_DISTANCE = 0x4000

# Записи, на которые есть ВНЕШНИЕ u32-ссылки в ROM (меню/инвентарь/код).
# Определено скриптом scripts_roms/tmc_ext_references.py.
# Внешние ссылки не отслеживаются инжектором — такие записи нельзя переезжать.
TMC_PROTECTED_RECORDS: list[int] = [
    0x9B9999, 0x9BA00B, 0x9BA19B, 0x9C07E7, 0x9C1900, 0x9CB93F,
    0x9CCA9A, 0x9CFB07, 0x9D0530, 0x9D2100, 0x9DAD8D, 0x9DC903,
    0x9DCE5B, 0x9DEEEC, 0x9E0008, 0x9F0209, 0x9F11C4,
]

# Минимальная полезная свободная зона для relocation (байт).
TMC_MIN_FREE_ZONE = 8

TMC_GAME_CODES = ['BZME']


class TMCTextDecoder:
    """Декодер/энкодер текста Zelda TMC с поддержкой банков записей.

    decode(data, start, length) — если объект привязан к банку (offsets),
    итерирует записи и разделяет их токеном [END]; иначе работает как
    обычный декодер потока байтов.
    """

    def __init__(self, charmap: dict[int, str], offsets: list[int] | None = None):
        self.charmap = charmap
        self.offsets = offsets
        self._reverse = {ch: byte for byte, ch in charmap.items() if ch is not None}

    def decode(self, data: bytes, start: int, length: int) -> str:
        end = min(start + length, len(data))
        if self.offsets:
            parts = []
            for rel in self.offsets:
                a = start + rel
                if a >= end:
                    break  # pragma: no cover
                b = a
                while b < end:  # pragma: no branch
                    bte = data[b]
                    if bte == 0x00:
                        break
                    if bte in TMC_CONTROL_CODE_PARAMS:
                        b += 1 + TMC_CONTROL_CODE_PARAMS[bte]
                        if b > end:
                            b = end  # pragma: no cover
                    else:
                        b += 1
                if b > a or data[a] in (0x00, 0xFF):  # pragma: no branch
                    parts.append(self._decode_one(data, a, b))
                    parts.append('[END]')
            return ''.join(parts)
        return self._decode_one(data, start, end)  # pragma: no cover

    def _decode_one(self, data: bytes, a: int, b: int) -> str:
        result: list[str] = []
        i = a
        while i < b:
            byte = data[i]
            if byte == 0x00:
                break  # pragma: no cover
            if byte == 0xFF:
                result.append('[MENUSEP]')
                i += 1
                continue
            if byte in TMC_CONTROL_CODE_PARAMS:
                n = 1 + TMC_CONTROL_CODE_PARAMS[byte]
                params = data[i + 1:i + n]
                if len(params) == TMC_CONTROL_CODE_PARAMS[byte]:  # pragma: no branch
                    result.append(f'[{byte:02X} ' + ' '.join(f'{p:02X}' for p in params) + ']')
                    i += n
                    continue
            if byte == 0x0A:  # pragma: no branch
                result.append('[LINEBREAK]')  # pragma: no cover
                i += 1  # pragma: no cover
                continue  # pragma: no cover
            if byte == 0x09:  # pragma: no cover
                result.append('[TAB]')  # pragma: no cover
                i += 1  # pragma: no cover
                continue  # pragma: no cover
            if byte in self.charmap:  # pragma: no branch
                ch = self.charmap[byte]
                if ch == '\n':  # pragma: no branch
                    result.append('[LINEBREAK]')  # pragma: no cover
                elif ch == '\t':  # pragma: no branch
                    result.append('[TAB]')  # pragma: no cover
                else:
                    result.append(ch)
                i += 1
                continue
            result.append(f'[UNK {byte:02X}]')  # pragma: no cover
            i += 1  # pragma: no cover
        return ''.join(result)

    def encode(self, text: str) -> bytes:
        """Кодирует строку с токенами обратно в байты ROM."""
        out = bytearray()
        i = 0
        n = len(text)
        while i < n:
            if text[i] == '[':
                m = re.match(r'\[(.*?)\]', text[i:])
                if m:
                    inner = m.group(1)
                    if inner == 'END':
                        out.append(0x00)
                        i += len(m.group(0))
                        continue
                    if inner == 'LINEBREAK':
                        out.append(0x0A)  # pragma: no cover
                        i += len(m.group(0))  # pragma: no cover
                        continue  # pragma: no cover
                    if inner == 'TAB':  # pragma: no cover
                        out.append(0x09)  # pragma: no cover
                        i += len(m.group(0))  # pragma: no cover
                        continue  # pragma: no cover
                    if inner == 'MENUSEP':
                        out.append(0xFF)  # pragma: no cover
                        i += len(m.group(0))  # pragma: no cover
                        continue  # pragma: no cover
                    parts = inner.split()  # pragma: no cover
                    if all(len(p) == 2 and all(c in '0123456789ABCDEF' for c in p) for p in parts):  # pragma: no cover
                        if len(parts) >= 2:  # pragma: no cover
                            cc = int(parts[0], 16)  # pragma: no cover
                            if cc in TMC_CONTROL_CODE_PARAMS and len(parts) - 1 == TMC_CONTROL_CODE_PARAMS[cc]:  # pragma: no cover
                                out.append(cc)  # pragma: no cover
                                for p in parts[1:]:  # pragma: no cover
                                    out.append(int(p, 16))  # pragma: no cover
                                i += len(m.group(0))  # pragma: no cover
                                continue  # pragma: no cover
                    if len(parts) == 2 and parts[0] == 'UNK' and len(parts[1]) == 2:  # pragma: no cover
                        out.append(int(parts[1], 16))  # pragma: no cover
                        i += len(m.group(0))  # pragma: no cover
                        continue  # pragma: no cover
                    out.append(0x5B)  # pragma: no cover
                    i += 1  # pragma: no cover
                    continue  # pragma: no cover
            ch = text[i]  # pragma: no cover
            if ch in self._reverse:  # pragma: no cover
                byte = self._reverse[ch]  # pragma: no cover
                if byte == 0x0A:  # pragma: no cover
                    out.append(0x0A)  # pragma: no cover
                elif byte == 0x09:  # pragma: no cover
                    out.append(0x09)  # pragma: no cover
                else:  # pragma: no cover
                    out.append(byte)  # pragma: no cover
            else:  # pragma: no cover
                raise ValueError(f'Не удалось закодировать символ: {ch!r}')  # pragma: no cover
            i += 1  # pragma: no cover
        return bytes(out)  # pragma: no cover


def _bank_free_zones(data: bytes | bytearray, banks: list[dict]) -> list[list[tuple[int, int]]]:  # pragma: no cover
    """Для каждого банка — список свободных 0xFF-зон (межбанковые паддинги),  # pragma: no cover
    куда можно перенести запись при relocation.  # pragma: no cover

    Возвращает список (per-bank) отсортированных интервалов (start, end).  # pragma: no cover
    Зона банка простирается от record_end банка до base следующего банка  # pragma: no cover
    (или до конца TMC_SCAN_RANGE для последнего). Внутри не адресуемы  # pragma: no cover
    0xFF-padding'и — они не входят в table_offsets и не используются игрой.  # pragma: no cover
    """  # pragma: no cover
    ordered = sorted(banks, key=lambda b: b["base"])  # pragma: no cover
    free: list[list[tuple[int, int]]] = []  # pragma: no cover
    data_len = len(data)  # pragma: no cover
    for i, bank in enumerate(ordered):  # pragma: no cover
        zone_start = bank["record_end"]  # pragma: no cover
        zone_end = ordered[i + 1]["base"] if i + 1 < len(ordered) else TMC_SCAN_RANGE[1]  # pragma: no cover
        # ограничиваем дистанцией от базы этого банка (offset хранится u32,  # pragma: no cover
        # но реальные offsets не превышают TMC_MAX_RELOC_DISTANCE от базы)  # pragma: no cover
        zone_end = min(zone_end, bank["base"] + TMC_MAX_RELOC_DISTANCE + 1)  # pragma: no cover
        # защита от обрезанного ROM  # pragma: no cover
        zone_end = min(zone_end, data_len)  # pragma: no cover
        runs: list[tuple[int, int]] = []  # pragma: no cover
        pos = max(zone_start, 0)  # pragma: no cover
        while pos < zone_end and pos < data_len:  # pragma: no cover
            if data[pos] == 0xFF:  # pragma: no cover
                j = pos  # pragma: no cover
                while j < zone_end and data[j] == 0xFF:  # pragma: no cover
                    j += 1  # pragma: no cover
                if j - pos >= TMC_MIN_FREE_ZONE:  # pragma: no cover
                    runs.append((pos, j))  # pragma: no cover
                pos = j  # pragma: no cover
            else:  # pragma: no cover
                pos += 1  # pragma: no cover
        free.append(runs)  # pragma: no cover
    return free  # pragma: no cover


def _scan_banks(data: bytes | bytearray, zone: tuple[int, int]) -> list[dict]:  # pragma: no cover
        """Сканирует текстовую зону и возвращает список банков.  # pragma: no cover

        Каждый банк: {'base', 'n', 'offsets', 'offsets_idx', 'table_offsets',  # pragma: no cover
        'table_count', 'record_end'}.  # pragma: no cover

        Сигнатура: N u32 LE, первый элемент таблицы == N*4 (размер таблицы),  # pragma: no cover
        target'ы дают записи с printables/control-кодами. Для поддержки
        relocation offsets могут быть немонотонными: длина таблицы берётся из
        vals[0] // 4, монотонность не требуется (запись могла переехать).

        Пустые записи (offset на байт 0x00/0xFF) НЕ исключаются из
        'table_offsets' (они адресуемы и занимают место), но исключаются из
        'offsets'/'offsets_idx', чтобы len(translations) == len(offsets).
        """
        a, b = zone
        b = min(b, len(data))
        banks: list[dict] = []
        pos = a
        while pos + TMC_MIN_ENTRIES * 4 <= b:
            first = struct.unpack_from('<I', data, pos)[0]
            if not (4 <= first < TMC_MAX_OFFSET):
                pos += 1
                continue
            table_count = first // 4
            if first != table_count * 4:
                pos += 1
                continue
            if table_count < TMC_MIN_ENTRIES or table_count > TMC_MAX_ROWS:
                pos += 1
                continue

            vals: list[int] = []
            cursor = pos
            valid = True
            for _ in range(table_count):
                if cursor + 4 > b:
                    valid = False
                    break
                v = struct.unpack_from('<I', data, cursor)[0]
                if not (4 <= v < TMC_MAX_OFFSET):
                    valid = False
                    break
                vals.append(v)
                cursor += 4
            if not valid or len(vals) < TMC_MIN_ENTRIES:
                pos += 1
                continue

            targets = [pos + v for v in vals]
            if any(t >= len(data) for t in targets):
                pos += 2
                continue

            non_empty_targets = [t for t in targets if data[t] not in (0x00, 0xFF)]
            if not non_empty_targets:
                pos += 1
                continue

            first_t = non_empty_targets[0]
            first = data[first_t:first_t + 96]
            if not any(0x20 <= x <= 0x7E for x in first):
                pos += 2
                continue

            ends = []
            for t in targets:
                if data[t] in (0x00, 0xFF):
                    ends.append(t)
                    continue
                j = t
                while j < len(data) and data[j] != 0x00:
                    if data[j] in TMC_CONTROL_CODE_PARAMS:
                        j += 1 + TMC_CONTROL_CODE_PARAMS[data[j]]
                    else:
                        j += 1
                ends.append(j)
            record_end = max(ends) + 1

            offsets: list[int] = []
            offsets_idx: list[int] = []
            for idx, v in enumerate(vals):
                if data[pos + v] not in (0x00, 0xFF):
                    offsets.append(v)
                    offsets_idx.append(idx)

            if len(offsets) != len(set(offsets)):
                pos += 1
                continue

            banks.append({
                'base': pos,
                'n': len(offsets),
                'offsets': offsets,
                'offsets_idx': offsets_idx,
                'table_offsets': list(vals),
                'table_count': table_count,
                'record_end': record_end,
            })
            pos = max(record_end, cursor)
        return banks


class ZeldaTMCPlugin(GamePlugin):
    """Плагин для The Legend of Zelda: The Minish Cap (GBA)."""

    def __init__(self) -> None:
        super().__init__()
        self._banks: list[dict] | None = None

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(TMC_GAME_CODES)
        return f'^GBA_({codes})$'

    def _get_banks(self, rom: GameBoyROM) -> list[dict]:
        if self._banks is None:  # pragma: no branch
            self._banks = _scan_banks(rom.data, TMC_SCAN_RANGE)
            logger.info(f"Zelda TMC: найдено банков текста: {len(self._banks)}")
        return self._banks  # pragma: no branch

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        banks = self._get_banks(rom)
        free_zones = _bank_free_zones(rom.data, banks)
        segments: list[dict] = []
        for bank, free in zip(banks, free_zones, strict=False):  # pragma: no branch
            offsets = bank['offsets']  # pragma: no branch
            decoder = TMCTextDecoder(CHARMAP_ZELDA_TMC, offsets=offsets)
            segments.append({
                'name': f'zelda_tmc_bank_{bank["base"]:07X}',
                'start': bank['base'],
                'end': bank['record_end'],
                'decoder': decoder,
                'compression': None,
                'charmap': CHARMAP_ZELDA_TMC,
                'terminators': [0x00],
                'bank_meta': {
                    'offsets': offsets,
                    'offsets_idx': bank['offsets_idx'],
                    'table_offsets': bank['table_offsets'],
                    'table_count': bank['table_count'],
                    'count': bank['n'],
                    'record_end': bank['record_end'],
                    'control_codes': TMC_CONTROL_CODE_PARAMS,
                    'free_zones': free,
                    'zone_end': max((z[1] for z in free), default=bank['record_end']),
                    'protected_records': TMC_PROTECTED_RECORDS,
                    'relocate': True,
                    'max_reloc_offset': TMC_MAX_RELOC_DISTANCE,
                },
            })
        if not segments:  # pragma: no branch
            logger.info("Zelda TMC: текстовые банки не найдены")
        return segments  # pragma: no branch

    def get_terminators(self, segment_name: str) -> list[int]:
        return [0x00]  # pragma: no cover
