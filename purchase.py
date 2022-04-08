# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval


class Purchase(metaclass=PoolMeta):
    __name__ = 'purchase.purchase'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.party.states['readonly'] = (cls.party.states['readonly']
            | Eval('lines', [0]))
        cls.lines.states['readonly'] = (cls.lines.states['readonly']
            | ~Eval('party'))


class Line(metaclass=PoolMeta):
    __name__ = 'purchase.line'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.product.context['supplier'] = Eval(
            '_parent_purchase', {}).get('party')
