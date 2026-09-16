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
Модуль генерации и применения патчей IPS/BPS.

Патч-файл — легальный способ дистрибуции перевода: распространяется diff
вместо патенного ROM, законный владелец применяет его к своему экземпляру.
IPS — простой формат (без контрольных сумм, адрес до 16MB). BPS (byuu
"beat") — формат с проверкой CRC32 исходного/патченного ROM и самого патча,
допускает ROM больше 16MB (GBA 32MB).

BPS реализован по канонической спецификации byuu (nall/beat/patch.hpp,
flips libbps.cpp):
  "BPS1" | source_size VLQ | target_size VLQ | metadata_size VLQ |
  metadata | actions | source_crc LE | target_crc LE | patch_crc LE

Каждое действие — одно VLQ: length = (instr >> 2) + 1, action = instr & 3,
action ∈ {0 SourceRead, 1 TargetRead, 2 SourceCopy, 3 TargetCopy}.
"""

import zlib

BPS_MAGIC = b"BPS1"
IPS_MAGIC = b"PATCH"
IPS_EOF = b"EOF"
IPS_HEADER_SIZE = len(IPS_MAGIC)
BPS_TAIL_SIZE = 12  # source_crc + target_crc + patch_crc
IPS_MAX_OFFSET = 0xFFFFFF
IPS_MAX_LEN = 0xFFFF
IPS_RLE_MIN_RUN = 8
BPS_ACTION_SOURCE_READ = 0
BPS_ACTION_TARGET_READ = 1
BPS_ACTION_SOURCE_COPY = 2
BPS_ACTION_TARGET_COPY = 3


class PatchError(ValueError):
    """Ошибка разбора или применения патча."""

    pass


def _ips_read_u24(data: bytes, pos: int) -> int:
    return int.from_bytes(data[pos:pos + 3], "big")


def _ips_write_u24(value: int) -> bytes:
    return value.to_bytes(3, "big")


def _vlq_encode(value: int) -> bytes:
    """Байтовое VLQ-кодирование BPS: старший бит 0x80 = последний байт."""
    out = bytearray()
    while True:
        chunk = value & 0x7F
        value >>= 7
        if value == 0:
            out.append(chunk | 0x80)
            break
        value -= 1
        out.append(chunk)
    return bytes(out)


def _vlq_decode(data: bytes, pos: int) -> tuple[int, int]:
    """Читает байтовое VLQ BPS. Возвращает (значение, новая позиция)."""
    value = 0
    shift = 1
    while True:
        if pos >= len(data):
            raise PatchError("BPS: VLQ оборвалось")
        chunk = data[pos]
        pos += 1
        value += (chunk & 0x7F) * shift
        if chunk & 0x80:
            return value, pos
        shift <<= 7
        value += shift


def _signed_offset(value: int) -> int:
    """Знаковое относительное смещение BPS: чётное = +, нечётное = -."""
    if value & 1:
        return -(value >> 1)
    return value >> 1


def bps_create(source: bytes, target: bytes) -> bytes:
    """Создаёт канонический BPS-патч, преобразующий source в target.

    Кодирование отображает source→target через чередование SourceRead
    (копия совпадающего префикса из источника по позиции вывода) и
    TargetRead (литеральный блок заменяющих байт). SourceCopy/TargetCopy
    не генерируются — это допустимый линейный режим формата.
    """
    src_len = len(source)
    tgt_len = len(target)

    body = bytearray()
    body.extend(_vlq_encode(src_len))
    body.extend(_vlq_encode(tgt_len))
    body.extend(_vlq_encode(0))  # metadata size

    t = 0
    while t < tgt_len:
        match = 0
        while (t + match < tgt_len and t + match < src_len
               and source[t + match] == target[t + match]):
            match += 1
        if match:
            body.extend(_vlq_encode(((match - 1) << 2)
                                    | BPS_ACTION_SOURCE_READ))
            t += match
            continue
        diff = 0
        while (t + diff < tgt_len
               and (t + diff >= src_len
                    or source[t + diff] != target[t + diff])):
            diff += 1
        body.extend(_vlq_encode(((diff - 1) << 2)
                                | BPS_ACTION_TARGET_READ))
        body.extend(target[t:t + diff])
        t += diff

    body.extend(zlib.crc32(source).to_bytes(4, "little"))
    body.extend(zlib.crc32(target).to_bytes(4, "little"))
    payload = BPS_MAGIC + bytes(body)
    patch_crc = zlib.crc32(payload).to_bytes(4, "little")
    return payload + patch_crc


def bps_apply(rom: bytes, patch: bytes) -> bytes:
    """Применяет канонический BPS-патч к исходному ROM.

    Проверяет CRC32 исходного ROM, CRC32 результата и CRC32 самого патча.
    Поддерживает все четыре команды формата (включая чужие патчи delta-режима).
    Нулевое поле source_crc в патче означает «не проверять исходный ROM»
    (совместимость с инструментами, обнуляющими CRC источника).
    """
    if not patch.startswith(BPS_MAGIC):
        raise PatchError("BPS: неверная сигнатура (ожидалось BPS1)")
    if len(patch) < len(BPS_MAGIC) + BPS_TAIL_SIZE:
        raise PatchError("BPS: файл обрезан")

    patch_crc = int.from_bytes(patch[-4:], "little")
    if zlib.crc32(patch[:-4]) != patch_crc:
        raise PatchError("BPS: контрольная сумма патча не совпадает")
    source_crc = int.from_bytes(patch[-12:-8], "little")
    target_crc = int.from_bytes(patch[-8:-4], "little")

    if source_crc and zlib.crc32(rom) != source_crc:
        raise PatchError(
            "BPS: исходный ROM не совпадает с ожидаемым (CRC32 не сходится)"
        )

    pos = len(BPS_MAGIC)
    src_size, pos = _vlq_decode(patch, pos)
    tgt_size, pos = _vlq_decode(patch, pos)
    meta_size, pos = _vlq_decode(patch, pos)
    pos += meta_size
    data_end = len(patch) - BPS_TAIL_SIZE
    if pos > data_end:
        raise PatchError("BPS: метаданные выходят за пределы патча")
    if len(rom) != src_size:
        raise PatchError(
            f"BPS: размер исходного ROM {len(rom)} != ожидаемый {src_size}"
        )

    target = bytearray()
    target_len = 0
    source_relative = 0
    target_relative = 0

    while target_len < tgt_size:
        instr, pos = _vlq_decode(patch, pos)
        if pos > data_end:
            raise PatchError("BPS: поток команд оборвался раньше целевого размера")
        length = (instr >> 2) + 1
        action = instr & 3

        if action == BPS_ACTION_SOURCE_READ:
            if target_len + length > src_size:
                raise PatchError("BPS: SourceRead выходит за границы исходного ROM")
            target.extend(rom[target_len:target_len + length])
            target_len += length

        elif action == BPS_ACTION_TARGET_READ:
            end = pos + length
            if end > data_end:
                raise PatchError("BPS: TargetRead выходит за границы патча")
            target.extend(patch[pos:end])
            pos = end
            target_len += length

        elif action == BPS_ACTION_SOURCE_COPY:
            offset, pos = _vlq_decode(patch, pos)
            if pos > data_end:
                raise PatchError("BPS: смещение выходит за пределы патча")
            source_relative += _signed_offset(offset)
            for _ in range(length):
                if source_relative < 0 or source_relative >= src_size:
                    raise PatchError("BPS: SourceCopy выходит за границы исходного ROM")
                target.append(rom[source_relative])
                source_relative += 1
                target_len += 1

        else:
            offset, pos = _vlq_decode(patch, pos)
            if pos > data_end:
                raise PatchError("BPS: смещение выходит за пределы патча")
            target_relative += _signed_offset(offset)
            for _ in range(length):
                if target_relative < 0 or target_relative >= target_len:
                    raise PatchError("BPS: TargetCopy выходит за границы целевого буфера")
                target.append(target[target_relative])
                target_relative += 1
                target_len += 1

        if target_len > tgt_size:
            raise PatchError("BPS: команда превышает целевой размер")

    if target_len != tgt_size:
        raise PatchError(
            f"BPS: итоговый размер {target_len} != ожидаемый {tgt_size}"
        )
    result = bytes(target)
    if zlib.crc32(result) != target_crc:
        raise PatchError("BPS: CRC32 результата не совпадает с ожидаемым")
    return result


def ips_create(source: bytes, target: bytes) -> bytes:
    """Создаёт IPS-патч, преобразующий source в target.

    Изменённые блоки режутся на чанки ≤ 0xFFFF. Серии из 8+ одинаковых байт
    кодируются RLE-записью. IPS не умеет уменьшать ROM: если target короче
    source, хвост не трогается.
    """
    records = bytearray()
    tgt_len = len(target)
    t = 0

    while t < tgt_len:
        if t < len(source) and source[t] == target[t]:
            t += 1
            continue
        j = t
        while j < tgt_len and (j >= len(source) or source[j] != target[j]):
            j += 1
        _emit_ips_record(records, t, target[t:j])
        t = j

    return IPS_MAGIC + bytes(records) + IPS_EOF


def _emit_ips_record(out: bytearray, offset: int, data: bytes) -> None:
    while data:
        if offset > IPS_MAX_OFFSET:
            raise PatchError(
                f"IPS: запись на смещении {offset:#x} выходит за адресацию 16MB"
            )
        chunk_len = min(len(data), IPS_MAX_LEN)
        chunk = data[:chunk_len]
        if offset + len(chunk) > IPS_MAX_OFFSET + 1:
            raise PatchError(
                f"IPS: запись на смещении {offset:#x} выходит за адресацию 16MB"
            )
        repeated = len(chunk) >= IPS_RLE_MIN_RUN and len(set(chunk)) == 1
        if repeated:
            out.extend(_ips_write_u24(offset))
            out.extend((0).to_bytes(2, "big"))
            out.extend(len(chunk).to_bytes(2, "big"))
            out.append(chunk[0])
        else:
            out.extend(_ips_write_u24(offset))
            out.extend(len(chunk).to_bytes(2, "big"))
            out.extend(chunk)
        offset += chunk_len
        data = data[chunk_len:]


def ips_apply(rom: bytes, patch: bytes) -> bytes:
    """Применяет IPS-патч к ROM, расширяя его при необходимости.

    Записи разбираются последовательно; маркер "EOF" проверяется только на
    границе записи, поэтому последовательность байт "EOF" внутри данных
    записи не ломает разбор.
    """
    if not patch.startswith(IPS_MAGIC):
        raise PatchError("IPS: неверная сигнатура (ожидалось PATCH)")

    out = bytearray(rom)
    pos = IPS_HEADER_SIZE
    while True:
        if pos + 3 > len(patch):
            raise PatchError("IPS: не найдена запись за последней позицией")
        if patch[pos:pos + 3] == IPS_EOF:
            break
        if pos + 5 > len(patch):
            raise PatchError("IPS: запись короче минимальной (5 байт)")

        offset = _ips_read_u24(patch, pos)
        size = int.from_bytes(patch[pos + 3:pos + 5], "big")

        if size == 0:
            if pos + 8 > len(patch):
                raise PatchError("IPS: RLE-запись оборвана")
            rle_len = int.from_bytes(patch[pos + 5:pos + 7], "big")
            rle_val = patch[pos + 7]
            if offset + rle_len > IPS_MAX_OFFSET + 1:
                raise PatchError("IPS: RLE выходит за пределы адресации")
            _ips_ensure_size(out, offset + rle_len)
            out[offset:offset + rle_len] = bytes([rle_val]) * rle_len
            pos += 8
        else:
            if pos + 5 + size > len(patch):
                raise PatchError("IPS: данные записи оборваны")
            if offset + size > IPS_MAX_OFFSET + 1:
                raise PatchError("IPS: запись выходит за пределы адресации")
            _ips_ensure_size(out, offset + size)
            out[offset:offset + size] = patch[pos + 5:pos + 5 + size]
            pos += 5 + size

    return bytes(out)


def _ips_ensure_size(out: bytearray, needed: int) -> None:
    if len(out) < needed:
        out.extend(b"\x00" * (needed - len(out)))


def create_patch(source: bytes, target: bytes, fmt: str = "bps") -> bytes:
    """Создаёт патч в заданном формате: 'ips' или 'bps' (по умолчанию bps)."""
    if fmt == "ips":
        return ips_create(source, target)
    if fmt == "bps":
        return bps_create(source, target)
    raise ValueError(f"Неизвестный формат патча: {fmt!r}")


def apply_patch(rom: bytes, patch: bytes) -> bytes:
    """Применяет патч, определяя формат по сигнатуре."""
    if patch.startswith(IPS_MAGIC):
        return ips_apply(rom, patch)
    if patch.startswith(BPS_MAGIC):
        return bps_apply(rom, patch)
    raise PatchError("Не удалось определить формат патча (ожидался IPS или BPS)")
