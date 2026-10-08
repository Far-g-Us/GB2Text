"""Замена картинки, собранной из тайлов: запечённый в графику текст.

Заголовок титульного экрана — это не шрифт, а картинка: у неё нет индекса
«тайл N = символ N», поэтому подстановкой символов она не переводится вовсе.
Единственный способ локализовать — заменить сами тайлы. Автоматически найти
такой блок не вышло (`scripts_roms/baked_text_probe.py`: критерий по виду
пикселей не отличает логотип от любой графики), и это не недостаток, а
свойство задачи: адрес ассетов лежит в ARM-коде, а не в данных. Поэтому здесь
блок задаёт ПОЛЬЗОВАТЕЛЬ — это надёжно и не требует дизассемблера.

Контракт, который делает операцию безопасной:
- `preview` ничего не пишет в ROM — только PNG (число тайлов кладётся в
  метаданные PNG, иначе apply отверг бы превью как «не того размера»);
- `apply` даёт ПОБАЙТОВОЕ ТОЖДЕСТВО: неизменённая картинка возвращается ровно
  теми же байтами. Для этого сэмплер пикселей сверяется с палитрой PNG: штатный
  `image_to_grids` необратим — игнорирует масштаб превью и возвращает 60 чужих
  пикселей из 64, из-за чего круговой путь менял байты при неизменной картинке.
  Замер: шрифт `0x1FF2F0` копии FireRed — 0 изменённых байт из 512, и то же для
  120 выбранных участков; обещается также то, что проверяется тестами, — после
  записи каждый тайл декодируется в картинку из PNG, а повторный apply ничего
  не меняет;
- для 4bpp ЛЮБЫЕ 32 байта декодируются как валидный тайл — это свойство
  формата, а не дырка. Именно поэтому нужен гард по виду пикселей: число
  одинаковых соседей откалибровано замером (шрифт — медиана 76, ARM-код — 19,
  данные — 17; порог 60), неграфический блок отвергается с подсказкой `--force`,
  которым гард снимается осознанно. Раньше блок просто задавался пользователем;
- для ШРИФТА с halves-упаковкой инструмент неприменим: два 2bpp-половинки в
  одном 32-байтном тайле не являются плоским тайлом. Такие блоки — это
  `core/font_tiles.py`, а не этот модуль; сам модуль на 4bpp с halves не
  претендует.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from core.font_tiles import TILE_BYTES, decode_tile, encode_tile, stride_for_bpp

TILE_ORDER = {1: 0, 2: 1, 4: 2}
SUPPORTED_BPP = (1, 2, 4)
PREVIEW_MAX_TILES = 4096


class PictureError(Exception):
    """Блок тайлов задан неверно или картинка не помещается."""


def _stride(bpp: int) -> int:
    if bpp not in TILE_ORDER:
        raise PictureError(
            f'Неподдерживаемый bpp={bpp!r} (ожидается 1, 2 или 4)')
    return stride_for_bpp(bpp)


def _check_block(data: bytes, offset: int, bpp: int, count: int) -> int:
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise PictureError(f'count должен быть положительным int, получено {count!r}')
    stride = _stride(bpp)
    if isinstance(offset, bool) or not isinstance(offset, int):
        raise PictureError(f'offset должен быть int, получено {offset!r}')
    need = offset + count * stride
    if offset < 0:
        raise PictureError(f'Смещение отрицательное: {offset}')
    if need > len(data):
        raise PictureError(
            f'Блок не помещается: нужно {need} байт, в ROM {len(data)} '
            f'(смещение {offset:#x}, {count} тайлов по {bpp}bpp)')
    return stride


def _grids(data: bytes, offset: int, stride: int, bpp: int,
           count: int) -> list[list[list[int]]]:
    return [decode_tile(data[offset + i * stride:offset + (i + 1) * stride], bpp)
            for i in range(count)]


# Порог «похоже на графику»: медианное число пар СОСЕДНИХ одинаковых пикселей
# в тайле (максимум 112 = 7*8 горизонтальных + 7*8 вертикальных пар). Метрика
# измеряет ПЛОСКОСТЬ блока, а не «графичность» как таковую: ровная заливка даёт
# 112 и гард её пропускает. Противовес — обязательный --force, потому что
# неверный --offset, попавший в паддинг, иначе записался бы молча.
#
# Калибровано замером на копии Pokemon FireRed (по 24 тайла на блок):
#   настоящий шрифт  — медиана 76, минимум 68
#   ARM-код (0x1000)  — медиана 19, максимум 56
#   данные (0x8000)   — медиана 17, максимум 34
# Зазор УЗКИЙ: худший образец кода — 56, порог 60, лучший шрифт — 68. Поэтому
# это отсечка «похоже на шум», а не доказательство графики: число намеренно
# оставлено на 4 выше худшего кода и на 8 ниже лучшего шрифта.
GRAPHICS_NEIGHBOUR_MEDIAN = 60


def neighbour_equal_count(blob: bytes, offset: int, bpp: int, count: int,
                          stride: int) -> list[int]:
    """Число пар соседних одинаковых пикселей в каждом тайле.

    Сигнал выбран потому, что он не зависит от bpp и от того, какие номера
    палитр игра использует: у букв и картинок много плоских участков (фон,
    перекладины), у кода и данных — почти нет.
    """
    out: list[int] = []
    for i in range(count):
        grid = decode_tile(blob[offset + i * stride:offset + (i + 1) * stride],
                           bpp)
        equal = 0
        for r in range(8):
            for c in range(7):
                if grid[r][c] == grid[r][c + 1]:
                    equal += 1
        for r in range(7):
            for c in range(8):
                if grid[r][c] == grid[r + 1][c]:
                    equal += 1
        out.append(equal)
    return out


def looks_like_graphics(blob: bytes, offset: int, bpp: int, count: int,
                        stride: int) -> tuple[bool, dict]:
    """Похож ли блок на тайловую графику, а не на код/данные.

    Для 4bpp круговой путь через сэмплер БЕЗ ПОТЕРЬ для любых 32 байт — это
    свойство формата, а не дырка: 4bpp несёт 16 уровней на два байта, поэтому
    «прочитать» можно что угодно. Значит отличить графику от кода можно только
    по виду пикселей, и единственный способ сделать это честно — откалибровать
    порог замером на настоящей графике и на настоящем коде (см. константу).
    """
    values = neighbour_equal_count(blob, offset, bpp, count, stride)
    if not values:
        return False, {'median': 0, 'min': 0, 'max': 0}
    ordered = sorted(values)
    median = ordered[len(ordered) // 2]
    ok = median >= GRAPHICS_NEIGHBOUR_MEDIAN
    return ok, {'median': median, 'min': ordered[0], 'max': ordered[-1],
                'threshold': GRAPHICS_NEIGHBOUR_MEDIAN}


def preview_to_png(data: bytes | bytearray, offset: int, bpp: int, count: int,
                   path: str | Path | None = None):
    """PNG с текущим содержимым блока. ROM не изменяется.

    Число тайлов пишется в метаданные PNG (`gb2text_tiles`), иначе round-trip
    невозможен: `font_grids_to_image` паддит канвас, и картинка из 16 тайлов
    читается обратно как 256 — ровно тот случай, когда apply отверг бы PNG как
    «не того размера», хотя превью делал он сам.
    """
    from core.font_tiles import font_grids_to_image

    if count > PREVIEW_MAX_TILES:
        # `font_grids_to_image` зовёт putpixel по 1024 раз на тайл: 4096 тайлов
        # — это уже десятки секунд и сотни мегабайт картинки. Рендерить весь
        # 32-МеБ ROM одним PNG бессмысленно и так нельзя.
        raise PictureError(
            f'Слишком много тайлов для превью: {count} (максимум '
            f'{PREVIEW_MAX_TILES}). Рендер одного тайла стоит 1024 вызова '
            f'putpixel, поэтому весь ROM одним превью не отрисовать — режьте '
            f'блок на части')
    blob = bytes(data)
    stride = _check_block(blob, offset, bpp, count)
    grids = _grids(blob, offset, stride, bpp, count)
    image = font_grids_to_image(grids, columns=min(count, 16), scale=4)
    if path is not None:
        from PIL.PngImagePlugin import PngInfo

        info = PngInfo()
        info.add_text('gb2text_tiles', str(count))
        info.add_text('gb2text_bpp', str(bpp))
        info.add_text('gb2text_scale', '4')
        image.save(str(path), pnginfo=info)
    return image


def _gray_to_index(palette: list[int] | None, bpp: int) -> dict[int, int]:
    """Карта «уровень серого -> номер палитры» для значений 0..(2**bpp-1).

    Нужна, потому что `image_to_grids` оказался НЕОБРАТИМЫМ: он игнорирует
    масштаб превью и на `scale=4` возвращал вместо 64 пикселей 60 чужих (измерено
    на синтетике: значения «залипали» по колонкам, т.е. читались не те пиксели).
    Свой сэмплер берёт палитру прямо из PNG и сопоставляет её обратно, поэтому
    круговой путь не теряет ни одного значения 0..15.
    """
    levels = 2 ** bpp
    gray = [i * 17 for i in range(levels)]
    if palette is None:
        return {g: i for i, g in enumerate(gray)}
    map_: dict[int, int] = {}
    for index in range(min(len(palette) // 3, levels)):
        red, green, blue = palette[index * 3:index * 3 + 3]
        if red == green == blue:
            map_.setdefault(red, index)
    return map_


def _check_gray_palette(img, bpp: int) -> None:
    """Палитра превью обязана быть серой рамкой `i * 17`.

    Иначе `lookup.get(color, index)` отдаёт индекс 0..255, который `encode_tile`
    отвергает, и наружу уходит сырое `ValueError` вместо `PictureError` — то есть
    в api-слое это становится `INTERNAL` (и HTTP 500 на сервере) вместо внятного
    отказа. Проверять дешевле, чем ловить исключение в другом слое.
    """
    if img.mode != 'P':
        return
    palette = img.getpalette()
    if palette is None:
        raise PictureError('mode P без палитры — так сохраняет не PIL')
    for index in range(min(len(palette) // 3, 2 ** bpp)):
        red, green, blue = palette[index * 3:index * 3 + 3]
        expected = index * 17
        if (red, green, blue) != (expected, expected, expected):
            raise PictureError(
                f'Палитра превью не серая рамка (индекс {index}: '
                f'{(red, green, blue)}, ожидалось {expected},{expected},'
                f'{expected}) — картинку перепалитровали, тайлы придётся '
                f'перекодировать вручную')


def _nearest_level(value, bpp: int) -> int:
    """Номер палитры для пикселя, который НЕ в режиме P.

    Модуль пишет уровень серого как `i * 17` (`core/font_tiles.font_grids_to_image`),
    поэтому рампа здесь ровно такая же. Ближайший уровень, а не `0`: иначе
    редактор, сохранивший превью в RGB/L/RGBA (обычный сценарий — все они теряют
    tEXt-метаданные и режим P), тихо превращал бы картинку в ноль, и apply
    записал бы это как обычную правку.
    """
    levels = 2 ** bpp
    if isinstance(value, (tuple, list)):
        if len(value) < 3:
            raise PictureError(
                f'Пиксель {value!r} не похож ни на RGB, ни на серый оттенок')
        level = (int(value[0]) + int(value[1]) + int(value[2])) // 3
    else:
        level = int(value)
    best = min(range(levels), key=lambda i: abs(i * 17 - level))
    return best


def _sample_grids(img, bpp: int, scale: int) -> list[list[list[int]]]:
    """PNG (уже открытый) -> список сеток 8x8 по пикселям палитры, без потерь.

    Принимает ОТКРЫТЫЙ Image намеренно: второй `Image.open` того же пути означал
    бы TOCTOU — между проверкой метаданных и чтением пикселей файл можно
    подменить, и apply записал бы постороннюю картинку.
    """
    _check_gray_palette(img, bpp)
    width, height = img.size
    palette = img.getpalette()
    # mode P: img.load() отдаёт ИНДЕКСЫ палитры, а не цвета.
    indexed = img.mode == 'P'
    pixels = img.load()
    step = 8 * scale
    per_row = max(1, width // step)
    lookup = _gray_to_index(palette, bpp)
    top = 2 ** bpp - 1
    grids: list[list[list[int]]] = []
    for row in range(height // step):
        for col in range(per_row):
            grid = []
            for r in range(8):
                line = []
                for c in range(8):
                    value = pixels[col * step + c * scale,
                                   row * step + r * scale]
                    if indexed:
                        index = int(value)
                        color = 0
                        if palette is not None and index * 3 < len(palette):
                            color = palette[index * 3]
                        line.append(min(lookup.get(color, index), top))
                    else:
                        line.append(_nearest_level(value, bpp))
                grid.append(line)
            grids.append(grid)
    return grids


def read_png(path: str | Path, bpp: int, count: int) -> list[list[list[int]]]:
    """Картинка из PNG + проверка, что она сделана для этого блока.

    Метаданные `gb2text_tiles`/`gb2text_scale`/`gb2text_bpp` обязательны. Без них
    превью неизвестного происхождения читалось бы как «любая картинка», и apply
    молча залил бы ею произвольный участок ROM. Отдельно проверяется ГЕОМЕТРИЯ:
    потерянный `gb2text_scale` (редактор съел tEXt-чанк) приводил к тому, что
    сэмплер читал левый верхний угол каждого тайла как отдельный тайл, и в ROM
    писался мусор — при успешном отчёте.
    """
    source = Path(path)
    if not source.is_file():
        raise PictureError(f'PNG не найден: {source}')
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover — зависимость опциональна
        raise PictureError(
            'Для apply нужен Pillow (pip install Pillow)') from exc
    # Файл открывается ОДИН раз и держится открытым до конца: иначе между
    # проверкой метаданных и чтением пикселей его можно подменить (TOCTOU).
    with Image.open(source) as img:
        text = img.text or {}
        declared = text.get('gb2text_tiles')
        scale_text = text.get('gb2text_scale')
        declared_bpp = text.get('gb2text_bpp')
        mode = img.mode
        size = img.size
        return _validate_and_sample(img, declared, scale_text,
                                    declared_bpp, mode, size, bpp, count)


def _validate_and_sample(img, declared, scale_text, declared_bpp, mode,
                         size, bpp: int, count: int) -> list[list[list[int]]]:
    """Проверки превью + чтение пикселей из уже открытого Image."""
    if declared is None or not str(declared).isdigit() or int(declared) < 1:
        raise PictureError(
            'В PNG нет метки gb2text_tiles (или она не положительное число) — '
            'это не превью из `picture preview`. Правьте картинку поверх превью, '
            'а не открывайте посторонний файл')
    if scale_text is None or not str(scale_text).isdigit() or int(scale_text) < 1:
        raise PictureError(
            'В PNG нет метки gb2text_scale (или она не число) — без неё сэмплер '
            'не знает, во сколько раз превью увеличено, и возьмёт не те пиксели')
    if declared_bpp is None or not str(declared_bpp).isdigit():
        raise PictureError(
            'В PNG нет метки gb2text_bpp — перекодирование тайлов молча испортило '
            'бы картинку')
    declared_scale = int(scale_text)
    if int(declared_bpp) != bpp:
        raise PictureError(
            f'PNG сделан для {declared_bpp} bpp, а запрошено {bpp} — '
            f'перекодирование тайлов молча испортило бы картинку')
    if int(declared) != count:
        raise PictureError(
            f'PNG сделан для блока из {declared} тайлов, а запрошено {count} — '
            f'это превью другого участка ROM')
    if mode not in ('P', 'L', 'RGB', 'RGBA'):
        raise PictureError(f'Неподдерживаемый режим PNG: {mode}')
    # Геометрия: превью рисуется колонками по 16 тайлов и паддится канвасом.
    # Несовпадение ловит и потерянный масштаб, и обрезанное редактором превью.
    columns = min(int(declared), 16)
    rows = -(-int(declared) // columns)
    expected = (columns * 8 * declared_scale, rows * 8 * declared_scale)
    if size != expected:
        raise PictureError(
            f'Геометрия PNG {size[0]}x{size[1]} не совпадает с превью '
            f'{count} тайлов при масштабе {declared_scale} ({expected[0]}x'
            f'{expected[1]}) — картинку обрезали или отмасштабировали')
    grids = _sample_grids(img, bpp, declared_scale)
    if len(grids) < count:
        raise PictureError(
            f'В PNG {len(grids)} тайлов, а в блоке {count} — не хватает')
    if len(grids) > count:
        # Канвас превью паддится, поэтому лишние тайлы — норма. Ровно столько,
        # сколько просил блок, и ни байтом больше.
        grids = grids[:count]
    return grids


def apply_picture(data: bytes | bytearray, offset: int, bpp: int, count: int,
                  grids: list[list[list[int]]], force: bool = False
                  ) -> tuple[bytes, dict]:
    """Новый ROM с заменённым блоком. Байты вне блока не меняются.

    Круговой путь БЕЗ ПОТЕРЬ (проверено на 120 участках копии FireRed и на
    синтетике): сэмплер пикселей необратим, поэтому он написан здесь и сверяется
    с палитрой PNG; после него `encode(decode(x)) == x` для любого плоского тайла,
    и неизменённая картинка не меняет ни одного байта.

    Гард «это вообще графика?» для 4bpp нужен именно потому, что круговой путь
    безупречен для ЛЮБЫХ 32 байт — отличить графику от кода иначе нечем.
    Отказ не тихий и не вечный: `force=True` сознательно снимает его, когда
    пользователь знает, что блок верный.

    Возвращает (новый ROM, статистика): `changed_bytes`, `changed_tiles`,
    `identical_pixels`, `looks_like_graphics`, `graphics_score`.
    """
    blob = bytes(data)
    stride = _check_block(blob, offset, bpp, count)
    if len(grids) != count:
        raise PictureError(
            f'Тайлов в картинке {len(grids)}, в блоке {count}')
    graphics, look = looks_like_graphics(blob, offset, bpp, count, stride)
    if not graphics and not force:
        raise PictureError(
            f'Блок по {offset:#x} не похож на графику: медиана «одинаковых '
            f'соседей» {look["median"]} при пороге {look["threshold"]} '
            f'(код/данные). Если вы уверены — повторите с --force')
    out = bytearray(blob)
    changed_tiles = 0
    for index, grid in enumerate(grids):
        pos = offset + index * stride
        encoded = bytes(encode_tile(grid, bpp))
        if len(encoded) != stride:
            raise PictureError(
                f'Тайл {index}: закодирован в {len(encoded)} байт, '
                f'ожидалось {stride}')
        if encoded == blob[pos:pos + stride]:
            continue
        out[pos:pos + stride] = encoded
        changed_tiles += 1
    result = bytes(out)
    identical = all(
        decode_tile(result[offset + i * stride:offset + (i + 1) * stride], bpp)
        == grids[i] for i in range(count))
    if not identical:
        raise PictureError(
            'После записи картинка не совпала с запрошенной — запись отменена')
    # Отдельно — совпала ли картинка с ИСХОДНОЙ. Это разные вещи: apply имеет
    # право изменить то, что пользователь нарисовал, но если PNG был превью того
    # же участка, несовпадение означает потерю на пути через PNG. Пользователь
    # обязан это увидеть, а не обнаружить в игре.
    end = offset + count * stride
    unchanged = sum(
        1 for i in range(count)
        if decode_tile(result[offset + i * stride:offset + (i + 1) * stride],
                       bpp)
        == decode_tile(blob[offset + i * stride:offset + (i + 1) * stride],
                       bpp))
    changed_bytes = sum(
        1 for pos in range(offset, end) if blob[pos] != result[pos])
    return result, {
        'changed_bytes': changed_bytes,
        'changed_tiles': changed_tiles,
        'identical_pixels': True,
        'unchanged_tiles': unchanged,
        'total_tiles': count,
        'looks_like_graphics': graphics,
        'graphics_score': look,
    }


def save_atomic(target: str | Path, payload: bytes) -> str:
    """Запись файла атомарно: mkstemp + `os.replace`, как у inject.

    Имя tmp-файла НЕ предсказуемо: заранее подложенный на `dest + '.tmp'`
    симлинк иначе провёл бы `write_bytes` и записал в произвольный файл.
    """
    dest = Path(target)
    handle, tmp_name = tempfile.mkstemp(
        dir=str(dest.parent), prefix=dest.name + '.', suffix='.tmp')
    try:
        with os.fdopen(handle, 'wb') as stream:
            stream.write(payload)
        os.replace(tmp_name, dest)
    except OSError as exc:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise PictureError(f'Не удалось записать {dest}: {exc}') from exc
    return str(dest)


__all__ = [
    'TILE_BYTES',
    'PictureError',
    'apply_picture',
    'preview_to_png',
    'read_png',
    'save_atomic',
]
