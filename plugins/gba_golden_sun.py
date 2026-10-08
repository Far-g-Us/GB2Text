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
Plugin for Golden Sun (GBA) - contextual Huffman.

Text encoding: contextual Huffman (256 trees, one per
previous character). The format was recovered from the goldensun-decomp
project (tools/pack_strings.c, src/decompress/huffman.s). Verified against
ROM SHA1 5c4695205413df7db52b9a184815a07783999971.

Extraction: decompressed strings are returned via 'raw_text'.
Insertion: translations are recompressed with the game's stock Huffman trees
(bit order as in pack_strings.c) and written into the string file slots.
A translation that does not fit its slot (compressed size larger than the
original) can only be inserted with slot data relocation, which is
not implemented - the injector skips such messages (skip_long).

Game codes: AGSE (Golden Sun 1, USA/EU). TLA uses AGFE (separate plugin).

NOTE: this plugin contains ONLY factual technical information.
Author dialogs and story content are not included.
"""

import logging
import struct

from core.decoder import CharMapDecoder
from core.plugin import GamePlugin
from core.rom import GameBoyROM

_ASCII_CHARMAP: dict[int, str] = {i: chr(i) for i in range(0x20, 0x7F)}

# Границы ASCII-области кредитов внутри окна сканирования.
#
# Признак «это мусор» обязан быть инвариантом к переводу: отбор работает и
# при обратном извлечении уже пропатченного ROM. Поэтому доля букв и длина
# текста как признак не годятся — измерено, что гейт по доле букв терял все
# кредиты ('NINTENDO.' -> 'NIN' даёт долю букв 3/9 = 0.33), а порог длины
# срезал настоящие заголовки staff roll ('Music' 5 байт, 'Writing' 7 байт).
#
# Длина НЕ инвариантна: при pad_byte=0x00 укороченная запись становится
# короче порога плотности. Поэтому длина применяется только к пробе, которая
# ищет начало области, и не применяется к отбору записей.
#
# Проба плотности: первое окно, где набирается `_CREDITS_DENSITY_MIN`
# NUL-терминированных прогонов длиной не менее `_CREDITS_MIN_RUN`. Машинный
# код таких строк не содержит, кредиты содержат плотной полосой.
_CREDITS_MIN_RUN = 5
_CREDITS_PROBE = 64
_CREDITS_DENSITY_MIN = 3
# Конец области — перед большим разрывом без строк. Кредиты идут подряд,
# разрывы между ними 1-2 байта. Порог 0x100 терпит рост разрывов при
# сокращении: удаление увеличивает дыры между записями.
_CREDITS_GAP = 0x100
# Минимум длины в обходе записей: 1, потому что сокращённая запись
# становится короткой и при бóльшем пороге выпадает из манифеста.
_CREDITS_WALK_MIN_RUN = 1
# Заполнитель дыры после укороченной записи: 0x00, чтобы хвост не был виден.
_CREDITS_PAD_BYTE = 0x00
# Окно кредитов GS. У TLA своё окно и свой префикс.
_CREDITS_WIN = (0x0F0000, 0x0F2000)
_CREDITS_PREFIX = 'gs_credits'
# Окно кредитов в этой ревизии ROM.
# Начало области задаётся константой ревизии, а не ищется сканером:
# при сокращении перевода печатные байты исчезают, и скан уплывает вперёд.
_CREDITS_FIXED_PROBE = 0x400
_CREDITS_FIXED_NEED = 12
# Минимальная длина прогона в проверке якоря. Отдельно от `_CREDITS_MIN_RUN`:
# тот про пробу плотности, а здесь про проверку якоря.
_CREDITS_FIXED_MIN_RUN = 4
_CREDITS_AT = 0x0F0AE4

logger = logging.getLogger('gb2text.plugins.golden_sun')

GAME_CODES = ['AGSE']

# ---- ROM layout constants (Golden Sun 1, USA/EU, SHA1 5c4695...) ----
GS_TREES_BASE = 0x37464
GS_OFFSETS_BASE = 0x38334
GS_STRINGS_PTR_BASE = 0x736B8
GS_DATA_FILES = 42
GS_STRINGS_PER_FILE = 256
GS_NO_TREE = 0x8000

# A decoded 0x00 byte terminates a string (the decoder stops on it).
# Control tokens must not contain '[', '\n' or the patterns '[XX]'/'[END]',
# so core.extractor._split_messages keeps every line as a single message.
GS_CONTROL_TOKENS: dict[int, str] = {
    0x01: '{NL}',        # newline inside the box
    0x02: '{END}',       # end of the message box
    0x03: '{CONT}',      # continue text on a new line
    0x07: '{CLR}',       # reset text color
    0x12: '{NAME}',      # character name placeholder
    0x13: '{CLASS}',     # class/level placeholder
    0x15: '{ABILITY}',   # psynergy/ability name placeholder
    0x16: '{NUM}',       # numeric placeholder (HP/PP/level/coins)
    0x1E: '{WAIT}',      # prompt "..."
}
GS_TOKEN_REVERSE = {v: k for k, v in GS_CONTROL_TOKENS.items()}


def _credits_region_impl(data: bytes, start: int,
                         end: int) -> tuple[int, int]:
    """Границы ASCII-области кредитов: (начало, конец).

    Начало — первое окно, где NUL-терминированных строк достаточно много:
    машинный код не содержит подряд идущих NUL-строк, кредиты содержат.
    Для Golden Sun даёт ровно 0x0F0AE4 — первую настоящую строку
    'NINTENDO.'.

    Конец — адрес завершения последней строки перед ПРОДОЛЖИТЕЛЬНЫМ
    РАЗРЫВОМ: кредиты идут подряд (разрывы 1-2 байта), а после них перед
    мусором образуется разрыв в 0x94 байта. Проба с порогом плотности на
    окне 64 байта для конца не годится — она срабатывала ВНУТРИ кредитов
    и схлопывала область в ноль.

    ГРАНИЦА ОБЛАСТИ ЗАВИСИТ ОТ ДЛИН ЗАПИСЕЙ, а не только от структуры.
    Начало — первая точка, где в окне `_CREDITS_PROBE` байт набирается
    `_CREDITS_DENSITY_MIN` NUL-терминированных прогонов длиной не менее
    `_CREDITS_MIN_RUN`. Укороченная запись короче порога, поэтому на патче
    точка смещается вперёд: у GS на 11 байт, у TLA на 82. Именно поэтому
    начало и задаётся константой ревизии (`_CREDITS_AT`,
    `TLA_CREDITS_AT`), а скан остаётся запасным путём для других ревизий.

    Отвергнутые инвариантные альтернативы и их замеры — см. KNOWN_ISSUES
    и `scripts_roms/gs_credits_boundary_probe.py`.
    """
    if _CREDITS_PROBE <= 0 or _CREDITS_DENSITY_MIN <= 0:
        return start, end

    def nul_runs(lo: int, hi: int,
                 min_run: int = _CREDITS_MIN_RUN) -> list[tuple[int, int]]:
        found: list[tuple[int, int]] = []
        i = lo
        while i < hi:
            if 0x20 <= data[i] <= 0x7E:
                s = i
                while i < hi and 0x20 <= data[i] <= 0x7E:
                    i += 1
                if (i - s >= min_run and i < len(data)
                        and data[i] == 0x00):
                    found.append((s, i))
            else:
                i += 1
        return found

    region_start = end
    for base in range(start, max(start, end - _CREDITS_PROBE + 1)):
        if len(nul_runs(base, min(base + _CREDITS_PROBE, end))) \
                >= _CREDITS_DENSITY_MIN:
            region_start = base
            break
    if region_start >= end:
        return region_start, end

    # Обход записей идёт по собственному минимуму длины
    # (`_CREDITS_WALK_MIN_RUN` = 1), а проба плотности, определяющая
    # начало области, остаётся на `_CREDITS_MIN_RUN`. Это разные признаки:
    # укороченная запись выпадает из отбора, но не должна ломать границу.
    runs = nul_runs(region_start, end, _CREDITS_WALK_MIN_RUN)
    if not runs:
        return region_start, region_start
    region_end = runs[0][1]
    for run_start, run_end in runs[1:]:
        if run_start - region_end >= _CREDITS_GAP:
            break
        region_end = run_end
    return region_start, region_end


def credits_region(data: bytes, start: int, end: int,
                   fixed_at: int | None = None) -> tuple[int, int]:
    """Границы плотной ASCII-области кредитов в окне адресов.

    Чистая функция без `self`: оба плагина Golden Sun и The Lost Age
    держат один и тот же формат.

    `fixed_at` — константа ревизии: начало области кредитов. Она нужна
    потому, что при сокращении перевода сканер плотности смещается вперёд
    (на 11 байт у GS, на 82 у TLA) и первые кредиты выпадают из манифеста.
    Константа от перевода не зависит, как и остальные константы адресов
    в этом плагине. Если проверка `_looks_like_credits` не подтверждает
    адрес, остаётся сканер.
    """
    if fixed_at is not None and start <= fixed_at < end \
            and _looks_like_credits(data, fixed_at, end):
        return fixed_at, _credits_region_impl(data, start, end)[1]
    return _credits_region_impl(data, start, end)


def _looks_like_credits(data: bytes, at: int, end: int) -> bool:
    """Проверка фиксированного начала области.

    Инвариантна к сокращению: перевод не убирает сами строки, поэтому
    количество NUL-терминированных прогонов сохраняется.
    """
    # Якорь обязан стоять НА ПЕЧАТНОМ байте: иначе он указывает внутрь
    # строки, и обход молча разрежет её. Замер без этой проверки: гард
    # принимал 70.9 % позиций окна и давал 219 сегментов вместо 109,
    # из них 144 байта для записи лежали внутри машинного кода.
    if at >= len(data) or not 0x20 <= data[at] <= 0x7E:
        return False
    found = 0
    i = at
    limit = min(end, at + _CREDITS_FIXED_PROBE)
    while i < limit and found < _CREDITS_FIXED_NEED:
        if 0x20 <= data[i] <= 0x7E:
            run = i
            while i < limit and 0x20 <= data[i] <= 0x7E:
                i += 1
            if (i - run) >= _CREDITS_FIXED_MIN_RUN \
                    and i < len(data) and data[i] == 0x00:
                found += 1
        else:
            i += 1
    return bool(found >= _CREDITS_FIXED_NEED)


def ascii_credits_segments(data, win_lo, win_hi, prefix,
                          log=logger,
                          fixed_at=None) -> list[dict]:
    """Сегменты ASCII-кредитов из окна ['win_lo', 'win_hi') с именем `'prefix'.

    Общий код: плагин GS делает своё, TLA вызывает тот же
    код для своих окна, но своим именем.
    """
    segments: list[dict] = []
    start = win_lo
    end = min(win_hi, len(data))
    if start >= len(data):
        return segments

    region_start, region_end = credits_region(data, start, end,
                                                 fixed_at)
    if region_start >= region_end:
        log.warning(
            f'Плотная ASCII-область кредитов не найдена в окне '
            f'0x{start:X}..0x{end:X}: кредиты этой ревизии не извлекаются')
        return segments

    i = region_start
    while i < region_end:
        if 0x20 <= data[i] <= 0x7E:
            str_start = i
            while i < region_end and 0x20 <= data[i] <= 0x7E:
                i += 1
            length = i - str_start
            nul_terminated = (str_start + length < len(data)
                              and data[str_start + length] == 0x00)
            if length >= _CREDITS_WALK_MIN_RUN and nul_terminated:
                text = bytes(data[str_start:str_start + length]).decode(
                    'ascii', errors='replace')
                segments.append({
                    'name': f'{prefix}_{str_start:06x}',
                    'start': str_start,
                    'end': str_start + length,
                    'decoder': CharMapDecoder(dict(_ASCII_CHARMAP)),
                    'compression': None,
                    'charmap': dict(_ASCII_CHARMAP),
                    'terminators': [0x00],
                    'pad_byte': _CREDITS_PAD_BYTE,
                    'raw_text': text,
                })
        else:
            i += 1
    return segments


class _BitReader:
    """LSB-first bit reader over a byte-array slice."""

    __slots__ = ('bitpos', 'bytepos', 'data')

    def __init__(self, data: bytes, start: int = 0):
        self.data = data
        self.bytepos = start
        self.bitpos = 0

    def read_bit(self) -> int:
        byte = self.data[self.bytepos]  # pragma: no cover
        bit = (byte >> self.bitpos) & 1  # pragma: no cover
        self.bitpos += 1  # pragma: no cover
        if self.bitpos == 8:  # pragma: no cover
            self.bitpos = 0
            self.bytepos += 1
        return bit


class _BitWriter:
    """LSB-first bit writer, mirrors bit_writer from pack_strings.c."""

    __slots__ = ('bits', 'bits_pending', 'out')

    def __init__(self):
        self.bits = 0
        self.bits_pending = 0
        self.out = bytearray()

    def append(self, bit: int) -> None:
        self.bits |= (bit << self.bits_pending)
        self.bits_pending += 1
        if self.bits_pending == 8:
            self.out.append(self.bits)
            self.bits = 0
            self.bits_pending = 0

    def flush(self) -> None:
        if self.bits_pending:
            self.out.append(self.bits)
            self.bits = 0
            self.bits_pending = 0


class GoldenSunHuffmanDecoder:
    """
    Contextual Huffman decoder for Golden Sun's compressed strings.

    Trees: 256 (indexed by the previous decoded byte).
    Tree i starts at trees_base + offsets[i]; offsets[i] == 0x8000
    means tree i is unused. Each tree consists of a leaf array
    (packed symbols, growing backwards from the start of the topology),
    followed by a pre-order topology bit stream (0=internal node,
    1=leaf, LSB-first).

    Base addresses are configurable so both Golden Sun 1 (AGSE) and
    The Lost Age (AGFE) share this decoder; defaults are GS1.
    """

    def __init__(self, rom_data: bytes | bytearray,
                 offsets_base: int = GS_OFFSETS_BASE,
                 trees_base: int = GS_TREES_BASE):
        self.data = bytes(rom_data)
        self.trees_base = trees_base
        if offsets_base + 512 > len(rom_data):
            raise ValueError('ROM too small for Golden Sun Huffman tables')
        self.offsets = list(struct.unpack_from('<256H', rom_data, offsets_base))
        # Разобранная топология: prev-байт -> список узлов pre-order.
        # Строится один раз на дерево вместо раскладки на КАЖДЫЙ символ.
        self._tree_cache: dict[int, list[int]] = {}

    def _read_leaf(self, topo_start: int, leaf_id: int) -> int:
        """Read a symbol from a tree's packed leaf array."""
        off = leaf_id + (leaf_id >> 1)
        if leaf_id & 1:
            return self.data[topo_start - off - 2]
        return ((self.data[topo_start - off - 1] & 0x0F) << 4) | \
            ((self.data[topo_start - off - 2] >> 4) & 0x0F)

    def _parse_tree(self, topo_start: int) -> list[int]:
        """Топология дерева в pre-order: узлы и число листьев слева.

        Узел — целое: неотрицательное значение означает лист с таким
        `leaf_id`, отрицательное — `-(leaves_in_left_subtree)`. Разбор идёт
        один раз на дерево: прежде он повторялся на каждый символ, и полная
        распаковка Golden Sun стоила ~24 млн вызовов рекурсивного `walk`.

        Обход ИТЕРАТИВНЫЙ, и это не оптимизация: в стоковом Golden Sun из
        239 деревьев 6 имеют высоту больше 900 (максимум 29 665), то есть
        рекурсивный разбор упал бы с RecursionError на совершенно нормальной
        игре. Старый обход рекурсией не пользовался — `walk()` вызывался
        только при переходе вправо, — поэтому деградации на вырожденном
        дереве раньше не было, и её не должно быть теперь.
        """
        nodes: list[int] = []
        data = self.data
        state = [topo_start, 0]  # [bytepos, bitpos]

        def read_bit() -> int:
            bit = (data[state[0]] >> state[1]) & 1
            state[1] += 1
            if state[1] == 8:
                state[1] = 0
                state[0] += 1
            return bit

        # Кадр незакрытого внутреннего узла:
        # [индекс в nodes, leaf_id поддерева, листья слева (None = не считали),
        #  листья справа].
        stack: list[list] = []
        leaf_id = 0
        while True:
            if read_bit() == 1:  # лист
                nodes.append(leaf_id)
                leaf_id += 1
                n_leaves = 1
            else:  # внутренний узел: спускаемся в левое поддерево
                nodes.append(0)
                stack.append([len(nodes) - 1, leaf_id, None, 0])
                continue
            # Узел закрыт (n_leaves листьев): поднимаемся по стеку.
            while stack:
                frame = stack[-1]
                if frame[2] is None:  # левое поддерево только что закрыто
                    frame[2] = n_leaves
                    leaf_id = frame[1] + n_leaves  # правый ребёнок отсюда
                    break
                frame[3] = n_leaves
                left = frame[2]
                nodes[frame[0]] = -left
                stack.pop()
                n_leaves = left + frame[3]
            else:
                break  # стек пуст: дерево разобрано целиком
        return nodes

    def _tree(self, prev: int) -> list[int]:
        """Разобранное дерево для prev-байта (с кэшем)."""
        cached = self._tree_cache.get(prev)
        if cached is None:
            cached = self._parse_tree(self.trees_base + self.offsets[prev])
            self._tree_cache[prev] = cached
        return cached

    def _decode_symbol(self, bitstream: _BitReader, prev: int) -> int:
        """Decode one symbol from the bit stream using the 'prev' tree."""
        tree_rel = self.offsets[prev]
        if tree_rel == GS_NO_TREE or tree_rel == 0:
            raise ValueError(f'no valid Huffman tree for prev=0x{prev:02X}')
        topo_start = self.trees_base + tree_rel
        if topo_start - 2 < 0 or topo_start >= len(self.data):
            raise ValueError(f'tree topology out of bounds: 0x{topo_start:X}')

        nodes = self._tree(prev)
        data = bitstream.data
        bytepos = bitstream.bytepos
        bitpos = bitstream.bitpos
        idx = 0
        while True:
            node = nodes[idx]
            if node >= 0:  # достигнут лист: node и есть его leaf_id
                bitstream.bytepos = bytepos
                bitstream.bitpos = bitpos
                return self._read_leaf(topo_start, node)
            # Внутренний узел: бит данных выбирает ребёнка. В pre-order
            # левый ребёнок идёт сразу за узлом, а правый — за левым
            # поддеревом, в котором 2*leaves-1 узлов.
            bit = (data[bytepos] >> bitpos) & 1
            bitpos += 1
            if bitpos == 8:
                bitpos = 0
                bytepos += 1
            idx += 1 if not bit else -2 * node

    def decode_string(self, compressed: bytes) -> bytes:
        """Decode a single compressed string (stops at 0x00)."""
        if not compressed:
            return b''
        dr = _BitReader(compressed)
        out = bytearray()
        prev = 0
        while True:
            try:
                sym = self._decode_symbol(dr, prev)
            except (EOFError, IndexError, ValueError):
                break
            if sym == 0:
                break
            out.append(sym)
            prev = sym
        return bytes(out)


class GoldenSunHuffmanEncoder:
    """
    Recompresses Golden Sun dialogs with the game's stock Huffman trees.

    For each tree (one per previous byte) builds a code map
    symbol -> bit path by walking the serialized topology exactly like the
    game does, then emits the bit stream with the same LSB-first writer as
    tools/pack_strings.c. The 0x00 terminator is encoded as part of the
    string, so decoding stops at the same logical point as in the original.

    Base addresses are configurable so both Golden Sun 1 (AGSE) and
    The Lost Age (AGFE) share this encoder; defaults are GS1.
    """

    def __init__(self, rom_data: bytes | bytearray,
                 offsets_base: int = GS_OFFSETS_BASE,
                 trees_base: int = GS_TREES_BASE):
        self.data = bytes(rom_data)
        self.trees_base = trees_base
        if offsets_base + 512 > len(rom_data):
            raise ValueError('ROM too small for Golden Sun Huffman tables')
        self.offsets = list(struct.unpack_from('<256H', rom_data, offsets_base))
        self._codes_cache: dict[int, dict[int, tuple[int, ...]]] = {}

    def _read_leaf(self, topo_start: int, leaf_id: int) -> int:
        off = leaf_id + (leaf_id >> 1)
        if leaf_id & 1:
            return self.data[topo_start - off - 2]
        return ((self.data[topo_start - off - 1] & 0x0F) << 4) | \
            ((self.data[topo_start - off - 2] >> 4) & 0x0F)

    def _build_codes(self, prev: int) -> dict[int, tuple[int, ...]]:
        tree_rel = self.offsets[prev]
        if tree_rel == GS_NO_TREE or tree_rel == 0:
            raise ValueError(f'no valid Huffman tree for prev=0x{prev:02X}')
        topo_start = self.trees_base + tree_rel
        tp = _BitReader(self.data, topo_start)
        codes: dict[int, tuple[int, ...]] = {}
        leaf_id = 0

        def walk(bits: tuple[int, ...]) -> None:
            nonlocal leaf_id
            if tp.read_bit() == 1:
                codes[self._read_leaf(topo_start, leaf_id)] = bits
                leaf_id += 1
            else:
                walk((*bits, 0))
                walk((*bits, 1))

        walk(())
        return codes

    def _codes_for(self, prev: int) -> dict[int, tuple[int, ...]]:
        codes = self._codes_cache.get(prev)
        if codes is None:
            codes = self._build_codes(prev)
            self._codes_cache[prev] = codes
        return codes

    def compress_string(self, raw: bytes) -> bytes:
        """Compress one string: encode each byte plus the 0x00 terminator."""
        writer = _BitWriter()
        prev = 0
        for byte in raw + b'\x00':
            path = self._codes_for(prev).get(byte)
            if path is None:
                raise ValueError(
                    f'char 0x{byte:02X} not encodable after 0x{prev:02X}'
                )
            for bit in path:
                writer.append(bit)
            prev = byte
        writer.flush()
        return bytes(writer.out)


class GoldenSunTextDecoder:
    """Maps decoded GS bytes to readable tokens (ASCII + codes)."""

    def __init__(self):
        self.charmap = {i: chr(i) for i in range(0x20, 0x7F)}
        self.charmap.update(GS_CONTROL_TOKENS)

    def decode(self, data: bytes) -> str:
        result: list[str] = []
        for byte in data:
            if 0x20 <= byte <= 0x7E:
                result.append(chr(byte))
            else:
                result.append(GS_CONTROL_TOKENS.get(byte, f'{{{byte:02X}}}'))
        return ''.join(result)

    def encode(self, text: str) -> bytes:
        """Reverse-maps tokens and ASCII back into bytes."""
        out = bytearray()
        tokens = sorted(GS_TOKEN_REVERSE, key=len, reverse=True)
        i = 0
        while i < len(text):
            tok = next((t for t in tokens if text.startswith(t, i)), None)
            if tok is not None:
                out.append(GS_TOKEN_REVERSE[tok])
                i += len(tok)
                continue
            if text[i] == '{':
                close = text.find('}', i)
                if close == -1:
                    out.append(0x00)
                    i += 1
                    continue
                token = text[i:close + 1]
                byte = GS_TOKEN_REVERSE.get(token)
                if byte is None:
                    try:
                        byte = int(token[1:-1], 16)
                    except ValueError:
                        byte = 0x00
                out.append(byte)
                i = close + 1
                continue
            code = ord(text[i])
            out.append(code if 0x20 <= code <= 0x7E else 0x00)
            i += 1
        return bytes(out)


class GoldenSunPlugin(GamePlugin):
    """Plugin for Golden Sun (GBA) - contextual Huffman dialogs."""

    def __init__(self):
        super().__init__()
        self._decoder = GoldenSunTextDecoder()
        # Разобранные строки на исходный ROM: инжектор зовёт
        # get_text_segments на каждый пакет, а распаковка всех 10722 строк
        # стоит ~2.5 с. Кэш держит САМ объект `rom.data`, поэтому
        # переиспользовать его `id()` невозможно; `rom.data` инфраструктурой
        # не мутируется — правки идут в modified_data инжектора.
        self._strings_cache: tuple | None = None

    def _decoded_strings(self, rom: GameBoyROM) -> list[tuple[int, int, int, str]]:
        """`(start, length, sid, text)` по всем строкам ROM, с кэшем."""
        data = rom.data
        cache = self._strings_cache
        if cache is not None and cache[0] is data:
            # Копия: внутренний кортеж не должен утекать к вызывающему.
            return list(cache[1])
        out: list[tuple[int, int, int, str]] = []
        try:
            huffman = GoldenSunHuffmanDecoder(data)
        except ValueError as e:
            logger.warning(f"Golden Sun Huffman tables unavailable: {e}")
            self._strings_cache = (data, ())
            return []
        decoder = self._decoder
        for fid in range(GS_DATA_FILES):
            strings_addr, lens_addr = struct.unpack_from(
                '<II', data, GS_STRINGS_PTR_BASE + fid * 8
            )
            if not (0x08000000 <= strings_addr <= 0x08800000
                    and 0x08000000 <= lens_addr <= 0x08800000):
                logger.warning(f"Bad string table pointers in file {fid}")
                continue
            strings_addr -= 0x08000000
            lens_addr -= 0x08000000
            data_len = lens_addr - strings_addr
            pos = 0
            for sid in range(GS_STRINGS_PER_FILE):
                if pos >= data_len:
                    break
                length = data[lens_addr + sid]
                if length == 0 or pos + length > data_len:
                    break
                compressed = bytes(data[strings_addr + pos:strings_addr + pos + length])
                decoded = huffman.decode_string(compressed)
                out.append((strings_addr + pos, length, fid * GS_STRINGS_PER_FILE + sid,
                            decoder.decode(decoded)))
                pos += length
        self._strings_cache = (data, tuple(out))
        return list(out)

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(GAME_CODES)
        return f'^GBA_({codes})$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Extract text segments from a Golden Sun ROM."""
        logger.info("Extracting text segments for Golden Sun")
        if GS_STRINGS_PTR_BASE + GS_DATA_FILES * 8 > len(rom.data):
            logger.warning("ROM too small for Golden Sun string table")
            return []

        try:
            compressor = GoldenSunHuffmanEncoder(rom.data)
        except ValueError as e:
            logger.warning(f"Golden Sun Huffman tables unavailable: {e}")
            return []

        segments: list[dict] = []
        for start, length, sid, text in self._decoded_strings(rom):
            segments.append({
                'name': f'gs_dialogue_f{sid // GS_STRINGS_PER_FILE:02d}_'
                        f'{sid % GS_STRINGS_PER_FILE:03d}',
                'start': start,
                'end': start + length,
                'decoder': self._decoder,
                'compression': 'huffman',
                'compressed_length': length,
                'pad_byte': 0xFF,
                'charmap': self._decoder.charmap,
                'terminators': [0x00],
                'raw_text': text,
                'encoder': self._make_compressor(compressor),
            })

        segments.extend(self._ascii_credits_segments(rom))
        logger.info(f"Total segments: {len(segments)}")
        return segments

    def _credits_region(self, data: bytes, start: int,
                      end: int) -> tuple[int, int]:
        """Область плотной ASCII-области кредитов в окне адресов.

        См. `credits_region` — реализованная функция общая для обоих плагинов.
        """
        return _credits_region_impl(data, start, end)

    def _ascii_credits_segments(self, rom: GameBoyROM) -> list[dict]:
        """Извлекает кредиты staff roll (чисто-ASCII область) сегментами.

        Окно 0x0F0000..0x0F2000 содержит и кредиты, и МАШИННЫЙ КОД: в
        Golden Sun код идёт примерно до 0x0F0AE0. Наивный скан «любой прогон
        печатаемых байт >= 5» выдавал 141 сегмент, и инжектор затирал 5-8 байт
        живых инструкций там, где сегмент лежал поверх кода
        (`0x0F026D: 4d 6c 46 23 60 20 1c 0b 4b 0c 4a 07 c3` = `ldr r3,[pc]` /
        `mov r3,r1` / `ldr r2,[pc]`). Измерено: из 141 прогона 107 —
        настоящие кредиты, 14 начинаются в области кода (ниже 0x0F0AE0), 20
        идут после кредитов; итого 34 сегмента поверх не-текста.

        Отбор сведён к границам ASCII-области и двум инвариантным признакам
        (длина прогона >= 5, терминатор 0x00) — см. константы модуля и
        обоснование в них.

        Имя сегмента содержит АДРЕС, а не порядковый номер: `len(segments)`
        сдвигается при любом изменении отбора, а имя сегмента — ключ в TMX,
        манифестах и кэше, поэтому старый перевод ушёл бы молча в другую
        строку.
        """
        return ascii_credits_segments(
            rom.data, _CREDITS_WIN[0], _CREDITS_WIN[1],
            _CREDITS_PREFIX, log=logger, fixed_at=_CREDITS_AT)

    def get_terminators(self, segment_name: str) -> list[int]:
        return [0x00]

    def get_compression_handler(self, segment_name: str):
        return None

    def _make_compressor(self, compressor: GoldenSunHuffmanEncoder):
        """Returns a callable: text -> compressed stream (Huffman, via the token table)."""
        def compress_text(text: str) -> bytes:
            raw = self._decoder.encode(text)
            return compressor.compress_string(raw)
        return compress_text
