#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
import tokenize
from StringIO import StringIO
from trytond.model import ModelView, ModelSQL, fields
from trytond.tools import safe_eval
from trytond.pyson import If, Eval
from trytond.transaction import Transaction
from trytond.pool import Pool


# code snippet taken from http://docs.python.org/library/tokenize.html
def decistmt(s):
    """Substitute Decimals for floats in a string of statements.

    >>> from decimal import Decimal
    >>> s = 'print +21.3e-5*-.1234/81.7'
    >>> decistmt(s)
    "print +Decimal ('21.3e-5')*-Decimal ('.1234')/Decimal ('81.7')"

    >>> exec(s)
    -3.21716034272e-007
    >>> exec(decistmt(s))
    -3.217160342717258261933904529E-7
    """
    result = []
    # tokenize the string
    g = tokenize.generate_tokens(StringIO(s).readline)
    for toknum, tokval, _, _, _  in g:
        # replace NUMBER tokens
        if toknum == tokenize.NUMBER and '.' in tokval:
            result.extend([
                (tokenize.NAME, 'Decimal'),
                (tokenize.OP, '('),
                (tokenize.STRING, repr(tokval)),
                (tokenize.OP, ')')
            ])
        else:
            result.append((toknum, tokval))
    return tokenize.untokenize(result)


class PriceList(ModelSQL, ModelView):
    'Price List'
    _name = 'product.price_list'
    _description = __doc__
    name = fields.Char('Name', required=True, translate=True)
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True, domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', 0)),
            ])
    lines = fields.One2Many('product.price_list.line', 'price_list', 'Lines')

    def default_company(self):
        return Transaction().context.get('company')

    def _get_context_price_list_line(self, party, product, unit_price,
            quantity, uom):
        '''
        Get price list context for unit price

        :param party: the BrowseRecord of the party.party
        :param product: the BrowseRecord of the product.product
        :param unit_price: a Decimal for the default unit price in the
            company's currency and default uom of the product
        :param quantity: the quantity of product
        :param uom: the BrowseRecord of the product.uom
        :return: a dictionary
        '''
        return {
            'unit_price': unit_price,
        }

    def compute(self, price_list, party, product, unit_price, quantity, uom,
            pattern=None):
        '''
        Compute price based on price list of party

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
        :return: the computed unit price
        '''
        pool = Pool()
        party_obj = pool.get('party.party')
        product_obj = pool.get('product.product')
        uom_obj = pool.get('product.uom')
        price_list_line_obj = pool.get('product.price_list.line')

        if not price_list:
            return unit_price

        if isinstance(price_list, (int, long)):
            price_list = self.browse(price_list)

        if isinstance(party, (int, long)):
            party = party_obj.browse(party)

        if isinstance(product, (int, long)):
            product = product_obj.browse(product)

        if isinstance(uom, (int, long)):
            uom = uom_obj.browse(uom)

        if pattern is None:
            pattern = {}

        pattern = pattern.copy()
        pattern['product'] = product and product.id or None
        pattern['quantity'] = uom_obj.compute_qty(uom, quantity,
                product.default_uom, round=False)

        for line in price_list.lines:
            if price_list_line_obj.match(line, pattern):
                with Transaction().set_context(
                        self._get_context_price_list_line(party, product,
                            unit_price, quantity, uom)):
                    return price_list_line_obj.get_unit_price(line)
        return unit_price

PriceList()


class PriceListLine(ModelSQL, ModelView):
    'Price List Line'
    _name = 'product.price_list.line'
    _description = __doc__
    price_list = fields.Many2One('product.price_list', 'Price List',
            required=True, ondelete='CASCADE')
    product = fields.Many2One('product.product', 'Product')
    sequence = fields.Integer('Sequence', required=True)
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

    def default_formula(self):
        return 'unit_price'

    def on_change_with_unit_digits(self, vals):
        product_obj = Pool().get('product.product')
        if vals.get('product'):
            product = product_obj.browse(vals['product'])
            return product.default_uom.digits
        return 2

    def get_unit_digits(self, ids, name):
        res = {}
        for line in self.browse(ids):
            if line.product:
                res[line.id] = line.product.default_uom.digits
            else:
                res[line.id] = 2
        return res

    def check_formula(self, ids):
        '''
        Check formula
        '''
        price_list_obj = Pool().get('product.price_list')
        context = price_list_obj._get_context_price_list_line(None, None,
                Decimal('0.0'), 0, None)
        lines = self.browse(ids)
        with Transaction().set_context(**context):
            for line in lines:
                try:
                    if not isinstance(self.get_unit_price(line), Decimal):
                        return False
                except Exception:
                    return False
        return True

    def match(self, line, pattern):
        '''
        Match line on pattern

        :param line: a BrowseRecord of price list line
        :param pattern: a dictonary with price list line field as key
                and match value as value
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

    def get_unit_price(self, line):
        '''
        Return unit price for a line

        :param line: a BrowseRecord of price list line
        :return: a Decimal
        '''
        context = Transaction().context.copy()
        context['Decimal'] = Decimal
        return safe_eval(decistmt(line.formula), context)

PriceListLine()
