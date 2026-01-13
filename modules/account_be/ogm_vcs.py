# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from stdnum.exceptions import (
    InvalidChecksum, InvalidFormat, InvalidLength, ValidationError)
from stdnum.util import clean, isdigits


def compact(number: str) -> str:
    """Convert the number to the minimal representation. This strips the number
    of any invalid separators and removes surrounding whitespace."""
    return clean(number, ' +/').strip()


def calc_check_digits(number: str) -> str:
    """Calculate the check digit that should be added."""
    number = compact(number)
    return '%02d' % ((int(number[:10]) % 97) or 97)


def validate(number: str) -> str:
    """Check if the number is a valid OGM-VCS."""
    number = compact(number)
    if not isdigits(number) or int(number) <= 0:
        raise InvalidFormat()
    if len(number) != 12:
        raise InvalidLength()
    if calc_check_digits(number) != number[-2:]:
        raise InvalidChecksum()
    return number


def is_valid(number: str) -> bool:
    """Check if the number is a valid VAT number."""
    try:
        return bool(validate(number))
    except ValidationError:
        return False


def format(number: str) -> str:
    """Format the number provided for output."""
    number = compact(number)
    number = number.rjust(12, '0')
    return f'{number[:3]}/{number[3:7]}/{number[7:]}'
