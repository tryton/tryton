# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal
from functools import total_ordering
from io import BytesIO
from tokenize import NAME, NUMBER, OP, STRING, tokenize, untokenize

# code snippet taken from http://docs.python.org/library/tokenize.html


def decistmt(s):
    """Substitute Decimals for floats or integers in a string of statements.

    >>> from decimal import Decimal
    >>> s = 'print(+21.3e-5*-.1234/81.7)'
    >>> decistmt(s)
    "print (+Decimal ('21.3e-5')*-Decimal ('.1234')/Decimal ('81.7'))"

    The format of the exponent is inherited from the platform C library.
    Known cases are "e-007" (Windows) and "e-07" (not Windows).  Since
    we're only showing 12 digits, and the 13th isn't close to 5, the
    rest of the output should be platform-independent.

    >>> exec(s) #doctest: +ELLIPSIS
    -3.217160342717258e-0...7

    Output from calculations with Decimal should be identical across all
    platforms.

    >>> exec(decistmt(s))
    -3.217160342717258261933904529E-7
    >>> decistmt('0')
    "Decimal ('0')"
    >>> decistmt('1.23')
    "Decimal ('1.23')"
    """
    result = []
    g = tokenize(BytesIO(s.encode('utf-8')).readline)  # tokenize the string
    for toknum, tokval, _, _, _ in g:
        if toknum == NUMBER:  # replace NUMBER tokens
            result.extend([
                (NAME, 'Decimal'),
                (OP, '('),
                (STRING, repr(tokval)),
                (OP, ')')
            ])
        else:
            result.append((toknum, tokval))
    return untokenize(result).decode('utf-8')


@total_ordering
class DecimalNull(Decimal):
    def __eq__(self, other):
        if isinstance(other, DecimalNull) or other is None:
            return True
        return False

    def __lt__(self, other):
        return 0 < other


def _return_self(self, *args, **kwargs):
    return self


_OPERATORS = (
    'add sub mul matmul truediv floordiv mod divmod pow lshift rshift and xor '
    'or'.split())
for op in _OPERATORS:
    setattr(DecimalNull, '__%s__' % op, _return_self)
    setattr(DecimalNull, '__r%s__' % op, _return_self)
