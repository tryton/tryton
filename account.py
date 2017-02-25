# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool, PoolMeta
from trytond.model import fields

__all__ = ['TaxRuleLineTemplate', 'TaxRuleLine', 'InvoiceLine']


class TaxRuleLineTemplate:
    __metaclass__ = PoolMeta
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


class TaxRuleLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.tax.rule.line'
    from_country = fields.Many2One('country.country', 'From Country',
        ondelete='RESTRICT')
    to_country = fields.Many2One('country.country', 'To Country',
        ondelete='RESTRICT')


class InvoiceLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice.line'

    def _get_tax_rule_pattern(self):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        PurchaseLine = pool.get('purchase.line')

        pattern = super(InvoiceLine, self)._get_tax_rule_pattern()

        from_country, to_country = None, None
        if isinstance(self.origin, SaleLine):
            if self.origin.warehouse.address:
                from_country = self.origin.warehouse.address.country
            to_country = self.origin.sale.shipment_address.country
        elif isinstance(self.origin, PurchaseLine):
            from_country = self.origin.purchase.invoice_address.country
            if self.origin.purchase.warehouse.address:
                to_country = self.origin.purchase.warehouse.address.country

        pattern['from_country'] = from_country.id if from_country else None
        pattern['to_country'] = to_country.id if to_country else None
        return pattern

    @fields.depends('origin')
    def on_change_product(self):
        super(InvoiceLine, self).on_change_product()

    @fields.depends('origin')
    def on_change_account(self):
        super(InvoiceLine, self).on_change_account()
