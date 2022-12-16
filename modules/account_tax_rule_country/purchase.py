# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.pyson import Eval


class Purchase(metaclass=PoolMeta):
    __name__ = 'purchase.purchase'

    @classmethod
    def __setup__(cls):
        super(Purchase, cls).__setup__()
        for field in (cls.invoice_address, cls.warehouse):
            field.states['readonly'] |= (
                Eval('lines', [0]) & Eval('invoice_address'))
            field.depends.extend(['invoice_address'])


class Line(metaclass=PoolMeta):
    __name__ = 'purchase.line'

    @fields.depends('purchase', '_parent_purchase.warehouse',
        '_parent_purchase.invoice_address')
    def _get_tax_rule_pattern(self):
        pattern = super()._get_tax_rule_pattern()

        from_country = from_subdivision = to_country = to_subdivision = None
        if self.purchase:
            if self.purchase.invoice_address:
                from_country = self.purchase.invoice_address.country
                from_subdivision = self.purchase.invoice_address.subdivision
            warehouse = self.purchase.warehouse
            if warehouse and warehouse.address:
                to_country = warehouse.address.country
                to_subdivision = warehouse.address.subdivision

        pattern['from_country'] = from_country.id if from_country else None
        pattern['from_subdivision'] = (
            from_subdivision.id if from_subdivision else None)
        pattern['to_country'] = to_country.id if to_country else None
        pattern['to_subdivision'] = (
            to_subdivision.id if to_subdivision else None)
        return pattern
