"""
sentry.utils.sourcemaps
~~~~~~~~~~~~~~~~~~~~~~~

Originally based on https://github.com/martine/python-sourcemap

:copyright: (c) 2010-2012 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import bisect
from collections import namedtuple
from sentry.utils import json


SourceMap = namedtuple('SourceMap', ['dst_line', 'dst_col', 'src', 'src_line', 'src_col', 'name'])
SourceMapIndex = namedtuple('SourceMapIndex', ['state_list', 'key_list'])

# Mapping of base64 letter -> integer value.
B64 = dict(
    (c, i) for i, c in
    enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/')
)


def parse_vlq(segment):
    """
    Parse a string of VLQ-encoded data.

    Returns:
      a list of integers.
    """

    values = []

    cur, shift = 0, 0
    for c in segment:
        val = B64[c]
        # Each character is 6 bits:
        # 5 of value and the high bit is the continuation.
        val, cont = val & 0b11111, val >> 5
        cur += val << shift
        shift += 5

        if not cont:
            # The low bit of the unpacked value is the sign.
            cur, sign = cur >> 1, cur & 1
            if sign:
                cur = -cur
            values.append(cur)
            cur, shift = 0, 0

    if cur or shift:
        raise Exception('leftover cur/shift in vlq decode')

    return values


def parse_sourcemap(sourcemap):
    """
    Given a file-like object, yield SourceMap objects as they are read from it.
    """

    smap = json.loads(sourcemap)
    sources = smap['sources']
    names = smap['names']
    mappings = smap['mappings']
    lines = mappings.split(';')

    dst_col, src_id, src_line, src_col, name_id = 0, 0, 0, 0, 0
    for dst_line, line in enumerate(lines):
        segments = line.split(',')
        dst_col = 0
        for segment in segments:
            if not segment:
                continue
            parse = parse_vlq(segment)
            dst_col += parse[0]

            src = None
            name = None
            if len(parse) > 1:
                src_id += parse[1]
                src = sources[src_id]
                src_line += parse[2]
                src_col += parse[3]

                if len(parse) > 4:
                    name_id += parse[4]
                    name = names[name_id]

            assert dst_line >= 0
            assert dst_col >= 0
            assert src_line >= 0
            assert src_col >= 0

            yield SourceMap(dst_line, dst_col, src, src_line, src_col, name)


def sourcemap_to_index(parsed_sourcemap):
    state_list = []
    key_list = []

    for state in parsed_sourcemap:
        state_list.append(state)
        key_list.append((state.dst_line, state.dst_col))

    return SourceMapIndex(state_list, key_list)


def find_source(indexed_sourcemap, lineno, colno):
    # error says "line no 0, column no 56"
    return indexed_sourcemap.state_list[bisect.bisect_left(indexed_sourcemap.key_list, (0, 56)) - 1]
