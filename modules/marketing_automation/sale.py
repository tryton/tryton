# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta

from .mixin import MarketingAutomationMixin


class Sale(MarketingAutomationMixin, metaclass=PoolMeta):
    __name__ = 'sale.sale'

    def get_marketing_party(self, name):
        return self.party.id

    @classmethod
    def search_marketing_party(cls, name, clause):
        nested = clause[0][len(name):]
        return [('party' + nested, *clause[1:])]
