#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.osv import fields, OSV
from trytond.model.modelstorage import OPERATORS
from decimal import Decimal

STATES = {
    'readonly': "active == False",
}

class UomCategory(OSV):
    'Product uom category'
    _name = 'product.uom.category'
    _description = __doc__
    name = fields.Char('Name', required=True, translate=True)
    uoms = fields.One2Many('product.uom', 'category', 'Unit of Measures')

    def __init__(self):
        super(UomCategory, self).__init__()
        self._order.insert(0, ('name', 'ASC'))

UomCategory()


class Uom(OSV):
    'Unit of measure'
    _name = 'product.uom'
    _description = __doc__
    name = fields.Char('Name', size=None, required=True, states=STATES,
            translate=True)
    symbol = fields.Char('Symbol', size=10, required=True, states=STATES,
            translate=True)
    category = fields.Many2One('product.uom.category', 'UOM Category',
            required=True, ondelete='cascade', states=STATES)
    rate = fields.Float('Rate', digits=(12, 6), required=True,
            on_change=['rate'], states=STATES,
            help='The coefficient for the formula:\n' \
                    '1 (base unit) = coef (this unit)')
    factor = fields.Float('Factor', digits=(12, 6), states=STATES,
            on_change=['factor'], required=True,
            help='The coefficient for the formula:\n' \
                    'coef (base unit) = 1 (this unit)')
    rounding = fields.Float('Rounding Precision', digits=(12, 6),
            required=True, states=STATES)
    digits = fields.Integer('Display Digits')
    active = fields.Boolean('Active')

    def __init__(self):
        super(Uom, self).__init__()
        self._order.insert(0, ('name', 'ASC'))

    def check_xml_record(self, cursor, user, ids, values, context=None):
        return True

    def default_rate(self, cursor, user, context=None):
        return 1.0

    def default_factor(self, cursor, user, context=None):
        return 1.0

    def default_active(self, cursor, user, context=None):
        return 1

    def default_rounding(self, cursor, user, context=None):
        return 0.01

    def default_digits(self, cursor, user, context=None):
        return 2

    def default_category(self, cursor, user, context=None):
        category_obj = self.pool.get('product.uom.category')
        product_obj = self.pool.get('product.product')
        if context is None:
            context = {}
        if 'category' in context:
            if isinstance(context['category'], (tuple, list)) \
                    and len(context['category']) > 1 \
                    and context['category'][1] in ('uom.category',
                            'product.default_uom.category'):
                if context['category'][1] == 'uom.category':
                    if not context['category'][0]:
                        return False
                    uom  = self.browse(cursor, user, context['category'][0],
                            context=context)
                    return category_obj.name_get(cursor, user, uom.category.id,
                            context=context)[0]
                else:
                    if not context['category'][0]:
                        return False
                    product = product_obj.browse(cursor, user,
                            context['category'][0], context=context)
                    return category_obj.name_get(cursor, user,
                            product.default_uom.category.id, context=context)[0]
        return False

    def on_change_factor(self, cursor, user, ids, value, context=None):
        if value.get('factor', 0.0) == 0.0:
            return {'rate': 0.0}
        return {'rate': round(1.0/value['factor'], 6)}

    def on_change_rate(self, cursor, user, ids, value, context=None):
        if value.get('rate', 0.0) == 0.0:
            return {'factor': 0.0}
        return {'factor': round(1.0/value['rate'], 6)}


    def __init__(self):
        super(Uom, self).__init__()
        self._sql_constraints += [
            ('non_zero_rate_factor', 'CHECK((rate != 0.0) or (factor != 0.0))',
                'Rate and factor can not be both equal to zero.')
        ]


    @staticmethod
    def round(number, precision=1.0):
        return round(number / precision) * precision

    @staticmethod
    def check_factor_and_rate(values):
        factor = None
        rate = None
        if ('factor' not in values) and ('rate' not in values):
            return values
        elif 'factor' in values and 'rate' in values:
            if values['rate'] == 0.0 and values['factor'] == 0.0:
                return values
            elif values['factor'] != 0.0 and \
                    values['rate'] != 0.0:
                if values['rate'] == round(1.0/values['factor'], 6) or \
                        values['factor'] == round(1.0/values['rate'], 6):
                    return values
                else:
                    factor = round(1.0/values['rate'], 6)
            elif values['rate'] != 0.0 and \
                    values['factor'] != round(1.0/values['rate'], 6):
                factor = round(1.0/values['rate'], 6)
            elif values['factor'] != 0.0 and \
                    values['rate'] != round(1.0/values['factor'], 6):
                rate = round(1.0/values['factor'], 6)
            else:
                return values
        elif 'rate' in values:
            if values['rate'] != 0.0:
                factor = round(1.0/values['rate'], 6)
            else:
                factor = 0.0
        elif 'factor' in values:
            if values['factor'] != 0.0:
                rate = round(1.0/values['factor'], 6)
            else:
                rate = 0.0

        if rate != None or factor != None:
            values = values.copy()
            if rate != None: values['rate'] = rate
            if factor != None: values['factor'] = factor
        return values

    def create(self, cursor, user, values, context=None):
        values = self.check_factor_and_rate(values)
        return super(Uom, self).create(cursor, user, values, context)

    def write(self, cursor, user, ids, values, context=None):
        values = self.check_factor_and_rate(values)
        return super(Uom, self).write(cursor, user, ids, values, context)

    def compute_qty(self, cursor, user, from_uom, qty, to_uom=False,
                    round=True, context=None):
        """
        Convert quantity for given uom's. from_uom and to_uom should
        be browse records.
        """
        if not from_uom or not qty or not to_uom:
            return qty
        if from_uom.category.id <> to_uom.category.id:
            return qty
        if from_uom.factor >= 1.0: # Choose the more precise field.
            amount = qty * from_uom.factor
        else:
            amount = qty / from_uom.rate
        if to_uom:
            if to_uom.factor >= 1.0:
                amount = amount / to_uom.factor
            else:
                amount = amount * to_uom.rate
            if round:
                amount = self.round(amount, to_uom.rounding)
        return amount

    def compute_price(self, cursor, user, from_uom, price, to_uom=False,
                      context=None):
        """
        Convert price for given uom's. from_uom and to_uom should be
        browse records.
        """
        if not from_uom or not price or not to_uom:
            return price
        if from_uom.category.id <> to_uom.category.id:
            return price

        if from_uom.factor >= 1.0:
            new_price = price / Decimal(str(from_uom.factor))
        else:
            new_price = price * Decimal(str(from_uom.rate))

        if to_uom.factor >= 1.0:
            new_price = new_price * Decimal(str(to_uom.factor))
        else:
            new_price = new_price / Decimal(str(to_uom.rate))

        return new_price

    def search(self, cursor, user, args, offset=0, limit=None, order=None,
            context=None, count=False, query_string=False):
        product_obj = self.pool.get('product.product')
        args = args[:]
        def process_args(args):
            i = 0
            while i < len(args):
                #add test for xmlrpc that doesn't handle tuple
                if (isinstance(args[i], tuple) \
                        or (isinstance(args[i], list) and len(args[i]) > 2 \
                        and args[i][1] in OPERATORS)) \
                        and args[i][0] == 'category' \
                        and isinstance(args[i][2], (list, tuple)) \
                        and len(args[i][2]) == 2 \
                        and args[i][2][1] in ('product.default_uom.category',
                                'uom.category'):
                    if not args[i][2][0]:
                        args[i] = ('id', '!=', '0')
                    else:
                        if args[i][2][1] == 'product.default_uom.category':
                            product = product_obj.browse(cursor, user,
                                    args[i][2][0], context=context)
                            category_id = product.default_uom.category.id
                        else:
                            uom = self.browse(cursor, user, args[i][2][0],
                                    context=context)
                            category_id = uom.category.id
                        args[i] = (args[i][0], args[i][1], category_id)
                elif isinstance(args[i], list):
                    process_args(args[i])
                i += 1
        process_args(args)
        return super(Uom, self).search(cursor, user, args, offset=offset,
                limit=limit, order=order, context=context, count=count,
                query_string=query_string)

Uom()
