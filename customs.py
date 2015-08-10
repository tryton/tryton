# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal

from sql import Null

from trytond.model import ModelSQL, ModelView, MatchMixin, fields
from trytond.pyson import Eval, If, Bool
from trytond.pool import Pool

from trytond.modules.product import price_digits

__all__ = ['TariffCode', 'DutyRate']

# Use 2 chars numbering to allow string comparison
MONTHS = [
    (None, ''),
    ('01', 'January'),
    ('02', 'February'),
    ('03', 'March'),
    ('04', 'April'),
    ('05', 'May'),
    ('06', 'June'),
    ('07', 'July'),
    ('08', 'August'),
    ('09', 'September'),
    ('10', 'October'),
    ('11', 'November'),
    ('12', 'December'),
    ]


class TariffCode(ModelSQL, ModelView, MatchMixin):
    'Tariff Code'
    __name__ = 'customs.tariff.code'
    _rec_name = 'code'
    code = fields.Char('Code', required=True,
        help='The code from Harmonized System of Nomenclature')
    description = fields.Char('Description', translate=True)
    active = fields.Boolean('Active', select=True)
    country = fields.Many2One('country.country', 'Country')
    # TODO country group
    start_month = fields.Selection(MONTHS, 'Start Month', sort=False,
        states={
            'required': Eval('end_month') | Eval('start_day'),
            },
        depends=['end_month', 'start_day'])
    start_day = fields.Integer('Start Day',
        domain=['OR',
            ('start_day', '<=', If(Eval('start_month').in_(
                        ['01', '03', '05', '07', '08', '10', '12']), 31,
                    If(Eval('start_month') == '02', 29, 30))),
            ('start_day', '=', None),
            ],
        states={
            'required': Bool(Eval('start_month')),
            },
        depends=['start_month'])
    end_month = fields.Selection(MONTHS, 'End Month', sort=False,
        states={
            'required': Eval('start_month') | Eval('end_day'),
            },
        depends=['start_month', 'end_day'])
    end_day = fields.Integer('End Day',
        domain=['OR',
            ('end_day', '<=', If(Eval('end_month').in_(
                        ['01', '03', '05', '07', '08', '10', '12']), 31,
                    If(Eval('end_month') == '02', 29, 30))),
            ('end_day', '=', None),
            ],
        states={
            'required': Bool(Eval('end_month')),
            },
        depends=['end_month'])
    duty_rates = fields.One2Many('customs.duty.rate', 'tariff_code',
        'Duty Rates')

    @classmethod
    def __setup__(cls):
        super(TariffCode, cls).__setup__()
        cls._order.insert(0, ('code', 'ASC'))

    @classmethod
    def default_active(cls):
        return True

    def match(self, pattern):
        if 'date' in pattern:
            pattern = pattern.copy()
            date = pattern.pop('date')
            if self.start_month and self.end_month:
                start = (int(self.start_month), self.start_day)
                end = (int(self.end_month), self.end_day)
                date = (date.month, date.day)
                if start <= end:
                    if not (start <= date <= end):
                        return False
                else:
                    if end <= date <= start:
                        return False
        return super(TariffCode, self).match(pattern)

    def get_duty_rate(self, pattern):
        for rate in self.duty_rates:
            if rate.match(pattern):
                return rate


class DutyRate(ModelSQL, ModelView, MatchMixin):
    'Duty Rate'
    __name__ = 'customs.duty.rate'
    tariff_code = fields.Many2One('customs.tariff.code', 'Tariff Code',
        required=True, select=True)
    country = fields.Many2One('country.country', 'Country')
    # TODO country group
    type = fields.Selection([
            ('import', 'Import'),
            ('export', 'Export'),
            ], 'Type')
    start_date = fields.Date('Start Date',
        domain=['OR',
            ('start_date', '<=', If(Bool(Eval('end_date')),
                    Eval('end_date', datetime.date.max), datetime.date.max)),
            ('start_date', '=', None),
            ],
        depends=['end_date'])
    end_date = fields.Date('End Date',
        domain=['OR',
            ('end_date', '>=', If(Bool(Eval('start_date')),
                    Eval('start_date', datetime.date.min), datetime.date.min)),
            ('end_date', '=', None),
            ],
        depends=['start_date'])
    computation_type = fields.Selection([
            ('amount', 'Amount'),
            ('quantity', 'Quantity'),
            ], 'Computation Type')
    amount = fields.Numeric('Amount', digits=price_digits,
        states={
            'required': Eval('computation_type').in_(['amount', 'quantity']),
            'invisible': ~Eval('computation_type').in_(['amount', 'quantity']),
            },
        depends=['computation_type'])
    currency = fields.Many2One('currency.currency', 'Currency',
        states={
            'required': Eval('computation_type').in_(['amount', 'quantity']),
            'invisible': ~Eval('computation_type').in_(['amount', 'quantity']),
            },
        depends=['computation_type'])
    uom = fields.Many2One('product.uom', 'Uom',
        states={
            'required': Eval('computation_type') == 'quantity',
            'invisible': Eval('computation_type') != 'quantity',
            },
        depends=['computation_type'])

    @classmethod
    def __setup__(cls):
        super(DutyRate, cls).__setup__()
        cls._order.insert(0, ('start_date', 'ASC'))
        cls._order.insert(0, ('end_date', 'ASC'))

    @classmethod
    def default_type(cls):
        return 'import'

    @staticmethod
    def order_start_date(tables):
        table, _ = tables[None]
        return [table.start_date == Null, table.start_date]

    @staticmethod
    def order_end_date(tables):
        table, _ = tables[None]
        return [table.end_date == Null, table.end_date]

    def match(self, pattern):
        if 'date' in pattern:
            pattern = pattern.copy()
            start = self.start_date or datetime.date.min
            end = self.end_date or datetime.date.max
            if not (start <= pattern.pop('date') <= end):
                return False
        return super(DutyRate, self).match(pattern)

    def compute(self, currency, quantity, uom, **kwargs):
        return getattr(self, 'compute_%s' % self.computation_type)(
            currency, quantity, uom, **kwargs)

    def compute_amount(self, currency, quantity, uom, **kwargs):
        pool = Pool()
        Currency = pool.get('currency.currency')
        return Currency.compute(self.currency, self.amount, currency)

    def compute_quantity(self, currency, quantity, uom, **kwargs):
        pool = Pool()
        Currency = pool.get('currency.currency')
        Uom = pool.get('product.uom')

        amount = Uom.compute_price(self.uom, self.amount, uom)
        amount *= Decimal(str(quantity))
        return Currency.compute(self.currency, amount, currency)
