#!/usr/bin/env python3


# Author: Pedro Freire
# Jan 2025
# GNU General Public License
# https://github.com/pfre/speccy-conv


import argparse
import os
import struct
import re


# Reference: https://docs.python.org/3.0/library/codecs.html#standard-encodings
CHARSET_UNICODE_FILE = "utf_8_sig"
CHARSET_UNICODE_CHAR = "utf_8"  # Same as CHARSET_UNICODE_FILE unless CHARSET_UNICODE_FILE == "utf_8_sig"

SOFT_EOF_BYTE = b"\x1A";  # Inline CP/M EOF marker
SINCLAIR_BASIC_LINE_IS_VARIABLE   = 0x4000   # If a line number has this value or bigger, it is actually the start of a Variable defition
SINCLAIR_BASIC_NUMBER_LENGTH      = 5        # 5 bytes with int/float representation of a number
SINCLAIR_BASIC_NUMBER_MARKER      = b'\x0E'  # Prefix to 5 bytes with int/float representation of a number
SINCLAIR_BASIC_TAPE_HEADER_MARKER = b'\x00'  # Leading byte on header blocks of files saved on tape by Sinclair BASIC
SINCLAIR_BASIC_TAPE_DATA_MARKER   = b'\xFF'  # Leading byte on data blocks of files saved on tape by Sinclair BASIC
    # Reference: https://problemkaputt.de/zxdocs.htm#spectrumcassette


# Dictionary to translate ZX Spectrum 128K, +2 or +3 encoding, into Unicode.
# User Defined Graphics (UDG) are converted to 🅰, 🅱, 🅲, ... so that
# reverse translation is possible.
#
# Note that dual-byte sequences (INK, PAPER, etc.) are not translated.
# https://en.wikipedia.org/wiki/ZX_Spectrum_character_set
dict_spectrum128_to_unicode = {
    b'\x06': '\t',  # PRINT comma
    b'\r':   '\n',
    #b'\x17': '\t',  # TAB: commented-out as this is a two-byte sequence
    b'\x5E': '↑',  # U+2191 UPWARDS ARROW
    b'\x60': '£',  # U+00A3 POUND SIGN
    b'\x7F': '©',  # U+00A9 COPYRIGHT SIGN
    #
    # Spectrum Graphics Symbols = Unicode Block Elements
    # https://en.wikipedia.org/wiki/Block_Elements
    b'\x80': '\u2800',  # U+2800 BRAILLE PATTERN BLANK
    b'\x81': '\u259D',  # U+259D QUADRANT UPPER RIGHT
    b'\x82': '\u2598',  # U+2598 QUADRANT UPPER LEFT
    b'\x83': '\u2580',  # U+2580 UPPER HALF BLOCK
    b'\x84': '\u2597',  # U+2597 QUADRANT LOWER RIGHT
    b'\x85': '\u2590',  # U+2590 RIGHT HALF BLOCK
    b'\x86': '\u259A',  # U+259A QUADRANT UPPER LEFT AND LOWER RIGHT
    b'\x87': '\u259C',  # U+259C QUADRANT UPPER LEFT AND UPPER RIGHT AND LOWER RIGHT
    b'\x88': '\u2596',  # U+2596 QUADRANT LOWER LEFT
    b'\x89': '\u259E',  # U+259E QUADRANT UPPER RIGHT AND LOWER LEFT
    b'\x8A': '\u258C',  # U+258C LEFT HALF BLOCK
    b'\x8B': '\u259B',  # U+259B QUADRANT UPPER LEFT AND UPPER RIGHT AND LOWER LEFT
    b'\x8C': '\u2584',  # U+2584 LOWER HALF BLOCK
    b'\x8D': '\u259F',  # U+259F QUADRANT UPPER RIGHT AND LOWER LEFT AND LOWER RIGHT
    b'\x8E': '\u2599',  # U+2599 QUADRANT UPPER LEFT AND LOWER LEFT AND LOWER RIGHT
    b'\x8F': '\u2588',  # U+2588 FULL BLOCK
    #
    # Default appearence of User-Defined Graphics (UDG),
    # using Unicode's Enclosed Alphanumerics
    # https://en.wikipedia.org/wiki/Enclosed_Alphanumerics
    # https://en.wikipedia.org/wiki/Enclosed_Alphanumeric_Supplement
    b'\x90': '🅰',  # U+1F150 NEGATIVE SQUARED LATIN CAPITAL LETTER A
    b'\x91': '🅱',  # U+1F151 NEGATIVE SQUARED LATIN CAPITAL LETTER B
    b'\x92': '🅲',  # U+1F152 NEGATIVE SQUARED LATIN CAPITAL LETTER C
    b'\x93': '🅳',  # U+1F153 NEGATIVE SQUARED LATIN CAPITAL LETTER D
    b'\x94': '🅴',  # U+1F154 NEGATIVE SQUARED LATIN CAPITAL LETTER E
    b'\x95': '🅵',  # U+1F155 NEGATIVE SQUARED LATIN CAPITAL LETTER F
    b'\x96': '🅶',  # U+1F156 NEGATIVE SQUARED LATIN CAPITAL LETTER G
    b'\x97': '🅷',  # U+1F157 NEGATIVE SQUARED LATIN CAPITAL LETTER H
    b'\x98': '🅸',  # U+1F158 NEGATIVE SQUARED LATIN CAPITAL LETTER I
    b'\x99': '🅹',  # U+1F159 NEGATIVE SQUARED LATIN CAPITAL LETTER J
    b'\x9A': '🅺',  # U+1F15A NEGATIVE SQUARED LATIN CAPITAL LETTER K
    b'\x9B': '🅻',  # U+1F15B NEGATIVE SQUARED LATIN CAPITAL LETTER L
    b'\x9C': '🅼',  # U+1F15C NEGATIVE SQUARED LATIN CAPITAL LETTER M
    b'\x9D': '🅽',  # U+1F15D NEGATIVE SQUARED LATIN CAPITAL LETTER N
    b'\x9E': '🅾',  # U+1F15E NEGATIVE SQUARED LATIN CAPITAL LETTER O
    b'\x9F': '🅿',  # U+1F15F NEGATIVE SQUARED LATIN CAPITAL LETTER P
    b'\xA0': '🆀',  # U+1F160 NEGATIVE SQUARED LATIN CAPITAL LETTER Q
    b'\xA1': '🆁',  # U+1F161 NEGATIVE SQUARED LATIN CAPITAL LETTER R
    b'\xA2': '🆂',  # U+1F162 NEGATIVE SQUARED LATIN CAPITAL LETTER S
    #
    # Tokens for Spectrum +3 (should be the same for 128K and +2)
    # Spacing for each token as shown by
    #   10 FOR c = 163 TO 255
    #   20 PRINT c; " ["; CHR$ (c); "]"
    #   30 NEXT c
    b'\xA3': " SPECTRUM ",  # Actually UDG '🆃' on 48K
    b'\xA4': " PLAY ",      # Actually UDG '🆄' on 48K
    b'\xA5': "RND",
    b'\xA6': "INKEY$",
    b'\xA7': "PI",
    b'\xA8': "FN ",
    b'\xA9': "POINT ",
    b'\xAA': "SCREEN$ ",
    b'\xAB': "ATTR ",
    b'\xAC': "AT ",
    b'\xAD': "TAB ",
    b'\xAE': "VAL$ ",
    b'\xAF': "CODE ",
    b'\xB0': "VAL ",
    b'\xB1': "LEN ",
    b'\xB2': "SIN ",
    b'\xB3': "COS ",
    b'\xB4': "TAN ",
    b'\xB5': "ASN ",
    b'\xB6': "ACS ",
    b'\xB7': "ATN ",
    b'\xB8': "LN ",
    b'\xB9': "EXP ",
    b'\xBA': "INT ",
    b'\xBB': "SQR ",
    b'\xBC': "SGN ",
    b'\xBD': "ABS ",
    b'\xBE': "PEEK ",
    b'\xBF': "IN ",
    b'\xC0': "USR ",
    b'\xC1': "STR$ ",
    b'\xC2': "CHR$ ",
    b'\xC3': "NOT ",
    b'\xC4': "BIN ",
    b'\xC5': " OR ",
    b'\xC6': " AND ",
    b'\xC7': "<=",
    b'\xC8': ">=",
    b'\xC9': "<>",
    b'\xCA': " LINE ",
    b'\xCB': " THEN ",
    b'\xCC': " TO ",
    b'\xCD': " STEP ",
    b'\xCE': " DEF FN ",
    b'\xCF': " CAT ",
    b'\xD0': " FORMAT ",
    b'\xD1': " MOVE ",
    b'\xD2': " ERASE ",
    b'\xD3': " OPEN #",
    b'\xD4': " CLOSE #",
    b'\xD5': " MERGE ",
    b'\xD6': " VERIFY ",
    b'\xD7': " BEEP ",
    b'\xD8': " CIRCLE ",
    b'\xD9': " INK ",
    b'\xDA': " PAPER ",
    b'\xDB': " FLASH ",
    b'\xDC': " BRIGHT ",
    b'\xDD': " INVERSE ",
    b'\xDE': " OVER ",
    b'\xDF': " OUT ",
    b'\xE0': " LPRINT ",
    b'\xE1': " LLIST ",
    b'\xE2': " STOP ",
    b'\xE3': " READ ",
    b'\xE4': " DATA ",
    b'\xE5': " RESTORE ",
    b'\xE6': " NEW ",
    b'\xE7': " BORDER ",
    b'\xE8': " CONTINUE ",
    b'\xE9': " DIM ",
    b'\xEA': " REM ",
    b'\xEB': " FOR ",
    b'\xEC': " GO TO ",
    b'\xED': " GO SUB ",
    b'\xEE': " INPUT ",
    b'\xEF': " LOAD ",
    b'\xF0': " LIST ",
    b'\xF1': " LET ",
    b'\xF2': " PAUSE ",
    b'\xF3': " NEXT ",
    b'\xF4': " POKE ",
    b'\xF5': " PRINT ",
    b'\xF6': " PLOT ",
    b'\xF7': " RUN ",
    b'\xF8': " SAVE ",
    b'\xF9': " RANDOMIZE ",
    b'\xFA': " IF ",
    b'\xFB': " CLS ",
    b'\xFC': " DRAW ",
    b'\xFD': " CLEAR ",
    b'\xFE': " RETURN ",
    b'\xFF': " COPY ",
}


# Dictionary to translate ZX Spectrum 16K or 48K encoding, into Unicode.
# User Defined Graphics (UDG) are converted to 🅰, 🅱, 🅲, ... so that
# reverse translation is possible.
#
dict_spectrum48_to_unicode = dict_spectrum128_to_unicode.copy();
dict_spectrum48_to_unicode[b'\xA3'] = '🆃';
dict_spectrum48_to_unicode[b'\xA4'] = '🆄';


# Dictionary to translate Unicode to any ZX Spectrum encoding.
# User Defined Graphics (UDG) are accepted as
#   - Ⓐ, Ⓑ, Ⓒ, ...
#   - ⓐ, ⓑ, ⓒ, ...
#   - 🄰, 🄱, 🄲, ...
#   - 🅐, 🅑, 🅒, ...
#   - 🅰, 🅱, 🅲, ...
#
# https://en.wikipedia.org/wiki/ZX_Spectrum_character_set
dict_unicode_to_spectrum = {
    '\t': b'\x06',  # PRINT comma
    '\n': b'\r',
    '↑':  b'\x5E',  # U+2191 UPWARDS ARROW
    '£':  b'\x60',  # U+00A3 POUND SIGN
    '©':  b'\x7F',  # U+00A9 COPYRIGHT SIGN
    #
    # Spectrum Graphics Symbols = Unicode Block Elements
    # https://en.wikipedia.org/wiki/Block_Elements
    '\u00A0': b'\x80',  # U+00A0 NO-BREAK SPACE
    '\u2002': b'\x80',  # U+2002 EN SPACE
    '\u2003': b'\x80',  # U+2003 EM SPACE
    '\u2800': b'\x80',  # U+2800 BRAILLE PATTERN BLANK
    '\u3000': b'\x80',  # U+2003 IDEOGRAPHIC SPACE
    '\u259D': b'\x81',  # U+259D QUADRANT UPPER RIGHT
    '\u2598': b'\x82',  # U+2598 QUADRANT UPPER LEFT
    '\u2580': b'\x83',  # U+2580 UPPER HALF BLOCK
    '\u2597': b'\x84',  # U+2597 QUADRANT LOWER RIGHT
    '\u2590': b'\x85',  # U+2590 RIGHT HALF BLOCK
    '\u259A': b'\x86',  # U+259A QUADRANT UPPER LEFT AND LOWER RIGHT
    '\u259C': b'\x87',  # U+259C QUADRANT UPPER LEFT AND UPPER RIGHT AND LOWER RIGHT
    '\u2596': b'\x88',  # U+2596 QUADRANT LOWER LEFT
    '\u259E': b'\x89',  # U+259E QUADRANT UPPER RIGHT AND LOWER LEFT
    '\u258C': b'\x8A',  # U+258C LEFT HALF BLOCK
    '\u259B': b'\x8B',  # U+259B QUADRANT UPPER LEFT AND UPPER RIGHT AND LOWER LEFT
    '\u2584': b'\x8C',  # U+2584 LOWER HALF BLOCK
    '\u259F': b'\x8D',  # U+259F QUADRANT UPPER RIGHT AND LOWER LEFT AND LOWER RIGHT
    '\u2599': b'\x8E',  # U+2599 QUADRANT UPPER LEFT AND LOWER LEFT AND LOWER RIGHT
    '\u2588': b'\x8F',  # U+2588 FULL BLOCK
    #
    # Default appearence of User-Defined Graphics (UDG),
    # using Unicode's Enclosed Alphanumerics
    # https://en.wikipedia.org/wiki/Enclosed_Alphanumerics
    # https://en.wikipedia.org/wiki/Enclosed_Alphanumeric_Supplement
    'Ⓐ': b'\x90',  # U+24B6 CIRCLED LATIN CAPITAL LETTER A
    'Ⓑ': b'\x91',  # U+24B7 CIRCLED LATIN CAPITAL LETTER B
    'Ⓒ': b'\x92',  # U+24B8 CIRCLED LATIN CAPITAL LETTER C
    'Ⓓ': b'\x93',  # U+24B9 CIRCLED LATIN CAPITAL LETTER D
    'Ⓔ': b'\x94',  # U+24BA CIRCLED LATIN CAPITAL LETTER E
    'Ⓕ': b'\x95',  # U+24BB CIRCLED LATIN CAPITAL LETTER F
    'Ⓖ': b'\x96',  # U+24BC CIRCLED LATIN CAPITAL LETTER G
    'Ⓗ': b'\x97',  # U+24BD CIRCLED LATIN CAPITAL LETTER H
    'Ⓘ': b'\x98',  # U+24BE CIRCLED LATIN CAPITAL LETTER I
    'Ⓙ': b'\x99',  # U+24BF CIRCLED LATIN CAPITAL LETTER J
    'Ⓚ': b'\x9A',  # U+24C0 CIRCLED LATIN CAPITAL LETTER K
    'Ⓛ': b'\x9B',  # U+24C1 CIRCLED LATIN CAPITAL LETTER L
    'Ⓜ': b'\x9C',  # U+24C2 CIRCLED LATIN CAPITAL LETTER M
    'Ⓝ': b'\x9D',  # U+24C3 CIRCLED LATIN CAPITAL LETTER N
    'Ⓞ': b'\x9E',  # U+24C4 CIRCLED LATIN CAPITAL LETTER O
    'Ⓟ': b'\x9F',  # U+24C5 CIRCLED LATIN CAPITAL LETTER P
    'Ⓠ': b'\xA0',  # U+24C6 CIRCLED LATIN CAPITAL LETTER Q
    'Ⓡ': b'\xA1',  # U+24C7 CIRCLED LATIN CAPITAL LETTER R
    'Ⓢ': b'\xA2',  # U+24C8 CIRCLED LATIN CAPITAL LETTER S
    'Ⓣ': b'\xA3',  # U+24C9 CIRCLED LATIN CAPITAL LETTER T
    'Ⓤ': b'\xA4',  # U+24CA CIRCLED LATIN CAPITAL LETTER U
    #
    'ⓐ': b'\x90',  # U+24D0 CIRCLED LATIN SMALL LETTER A
    'ⓑ': b'\x91',  # U+24D1 CIRCLED LATIN SMALL LETTER B
    'ⓒ': b'\x92',  # U+24D2 CIRCLED LATIN SMALL LETTER C
    'ⓓ': b'\x93',  # U+24D3 CIRCLED LATIN SMALL LETTER D
    'ⓔ': b'\x94',  # U+24D4 CIRCLED LATIN SMALL LETTER E
    'ⓕ': b'\x95',  # U+24D5 CIRCLED LATIN SMALL LETTER F
    'ⓖ': b'\x96',  # U+24D6 CIRCLED LATIN SMALL LETTER G
    'ⓗ': b'\x97',  # U+24D7 CIRCLED LATIN SMALL LETTER H
    'ⓘ': b'\x98',  # U+24D8 CIRCLED LATIN SMALL LETTER I
    'ⓙ': b'\x99',  # U+24D9 CIRCLED LATIN SMALL LETTER J
    'ⓚ': b'\x9A',  # U+24DA CIRCLED LATIN SMALL LETTER K
    'ⓛ': b'\x9B',  # U+24DB CIRCLED LATIN SMALL LETTER L
    'ⓜ': b'\x9C',  # U+24DC CIRCLED LATIN SMALL LETTER M
    'ⓝ': b'\x9D',  # U+24DD CIRCLED LATIN SMALL LETTER N
    'ⓞ': b'\x9E',  # U+24DE CIRCLED LATIN SMALL LETTER O
    'ⓟ': b'\x9F',  # U+24DF CIRCLED LATIN SMALL LETTER P
    'ⓠ': b'\xA0',  # U+24E0 CIRCLED LATIN SMALL LETTER Q
    'ⓡ': b'\xA1',  # U+24E1 CIRCLED LATIN SMALL LETTER R
    'ⓢ': b'\xA2',  # U+24E2 CIRCLED LATIN SMALL LETTER S
    'ⓣ': b'\xA3',  # U+24E3 CIRCLED LATIN SMALL LETTER T
    'ⓤ': b'\xA4',  # U+24E4 CIRCLED LATIN SMALL LETTER U
    #
    '🄰': b'\x90',  # U+1F130 SQUARED LATIN CAPITAL LETTER A
    '🄱': b'\x91',  # U+1F131 SQUARED LATIN CAPITAL LETTER B
    '🄲': b'\x92',  # U+1F132 SQUARED LATIN CAPITAL LETTER C
    '🄳': b'\x93',  # U+1F133 SQUARED LATIN CAPITAL LETTER D
    '🄴': b'\x94',  # U+1F134 SQUARED LATIN CAPITAL LETTER E
    '🄵': b'\x95',  # U+1F135 SQUARED LATIN CAPITAL LETTER F
    '🄶': b'\x96',  # U+1F136 SQUARED LATIN CAPITAL LETTER G
    '🄷': b'\x97',  # U+1F137 SQUARED LATIN CAPITAL LETTER H
    '🄸': b'\x98',  # U+1F138 SQUARED LATIN CAPITAL LETTER I
    '🄹': b'\x99',  # U+1F139 SQUARED LATIN CAPITAL LETTER J
    '🄺': b'\x9A',  # U+1F13A SQUARED LATIN CAPITAL LETTER K
    '🄻': b'\x9B',  # U+1F13B SQUARED LATIN CAPITAL LETTER L
    '🄼': b'\x9C',  # U+1F13C SQUARED LATIN CAPITAL LETTER M
    '🄽': b'\x9D',  # U+1F13D SQUARED LATIN CAPITAL LETTER N
    '🄾': b'\x9E',  # U+1F13E SQUARED LATIN CAPITAL LETTER O
    '🄿': b'\x9F',  # U+1F13F SQUARED LATIN CAPITAL LETTER P
    '🅀': b'\xA0',  # U+1F140 SQUARED LATIN CAPITAL LETTER Q
    '🅁': b'\xA1',  # U+1F141 SQUARED LATIN CAPITAL LETTER R
    '🅂': b'\xA2',  # U+1F142 SQUARED LATIN CAPITAL LETTER S
    '🅃': b'\xA3',  # U+1F143 SQUARED LATIN CAPITAL LETTER T
    '🅄': b'\xA4',  # U+1F144 SQUARED LATIN CAPITAL LETTER U
    #
    '🅐': b'\x90',  # U+1F150 NEGATIVE CIRCLED LATIN CAPITAL LETTER A
    '🅑': b'\x91',  # U+1F151 NEGATIVE CIRCLED LATIN CAPITAL LETTER B
    '🅒': b'\x92',  # U+1F152 NEGATIVE CIRCLED LATIN CAPITAL LETTER C
    '🅓': b'\x93',  # U+1F153 NEGATIVE CIRCLED LATIN CAPITAL LETTER D
    '🅔': b'\x94',  # U+1F154 NEGATIVE CIRCLED LATIN CAPITAL LETTER E
    '🅕': b'\x95',  # U+1F155 NEGATIVE CIRCLED LATIN CAPITAL LETTER F
    '🅖': b'\x96',  # U+1F156 NEGATIVE CIRCLED LATIN CAPITAL LETTER G
    '🅗': b'\x97',  # U+1F157 NEGATIVE CIRCLED LATIN CAPITAL LETTER H
    '🅘': b'\x98',  # U+1F158 NEGATIVE CIRCLED LATIN CAPITAL LETTER I
    '🅙': b'\x99',  # U+1F159 NEGATIVE CIRCLED LATIN CAPITAL LETTER J
    '🅚': b'\x9A',  # U+1F15A NEGATIVE CIRCLED LATIN CAPITAL LETTER K
    '🅛': b'\x9B',  # U+1F15B NEGATIVE CIRCLED LATIN CAPITAL LETTER L
    '🅜': b'\x9C',  # U+1F15C NEGATIVE CIRCLED LATIN CAPITAL LETTER M
    '🅝': b'\x9D',  # U+1F15D NEGATIVE CIRCLED LATIN CAPITAL LETTER N
    '🅞': b'\x9E',  # U+1F15E NEGATIVE CIRCLED LATIN CAPITAL LETTER O
    '🅟': b'\x9F',  # U+1F15F NEGATIVE CIRCLED LATIN CAPITAL LETTER P
    '🅠': b'\xA0',  # U+1F160 NEGATIVE CIRCLED LATIN CAPITAL LETTER Q
    '🅡': b'\xA1',  # U+1F161 NEGATIVE CIRCLED LATIN CAPITAL LETTER R
    '🅢': b'\xA2',  # U+1F162 NEGATIVE CIRCLED LATIN CAPITAL LETTER S
    '🅣': b'\xA3',  # U+1F163 NEGATIVE CIRCLED LATIN CAPITAL LETTER T
    '🅤': b'\xA4',  # U+1F164 NEGATIVE CIRCLED LATIN CAPITAL LETTER U
    #
    '🅰': b'\x90',  # U+1F170 NEGATIVE SQUARED LATIN CAPITAL LETTER A
    '🅱': b'\x91',  # U+1F171 NEGATIVE SQUARED LATIN CAPITAL LETTER B
    '🅲': b'\x92',  # U+1F172 NEGATIVE SQUARED LATIN CAPITAL LETTER C
    '🅳': b'\x93',  # U+1F173 NEGATIVE SQUARED LATIN CAPITAL LETTER D
    '🅴': b'\x94',  # U+1F174 NEGATIVE SQUARED LATIN CAPITAL LETTER E
    '🅵': b'\x95',  # U+1F175 NEGATIVE SQUARED LATIN CAPITAL LETTER F
    '🅶': b'\x96',  # U+1F176 NEGATIVE SQUARED LATIN CAPITAL LETTER G
    '🅷': b'\x97',  # U+1F177 NEGATIVE SQUARED LATIN CAPITAL LETTER H
    '🅸': b'\x98',  # U+1F178 NEGATIVE SQUARED LATIN CAPITAL LETTER I
    '🅹': b'\x99',  # U+1F179 NEGATIVE SQUARED LATIN CAPITAL LETTER J
    '🅺': b'\x9A',  # U+1F17A NEGATIVE SQUARED LATIN CAPITAL LETTER K
    '🅻': b'\x9B',  # U+1F17B NEGATIVE SQUARED LATIN CAPITAL LETTER L
    '🅼': b'\x9C',  # U+1F17C NEGATIVE SQUARED LATIN CAPITAL LETTER M
    '🅽': b'\x9D',  # U+1F17D NEGATIVE SQUARED LATIN CAPITAL LETTER N
    '🅾': b'\x9E',  # U+1F17E NEGATIVE SQUARED LATIN CAPITAL LETTER O
    '🅿': b'\x9F',  # U+1F17F NEGATIVE SQUARED LATIN CAPITAL LETTER P
    '🆀': b'\xA0',  # U+1F180 NEGATIVE SQUARED LATIN CAPITAL LETTER Q
    '🆁': b'\xA1',  # U+1F181 NEGATIVE SQUARED LATIN CAPITAL LETTER R
    '🆂': b'\xA2',  # U+1F182 NEGATIVE SQUARED LATIN CAPITAL LETTER S
    '🆃': b'\xA3',  # U+1F183 NEGATIVE SQUARED LATIN CAPITAL LETTER T
    '🆄': b'\xA4',  # U+1F184 NEGATIVE SQUARED LATIN CAPITAL LETTER U
}


# Dictionary to translate ZX Spectrum HiSoft GEN Assembler encoding, into Unicode.
# This matches normal ZX Spectrum encoding, but '\t' is used for itself, with no translation.
# Also, tokens are unlikely to be used, so we base the dictionary on ZX Spectrum 48K,
# that has extra User Defined Graphics overwriting some tokens.
#
dict_spectrum_hisoft_gen_asm_to_unicode = dict_spectrum48_to_unicode.copy();
if b'\t' in dict_spectrum_hisoft_gen_asm_to_unicode:
    del dict_spectrum_hisoft_gen_asm_to_unicode[b'\t'];


# Dictionary to translate Unicode to any ZX Spectrum HiSoft GEN Assembler encoding.
# This matches normal ZX Spectrum encoding, but '\t' is used for itself, with no translation.
#
dict_unicode_to_spectrum_hisoft_gen_asm = dict_unicode_to_spectrum.copy();
if '\t' in dict_unicode_to_spectrum_hisoft_gen_asm:
    del dict_unicode_to_spectrum_hisoft_gen_asm['\t'];


# Spectrum File Header
#
# On tape:
#   https://problemkaputt.de/zxdocs.htm#spectrumcassette
#
# On +3DOS (+3 BASIC Header):
#   From the ZX Spectrum +3 Manual
#   - "Guide to +3DOS"
#     - "Essential filing system routines"
#       - "DOS OPEN 0106h (262)"
#
class Spectrum_File_Header:
    TYPE_BASIC_PROGRAM  = 0
    TYPE_NUMERIC_ARRAY  = 1
    TYPE_CHAR_ARRAY     = 2
    TYPE_CODE_OR_SCREEN = 3

    TAPE_HEADER_TYPE          = 0
    PLUS3_BASIC_HEADER_TYPE   = 1

    TAPE_HEADER_LENGTH        = 17
    PLUS3_BASIC_HEADER_LENGTH =  8

    FILE_NAME_MAX_LENGTH = 10
    BASIC_NO_AUTO_START  = 0x8000  # Or anything above, until 0xFFFF
    CODE_DEFAULT_ADDRESS = 16384
        # Screen start; used when address doesn't matter.
        # Using screen address makes a mistake such as "LOAD file CODE" obvious
        # before a retry.


    header_type                = TAPE_HEADER_TYPE
    file_type                  = 0
    file_name                  = ""  # absent in a PLUS3_BASIC_HEADER_TYPE
    file_length                = 0
    basic_automatic_start_line = 0
    basic_prog_length          = 0
    code_load_address          = 0
    array_name                 = '\x00'

    def __init__( self, header_type = TAPE_HEADER_TYPE, file_name = "", file_length = 0 ):
        """
        Zero all Spectrum File Header data, space-fill file_name.

        From the ZX Spectrum +3 manual:
        "If open action = 1, and the file exists (and has a header), then the
        header data is read from the file, otherwise the header data is zeroised.
        The header data is available even if the file does not have a header."
        """
        assert header_type == self.TAPE_HEADER_TYPE  or  header_type == self.PLUS3_BASIC_HEADER_TYPE,  \
            "header_type must be one of Spectrum_File_Header.TAPE_HEADER_TYPE or Spectrum_File_Header.PLUS3_BASIC_HEADER_TYPE"
        assert len(file_name) <= self.FILE_NAME_MAX_LENGTH,  \
            f"file_name must have maximum length of Spectrum_File_Header.FILE_NAME_MAX_LENGTH ({self.FILE_NAME_MAX_LENGTH})"
        self.header_type                = header_type
        self.file_type                  = 0
        self.file_name                  = file_name
        self.file_length                = file_length
        self.basic_automatic_start_line = 0
        self.basic_prog_length          = 0
        self.code_load_address          = 0
        self.array_name                 = '\x00'

    def header_length(self):
        if self.header_type == self.TAPE_HEADER_TYPE:
            return self.TAPE_HEADER_LENGTH
        elif self.header_type == self.PLUS3_BASIC_HEADER_TYPE:
            return self.PLUS3_BASIC_HEADER_LENGTH
        else:
            assert False,  \
                "header_type must be one of Spectrum_File_Header.TAPE_HEADER_TYPE or Spectrum_File_Header.PLUS3_BASIC_HEADER_TYPE"


    def set_type_basic_program( self, start_line = BASIC_NO_AUTO_START, offset_to_prog = 0 ):
        self.file_type = self.TYPE_BASIC_PROGRAM
        assert start_line == self.BASIC_NO_AUTO_START  or  \
               (start_line >= 1 and start_line <= 9999),  \
               "Start_line must be Spectrum_File_Header.BASIC_NO_AUTO_START or between 1 and 9999."
        self.basic_automatic_start_line = start_line
        self.basic_prog_length = offset_to_prog

    def set_type_numeric_array( self, name ):
        self.file_type = self.TYPE_NUMERIC_ARRAY
        assert len(name) == 1  and  name[0].isalpha(), "Name must be a single letter"
        self.array_name = name

    def set_type_char_array( self, name ):
        self.file_type = self.TYPE_CHAR_ARRAY
        assert len(name) == 1  and  name[0].isalpha(), "Name must be a single letter"
        self.array_name = name

    def set_type_code_or_screen( self, load_address = CODE_DEFAULT_ADDRESS ):
        self.file_type = self.TYPE_CODE_OR_SCREEN
        self.code_load_address = load_address


    def is_zeroed( self ):
        return  \
            self.file_type                  == 0  and  \
            self.file_length                == 0  and  \
            self.basic_automatic_start_line == 0  and  \
            self.basic_prog_length          == 0  and  \
            self.code_load_address          == 0  and  \
            self.array_name                 == '\x00'


    def encode( self ):
        """
        Encodes this object into an 8-byte header array
        which is returned.

        Sanity assertions are disabled so that an insane decode() can be encode()ed back.
        """

        header_bytes = b""

        if self.header_type == self.TAPE_HEADER_TYPE  or  not self.is_zeroed():
            header_bytes += struct.pack( "<B", self.file_type )

            if self.header_type == self.TAPE_HEADER_TYPE:
                for char in self.file_name.strip()[:self.FILE_NAME_MAX_LENGTH].ljust(self.FILE_NAME_MAX_LENGTH):
                    header_bytes += dict_unicode_to_spectrum.get( char, char.encode(CHARSET_UNICODE_CHAR) )

            header_bytes += struct.pack( "<H", self.file_length )

            if self.file_type == self.TYPE_BASIC_PROGRAM:
                #assert self.basic_automatic_start_line == self.BASIC_NO_AUTO_START  or  \
                #    (self.basic_automatic_start_line >= 1 and self.basic_automatic_start_line <= 9999),  \
                #    "Spectrum_File_Header.basic_automatic_start_line must be Spectrum_File_Header.BASIC_NO_AUTO_START or between 1 and 9999."
                header_bytes += struct.pack( "<H", self.basic_automatic_start_line )
                header_bytes += struct.pack( "<H", self.basic_prog_length )

            elif self.file_type == self.TYPE_NUMERIC_ARRAY  or  \
                self.file_type == self.TYPE_CHAR_ARRAY:
                header_bytes += b'\x00'
                #assert len(self.array_name) == 1  and  self.array_name[0].isalpha(), "Spectrum_File_Header.array_name must be a single letter"
                header_bytes += dict_unicode_to_spectrum.get( self.array_name[0], self.array_name[0].encode(CHARSET_UNICODE_CHAR) )
                header_bytes += b'\x00\x00'

            elif self.file_type == self.TYPE_CODE_OR_SCREEN:
                header_bytes += struct.pack( "<H", self.code_load_address )
                header_bytes += b'\x00\x80' if self.header_type==self.TAPE_HEADER_TYPE else b'\x00\x00'
                    # 0x8000 for historical reasons
                    # https://problemkaputt.de/zxdocs.htm#spectrumcassette

            #else:
            #    assert False, "Invalid value for Spectrum_File_Header.file_type"

        header_bytes = header_bytes.ljust( self.header_length(), b'\x00' )
        assert len(header_bytes) == self.header_length(), f"Generated header bytes should total Spectrum_File_Header.TAPE_HEADER_LENGTH/PLUS3_BASIC_HEADER_LENGTH ({self.header_length()}) bytes in length"
        return header_bytes


    def decode( self, header_bytes ):
        """
        Decodes +3 BASIC Header from a byte array.
        Current object is always changed except if header_bytes is of the incorrect length,
        in which case the current object is zeroed.
        Caller must do value checks before calling self.encode()

        Returns True if header_bytes describe a sane +3 BASIC Header.
        Returns False otherwise.
        """

        decode_ok = True
        self.__init__( self.header_type );  # Zero self

        # Check if tape header was extracted with the raw leading+trailing check bytes
        if  self.header_type == self.TAPE_HEADER_TYPE  and  \
            len(header_bytes) == self.header_length()+2:

            if header_bytes[0] != SINCLAIR_BASIC_TAPE_HEADER_MARKER:
                return False

            # Calculate the final Checksum XOR byte
            header_checkxor = header_bytes[-1]  # Trailing check byte is a Checksum XOR
            header_bytes = header_bytes[ 1 : -1 ]  # remove the raw leading+trailing check bytes
            checkxor = 0
            for byte in header_bytes:
                checkxor ^= byte

            if checkxor != header_checkxor:
                return False
                # header_bytes seems to be a tape header was extracted with the
                # raw leading+trailing check bytes, but the trailing Checksum
                # XOR does not verify the data as being good.


        # Check if header_bytes is of the expected length
        if len(header_bytes) != self.header_length():
            return False

        if self.header_type == self.TAPE_HEADER_TYPE  or  header_bytes != b"".ljust(self.header_length(), b'\x00'):
            self.file_type = header_bytes[0]

            if self.header_type == self.TAPE_HEADER_TYPE:
                file_name = ""
                for byte in header_bytes[ 1 : self.FILE_NAME_MAX_LENGTH+1 ]:
                    if byte in dict_spectrum48_to_unicode:
                        file_name += dict_spectrum48_to_unicode[byte]
                        # Filenames shouldn't have tokens: use dict_spectrum48_to_unicode which has more non-token conversions
                    else:
                        file_name += byte.decode( CHARSET_UNICODE_CHAR )
                self.file_name = file_name.strip()
                header_bytes = header_bytes[ self.FILE_NAME_MAX_LENGTH+1-1 : ]

            self.file_length = struct.unpack( "<H", header_bytes[1:3] )[0]

            if self.file_type == self.TYPE_BASIC_PROGRAM:
                self.basic_automatic_start_line = struct.unpack( "<H", header_bytes[3:5] )[0]
                self.basic_prog_length          = struct.unpack( "<H", header_bytes[5:7] )[0]
                decode_ok = decode_ok  and  \
                    ( self.basic_automatic_start_line == self.BASIC_NO_AUTO_START  or  \
                      (self.basic_automatic_start_line >= 1 and self.basic_automatic_start_line <= 9999) \
                    )

            elif self.file_type == self.TYPE_NUMERIC_ARRAY  or  \
                self.file_type == self.TYPE_CHAR_ARRAY:
                self.array_name = dict_spectrum128_to_unicode.get( header_bytes[4], header_bytes[4].decode(CHARSET_UNICODE_CHAR) )
                decode_ok = decode_ok  and  \
                    len(self.array_name) == 1  and  self.array_name[0].isalpha()

            elif self.file_type == self.TYPE_CODE_OR_SCREEN:
                self.code_load_address = struct.unpack( "<H", header_bytes[3:5] )[0]

            else:
                decode_ok = False

        return decode_ok


# +3DOS File Header
# From the ZX Spectrum +3 Manual
# - "Guide to +3DOS"
#   - "File headers"
#
class Plus3Dos_File_Header:
    HEADER_SIGNATURE = b"PLUS3DOS"+SOFT_EOF_BYTE
    HEADER_LENGTH    = 128

    signature               = HEADER_SIGNATURE
    issue_number            = 1
    version_number          = 0
    file_length_with_header = HEADER_LENGTH
    basic_header            = Spectrum_File_Header( Spectrum_File_Header.PLUS3_BASIC_HEADER_TYPE )

    def __init__( self, file_length = 0 ):
        self.signature               = self.HEADER_SIGNATURE
        self.issue_number            = 1
        self.version_number          = 0
        self.file_length_with_header = self.HEADER_LENGTH + file_length
        self.basic_header            = Spectrum_File_Header(Spectrum_File_Header.PLUS3_BASIC_HEADER_TYPE)  # Leave it as the default "zeroed"

    def set_file_length( self, file_length ):
        self.file_length_with_header  = self.HEADER_LENGTH + file_length
        if not self.basic_header.is_zeroed():
            self.basic_header.file_length = file_length


    def encode( self ):
        header_bytes  = self.signature
        header_bytes += struct.pack( "<B", self.issue_number )
        header_bytes += struct.pack( "<B", self.version_number )
        header_bytes += struct.pack( "<I", self.file_length_with_header )
        header_bytes += self.basic_header.encode()
        header_bytes = header_bytes.ljust( self.HEADER_LENGTH-1, b'\x00' )

        # Calculate the final Checksum byte
        checksum = 0
        for byte in header_bytes:
            checksum += byte
        checksum %= 256
        header_bytes += struct.pack( "<B", checksum )

        assert len(header_bytes) == self.HEADER_LENGTH, f"Generated header bytes should total {self.HEADER_LENGTH} bytes in length"
        return header_bytes


    def decode( self, header_bytes ):
        """
        Decodes +3DOS File Header from a byte array.

        Will try to match header_bytes' signature with self.signature, not self.HEADER_SIGNATURE.
        Returns True if current object changed from header_bytes.
        Returns False if current object wasn't modified as there were errors in header_bytes.
        """

        # Check if header_bytes is of the expected length
        if len(header_bytes) != self.HEADER_LENGTH:
            return False

        # Check if signature is present
        assert len(self.signature) == 9, "self.signature must be 9 bytes in length"
        if header_bytes[0:len(self.signature)] != self.signature:
            return False

        # Calculate the final Checksum byte
        checksum = 0
        for byte in header_bytes[:-1]:
            checksum += byte
        checksum %= 256
        header_checksum = header_bytes[-1]

        # Check if final Checksum byte is correct
        if checksum != header_checksum:
            return False
            # header_bytes seems to be a valid +3DOS File Header, but the
            # trailing Checksum does not verify the data as being good.

        issue_number             = header_bytes[9]
        version_number           = header_bytes[10]
        file_length_with_header  = struct.unpack( "<I", header_bytes[11:15] )[0]
        basic_header             = Spectrum_File_Header( Spectrum_File_Header.PLUS3_BASIC_HEADER_TYPE )
        basic_header_decode_ok   = basic_header.decode( header_bytes[15:23] )

        # Check if +3 BASIC Header was decoded correctly
        if not basic_header_decode_ok:
            return False

        self.__init__();
        self.issue_number = issue_number
        self.version_number = version_number
        self.file_length_with_header = file_length_with_header
        self.basic_header = basic_header
        return True


def spectrum_hisoft_gen_asm_to_unicode(
    filename_spectrum,
    filename_unicode,
    include_line_numbers = False,
    stop_at_soft_eof = False
    ):
    """
    Convert a ZX Spectrum's HiSoft GEN Assembler file to Unicode format.
    The original file would need to have been extracted from TAP/TZX/DSK.

    For files extracted from a DSK:
    - This function detects a +3DOS File Header (if present) on files extracted in CP/M mode.
    - This function detects a Soft-EOF (if present) on files without +3DOS File Header.

    Soft-EOF detection can result in false positives, so it's disabled by default,
    and is forcefully disabled if a +3DOS File Header is found.
    """

    with open(filename_spectrum, "rb"                               ) as infile,  \
         open(filename_unicode,  "wt", encoding=CHARSET_UNICODE_FILE) as outfile:

        # Some HiSoft GEN Assembly file start with a 16-bit file length value
        waiting_for_lead_file_length = True

        # Maximum length to read
        # Defaults to 32Mb, the maximum file length between +3DOS and CP/M
        # Documented in the ZX Spectrum +3 manual, "CP/M File compatibility"
        # max_length = 32*1024*1024
        # We instead measure the exact file size, as this is important for the
        # lead file length check
        infile.seek( 0, 2 )  # whence=2 means relative to the EOF
        max_length = infile.tell()
        infile.seek( 0 )  # Rewind back to the beginning of the file

        # Check for optional leading +3DOS File Header
        # If present, read Max_length from it
        plus3dos_header = Plus3Dos_File_Header()
        plus3dos_header_bytes = infile.read( plus3dos_header.HEADER_LENGTH )
        #
        if  len(plus3dos_header_bytes) == plus3dos_header.HEADER_LENGTH  and  \
            plus3dos_header.decode(plus3dos_header_bytes):
            max_length = plus3dos_header.file_length_with_header - plus3dos_header.HEADER_LENGTH
            # With a +3DOS File Header we know the exact length of the file:
            # don't look for Soft-EOF as that is error-prone
            stop_at_soft_eof = False
        else:
            # Rewind back to the beginning of the file
            infile.seek( 0 )

        # Repeat for each Assembly code line
        while max_length > 2:

            # Read the line number in binary (16 bit)
            #
            # Read two bytes (16 bits)
            line_number_bytes = infile.read( 2 )
            max_length -= 2
            #
            # Check if we found the EOF
            if  len(line_number_bytes) < 2  or  \
                (stop_at_soft_eof  and  (line_number_bytes[0] == SOFT_EOF_BYTE or line_number_bytes[1] == SOFT_EOF_BYTE)):
                return
            #
            # Convert the bytes to a little-endian unsigned 16-bit number
            line_number = struct.unpack("<H", line_number_bytes)[0]

            # Check/Skip lead file length, two bytes
            if waiting_for_lead_file_length:
                waiting_for_lead_file_length = False
                if line_number == max_length+2:
                    continue  # Continue to the next line

            # Write the number as text, padded to 6 characters;
            # Take up 8 characters total, so that '\t' works properly after this
            if include_line_numbers:
                outfile.write( f"{line_number:6d}  " )

            # Read Assembly line: all bytes until '\r'
            while max_length > 0:

                # Read a single byte
                byte = infile.read( 1 )
                max_length -= 1

                # Check if we found the EOF
                if  len(byte) < 1  or  \
                    (stop_at_soft_eof  and  byte == SOFT_EOF_BYTE):
                    return

                # Check if we found the EOL
                if byte == b'\r':
                    break

                # Translate and write the byte to the output file
                # (can't use dict.get(...) as byte.decode() may fail)
                if byte in dict_spectrum_hisoft_gen_asm_to_unicode:
                    outfile.write( dict_spectrum_hisoft_gen_asm_to_unicode[byte] )
                else:
                    outfile.write( byte.decode(CHARSET_UNICODE_CHAR) )

            # Append '\n' to the output file to mark the EOL
            outfile.write( "\n" )




def unicode_to_spectrum_hisoft_gen_asm(
    filename_unicode,
    filename_spectrum,
    filename_tape_header,
    prepend_plus3dos_header = False,
    append_soft_eof = False
    ):
    """
    Convert a Unicode file to ZX Spectrum's HiSoft GEN Assembler format.
    The converted file would need to be written to TAP/TZX/DSK to be used in an emulator.

    This function will auto-detect if line numbers were exported into the PC file, and
    use them if present. If missing, all lines will be numbered starting at 10, in steps
    of 10.

    If inserting the file back to a DSK, remember to run the following command on the
    ZX Spectrum +3 [emulator] to recreate the +3DOS File Header:
    - COPY file TO SPECTRUM FORMAT
    - Use the created "file.HED" file
    """

    with open(filename_unicode,  "rt", encoding=CHARSET_UNICODE_FILE) as infile,  \
         open(filename_spectrum, "wb"                               ) as outfile:

        # Renumbering pattern
        line_number     = 10  # Start line number
        line_number_inc = 10  # Line number incrementing step
        regex_line_number = re.compile( r"\A[ ]*([0-9]+)\b[ ]{0,2}(.*)\Z" )

        # Write +3DOS File Header
        if prepend_plus3dos_header:
            plus3dos_header = Plus3Dos_File_Header()
            # We need to know the final file length to re-write and re-calculate the checksum
            # So for now we just write the header with all zeros
            outfile.write( b"".ljust(plus3dos_header.HEADER_LENGTH, b'\x00') )

        # Read each Assembly line
        while True:

            # Read an entire Unicode text line
            line_text = infile.readline()

            # Check if we found the EOF
            if len(line_text) < 1:
                break

            # Remove any trailing newline (and whitespace)
            line_text = line_text.rstrip()

            # Check/Read a leading line number
            regex_match = regex_line_number.match( line_text )
            if regex_match != None:
                line_number = int( regex_match.group(1) )
                line_text   =      regex_match.group(2)

            # Convert the line number to a 16-bit binary
            line_number_bytes = struct.pack( "<H", line_number )

            # Write the line number's two bytes (16 bits),
            # the remainder of the line (translating to ZX Spectrum encoding)
            # and the EOL '\r' terminator
            outfile.write( line_number_bytes )
            for char in line_text:
                outfile.write( dict_unicode_to_spectrum_hisoft_gen_asm.get(char, char.encode(CHARSET_UNICODE_CHAR)) )
            outfile.write( "\r".encode(CHARSET_UNICODE_CHAR) )

            # Increment the line number
            line_number += line_number_inc

        # If requested, append the Soft-EOF
        if append_soft_eof:
            outfile.write( SOFT_EOF_BYTE )

        # (Re-)Write +3DOS File Header, now with the proper file length
        if prepend_plus3dos_header:
            file_length_with_header = outfile.tell()
            if append_soft_eof:
                file_length_with_header -= 1  # Remove the final Soft-EOF
            plus3dos_header.basic_header.set_type_code_or_screen()
            plus3dos_header.set_file_length( file_length_with_header - plus3dos_header.HEADER_LENGTH )
            header_bytes = plus3dos_header.encode()
            outfile.seek( 0 )
            outfile.write( header_bytes )

        # Check for optional tape header file to write
        if filename_tape_header != None:
            file_length = outfile.tell()
            with open(filename_tape_header, "wb") as headerfile:
                tape_header = Spectrum_File_Header(
                    Spectrum_File_Header.TAPE_HEADER_TYPE,
                    os.path.basename(filename_spectrum.replace('\\', '/'))[: Spectrum_File_Header.FILE_NAME_MAX_LENGTH],
                    file_length )
                tape_header.set_type_code_or_screen()
                header_bytes = tape_header.encode()
                headerfile.write( header_bytes )


def spectrum_sinclair_bas_to_unicode(
    filename_spectrum,
    filename_unicode,
    filename_tape_header,
    use_spectrum48k_tokens = False,
    stop_at_soft_eof = False
    ):
    """
    Convert a ZX Spectrum's Sinclair BASIC file to Unicode format.
    The original file would need to have been extracted from TAP/TZX/DSK.

    For files extracted from a DSK:
    - This function detects a +3DOS File Header (if present) on files extracted in CP/M mode.
    - This function detects a Soft-EOF (if present) on files without +3DOS File Header.

    Soft-EOF detection can result in false positives, so it's disabled by default,
    and is forcefully disabled if a +3DOS File Header is found.
    """

    if use_spectrum48k_tokens:
        dict = dict_spectrum48_to_unicode
    else:
        dict = dict_spectrum128_to_unicode

    # Flag if we know PROG length
    # If not, we'll use heuristics
    prog_length_is_known = False

    # Maximum length to read
    # Defaults to 32Mb, the maximum file length between +3DOS and CP/M
    # Documented in the ZX Spectrum +3 manual, "CP/M File compatibility"
    max_length = 32*1024*1024

    # Check for optional tape header file to read
    if filename_tape_header != None:
        with open(filename_tape_header, "rb") as headerfile:
            header_bytes = headerfile.read()
            tape_header = Spectrum_File_Header( Spectrum_File_Header.TAPE_HEADER_TYPE )
            if tape_header.decode(header_bytes):
                if  tape_header.basic_header.file_type == tape_header.basic_header.TYPE_BASIC_PROGRAM:
                    max_length = min( max_length, tape_header.basic_header.basic_prog_length )
                    prog_length_is_known = True

    with open(filename_spectrum, "rb"                               ) as infile,  \
         open(filename_unicode,  "wt", encoding=CHARSET_UNICODE_FILE) as outfile:

        # Check for optional leading +3DOS File Header
        # If present, read max_length from it
        plus3dos_header = Plus3Dos_File_Header()
        plus3dos_header_bytes = infile.read( plus3dos_header.HEADER_LENGTH )
        #
        if  len(plus3dos_header_bytes) == plus3dos_header.HEADER_LENGTH  and  \
            plus3dos_header.decode(plus3dos_header_bytes):
            max_length = plus3dos_header.file_length_with_header - plus3dos_header.HEADER_LENGTH
            #
            # Try to read +3 BASIC Header
            # If present, read basic_prog_length from it, and use it if smaller than max_length
            if  not plus3dos_header.basic_header.is_zeroed()  and  \
                plus3dos_header.basic_header.file_type == plus3dos_header.basic_header.TYPE_BASIC_PROGRAM:
                max_length = min( max_length, plus3dos_header.basic_header.basic_prog_length )
                prog_length_is_known = True
            #
            # With a +3DOS File Header we know the exact length of the file:
            # don't look for Soft-EOF as that is error-prone
            stop_at_soft_eof = False
        else:
            # Rewind back to the beginning of the file
            infile.seek( 0 )

        # Repeat for each Assembly code line
        while max_length > 2:

            # Read the line number in binary (16 bit)
            #
            # Read two bytes (16 bits)
            line_number_and_length_bytes = infile.read( 4 )
            max_length -= 4
            #
            # Check if we found the EOF
            if  len(line_number_and_length_bytes) < 4  or  \
                (stop_at_soft_eof  and  (line_number_and_length_bytes[0] == SOFT_EOF_BYTE or line_number_and_length_bytes[1] == SOFT_EOF_BYTE)):
                return
            #
            # Convert the bytes to a big-endian and little-endian unsigned 16-bit numbers
            line_number = struct.unpack(">H", line_number_and_length_bytes[:2])[0]
            line_length = struct.unpack("<H", line_number_and_length_bytes[2:])[0]
                # line_length is unused, as we're parsing the line, not skipping it
            #
            # Check if we found VARS, the end of the BASIC program and start of Variables
            if  not prog_length_is_known  and  \
                line_number >= SINCLAIR_BASIC_LINE_IS_VARIABLE:
                return

            # Write the number as text, padded to 4 characters
            outfile.write( f"{line_number:4d} " )

            # Read Assembly line: all bytes until '\r'
            while max_length > 0:

                # Read a single byte
                byte = infile.read( 1 )
                max_length -= 1

                # Check if we found the EOF
                if  len(byte) < 1  or  \
                    (stop_at_soft_eof  and  byte == SOFT_EOF_BYTE):
                    return

                # Check for int/float representation of a number
                if byte == SINCLAIR_BASIC_NUMBER_MARKER:
                    infile.read( SINCLAIR_BASIC_NUMBER_LENGTH )
                    max_length -= SINCLAIR_BASIC_NUMBER_LENGTH
                    continue

                # Check if we found the EOL
                if byte == b'\r':
                    break

                # Translate and write the byte to the output file
                # (can't use dict.get(...) as byte.decode() may fail)
                if byte in dict:
                    outfile.write( dict[byte] )
                else:
                    outfile.write( byte.decode(CHARSET_UNICODE_CHAR) )

            # Append '\n' to the output file to mark the EOL
            outfile.write( "\n" )


#   The Main Program, Parse Arguments and run features.
#
if __name__ == "__main__":
    # Add arguments
    parser = argparse.ArgumentParser(
        #prog="ZX Spectrum file converter",
        description="ZX Spectrum <-> Unicode file converter.\nSupports Sinclair BASIC (BAS) and HiSoft GEN Assembler (ASM).",
        epilog='Author: Pedro Freire - Jan 2025 - GNU General Public License - https://github.com/pfre/speccy-conv' )

    # Positional parameters
    parser.add_argument(
        "action",
        choices  = [ "bas2u", "asm2u", "u2asm" ],
        help     = "Operation to perform, e.g.: bas2u = Sinclair BASIC to Unicode",
        )
    parser.add_argument(
        "filenameInput",
        help = "Filename of input file to convert",
        )
    parser.add_argument(
        "filenameOutput",
        help    = "Filename of output file to generate; defaults to the same as input, with an extension added",
        nargs   = '?',
        default = None
        )

    # Optional parameters
    parser.add_argument(
        "-4",
        "--useSpectrum48KTokens",
        help    = "Use ZX Spectrum 48K (vs 128K) BASIC tokens in the output (Unicode) file (only for bas2u)",
        action  = "store_true",
        default = False
        )
    parser.add_argument(
        "-l",
        "--includeLineNumbers",
        help    = "Include line numbers in the output (Unicode) file (only for asm2u)",
        action  = "store_true",
        default = False
        )
    parser.add_argument(
        "-t",
        "--tapeHeaderFile",
        help    = "Tape header filename to read (Spectrum input) or generate (Spectrum output)",
        metavar = "filenameHeader"
        )
    parser.add_argument(
        "-3",
        "--prependPlus3DosHeader",
        help    = "Prepend +3DOS File Header to the beginning of the output (Spectrum) file",
        action  = "store_true",
        default = False
        )
    parser.add_argument(
        "-s",
        "--useSoftEOF",
        help    = "Stop parsing (Spectrum) input at Soft-EOF (1Ah), or append Soft-EOF to the end of the output (Spectrum) file",
        action  = "store_true",
        default = False
        )

    args = parser.parse_args()
    filenameOutput = args.filenameOutput

    if  args.tapeHeaderFile != None  and  \
        (args.prependPlus3DosHeader  or  args.useSoftEOF):
        parser.error( "Cannot use --tapeHeaderFile at the same time as disk options --prependPlus3DosHeader or --useSoftEOF" )


    if args.action == "bas2u":
        if filenameOutput == None:
            filenameOutput = args.filenameInput + ".txt"
        spectrum_sinclair_bas_to_unicode(
            args.filenameInput,
            filenameOutput,
            args.tapeHeaderFile,
            args.useSpectrum48KTokens,
            args.useSoftEOF
            )

    if args.action == "asm2u":
        if filenameOutput == None:
            filenameOutput = args.filenameInput + ".txt"
        spectrum_hisoft_gen_asm_to_unicode(
            args.filenameInput,
            filenameOutput,
            args.includeLineNumbers,
            args.useSoftEOF
            )

    if args.action == "u2asm":
        if filenameOutput == None:
            filenameOutput = args.filenameInput + ".asm"
        unicode_to_spectrum_hisoft_gen_asm(
            args.filenameInput,
            filenameOutput,
            args.tapeHeaderFile,
            args.prependPlus3DosHeader,
            args.useSoftEOF
            )
