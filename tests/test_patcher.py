"""
GB Text Extraction Framework

ПРЕДУПРЕЖДЕНИЕ ОБ АВТОРСКИХ ПРАВАХ:
Этот программный инструмент предназначен ТОЛЬКО для анализа ROM-файлов,
законно принадлежащих пользователю. Использование этого инструмента для
нелегального копирования, распространения или модификации защищенных
авторским правом материалов строго запрещено.
"""

import os
import zlib
from pathlib import Path

import pytest

from core.patcher import (
    BPS_MAGIC,
    IPS_MAGIC,
    PatchError,
    _vlq_decode,
    _vlq_encode,
    apply_patch,
    bps_apply,
    bps_create,
    create_patch,
    ips_apply,
    ips_create,
)


def _sample_rom(size: int = 0x8000, seed: int = 1) -> bytes:
    rng = seed
    out = bytearray()
    for _ in range(size):
        rng = (rng * 1103515245 + 12345) & 0x7FFFFFFF
        out.append((rng >> 16) & 0xFF)
    out[0:4] = b"GB2T"
    return bytes(out)


class TestVLQ:
    @pytest.mark.parametrize("value,expected", [
        (0, b"\x80"),
        (1, b"\x81"),
        (127, b"\xff"),
        (128, b"\x00\x80"),
        (129, b"\x01\x80"),
        (255, b"\x7f\x80"),
        (256, b"\x00\x81"),
        (16384, b"\x00\xff"),
    ])
    def test_encode(self, value, expected):
        assert _vlq_encode(value) == expected

    @pytest.mark.parametrize("value", [0, 1, 2, 127, 128, 129, 255, 256,
                                       16383, 16384, 10 ** 6, 10 ** 9])
    def test_roundtrip(self, value):
        data = _vlq_encode(value)
        decoded, pos = _vlq_decode(data, 0)
        assert decoded == value
        assert pos == len(data)

    def test_decode_truncated(self):
        data = b"\x00"
        with pytest.raises(PatchError):
            _vlq_decode(data, 0)


class TestIPS:
    def test_roundtrip_literal(self):
        src = _sample_rom(0x10000)
        tgt = bytearray(src)
        tgt[0x120] = 0xAA
        tgt[0x123:0x125] = b"\x11\x22"
        tgt[0x2000:0x2004] = b"\xDE\xAD\xBE\xEF"
        patch = ips_create(src, bytes(tgt))
        assert patch[:5] == IPS_MAGIC
        assert patch[-3:] == b"EOF"
        out = ips_apply(src, patch)
        assert out == bytes(tgt)

    def test_roundtrip_identical(self):
        src = _sample_rom(0x10000)
        patch = ips_create(src, src)
        assert patch == b"PATCHEOF"
        assert ips_apply(src, patch) == src

    def test_rle_used(self):
        src = _sample_rom(0x10000)
        tgt = bytearray(src)
        tgt[0x800:0x880] = b"\xFF" * 0x80
        patch = ips_create(src, bytes(tgt))
        assert b"\x00\x00" in patch
        assert ips_apply(src, patch) == bytes(tgt)

    def test_eof_inside_record_data(self):
        src = _sample_rom(0x20000)
        tgt = bytearray(src)
        tgt[0x100:0x103] = b"EOF"
        patch = ips_create(src, bytes(tgt))
        assert ips_apply(src, patch) == bytes(tgt)

    def test_long_block_chunked(self):
        src = _sample_rom(0x40000)
        tgt = bytearray(src)
        tgt[0x1000:0x1000 + 0x11000] = b"\xA5" * 0x11000
        patch = ips_create(src, bytes(tgt))
        assert ips_apply(src, patch) == bytes(tgt)

    def test_expand_rom(self):
        src = _sample_rom(0x10000)
        tgt = src + b"\x00\x01\x02\x03"
        patch = ips_create(src, tgt)
        assert ips_apply(src, patch) == tgt

    def test_truncate_not_supported(self):
        src = _sample_rom(0x10000)
        tgt = src[:0x800]
        patch = ips_create(src, tgt)
        out = ips_apply(src, patch)
        assert out == src

    def test_bad_signature(self):
        with pytest.raises(PatchError):
            ips_apply(_sample_rom(0x100), b"NOPE")

    def test_missing_eof(self):
        with pytest.raises(PatchError):
            ips_apply(_sample_rom(0x100), b"PATCH\x00\x00\x00\x01\xff")

    def test_truncated_record(self):
        patch = b"PATCH\x00\x00\x10\x00\x04\x01\x02\x03EOF"
        with pytest.raises(PatchError):
            ips_apply(_sample_rom(0x2000), patch)

    def test_create_patch_dispatch(self):
        src = _sample_rom(0x1000)
        tgt_mut = bytearray(src)
        tgt_mut[10] = 0x5A
        tgt = bytes(tgt_mut)
        assert create_patch(src, tgt, "ips") == ips_create(src, tgt)
        assert create_patch(src, tgt, "bps") == bps_create(src, tgt)
        with pytest.raises(ValueError):
            create_patch(src, tgt, "nup")


class TestBPS:
    def test_roundtrip_literal(self):
        src = _sample_rom(0x40000)
        tgt = bytearray(src)
        tgt[0x1234:0x1250] = os.urandom(0x1C)
        tgt[0x30000:0x32000] = os.urandom(0x2000)
        patch = bps_create(src, bytes(tgt))
        assert patch[:4] == BPS_MAGIC
        out = bps_apply(src, patch)
        assert out == bytes(tgt)

    def test_roundtrip_identical(self):
        src = _sample_rom(0x40000)
        patch = bps_create(src, src)
        assert bps_apply(src, patch) == src

    def test_roundtrip_expand(self):
        src = _sample_rom(0x8000)
        tgt = src + os.urandom(0x1000)
        patch = bps_create(src, tgt)
        assert bps_apply(src, patch) == tgt

    def test_roundtrip_shrink(self):
        src = _sample_rom(0x8000)
        tgt = src[:0x400]
        patch = bps_create(src, tgt)
        assert bps_apply(src, patch) == tgt

    def test_many_adjacent_edits(self):
        src = _sample_rom(0x10000)
        tgt = bytearray(src)
        for i in range(0x100):
            tgt[0x1000 + i * 3] += 1
        patch = bps_create(src, bytes(tgt))
        assert bps_apply(src, patch) == bytes(tgt)

    def test_wrong_source_raises(self):
        src = _sample_rom(0x10000)
        tgt = bytearray(src)
        tgt[0x100] = 0x55
        patch = bps_create(src, bytes(tgt))
        other = _sample_rom(0x10000, seed=2)
        with pytest.raises(PatchError):
            bps_apply(other, patch)

    def test_bad_signature(self):
        with pytest.raises(PatchError):
            bps_apply(_sample_rom(0x100), b"NOPE")

    def test_tampered_patch_raises(self):
        src = _sample_rom(0x10000)
        tgt = bytearray(src)
        tgt[0x200] = 0x77
        patch = bytearray(bps_create(src, bytes(tgt)))
        patch[-1] ^= 0xFF
        with pytest.raises(PatchError):
            bps_apply(src, bytes(patch))

    def test_crc_target_mismatch_raises(self):
        src = _sample_rom(0x10000)
        tgt = bytearray(src)
        tgt[0x200] = 0x77
        patch = bytearray(bps_create(src, bytes(tgt)))
        patch[-8:-4] = b"\x00\x00\x00\x00"
        patch[-4:] = zlib.crc32(bytes(patch[:-4])).to_bytes(4, "little")
        with pytest.raises(PatchError):
            bps_apply(src, bytes(patch))


class TestBPSCanonical:
    def test_crc_fields_at_end(self):
        src = _sample_rom(0x1000)
        tgt_mut = bytearray(src)
        tgt_mut[0x20] = 0x42
        tgt = bytes(tgt_mut)
        patch = bps_create(src, tgt)
        assert patch[:4] == BPS_MAGIC
        src_crc = int.from_bytes(patch[-12:-8], "little")
        tgt_crc = int.from_bytes(patch[-8:-4], "little")
        patch_crc = int.from_bytes(patch[-4:], "little")
        assert src_crc == zlib.crc32(src)
        assert tgt_crc == zlib.crc32(tgt)
        assert patch_crc == zlib.crc32(patch[:-4])

    def test_handmade_canonical_patch_applies(self):
        src = b"\x01\x02\x03\x04\x05"
        tgt = b"\x01\xAA\x03\x04\x05"
        body = bytearray()
        body.extend(_vlq_encode(len(src)))
        body.extend(_vlq_encode(len(tgt)))
        body.extend(_vlq_encode(0))
        body.extend(_vlq_encode(((1 - 1) << 2) | 0))
        body.extend(_vlq_encode(((1 - 1) << 2) | 1))
        body.extend(b"\xAA")
        body.extend(_vlq_encode(((3 - 1) << 2) | 0))
        body.extend(zlib.crc32(src).to_bytes(4, "little"))
        body.extend(zlib.crc32(tgt).to_bytes(4, "little"))
        body.extend(zlib.crc32(BPS_MAGIC + bytes(body)).to_bytes(4, "little"))
        assert bps_apply(src, BPS_MAGIC + bytes(body)) == tgt

    def test_source_read_uses_output_offset(self):
        src = b"ABCDEFGH"
        tgt = b"AB" + b"zz" + b"EFGH"
        patch = bps_create(src, tgt)
        assert bps_apply(src, patch) == tgt
        src_crc = int.from_bytes(patch[-12:-8], "little")
        assert src_crc == zlib.crc32(src)

    def test_apply_accepts_source_copy(self):
        src = b"ABCDEFGH"
        tgt = b"AB" + b"AB" + b"EFGH"
        body = bytearray()
        body.extend(_vlq_encode(len(src)))
        body.extend(_vlq_encode(len(tgt)))
        body.extend(_vlq_encode(0))
        body.extend(_vlq_encode(((2 - 1) << 2) | 0))
        body.extend(_vlq_encode(((2 - 1) << 2) | 2))
        body.extend(_vlq_encode(0))
        body.extend(_vlq_encode(((4 - 1) << 2) | 0))
        body.extend(zlib.crc32(src).to_bytes(4, "little"))
        body.extend(zlib.crc32(tgt).to_bytes(4, "little"))
        body.extend(zlib.crc32(BPS_MAGIC + bytes(body)).to_bytes(4, "little"))
        assert bps_apply(src, BPS_MAGIC + bytes(body)) == tgt

    def test_apply_accepts_target_copy(self):
        src = b"AB"
        tgt = b"ABABAB"
        body = bytearray()
        body.extend(_vlq_encode(len(src)))
        body.extend(_vlq_encode(len(tgt)))
        body.extend(_vlq_encode(0))
        body.extend(_vlq_encode(((2 - 1) << 2) | 0))
        body.extend(_vlq_encode(((4 - 1) << 2) | 3))
        body.extend(_vlq_encode(0))
        body.extend(zlib.crc32(src).to_bytes(4, "little"))
        body.extend(zlib.crc32(tgt).to_bytes(4, "little"))
        body.extend(zlib.crc32(BPS_MAGIC + bytes(body)).to_bytes(4, "little"))
        assert bps_apply(src, BPS_MAGIC + bytes(body)) == tgt


class TestAutoDetect:
    def test_apply_patch_detects_format(self):
        src = _sample_rom(0x10000)
        tgt_mut = bytearray(src)
        tgt_mut[0x400] = 0x33
        tgt = bytes(tgt_mut)
        assert apply_patch(src, ips_create(src, tgt)) == tgt
        assert apply_patch(src, bps_create(src, tgt)) == tgt

    def test_unknown_format(self):
        with pytest.raises(PatchError):
            apply_patch(_sample_rom(0x100), b"UNKNOWN")


class TestRealROMRoundTrip:
    def _rom_paths(self):
        base = Path(__file__).parent.parent / 'test_roms'
        if not base.is_dir():
            return []
        return sorted(base.glob("*.*"))

    @pytest.mark.rom_required
    @pytest.mark.slow
    def test_ips_bps_roundtrip_on_roms(self):
        roms = self._rom_paths()
        if not roms:
            pytest.skip("test_roms/ пуста")
        for rom_path in roms:
            data = rom_path.read_bytes()
            if len(data) < 0x100:
                continue
            tgt_mut = bytearray(data)
            for off in (0x10, 0x100, 0x1000, min(len(tgt_mut) - 4, 0xFFFFF0)):
                if 0 <= off < len(tgt_mut):
                    tgt_mut[off] ^= 0x5A
            tgt = bytes(tgt_mut)
            patch = bps_create(data, tgt)
            assert bps_apply(data, patch) == tgt
            if len(data) <= 0x1000000:
                patch = ips_create(data, tgt)
                assert ips_apply(data, patch) == tgt
