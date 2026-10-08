"""
GB Text Extraction Framework

COPYRIGHT WARNING:
This software tool is intended ONLY for the analysis of ROM files
lawfully owned by the user. Any use of this tool to
illegally copy, distribute, or modify copyrighted
material is strictly prohibited.

This project does NOT contain or distribute any ROM files or
copyrighted material. All ROM files must be
lawfully acquired by the user independently.

This tool is developed exclusively for research purposes,
education, and reverse engineering within the limits permitted by law.
"""

"""
Plugin for Final Fantasy IV Advance (GBA)

Game codes: BZ4E (USA), BZ4J (Japan), BZ4P (Europe)

Text encoding: custom single-byte + multi-byte (Square Enix)
Source: https://datacrystal.tcrf.net/wiki/Final_Fantasy_IV_Advance/TBL

This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging
import re

from core.plugin import GamePlugin
from core.rom import GameBoyROM
from plugins.aliased_records import merge_aliased_records

logger = logging.getLogger('gb2text.plugins.ff4_advance')

_UNKNOWN_TOKEN_RE = re.compile(r'\[[0-9A-F]{2,6}\]')
# Любой control-токен: `[AC]`, `[NAME_CECIL]`, `[F6]`. Собран из двух форм,
# чтобы «запись только из токенов» распознавалась одинаково что для
# неизвестных байт, что для именованных контолов.
_CONTROL_TOKEN_RE = re.compile(r'(?:\[[0-9A-F]{2,6}\]|\[[A-Z_][A-Z0-9_]*\])+')


def _strip_unknown_tokens(text: str) -> str:
    """Removes hex tokens of unknown bytes ('[C280]', '[9A]', etc.)."""
    return _UNKNOWN_TOKEN_RE.sub('', text)


def _code_table_targets(targets: list[int], min_run: int = 12) -> set[int]:
    """Цели указателей, указывающие в посимвольную таблицу кодов, а не в текст.

    Сразу за таблицей указателей (0x2E98BC) лежит не диалог, а
    перечисление charmap в виде «2 байта на символ»: `6f 0c` -> 'あ',
    `c2 80 0c` -> '[C280]'. Такие записи не переводимы (это кодировка), и
    отдавать их инжектору нельзя: перезапись сломает раскладку символов.

    Критерий обязателен НЕ по длине текста, а по геометрии указателей:
    длина записи меняется переводом, а цели указателей — нет. Запись
    считается кодом, если её span (следующая цель минус текущая) не больше
    _CODE_SPAN_MAX и она лежит в плотном ряду из >= min_run таких целей с
    шагом <= _CODE_SPAN_MAX.

    min_run = 12, а не меньше: на BZ4E меню-строка '0', '/', 'Empty:/'
    даёт РОВНО такую же геометрию (цели с шагом 1-3, каждая закрыта
    0x0C), и при min_run=8 фильтр съедал 6 настоящих записей, включая
    каноническое 'Empty'. Настоящая таблица кодов — ряд длиной 303
    (0x2E98BC-0x2E9B33), поэтому 12 отсекает её целиком и не задевает
    меню. Одиночные короткие записи ('OK', '1') в такой ряд не попадают.
    """
    ordered = sorted(set(targets))
    # У последней цели span до следующей может быть большим (конец таблицы
    # кодов — обрыв), поэтому берём span предпоследней цели: в плотном ряду
    # последняя запись устроена так же, как и остальные.
    last_span = (ordered[-1] - ordered[-2]) if len(ordered) > 1 else 0
    code_ranges: list[tuple[int, int]] = []
    run_start = 0
    for pos in range(1, len(ordered) + 1):
        broken = (pos == len(ordered)
                  or ordered[pos] - ordered[pos - 1] > _CODE_SPAN_MAX)
        if broken:
            run = ordered[run_start:pos]
            if len(run) >= min_run:
                code_ranges.append((run[0], run[-1]))
            run_start = pos
    if not code_ranges:
        return set()
    flagged = set()
    for pos, target in enumerate(ordered):
        span = (ordered[pos + 1] - target) if pos + 1 < len(ordered) else last_span
        if span > _CODE_SPAN_MAX:
            continue
        for lo, hi in code_ranges:
            if lo <= target <= hi:
                flagged.add(target)
                break
    return flagged


def _is_junk_record(decoded: str) -> bool:
    """Мусорная запись: пусто, только токены, либо два и более неизвестных.

    ПРАВИЛО: фильтр не должен зависеть от длины текста. Решение принимается
    при обратном скане уже по ПЕРЕВОДУ, и русский перевод почти всегда
    короче оригинала. Старые пороги «clean_len <= 1» и «чистого текста
    меньше 30%» отсекали запись, переведённую в пару символов, — запись
    исчезала из манифеста и становилась непереводимой. Число неизвестных
    токенов перевод не меняет (набор символов тот же), поэтому только
    этот критерий стабилен между исходным и пропатченным ROM.

    Запись, состоящая ТОЛЬКО из control-токенов (например `[AC]`), —
    инвариантно мусорная: перевод не может сделать её содержательнее, а
    переводить нечего. Отдельный критерий, а не «длина»: длина запрещена.
    """
    if not decoded or all(c in ' \t\n' for c in decoded):
        return True
    if _CONTROL_TOKEN_RE.fullmatch(decoded.strip()):
        return True
    return len(_UNKNOWN_TOKEN_RE.findall(decoded)) >= 2


# FF4 Advance character table - BZ4E (USA)
# Source: FF4 Hacking Wiki / DataCrystal TBL
# Single-byte characters (0x00-0x7F)
CHARMAP_FF4: dict[int, str] = {
    0x00: ' ', 0x01: 'e', 0x02: 'o', 0x03: 't', 0x04: 'a', 0x05: 'r',
    0x06: 'n', 0x07: 's', 0x08: 'i', 0x09: 'h', 0x0A: 'l', 0x0B: '.',
    0x0D: 'u', 0x0E: 'd', 0x0F: 'm', 0x10: 'y', 0x11: 'g', 0x12: 'c',
    0x13: 'w', 0x14: ':', 0x15: 'f', 0x16: '!', 0x17: 'p', 0x18: 'b',
    0x19: 'v', 0x1A: 'I', 0x1B: 'k', 0x1C: "'", 0x1D: ',', 0x1E: 'T',
    0x1F: 'S', 0x20: '?', 0x21: 'W', 0x22: 'C', 0x23: 'A', 0x24: 'B',
    0x25: 'M', 0x26: 'H', 0x27: 'G', 0x28: 'R', 0x29: 'Y', 0x2A: 'D',
    0x2B: 'E', 0x2C: 'L', 0x2D: 'P', 0x2E: 'O', 0x2F: 'N', 0x30: 'F',
    0x31: '-', 0x32: 'z', 0x34: 'K', 0x37: 'U', 0x38: 'j', 0x39: 'x',
    0x3F: '1', 0x40: 'Z', 0x42: '0', 0x43: 'q', 0x45: '2', 0x48: '*',
    0x49: '3', 0x4A: 'V', 0x4B: '"', 0x4F: '(', 0x50: ')', 0x52: '4',
    0x54: 'Q', 0x55: '5', 0x56: '9', 0x57: 'J', 0x58: 'X', 0x5A: '/',
    0x5C: '6', 0x5E: '7', 0x60: '+', 0x64: '8', 0x66: '&', 0x67: '%',
    0x69: ';', 0x6A: '_',
    # Hiragana (0x6F-0x7F)
    0x6F: '\u3042', 0x70: '\u3044', 0x71: '\u3046', 0x72: '\u3048', 0x73: '\u304A',
    0x74: '\u304B', 0x75: '\u304D', 0x76: '\u304F', 0x77: '\u3051', 0x78: '\u3053',
    0x79: '\u3055', 0x7A: '\u3057', 0x7B: '\u3059', 0x7C: '\u305B', 0x7D: '\u305D',
    0x7E: '\u305F', 0x7F: '\u3061',
    # Multi-byte kanji - BZ4E (0xC2XX-0xD6XX)
    0xC4A4: '\u2026',  # Ellipsis
    0xC3A3: '\u793C', 0xC6B6: '\u516C', 0xC48E: '\u6210', 0xC4BA: '\u901A',
    0xC68E: 'h', 0xC69E: 'a', 0xC69F: 'c', 0xC6A0: 'r',
    0xC7BF: ',',
    0xCB81: '%', 0xCBB0: 'i', 0xCBBB: 'g', 0xCBBD: 'l', 0xCBBF: '\u78BA',
    0xCE8E: 'b', 0xCE8F: 'f', 0xCE90: 'j', 0xCE91: 'k', 0xCE94: 'q',
    0xCE95: 'v', 0xCE96: 'w', 0xCE97: 'x', 0xCE99: 'z',
    0xD181: '4',
}

# FF4 Advance control codes (from DataCrystal)
FF4_CONTROL_CODES: dict[int, str] = {
    # End of line
    0x0C: '[END]',
    # Line breaks
    0xC596: '[LINEBREAK_DIALOGUE]',
    0xC683: '[LINEBREAK_MENU]',
    # Names
    0xC598: '[NAME_CECIL]', 0xC599: '[NAME_KAIN]', 0xC59A: '[NAME_ROSA]',
    0xC59B: '[NAME_RYDIA]', 0xC59C: '[NAME_CID]', 0xC59D: '[NAME_TELLAH]',
    0xC59E: '[NAME_EDWARD]', 0xC59F: '[NAME_YANG]',
    0xC5A0: '[NAME_PALOM]', 0xC5A1: '[NAME_POLOM]', 0xC5A2: '[NAME_EDGE]',
    0xC5A3: '[NAME_FUSOYA]',
    # Clear box
    0xC5AC: '[CLEAN_BOX]',
    # Images
    0xC5AD: '[PIC_CECIL]', 0xC5AE: '[PIC_KAIN]', 0xC5AF: '[PIC_ROSA]',
    0xC5B0: '[PIC_RYDIA]', 0xC5B1: '[PIC_CID]', 0xC5B2: '[PIC_TELLAH]',
    0xC5B3: '[PIC_EDWARD]', 0xC5B4: '[PIC_YANG]',
    0xC5B5: '[PIC_PALOM]', 0xC5B6: '[PIC_POLOM]', 0xC5B7: '[PIC_EDGE]',
    0xC5B8: '[PIC_FUSOYA]', 0xC5B9: '[PIC_GOLBEZ]',
    # Remove image
    0xC5BA: '[REMOVE_PIC]',
    # Variables
    0xC5BB: '[VAR1]', 0xC5BD: '[CUR_HP]', 0xC5BE: '[VAR2]', 0xC5BF: '[MAX_HP]',
    # Treasure/Inn
    0xC680: '[TREASURE_ITEM]', 0xC681: '[INN_GIL]',
    # Box control
    0xC682: '[BOX_NO_BUTTON]',
}

# FF4 Advance text terminators
# Only 0x0C is the end-of-line marker
# 0x00 is a SPACE character, not a terminator
FF4_TERMINATORS = [0x0C]

# Порог «запись не длиннее этого — кандидат в таблицу кодов» (в байтах,
# включая разделитель 0x0C). Настоящие записи меню короче 4 байт редко.
_CODE_SPAN_MAX = 3

# Алиасы 1-байт/2-байт ('h' = 0x09 и 0xC68E и т.п.) — РАЗЛИЧАЕМ, как в FF5:
# 2-байтные формы вырезаны, decode показывает сырые токены '[XXXX]'.
# Замена 2-байтной формы 1-байтной сдвигает абсолютные позиции хвоста
# и ломает указатели в середину записи. Control-коды не тронуты.
_single_values = {char for code, char in CHARMAP_FF4.items() if code < 0x100}
for _code in [code for code, char in CHARMAP_FF4.items()
              if code >= 0x100 and char in _single_values]:
    del CHARMAP_FF4[_code]
del _single_values, _code

# Known pointer table locations for FF4 Advance (BZ4E)
# Source: https://datacrystal.tcrf.net/wiki/Final_Fantasy_IV_Advance/ROM_map
# Verified empirically on BZ4E: pointers are OFFSETS from 0x2E3670 (table start - 0x10),
# NOT from 0x2E98BC. Index 0 -> 0x2E98BC (data stream start), index 6286 -> 0x323B48.
# The old base 0x2E98BC produced an exact shift of 0x624C, cutting strings mid-word.
FF4_POINTER_TABLE_OFFSET = 0x2E3680  # Start of the pointer table (6287 entries of 4 bytes)
FF4_POINTER_COUNT = 6287             # Pointer count
FF4_TEXT_DATA_START = 0x2E3670       # Pointer offset base (table start - 0x10)
FF4_TEXT_BLOCK_END = 0x323B64        # End of the text block
FF4_POINTER_SIZE = 4                 # Each pointer 4 bytes (2-byte value + 2-byte padding)

# Game codes for detection
FF4_GAME_CODES = ['BZ4E', 'BZ4J', 'BZ4P']


class FF4TextDecoder:
    """FF4 Advance text decoder with multi-byte control code support"""

    _TOKEN_RE = re.compile(r'\[([0-9A-F]{2}(?:[0-9A-F]{2})*)\]|\[([A-Z_][A-Z0-9_]*)\]|(.)')

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap
        # Single-byte (keys < 0x100): priority - shorter mapping
        self.rev_single: dict[str, int] = {}
        # Multi-byte (keys >= 0x100): fallback for characters without a single-byte variant
        self.rev_multi: dict[str, tuple[int, int]] = {}
        for code, ch in charmap.items():
            if code < 0x100:
                if ch not in self.rev_single:  # pragma: no branch
                    self.rev_single[ch] = code
            elif code not in FF4_CONTROL_CODES:  # pragma: no branch
                if ch not in self.rev_multi:  # pragma: no branch
                    self.rev_multi[ch] = (code >> 8, code & 0xFF)
        # Control codes -> bytes (terminator 0x0C - single byte, the rest - 2 bytes)
        # Keys without brackets '[NAME_CECIL]' -> 'NAME_CECIL' - matches the capture regex.
        self.rev_control: dict[str, bytes] = {}
        for code, name in FF4_CONTROL_CODES.items():
            self.rev_control[name[1:-1]] = bytes([code]) if code < 0x100 else code.to_bytes(2, 'big')

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        i = start
        end = min(start + length, len(data))

        while i < end:
            byte = data[i]

            if byte in FF4_TERMINATORS:
                break

            # Multi-byte characters (prefix 0xC2-0xD6)
            if 0xC2 <= byte <= 0xD6 and i + 1 < end and data[i + 1] not in FF4_TERMINATORS:
                second = data[i + 1]
                code = (byte << 8) | second
                if code in FF4_CONTROL_CODES:
                    result.append(FF4_CONTROL_CODES[code])
                elif code in self.charmap:
                    result.append(self.charmap[code])
                else:
                    result.append(f'[{byte:02X}{second:02X}]')
                i += 2
                continue

            # Single-byte characters
            if byte in self.charmap:
                result.append(self.charmap[byte])
            else:
                result.append(f'[{byte:02X}]')
            i += 1

        return ''.join(result)

    def encode(self, text: str) -> bytes:
        result = bytearray()
        for match in self._TOKEN_RE.finditer(text):
            hex_val, named, char = match.groups()
            if hex_val is not None:
                result.extend(bytes.fromhex(hex_val))
            elif named is not None:
                ctrl = self.rev_control.get(named)
                if ctrl is not None:
                    result.extend(ctrl)
                else:
                    raise ValueError(f"Unknown control token: [{named}]")
            else:
                single = self.rev_single.get(char)
                if single is not None:
                    result.append(single)
                else:
                    pair = self.rev_multi.get(char)
                    if pair is not None:
                        result.extend(pair)
                    else:
                        raise ValueError(f"Character not in charmap: {char!r}")
        return bytes(result)


class FF4AdvancePlugin(GamePlugin):
    """Plugin for Final Fantasy IV Advance (GBA)"""

    def __init__(self):
        super().__init__()
        self._decoder = FF4TextDecoder(CHARMAP_FF4)

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(FF4_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_pointer_size(self, rom: GameBoyROM) -> int:
        return FF4_POINTER_SIZE

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Extract FF4 Advance text segments using the pointer table"""
        logger.info("Извлечение текстовых сегментов для Final Fantasy IV Advance")

        segments: list[dict] = []
        candidates: list[dict] = []

        # Read the pointer table and create segments for each text record
        # Pointer table at 0x2E3680, each record is 4 bytes (2-byte value + 2-byte padding)
        # Pointers are relative offsets from FF4_TEXT_DATA_START
        ptr_table_size = FF4_POINTER_COUNT * FF4_POINTER_SIZE
        if FF4_POINTER_TABLE_OFFSET + ptr_table_size > len(rom.data):
            logger.error("Таблица указателей выходит за пределы данных ROM")
            return segments

        # Create segments for all pointers
        targets = [
            int.from_bytes(
                rom.data[FF4_POINTER_TABLE_OFFSET + i * FF4_POINTER_SIZE:
                         FF4_POINTER_TABLE_OFFSET + i * FF4_POINTER_SIZE + 2],
                'little')
            for i in range(FF4_POINTER_COUNT)
        ]
        code_table_targets = _code_table_targets(targets)
        code_table_addrs = {FF4_TEXT_DATA_START + t for t in code_table_targets}
        for i in range(FF4_POINTER_COUNT):
            ptr_offset = FF4_POINTER_TABLE_OFFSET + i * FF4_POINTER_SIZE
            ptr_val = targets[i]

            # Compute the actual offset in the ROM
            actual_offset = FF4_TEXT_DATA_START + ptr_val

            # Validate the offset
            if actual_offset >= len(rom.data):
                continue

            # Указатель в посимвольную таблицу кодов: запись не переводимая
            # и перезапись сломала бы раскладку символов.
            if ptr_val in code_table_targets:
                continue

            # Find the end of the text (next pointer or end of block)
            if i + 1 < FF4_POINTER_COUNT:  # pragma: no branch
                next_ptr_offset = FF4_POINTER_TABLE_OFFSET + (i + 1) * FF4_POINTER_SIZE
                next_ptr_val = int.from_bytes(rom.data[next_ptr_offset:next_ptr_offset+2], 'little')
                next_offset = FF4_TEXT_DATA_START + next_ptr_val
                if not actual_offset < next_offset <= FF4_TEXT_BLOCK_END:
                    next_offset = FF4_TEXT_BLOCK_END
            else:
                next_offset = FF4_TEXT_BLOCK_END  # pragma: no cover

            # Ensure a valid range
            if next_offset <= actual_offset:  # pragma: no branch
                next_offset = actual_offset + 100  # Fallback  # pragma: no cover

            end = min(next_offset, FF4_TEXT_BLOCK_END)
            # Один указатель может покрывать несколько 0x0C-записей, а декодер
            # останавливается на первом терминаторе: режем на подсегменты
            # по записям, иначе хвостовые записи невидимы экстрактору
            # и ломают счётчик инжектора (ff4_text_887).
            # Cap: мусорный next-указатель даёт гигантский span — такие
            # пропускаем (настоящие диалоговые записи мелкие).
            if end - actual_offset > 0x10000:
                logger.warning("Подозрительно длинный спан 0x%X для указателя %d — пропуск",
                               end - actual_offset, i)
                continue
            bounds = []
            rec_start = actual_offset
            pos = actual_offset
            end = min(end, len(rom.data))
            while pos < end:
                if rom.data[pos] == 0x0C:
                    # Подряд идущие 0x0C: rec_start уже указывает на pos
                    # (он равен pos предыдущего разделителя + 1), и такая
                    # «запись» — один байт 0x0C без текста. Пропускаем её,
                    # иначе в манифесте появятся пустые записи в один байт.
                    if pos > rec_start:
                        bounds.append((rec_start, pos + 1))
                    rec_start = pos + 1
                pos += 1
            # Хвост блока, не закрытый 0x0C, — ОБРЕЗАН следующим указателем,
            # а не запись. Такое окно не переписываемо (нет разделителя, и
            # паддинг затёр бы чужие данные) и не является текстом: в
            # исходнике это хвост настоящей записи, чью целиком найдёт
            # другой указатель. Такие окна отбрасываем.
            #
            # Записи, чьё окно накрывает таблицу указателей, — мусорные
            # указатели внутрь самой таблицы (у FF4 блок текста начинается
            # ДО таблицы, 0x2e3670 < 0x2e3680). Такие окна нельзя
            # переписывать: запись уничтожит сами указатели.
            ptr_table_start = FF4_POINTER_TABLE_OFFSET
            ptr_table_end = FF4_POINTER_TABLE_OFFSET + FF4_POINTER_COUNT * FF4_POINTER_SIZE
            bounds = [(rs, re_) for rs, re_ in bounds
                      if not (rs < ptr_table_end and re_ > ptr_table_start)
                      # Подзапись внутри таблицы кодов: нарезка по 0x0C
                      # порождает сотни двухбайтных «записей» из одного
                      # указателя, и каждая попала бы в манифест.
                      and rs not in code_table_addrs]
            if not bounds:
                continue
            for rec_start, rec_end in bounds:
                decoded = self._decoder.decode(
                    bytes(rom.data[rec_start:rec_end]), 0, rec_end - rec_start)
                candidates.append({
                    # Имя — чистая функция от (индекс указателя, смещение).
                    # Ветки вида «одна запись -> имя без смещения» быть не
                    # должно: она content-based (junk-фильтр решает, сколько
                    # записей выжило), и при переводе, сокращающем запись,
                    # формат имени меняется — сегмент пропадает из манифеста
                    # при обратной сверке.
                    'name': f'ff4_text_{i}_{rec_start:06x}',
                    'start': rec_start,
                    'end': rec_end,
                    'decoder': self._decoder,
                    'compression': None,
                    'charmap': CHARMAP_FF4,
                    'terminators': FF4_TERMINATORS,
                    # Записи FF4 идут вплотную, а 0x00 в charmap — пробел:
                    # паддинг пробелами дописал бы их в текст, поэтому
                    # разделителем и паддингом остаётся 0x0C. Сокращение
                    # записи, в середину которой смотрит чужой указатель,
                    # запрещено флагом has_mid_alias (см. ниже) — иначе
                    # паддинг затёр бы хвост, где начинается та запись.
                    'pad_byte': 0x0C,
                    'pointer_table': FF4_POINTER_TABLE_OFFSET,
                    'pointer_count': FF4_POINTER_COUNT,
                    'pointer_offset': ptr_offset,
                    'original_text': decoded,
                })

        # Сливаем ТОЧНЫЕ дубли окон: два указателя в одну запись.
        candidates = merge_aliased_records(candidates)

        # Указатели часто попадают в середину чужой записи ('English' ->
        # хвост 'lish' с тем же концом). Такое окно нельзя переписывать
        # (затрёт соседнюю запись), но и выбрасывать нельзя: это настоящий
        # текст, просто адресуемый через чужое окно. Поэтому окно, целиком
        # лежащее ВНУТРИ уже занятого, становится read-only алиасом: видно
        # в манифесте, но инжектор его не трогает. Частичное перекрытие —
        # мусорный указатель, отбрасываем.
        #
        # Сортируем по (start, -end): при одинаковом start первым идёт
        # самое длинное окно, то есть настоящая запись до 0x0C. Иначе
        # хостом становится обрезанный фрагмент ('Eng'), а целая запись
        # ('English') уходит в мусор.
        candidates.sort(key=lambda s: (s['start'], -s['end']))
        canonicals: list[dict] = []
        alias_pairs: list[tuple[dict, dict]] = []
        covered_to = -1
        covered_by: dict | None = None
        for seg in candidates:
            if covered_by is None or seg['start'] >= covered_to:
                canonicals.append(seg)
                covered_to = seg['end']
                covered_by = seg
                continue
            if seg['end'] <= covered_to:
                alias = dict(seg)
                alias['injectable'] = False
                alias['alias_of'] = covered_by['name']
                alias['alias_start'] = covered_by['start']
                alias_pairs.append((covered_by, alias))
            # Частичное перекрытие — мусорный указатель, отбрасываем.

        # Junk-фильтр решает ПО КАНОНИЧЕСКОЙ записи, а алиасы наследуют
        # решение хоста. Иначе мусорный хост отбрасывается, а его короткий
        # суффикс-алиас проходит фильтр и остаётся записью без инжектируемого
        # канона: текст в этом окне навсегда непереводим, а alias_of —
        # висячая ссылка. Наследование заодно делает состав алиасов
        # независимым от их собственного текста: после перевода хоста
        # содержимое окна меняется, и самостоятельный фильтр унёс бы алиас
        # из манифеста.
        junk = {c['name'] for c in canonicals
                if _is_junk_record(c.get('original_text') or '')}
        segments = [c for c in canonicals if c['name'] not in junk]
        segments.extend(a for host, a in alias_pairs if host['name'] not in junk)

        # Помечаем хостов, в середину которых смотрит чужой указатель.
        # Такой хост НЕЛЬЗЯ сокращать: его хвост — это отдельная запись для
        # другого указателя, и паддинг разделителем затёр бы её, а игра
        # показала бы в этом месте пустую строку. Инжектор по флагу refuses
        # переводы короче оригинала (см. _mid_alias_refusal в core/injector).
        aliased_hosts = {seg['alias_of'] for seg in segments if seg.get('alias_of')}
        for seg in segments:
            if seg['name'] in aliased_hosts:
                seg['has_mid_alias'] = True

        logger.info(f"Total segments: {len(segments)}")
        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        return FF4_TERMINATORS

    def get_compression_handler(self, segment_name: str):
        return None
