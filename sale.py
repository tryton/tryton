# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import PoolMeta, Pool
from trytond.model import ModelSQL, ModelView, MatchMixin, Workflow, fields
from trytond.pyson import Eval

__all__ = ['Sale', 'SaleLine',
    'SaleExtra', 'SaleExtraLine']
__metaclass__ = PoolMeta


class Sale:
    __name__ = 'sale.sale'

    @classmethod
    @ModelView.button
    @Workflow.transition('quotation')
    def quote(cls, sales):
        super(Sale, cls).quote(sales)
        for sale in sales:
            sale.set_extra()
        cls.save(sales)

    def set_extra(self):
        'Set extra lines'
        pool = Pool()
        Extra = pool.get('sale.extra')

        extra_lines = Extra.get_lines(self)
        extra2lines = {line.extra: line for line in extra_lines}
        lines = list(self.lines)
        for line in list(lines):
            if line.type != 'line' or not line.extra:
                continue
            if line.extra in extra2lines:
                del extra2lines[line.extra]
                continue
            else:
                lines.remove(line)
        if extra2lines:
            lines.extend(extra2lines.values())
        self.lines = lines


class SaleLine:
    __name__ = 'sale.line'

    extra = fields.Many2One('sale.extra.line', 'Extra', ondelete='RESTRICT')


class SaleExtra(ModelSQL, ModelView, MatchMixin):
    'Sale Extra'
    __name__ = 'sale.extra'

    name = fields.Char('Name', translate=True, required=True)
    active = fields.Boolean('Active')
    price_list = fields.Many2One('product.price_list', 'Price List',
        required=True, ondelete='CASCADE')
    sale_amount = fields.Numeric('Sale Amount',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    lines = fields.One2Many('sale.extra.line', 'extra', 'Lines')

    @staticmethod
    def default_active():
        return True

    @fields.depends('price_list')
    def on_change_with_currency_digits(self, name=None):
        if self.price_list.company:
            return self.price_list.company.currency.digits
        return 2

    @classmethod
    def get_lines(cls, sale, pattern=None):
        'Return extra sale lines'
        pool = Pool()
        Currency = pool.get('currency.currency')

        if not sale.price_list:
            return []

        if pattern is None:
            pattern = {}
        pattern['sale_amount'] = Currency.compute(sale.currency,
            sale.untaxed_amount, sale.company.currency)

        lines = []
        for extra in sale.price_list.sale_extras:
            if extra.match(pattern):
                for line in extra.lines:
                    if line.match(pattern):
                        lines.append(line.get_line(sale))
                        break
        return lines

    def match(self, pattern):
        pattern = pattern.copy()
        sale_amount = pattern.pop('sale_amount')

        match = super(SaleExtra, self).match(pattern)

        if self.sale_amount is not None:
            if sale_amount < self.sale_amount:
                return False
        return match


class SaleExtraLine(ModelSQL, ModelView, MatchMixin):
    'Sale Extra Line'
    __name__ = 'sale.extra.line'

    extra = fields.Many2One('sale.extra', 'Extra', required=True,
        ondelete='CASCADE')
    sequence = fields.Integer('Sequence')
    sale_amount = fields.Numeric('Sale Amount',
        digits=(16, Eval('_parent_extra', {}).get('currency_digits', 2)))
    product = fields.Many2One('product.product', 'Product', required=True,
        domain=[('salable', '=', True)])
    product_uom_category = fields.Function(
        fields.Many2One('product.uom.category', 'Product UoM Category'),
        'on_change_with_product_uom_category')
    quantity = fields.Float('Quantity',
        digits=(16, Eval('unit_digits', 2)), required=True,
        depends=['unit_digits'])
    unit = fields.Many2One('product.uom', 'Unit', required=True,
        domain=[
            ('category', '=', Eval('product_uom_category', -1)),
            ],
        depends=['product_uom_category'])
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'on_change_with_unit_digits')
    free = fields.Boolean('Free')

    @classmethod
    def __setup__(cls):
        super(SaleExtraLine, cls).__setup__()
        cls._order.insert(0, ('extra', 'ASC'))
        cls._order.insert(0, ('sequence', 'ASC'))

    @fields.depends('product')
    def on_change_with_product_uom_category(self, name=None):
        if self.product:
            return self.product.default_uom_category.id

    @fields.depends('unit')
    def on_change_with_unit_digits(self, name=None):
        if self.unit:
            return self.unit.digits
        return 2

    @fields.depends('product')
    def on_change_product(self):
        if self.product:
            self.unit = self.product.sale_uom

    @staticmethod
    def default_free():
        return False

    def match(self, pattern):
        pattern = pattern.copy()
        sale_amount = pattern.pop('sale_amount')

        match = super(SaleExtraLine, self).match(pattern)

        if self.sale_amount is not None:
            if sale_amount < self.sale_amount:
                return False
        return match

    def get_line(self, sale):
        pool = Pool()
        Line = pool.get('sale.line')

        sequence = None
        if sale.lines:
            last_line = sale.lines[-1]
            if last_line.sequence is not None:
                sequence = last_line.sequence + 1

        line = Line(
            sale=sale,
            sequence=sequence,
            type='line',
            product=self.product,
            quantity=self.quantity,
            unit=self.unit,
            extra=self,
            )
        line.on_change_product()
        if self.free:
            line.unit_price = line.amount = Decimal(0)
        return line
