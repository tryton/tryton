# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.pyson import Eval

__all__ = ['Purchase', 'PurchaseLine']


class Purchase:
    __metaclass__ = PoolMeta
    __name__ = 'purchase.purchase'

    @classmethod
    def __setup__(cls):
        super(Purchase, cls).__setup__()
        for field in (cls.invoice_address, cls.warehouse):
            field.states['readonly'] |= (
                Eval('lines', [0]) & Eval('invoice_address'))
            field.depends.extend(['invoice_address'])


class PurchaseLine:
    __metaclass__ = PoolMeta
    __name__ = 'purchase.line'

    def _get_tax_rule_pattern(self):
        pattern = super(PurchaseLine, self)._get_tax_rule_pattern()

        from_country, to_country = None, None
        if self.purchase:
            if self.purchase.invoice_address:
                from_country = self.purchase.invoice_address.country
            warehouse = self.purchase.warehouse
            if warehouse and warehouse.address:
                to_country = warehouse.address.country

        pattern['from_country'] = from_country.id if from_country else None
        pattern['to_country'] = to_country.id if to_country else None
        return pattern

    @fields.depends('_parent_purchase.warehouse',
        '_parent_purchase.invoice_address')
    def on_change_product(self):
        super(PurchaseLine, self).on_change_product()
