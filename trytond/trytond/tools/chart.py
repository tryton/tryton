# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from collections.abc import Collection

_UNICODE_BLOCKS = (
    '\N{LOWER ONE EIGHTH BLOCK}'
    '\N{LOWER ONE QUARTER BLOCK}'
    '\N{LOWER THREE EIGHTHS BLOCK}'
    '\N{LOWER HALF BLOCK}'
    '\N{LOWER FIVE EIGHTHS BLOCK}'
    '\N{LOWER THREE QUARTERS BLOCK}'
    '\N{LOWER SEVEN EIGHTHS BLOCK}'
    '\N{FULL BLOCK}')
_UNICODE_BLOCKS_LENGTH = len(_UNICODE_BLOCKS)


def sparkline(numbers):
    "Return a string of the same length with unicode blocks"
    if not isinstance(numbers, Collection):
        numbers = list(numbers)
    mn, mx = min(numbers, default=0), max(numbers, default=0)
    extent = (mx - mn) or 1
    return ''.join(
        _UNICODE_BLOCKS[min([
                    int((n - mn) / extent * _UNICODE_BLOCKS_LENGTH),
                    _UNICODE_BLOCKS_LENGTH - 1])]
        for n in numbers)
