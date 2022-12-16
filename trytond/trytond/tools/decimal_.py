# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import sys
from tokenize import *
from io import BytesIO, StringIO

# code snippet taken from http://docs.python.org/library/tokenize.html


if sys.version_info < (3,):
    def decistmt(s):
        """Substitute Decimals for floats in a string of statements.

        >>> from decimal import Decimal
        >>> s = 'print +21.3e-5*-.1234/81.7'
        >>> decistmt(s)
        u"print +Decimal (u'21.3e-5')*-Decimal (u'.1234')/Decimal (u'81.7')"

        >>> exec(s)
        -3.21716034272e-07
        >>> exec(decistmt(s))
        -3.217160342717258261933904529E-7

        """
        result = []
        g = generate_tokens(StringIO(s.decode('utf-8')).readline)   # tokenize the string
        for toknum, tokval, _, _, _ in g:
            if toknum == NUMBER and '.' in tokval:  # replace NUMBER tokens
                result.extend([
                    (NAME, 'Decimal'),
                    (OP, '('),
                    (STRING, repr(tokval)),
                    (OP, ')')
                ])
            else:
                result.append((toknum, tokval))
        return untokenize(result)
else:
    def decistmt(s):
        """Substitute Decimals for floats in a string of statements.

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
        """
        result = []
        g = tokenize(BytesIO(s.encode('utf-8')).readline)  # tokenize the string
        for toknum, tokval, _, _, _ in g:
            if toknum == NUMBER and '.' in tokval:  # replace NUMBER tokens
                result.extend([
                    (NAME, 'Decimal'),
                    (OP, '('),
                    (STRING, repr(tokval)),
                    (OP, ')')
                ])
            else:
                result.append((toknum, tokval))
        return untokenize(result).decode('utf-8')
