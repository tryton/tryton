# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool, PoolMeta
from trytond.model import fields
from trytond.pyson import Eval


class TaxRule(metaclass=PoolMeta):
    __name__ = 'account.tax.rule'

    def apply(self, tax, pattern):
        pool = Pool()
        Subdivision = pool.get('country.subdivision')

        def parents(subdivision):
            while subdivision:
                yield subdivision.id
                subdivision = subdivision.parent

        pattern = pattern.copy()
        for name in ['from_subdivision', 'to_subdivision']:
            subdivision = pattern.pop(name, None)
            if not subdivision:
                continue
            subdivision = Subdivision(subdivision)
            pattern[name] = list(parents(subdivision))
        return super().apply(tax, pattern)


class _TaxRuleLineMixin:
    __slots__ = ()
    from_country = fields.Many2One(
        'country.country', 'From Country', ondelete='RESTRICT',
        help="Apply only to addresses of this country.")
    from_subdivision = fields.Many2One(
        'country.subdivision', "From Subdivision", ondelete='RESTRICT',
        domain=[
            ('country', '=', Eval('from_country', -1)),
            ],
        states={
            'invisible': ~Eval('from_country'),
            },
        depends=['from_country'],
        help="Apply only to addresses in this subdivision.")
    to_country = fields.Many2One(
        'country.country', 'To Country', ondelete='RESTRICT',
        help="Apply only to addresses of this country.")
    to_subdivision = fields.Many2One(
        'country.subdivision', "To Subdivision", ondelete='RESTRICT',
        domain=[
            ('country', '=', Eval('to_country', -1)),
            ],
        states={
            'invisible': ~Eval('to_country'),
            },
        depends=['to_country'],
        help="Apply only to addresses in this subdivision.")


class TaxRuleLineTemplate(_TaxRuleLineMixin, metaclass=PoolMeta):
    __name__ = 'account.tax.rule.line.template'

    def _get_tax_rule_line_value(self, rule_line=None):
        value = super(TaxRuleLineTemplate, self)._get_tax_rule_line_value(
            rule_line=rule_line)
        if not rule_line or rule_line.from_country != self.from_country:
            value['from_country'] = (
                self.from_country.id if self.from_country else None)
        if (not rule_line
                or rule_line.from_subdivision != self.from_subdivision):
            value['from_subdivision'] = (
                self.from_subdivision.id if self.from_subdivision else None)
        if not rule_line or rule_line.to_country != self.to_country:
            value['to_country'] = (
                self.to_country.id if self.to_country else None)
        if (not rule_line
                or rule_line.to_subdivision != self.to_subdivision):
            value['to_subdivision'] = (
                self.to_subdivision.id if self.to_subdivision else None)
        return value


class TaxRuleLine(_TaxRuleLineMixin, metaclass=PoolMeta):
    __name__ = 'account.tax.rule.line'

    def match(self, pattern):
        for name in ['from_subdivision', 'to_subdivision']:
            subdivision = getattr(self, name)
            if name not in pattern:
                if subdivision:
                    return False
                else:
                    continue
            pattern = pattern.copy()
            subdivisions = pattern.pop(name)
            if (subdivision is not None
                    and subdivision.id not in subdivisions):
                return False
        return super().match(pattern)


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @fields.depends('origin')
    def _get_tax_rule_pattern(self):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        PurchaseLine = pool.get('purchase.line')

        pattern = super(InvoiceLine, self)._get_tax_rule_pattern()

        from_country = from_subdivision = to_country = to_subdivision = None
        if isinstance(self.origin, SaleLine):
            warehouse_address = self.origin.warehouse.address
            if warehouse_address:
                from_country = warehouse_address.country
                from_subdivision = warehouse_address.subdivision
            shipment_address = self.origin.sale.shipment_address
            to_country = shipment_address.country
            to_subdivision = shipment_address.subdivision
        elif isinstance(self.origin, PurchaseLine):
            invoice_address = self.origin.purchase.invoice_address
            from_country = invoice_address.country
            from_subdivision = invoice_address.subdivision
            warehouse_address = self.origin.purchase.warehouse.address
            if warehouse_address:
                to_country = warehouse_address.country
                to_subdivision = warehouse_address.subdivision

        pattern['from_country'] = from_country.id if from_country else None
        pattern['from_subdivision'] = (
            from_subdivision.id if from_subdivision else None)
        pattern['to_country'] = to_country.id if to_country else None
        pattern['to_subdivision'] = (
            to_subdivision.id if to_subdivision else None)
        return pattern
