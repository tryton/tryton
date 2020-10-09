# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.rpc import RPC


class SymbolMixin(object):
    __slots__ = ()

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__rpc__.update({
                'get_symbol': RPC(instantiate=0, cache=dict(days=1)),
                })

    def get_symbol(self, sign, symbol=None):
        'Return the symbol and its position'
        position = 1
        if symbol is None:
            symbol = getattr(self, 'symbol', None)
        return symbol, position
