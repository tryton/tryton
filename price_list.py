# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from simpleeval import simple_eval

from trytond.model import ModelView, ModelSQL, MatchMixin, fields, \
    sequence_ordered
from trytond.tools import decistmt
from trytond.pyson import If, Eval
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond import backend

__all__ = ['PriceList', 'PriceListLine']


class PriceList(ModelSQL, ModelView):
    'Price List'
    __name__ = 'product.price_list'

    name = fields.Char('Name', required=True, translate=True,
        help="The main identifier of the price list.")
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True, domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        help=("Make the price list belong to the company.\n"
            "It defines the currency of the price list."))
    tax_included = fields.Boolean('Tax Included',
        help="Check if result's formula includes taxes.")
    lines = fields.One2Many('product.price_list.line', 'price_list', 'Lines',
        help="Add price formulas for different criterias.")

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_tax_included():
        return False

    def get_context_formula(self, party, product, unit_price, quantity, uom):
        return {
            'names': {
                'unit_price': unit_price,
                },
            }

    def compute(self, party, product, unit_price, quantity, uom,
            pattern=None):
        'Compute price based on price list of party'

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
            product.default_uom, round=False) if product else quantity

        context = self.get_context_formula(
            party, product, unit_price, quantity, uom)
        for line in self.lines:
            if line.match(pattern):
                return line.get_unit_price(**context)
        return unit_price


class PriceListLine(sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    'Price List Line'
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
        digits=(16, Eval('unit_digits', 2)),
        domain=['OR', ('quantity', '>=', 0), ('quantity', '=', None)],
        depends=['unit_digits'],
        help="Apply only when quantity is greater.")
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'on_change_with_unit_digits')
    formula = fields.Char('Formula', required=True,
        help=('Python expression that will be evaluated with:\n'
            '- unit_price: the original unit_price'))

    @classmethod
    def __setup__(cls):
        super(PriceListLine, cls).__setup__()
        cls._order.insert(1, ('price_list', 'ASC'))
        cls._error_messages.update({
                'invalid_formula': ('Invalid formula "%(formula)s" in price '
                    'list line "%(line)s" with exception "%(exception)s".'),
                })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)

        super(PriceListLine, cls).__register__(module_name)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

    @staticmethod
    def default_formula():
        return 'unit_price'

    @fields.depends('product')
    def on_change_with_unit_digits(self, name=None):
        if self.product:
            return self.product.default_uom.digits

    @classmethod
    def validate(cls, lines):
        super(PriceListLine, cls).validate(lines)
        for line in lines:
            line.check_formula()

    def check_formula(self):
        '''
        Check formula
        '''
        context = self.price_list.get_context_formula(
            None, None, Decimal('0'), 0, None)

        try:
            if not isinstance(self.get_unit_price(**context), Decimal):
                raise ValueError
        except Exception as exception:
            self.raise_user_error('invalid_formula', {
                    'formula': self.formula,
                    'line': self.rec_name,
                    'exception': exception,
                    })

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
        return super(PriceListLine, self).match(pattern)

    def get_unit_price(self, **context):
        'Return unit price (as Decimal)'
        context.setdefault('functions', {})['Decimal'] = Decimal
        return simple_eval(decistmt(self.formula), **context)
