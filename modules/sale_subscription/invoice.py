# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @property
    def origin_name(self):
        pool = Pool()
        SubscriptionLine = pool.get('sale.subscription.line')
        name = super(InvoiceLine, self).origin_name
        if isinstance(self.origin, SubscriptionLine):
            name = self.origin.subscription.rec_name
        return name

    @classmethod
    def _get_origin(cls):
        models = super(InvoiceLine, cls)._get_origin()
        models.append('sale.subscription.line')
        return models
