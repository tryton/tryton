# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal

from simpleeval import simple_eval

from trytond.pool import PoolMeta, Pool
from trytond.model import ModelSQL, ModelView, MatchMixin, Workflow, fields
from trytond.pyson import Eval, If, Bool
from trytond.transaction import Transaction
from trytond.tools import decistmt

from trytond.modules.product import price_digits

__all__ = ['Sale', 'SaleLine',
    'SalePromotion', 'SalePromotion_Product']


class Sale:
    __metaclass__ = PoolMeta
    __name__ = 'sale.sale'

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, sales):
        super(Sale, cls).draft(sales)
        # Reset to draft unit price
        for sale in sales:
            changed = False
            for line in sale.lines:
                if line.type != 'line':
                    continue
                if line.draft_unit_price is not None:
                    line.unit_price = line.draft_unit_price
                    line.draft_unit_price = None
                    changed = True
            if changed:
                sale.lines = sale.lines  # Trigger changes
        cls.save(sales)

    @classmethod
    @ModelView.button
    @Workflow.transition('quotation')
    def quote(cls, sales):
        super(Sale, cls).quote(sales)
        # Store draft unit price before changing it
        for sale in sales:
            for line in sale.lines:
                if line.type != 'line':
                    continue
                if line.draft_unit_price is None:
                    line.draft_unit_price = line.unit_price
            sale.apply_promotion()
        cls.save(sales)

    def apply_promotion(self):
        'Apply promotion'
        pool = Pool()
        Promotion = pool.get('sale.promotion')

        promotions = Promotion.get_promotions(self)
        for promotion in promotions:
            promotion.apply(self)


class SaleLine:
    __metaclass__ = PoolMeta
    __name__ = 'sale.line'

    draft_unit_price = fields.Numeric('Draft Unit Price',
        digits=price_digits, readonly=True)
    promotion = fields.Many2One('sale.promotion', 'Promotion',
        ondelete='RESTRICT',
        domain=[
            ('company', '=', Eval('_parent_sale', {}).get('company', -1)),
            ])


class SalePromotion(ModelSQL, ModelView, MatchMixin):
    'Sale Promotion'
    __name__ = 'sale.promotion'

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
    active = fields.Boolean('Active')
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
    quantity = fields.Float('Quantity', digits=(16, Eval('unit_digits', 2)),
        depends=['unit_digits'])
    unit = fields.Many2One('product.uom', 'Unit',
        states={
            'required': Bool(Eval('quantity', 0)),
            },
        depends=['quantity'])
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'on_change_with_unit_digits')
    unit_category = fields.Function(fields.Many2One('product.uom.category',
            'Unit Category'), 'on_change_with_unit_category')
    products = fields.Many2Many('sale.promotion-product.product',
        'promotion', 'product', 'Products',
        domain=[
            ('default_uom_category', '=', Eval('unit_category')),
            ],
        depends=['unit_category'])
    formula = fields.Char('Formula', required=True,
        help=('Python expression that will be evaluated with:\n'
            '- unit_price: the original unit_price'))

    @classmethod
    def __setup__(cls):
        super(SalePromotion, cls).__setup__()
        cls._error_messages.update({
                'invalid_formula': ('Invalid formula "%(formula)s" '
                    'in promotion "%(promotion)s" '
                    'with exception "%(exception)s".'),
                })

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_active():
        return True

    @fields.depends('unit')
    def on_change_with_unit_digits(self, name=None):
        if self.unit:
            return self.unit.digits
        return 2

    @fields.depends('unit')
    def on_change_with_unit_category(self, name=None):
        if self.unit:
            return self.unit.category.id

    @classmethod
    def validate(cls, promotions):
        super(SalePromotion, cls).validate(promotions)
        for promotion in promotions:
            promotion.check_formula()

    def check_formula(self):
        context = self.get_context_formula(None)
        try:
            if not isinstance(self.get_unit_price(**context), Decimal):
                raise ValueError('Not a Decimal')
        except Exception, exception:
            self.raise_user_error('invalid_formula', {
                    'formula': self.formula,
                    'promotion': self.rec_name,
                    'exception': exception,
                    })

    @classmethod
    def _promotions_domain(cls, sale):
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
    def get_promotions(cls, sale, pattern=None):
        'Yield promotions that apply to sale'
        promotions = cls.search(cls._promotions_domain(sale))
        if pattern is None:
            pattern = {}
        for promotion in promotions:
            ppattern = pattern.copy()
            ppattern.update(promotion.get_pattern(sale))
            if promotion.match(ppattern):
                yield promotion

    def get_pattern(self, sale):
        pool = Pool()
        Uom = pool.get('product.uom')
        pattern = {}
        if not self.unit:
            return pattern
        quantity = 0
        for line in sale.lines:
            if self.is_valid_sale_line(line):
                quantity += Uom.compute_qty(line.unit, line.quantity,
                    self.unit)
        pattern['quantity'] = quantity
        return pattern

    def match(self, pattern):
        if 'quantity' in pattern:
            pattern = pattern.copy()
            if self.quantity > pattern.pop('quantity'):
                return False
        return super(SalePromotion, self).match(pattern)

    def is_valid_sale_line(self, line):
        if self.products:
            return line.product in self.products
        elif self.unit:
            return line.unit.category == self.unit.category
        else:
            return True

    def apply(self, sale):
        new_prices = {}
        for line in sale.lines:
            if line.type != 'line':
                continue
            if not self.is_valid_sale_line(line):
                continue
            context = self.get_context_formula(line)
            new_prices[line] = self.get_unit_price(**context)

        # Apply promotion only if all unit prices decrease
        if all(l.unit_price >= p for l, p in new_prices.iteritems()):
            for line, unit_price in new_prices.iteritems():
                line.unit_price = unit_price
                line.promotion = self
            sale.lines = sale.lines  # Trigger the change

    def get_context_formula(self, sale_line):
        pool = Pool()
        Product = pool.get('product.product')
        if sale_line:
            with Transaction().set_context(uom=sale_line.unit.id,
                    currency=sale_line.sale.currency.id):
                prices = Product.get_sale_price([sale_line.product])
            unit_price = prices[sale_line.product.id]
        else:
            unit_price = Decimal(0)
        return {
            'names': {
                'unit_price': unit_price,
                },
            }

    def get_unit_price(self, **context):
        'Return unit price (as Decimal)'
        context.setdefault('functions', {})['Decimal'] = Decimal
        return simple_eval(decistmt(self.formula), **context)


class SalePromotion_Product(ModelSQL):
    'Sale Promotion - Product'
    __name__ = 'sale.promotion-product.product'

    promotion = fields.Many2One('sale.promotion', 'Promotion',
        required=True, ondelete='CASCADE', select=True)
    product = fields.Many2One('product.product', 'Product',
        required=True, ondelete='CASCADE')
