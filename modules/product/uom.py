# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal
from math import ceil, floor, log10

import trytond.config as config
from trytond.i18n import gettext
from trytond.model import (
    Check, DeactivableMixin, DigitsMixin, ModelSQL, ModelView, SymbolMixin,
    fields)
from trytond.pyson import Eval, If

from .exceptions import UOMAccessError, UOMValidationError

__all__ = ['uom_conversion_digits']

uom_conversion_digits = (
    config.getint('product', 'uom_conversion_decimal', default=12),) * 2


class UomCategory(ModelSQL, ModelView):
    __name__ = 'product.uom.category'
    name = fields.Char('Name', required=True, translate=True)
    uoms = fields.One2Many('product.uom', 'category', "Units of Measure")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('name', 'ASC'))


class Uom(SymbolMixin, DigitsMixin, DeactivableMixin, ModelSQL, ModelView):
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
        domain=[
            If(Eval('factor', 0) == 0, ('rate', '!=', 0), ()),
            ],
        help="The coefficient for the formula:\n"
        "1 (base unit) = coef (this unit)")
    factor = fields.Float(
        "Factor", digits=uom_conversion_digits, required=True,
        domain=[
            If(Eval('rate', 0) == 0, ('factor', '!=', 0), ()),
            ],
        help="The coefficient for the formula:\n"
        "coefficient (base unit) = 1 (this unit)")
    rounding = fields.Float(
        "Rounding Precision",
        digits=(None, Eval('digits', None)), required=True,
        domain=[
            ('rounding', '>', 0),
            ],
        help="The accuracy to which values are rounded.")
    digits = fields.Integer(
        "Display Digits", required=True,
        help="The number of digits to display after the decimal separator.")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('non_zero_rate_factor', Check(t, (t.rate != 0) | (t.factor != 0)),
                'product.msg_uom_no_zero_factor_rate')
            ]
        cls._order.insert(0, ('name', 'ASC'))

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
    def validate_fields(cls, uoms, field_names):
        super().validate_fields(uoms, field_names)
        cls.check_factor_and_rate(uoms, field_names)

    @classmethod
    def check_factor_and_rate(cls, uoms, field_names=None):
        "Check coherence between factor and rate"
        if field_names and not (field_names & {'rate', 'factor'}):
            return
        for uom in uoms:
            if uom.rate == uom.factor == 0.0:
                continue
            if (uom.rate != round(
                        1.0 / uom.factor, uom_conversion_digits[1])
                    and uom.factor != round(
                        1.0 / uom.rate, uom_conversion_digits[1])):
                raise UOMValidationError(
                    gettext('product.msg_uom_incompatible_factor_rate',
                        uom=uom.rec_name))

    @classmethod
    def check_modification(cls, mode, uoms, values=None, external=False):
        super().check_modification(
            mode, uoms, values=values, external=external)
        if (mode == 'write'
                and values.keys() & {'factor', 'rate', 'category', 'digits'}):
            for uom in uoms:
                for field_name in values.keys() & {'factor', 'rate'}:
                    if values[field_name] != getattr(uom, field_name):
                        raise UOMAccessError(gettext(
                                'product.msg_uom_modify_%s' % field_name,
                                uom=uom.rec_name),
                            gettext('product.msg_uom_modify_options'))
                if 'category' in values:
                    if values['category'] != uom.category.id:
                        raise UOMAccessError(gettext(
                                'product.msg_uom_modify_category',
                                uom=uom.rec_name),
                            gettext('product.msg_uom_modify_options'))
                if 'digits' in values:
                    if values['digits'] < uom.digits:
                        raise UOMAccessError(gettext(
                                'product.msg_uom_decrease_digits',
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
            raise ValueError("missing from_UoM")
        if to_uom is None:
            raise ValueError("missing to_UoM")
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
            raise ValueError("missing from_UoM")
        if to_uom is None:
            raise ValueError("missing to_UoM")
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
