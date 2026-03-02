# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import ROUND_HALF_EVEN

from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval


class Currency(metaclass=PoolMeta):
    __name__ = 'currency.currency'

    cash_rounding = fields.Numeric(
        "Cash Rounding Factor",
        digits=(12, Eval('digits', 6)),
        depends=['digits'])

    def cash_round(self, amount, rounding=ROUND_HALF_EVEN):
        if self.cash_rounding is not None:
            factor = self.cash_rounding
        else:
            factor = self.rounding
        return self._round(amount, factor, rounding)
