# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal

from simpleeval import simple_eval

from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, MatchMixin, ModelSQL, ModelView, Workflow, fields)
from trytond.modules.currency.fields import Monetary
from trytond.modules.product import price_digits, round_price
from trytond.modules.product_price_list import Null
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, If
from trytond.tools import decistmt
from trytond.transaction import Transaction

from .exceptions import FormulaError


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    original_untaxed_amount = fields.Function(Monetary(
            "Original Untaxed", digits='currency', currency='currency',
            states={
                'invisible': (
                    ~Eval('state').in_(['draft', 'quotation'])
                    | (Eval('original_untaxed_amount')
                        == Eval('untaxed_amount'))),
                }),
        'get_original_amount')
    original_tax_amount = fields.Function(Monetary(
            "Original Tax", digits='currency', currency='currency',
            states={
                'invisible': (
                    ~Eval('state').in_(['draft', 'quotation'])
                    | (Eval('original_tax_amount') == Eval('tax_amount'))),
                }),
        'get_original_amount')
    original_total_amount = fields.Function(Monetary(
            "Original Total", digits='currency', currency='currency',
            states={
                'invisible': (
                    ~Eval('state').in_(['draft', 'quotation'])
                    | (Eval('original_total_amount') == Eval('total_amount'))),
                }),
        'get_original_amount')

    def get_original_amount(self, names):
        amounts = dict.fromkeys(names)
        if self.state in {'draft', 'quotation'}:
            amounts['original_untaxed_amount'] = sum(
                (line.original_amount for line in self.line_lines), Decimal(0))
            if {'original_tax_amount', 'original_total_amount'} & set(names):
                with Transaction().set_context(_original_amount=True):
                    amounts['original_tax_amount'] = self.get_tax_amount()
                amounts['original_total_amount'] = sum(
                    filter(None, amounts.values()))
        return amounts

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, sales):
        super().draft(sales)
        # Reset to draft unit price
        for sale in sales:
            sale.unapply_promotion()
        cls.save(sales)

    @classmethod
    @ModelView.button
    @Workflow.transition('quotation')
    def quote(cls, sales):
        super().quote(sales)
        # Store draft unit price before changing it
        for sale in sales:
            sale.apply_promotion()
        cls.save(sales)

    def unapply_promotion(self):
        "Unapply promotion"
        changed = False
        for line in self.lines:
            if line.type != 'line':
                continue
            if line.original_unit_price is not None:
                line.unit_price = line.original_unit_price
                line.original_unit_price = None
                changed = True
            if line.promotion:
                line.promotion = None
                changed = True
        if changed:
            self.lines = self.lines  # Trigger changes

    def apply_promotion(self):
        "Apply promotion"
        pool = Pool()
        Promotion = pool.get('sale.promotion')

        for line in self.lines:
            if line.type == 'line' and line.original_unit_price is None:
                line.original_unit_price = line.unit_price

        promotions = Promotion.get_promotions(self)
        for promotion in promotions:
            promotion.apply(self)


class Line(metaclass=PoolMeta):
    __name__ = 'sale.line'

    original_unit_price = Monetary(
        "Original Unit Price", digits=price_digits, currency='currency',
        readonly=True,
        states={
            'required': Bool(Eval('promotion', None)),
            'invisible': ~Eval('promotion'),
            })
    original_amount = fields.Function(Monetary(
            "Original Amount", digits='currency', currency='currency',
            states={
                'invisible': ~Eval('promotion'),
                }),
        'get_original_amount')
    promotion = fields.Many2One('sale.promotion', "Promotion",
        ondelete='RESTRICT',
        domain=[
            ('company', '=', Eval('company', -1)),
            ])

    @classmethod
    def __register__(cls, module):
        table_h = cls.__table_handler__(module)
        # Migration from 7.4: rename draft_unit_price
        table_h.column_rename('draft_unit_price', 'original_unit_price')
        super().__register__(module)

    def get_original_amount(self, name):
        currency = self.sale.currency

        def _amount(line):
            return currency.round(
                Decimal(str(line.quantity))
                * (line.original_unit_price or line.unit_price))

        if self.type == 'line':
            return _amount(self)
        elif self.type == 'subtotal':
            amount = Decimal(0)
            for line2 in self.sale.lines:
                if line2.type == 'line':
                    amount += _amount(line2)
                elif line2.type == 'subtotal':
                    if self == line2:
                        break
                    amount = Decimal(0)
            return amount

    @property
    def taxable_lines(self):
        lines = super().taxable_lines
        if (getattr(self, 'type', None) == 'line'
                and Transaction().context.get('_original_amount')):
            lines = [(
                    getattr(self, 'taxes', None) or [],
                    getattr(self, 'original_unit_price', None)
                    or getattr(self, 'unit_price', None)
                    or Decimal(0),
                    getattr(self, 'quantity', None) or 0,
                    None,
                    )]
        return lines


class Promotion(
        DeactivableMixin, ModelSQL, ModelView, MatchMixin):
    __name__ = 'sale.promotion'

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

    amount = Monetary("Amount", currency='currency', digits='currency')
    currency = fields.Many2One(
        'currency.currency', "Currency",
        states={
            'required': Bool(Eval('amount', 0)),
            })
    untaxed_amount = fields.Boolean(
        "Untaxed Amount",
        states={
            'invisible': ~Eval('amount'),
            })

    quantity = fields.Float('Quantity', digits='unit')
    unit = fields.Many2One('product.uom', 'Unit',
        states={
            'required': Bool(Eval('quantity', 0)),
            })
    products = fields.Many2Many(
        'sale.promotion-product.product', 'promotion', 'product', "Products",
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    categories = fields.Many2Many(
        'sale.promotion-product.category', 'promotion', 'category',
        "Categories",
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    formula = fields.Char('Formula', required=True,
        help=('Python expression that will be evaluated with:\n'
            '- unit_price: the original unit_price'))

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def default_untaxed_amount(cls):
        return False

    @classmethod
    def validate_fields(cls, promotions, field_names):
        super().validate_fields(promotions, field_names)
        cls.check_formula(promotions, field_names)

    @classmethod
    def check_formula(cls, promotions, field_names=None):
        if field_names and 'formula' not in field_names:
            return
        for promotion in promotions:
            context = promotion.get_context_formula(None)
            try:
                unit_price = promotion.get_unit_price(**context)
                if not isinstance(unit_price, Decimal):
                    raise ValueError('Not a Decimal')
            except Exception as exception:
                raise FormulaError(
                    gettext('sale_promotion.msg_invalid_formula',
                        formula=promotion.formula,
                        promotion=promotion.rec_name,
                        exception=exception)) from exception

    @classmethod
    def _promotions_domain(cls, sale):
        pool = Pool()
        Date = pool.get('ir.date')
        with Transaction().set_context(company=sale.company.id):
            sale_date = sale.sale_date or Date.today()
        return [
            ['OR',
                ('start_date', '<=', sale_date),
                ('start_date', '=', None),
                ],
            ['OR',
                ('end_date', '=', None),
                ('end_date', '>=', sale_date),
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
        Currency = pool.get('currency.currency')
        Uom = pool.get('product.uom')
        Sale = pool.get('sale.sale')
        pattern = {}
        if self.currency:
            amount = self.get_sale_amount(Sale(sale.id))
            pattern['amount'] = Currency.compute(
                sale.currency, amount, self.currency)
        if self.unit:
            quantity = 0
            for line in sale.lines:
                if line.type != 'line':
                    continue
                if self.is_valid_sale_line(line):
                    quantity += Uom.compute_qty(line.unit, line.quantity,
                        self.unit)
            pattern['quantity'] = quantity
        return pattern

    def match(self, pattern):
        def sign(amount):
            return Decimal(1).copy_sign(amount)
        if 'quantity' in pattern:
            pattern = pattern.copy()
            if (self.quantity or 0) > pattern.pop('quantity'):
                return False
        if 'amount' in pattern:
            pattern = pattern.copy()
            amount = pattern.pop('amount')
            if (sign(self.amount or 0) * sign(amount) >= 0
                    and abs(self.amount or 0) > abs(amount)):
                return False
        return super().match(pattern)

    def get_sale_amount(self, sale):
        if self.untaxed_amount:
            return sale.untaxed_amount
        else:
            return sale.total_amount

    def is_valid_sale_line(self, line):

        def parents(categories):
            for category in categories:
                while category:
                    yield category
                    category = category.parent

        if line.quantity <= 0 or line.unit_price <= 0:
            return False
        elif self.unit and line.unit.category != self.unit.category:
            return False
        elif self.products and line.product not in self.products:
            return False
        elif self.categories:
            if not line.product:
                return False
            categories = set(parents(line.product.categories_all))
            if not categories.intersection(self.categories):
                return False
        return True

    def apply(self, sale):
        applied = False
        for line in sale.lines:
            if line.type != 'line':
                continue
            if not self.is_valid_sale_line(line):
                continue
            context = self.get_context_formula(line)
            new_price = self.get_unit_price(**context)
            if new_price is not None:
                if new_price < 0:
                    new_price = Decimal(0)
                if line.unit_price >= new_price:
                    line.unit_price = round_price(new_price)
                    line.promotion = self
                    applied = True
        if applied:
            sale.lines = sale.lines  # Trigger the change

    def get_context_formula(self, sale_line):
        pool = Pool()
        Product = pool.get('product.product')
        if sale_line:
            with Transaction().set_context(
                    sale_line._get_context_sale_price()):
                prices = Product.get_sale_price([sale_line.product])
            unit_price = prices[sale_line.product.id]
        else:
            unit_price = Decimal(0)
        return {
            'names': {
                'unit_price': unit_price if unit_price is not None else Null(),
                },
            }

    def get_unit_price(self, **context):
        'Return unit price (as Decimal)'
        context.setdefault('functions', {})['Decimal'] = Decimal
        unit_price = simple_eval(decistmt(self.formula), **context)
        unit_price = max(unit_price, Decimal(0))
        if isinstance(unit_price, Null):
            unit_price = None
        return unit_price


class Promotion_Product(ModelSQL):
    __name__ = 'sale.promotion-product.product'

    promotion = fields.Many2One(
        'sale.promotion', "Promotion", required=True, ondelete='CASCADE')
    product = fields.Many2One('product.product', 'Product',
        required=True, ondelete='CASCADE')


class Promotion_ProductCategory(ModelSQL):
    __name__ = 'sale.promotion-product.category'

    promotion = fields.Many2One(
        'sale.promotion', "Promotion", required=True, ondelete='CASCADE')
    category = fields.Many2One(
        'product.category', "Category",
        required=True, ondelete='CASCADE')
