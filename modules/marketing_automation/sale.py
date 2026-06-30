# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool, PoolMeta

from .mixin import MarketingAutomationMixin


class Sale(MarketingAutomationMixin, metaclass=PoolMeta):
    __name__ = 'sale.sale'

    def get_marketing_party(self, name):
        return self.party.id

    @classmethod
    def search_marketing_party(cls, name, clause):
        nested = clause[0][len(name):]
        return [('party' + nested, *clause[1:])]

    @property
    def marketing_access_context(self):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        context = super().marketing_access_context
        context.setdefault('_groups', []).append(
            ModelData.get_id('sale.group_sale'))
        context.setdefault('_companies', []).append(
            self.company.id)
        return context
