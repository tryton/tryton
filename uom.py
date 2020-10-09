# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal
from math import ceil, floor, log10

from trytond.config import config
from trytond.i18n import gettext
from trytond.model import (
    ModelView, ModelSQL, DeactivableMixin, fields, Check, SymbolMixin)
from trytond.model.exceptions import AccessError
from trytond.pyson import Eval
from trytond.transaction import Transaction

from .exceptions import UOMValidationError

__all__ = ['uom_conversion_digits']

uom_conversion_digits = (
    config.getint('product', 'uom_conversion_decimal', default=12),) * 2


class UomCategory(ModelSQL, ModelView):
    "Unit of Measure Category"
    __name__ = 'product.uom.category'
    name = fields.Char('Name', required=True, translate=True)
    uoms = fields.One2Many('product.uom', 'category', "Units of Measure")

    @classmethod
    def __setup__(cls):
        super(UomCategory, cls).__setup__()
        cls._order.insert(0, ('name', 'ASC'))


class Uom(SymbolMixin, DeactivableMixin, ModelSQL, ModelView):
    "Unit of Measure"
    __name__ = 'product.uom'
    name = fields.Char("Name", size=None, required=True, translate=True)
    symbol = fields.Char(
        "Symbol", size=10, required=True, translate=True,
        help="The symbol that represents the unit of measure.")
    category = fields.Many2One(
        'product.uom.category', "Category", required=True, ondelete='RESTRICT',
        help="The category that contains the unit of measure.\n"
        "Conversions between different units of measure can be done if they "
        "are in the same category.")
    rate = fields.Float(
        "Rate", digits=uom_conversion_digits, required=True,
        help="The coefficient for the formula:\n"
        "1 (base unit) = coef (this unit)")
    factor = fields.Float(
        "Factor", digits=uom_conversion_digits, required=True,
        help="The coefficient for the formula:\n"
        "coefficient (base unit) = 1 (this unit)")
    rounding = fields.Float(
        "Rounding Precision", digits=(12, Eval('digits', 12)), required=True,
        domain=[
            ('rounding', '>', 0),
            ],
        depends=['digits'],
        help="The accuracy to which values are rounded.")
    digits = fields.Integer(
        "Display Digits", required=True,
        help="The number of digits to display after the decimal separator.")

    @classmethod
    def __setup__(cls):
        super(Uom, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('non_zero_rate_factor', Check(t, (t.rate != 0) | (t.factor != 0)),
                'product.msg_uom_no_zero_factor_rate')
            ]
        cls._order.insert(0, ('name', 'ASC'))

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
            self.rate = round(1.0 / self.factor, uom_conversion_digits[1])

    @fields.depends('rate')
    def on_change_rate(self):
        if (self.rate or 0.0) == 0.0:
            self.factor = 0.0
        else:
            self.factor = round(
                1.0 / self.rate, uom_conversion_digits[1])

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
                    1.0 / self.factor, uom_conversion_digits[1])
                and self.factor != round(
                    1.0 / self.rate, uom_conversion_digits[1])):
            raise UOMValidationError(
                gettext('product.msg_uom_incompatible_factor_rate',
                    uom=self.rec_name))

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

        old_uom = dict((uom.id, (uom.factor, uom.rate, uom.category))
            for uom in all_uoms)

        super(Uom, cls).write(*args)

        for uom in all_uoms:
            for i, field in enumerate(['factor', 'rate', 'category']):
                if getattr(uom, field) != old_uom[uom.id][i]:
                    raise AccessError(
                        gettext('product.msg_uom_modify_%s' % field,
                            uom=uom.rec_name),
                        gettext('product.msg_uom_modify_options'))

    @property
    def accurate_field(self):
        """
        Select the more accurate field.
        It chooses the field that has the least decimal.
        """
        return _accurate_operator(self.factor, self.rate)

    @classmethod
    def compute_qty(cls, from_uom, qty, to_uom, round=True,
            factor=None, rate=None):
        """
        Convert quantity for given uom's.

        When converting between uom's from different categories the factor and
        rate provide the ratio to use to convert between the category's base
        uom's.
        """
        if not qty or (from_uom is None and to_uom is None):
            return qty
        if from_uom is None:
            raise ValueError("missing from_uom")
        if to_uom is None:
            raise ValueError("missing to_uom")
        if from_uom.category.id != to_uom.category.id:
            if not factor and not rate:
                raise ValueError(
                    "cannot convert between %s and %s without a factor or rate"
                    % (from_uom.category.name, to_uom.category.name))
        elif factor or rate:
            raise ValueError("factor and rate not allowed for same category")

        if from_uom.accurate_field == 'factor':
            amount = qty * from_uom.factor
        else:
            amount = qty / from_uom.rate

        if factor and rate:
            if _accurate_operator(factor, rate) == 'rate':
                factor = None
            else:
                rate = None
        if factor:
            amount *= factor
        elif rate:
            amount /= rate

        if to_uom.accurate_field == 'factor':
            amount = amount / to_uom.factor
        else:
            amount = amount * to_uom.rate

        if round:
            amount = to_uom.round(amount)

        return amount

    @classmethod
    def compute_price(cls, from_uom, price, to_uom, factor=None, rate=None):
        """
        Convert price for given uom's.

        When converting between uom's from different categories the factor and
        rate provide the ratio to use to convert between the category's base
        uom's.
        """
        if not price or (from_uom is None and to_uom is None):
            return price
        if from_uom is None:
            raise ValueError("missing from_uom")
        if to_uom is None:
            raise ValueError("missing to_uom")
        if from_uom.category.id != to_uom.category.id:
            if not factor and not rate:
                raise ValueError(
                    "cannot convert between %s and %s without a factor or rate"
                    % (from_uom.category.name, to_uom.category.name))
        elif factor or rate:
            raise ValueError("factor and rate not allow for same category")

        format_ = '%%.%df' % uom_conversion_digits[1]

        if from_uom.accurate_field == 'factor':
            new_price = price / Decimal(format_ % from_uom.factor)
        else:
            new_price = price * Decimal(format_ % from_uom.rate)

        if factor and rate:
            if _accurate_operator(factor, rate) == 'rate':
                factor = None
            else:
                rate = None
        if factor:
            new_price /= Decimal(factor)
        elif rate:
            new_price *= Decimal(rate)

        if to_uom.accurate_field == 'factor':
            new_price = new_price * Decimal(format_ % to_uom.factor)
        else:
            new_price = new_price / Decimal(format_ % to_uom.rate)

        return new_price


def _round(uom, number, func=round):
    if not number:
        # Avoid unnecessary computation
        return number
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


def _accurate_operator(factor, rate):
    lengths = {}
    for name, value in [('rate', rate), ('factor', factor)]:
        format_ = '%%.%df' % uom_conversion_digits[1]
        lengths[name] = len((format_ % value).split('.')[1].rstrip('0'))
    if lengths['rate'] < lengths['factor']:
        return 'rate'
    elif lengths['factor'] < lengths['rate']:
        return 'factor'
    elif factor >= 1.0:
        return 'factor'
    else:
        return 'rate'
