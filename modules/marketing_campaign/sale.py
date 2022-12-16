# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta

from .marketing import MarketingCampaignMixin, Parameter


class Sale(MarketingCampaignMixin, metaclass=PoolMeta):
    __name__ = 'sale.sale'


class Opportunity(MarketingCampaignMixin, metaclass=PoolMeta):
    __name__ = 'sale.opportunity'

    def _get_sale_opportunity(self):
        sale = super()._get_sale_opportunity()
        for fname, field in self._fields.items():
            if (field._type == 'many2one'
                    and isinstance(field.get_target(), Parameter)):
                setattr(sale, fname, getattr(self, fname))
        return sale


class POSSale(MarketingCampaignMixin, metaclass=PoolMeta):
    __name__ = 'sale.point.sale'
