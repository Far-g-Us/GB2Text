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
Plugin for Final Fantasy V Advance (GBA)

Game codes: BZ5E (USA), BZ5J (Japan), BZ5P (Europe)

Text pointer table at 0x36DD64, 24036 records, relative offsets from 0x36DD54.
Each record ends where the next one begins (variable-length text).
0x0D is the end-of-line marker.

Source: https://www.ff6hacking.com/ff5wiki/index.php?title=FFVA_ROM_map

This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging
import re

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.ff5_advance')

_UNKNOWN_TOKEN_RE = re.compile(r'\[[0-9A-F]{2,6}\]')


def _strip_unknown_tokens(text: str) -> str:
    """Removes hex tokens of unknown bytes ('[B7]', '[C28E]', etc.)."""
    return _UNKNOWN_TOKEN_RE.sub('', text)

# Text pointer table constants (from the FF5 Hacking Wiki ROM map)
FF5_TEXT_POINTER_TABLE = 0x36DD64
FF5_TEXT_POINTER_BASE = 0x36DD54
FF5_TEXT_POINTER_COUNT = 24036

# Maximum reasonable text record length (characters, not bytes of an oversized scan).
# Giant segments (0x100000+ bytes) are pointers running into ROM graphics/padding
# (areas 0x73XXXX-0x77XXXX etc.) where the 0x0D terminator is absent for hundreds of KiB.
FF5_MAX_SEGMENT_LEN = 0x4000

# FF5 Advance character table - BZ5E (USA)
# Source: FF5 Hacking Wiki / DataCrystal
CHARMAP_FF5: dict[int, str] = {
    # Single-byte (0x00-0x77)
    0x00: ' ', 0x01: 'e', 0x02: 't', 0x03: 'a', 0x04: 'o', 0x05: 'n',
    0x06: 's', 0x07: 'r', 0x08: 'i', 0x09: 'h', 0x0A: 'l', 0x0B: '.',
    0x0C: 'd', 0x0E: 'u', 0x0F: 'm', 0x10: 'g', 0x11: 'y', 0x12: 'c',
    0x13: 'w', 0x14: 'f', 0x15: 'p', 0x16: '!', 0x17: 'b', 0x18: ':',
    0x19: 'k', 0x1A: "'", 0x1B: ',', 0x1C: 'v', 0x1D: 'T', 0x1E: 'I',
    0x1F: 'S', 0x20: 'C', 0x21: 'G', 0x22: 'W', 0x23: '?', 0x24: 'F',
    0x25: 'L', 0x26: '-', 0x27: 'B', 0x28: 'P', 0x29: 'M', 0x2A: 'K',
    0x2B: 'H', 0x2C: 'A', 0x2D: 'D', 0x2E: 'E', 0x2F: 'R', 0x30: 'x',
    0x31: 'O', 0x32: 'Y', 0x33: 'N', 0x34: 'z', 0x35: 'j', 0x36: 'q',
    0x37: '1', 0x38: 'V', 0x39: 'U', 0x3A: '2', 0x3B: 'X', 0x3C: 'J',
    0x3D: '*', 0x3E: '"', 0x3F: '0', 0x40: '3', 0x41: 'Z', 0x42: '4',
    0x43: '5', 0x44: 'Q', 0x45: '6', 0x46: '8', 0x47: '7', 0x48: '%',
    0x49: '9', 0x4A: '+', 0x4B: ';', 0x4C: '/', 0x4E: '&', 0x4F: '(',
    0x50: ')', 0x51: '=', 0x52: '\u30FB', 0x53: '\u2025', 0x54: '\u3002',
    0x55: '\u30FC', 0x5B: '\u2191', 0x5C: '\u2192', 0x5D: '\u2193',
    0x5E: '\u2190', 0x6C: '\u266A',
    # Multi-byte kanji - BZ5E (0xC2XX-0xD2XX)
    0xC280: '\u30D7', 0xC281: '\u3050', 0xC282: '\u3079', 0xC283: '\u30E5',
    0xC284: '\u3056', 0xC285: '\u9B54', 0xC286: '3', 0xC287: '\u69D8',
    0xC288: '\u30DD', 0xC289: '\u30AD', 0xC28A: '4', 0xC28B: '\u30A3',
    0xC28C: '\u30EF', 0xC28D: '\u9054', 0xC28E: '\u5927', 0xC28F: '\u30B4',
    0xC290: '\u738B', 0xC291: '\u30AA', 0xC292: '\u98DB', 0xC293: '\u30C1',
    0xC294: '\u57CE', 0xC295: '\u58EB', 0xC296: '\u524D', 0xC297: '\u306C',
    0xC298: '\u30CF', 0xC299: '\u7269', 0xC29A: '\u754C', 0xC29B: '\u4E16',
    0xC29C: '\u3071', 0xC29D: '\u3083', 0xC29E: 'P', 0xC29F: '\u7AF9',
    0xC2A0: '\u4F55', 0xC2A1: '\u30D9', 0xC2A2: '\u8005', 0xC2A3: '\u9593',
    0xC2A4: '\u30D1', 0xC2A5: '\u5C01', 0xC2A6: '5', 0xC2A7: '\u5165',
    0xC2A8: '\u672C', 0xC2A9: '\u51FA', 0xC2AA: '\u898B', 0xC2AB: '\u4EBA',
    0xC2AC: '\u6C17', 0xC2AD: '\u968E', 0xC2AE: '\u30DB', 0xC2AF: '\u7121',
    0xC2B0: '\u8A00', 0xC2B1: '\u624B', 0xC2B2: '\u79C1', 0xC2B3: '\u5370',
    0xC2B4: '\u30B2', 0xC2B5: '\u30CD', 0xC2B6: '\u8239', 0xC2B7: '\u30BB',
    0xC2B8: 'B', 0xC2B9: '\u77F3', 0xC2BA: '\u6226', 0xC2BB: '\u4E00',
    0xC2BC: '\u4FC2', 0xC2BD: '\u30BE', 0xC2BE: '\u5730', 0xC2BF: '\u30CE',
    0xC380: '\u5B88', 0xC381: '\u98A8', 0xC382: '\u6642', 0xC383: '\u30D4',
    0xC384: '\u6D77', 0xC385: '\u601D', 0xC386: '\u3065', 0xC387: 'H',
    0xC388: '\u5206', 0xC389: '\u4E8B', 0xC38A: '\u5143', 0xC38B: '\u623B',
    0xC38C: '\u4E0B', 0xC38D: '\u5854', 0xC38E: '\u6C34', 0xC38F: '\u4ECA',
    0xC390: '\u4E2D', 0xC391: '\u751F', 0xC392: '\u30D2', 0xC393: '\u795E',
    0xC394: '\u6240', 0xC395: '\u6765', 0xC396: '\u5FC3', 0xC397: '\u4E0A',
    0xC398: '\u6CD5', 0xC399: '\u7236', 0xC39A: '\u30BA', 0xC39B: '\u30BD',
    0xC39C: '\u5012', 0xC39D: '\u706B', 0xC39E: '\u30A6', 0xC39F: '\u6301',
    0xC3A0: '\u76EE', 0xC3A1: '\u68EE', 0xC3A2: '\u6BBF', 0xC3A3: 'M',
    0xC3A4: '\u6211', 0xC3A5: '\u753A', 0xC3A6: '\u5E74', 0xC3A7: '\u4F7F',
    0xC3A8: '\u5B50', 0xC3A9: '\u5175', 0xC3AA: '\u5834', 0xC3AB: '6',
    0xC3AC: '\u9053', 0xC3AD: '\u4F53', 0xC3AE: '8', 0xC3AF: '\u5909',
    0xC3B0: '\u5F37', 0xC3B1: '\u4E08', 0xC3B2: '\u592B', 0xC3B3: '\u967D',
    0xC3B4: '\u5F53', 0xC3B5: '\u5E30', 0xC3B6: '\u6B21', 0xC3B7: '\u30D8',
    0xC3B8: '\u6700', 0xC3B9: '\u7A7A', 0xC3BA: '\u52A9', 0xC3BB: '\u5973',
    0xC3BC: '\u5C4B', 0xC3BD: '\u780E', 0xC3BE: '\u6B7B', 0xC3BF: '\u805E',
    0xC480: '\u77E5', 0xC481: '\u5F8C', 0xC482: '\u60AA', 0xC483: '\u66F8',
    0xC484: '\u30FB', 0xC485: '\u7802', 0xC486: '\u81E3', 0xC487: '\u30CC',
    0xC488: '\u5F85', 0xC489: '\u52D5', 0xC48A: '\u6751', 0xC48B: '\u73FE',
    0xC48C: '\u53E4', 0xC48D: '\u30C4', 0xC48E: '\u8FBC', 0xC48F: '\u6563',
    0xC490: '\u90AA', 0xC491: '\u9ED2', 0xC492: '\u8CCA', 0xC493: '\u65B9',
    0xC494: '\u81EA', 0xC495: '\u4EE3', 0xC496: '\u6B66', 0xC497: '\u5668',
    0xC498: '\u5317', 0xC499: '\u7720', 0xC49A: ':', 0xC49B: '7',
    0xC49C: '\u6B62', 0xC49D: '\u7A7F', 0xC49E: '\u767A', 0xC49F: '/',
    0xC4A0: '\u958B', 0xC4A1: '\u6025', 0xC4A2: '\u65E9', 0xC4A3: '\u9928',
    0xC4A4: '\u5CF6', 0xC4A5: '\u30DA', 0xC4A6: '\u65C5', 0xC4A7: '\u5FA9',
    0xC4A8: '\u4E0D', 0xC4A9: '\u4E4E', 0xC4AA: '\u4F5C', 0xC4AB: '\u6D88',
    0xC4AC: '\u56F3', 0xC4AD: '\u843D', 0xC4AE: '\u983C', 0xC4AF: '\u6EC5',
    0xC4B0: '\u9632', 0xC4B1: '\u5F31', 0xC4B2: '\u56DE', 0xC4B3: '\u5168',
    0xC4B4: '\u571F', 0xC4B5: '\u99C4', 0xC4B6: '\u89E3', 0xC4B7: '\u90E8',
    0xC4B8: '\u9577', 0xC4B9: '\u6D41', 0xC4BA: '\u4F1D', 0xC4BB: '\u72ED',
    0xC4BC: '\u4E57', 0xC4BD: '\u5408', 0xC4BE: '\u8349', 0xC4BF: '\u307D',
    0xC580: '\u7ACB', 0xC581: '\u53D6', 0xC582: '\u547D', 0xC583: '\u8FD1',
    0xC584: 'A', 0xC585: '\u6D1E', 0xC586: '\u6F20', 0xC587: '\u5EA6',
    0xC588: '\u6575', 0xC589: '\u535A', 0xC58A: '\u677F', 0xC58B: '\u30F4',
    0xC58C: 'L', 0xC58D: '9', 0xC58E: '\u8A70', 0xC58F: '\u95C7',
    0xC590: '\u65E5', 0xC591: '\u8A71', 0xC592: '%', 0xC593: '\u8D77',
    0xC594: '\u8EAB', 0xC595: '\u547C', 0xC596: '\u6A5F', 0xC597: '\u68B0',
    0xC598: '\u6B8B', 0xC599: '\u6B4C', 0xC59A: '\u653B', 0xC59B: '\u7DD2',
    0xC59C: '\u8A18', 0xC59D: '\u5371', 0xC59E: '\u767D', 0xC59F: '\u5FC5',
    0xC5A0: '\u4EF2', 0xC5A1: '\u5F15', 0xC5A2: '\u3077', 0xC5A3: '\u708E',
    0xC5A4: '\u5316', 0xC5A5: '\u61B6', 0xC5A6: '\u8AAC', 0xC5A7: '\u899A',
    0xC5A8: '\u5B8C', 0xC5A9: '\u5149', 0xC5AA: '\u5177', 0xC5AB: '\u7B2C',
    0xC5AC: '\u3074', 0xC5AD: '\u5916', 0xC5AE: '\u7206', 0xC5AF: '\u907A',
    0xC5B0: '\u967A', 0xC5B1: '\u8DE1', 0xC5B2: '\u904B', 0xC5B3: '\u6CB3',
    0xC5B4: '\u8247', 0xC5B5: '\u5C71', 0xC5B6: '\u4F1A', 0xC5B7: '\u5F35',
    0xC5B8: '\u6EF0', 0xC5B9: '\u8001', 0xC5BA: '\u6483', 0xC5BB: '\u5931',
    0xC5BC: '\u5148', 0xC5BD: '\u5411', 0xC5BE: '\u5DE2', 0xC5BF: '\u6728',
    0xC680: 'E', 0xC681: 'T', 0xC682: '\u4F11', 0xC683: '\u5BC2',
    0xC684: '\u59EC', 0xC685: '\u540C', 0xC686: '\u6D3B', 0xC687: '\u5897',
    0xC688: '\u63A2', 0xC689: '\u660E', 0xC68A: '\u5E95', 0xC68B: '\u58C1',
    0xC68C: '\u6628', 0xC68D: '\u62FE', 0xC68E: '\u59D0', 0xC68F: '\u8535',
    0xC690: '\u8B70', 0xC691: '\u6697', 0xC692: '\u9589', 0xC693: '\u59FF',
    0xC694: '\u540D', 0xC695: '\u7528', 0xC696: '\u5099', 0xC697: '\u95D8',
    0xC698: '\u98F2', 0xC699: '\u897F', 0xC69A: '\u56FD', 0xC69B: '\u5074',
    0xC69C: '\u9580', 0xC69D: '\u7D76', 0xC69E: '\u904E', 0xC69F: '\u7834',
    0xC6A0: '\u4E88', 0xC6A1: 'R', 0xC6A2: '.', 0xC6A3: '\u914D',
    0xC6A4: '\u5438', 0xC6A5: '\u7136', 0xC6A6: '\u9078', 0xC6A7: '\u78BA',
    0xC6A8: '\u6771', 0xC6A9: '\u6050', 0xC6AA: '\u4FE1', 0xC6AB: '\u62BC',
    0xC6AC: '\u5C11', 0xC6AD: '\u5263', 0xC6AE: '\u5C0F', 0xC6AF: '\u6BCD',
    0xC6B0: '\u4ED8', 0xC6B1: '\u6708', 0xC6B2: '\u5F79', 0xC6B3: '\u4F5C',
    0xC6B4: '\u58CA', 0xC6B5: '\u4EA1', 0xC6B6: '\u8C37', 0xC6B7: '\u68DA',
    0xC6B8: '\u793C', 0xC6B9: '\u7D9A', 0xC6BA: '\u901A', 0xC6BB: '\u8CB8',
    0xC6BC: '\u52C7', 0xC6BD: '\u9152', 0xC6BE: '\u98DF', 0xC6BF: '\u59CB',
    0xC780: '\u5357', 0xC781: '\u7378', 0xC782: '\u4E09', 0xC783: '\u6247',
    0xC784: '\u6797', 0xC785: '\u4F9B', 0xC787: '\u30E4', 0xC788: '\u6C7A',
    0xC789: '\u80FD', 0xC78A: '\u7A81', 0xC78B: '\u4EE5', 0xC78C: '\u9023',
    0xC78D: '\u9707', 0xC78E: '\u9858', 0xC78F: '\u5144',
    0xC790: '\u597D', 0xC791: '\u50B7', 0xC792: '\u5B89', 0xC793: '\u5E45',
    0xC794: '\u5BBF', 0xC795: '\u7F6E', 0xC796: '\u88AD', 0xC797: '\u5B9D',
    0xC798: '\u7BB1', 0xC799: '\u9762', 0xC79A: '\u756A', 0xC79B: '\u5BB6',
    0xC79C: '\u4F4F', 0xC79D: '\u5BFE', 0xC79E: '\u96C6', 0xC79F: '\u53EC',
    0xC7A0: '\u559C', 0xC7A1: '\u8ABF', 0xC7A2: '\u51C4', 0xC7A3: '\u5B66',
    0xC7A4: '\u6668', 0xC7A5: '\u7406', 0xC7A6: '\u8CEA', 0xC7A7: '\u9B42',
    0xC7A8: '-', 0xC7A9: ' ', 0xC7AA: '\u8FFD', 0xC7AB: '\u6559',
    0xC7AC: '\u6253', 0xC7AD: '\u76F4', 0xC7AE: '\u52DD', 0xC7AF: '\u629C',
    0xC7B0: '\u6C42', 0xC7B1: '\u521D', 0xC7B2: '\u7740', 0xC7B3: '\u8CB4',
    0xC7B4: '\u6F5C', 0xC7B5: '\u7A76', 0xC7B6: '\u9045', 0xC7B7: '\u75C5',
    0xC7B8: '\u5207', 0xC7B9: '\u885B', 0xC7BA: 'C', 0xC7BB: 'X',
    0xC7BC: '\u611F', 0xC7BD: '\u88C5', 0xC7BE: '\u982D', 0xC7BF: '\u591A',
    0xC880: '\u610F', 0xC881: '\u7262', 0xC882: '\u8FD4', 0xC883: '\u9CE9',
    0xC884: '\u9055', 0xC885: '\u53D7', 0xC886: '\u9752', 0xC887: '\u8CA0',
    0xC888: '\u5BC4', 0xC889: '\u8131', 0xC88A: '\u6C88', 0xC88B: '\u9AD8',
    0xC88C: '\u5FD8', 0xC88D: '\u518D', 0xC88E: '\u6355', 0xC88F: '\u679C',
    0xC890: '\u8AAD', 0xC891: '\u6398', 0xC892: '\u6210', 0xC893: '\u5F62',
    0xC894: '\u7832', 0xC895: '\u653E', 0xC896: '\u6280', 0xC897: '\u5B58',
    0xC898: '\u307A', 0xC899: '\u5225', 0xC89A: '\u5B57', 0xC89B: '\u75DB',
    0xC89C: '\u4EFB', 0xC89D: '\u8A66', 0xC89E: '\u8E8D', 0xC89F: '\u5DE6',
    0xC8A0: '\u6570', 0xC8A1: '\u64CD', 0xC8A2: '\u5893', 0xC8A3: '\u6545',
    0xC8A4: '\u5EFA', 0xC8A5: '\u6BD2', 0xC8A6: '\u91CD', 0xC8A7: '\u58F2',
    0xC8A8: '\u9060', 0xC8A9: '\u9678', 0xC8AA: '\u7A74', 0xC8AB: '\u5ACC',
    0xC8AC: '\u5EF6', 0xC8AD: '\u5E83', 0xC8AE: '\u6D6E', 0xC8AF: '\u6587',
    0xC8B0: '\u53F3', 0xC8B1: '\u5965', 0xC8B2: '\u9060', 0xC8B3: '\u53BB',
    0xC8B4: '\u4E8C', 0xC8B5: '\u72B6', 0xC8B6: '\u7D50', 0xC8B7: '\u58F0',
    0xC8B8: '\u9664', 0xC8B9: '\u5ECA', 0xC8BA: 'S', 0xC8BB: '+',
    0xC8BC: '\u4ED6', 0xC8BD: '\u96A0', 0xC8BE: '\u91D1', 0xC8BF: '\u80B2',
    0xC980: '\u9003', 0xC981: '\u671B', 0xC982: '\u88CF', 0xC983: '\u7D87',
    0xC984: '\u9E97', 0xC985: '\u72D9', 0xC986: '\u6BB5', 0xC987: '\u96E2',
    0xC988: '\u983C', 0xC989: '\u6CBB', 0xC98A: '\u5631', 0xC98B: '\u9811',
    0xC98C: '\u6E21', 0xC98D: '\u5358', 0xC98E: '\u534A', 0xC98F: '\u73CD',
    0xC990: '\u79D8', 0xC991: '\u771F', 0xC992: '\u639B', 0xC993: '\u7570',
    0xC994: '\u5185', 0xC995: '\u606F', 0xC996: '\u56E3', 0xC997: '\u53E3',
    0xC999: '\u5C64', 0xC99A: 'K', 0xC99B: 'O', 0xC99C: 'V',
    0xC99D: '\u5229', 0xC99E: '\u8FBA', 0xC99F: '\u5272',
    0xC9A0: '\u8D70', 0xC9A1: '\u76F8', 0xC9A2: '\u9759', 0xC9A3: '\u602A',
    0xC9A4: '\u5F90', 0xC9A5: '\u89AA', 0xC9A6: '\u6050', 0xC9A7: '\u6804',
    0xC9A8: '\u56F0', 0xC9A9: '\u500D', 0xC9AA: '\u5F71', 0xC9AB: '\u5305',
    0xC9AC: '\u8853', 0xC9AD: '\u5473', 0xC9AE: '\u5546', 0xC9AF: '\u82E6',
    0xC9B0: '\u5171', 0xC9B1: '\u512A', 0xC9B2: '\u5339', 0xC9B3: '\u53CD',
    0xC9B4: '\u6E96', 0xC9B5: '\u71C3', 0xC9B6: '\u683C', 0xC9B7: '\u5BC6',
    0xC9B8: '\u904A', 0xC9B9: '\u8AB2', 0xC9BA: '\u7D04', 0xC9BB: '\u675F',
    0xC9BC: '\u5922', 0xC9BD: '\u53F0', 0xC9BE: '\u5FF5', 0xC9BF: '\u8A9E',
    0xCA80: '\u871C', 0xCA81: '\u697C', 0xCA82: '\u5B9F', 0xCA83: '\u6975',
    0xCA84: '\u5728', 0xCA85: '\u5DE8', 0xCA88: '\u5EAB', 0xCA89: '\u30E6',
    0xCA8A: '\u30F2', 0xCA8B: '\u51B7', 0xCA8C: '\u5FA1', 0xCA8D: '\u964D',
    0xCA8E: '\u55AA', 0xCA8F: '\u8DB3',
    0xCA90: '\u7684', 0xCA91: '(', 0xCA92: ')', 0xCA93: '\u5EA7',
    0xCA94: '\u6DF1', 0xCA95: '\u9032', 0xCA96: '\u5024', 0xCA97: '\u79FB',
    0xCA98: '\u4E45', 0xCA99: '\u591C', 0xCA9A: '\u7F8E', 0xCA9B: '\u60B2',
    0xCA9C: '\u672B', 0xCA9D: '\u8A31', 0xCA9E: '\u7814', 0xCA9F: '\u66AE',
    0xCAA0: '\u6B63', 0xCAA1: '\u5C3D', 0xCAA2: '\u6BBA', 0xCAA3: '\u7C21',
    0xCAA4: '\u5192', 0xCAA5: '\u97F3', 0xCAA6: '\u6D3E', 0xCAA7: '\u8A69',
    0xCAA8: '\u9020', 0xCAA9: '\u5FD9', 0xCAAA: '\u63FA', 0xCAAB: '\u7D42',
    0xCAAC: '\u57CB', 0xCAAD: '\u5E7B', 0xCAAE: '\u7387', 0xCAAF: '\u53CB',
    0xCAB0: '\u5374', 0xCAB1: '\u5BA4', 0xCAB2: '\u679D', 0xCAB3: '\u7D99',
    0xCAB4: '\u4FDD', 0xCAB5: '\u7D20', 0xCAB6: '\u6674', 0xCAB7: '\u5468',
    0xCAB8: '\u4FEE', 0xCAB9: '\u5F97', 0xCABA: '\u52B9', 0xCABB: '\u614B',
    0xCABC: '\u6CE2', 0xCABE: '\u5948',
    0xCB80: 'G', 0xCB81: 'I', 0xCB82: 'a', 0xCB83: 'b', 0xCB84: 'c',
    0xCB85: 'd', 0xCB86: 'e', 0xCB87: 'f', 0xCB88: 'g', 0xCB89: 'h',
    0xCB8A: 'i', 0xCB8B: 'j', 0xCB8C: 'k', 0xCB8D: 'l', 0xCB8E: 'm',
    0xCB8F: 'n', 0xCB90: 'o', 0xCB91: 'p', 0xCB92: 'q', 0xCB93: 'r',
    0xCB94: 's', 0xCB95: 't', 0xCB96: 'u', 0xCB97: 'v', 0xCB98: 'w',
    0xCB99: 'x', 0xCB9A: 'y', 0xCB9B: 'z',
    0xCB9E: '\u7279', 0xCB9F: '\u8235',
    0xCBA0: '\u9189', 0xCBA1: '\u7948', 0xCBA2: '\u5E0C', 0xCBA3: '\u58C4',
    0xCBA4: '\u6388', 0xCBA5: '\u5217', 0xCBA6: '\u753B', 0xCBA7: '\u66FF',
    0xCBA8: '\u793A', 0xCBA9: '\u5E7D', 0xCBAA: '\u970F', 0xCBAB: '\u4F8B',
    0xCBAC: '\u7247', 0xCBAD: '\u8981', 0xCBAE: '\u5BD2', 0xCBAF: '\u7537',
    0xCBB0: '\u82B1', 0xCBB1: '\u978B', 0xCBB2: '\u72FC', 0xCBB3: '\u66B4',
    0xCBB4: '\u8D64', 0xCBB5: '\u5BB4', 0xCBB6: '\u75B2', 0xCBB7: '\u60C5',
    0xCBB8: '\u88C2', 0xCBB9: '\u6012', 0xCBBA: '\u7B11', 0xCBBB: '\u5145',
    0xCBBC: '\u6255', 0xCBBD: '\u5B6B', 0xCBBE: '\u63C3', 0xCBBF: '\u6696',
    0xCC80: '\u541F', 0xCC81: '\u5B99', 0xCC82: '\u6A4B', 0xCC83: '\u9014',
    0xCC84: '\u8A2D', 0xCC85: '\u821E', 0xCC86: '\u90F7', 0xCC87: '\u5883',
    0xCC88: '\u7533', 0xCC89: '\u8A8D', 0xCC8A: '\u5831', 0xCC8B: '\u6027',
    0xCC8C: '\u52A0', 0xCC8D: '\u65B0', 0xCC8E: '\u6075', 0xCC8F: '\u4E0E',
    0xCC90: '\u82F1', 0xCC92: '\u5E73', 0xCC93: '\u548C', 0xCC94: '\u5E97',
    0xCC95: '\u6B32', 0xCC96: '\u512A', 0xCC97: '\u5B64', 0xCC98: '\u6C38',
    0xCC99: '\u50CF', 0xCC9A: '\u5FDC', 0xCC9B: '\u5460', 0xCC9C: '\u65AD',
    0xCC9D: '\u6311', 0xCC9E: '\u6D25',
    0xCCA2: '\u814E', 0xCCA3: '\u3062', 0xCCA4: '\u3041', 0xCCA5: '\u3043',
    0xCCA6: '\u3045', 0xCCA7: '\u3047', 0xCCA8: '\u3049', 0xCCA9: '\u30E8',
    0xCCAA: '\u30C2', 0xCCAB: '\u30C5', 0xCCAC: 'D', 0xCCAD: 'J',
    0xCCAE: 'N', 0xCCAF: 'Q',
    0xCCB0: 'U', 0xCCB1: 'W', 0xCCB2: 'Y', 0xCCB3: 'Z',
    0xCCB5: '\u2025', 0xCCB6: '\u2015',
    0xCCB7: '[DPAD]', 0xCCB8: '[DPAD_UP]', 0xCCB9: '[DPAD_RIGHT]',
    0xCCBA: '[DPAD_DOWN]', 0xCCBB: '[DPAD_LEFT]',
    0xCCBC: '\u2191', 0xCCBD: '\u2192', 0xCCBE: '\u2193', 0xCCBF: '\u2190',
    0xCD80: '\u8056', 0xCD81: '\u8F2A', 0xCD82: '\u6CC9', 0xCD83: '\u9802',
    0xCD84: '\u80C6', 0xCD85: '\u76D7', 0xCD86: '\u9A5A', 0xCD87: '\u5F1F',
    0xCD88: '\u7A3C', 0xCD89: '\u696D', 0xCD8A: '\u58F6', 0xCD8B: '\u666E',
    0xCD8C: '\u8868', 0xCD8D: '\u8DEF', 0xCD8E: '\u4E21', 0xCD8F: '\u6CCA',
    0xCD90: '\u6F02', 0xCD91: '\u4E7E', 0xCD92: '\u7167', 0xCD93: '\u7372',
    0xCD94: '\u8D8A', 0xCD95: '\u623F', 0xCD96: '\u963B', 0xCD97: '\u6E05',
    0xCD98: '\u8C4A', 0xCD99: '\u5197', 0xCD9A: '\u8AC7', 0xCD9B: '\u70B9',
    0xCD9C: '\u9ED8', 0xCD9D: '\u4F59', 0xCD9E: '\u697D', 0xCD9F: '\u533B',
    0xCDA0: '\u820C', 0xCDA1: '\u8A73', 0xCDA2: '\u5E7C', 0xCDA3: '\u8584',
    0xCDA4: '\u7981', 0xCDA5: '\u5439', 0xCDA6: '\u968A', 0xCDA7: '\u6B69',
    0xCDA8: '\u6B20', 0xCDA9: '\u614C', 0xCDAA: '\u8010', 0xCDAB: '\u69CB',
    0xCDAC: '\u6557', 0xCDAD: '\u7F8A', 0xCDAE: '\u59BB', 0xCDAF: '\u604B',
    0xCDB0: '\u8D08', 0xCDB1: '\u66F2', 0xCDB2: '\u5BA2', 0xCDB3: '\u6839',
    0xCDB4: '\u6CA2', 0xCDB5: '\u5A18', 0xCDB6: '\u65CF', 0xCDB7: '\u8272',
    0xCDB8: '\u983C', 0xCDB9: '\u5E2B', 0xCDBA: '\u501F', 0xCDBB: '\u5E78',
    0xCDBC: '\u5E8A', 0xCDBD: '\u6539', 0xCDBE: '\u636E', 0xCDBF: '\u81C6',
    0xCE80: '\u611B', 0xCE81: '\u51F6', 0xCE82: '\u9F3B', 0xCE83: '\u8ECD',
    0xCE84: '\u8A33', 0xCE85: '\u4F3C', 0xCE86: '\u6368', 0xCE87: '\u6CE3',
    0xCE88: '\u5C0E', 0xCE89: '\u9006', 0xCE8A: '\u56F2', 0xCE8B: '\u518C',
    0xCE8C: '\u6162', 0xCE8D: '\u8A17', 0xCE8E: '\u8A03', 0xCE8F: '\u80F8',
    0xCE90: '\u9001', 0xCE92: '\u9854', 0xCE93: '\u8A2A', 0xCE94: '\u8FF7',
    0xCE95: '\u89E6', 0xCE96: '\u53EF', 0xCE97: '\u767B', 0xCE98: '\u6A2A',
    0xCE99: '\u6D9C', 0xCE9A: '\u96E8', 0xCE9B: '\u7CBE', 0xCE9C: '\u539F',
    0xCE9D: '\u56E0', 0xCE9E: '\u5F0F', 0xCE9F: '\u77AC',
    0xCEA0: '\u7A2E', 0xCEA1: '\u985E', 0xCEA2: '\u8C61', 0xCEA3: '\u6CC1',
    0xCEA4: '\u6CB9', 0xCEA5: '\u6E9C', 0xCEA8: '\u4E71', 0xCEA9: '\u586B',
    0xCEAA: '\u61FC', 0xCEAB: '\u7532',
    0xCEB7: '\u6307', 0xCEB8: '\u96F7', 0xCEB9: '\u95A2', 0xCEBA: '\u4FC2',
    0xCEBB: '\u5D29', 0xCEBC: '\u8B1D', 0xCEBD: '\u90FD', 0xCEBE: '\u7D10',
    0xCEBF: '\u6E29',
    0xCF80: '\u796D', 0xCF81: '\u7D44', 0xCF82: '\u5360', 0xCF83: '\u9818',
    0xCF84: '\u901F', 0xCF85: '\u7DD1', 0xCF86: '\u7559', 0xCF87: '\u80CC',
    0xCF88: '\u8150', 0xCF89: '\u51DC', 0xCF8A: '\u6E7E', 0xCF8B: '\u670D',
    0xCF8C: '\u6069', 0xCF8D: '\u6E2F', 0xCF8E: '\u9B5A', 0xCF8F: '\u4E89',
    0xCF90: '\u54B2', 0xCF91: '\u7D2B', 0xCF92: '\u51AC', 0xCF93: '\u89D2',
    0xCF94: '\u8336', 0xCF95: '\u50E5', 0xCF96: '\u6C37', 0xCF97: '\u6C11',
    0xCF98: '\u8870', 0xCF99: '\u63A1', 0xCF9A: '\u8A08', 0xCF9B: '\u6BCE',
    0xCF9C: '\u60B9', 0xCF9D: '\u5D0E', 0xCF9E: '\u906D', 0xCF9F: '\u6BD4',
    0xCFA0: '\u5FDC', 0xCFA1: '\u57FA', 0xCFA2: '\u5DEE', 0xCFA3: '\u8CC7',
    0xCFA4: '\u554F', 0xCFA5: '\u984C', 0xCFA6: '\u53C2', 0xCFA7: '\u5BB9',
    0xCFA8: '\u8A67', 0xCFA9: '\u65A9', 0xCFAA: '\u98FC', 0xCFAB: '\u7A3B',
    0xCFAC: '\u8E74', 0xCFAD: '\u72E9', 0xCFAE: '\u8449', 0xCFAF: '\u9234',
    0xCFB0: '\u8352', 0xCFB1: '\u4E92', 0xCFB2: '\u6574', 0xCFB3: '\u4FBF',
    0xCFB4: '\u7B87', 0xCFB5: '\u679A', 0xCFB6: '\u640D', 0xCFB7: '\u9971',
    0xCFB8: '\u505C', 0xCFB9: '\u7591', 0xCFBA: '\u4F8D', 0xCFBB: '\u9A0E',
    0xCFBC: '\u58C1', 0xCFBD: '\u54C1', 0xCFBE: '\u713C', 0xCFBF: '\u5609',
    0xD080: '\u5589', 0xD081: '\u67D3', 0xD082: '\u5C40', 0xD083: '\u5BF8',
    0xD084: '\u76AE', 0xD085: '\u8089', 0xD086: '\u9A1F', 0xD087: '\u731B',
    0xD088: '\u7531', 0xD08A: '\u5805', 0xD08B: '\u6E56', 0xD08C: '\u77B3',
    0xD08D: '\u7741', 0xD08E: '\u7565', 0xD08F: '\u529F',
    0xD090: '\u62C5', 0xD091: '\u52E2', 0xD092: '\u631E', 0xD093: '\u6D78',
    0xD094: '\u6C5A', 0xD095: '\u8F9B', 0xD096: '\u62B1', 0xD097: '\u9000',
    0xD098: '\u7D61', 0xD099: '\u81A0', 0xD09A: '\u7247', 0xD09B: '\u7272',
    0xD09C: '\u4EA4', 0xD09D: '\u7FA4', 0xD09E: '\u6C60', 0xD09F: '\u7F1A',
    0xD0A0: '\u6B6F', 0xD0A1: '\u5DDD', 0xD0A2: '\u7D39', 0xD0A3: '\u4ECB',
    0xD0A4: '\u61E3', 0xD0A5: '\u7F6A', 0xD0A6: '\u611A', 0xD0A7: '\u584A',
    0xD0A8: '\u6E90', 0xD0A9: '\u7D19', 0xD0AA: '\u559C', 0xD0AB: '\u6CEA',
    0xD0AC: '\u8F1D', 0xD0AD: '\u9694', 0xD0AE: '\u63DB', 0xD0AF: '\u59D4',
    0xD0B0: '\u80A1', 0xD0B1: '\u4EE4', 0xD0B2: '\u6D01', 0xD0B3: '\u8986',
    0xD0B4: '\u7956', 0xD0B5: '\u91CE', 0xD0B6: '\u90CE', 0xD0B7: '\u82E5',
    0xD0B8: '\u64A5', 0xD0B9: '\u5343', 0xD0BA: '\u4E26', 0xD0BB: '\u4FA1',
    0xD0BC: '\u8840', 0xD0BD: '\u67AF', 0xD0BE: '\u7530', 0xD0BF: '\u820D',
    0xD180: '\u5618', 0xD181: '\u9A12', 0xD182: '\u5E79', 0xD183: '\u8AC7',
    0xD184: '\u4E95', 0xD185: '\u6238', 0xD186: '\u6599', 0xD187: '\u60A3',
    0xD188: '\u652F', 0xD189: '\u6551', 0xD18A: '\u7403', 0xD18B: '\u4FA1',
    0xD18C: '\u7D1A', 0xD18D: '\u7126', 0xD18E: '\u4F4E', 0xD18F: '\u5999',
    0xD190: '\u6EBA', 0xD191: '\u6B6A', 0xD192: '\u544A', 0xD193: '\u5674',
    0xD194: '\u8A3C', 0xD195: '\u9806', 0xD196: '\u53E9', 0xD197: '\u96D5',
    0xD198: '\u4FB5', 0xD199: '\u6392', 0xD19A: '\u672A', 0xD19B: '\u5B9A',
    0xD19C: '\u7DF4', 0xD19D: '\u91DD', 0xD19E: '\u6CE8', 0xD19F: '\u690D',
    0xD1A0: '\u60F1', 0xD1A1: '\u4FCA', 0xD1A2: '\u654F', 0xD1A3: '\u7D0B',
    0xD1A4: '\u84EC', 0xD1A5: '\u4F34', 0xD1A6: '\u96C4', 0xD1A7: '\u6028',
    0xD1A8: '\u60A0', 0xD1A9: '\u56FA', 0xD1AA: '\u643A', 0xD1AB: '\u92FC',
    0xD1AC: '\u9244', 0xD1AD: '\u822A', 0xD1AE: '\u969B', 0xD1AF: '\u8CB7',
    0xD1B0: '\u67E5', 0xD1B1: '\u89B3', 0xD1B2: '\u97FF', 0xD1B3: '\u67F1',
    0xD1B4: '\u6DF7', 0xD1B5: '\u8CDE', 0xD1B6: '\u62E1', 0xD1B7: '\u96FB',
    0xD1B8: '\u5727', 0xD1B9: '\u6607', 0xD1BA: '\u9583', 0xD1BB: '\u5C04',
    0xD1BC: '\u4E3B', 0xD1BD: '\u5B87', 0xD1BE: '\u5247', 0xD1BF: '\u6B74',
    0xD280: '\u53F2', 0xD281: '\u7B49', 0xD282: '\u514D', 0xD283: '\u7686',
    0xD284: '\u7FFC', 0xD285: '\u4E86', 0xD286: '\u596A', 0xD287: '\u25CB',
    0xD288: '\u00D7', 0xD289: '\u0394', 0xD28A: '\u25A1', 0xD28B: '\u6F22',
    0xD28C: '\u7E41', 0xD28D: '\u9650', 0xD28E: '\u8FEB', 0xD28F: '\u6DA3',
    0xD290: '\u5009', 0xD291: '\u7D0D', 0xD292: '\u7389',
}

# FF5 Advance control codes (from DataCrystal)
FF5_CONTROL_CODES: dict[int, str] = {
    0x0D: '[END]',
    0xC28E: '[LINEBREAK]', 0xC392: '[LINEBREAK_MENU]',
    0xC2A5: '[PIC_BARTZ]', 0xC2A6: '[PIC_LENNA]', 0xC2A7: '[PIC_GALUF]',
    0xC2A8: '[PIC_FARIS]', 0xC2A9: '[PIC_KRILE]', 0xC2AA: '[PIC_BOKO]',
    0xC2AB: '[PIC_CID]', 0xC2AC: '[PIC_MID]', 0xC2AD: '[PIC_DORGANN]',
    0xC2AE: '[PIC_KELGER]', 0xC2AF: '[PIC_XEZAT]', 0xC2B0: '[PIC_KING_TYCOON]',
    0xC2B1: '[PIC_GILGAMESH]', 0xC2B2: '[PIC_EXDEATH]',
    0xC2B3: '[BARTZ_NAME]',
    0xC2B4: '[DIALOGUE_ITEM]', 0xC2B5: '[DIALOGUE_GIL]',
    0xC2B6: '[DIALOGUE_ABILITY]',
    0xC2B7: '[CLEAN_BOX]', 0xC2B8: '[AUTO_RESPONSE]',
    0xC2B9: '[PAUSE1]', 0xC2BA: '[PAUSE2]', 0xC2BB: '[PAUSE3]',
    0xC2BC: '[PAUSE4]', 0xC2BD: '[PAUSE5]',
    0xC380: '[BATTLE_VAR1]', 0xC381: '[BATTLE_VAR2]', 0xC382: '[BATTLE_VAR3]',
    0xC383: '[BATTLE_ITEM]', 0xC384: '[JOB_ABILITY]', 0xC385: '[MAGIC_ABILITY]',
    0xC386: '[CHAR_NAME]', 0xC391: '[REMOVE_PIC]',
}

FF5_TERMINATORS = [0x0D]

FF5_GAME_CODES = ['BZ5E', 'BZ5J', 'BZ5P']


class FF5TextDecoder:
    """FF5 Advance text decoder with multi-byte control code support"""

    _TOKEN_RE = re.compile(r'\[([0-9A-F]{2}(?:[0-9A-F]{2})*)\]|\[([A-Z_][A-Z0-9_]*)\]|(.)')

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap
        # Single-byte (keys < 0x100): priority - shorter mapping
        self.rev_single: dict[str, int] = {}
        # Multi-byte (keys >= 0x100): fallback for characters without a single-byte variant
        self.rev_multi: dict[str, tuple[int, int]] = {}
        for code, ch in charmap.items():
            if code < 0x100:
                if ch not in self.rev_single:
                    self.rev_single[ch] = code
            elif code not in FF5_CONTROL_CODES:
                if ch not in self.rev_multi:
                    self.rev_multi[ch] = (code >> 8, code & 0xFF)
        # Control codes -> bytes (terminator 0x0D - single byte, the rest - 2 bytes)
        # Keys without brackets '[PIC_BARTZ]' -> 'PIC_BARTZ' - matches the capture regex.
        self.rev_control: dict[str, bytes] = {}
        for code, name in FF5_CONTROL_CODES.items():
            self.rev_control[name[1:-1]] = bytes([code]) if code < 0x100 else code.to_bytes(2, 'big')

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        i = start
        end = min(start + length, len(data))

        while i < end:
            byte = data[i]

            if byte in FF5_TERMINATORS:
                break

            if 0xC2 <= byte <= 0xD2 and i + 1 < end and data[i + 1] not in FF5_TERMINATORS:
                second = data[i + 1]
                code = (byte << 8) | second
                if code in FF5_CONTROL_CODES:
                    result.append(FF5_CONTROL_CODES[code])
                elif code in self.charmap:
                    result.append(self.charmap[code])
                else:
                    result.append(f'[{byte:02X}{second:02X}]')
                i += 2
                continue

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


class FF5AdvancePlugin(GamePlugin):
    """Plugin for Final Fantasy V Advance (GBA)"""

    def __init__(self):
        super().__init__()
        self._decoder = FF5TextDecoder(CHARMAP_FF5)

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(FF5_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_pointer_size(self, rom: GameBoyROM) -> int:
        return 4

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Extract FF5 Advance text segments via the pointer table"""
        logger.info("Извлечение текстовых сегментов для Final Fantasy V Advance")

        segments: list[dict] = []

        table_end = FF5_TEXT_POINTER_TABLE + FF5_TEXT_POINTER_COUNT * 4
        if table_end > len(rom.data):
            logger.warning(f"Таблица указателей выходит за конец ROM ({len(rom.data):#x})")
            return segments

        for i in range(FF5_TEXT_POINTER_COUNT):
            ptr_offset = FF5_TEXT_POINTER_TABLE + i * 4
            raw = int.from_bytes(rom.data[ptr_offset:ptr_offset + 4], 'little')
            text_offset = FF5_TEXT_POINTER_BASE + raw

            if text_offset >= len(rom.data):
                continue

            text_start = text_offset
            text_end = text_start
            # Bound the terminator scan: pointers in the
            # data/padding area can point to a 0x0D megabytes away,
            # and without a limit each such segment would scan the rest of the ROM.
            while text_end < len(rom.data) and rom.data[text_end] not in FF5_TERMINATORS:
                text_end += 1
                if text_end - text_start >= FF5_MAX_SEGMENT_LEN:
                    break
            text_end += 1

            text_len = text_end - text_start
            if text_len < 2 or text_len > FF5_MAX_SEGMENT_LEN:
                continue

            decoded = self._decoder.decode(rom.data, text_start, text_len)
            if not decoded or all(c in ' \t\n' for c in decoded):
                continue

            # Junk tail segments: pointers run into data/padding areas,
            # where the decoder produces long strings of [XX] tokens. Filter out records:
            #   - with 2+ hex tokens (valid text contains at most one leading,
            #     e.g. '[8E][PIC_GALUF]'; binary data yields dozens of tokens);
            #   - where clean text is less than 30% of the length (lone tokens like '[56]').
            clean_len = len(_strip_unknown_tokens(decoded))
            if len(_UNKNOWN_TOKEN_RE.findall(decoded)) >= 2:
                continue
            if clean_len / len(decoded) < 0.3:
                continue

            segments.append({
                'name': f'ff5_text_{i}',
                'start': text_start,
                'end': text_end,
                'decoder': self._decoder,
                'compression': None,
                'charmap': CHARMAP_FF5,
                'terminators': FF5_TERMINATORS,
                'pad_byte': 0x00,
                'original_text': decoded,
                'pointer_offset': ptr_offset,
                'pointer_value': raw,
            })

        logger.info(f"Извлечено {len(segments)} текстовых записей из таблицы указателей")
        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        return FF5_TERMINATORS

    def get_compression_handler(self, segment_name: str):
        return None
