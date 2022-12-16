#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import decimal
from decimal import Decimal

_convert_other = decimal._convert_other

def _convert_Float(other, *args, **kwargs):
    if isinstance(other, Float):
        return other.decimal
    return _convert_other(other, *args, **kwargs)
decimal._convert_other = _convert_Float


class Float(float):
    def __init__(self, value):
        super(Float, self).__init__()
        self.__decimal = Decimal(value)

    @property
    def decimal(self):
        return self.__decimal

    def __repr__(self):
        return str(self.decimal)

    def __str__(self):
        return str(self.decimal)

    def __abs__(self, round=True, context=None):
        return Float(str(abs(self.decimal)))

    def __add__(self, other, context=None):
        if isinstance(other, Decimal):
            return self.decimal.__add__(other, context=context)
        return super(Float, self).__add__(other)

    def __radd__(self, other, context=None):
        if isinstance(other, Decimal):
            return self.decimal.__radd__(other, context=context)
        return super(Float, self).__radd__(other)

    def __div__(self, other, context=None):
        if isinstance(other, Decimal):
            return self.decimal.__div__(other, context=context)
        return super(Float, self).__div__(other)

    def __rdiv__(self, other, context=None):
        if isinstance(other, Decimal):
            return self.decimal.__rdiv__(other, context=context)
        return super(Float, self).__rdiv__(other)

    def __divmod__(self, other, context=None):
        if isinstance(other, Decimal):
            return self.decimal.__divmod__(other, context=context)
        return super(Float, self).__divmod__(other)

    def __rdivmod__(self, other, context=None):
        if isinstance(other, Decimal):
            return self.decimal.__rdivmod__(other, context=context)
        return super(Float, self).__rdivmod__(other)

    def __eq__(self, other):
        if isinstance(other, Decimal):
            return self.decimal.__eq__(other)
        return super(Float, self).__eq__(other)

    def __hash__(self):
        return super(Float, self).__hash__()

    def __floordiv__(self, other, context=None):
        if isinstance(other, Decimal):
            return self.decimal.__floordiv__(other, context=context)
        return super(Float, self).__floordiv__(other)

    def __rfloordiv__(self, other, context=None):
        if isinstance(other, Decimal):
            return self.decimal.__rfloordiv__(other, context=context)
        return super(Float, self).__rfloordiv__(other)

    def __format__(self, specifier, context=None):
        return self.decimal.__format__(specifier, context=context)

    def __ge__(self, other, context=None):
        if isinstance(other, Decimal):
            if hasattr(self.decimal, '__ge__'):
                return self.decimal.__ge__(other, context=context)
            # For Python < 2.6
            return self.decimal >= other
        return super(Float, self).__ge__(other)

    def __gt__(self, other, context=None):
        if isinstance(other, Decimal):
            if hasattr(self.decimal, '__gt__'):
                return self.decimal.__gt__(other, context=context)
            # For Python < 2.6
            return self.decimal > other
        return super(Float, self).__gt__(other)

    def __le__(self, other, context=None):
        if isinstance(other, Decimal):
            if hasattr(self.decimal, '__le__'):
                return self.decimal.__le__(other, context=context)
            # For Python < 2.6
            return self.decimal <= other
        return super(Float, self).__le__(other)

    def __lt__(self, other, context=None):
        if isinstance(other, Decimal):
            if hasattr(self.decimal, '__lt__'):
                return self.decimal.__lt__(other, context=context)
            # For Python < 2.6
            return self.decimal < other
        return super(Float, self).__lt__(other)

    def __mod__(self, other, context=None):
        if isinstance(other, Decimal):
            return self.decimal.__mod__(other, context=context)
        return super(Float, self).__mod__(other)

    def __rmod__(self, other, context=None):
        if isinstance(other, Decimal):
            return self.decimal.__rmod__(other, context=context)
        return super(Float, self).__rmod__(other)

    def __mul__(self, other, context=None):
        if isinstance(other, Decimal):
            return self.decimal.__mul__(other, context=context)
        return super(Float, self).__mul__(other)

    def __rmul__(self, other, context=None):
        if isinstance(other, Decimal):
            return self.decimal.__rmul__(other, context=context)
        return super(Float, self).__rmul__(other)

    def __ne__(self, other):
        if isinstance(other, Decimal):
            return self.decimal.__ne__(other)
        return super(Float, self).__ne__(other)

    def __neg__(self, context=None):
        return Float(str(-self.decimal))

    def __nonzero__(self):
        return self.decimal.__nonzero__()

    def __pos__(self):
        return Float(str(self.decimal))

    def __pow__(self, other, modulo=None, context=None):
        if isinstance(other, Decimal):
            return self.decimal.__pow__(other, modulo, context)
        return super(Float, self).__pow__(other, modulo)

    def __rpow__(self, other, context=None):
        if isinstance(other, Decimal):
            return self.decimal.__rpow__(other, context=context)
        return super(Float, self).__rpow__(other)

    def __sub__(self, other, context=None):
        if isinstance(other, Decimal):
            return self.decimal.__sub__(other, context=context)
        return super(Float, self).__sub__(other)

    def __rsub__(self, other, context=None):
        if isinstance(other, Decimal):
            return self.decimal.__rsub__(other, context=context)
        return super(Float, self).__rsub__(other)

    def __truediv__(self, other, context=None):
        if isinstance(other, Decimal):
            return self.decimal.__truediv__(other, context=context)
        return super(Float, self).__truediv__(other)

    def __getattr__(self, name):
        return getattr(self.decimal, name)
