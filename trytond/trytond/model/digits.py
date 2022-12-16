# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.cache import Cache
from trytond.rpc import RPC


class DigitsMixin:
    __slots__ = ()

    _digits_cache = Cache('_digits_mixin..get_digits', context=False)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__rpc__.update({
                'get_digits': RPC(instantiate=0, cache=dict(days=1)),
                })

    def get_digits(self):
        key = str(self)
        digits = self._digits_cache.get(key)
        if digits is not None:
            return digits
        digits = self._get_digits()
        self._digits_cache.set(key, digits)
        return digits

    def _get_digits(self):
        return (16, self.digits)

    @classmethod
    def write(cls, *args):
        super().write(*args)
        cls._digits_cache.clear()
