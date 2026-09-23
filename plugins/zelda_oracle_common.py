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
Общий декодер текста The Legend of Zelda: Oracle of Seasons (GBC, US).

Формат подтверждён на реальном ROM (см. scripts_roms/check_oos_text.py и
референсный dumpText.py из проекта Stewmath/oracles-disasm — только факты,
тексты игр не воспроизводятся):

  - ~2822 текстовых записей в непрерывном пуле (0x73382-0x84DDF US).
    Адреса записей задаются 0x64-entry таблицей "high index"; группы
    0-3 — словарные (DICT), группы 4-0x63 — собственно тексты (TX_).
  - Каждая запись — последовательность байт, терминированная 0x00.
  - Мини-словарь: байты 0x02-0x05 — двухбайтовая ссылка на запись словаря
    (index = ((b-2)<<8) | next), раскрывается рекурсивно.
  - Контрольные коды 0x06-0x0F потребляют один байт-параметр.
  - 0x01 — перенос строки; 0x10-0x19 — глифы; 0x7E/0x7F — фигуры;
    0xB8/0xBA — двухбайтовые кнопки A/B; 0x80-0x90 и 0xA0-0xB0 —
    акцентированные латинские буквы (литералы, безопасны при вставке).
  - Безопасные для raw-вставки байты: литералы 0x20-0x7E (0x5C → '~'),
    акцентированные 0x80-0x90/0xA0-0xB0 и контрольные коды ТОЛЬКО в виде
    корректной пары опкод+параметр (encode никогда не эмитит голые
    управляющие байты).

Токены (bracket-стиль, как в прочих плагинах фреймворка — не ломают
_split_messages и валидируются локализационным линтером):
  [NL] [LINK] [CHILD] [SECRET1] [SECRET2] [STOP] [OPT] [NUM1] [NUM2]
  [HEARTPIECE] [SLOW] [CIRCLE] [CLUB] [DIAMOND] [SPADE] [HEART] [UP]
  [DOWN] [LEFT] [RIGHT] [TIMES] [TRIANGLE] [RECTANGLE] [ABTN] [BBTN]
  [COL(N)] [COL(0xXX)] [SPEED(N)] [POS(N)] [WAIT(N)] [ITEM(0xXX)]
  [SYM(0xXX)] [CHARSFX(0xXX)] [SFX(0xXX)] [CMD(0xXX)]
  [JUMP(TX_XXXX|DICT?_XX|0xXX)] [CALL(...)] [X_XX]
Акцентированные буквы выводятся как есть (Unicode), канзи-символы
(0x06 c параметром < 0x80) — как сами иероглифы.

NOTE: This module contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import re

_NUM_HIGH_INDICES = 0x64
_LAST_GROUP_SIZE = 0x1D
_TEXT_BASE2_INDEX_START = 0x2C
_TEXT_BASE3_INDEX_START = 0x100
_TEXT_BASE1_TABLE = 0xFCFE2
_TEXT_BASE2_TABLE = 0xFCFFA
_LANGUAGE_TABLE = 0xFD012

_MAX_DICT_DEPTH = 32
_MAX_DECOMPRESS_OUT = 0x10000

_SPEC_CHAR_TABLE = (
    'ÀÂÄÆÇÈÉÊËÎÏÑÖŒÙÛ'
    'Ü???????????????'
    'àâäæçèéêëîïñöœùû'
    'ü???????????????'
    '????????????????'
    '????????????????'
)

_KANJI_TABLE = (
    '姫村下木東西南北地図出入口水氷池'
    '見門手力知恵勇気火金銀？？実上四'
    '季春夏秋冬右左大小本王国男女少年'
    '山人世中々剣花闇将軍真支配者鉄目'
    '詩死心節甲邪悪魔聖川結界生時炎？'
    '天空暗黒塔海仙？'
)

_SYMBOL_TOKENS: dict[int, str] = {
    0x10: '[CIRCLE]',
    0x11: '[CLUB]',
    0x12: '[DIAMOND]',
    0x13: '[SPADE]',
    0x14: '[HEART]',
    0x15: '[UP]',
    0x16: '[DOWN]',
    0x17: '[LEFT]',
    0x18: '[RIGHT]',
    0x19: '[TIMES]',
}

_NOARG_TOKENS: dict[str, bytes] = {
    '[NL]': b'\x01',
    '[LINK]': b'\x0A\x00',
    '[CHILD]': b'\x0A\x01',
    '[SECRET1]': b'\x0A\x02',
    '[SECRET2]': b'\x0A\x03',
    '[STOP]': b'\x0C\x18',
    '[OPT]': b'\x0C\x10',
    '[NUM1]': b'\x0C\x08',
    '[NUM2]': b'\x0C\x30',
    '[HEARTPIECE]': b'\x0C\x28',
    '[SLOW]': b'\x0C\x38',
    '[TRIANGLE]': b'\x7E',
    '[RECTANGLE]': b'\x7F',
    '[ABTN]': b'\xB8\xB9',
    '[BBTN]': b'\xBA\xBB',
}
_NOARG_TOKENS.update({token: bytes([byte]) for byte, token in _SYMBOL_TOKENS.items()})

_SPEC_REV: dict[str, int] = {
    ch: 0x80 + i for i, ch in enumerate(_SPEC_CHAR_TABLE) if ch and ch != '?'
}

_KANJI_REV: dict[str, int] = {
    ch: i for i, ch in enumerate(_KANJI_TABLE) if i < 0x60 and ch and ch != '？'
}

_TOKEN_RE = re.compile(
    r'\['
    r'(?P<fix>NL|LINK|CHILD|SECRET1|SECRET2|STOP|OPT|NUM1|NUM2|HEARTPIECE|'
    r'SLOW|CIRCLE|CLUB|DIAMOND|SPADE|HEART|UP|DOWN|LEFT|RIGHT|TIMES|'
    r'TRIANGLE|RECTANGLE|ABTN|BBTN)\]'
    r'|\[(?P<param>COL|SPEED|POS|WAIT|ITEM|SYM|CHARSFX|SFX|CMD)'
    r'\((?P<arg>\d+|0x[0-9A-Fa-f]{2})\)\]'
    r'|\[(?P<label>JUMP|CALL)'
    r'\((?P<target>TX_[0-9A-Fa-f]{4}|DICT[0-3]_[0-9A-Fa-f]{2}'
    r'|0x[0-9A-Fa-f]{2})\)\]'
    r'|\[X_(?P<rawhex>[0-9A-Fa-f]{2})\]'
)


def _read16(buf, i):
    return buf[i] | (buf[i + 1] << 8)


def _banked_address(bank, pos):
    return bank * 0x4000 + (pos & 0x3FFF)


class OracleTextDecoder:
    """Decoder/encoder для текстового пула Oracle of Seasons (US).

    decode(data, start, length): читает запись, раскрывает словарные ссылки
    рекурсивно и отдаёт строку с bracket-токенами и Unicode-литералами.
    encode(text): обратный маппинг (без словарной рекомпрессии — запись
    может стать длиннее оригинала; инжектор решает через skip_long).
    """

    def __init__(self):
        self._initialized = False
        self._data_id = None
        self._text_base1 = 0
        self._text_base2 = 0
        self._text_table = 0
        self._text_start = 0
        self._text_end = 0
        self._idx_to_addr: dict[int, int] = {}
        self._addr_to_index: dict[int, int] = {}
        self.last_unmapped_chars: list[str] = []
        self._dict_phrase_cache: list[tuple[bytes, int]] | None = None
        self._last_data: bytes | None = None

    def _init(self, data: bytes) -> None:
        if self._initialized and self._data_id == id(data):
            return
        for table, attr in ((_TEXT_BASE1_TABLE, '_text_base1'),
                            (_TEXT_BASE2_TABLE, '_text_base2')):
            setattr(self, attr, _banked_address(
                data[table], _read16(data, table + 1)))
        self._text_table = _banked_address(
            data[_LANGUAGE_TABLE + 2], _read16(data, _LANGUAGE_TABLE))

        high_index_list: list[dict] = []
        for i in range(_NUM_HIGH_INDICES):
            address = self._text_table + _read16(
                data, self._text_table + i * 2)
            found = next((d for d in high_index_list if d['address'] == address),
                         None)
            if found is None:
                found = {'address': address, 'indices': [i]}
                high_index_list.append(found)
            else:
                found['indices'].append(i)
        high_index_list.sort(key=lambda d: d['address'])
        for i in range(len(high_index_list) - 1):
            high_index_list[i]['size'] = (
                high_index_list[i + 1]['address']
                - high_index_list[i]['address']) // 2
        high_index_list[-1]['size'] = _LAST_GROUP_SIZE

        idx_to_addr: dict[int, int] = {}
        addr_to_index: dict[int, int] = {}
        text_addrs: list[int] = []
        for struct in high_index_list:
            group = struct['indices'][0]
            if group < _TEXT_BASE2_INDEX_START:
                base = self._text_base1
            elif group < _TEXT_BASE3_INDEX_START:
                base = self._text_base2
            else:  # pragma: no cover - недостижимо: group это индекс таблицы 0..99 < 0x100
                base = 0
            for j in range(struct['size']):
                addr = struct['address'] + j * 2
                if addr + 2 > len(data):
                    continue
                text_addr = _read16(data, addr) + base
                index = (group << 8) | j
                idx_to_addr[index] = text_addr
                if text_addr not in addr_to_index:
                    addr_to_index[text_addr] = index
                text_addrs.append(text_addr)

        self._idx_to_addr = idx_to_addr
        self._addr_to_index = addr_to_index
        if text_addrs:
            self._text_start = min(text_addrs)
            self._text_end = max(text_addrs) + 1
        else:
            self._text_start = 0
            self._text_end = 0
        self._initialized = True
        self._data_id = id(data)
        self._last_data = data

    def decode(self, data: bytes, start: int, length: int) -> str:
        """Декодирует запись по адресу start (0x00-терминальная)."""
        self._init(data)
        if not (0 <= start < len(data)):
            raise ValueError(f"Oracle record address out of range: 0x{start:X}")
        out = bytearray()
        self._decompress(data, start, length, out, 0, {start})
        index = self._addr_to_index.get(start)
        return self._stringify(out, index)

    def build_manifest(self, data: bytes) -> list[dict]:
        """Сканирует текстовый пул и возвращает манифест записей.

        Каждая запись: {'target': адрес, 'free_after': длина включая 0x00,
        'raw': исходные байты записи (без завершающего 0x00),
        'original': декодированный текст}. 'raw'/'original' позволяют
        инжектору писать verbatim-копию при round-trip (перевод == оригинал),
        а для новых переводов — словарную рекомпрессию через 'encoder'.
        Словарные записи (idx<0x400) включаются как есть: их перезапись
        тем же raw безопасна, а переводы согласуют словарь по всем ссылкам.
        Граница скана растёт вслед за записями (как в dumpText.py), чтобы
        последняя запись не обрезалась по max(addr)+1.
        """
        self._init(data)
        if not self._text_start and not self._text_end:
            return []
        manifest: list[dict] = []
        text_end = self._text_end
        addr = self._text_start
        while addr < text_end:
            rec_start = addr
            end = self._record_bound(data, addr)
            if end <= rec_start or end > len(data):
                break
            raw = data[rec_start:end - 1] if data[end - 1] == 0 else \
                data[rec_start:end]
            try:
                out = bytearray()
                self._decompress(data, rec_start, end - rec_start, out, 0,
                                 {rec_start})
                index = self._addr_to_index.get(rec_start)
                text = self._stringify(out, index)
            except Exception:
                text = ''
            if text.strip():
                manifest.append({
                    'target': rec_start,
                    'free_after': end - rec_start,
                    'raw': raw,
                    'original': text,
                })
            addr = end
            if addr > text_end:
                text_end = addr
        return manifest

    def _decompress(self, data: bytes, start: int, length: int,
                    out: bytearray, depth: int, stack: set[int]) -> None:
        """Раскрывает запись в out; словарные ссылки — рекурсивно."""
        if depth > _MAX_DICT_DEPTH:
            raise ValueError(f"Oracle dictionary too deep at 0x{start:X}")
        end = min(start + length, len(data))
        i = start
        while i < end:
            b = data[i]
            if b == 0:
                break
            if 2 <= b < 6 and i + 1 < end:
                idx = ((b - 2) << 8) | data[i + 1]
                daddr = self._idx_to_addr.get(idx)
                if daddr is not None:
                    if daddr in stack:
                        raise ValueError(
                            f"Oracle dictionary cycle at 0x{daddr:X}")
                    stack.add(daddr)
                    try:
                        self._decompress(data, daddr, len(data) - daddr,
                                         out, depth + 1, stack)
                    finally:
                        stack.discard(daddr)
                    if len(out) > _MAX_DECOMPRESS_OUT:
                        raise ValueError('Oracle decompression output too large')
                    i += 2
                    continue
                out.append(b)
                out.append(data[i + 1])
                i += 2
                continue
            if 6 <= b < 0x10 and i + 1 < end:
                out.append(b)
                out.append(data[i + 1])
                if len(out) > _MAX_DECOMPRESS_OUT:
                    raise ValueError('Oracle decompression output too large')
                i += 2
                continue
            out.append(b)
            i += 1

    def _record_bound(self, data: bytes, start: int) -> int:
        """Конец записи (мимо 0x00 или перед соседней записью без 0x00).

        Граница скана — конец данных (а не self._text_end): последняя запись
        пула лежит за max(addr)+1, и обрезать её по начальной text_end нельзя.
        Внешний цикл build_manifest всё равно ограничивает продвижение.
        """
        pos = start
        end = len(data)
        while pos < end and data[pos] != 0:
            b = data[pos]
            pos += 1
            if self._addr_to_index.get(pos) is not None:
                return pos
            if 2 <= b < 0x10 and pos < end:
                pos += 1
            if self._addr_to_index.get(pos) is not None:
                return pos
        if pos < end:
            pos += 1
        return pos

    def _stringify(self, data: bytearray, index: int | None) -> str:
        parts: list[str] = []
        i = 0
        n = len(data)
        while i < n:
            b = data[i]
            if b == 0x01:
                parts.append('[NL]')
            elif b == 0x7E or b == 0x7F:
                parts.append('[TRIANGLE]' if b == 0x7E else '[RECTANGLE]')
            elif b == 0x27 or (0x20 <= b <= 0x7D):
                parts.append('~' if b == 0x5C else chr(b))
            elif (0x80 <= b < 0x91) or (0xA0 <= b < 0xB1):
                parts.append(_SPEC_CHAR_TABLE[b - 0x80])
            elif b == 0x06 and i + 1 < n:
                p = data[i + 1]
                if p & 0x80:
                    parts.append(f'[ITEM(0x{p & 0x7F:02X})]')
                else:
                    ch = _KANJI_TABLE[p & 0x7F] if (p & 0x7F) < 0x60 else '？'
                    parts.append(ch if ch != '？' else f'[SYM(0x{p & 0x7F:02X})]')
                i += 1
            elif b == 0x07 and i + 1 < n:
                parts.append(self._label_token('JUMP', index, data[i + 1]))
                i += 1
            elif b == 0x09 and i + 1 < n:
                p = data[i + 1]
                parts.append(f'[COL({p})]' if p < 0x80 else f'[COL(0x{p:02X})]')
                i += 1
            elif b == 0x0A and i + 1 < n:
                p = data[i + 1]
                if p == 0:
                    parts.append('[LINK]')
                    i += 1
                elif p == 1:
                    parts.append('[CHILD]')
                    i += 1
                elif p == 2:
                    parts.append('[SECRET1]')
                    i += 1
                elif p == 3:
                    parts.append('[SECRET2]')
                    i += 1
                else:
                    parts.append('[X_0A]')
            elif b == 0x0B and i + 1 < n:
                parts.append(f'[CHARSFX(0x{data[i + 1]:02X})]')
                i += 1
            elif b == 0x0C and i + 1 < n:
                p = data[i + 1]
                kind, c = p >> 3, p & 3
                token = {
                    0: f'[SPEED({c})]',
                    1: '[NUM1]',
                    2: '[OPT]',
                    3: '[STOP]',
                    4: f'[POS({c})]',
                    5: '[HEARTPIECE]',
                    6: '[NUM2]',
                    7: '[SLOW]',
                }.get(kind)
                parts.append(token if token is not None else f'[CMD(0x{p:02X})]')
                i += 1
            elif b == 0x0D and i + 1 < n:
                parts.append(f'[WAIT({data[i + 1]})]')
                i += 1
            elif b == 0x0E and i + 1 < n:
                parts.append(f'[SFX(0x{data[i + 1]:02X})]')
                i += 1
            elif b == 0x0F and i + 1 < n:
                parts.append(self._label_token('CALL', index, data[i + 1]))
                i += 1
            elif b in _SYMBOL_TOKENS:
                parts.append(_SYMBOL_TOKENS[b])
            elif b == 0xB8 and i + 1 < n and data[i + 1] == 0xB9:
                parts.append('[ABTN]')
                i += 1
            elif b == 0xBA and i + 1 < n and data[i + 1] == 0xBB:
                parts.append('[BBTN]')
                i += 1
            elif b == 0:
                break
            else:
                parts.append(f'[X_{b:02X}]')
            i += 1
        return ''.join(parts)

    @staticmethod
    def _index_name(index: int) -> str:
        if index < 0x400:
            return f'DICT{index >> 8:X}_{index & 0xFF:02X}'
        return f'TX_{index - 0x400:04X}'

    @classmethod
    def _label_token(cls, op: str, index: int | None, p: int) -> str:
        if index is None or p >= 0xFC:
            return f'[{op}(0x{p:02X})]'
        return f'[{op}({cls._index_name((index & 0xFF00) | p)})]'

    def encode(self, text: str) -> bytes:
        """Перекодирует строку в байты (raw, без словарной рекомпрессии).
        """
        return self.encode_literal(text)

    def encode_literal(self, text: str) -> bytes:
        """Литеральное кодирование (без словарной рекомпрессии)."""
        out = bytearray()
        i = 0
        n = len(text)
        while i < n:
            if text[i] == '[':
                m = _TOKEN_RE.match(text, i)
                if m is not None:
                    encoded = self._encode_token(m)
                    if encoded is not None:
                        out.extend(encoded)
                        i = m.end()
                        continue
            ch = text[i]
            code = ord(ch)
            if ch == '~':
                out.append(0x5C)
            elif 0x20 <= code <= 0x7E:
                out.append(code)
            elif ch in _SPEC_REV:
                out.append(_SPEC_REV[ch])
            elif ch in _KANJI_REV:
                out.append(0x06)
                out.append(_KANJI_REV[ch])
            else:
                if ch not in self.last_unmapped_chars:
                    self.last_unmapped_chars.append(ch)
            i += 1
        return bytes(out)

    def encode_compressed(self, text: str) -> bytes:
        """Словарная рекомпрессия: encode_literal + greedy longest-match.

        Полные раскрытия dict-записей (idx<0x400) служат фразами; каждая замена
        сокращает поток (фраза выигрывает минимум 1 байт). Декодирование ссылки
        даёт ровно те же байты, что и исходная фраза — round-trip безопасен.
        """
        raw = self.encode_literal(text)
        return self._dict_compress(raw)

    def _dict_compress(self, raw: bytes) -> bytes:
        phrases = self._dict_phrases()
        if not phrases:
            return raw
        buckets: dict[int, list[tuple[bytes, int]]] = {}
        for p, idx in phrases:
            buckets.setdefault(p[0], []).append((p, idx))
        cmp_phrases = {b: sorted(lst, key=lambda kv: len(kv[0]), reverse=True)
                       for b, lst in buckets.items()}
        out = bytearray()
        i = 0
        n = len(raw)
        while i < n:
            best = None
            for p, idx in cmp_phrases.get(raw[i], ()):
                if raw.startswith(p, i):
                    best = (p, idx)
                    break
            if best is not None:
                p, idx = best
                out.append(2 + (idx >> 8))
                out.append(idx & 0xFF)
                i += len(p)
            else:
                out.append(raw[i])
                i += 1
        return bytes(out)

    def _dict_phrases(self) -> list[tuple[bytes, int]]:
        """Фразы = полные раскрытия записей словаря (без 0x00)."""
        data = self._last_data
        if data is None:
            return []
        if self._dict_phrase_cache is not None:
            return self._dict_phrase_cache
        phrases: list[tuple[bytes, int]] = []
        for idx, addr in self._idx_to_addr.items():
            if idx >= 0x400:
                continue
            out = bytearray()
            try:
                self._decompress(data, addr, len(data) - addr, out, 0, {addr})
            except ValueError:
                continue
            p = bytes(out)
            if len(p) >= 2 and b'\x00' not in p:
                phrases.append((p, idx))
        self._dict_phrase_cache = sorted(
            phrases, key=lambda kv: len(kv[0]), reverse=True)
        return self._dict_phrase_cache

    def _encode_token(self, m: re.Match) -> bytes | None:
        if m.group('fix') is not None:
            return _NOARG_TOKENS.get('[' + m.group('fix') + ']')
        if m.group('rawhex') is not None:
            return bytes([int(m.group('rawhex'), 16)])
        if m.group('param') is not None:
            name = m.group('param')
            arg = m.group('arg')
            val = int(arg, 0) if arg.lower().startswith('0x') else int(arg)
            if name == 'COL':
                return bytes([0x09, val]) if 0 <= val <= 0xFF else None
            if name == 'SPEED':
                return bytes([0x0C, val & 3]) if 0 <= val <= 3 else None
            if name == 'POS':
                return bytes([0x0C, 0x20 | (val & 3)]) if 0 <= val <= 3 else None
            if name == 'WAIT':
                return bytes([0x0D, val]) if 0 <= val <= 0xFF else None
            if name == 'ITEM':
                return bytes([0x06, 0x80 | (val & 0x7F)]) if 0 <= val <= 0xFF else None
            if name == 'SYM':
                return bytes([0x06, val]) if 0 <= val <= 0x7F else None
            if name == 'CHARSFX':
                return bytes([0x0B, val]) if 0 <= val <= 0xFF else None
            if name == 'SFX':
                return bytes([0x0E, val]) if 0 <= val <= 0xFF else None
            if name == 'CMD':
                return bytes([0x0C, val]) if 0 <= val <= 0xFF else None
            return None  # pragma: no cover - недостижимо: имена param исчерпаны regex выше
        if m.group('label') is not None:
            param = self._label_param(m.group('target'))
            if param is None:
                return None  # pragma: no cover - недостижимо: target из regex всегда парсится
            op = m.group('label')
            return bytes([0x07, param]) if op == 'JUMP' else bytes([0x0F, param])
        return None  # pragma: no cover - недостижимо: одна из групп regex всегда участвует

    @staticmethod
    def _label_param(target: str) -> int | None:
        if target.startswith('0x'):
            return int(target, 16)
        if target.startswith('TX_'):
            return int(target[3:], 16) & 0xFF
        if target.startswith('DICT'):
            return int(target[6:], 16)
        return None
