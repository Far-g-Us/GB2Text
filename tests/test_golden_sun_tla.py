"""
Тесты для плагина Golden Sun: The Lost Age (GBA) - контекстный Хаффман.

Проверяются детерминированность декодера, токен-маппинг (в т.ч. двухбайтовые
контрольные коды), структура сегментов и, при наличии легального ROM,
интеграция с реальными данными (адреса/счётчики — только факты, не тексты).
"""

import os
import re
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.rom import GameBoyROM
from plugins.gba_golden_sun_tla import (
    TLA_CREDITS_AT,
    TLA_CREDITS_COUNT,
    TLA_CREDITS_REGION_END,
    TLA_CREDITS_REGION_START,
    TLA_CREDITS_WIN,
    GoldenSunTLAPlugin,
    GoldenSunTLATextDecoder,
)

# SHA1 golden sun tla rom not exposed; game code AGFE
TLA_ROM = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'test_game', 'Golden Sun - The Lost Age (USA, Europe).gba',
)


def _has_tla_rom() -> bool:
    return os.path.exists(TLA_ROM)


def _fits_segment(plugin, segment, translation, rom) -> bool:
    try:
        compressed = segment['encoder'](translation)
    except (ValueError, KeyError, IndexError):
        return False
    return bool(len(compressed) <= segment['compressed_length'])


@pytest.fixture(scope='module')
def tla_plugin():
    return GoldenSunTLAPlugin()


@pytest.fixture(scope='module')
def tla_rom():
    if not _has_tla_rom():
        pytest.skip("Golden Sun TLA ROM не найден (легально-owned только)")
    return GameBoyROM(TLA_ROM)


@pytest.fixture(scope='module')
def tla_segments(tla_rom, tla_plugin):
    return tla_plugin.get_text_segments(tla_rom)


class TestTLAPluginContract:
    def test_plugin_matches_agfe(self, tla_plugin):
        match = re.search(tla_plugin.game_id_pattern, 'GBA_AGFE')
        assert match is not None

    def test_plugin_rejects_agse(self, tla_plugin):
        match = re.search(tla_plugin.game_id_pattern, 'GBA_AGSE')
        assert match is None

    def test_game_codes(self, tla_plugin, tla_rom):
        match = re.fullmatch(tla_plugin.game_id_pattern, tla_rom.get_game_id())
        assert match is not None
        assert match.group(1) == 'AGFE'

    def test_terminators(self, tla_plugin):
        assert tla_plugin.get_terminators('gs_dialogue_f00_000') == [0x00]


class TestTLATokenMapping:
    def test_nl_end_cont(self):
        dec = GoldenSunTLATextDecoder()
        assert dec.decode(b'\x01') == '{NL}'
        assert dec.decode(b'\x02') == '{END}'
        assert dec.decode(b'\x03') == '{CONT}'

    def test_two_byte_token(self):
        """0x08 0x05 (цвет) — двухбайтовый токен, bi-directional."""
        dec = GoldenSunTLATextDecoder()
        text = dec.decode(b'\x08\x05Hello\x02')
        assert text == '{08 05}Hello{END}'
        assert dec.encode(text) == b'\x08\x05Hello\x02'

    def test_two_byte_token_reverse(self):
        dec = GoldenSunTLATextDecoder()
        assert dec.encode('{12 01}') == b'\x12\x01'
        assert dec.encode('{1D 02}') == b'\x1d\x02'

    def test_tokens_avoid_split_patterns(self):
        """Токены не должны ломать _split_messages: без '[', '\n', '[XX]'."""
        dec = GoldenSunTLATextDecoder()
        for b in range(0x01, 0x20):
            token = dec.decode(bytes([b]))
            assert '[' not in token
            assert '\n' not in token
            assert not re.fullmatch(r'\[[0-9A-Fa-f]{2}\]', token)
            assert token != '[END]'


class TestTLASegments:
    def test_segment_count(self, tla_segments):
        dialogue = [s for s in tla_segments if s['name'].startswith('gs_dialogue_')]
        assert len(dialogue) >= 12000

    def test_segment_bounds_in_rom(self, tla_rom, tla_segments):
        for segment in tla_segments:
            assert 0 <= segment['start'] < segment['end'] <= len(tla_rom.data)

    def test_segment_raw_text_not_empty(self, tla_segments):
        for segment in tla_segments:
            assert isinstance(segment['raw_text'], str)
            assert len(segment['raw_text']) > 0

    def test_all_dialogue_named_consistently(self, tla_segments):
        names = [s['name'] for s in tla_segments
                 if s['name'].startswith('gs_dialogue_')]
        assert all(re.fullmatch(r'gs_dialogue_f\d{2}_\d{3}', n) for n in names)
        assert len(set(names)) == len(names)


class TestTLAHuffman:
    def test_decoder_deterministic(self, tla_rom):
        from plugins.gba_golden_sun import GoldenSunHuffmanDecoder
        dec = GoldenSunHuffmanDecoder(
            tla_rom.data, offsets_base=0x060A4C, trees_base=0x05F914)
        sample = bytes(tla_rom.data[0x060C38:0x060C38 + 64])
        a = dec.decode_string(sample)
        b = dec.decode_string(sample)
        assert a == b


class TestTLAEncoder:
    def test_encode_length_never_exceeds_slot(self, tla_rom, tla_segments):
        for segment in tla_segments:
            if 'encoder' not in segment:
                continue
            compressed = segment['encoder'](segment['raw_text'])
            assert (
                len(compressed) <= segment['compressed_length']
            ), segment['name']

    def test_segment_encoder_contract(self, tla_segments):
        dialogue = [s for s in tla_segments if s['name'].startswith('gs_dialogue_')]
        for segment in dialogue[:200]:
            assert callable(segment['encoder'])
            assert segment['compression'] == 'huffman'
            assert segment['compressed_length'] > 0
            assert segment['compressed_length'] == segment['end'] - segment['start']
            assert segment['pad_byte'] == 0xFF


class TestTLAInjector:
    def test_inject_single_message(self, tla_rom, tla_plugin, tla_segments, tmp_path):
        from core.injector import TextInjector

        translation = 'Hello World!'
        seg = next(
            (s for s in tla_segments
             if s['name'].startswith('gs_dialogue_')
             and _fits_segment(tla_plugin, s, translation, tla_rom)),
            None,
        )
        assert seg is not None, 'нет сегмента, подходящего под тестовый перевод'
        name = seg['name']

        injector = TextInjector(tla_rom.path)
        ok = injector.inject_segment(name, [translation], tla_plugin,
                                     segments=tla_segments)
        assert ok

        out_rom = tmp_path / 'patched.gba'
        injector.save(str(out_rom))
        assert out_rom.exists()
        assert len(out_rom.read_bytes()) == len(tla_rom.data)

        from core.rom import GameBoyROM
        patched = GameBoyROM(str(out_rom))
        patched_seg = next(
            s for s in tla_plugin.get_text_segments(patched)
            if s['name'] == name)
        assert patched_seg['raw_text'] == translation

    def test_inject_no_translation_is_noop(self, tla_rom):
        from core.injector import TextInjector
        plugin = GoldenSunTLAPlugin()
        injector = TextInjector(tla_rom.path)
        assert injector.inject_segment('gs_dialogue_f00_005', [], plugin) is True


@pytest.mark.rom_required
@pytest.mark.slow
def test_real_rom_roundtrip():
    """extract → inject (те же тексты) → extract: идентичные тексты."""
    if not _has_tla_rom():
        pytest.skip('Golden Sun TLA ROM не найден (легально-owned только)')
    from core.extractor import TextExtractor
    from core.injector import TextInjector

    plugin = GoldenSunTLAPlugin()
    with tempfile.TemporaryDirectory() as td:
        work = os.path.join(td, 'roundtrip.gba')
        shutil.copyfile(TLA_ROM, work)
        rom = GameBoyROM(TLA_ROM)
        segments = plugin.get_text_segments(rom)
        before = TextExtractor(TLA_ROM, rom=rom).extract()
        injector = TextInjector(work)
        injected = 0
        for seg in segments:
            texts = [m['text'] for m in before.get(seg['name'], [])]
            if injector.inject_segment(seg['name'], texts, plugin,
                                       segments=segments):
                injected += 1
        injector.save(work)
        assert injected == len(segments)

        after = TextExtractor(work, rom=GameBoyROM(work)).extract()
        for seg in segments:
            before_texts = [m['text'] for m in before.get(seg['name'], [])]
            after_texts = [m['text'] for m in after.get(seg['name'], [])]
            assert before_texts == after_texts, seg['name']


class TestTLACredits:
    """ASCII-кредиты TLA — раньше не извлекались вообще."""

    def test_credits_extracted(self, tla_rom, tla_segments):
        creds = [s for s in tla_segments
                 if s['name'].startswith('gs_tla_credits_')]
        assert len(creds) == TLA_CREDITS_COUNT, (
            f'TLA: {len(creds)} кредитов, ожидаем {TLA_CREDITS_COUNT}')
        texts = {s.get('raw_text') for s in creds}
        for expected in ('NINTENDO', 'CAMELOT', 'STAFF'):
            assert expected in texts, (
                f'в кредитах TLA нет ожидаемого {expected!r}')

    def test_credits_region_bounds_are_measured(self, tla_rom, tla_segments):
        from plugins.gba_golden_sun import credits_region

        start, end = credits_region(tla_rom.data, TLA_CREDITS_WIN[0],
                                    TLA_CREDITS_WIN[1],
                                    fixed_at=TLA_CREDITS_AT)
        # Сверяется с измерением, а не с константой: при сдвиге якоря внутрь
        # строки проверка отвергла бы его, но прошла бы 399 сегментов вместо 101.
        assert start == TLA_CREDITS_REGION_START, (
            f'область стартовала с {start:#x}, измеренное начало '
            f'{TLA_CREDITS_REGION_START:#x}')
        assert end == TLA_CREDITS_REGION_END, (
            f'область закончилась на {end:#x}, измеренный конец '
            f'{TLA_CREDITS_REGION_END:#x}')
        creds = [s for s in tla_segments
                 if s['name'].startswith('gs_tla_credits_')]
        assert creds, 'кредиты не извлечены, а область непуста'
        assert creds[0]['start'] == TLA_CREDITS_REGION_START, (
            f'первый сегмент {creds[0]["start"]:#x}, измеренное начало '
            f'{TLA_CREDITS_REGION_START:#x}')
        assert creds[0]['name'] == 'gs_tla_credits_1a1a10', creds[0]['name']

    def test_wrong_anchor_falls_back_to_scan(self, tla_rom):
        # Якорь не на строке кредитов отвергается, и область ищется сканером.
        from plugins.gba_golden_sun import ascii_credits_segments, credits_region

        segs_bad = ascii_credits_segments(tla_rom.data, TLA_CREDITS_WIN[0],
                                          TLA_CREDITS_WIN[1], 'x',
                                          fixed_at=TLA_CREDITS_WIN[0])
        assert len(segs_bad) == TLA_CREDITS_COUNT, (
            f'откат дал {len(segs_bad)} сегментов вместо {TLA_CREDITS_COUNT}')
        start, end = credits_region(tla_rom.data, TLA_CREDITS_WIN[0],
                                    TLA_CREDITS_WIN[1],
                                    fixed_at=TLA_CREDITS_WIN[0])
        # Сканер возвращает на байт раньше якоря: он
        # смещении относит NUL перед печатным прогоном. Расхождение
        # сегментов то же, потому что поведение якоря не важно.
        assert start == 0x1A1A0F, (
            f'сканер возвратил {start:#x}, ожидалось 0x1A1A0F')
        assert end == TLA_CREDITS_REGION_END

    def test_short_credit_is_present(self, tla_rom, tla_segments):
        texts = {s.get('raw_text') for s in tla_segments
                 if s['name'].startswith('gs_tla_credits_')}
        assert 'and' in texts, (
            'кредит 'and' (3 символа) не попал в манифест — длина короче '
            '_CREDITS_MIN_RUN не должна быть в отборе')

    def test_credits_survive_shortening(self, tla_rom):
        from core.extractor import TextExtractor
        from core.injector import TextInjector
        from tests.test_realrom_pipeline import _inject_all, _shorten

        plugin = GoldenSunTLAPlugin()
        before = TextExtractor(TLA_ROM).extract()
        names = {n for n in before if n.startswith('gs_tla_credits_')}
        assert names
        with tempfile.TemporaryDirectory() as td:
            work = os.path.join(td, 'w.gba')
            shutil.copyfile(TLA_ROM, work)
            inj = TextInjector(work)
            segmeta = {s['name']: s for s in inj._get_segments(plugin)
                       if isinstance(s, dict)}
            _inject_all(inj, plugin, before, segmeta, _shorten)
            out = os.path.join(td, 'o.gba')
            inj.save(out)
            after = TextExtractor(out).extract()
        after_names = {n for n in after if n.startswith('gs_tla_credits_')}
        lost = names - after_names
        assert not lost, (
            f'потеряно кредитов: {len(lost)} из {len(names)}: '
            f'{sorted(lost)[:5]}')
