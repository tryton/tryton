# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from __future__ import division
from decimal import Decimal
from sql import Table
from math import ceil, floor, log10

from trytond.model import ModelView, ModelSQL, fields, Check
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
    category = fields.Many2One('product.uom.category', 'Category',
        required=True, ondelete='RESTRICT', states=STATES, depends=DEPENDS)
    rate = fields.Float('Rate', digits=(12, 12), required=True,
        states=STATES, depends=DEPENDS,
        help=('The coefficient for the formula:\n'
            '1 (base unit) = coef (this unit)'))
    factor = fields.Float('Factor', digits=(12, 12), states=STATES,
        required=True, depends=DEPENDS,
        help=('The coefficient for the formula:\n'
            'coef (base unit) = 1 (this unit)'))
    rounding = fields.Float('Rounding Precision', digits=(12, 12),
        required=True, states=STATES, depends=DEPENDS,
        domain=[
            ('rounding', '>', 0),
            ])
    digits = fields.Integer('Display Digits', required=True)
    active = fields.Boolean('Active')

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        model_data = Table('ir_model_data')
        # Migration from 1.6: corrected misspelling of ounce (was once)
        cursor.execute(*model_data.update(
                columns=[model_data.fs_id],
                values=['uom_ounce'],
                where=(model_data.fs_id == 'uom_once')
                & (model_data.module == 'product')))
        super(Uom, cls).__register__(module_name)

    @classmethod
    def __setup__(cls):
        super(Uom, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('non_zero_rate_factor', Check(t, (t.rate != 0) | (t.factor != 0)),
                'Rate and factor can not be both equal to zero.')
            ]
        cls._order.insert(0, ('name', 'ASC'))
        cls._error_messages.update({
                'change_uom_rate_title': ('You cannot change Rate, Factor or '
                    'Category on a Unit of Measure.'),
                'change_uom_rate': ('If the UOM is still not used, you can '
                    'delete it otherwise you can deactivate it '
                    'and create a new one.'),
                'invalid_factor_and_rate': (
                    'Invalid Factor and Rate values in UOM "%s".'),
                })

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

    @fields.depends('factor')
    def on_change_factor(self):
        if (self.factor or 0.0) == 0.0:
            self.rate = 0.0
        else:
            self.rate = round(1.0 / self.factor, self.__class__.rate.digits[1])

    @fields.depends('rate')
    def on_change_rate(self):
        if (self.rate or 0.0) == 0.0:
            self.factor = 0.0
        else:
            self.factor = round(
                1.0 / self.rate, self.__class__.factor.digits[1])

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            (cls._rec_name,) + tuple(clause[1:]),
            ('symbol',) + tuple(clause[1:]),
            ]

    def round(self, number):
        return _round(self, number, func=round)

    def ceil(self, number):
        return _round(self, number, func=ceil)

    def floor(self, number):
        return _round(self, number, func=floor)

    @classmethod
    def validate(cls, uoms):
        super(Uom, cls).validate(uoms)
        for uom in uoms:
            uom.check_factor_and_rate()

    def check_factor_and_rate(self):
        "Check coherence between factor and rate"
        if self.rate == self.factor == 0.0:
            return
        if (self.rate != round(
                    1.0 / self.factor, self.__class__.rate.digits[1])
                and self.factor != round(
                    1.0 / self.rate, self.__class__.factor.digits[1])):
            self.raise_user_error('invalid_factor_and_rate', (
                        self.rec_name,))

    @classmethod
    def write(cls, *args):
        if Transaction().user == 0:
            super(Uom, cls).write(*args)
            return

        actions = iter(args)
        all_uoms = []
        for uoms, values in zip(actions, actions):
            if 'rate' not in values and 'factor' not in values \
                    and 'category' not in values:
                continue
            all_uoms += uoms

        old_uom = dict((uom.id, (uom.factor, uom.rate, uom.category.id))
            for uom in all_uoms)

        super(Uom, cls).write(*args)

        for uom in all_uoms:
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
    def compute_qty(cls, from_uom, qty, to_uom, round=True):
        """
        Convert quantity for given uom's.
        """
        if not qty or (from_uom is None and to_uom is None):
            return qty
        if from_uom is None:
            raise ValueError("missing from_uom")
        if to_uom is None:
            raise ValueError("missing to_uom")
        if from_uom.category.id != to_uom.category.id:
            raise ValueError("cannot convert between %s and %s"
                    % (from_uom.category.name, to_uom.category.name))

        if from_uom.accurate_field == 'factor':
            amount = qty * from_uom.factor
        else:
            amount = qty / from_uom.rate

        if to_uom.accurate_field == 'factor':
            amount = amount / to_uom.factor
        else:
            amount = amount * to_uom.rate

        if round:
            amount = to_uom.round(amount)

        return amount

    @classmethod
    def compute_price(cls, from_uom, price, to_uom):
        """
        Convert price for given uom's.
        """
        if not price or (from_uom is None and to_uom is None):
            return price
        if from_uom is None:
            raise ValueError("missing from_uom")
        if to_uom is None:
            raise ValueError("missing to_uom")
        if from_uom.category.id != to_uom.category.id:
            raise ValueError('cannot convert between %s and %s'
                    % (from_uom.category.name, to_uom.category.name))

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


def _round(uom, number, func=round):
    precision = uom.rounding
    # Convert precision into an integer greater than 1 to avoid precision lost.
    # This works for most cases because rounding is often: n * 10**i
    if precision < 1:
        exp = -floor(log10(precision))
        factor = 10 ** exp
        number *= factor
        precision *= factor
    else:
        factor = 1
    # Divide by factor which is an integer to avoid precision lost due to
    # multiplication by float < 1.
    # example:
    # >>> 3 * 0.1
    # 0.30000000000000004
    # >>> 3 / 10.
    # 0.3
    return func(number / precision) * precision / factor
