# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal

from sql import Null

from trytond.pool import PoolMeta, Pool
from trytond.model import (
    ModelSQL, ModelView, MatchMixin, Workflow, DeactivableMixin, fields,
    sequence_ordered)
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

        super(Sale, cls).quote(sales)

        lines_to_delete = []
        for sale in sales:
            sale.set_extra(lines_to_delete)
        if lines_to_delete:
            Line.delete(lines_to_delete)
        cls.save(sales)

    def set_extra(self, lines_to_delete):
        'Set extra lines and fill lines_to_delete'
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
                lines_to_delete.append(line)
        if extra2lines:
            lines.extend(extra2lines.values())
        self.lines = lines


class Line(metaclass=PoolMeta):
    __name__ = 'sale.line'

    extra = fields.Many2One('sale.extra.line', 'Extra', ondelete='RESTRICT')


class Extra(DeactivableMixin, ModelSQL, ModelView, MatchMixin):
    'Sale Extra'
    __name__ = 'sale.extra'

    name = fields.Char('Name', translate=True, required=True)
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': Eval('id', 0) > 0,
            },
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        select=True)
    start_date = fields.Date('Start Date',
        domain=['OR',
            ('start_date', '<=', If(~Eval('end_date', None),
                    datetime.date.max,
                    Eval('end_date', datetime.date.max))),
            ('start_date', '=', None),
            ],
        depends=['end_date'])
    end_date = fields.Date('End Date',
        domain=['OR',
            ('end_date', '>=', If(~Eval('start_date', None),
                    datetime.date.min,
                    Eval('start_date', datetime.date.min))),
            ('end_date', '=', None),
            ],
        depends=['start_date'])
    price_list = fields.Many2One('product.price_list', 'Price List',
        ondelete='CASCADE',
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    sale_amount = fields.Numeric('Sale Amount',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    lines = fields.One2Many('sale.extra.line', 'extra', 'Lines')

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        PriceList = pool.get('product.price_list')
        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()
        price_list = PriceList.__table__()

        super().__register__(module_name)

        table = cls.__table_handler__(module_name)
        # Migration from 3.6: price_list not required and new company
        table.not_null_action('price_list', 'remove')
        query = sql_table.join(price_list,
            condition=sql_table.price_list == price_list.id
            ).select(sql_table.id, price_list.company,
                where=sql_table.company == Null)
        cursor.execute(*query)
        for extra_id, company_id in cursor.fetchall():
            query = sql_table.update([sql_table.company], [company_id],
                where=sql_table.id == extra_id)
            cursor.execute(*query)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @fields.depends('company')
    def on_change_with_currency_digits(self, name=None):
        if self.company:
            return self.company.currency.digits
        return 2

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
    def get_lines(cls, sale, pattern=None):
        'Yield extra sale lines'
        pool = Pool()
        Currency = pool.get('currency.currency')
        extras = cls.search(cls._extras_domain(sale))
        if pattern is None:
            pattern = {}
        else:
            pattern = pattern.copy()
        pattern['sale_amount'] = Currency.compute(sale.currency,
            sale.untaxed_amount, sale.company.currency)

        for extra in extras:
            epattern = pattern.copy()
            epattern.update(extra.get_pattern(sale))
            if extra.match(epattern):
                for line in extra.lines:
                    lpattern = epattern.copy()
                    lpattern.update(line.get_pattern(sale))
                    if line.match(lpattern):
                        yield line.get_line(sale)
                        break

    def get_pattern(self, sale):
        return {}

    def match(self, pattern):
        pattern = pattern.copy()
        sale_amount = pattern.pop('sale_amount')

        match = super().match(pattern)

        if self.sale_amount is not None:
            if sale_amount < self.sale_amount:
                return False
        return match


class ExtraLine(sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    'Sale Extra Line'
    __name__ = 'sale.extra.line'

    extra = fields.Many2One('sale.extra', 'Extra', required=True,
        ondelete='CASCADE')
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
        super().__setup__()
        cls._order.insert(1, ('extra', 'ASC'))

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

    def get_pattern(self, sale):
        return {}

    def match(self, pattern):
        pattern = pattern.copy()
        sale_amount = pattern.pop('sale_amount')

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
