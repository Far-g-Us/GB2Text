"""FFTA character definitions from LeonarthCG/FFTA_Engine_Hacks"""
# Source: https://github.com/LeonarthCG/FFTA_Engine_Hacks/blob/master/Text/Text%20Character%20Definitions.event
#
# This is the printable (non-kanji) range of the FFTA event-text charmap —
# the system used by the LZSS-compressed dialogue strings (0x32 marker).
# Verified to match CHARMAP_FFTA_MULTI in plugins/gba_fft_advance.py code for code.
#
# Project conventions for display:
# - 0x80E9 ellipsis is shown as a single '…' character
# - 0x80F3-0x80F6 quotes are shown as straight ASCII ' and "
# - 0x810F/0x8110 are '<-' / '->' (arrowheads) per the event definitions
# - 0x8118-0x8122 are full-width 0-9 and '－' (fixed-width range per source)

FFTA_CHARMAP_EVENT = {
    # Numbers (0x80 prefix)
    0x80A6: '0', 0x80A7: '1', 0x80A8: '2', 0x80A9: '3', 0x80AA: '4',
    0x80AB: '5', 0x80AC: '6', 0x80AD: '7', 0x80AE: '8', 0x80AF: '9',
    # Uppercase (0x80 prefix)
    0x80B0: 'A', 0x80B1: 'B', 0x80B2: 'C', 0x80B3: 'D', 0x80B4: 'E',
    0x80B5: 'F', 0x80B6: 'G', 0x80B7: 'H', 0x80B8: 'I', 0x80B9: 'J',
    0x80BA: 'K', 0x80BB: 'L', 0x80BC: 'M', 0x80BD: 'N', 0x80BE: 'O',
    0x80BF: 'P', 0x80C0: 'Q', 0x80C1: 'R', 0x80C2: 'S', 0x80C3: 'T',
    0x80C4: 'U', 0x80C5: 'V', 0x80C6: 'W', 0x80C7: 'X', 0x80C8: 'Y',
    0x80C9: 'Z',
    # Lowercase (0x80 prefix)
    0x80CA: 'a', 0x80CB: 'b', 0x80CC: 'c', 0x80CD: 'd', 0x80CE: 'e',
    0x80CF: 'f', 0x80D0: 'g', 0x80D1: 'h', 0x80D2: 'i', 0x80D3: 'j',
    0x80D4: 'k', 0x80D5: 'l', 0x80D6: 'm', 0x80D7: 'n', 0x80D8: 'o',
    0x80D9: 'p', 0x80DA: 'q', 0x80DB: 'r', 0x80DC: 's', 0x80DD: 't',
    0x80DE: 'u', 0x80DF: 'v', 0x80E0: 'w', 0x80E1: 'x', 0x80E2: 'y',
    0x80E3: 'z',
    # Punctuation (0x80 prefix)
    0x80E4: '.',
    0x80E9: '…', 0x80EA: '?', 0x80EB: '!',
    0x80EC: ',', 0x80ED: '·', 0x80EE: ':', 0x80EF: '_',
    0x80F1: '/', 0x80F2: '~',
    0x80F3: "'", 0x80F4: "'",  # straight single quotes (font renders ' ')
    0x80F5: '"', 0x80F6: '"',  # straight double quotes
    0x80F7: '(', 0x80F8: ')',
    0x80FD: '+', 0x80FE: '-', 0x80FF: '±',  # plus-minus
    # Symbols (0x81 prefix)
    0x8100: '×',
    0x8101: '=', 0x8102: '<', 0x8103: '>',
    0x8104: '∞',
    0x8105: '♂', 0x8106: '♀',
    0x8107: '%', 0x8108: '&', 0x8109: '*',
    0x810A: '※', 0x810B: '─', 0x810C: '│',
    0x810D: '▲', 0x810E: '▼',
    0x810F: '←', 0x8110: '→',
    0x8111: '○', 0x8112: '△', 0x8113: '□', 0x8114: '■',
    0x8115: '♪', 0x8116: ';', 0x8117: '◎',
    # Full-width numbers 0-9 and '－' (fixed-width range, 0x81 prefix)
    0x8118: '０', 0x8119: '１', 0x811A: '２', 0x811B: '３', 0x811C: '４',
    0x811D: '５', 0x811E: '６', 0x811F: '７', 0x8120: '８', 0x8121: '９',
    0x8122: '－',
}
