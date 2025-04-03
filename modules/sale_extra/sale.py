# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal

from trytond.model import (
    DeactivableMixin, MatchMixin, ModelSQL, ModelView, Workflow, fields,
    sequence_ordered)
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If
from trytond.transaction import Transaction


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @classmethod
    @ModelView.button
    @Workflow.transition('quotation')
    def quote(cls, sales):
        pool = Pool()
        Line = pool.get('sale.line')

        super().quote(sales)

        # State must be draft to add or delete lines
        # because extra must be set after to have correct amount
        cls.write(sales, {'state': 'draft'})
        removed = []
        for sale in sales:
            removed.extend(sale.set_extra())
        Line.delete(removed)
        cls.save(sales)
        # Reset to quotation state to avoid duplicate log entries
        cls.write(sales, {'state': 'quotation'})

    def set_extra(self):
        'Set extra lines and fill lines_to_delete'
        pool = Pool()
        Extra = pool.get('sale.extra')
        removed = []
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
                removed.append(line)
        if extra2lines:
            lines.extend(extra2lines.values())
        self.lines = lines
        return removed


class Line(metaclass=PoolMeta):
    __name__ = 'sale.line'

    extra = fields.Many2One('sale.extra.line', 'Extra', ondelete='RESTRICT')


class Extra(DeactivableMixin, ModelSQL, ModelView, MatchMixin):
    __name__ = 'sale.extra'

    name = fields.Char('Name', translate=True, required=True)
    company = fields.Many2One(
        'company.company', "Company", required=True,
        states={
            'readonly': Eval('id', 0) > 0,
            })
    start_date = fields.Date('Start Date',
        domain=['OR',
            ('start_date', '<=', If(~Eval('end_date', None),
                    datetime.date.max,
                    Eval('end_date', datetime.date.max))),
            ('start_date', '=', None),
            ])
    end_date = fields.Date('End Date',
        domain=['OR',
            ('end_date', '>=', If(~Eval('start_date', None),
                    datetime.date.min,
                    Eval('start_date', datetime.date.min))),
            ('end_date', '=', None),
            ])
    price_list = fields.Many2One('product.price_list', 'Price List',
        ondelete='CASCADE',
        domain=[
            ('company', '=', Eval('company', -1)),
            ])
    sale_amount = Monetary(
        "Sale Amount", currency='currency', digits='currency')
    currency = fields.Function(fields.Many2One(
            'currency.currency', "Currency"),
        'on_change_with_currency')
    lines = fields.One2Many('sale.extra.line', 'extra', 'Lines')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @fields.depends('company')
    def on_change_with_currency(self, name=None):
        return self.company.currency if self.company else None

    @classmethod
    def _extras_domain(cls, sale):
        return [
            ['OR',
                ('start_date', '<=', sale.sale_date),
                ('start_date', '=', None),
                ],
            ['OR',
                ('end_date', '=', None),
                ('end_date', '>=', sale.sale_date),
                ],
            ['OR',
                ('price_list', '=', None),
                ('price_list', '=',
                    sale.price_list.id if sale.price_list else None),
                ],
            ('company', '=', sale.company.id),
            ]

    @classmethod
    def get_lines(cls, sale, pattern=None, line_pattern=None):
        'Yield extra sale lines'
        pool = Pool()
        Currency = pool.get('currency.currency')
        extras = cls.search(cls._extras_domain(sale))
        pattern = pattern.copy() if pattern is not None else {}
        line_pattern = line_pattern.copy() if line_pattern is not None else {}
        sale_amount = Currency.compute(
            sale.currency, sale.untaxed_amount, sale.company.currency)
        pattern.setdefault('sale_amount', sale_amount)
        line_pattern.setdefault('sale_amount', sale_amount)

        for extra in extras:
            if extra.match(pattern):
                for line in extra.lines:
                    if line.match(line_pattern):
                        yield line.get_line(sale)
                        break

    def match(self, pattern):
        pattern = pattern.copy()
        sale_amount = pattern.pop('sale_amount')

        match = super().match(pattern)

        if self.sale_amount is not None:
            if sale_amount < self.sale_amount:
                return False
        return match


class ExtraLine(sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    __name__ = 'sale.extra.line'

    extra = fields.Many2One('sale.extra', 'Extra', required=True,
        ondelete='CASCADE')
    sale_amount = Monetary(
        "Sale Amount", currency='currency', digits='currency')
    product = fields.Many2One('product.product', 'Product', required=True,
        domain=[('salable', '=', True)])
    product_uom_category = fields.Function(
        fields.Many2One('product.uom.category', 'Product UoM Category'),
        'on_change_with_product_uom_category')
    quantity = fields.Float("Quantity", digits='unit', required=True)
    unit = fields.Many2One('product.uom', 'Unit', required=True,
        domain=[
            ('category', '=', Eval('product_uom_category', -1)),
            ])
    free = fields.Boolean('Free')
    currency = fields.Function(fields.Many2One(
            'currency.currency', "Currency"),
        'on_change_with_currency')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('extra')
        cls._order.insert(1, ('extra', 'ASC'))

    @fields.depends('product')
    def on_change_with_product_uom_category(self, name=None):
        return self.product.default_uom_category if self.product else None

    @fields.depends('product')
    def on_change_product(self):
        if self.product:
            self.unit = self.product.sale_uom

    @staticmethod
    def default_free():
        return False

    @fields.depends('extra', '_parent_extra.currency')
    def on_change_with_currency(self, name=None):
        return self.extra.currency if self.extra else None

    def match(self, pattern):
        pattern = pattern.copy()
        sale_amount = pattern.pop('sale_amount')

        if (not self.product.active
                or not self.product.salable):
            return False

        match = super().match(pattern)

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
