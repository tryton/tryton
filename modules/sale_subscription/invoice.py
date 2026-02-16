# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, If


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        if not cls.origin.domain:
            cls.origin.domain = {}
        cls.origin.domain['sale.subscription.line'] = [
            If(Bool(Eval('_parent_invoice')),
                If(Eval('_parent_invoice', {}).get('type') != 'out',
                    ('id', '=', -1),
                    ()),
                If(Eval('invoice_type') != 'out',
                    ('id', '=', -1),
                    ())),
            ]

    @property
    def origin_name(self):
        pool = Pool()
        SubscriptionLine = pool.get('sale.subscription.line')
        name = super().origin_name
        if isinstance(self.origin, SubscriptionLine) and self.origin.id >= 0:
            name = self.origin.subscription.rec_name
        return name

    @classmethod
    def _get_origin(cls):
        models = super()._get_origin()
        models.append('sale.subscription.line')
        return models
