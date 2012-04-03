#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval
from trytond.transaction import Transaction

STATES = {
    'readonly': ~Eval('active', True),
    }
DEPENDS = ['active']


class UomCategory(ModelSQL, ModelView):
    'Product uom category'
    _name = 'product.uom.category'
    _description = __doc__
    name = fields.Char('Name', required=True, translate=True)
    uoms = fields.One2Many('product.uom', 'category', 'Unit of Measures')

    def __init__(self):
        super(UomCategory, self).__init__()
        self._order.insert(0, ('name', 'ASC'))

UomCategory()


class Uom(ModelSQL, ModelView):
    'Unit of measure'
    _name = 'product.uom'
    _description = __doc__
    name = fields.Char('Name', size=None, required=True, states=STATES,
        translate=True, depends=DEPENDS)
    symbol = fields.Char('Symbol', size=10, required=True, states=STATES,
        translate=True, depends=DEPENDS)
    category = fields.Many2One('product.uom.category', 'UOM Category',
        required=True, ondelete='RESTRICT', states=STATES, depends=DEPENDS)
    rate = fields.Float('Rate', digits=(12, 12), required=True,
        on_change=['rate'], states=STATES, depends=DEPENDS,
        help='The coefficient for the formula:\n' \
            '1 (base unit) = coef (this unit)')
    factor = fields.Float('Factor', digits=(12, 12), states=STATES,
        on_change=['factor'], required=True, depends=DEPENDS,
        help='The coefficient for the formula:\n' \
            'coef (base unit) = 1 (this unit)')
    rounding = fields.Float('Rounding Precision', digits=(12, 12),
        required=True, states=STATES, depends=DEPENDS)
    digits = fields.Integer('Display Digits', required=True)
    active = fields.Boolean('Active')

    def init(self, module_name):
        cursor = Transaction().cursor
        # Migration from 1.6: corrected misspelling of ounce (was once)
        cursor.execute("UPDATE ir_model_data "\
                "SET fs_id = REPLACE(fs_id, 'uom_once', 'uom_ounce') "\
                "WHERE fs_id = 'uom_once' AND module = 'product'")
        super(Uom, self).init(module_name)

    def __init__(self):
        super(Uom, self).__init__()
        self._sql_constraints += [
            ('non_zero_rate_factor', 'CHECK((rate != 0.0) or (factor != 0.0))',
                'Rate and factor can not be both equal to zero.')
        ]
        self._constraints += [
            ('check_factor_and_rate', 'invalid_factor_and_rate'),
        ]
        self._order.insert(0, ('name', 'ASC'))
        self._error_messages.update({
                'change_uom_rate_title': 'You cannot change Rate, Factor or '
                    'Category on a Unit of Measure. ',
                'change_uom_rate': 'If the UOM is still not used, you can '
                    'delete it otherwise you can deactivate it '
                    'and create a new one.',
                'invalid_factor_and_rate': 'Invalid Factor and Rate values!',
            })

    def check_xml_record(self, ids, values):
        return True

    def default_rate(self):
        return 1.0

    def default_factor(self):
        return 1.0

    def default_active(self):
        return True

    def default_rounding(self):
        return 0.01

    def default_digits(self):
        return 2

    def on_change_factor(self, value):
        if value.get('factor', 0.0) == 0.0:
            return {'rate': 0.0}
        return {'rate': round(1.0 / value['factor'], self.rate.digits[1])}

    def on_change_rate(self, value):
        if value.get('rate', 0.0) == 0.0:
            return {'factor': 0.0}
        return {'factor': round(1.0 / value['rate'], self.factor.digits[1])}

    def search_rec_name(self, name, clause):
        ids = self.search(['OR',
            (self._rec_name,) + clause[1:],
            ('symbol',) + clause[1:],
            ], order=[])
        return [('id', 'in', ids)]

    @staticmethod
    def round(number, precision=1.0):
        return round(number / precision) * precision

    def check_factor_and_rate(self, ids):
        "Check coherence between factor and rate"
        for uom in self.browse(ids):
            if uom.rate == uom.factor == 0.0:
                continue
            if uom.rate != round(1.0 / uom.factor, self.rate.digits[1]) and \
                    uom.factor != round(1.0 / uom.rate, self.factor.digits[1]):
                return False
        return True

    def write(self, ids, values):
        if Transaction().user == 0:
            return super(Uom, self).write(ids, values)
        if 'rate' not in values and 'factor' not in values \
                and 'category' not in values:
            return super(Uom, self).write(ids, values)

        if isinstance(ids, (int, long)):
            ids = [ids]

        uoms = self.browse(ids)
        old_uom = dict((uom.id, (uom.factor, uom.rate, uom.category.id)) \
                           for uom in uoms)

        res = super(Uom, self).write(ids, values)
        uoms = self.browse(ids)

        for uom in uoms:
            if uom.factor != old_uom[uom.id][0] \
                    or uom.rate != old_uom[uom.id][1] \
                    or uom.category.id != old_uom[uom.id][2]:

                self.raise_user_error('change_uom_rate_title',
                        error_description='change_uom_rate')
        return res

    def select_accurate_field(self, uom):
        """
        Select the more accurate field.
        It chooses the field that has the least decimal.

        :param uom: a BrowseRecord of UOM.
        :return: 'factor' or 'rate'.
        """
        lengths = {}
        for field in ('rate', 'factor'):
            format = '%%.%df' % getattr(self, field).digits[1]
            lengths[field] = len((format % getattr(uom,
                field)).split('.')[1].rstrip('0'))
        if lengths['rate'] < lengths['factor']:
            return 'rate'
        elif lengths['factor'] < lengths['rate']:
            return 'factor'
        elif uom.factor >= 1.0:
            return 'factor'
        else:
            return 'rate'

    def compute_qty(self, from_uom, qty, to_uom=None, round=True):
        """
        Convert quantity for given uom's.

        :param from_uom: a BrowseRecord of product.uom
        :param qty: an int or long or float value
        :param to_uom: a BrowseRecord of product.uom
        :param round: a boolean to round or not the result
        :return: the converted quantity
        """
        if not from_uom or not qty or not to_uom:
            return qty
        if from_uom.category.id != to_uom.category.id:
            return qty
        if self.select_accurate_field(from_uom) == 'factor':
            amount = qty * from_uom.factor
        else:
            amount = qty / from_uom.rate
        if to_uom is not None:
            if self.select_accurate_field(to_uom) == 'factor':
                amount = amount / to_uom.factor
            else:
                amount = amount * to_uom.rate
            if round:
                amount = self.round(amount, to_uom.rounding)
        return amount

    def compute_price(self, from_uom, price, to_uom=None):
        """
        Convert price for given uom's.

        :param from_uom: a BrowseRecord of product.uom
        :param price: a Decimal value
        :param to_uom: a BrowseRecord of product.uom
        :return: the converted price
        """
        if not from_uom or not price or not to_uom:
            return price
        if from_uom.category.id != to_uom.category.id:
            return price
        factor_format = '%%.%df' % self.factor.digits[1]
        rate_format = '%%.%df' % self.rate.digits[1]

        if self.select_accurate_field(from_uom) == 'factor':
            new_price = price / Decimal(factor_format % from_uom.factor)
        else:
            new_price = price * Decimal(rate_format % from_uom.rate)

        if self.select_accurate_field(to_uom) == 'factor':
            new_price = new_price * Decimal(factor_format % to_uom.factor)
        else:
            new_price = new_price / Decimal(rate_format % to_uom.rate)

        return new_price

Uom()
