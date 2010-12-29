#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.tools import safe_eval
from trytond.pyson import If, In, Eval, Get
from decimal import Decimal
import re

_RE_DECIMAL = re.compile('([\.0-9]+(\.[0-9]+)?)')


class PriceList(ModelSQL, ModelView):
    'Price List'
    _name = 'product.price_list'
    _description = __doc__
    name = fields.Char('Name', required=True, translate=True)
    company = fields.Many2One('company.company', 'Company', required=True,
            select=1, domain=[
                ('id', If(In('company', Eval('context', {})), '=', '!='),
                    Get(Eval('context', {}), 'company', 0)),
            ])
    lines = fields.One2Many('product.price_list.line', 'price_list', 'Lines')

    def default_company(self, cursor, user, context=None):
        if context is None:
            context = {}
        if context.get('company'):
            return context['company']
        return False

    def _get_context_price_list_line(self, cursor, user, party,
            product, unit_price, quantity, uom, context=None):
        '''
        Get price list context for unit price

        :param cursor: the database cursor
        :param user: the user id
        :param party: the BrowseRecord of the party.party
        :param product: the BrowseRecord of the product.product
        :param unit_price: a Decimal for the default unit price in the
            company's currency and default uom of the product
        :param quantity: the quantity of product
        :param uom: the BrowseRecord of the product.uom
        :param context: the context
        :return: a dictionary
        '''
        return {
            'unit_price': unit_price,
        }

    def compute(self, cursor, user, price_list, party, product, unit_price,
            quantity, uom, pattern=None, context=None):
        '''
        Compute price based on price list of party

        :param cursor: the database cursor
        :param user: the user id
        :param price_list: the price list id or the BrowseRecord of the
            product.price_list
        :param party: the party id or the BrowseRecord of the party.party
        :param product: the product id or the BrowseRecord of the
            product.product
        :param unit_price: a Decimal for the default unit price in the
            company's currency and default uom of the product
        :param quantity: the quantity of product
        :param uom: the UOM id or the BrowseRecord of the product.uom
        :param pattern: a dictionary with price list field as key
            and match value as value
        :param context: the context
        :return: the computed unit price
        '''
        party_obj = self.pool.get('party.party')
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        price_list_line_obj = self.pool.get('product.price_list.line')

        if not price_list:
            return unit_price

        if isinstance(price_list, (int, long)):
            price_list = self.browse(cursor, user, price_list, context=context)

        if isinstance(party, (int, long)):
            party = party_obj.browse(cursor, user, party, context=context)

        if isinstance(product, (int, long)):
            product = product_obj.browse(cursor, user, product, context=context)

        if isinstance(uom, (int, long)):
            uom = uom_obj.browse(cursor, user, uom, context=context)

        if pattern is None:
            pattern = {}

        pattern = pattern.copy()
        pattern['product'] = product and product.id or False
        pattern['quantity'] = uom_obj.compute_qty(cursor, user, uom,
                quantity, product.default_uom, round=False, context=context)

        for line in price_list.lines:
            if price_list_line_obj.match(cursor, user, line, pattern,
                    context=context):
                return price_list_line_obj.get_unit_price(cursor, user, line,
                        context=self._get_context_price_list_line(
                            cursor, user, party, product, unit_price,
                            quantity, uom, context=context))
        return unit_price

PriceList()


class PriceListLine(ModelSQL, ModelView):
    'Price List Line'
    _name = 'product.price_list.line'
    _description = __doc__
    price_list = fields.Many2One('product.price_list', 'Price List',
            required=True, ondelete='CASCADE')
    product = fields.Many2One('product.product', 'Product')
    sequence = fields.Integer('Sequence')
    quantity = fields.Float('Quantity', digits=(16, Eval('unit_digits', 2)),
            depends=['unit_digits'])
    unit_digits = fields.Function(fields.Integer('Unit Digits',
        on_change_with=['product']), 'get_unit_digits')
    formula = fields.Char('Formula', required=True,
            help='Python expression that will be evaluated with:\n' \
                    '- unit_price: the original unit_price')

    def __init__(self):
        super(PriceListLine, self).__init__()
        self._order.insert(0, ('price_list', 'ASC'))
        self._order.insert(0, ('sequence', 'ASC'))
        self._constraints += [
            ('check_formula', 'invalid_formula'),
        ]
        self._error_messages.update({
            'invalid_formula': 'Invalid formula!',
        })

    def default_formula(self, cursor, user, context=None):
        return 'unit_price'

    def on_change_with_unit_digits(self, cursor, user, vals, context=None):
        product_obj = self.pool.get('product.product')
        if vals.get('product'):
            product = product_obj.browse(cursor, user, vals['product'],
                    context=context)
            return product.default_uom.digits
        return 2

    def get_unit_digits(self, cursor, user, ids, name, context=None):
        res = {}
        for line in self.browse(cursor, user, ids, context=context):
            if line.product:
                res[line.id] = line.product.default_uom.digits
            else:
                res[line.id] = 2
        return res

    def check_formula(self, cursor, user, ids):
        '''
        Check formula
        '''
        price_list_obj = self.pool.get('product.price_list')
        context = price_list_obj._get_context_price_list_line(cursor, user,
                None, None, Decimal('0.0'), 0, None)
        for line in self.browse(cursor, user, ids):
            try:
                if not isinstance(self.get_unit_price(cursor, user, line,
                    context=context), Decimal):
                    return False
            except:
                return False
        return True

    def match(self, cursor, user, line, pattern, context=None):
        '''
        Match line on pattern

        :param cursor: the database cursor
        :param user: the user id
        :param line: a BrowseRecord of price list line
        :param pattern: a dictonary with price list line field as key
                and match value as value
        :param context: the context
        :return: a boolean
        '''
        res = True
        for field in pattern.keys():
            if field not in self._columns:
                continue
            if not line[field]:
                continue
            if self._columns[field]._type == 'many2one':
                if line[field].id != pattern[field]:
                    res = False
                    break
            elif field == 'quantity':
                if line[field] > pattern[field]:
                    res = False
                    break
            else:
                if line[field] != pattern[field]:
                    res = False
                    break
        return res

    def get_unit_price(self, cursor, user, line, context=None):
        '''
        Return unit price for a line

        :param cursor: the database cursor
        :param user: the user id
        :param line: a BrowseRecord of price list line
        :param context: the context
        :return: a Decimal
        '''
        if context is None:
            context = {}
        ctx = context.copy()
        ctx['Decimal'] = Decimal
        return safe_eval(_RE_DECIMAL.sub(lambda m: "Decimal('%s')" % m.group(1),
            line.formula), ctx)

PriceListLine()
