# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool, PoolMeta
from trytond.model import fields

__all__ = ['TaxRuleLineTemplate', 'TaxRuleLine', 'InvoiceLine']


class TaxRuleLineTemplate(metaclass=PoolMeta):
    __name__ = 'account.tax.rule.line.template'
    from_country = fields.Many2One('country.country', 'From Country',
        ondelete='RESTRICT')
    to_country = fields.Many2One('country.country', 'To Country',
        ondelete='RESTRICT')

    def _get_tax_rule_line_value(self, rule_line=None):
        value = super(TaxRuleLineTemplate, self)._get_tax_rule_line_value(
            rule_line=rule_line)
        if not rule_line or rule_line.from_country != self.from_country:
            value['from_country'] = (
                self.from_country.id if self.from_country else None)
        if not rule_line or rule_line.to_country != self.to_country:
            value['to_country'] = (
                self.to_country.id if self.to_country else None)
        return value


class TaxRuleLine(metaclass=PoolMeta):
    __name__ = 'account.tax.rule.line'
    from_country = fields.Many2One('country.country', 'From Country',
        ondelete='RESTRICT')
    to_country = fields.Many2One('country.country', 'To Country',
        ondelete='RESTRICT')


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @fields.depends('origin')
    def _get_tax_rule_pattern(self):
        pool = Pool()
        try:
            SaleLine = pool.get('sale.line')
        except KeyError:
            SaleLine = None
        try:
            PurchaseLine = pool.get('purchase.line')
        except KeyError:
            PurchaseLine = None

        pattern = super(InvoiceLine, self)._get_tax_rule_pattern()

        from_country, to_country = None, None
        if (SaleLine
                and isinstance(self.origin, SaleLine)
                and self.origin.id >= 0):
            warehouse = self.origin.warehouse
            if warehouse and warehouse.address:
                from_country = warehouse.address.country
            shipment_address = self.origin.sale.shipment_address
            to_country = shipment_address.country
        elif (PurchaseLine
                and isinstance(self.origin, PurchaseLine)
                and self.origin.id >= 0):
            invoice_address = self.origin.purchase.invoice_address
            from_country = invoice_address.country
            warehouse = self.origin.purchase.warehouse
            if warehouse and warehouse.address:
                to_country = warehouse.address.country

        pattern['from_country'] = from_country.id if from_country else None
        pattern['to_country'] = to_country.id if to_country else None
        return pattern
