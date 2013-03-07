#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval
from trytond.transaction import Transaction

__all__ = ['UomCategory', 'Uom']

STATES = {
    'readonly': ~Eval('active', True),
    }
DEPENDS = ['active']


class UomCategory(ModelSQL, ModelView):
    'Product uom category'
    __name__ = 'product.uom.category'
    name = fields.Char('Name', required=True, translate=True)
    uoms = fields.One2Many('product.uom', 'category', 'Unit of Measures')

    @classmethod
    def __setup__(cls):
        super(UomCategory, cls).__setup__()
        cls._order.insert(0, ('name', 'ASC'))


class Uom(ModelSQL, ModelView):
    'Unit of measure'
    __name__ = 'product.uom'
    name = fields.Char('Name', size=None, required=True, states=STATES,
        translate=True, depends=DEPENDS)
    symbol = fields.Char('Symbol', size=10, required=True, states=STATES,
        translate=True, depends=DEPENDS)
    category = fields.Many2One('product.uom.category', 'UOM Category',
        required=True, ondelete='RESTRICT', states=STATES, depends=DEPENDS)
    rate = fields.Float('Rate', digits=(12, 12), required=True,
        on_change=['rate'], states=STATES, depends=DEPENDS,
        help=('The coefficient for the formula:\n'
            '1 (base unit) = coef (this unit)'))
    factor = fields.Float('Factor', digits=(12, 12), states=STATES,
        on_change=['factor'], required=True, depends=DEPENDS,
        help=('The coefficient for the formula:\n'
            'coef (base unit) = 1 (this unit)'))
    rounding = fields.Float('Rounding Precision', digits=(12, 12),
        required=True, states=STATES, depends=DEPENDS)
    digits = fields.Integer('Display Digits', required=True)
    active = fields.Boolean('Active')

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        # Migration from 1.6: corrected misspelling of ounce (was once)
        cursor.execute("UPDATE ir_model_data "
            "SET fs_id = REPLACE(fs_id, 'uom_once', 'uom_ounce') "
            "WHERE fs_id = 'uom_once' AND module = 'product'")
        super(Uom, cls).__register__(module_name)

    @classmethod
    def __setup__(cls):
        super(Uom, cls).__setup__()
        cls._sql_constraints += [
            ('non_zero_rate_factor', 'CHECK((rate != 0.0) or (factor != 0.0))',
                'Rate and factor can not be both equal to zero.')
            ]
        cls._order.insert(0, ('name', 'ASC'))
        cls._error_messages.update({
                'change_uom_rate_title': ('You cannot change Rate, Factor or '
                    'Category on a Unit of Measure. '),
                'change_uom_rate': ('If the UOM is still not used, you can '
                    'delete it otherwise you can deactivate it '
                    'and create a new one.'),
                'invalid_factor_and_rate': ('Invalid Factor and Rate values in '
                    'UOM "%s".'),
                })

    @classmethod
    def __post_setup__(cls):
        super(Uom, cls).__post_setup__()
        if 'category' not in cls._fields:
            print cls, cls._fields

    @classmethod
    def check_xml_record(cls, records, values):
        return True

    @staticmethod
    def default_rate():
        return 1.0

    @staticmethod
    def default_factor():
        return 1.0

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_rounding():
        return 0.01

    @staticmethod
    def default_digits():
        return 2

    def on_change_factor(self):
        if (self.factor or 0.0) == 0.0:
            return {'rate': 0.0}
        return {
            'rate': round(1.0 / self.factor, self.__class__.rate.digits[1]),
            }

    def on_change_rate(self):
        if (self.rate or 0.0) == 0.0:
            return {'factor': 0.0}
        return {
            'factor': round(1.0 / self.rate, self.__class__.factor.digits[1]),
            }

    @classmethod
    def search_rec_name(cls, name, clause):
        ids = map(int, cls.search(['OR',
                    (cls._rec_name,) + clause[1:],
                    ('symbol',) + clause[1:],
                    ], order=[]))
        return [('id', 'in', ids)]

    @staticmethod
    def round(number, precision=1.0):
        return round(number / precision) * precision

    @classmethod
    def validate(cls, uoms):
        super(Uom, cls).validate(uoms)
        for uom in uoms:
            uom.check_factor_and_rate()

    def check_factor_and_rate(self):
        "Check coherence between factor and rate"
        if self.rate == self.factor == 0.0:
            return True
        if (self.rate != round(
                    1.0 / self.factor, self.__class__.rate.digits[1])
                and self.factor != round(
                    1.0 / self.rate, self.__class__.factor.digits[1])):
            self.raise_user_error('invalid_factor_and_rate', (
                        self.rec_name,))

    @classmethod
    def write(cls, uoms, values):
        if Transaction().user == 0:
            return super(Uom, cls).write(uoms, values)
        if 'rate' not in values and 'factor' not in values \
                and 'category' not in values:
            super(Uom, cls).write(uoms, values)
            return

        old_uom = dict((uom.id, (uom.factor, uom.rate, uom.category.id))
            for uom in uoms)

        super(Uom, cls).write(uoms, values)

        for uom in uoms:
            if uom.factor != old_uom[uom.id][0] \
                    or uom.rate != old_uom[uom.id][1] \
                    or uom.category.id != old_uom[uom.id][2]:

                cls.raise_user_error('change_uom_rate_title',
                    error_description='change_uom_rate')

    @property
    def accurate_field(self):
        """
        Select the more accurate field.
        It chooses the field that has the least decimal.
        """
        lengths = {}
        for field in ('rate', 'factor'):
            format = '%%.%df' % getattr(self.__class__, field).digits[1]
            lengths[field] = len((format % getattr(self,
                        field)).split('.')[1].rstrip('0'))
        if lengths['rate'] < lengths['factor']:
            return 'rate'
        elif lengths['factor'] < lengths['rate']:
            return 'factor'
        elif self.factor >= 1.0:
            return 'factor'
        else:
            return 'rate'

    @classmethod
    def compute_qty(cls, from_uom, qty, to_uom=None, round=True):
        """
        Convert quantity for given uom's.
        """
        if not from_uom or not qty or not to_uom:
            return qty
        if from_uom.category.id != to_uom.category.id:
            return qty
        if from_uom.accurate_field == 'factor':
            amount = qty * from_uom.factor
        else:
            amount = qty / from_uom.rate
        if to_uom is not None:
            if to_uom.accurate_field == 'factor':
                amount = amount / to_uom.factor
            else:
                amount = amount * to_uom.rate
            if round:
                amount = cls.round(amount, to_uom.rounding)
        return amount

    @classmethod
    def compute_price(cls, from_uom, price, to_uom=None):
        """
        Convert price for given uom's.
        """
        if not from_uom or not price or not to_uom:
            return price
        if from_uom.category.id != to_uom.category.id:
            return price
        factor_format = '%%.%df' % cls.factor.digits[1]
        rate_format = '%%.%df' % cls.rate.digits[1]

        if from_uom.accurate_field == 'factor':
            new_price = price / Decimal(factor_format % from_uom.factor)
        else:
            new_price = price * Decimal(rate_format % from_uom.rate)

        if to_uom.accurate_field == 'factor':
            new_price = new_price * Decimal(factor_format % to_uom.factor)
        else:
            new_price = new_price / Decimal(rate_format % to_uom.rate)

        return new_price
