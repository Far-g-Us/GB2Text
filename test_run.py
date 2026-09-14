
import logging
import os
import re
import shutil
import traceback

logging.basicConfig(level=logging.WARNING, format='[%(levelname)s] %(name)s: %(message)s')

from core.decoder import CharMapDecoder
from core.injector import TextInjector
from core.rom import GameBoyROM
from core.scanner import auto_detect_charmap, is_text_like
from plugins.gba_mario_luigi_ss import MarioLuigiSSPlugin
from plugins.generic import GenericGBAPlugin

results = []

def log(msg, level='INFO'):
    print(f'  [{level}] {msg}')
    results.append(msg)

try:
    # ============================================================
    # TEST 1: Mario & Luigi - Superstar Saga
    # ============================================================
    mlss_path = os.path.join('test_roms', 'Mario & Luigi - Superstar Saga (USA).gba')
    mlss_copy = os.path.join('test_roms', '_mlss_test_copy.gba')

    print()
    print('=' * 70)
    print('TEST 1: Mario & Luigi - Superstar Saga (USA).gba')
    print('=' * 70)

    # Step 1: Load ROM
    rom = GameBoyROM(mlss_path)
    log(f'ROM loaded: system={rom.system}, size={rom.size}, game_id={rom.get_game_id()}')

    # Step 2: MarioLuigiSSPlugin detection
    plugin = MarioLuigiSSPlugin()
    game_id = rom.get_game_id()
    pattern_match = re.match(plugin.game_id_pattern, game_id)
    log(f'MarioLuigiSSPlugin pattern match: {bool(pattern_match)} (pattern={plugin.game_id_pattern}, game_id={game_id})')

    # Step 3: MarioLuigiSSPlugin.get_text_segments()
    segments_mlss = plugin.get_text_segments(rom)
    log(f'MarioLuigiSSPlugin segments: {len(segments_mlss)}')
    for seg in segments_mlss[:5]:
        log(f'  - {seg[chr(110)+chr(97)+chr(109)+chr(101)]}: 0x{seg[chr(115)+chr(116)+chr(97)+chr(114)+chr(116)]:X}-0x{seg[chr(101)+chr(110)+chr(100)]:X} (size={seg[chr(101)+chr(110)+chr(100)]-seg[chr(115)+chr(116)+chr(97)+chr(114)+chr(116)]})')

    # Step 4: GenericGBAPlugin.get_text_segments()
    generic_plugin = GenericGBAPlugin()
    segments_generic = generic_plugin.get_text_segments(rom)
    log(f'GenericGBAPlugin segments: {len(segments_generic)}')
    for seg in segments_generic[:5]:
        log(f'  - {seg[chr(110)+chr(97)+chr(109)+chr(101)]}: 0x{seg[chr(115)+chr(116)+chr(97)+chr(114)+chr(116)]:X}-0x{seg[chr(101)+chr(110)+chr(100)]:X} (size={seg[chr(101)+chr(110)+chr(100)]-seg[chr(115)+chr(116)+chr(97)+chr(114)+chr(116)]})')

    # Step 5: is_text_like check
    print()
    log('--- is_text_like tests ---')
    test_data = b'Hello World! This is a test string.'
    r1 = is_text_like(test_data, 0, len(test_data))
    log(f'is_text_like(ascii text): {r1}')
    test_random = bytes(range(256))
    r2 = is_text_like(test_random, 0, 32)
    log(f'is_text_like(random bytes): {r2}')
    test_ascii = b'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    r3 = is_text_like(test_ascii, 0, len(test_ascii))
    log(f'is_text_like(ABC..): {r3}')

    # Step 6: Inject test
    print()
    log('--- Injection test (MLSS) ---')
    shutil.copy2(mlss_path, mlss_copy)
    injector = TextInjector(mlss_copy)

    for seg in segments_mlss[:1]:
        seg_name = seg[chr(110)+chr(97)+chr(109)+chr(101)]
        if not seg.get(chr(100)+chr(101)+chr(99)+chr(111)+chr(100)+chr(101)+chr(114)):
            charmap = auto_detect_charmap(rom.data, seg[chr(115)+chr(116)+chr(97)+chr(114)+chr(116)])
            seg[chr(100)+chr(101)+chr(99)+chr(111)+chr(100)+chr(101)+chr(114)] = CharMapDecoder(charmap)

        msgs = injector._extract_original_messages(seg)
        log(f'Segment {seg_name}: {len(msgs)} messages found')
        for m in msgs[:3]:
            log(f'  msg offset=0x{m[chr(111)+chr(102)+chr(102)+chr(115)+chr(101)+chr(116)]:X}, len={m[chr(108)+chr(101)+chr(110)+chr(103)+chr(116)+chr(104)]}')
        if msgs:
            garbled = ['X' * min(m[chr(108)+chr(101)+chr(110)+chr(103)+chr(116)+chr(104)], 5) for m in msgs]
            ok = injector.inject_segment(seg_name, garbled, plugin, skip_long=True)
            log(f'inject_segment(skip_long=True): {ok}')
            if ok:
                injector.save(mlss_copy)
                orig = open(mlss_path, 'rb').read()
                patched = open(mlss_copy, 'rb').read()
                diff_count = sum(1 for a, b in zip(orig, patched, strict=False) if a != b)
                log(f'ROM patched: {diff_count} bytes differ from original')
        break

    if os.path.exists(mlss_copy):
        os.remove(mlss_copy)

    # ============================================================
    # TEST 2: Astro Boy - Omega Factor
    # ============================================================
    astro_path = os.path.join('test_roms', 'Astro Boy - Omega Factor (USA).gba')
    astro_copy = os.path.join('test_roms', '_astro_test_copy.gba')

    print()
    print('=' * 70)
    print('TEST 2: Astro Boy - Omega Factor (USA).gba')
    print('=' * 70)

    rom2 = GameBoyROM(astro_path)
    log(f'ROM loaded: system={rom2.system}, size={rom2.size}, game_id={rom2.get_game_id()}')

    match2 = re.match(plugin.game_id_pattern, rom2.get_game_id())
    log(f'MarioLuigiSSPlugin on Astro: pattern_match={bool(match2)}')

    segments_astro = generic_plugin.get_text_segments(rom2)
    log(f'GenericGBAPlugin segments: {len(segments_astro)}')
    for seg in segments_astro[:5]:
        log(f'  - {seg[chr(110)+chr(97)+chr(109)+chr(101)]}: 0x{seg[chr(115)+chr(116)+chr(97)+chr(114)+chr(116)]:X}-0x{seg[chr(101)+chr(110)+chr(100)]:X} (size={seg[chr(101)+chr(110)+chr(100)]-seg[chr(115)+chr(116)+chr(97)+chr(114)+chr(116)]})')

    # Injection test
    print()
    log('--- Injection test (Astro Boy) ---')
    shutil.copy2(astro_path, astro_copy)
    injector2 = TextInjector(astro_copy)

    for seg in segments_astro[:1]:
        seg_name = seg[chr(110)+chr(97)+chr(109)+chr(101)]
        if not seg.get(chr(100)+chr(101)+chr(99)+chr(111)+chr(100)+chr(101)+chr(114)):
            charmap = auto_detect_charmap(rom2.data, seg[chr(115)+chr(116)+chr(97)+chr(114)+chr(116)])
            seg[chr(100)+chr(101)+chr(99)+chr(111)+chr(100)+chr(101)+chr(114)] = CharMapDecoder(charmap)

        msgs = injector2._extract_original_messages(seg)
        log(f'Segment {seg_name}: {len(msgs)} messages found')
        for m in msgs[:3]:
            log(f'  msg offset=0x{m[chr(111)+chr(102)+chr(102)+chr(115)+chr(101)+chr(116)]:X}, len={m[chr(108)+chr(101)+chr(110)+chr(103)+chr(116)+chr(104)]}')
        if msgs:
            garbled = ['X' * min(m[chr(108)+chr(101)+chr(110)+chr(103)+chr(116)+chr(104)], 5) for m in msgs]
            ok = injector2.inject_segment(seg_name, garbled, generic_plugin, skip_long=True)
            log(f'inject_segment(skip_long=True): {ok}')
            if ok:
                injector2.save(astro_copy)
                orig = open(astro_path, 'rb').read()
                patched = open(astro_copy, 'rb').read()
                diff_count = sum(1 for a, b in zip(orig, patched, strict=False) if a != b)
                log(f'ROM patched: {diff_count} bytes differ from original')
        break

    if os.path.exists(astro_copy):
        os.remove(astro_copy)

    print()
    print('=' * 70)
    print('ALL TESTS COMPLETED SUCCESSFULLY')
    print('=' * 70)

except Exception as e:
    print(f'FATAL ERROR: {e}')
    traceback.print_exc()
