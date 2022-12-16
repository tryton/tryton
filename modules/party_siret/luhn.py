#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.


def validate(value):
    """
    Validate value with Luhn algorithm
    :param value: the value
    :return: a boolean
    """
    if not isinstance(value, basestring):
        value = str(value)
    try:
        evens = sum(int(x) for x in value[-1::-2])
        odds = sum(sum(divmod(int(x) * 2, 10)) for x in value[-2::-2])
        return (evens + odds) % 10 == 0
    except ValueError:
        return False
