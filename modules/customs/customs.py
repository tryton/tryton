# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal

from sql import Null

from trytond import backend
from trytond.model import (
    DeactivableMixin, MatchMixin, ModelSQL, ModelView, fields)
from trytond.modules.product import price_digits
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, If
from trytond.transaction import Transaction


class CountryMatchMixin(MatchMixin):
    country = fields.Many2One(
        'country.country', "Country",
        states={
            'invisible': Bool(Eval('organization')),
            })
    organization = fields.Many2One(
        'country.organization', "Organization",
        states={
            'invisible': Bool(Eval('country')),
            })

    def match(self, pattern, match_none=False):
        if 'country' in pattern:
            pattern = pattern.copy()
            country = pattern.pop('country')
            if country is not None or match_none:
                if self.country and self.country.id != country:
                    return False
                if (self.organization
                        and country not in [
                            c.id for c in self.organization.countries]):
                    return False
        return super().match(pattern, match_none=match_none)


class TariffCode(DeactivableMixin, CountryMatchMixin, ModelSQL, ModelView):
    __name__ = 'customs.tariff.code'
    _rec_name = 'code'
    code = fields.Char('Code', required=True,
        help='The code from Harmonized System of Nomenclature.')
    description = fields.Char('Description', translate=True)
    start_month = fields.Many2One('ir.calendar.month', "Start Month",
        states={
            'required': Eval('end_month') | Eval('start_day'),
            })
    start_day = fields.Integer('Start Day',
        domain=['OR',
            ('start_day', '=', None),
            [('start_day', '>=', 1), ('start_day', '<=', 31)],
            ],
        states={
            'required': Bool(Eval('start_month')),
            })
    end_month = fields.Many2One('ir.calendar.month', "End Month",
        states={
            'required': Eval('start_month') | Eval('end_day'),
            })
    end_day = fields.Integer('End Day',
        domain=['OR',
            ('end_day', '=', None),
            [('end_day', '>=', 1), ('end_day', '<=', 31)],
            ],
        states={
            'required': Bool(Eval('end_month')),
            })
    duty_rates = fields.One2Many('customs.duty.rate', 'tariff_code',
        'Duty Rates')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('code', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        pool = Pool()
        Month = pool.get('ir.calendar.month')
        sql_table = cls.__table__()
        month = Month.__table__()
        table_h = cls.__table_handler__(module_name)

        # Migration from 6.6: use ir.calendar
        migrate_calendar = False
        if (backend.TableHandler.table_exist(cls._table)
                and table_h.column_exist('start_month')
                and table_h.column_exist('end_month')):
            migrate_calendar = (
                table_h.column_is_type('start_month', 'VARCHAR')
                or table_h.column_is_type('end_month', 'VARCHAR'))
            if migrate_calendar:
                table_h.column_rename('start_month', '_temp_start_month')
                table_h.column_rename('end_month', '_temp_end_month')

        super().__register__(module_name)

        table_h = cls.__table_handler__(module_name)

        # Migration from 6.6: use ir.calendar
        if migrate_calendar:
            update = transaction.connection.cursor()
            cursor.execute(*month.select(month.id, month.index))
            for month_id, index in cursor:
                str_index = f'{index:02d}'
                update.execute(*sql_table.update(
                        [sql_table.start_month], [month_id],
                        where=sql_table._temp_start_month == str_index))
                update.execute(*sql_table.update(
                        [sql_table.end_month], [month_id],
                        where=sql_table._temp_end_month == str_index))
            table_h.drop_column('_temp_start_month')
            table_h.drop_column('_temp_end_month')

    def match(self, pattern, match_none=False):
        if 'date' in pattern:
            pattern = pattern.copy()
            date = pattern.pop('date')
            if self.start_month and self.end_month:
                start = (self.start_month.index, self.start_day)
                end = (self.end_month.index, self.end_day)
                date = (date.month, date.day)
                if start <= end:
                    if not (start <= date <= end):
                        return False
                else:
                    if end <= date <= start:
                        return False
        return super().match(pattern, match_none=match_none)

    def get_duty_rate(self, pattern):
        for rate in self.duty_rates:
            if rate.match(pattern):
                return rate


class DutyRate(CountryMatchMixin, ModelSQL, ModelView):
    __name__ = 'customs.duty.rate'
    tariff_code = fields.Many2One(
        'customs.tariff.code', "Tariff Code", required=True)
    type = fields.Selection([
            ('import', 'Import'),
            ('export', 'Export'),
            ], 'Type')
    start_date = fields.Date('Start Date',
        domain=['OR',
            ('start_date', '<=', If(Bool(Eval('end_date')),
                    Eval('end_date', datetime.date.max), datetime.date.max)),
            ('start_date', '=', None),
            ])
    end_date = fields.Date('End Date',
        domain=['OR',
            ('end_date', '>=', If(Bool(Eval('start_date')),
                    Eval('start_date', datetime.date.min), datetime.date.min)),
            ('end_date', '=', None),
            ])
    computation_type = fields.Selection([
            ('amount', 'Amount'),
            ('quantity', 'Quantity'),
            ], 'Computation Type')
    amount = fields.Numeric('Amount', digits=price_digits,
        states={
            'required': Eval('computation_type').in_(['amount', 'quantity']),
            'invisible': ~Eval('computation_type').in_(['amount', 'quantity']),
            })
    currency = fields.Many2One('currency.currency', 'Currency',
        states={
            'required': Eval('computation_type').in_(['amount', 'quantity']),
            'invisible': ~Eval('computation_type').in_(['amount', 'quantity']),
            })
    uom = fields.Many2One(
        'product.uom', "UoM",
        states={
            'required': Eval('computation_type') == 'quantity',
            'invisible': Eval('computation_type') != 'quantity',
            },
        help="The Unit of Measure.")

    @classmethod
    def __setup__(cls):
        super().__setup__()
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
        return super().match(pattern)

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
