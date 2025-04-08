# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from simpleeval import simple_eval

from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, MatchMixin, ModelSQL, ModelView, fields,
    sequence_ordered)
from trytond.modules.product import round_price
from trytond.pool import Pool
from trytond.tools.decimal_ import DecimalNull as Null
from trytond.tools.decimal_ import decistmt
from trytond.transaction import Transaction

from .exceptions import FormulaError


class PriceList(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'product.price_list'

    name = fields.Char('Name', required=True, translate=True,
        help="The main identifier of the price list.")
    company = fields.Many2One(
        'company.company', "Company", required=True,
        help="Make the price list belong to the company.\n"
        "It defines the currency of the price list.")
    tax_included = fields.Boolean('Tax Included',
        help="Check if result's formula includes taxes.")
    unit = fields.Selection([
            ('product_default', "Product Default"),
            ], "Unit", required=True,
        help="The unit in which the quantity is expressed.")
    price = fields.Selection([
            (None, ""),
            ('list_price', "List price"),
            ('cost_price', "Cost Price"),
            ], "Price",
        help="The value used for 'unit_price'.")
    lines = fields.One2Many(
        'product.price_list.line', 'price_list', "Lines",
        help="Add price formulas for different criteria.\n"
        "The first matching line is used.")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'open_lines': {},
                })

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_tax_included():
        return False

    @classmethod
    def default_unit(cls):
        return 'product_default'

    def get_context_formula(self, product, quantity, uom, pattern=None):
        if product:
            cost_price = product.get_multivalue('cost_price') or Decimal('0')
            list_price = product.list_price_used
        else:
            cost_price = Decimal('0')
            list_price = Null()
        if self.price == 'list_price':
            unit_price = list_price
        elif self.price == 'cost_price':
            unit_price = cost_price
        else:
            unit_price = Null()
        return {
            'names': {
                'unit_price': unit_price if unit_price is not None else Null(),
                'cost_price': cost_price if cost_price is not None else Null(),
                'list_price': list_price if list_price is not None else Null(),
                },
            }

    def get_uom(self, product):
        return product.default_uom

    @classmethod
    @ModelView.button_action(
        'product_price_list.act_price_list_line_form')
    def open_lines(cls, price_lists):
        return {}

    def compute(self, product, quantity, uom, pattern=None):
        Uom = Pool().get('product.uom')

        def parents(categories):
            for category in categories:
                while category:
                    yield category
                    category = category.parent

        if pattern is None:
            pattern = {}

        pattern = pattern.copy()
        if product:
            pattern['categories'] = [
                c.id for c in parents(product.categories_all)]
            pattern['product'] = product.id
        pattern['quantity'] = Uom.compute_qty(uom, quantity,
            self.get_uom(product), round=False) if product else quantity

        context = self.get_context_formula(
            product, quantity, uom, pattern=pattern)
        for line in self.lines:
            if line.match(pattern):
                return line.get_unit_price(**context)


class PriceListLine(sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    __name__ = 'product.price_list.line'

    price_list = fields.Many2One('product.price_list', 'Price List',
            required=True, ondelete='CASCADE',
        help="The price list to which the line belongs.")
    category = fields.Many2One(
        'product.category', "Category", ondelete='CASCADE',
        help="Apply only to products of this category.")
    product = fields.Many2One('product.product', 'Product', ondelete='CASCADE',
        help="Apply only to this product.")
    quantity = fields.Float(
        'Quantity',
        domain=['OR', ('quantity', '>=', 0), ('quantity', '=', None)],
        help="Apply only when quantity is greater.")
    formula = fields.Char('Formula', required=True,
        help=('Python expression that will be evaluated with:\n'
            '- unit_price: the original unit_price\n'
            '- cost_price: the cost price of the product\n'
            '- list_price: the list price of the product'))

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('price_list')

    @staticmethod
    def default_formula():
        return 'unit_price'

    @classmethod
    def validate_fields(cls, lines, field_names):
        super().validate_fields(lines, field_names)
        cls.check_formula(lines, field_names)

    @classmethod
    def check_formula(cls, lines, field_names=None):
        '''
        Check formula
        '''
        if field_names and not (field_names & {'price_list', 'formula'}):
            return
        for line in lines:
            context = line.price_list.get_context_formula(
                product=None, quantity=0, uom=None)
            line.get_unit_price(**context)

    def match(self, pattern):
        if 'quantity' in pattern:
            pattern = pattern.copy()
            quantity = pattern.pop('quantity')
            if self.quantity is not None and self.quantity > abs(quantity):
                return False
        if 'categories' in pattern:
            pattern = pattern.copy()
            categories = pattern.pop('categories')
            if (self.category is not None
                    and self.category.id not in categories):
                return False
        return super().match(pattern)

    def get_unit_price(self, **context):
        'Return unit price (as Decimal)'
        context.setdefault('functions', {})['Decimal'] = Decimal
        try:
            unit_price = simple_eval(decistmt(self.formula), **context)
            if isinstance(unit_price, Null):
                unit_price = None
            if unit_price is not None:
                if not isinstance(unit_price, Decimal):
                    raise ValueError("result is not a Decimal")
                unit_price = round_price(unit_price)
            return unit_price
        except Exception as exception:
            raise FormulaError(
                gettext('product_price_list.msg_invalid_formula',
                    formula=self.formula,
                    line=self.rec_name,
                    exception=exception)) from exception


class PriceListLineContext(ModelView):
    __name__ = 'product.price_list.line.context'
