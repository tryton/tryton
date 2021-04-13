# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import logging

from decimal import Decimal, ROUND_HALF_EVEN, localcontext

from dateutil.relativedelta import relativedelta

from sql import Window
from sql.functions import NthValue

try:
    from forex_python.converter import CurrencyRates, RatesNotAvailableError
    get_rates = CurrencyRates(force_decimal=True).get_rates
except ImportError:
    CurrencyRates = get_rates = None

from trytond.i18n import gettext
from trytond.model import (
    ModelView, ModelSQL, DeactivableMixin, fields, Unique, Check, SymbolMixin)
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.rpc import RPC
from trytond.pyson import Eval, If

from .exceptions import RateError
from .ir import rate_decimal

logger = logging.getLogger(__name__)


class Currency(SymbolMixin, DeactivableMixin, ModelSQL, ModelView):
    'Currency'
    __name__ = 'currency.currency'
    name = fields.Char('Name', required=True, translate=True,
        help="The main identifier of the currency.")
    symbol = fields.Char('Symbol', size=10, required=True,
        help="The symbol used for currency formating.")
    code = fields.Char('Code', size=3, required=True,
        help="The 3 chars ISO currency code.")
    numeric_code = fields.Char('Numeric Code', size=3,
        help="The 3 digits ISO currency code.")
    rate = fields.Function(fields.Numeric(
            "Current rate", digits=(rate_decimal * 2, rate_decimal)),
        'get_rate')
    rates = fields.One2Many('currency.currency.rate', 'currency', 'Rates',
        help="Add floating exchange rates for the currency.")
    rounding = fields.Numeric('Rounding factor', required=True,
        digits=(12, Eval('digits', 6)), depends=['digits'],
        help="The minimum amount which can be represented in this currency.")
    digits = fields.Integer("Digits", required=True,
        help="The number of digits to display after the decimal separator.")

    @classmethod
    def __setup__(cls):
        super(Currency, cls).__setup__()
        cls._order.insert(0, ('code', 'ASC'))
        cls.__rpc__.update({
                'compute': RPC(instantiate=slice(0, 3, 2)),
                })

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Data = pool.get('ir.model.data')
        data = Data.__table__()
        cursor = Transaction().connection.cursor()

        super(Currency, cls).__register__(module_name)

        table_h = cls.__table_handler__(module_name)

        # Migration from 4.6: removal of monetary
        for col in [
                'mon_grouping', 'mon_decimal_point',
                'p_sign_posn', 'n_sign_posn']:
            table_h.not_null_action(col, 'remove')

        # Migration from 5.2: remove country data
        cursor.execute(*data.delete(where=(data.module == 'currency')
                & (data.model == cls.__name__)))

    @staticmethod
    def default_rounding():
        return Decimal('0.01')

    @staticmethod
    def default_digits():
        return 2

    @classmethod
    def check_xml_record(cls, records, values):
        return True

    @classmethod
    def search_global(cls, text):
        for record, rec_name, icon in super(Currency, cls).search_global(text):
            icon = icon or 'tryton-currency'
            yield record, rec_name, icon

    @classmethod
    def search_rec_name(cls, name, clause):
        currencies = None
        field = None
        for field in ('code', 'numeric_code'):
            currencies = cls.search([(field,) + tuple(clause[1:])], limit=1)
            if currencies:
                break
        if currencies:
            return [(field,) + tuple(clause[1:])]
        return [(cls._rec_name,) + tuple(clause[1:])]

    @fields.depends('rates')
    def on_change_with_rate(self):
        now = datetime.date.today()
        closer = datetime.date.min
        res = Decimal('0.0')
        for rate in self.rates or []:
            date = getattr(rate, 'date', None) or now
            if date <= now and date > closer:
                res = rate.rate
                closer = date
        return res

    @staticmethod
    def get_rate(currencies, name):
        '''
        Return the rate at the date from the context or the current date
        '''
        Rate = Pool().get('currency.currency.rate')
        Date = Pool().get('ir.date')

        res = {}
        date = Transaction().context.get('date', Date.today())
        for currency in currencies:
            rates = Rate.search([
                    ('currency', '=', currency.id),
                    ('date', '<=', date),
                    ], limit=1, order=[('date', 'DESC')])
            if rates:
                res[currency.id] = rates[0].id
            else:
                res[currency.id] = 0
        rate_ids = [x for x in res.values() if x]
        rates = Rate.browse(rate_ids)
        id2rate = {}
        for rate in rates:
            id2rate[rate.id] = rate
        for currency_id in res.keys():
            if res[currency_id]:
                res[currency_id] = id2rate[res[currency_id]].rate
        return res

    def round(self, amount, rounding=ROUND_HALF_EVEN):
        'Round the amount depending of the currency'
        return self._round(amount, self.rounding, rounding)

    @classmethod
    def _round(cls, amount, factor, rounding):
        with localcontext() as ctx:
            ctx.prec = max(ctx.prec, (amount / factor).adjusted() + 1)
            # Divide and multiple by factor for case factor is not 10En
            result = (amount / factor).quantize(Decimal('1.'),
                    rounding=rounding) * factor
        return Decimal(result)

    def is_zero(self, amount):
        'Return True if the amount can be considered as zero for the currency'
        return abs(self.round(amount)) < self.rounding

    @classmethod
    def compute(cls, from_currency, amount, to_currency, round=True):
        '''
        Take a currency and an amount
        Return the amount to the new currency
        Use the rate of the date of the context or the current date
        '''
        Date = Pool().get('ir.date')
        Lang = Pool().get('ir.lang')
        from_currency = cls(int(from_currency))
        to_currency = cls(int(to_currency))

        if to_currency == from_currency:
            if round:
                return to_currency.round(amount)
            else:
                return amount
        if (not from_currency.rate) or (not to_currency.rate):
            date = Transaction().context.get('date', Date.today())
            if not from_currency.rate:
                name = from_currency.name
            else:
                name = to_currency.name

            lang = Lang.get()
            raise RateError(gettext('currency.msg_no_rate',
                    currency=name,
                    date=lang.strftime(date)))
        if round:
            return to_currency.round(
                amount * to_currency.rate / from_currency.rate)
        else:
            return amount * to_currency.rate / from_currency.rate

    @classmethod
    def currency_rate_sql(cls):
        "Return a SQL query with currency, rate, start_date and end_date"
        pool = Pool()
        Rate = pool.get('currency.currency.rate')
        transaction = Transaction()
        database = transaction.database

        rate = Rate.__table__()
        if database.has_window_functions():
            window = Window(
                [rate.currency],
                order_by=[rate.date.asc],
                frame='ROWS', start=0, end=1)
            # Use NthValue instead of LastValue to get NULL for the last row
            end_date = NthValue(rate.date, 2, window=window)
        else:
            next_rate = Rate.__table__()
            end_date = next_rate.select(
                next_rate.date,
                where=(next_rate.currency == rate.currency)
                & (next_rate.date > rate.date),
                order_by=[next_rate.date.asc],
                limit=1)

        query = (rate
            .select(
                rate.currency.as_('currency'),
                rate.rate.as_('rate'),
                rate.date.as_('start_date'),
                end_date.as_('end_date'),
                ))
        return query

    def get_symbol(self, sign, symbol=None):
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get()
        symbol, position = super().get_symbol(sign, symbol=symbol)
        if ((sign < 0 and lang.n_cs_precedes)
                or (sign >= 0 and lang.p_cs_precedes)):
            position = 0
        return symbol, position


class CurrencyRate(ModelSQL, ModelView):
    "Currency Rate"
    __name__ = 'currency.currency.rate'
    date = fields.Date('Date', required=True, select=True,
        help="From when the rate applies.")
    rate = fields.Numeric(
        "Rate", digits=(rate_decimal * 2, rate_decimal), required=1,
        help="The floating exchange rate used to convert the currency.")
    currency = fields.Many2One('currency.currency', 'Currency',
            ondelete='CASCADE',
        help="The currency on which the rate applies.")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('currency')
        t = cls.__table__()
        cls._sql_constraints = [
            ('date_currency_uniq', Unique(t, t.date, t.currency),
                'currency.msg_currency_unique_rate_date'),
            ('check_currency_rate', Check(t, t.rate >= 0),
                'currency.msg_currency_rate_positive'),
            ]
        cls._order.insert(0, ('date', 'DESC'))

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()

    @classmethod
    def check_xml_record(cls, records, values):
        return True

    def get_rec_name(self, name):
        return str(self.date)


class CronFetchError(Exception):
    pass


class Cron(ModelSQL, ModelView):
    "Currency Cron"
    __name__ = 'currency.cron'

    source = fields.Selection(
        [], "Source", required=True,
        help="The external source for rates.")
    frequency = fields.Selection([
            ('daily', "Daily"),
            ('weekly', "Weekly"),
            ('monthly', "Monthly"),
            ], "Frequency", required=True,
        help="How frequently rates must be updated.")
    weekday = fields.Many2One(
        'ir.calendar.day', "Day of Week",
        states={
            'required': Eval('frequency') == 'weekly',
            'invisible': Eval('frequency') != 'weekly',
            },
        depends=['frequency'])
    day = fields.Integer(
        "Day of Month",
        domain=[If(Eval('frequency') == 'monthly',
                [('day', '>=', 1), ('day', '<=', 31)],
                [('day', '=', None)]),
            ],
        states={
            'required': Eval('frequency') == 'monthly',
            'invisible': Eval('frequency') != 'monthly',
            },
        depends=['frequency'])
    currency = fields.Many2One(
        'currency.currency', "Currency", required=True,
        help="The base currency to fetch rate.")
    currencies = fields.Many2Many(
        'currency.cron-currency.currency', 'cron', 'currency', "Currencies",
        help="The currencies to update the rate.")
    last_update = fields.Date("Last Update", required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'run': {},
                })
        if CurrencyRates:
            cls.source.selection.append(('ecb', "European Central Bank"))

    @classmethod
    def default_frequency(cls):
        return 'monthly'

    @classmethod
    def default_day(cls):
        return 1

    @classmethod
    def default_last_update(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()

    @classmethod
    @ModelView.button
    def run(cls, crons):
        cls.update(crons)

    @classmethod
    def update(cls, crons=None):
        pool = Pool()
        Rate = pool.get('currency.currency.rate')
        if crons is None:
            crons = cls.search([])
        rates = []
        for cron in crons:
            rates.extend(cron._update())
        Rate.save(rates)
        cls.save(crons)

    def _update(self):
        limit = self.limit_update()
        date = self.next_update()
        while date <= limit:
            try:
                yield from self._rates(date)
            except CronFetchError:
                logger.warning("Could not fetch rates temporary")
                break
            except Exception:
                logger.error("Fail to fetch rates", exc_info=True)
                break
            self.last_update = date
            date = self.next_update()

    def next_update(self):
        return self.last_update + self.delta()

    def limit_update(self):
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()

    def delta(self):
        if self.frequency == 'daily':
            delta = relativedelta(days=1)
        elif self.frequency == 'weekly':
            delta = relativedelta(weeks=1, weekday=int(self.weekday.index))
        elif self.frequency == 'monthly':
            delta = relativedelta(months=1, day=self.day)
        else:
            delta = relativedelta()
        return delta

    def _rates(self, date, rounding=None):
        pool = Pool()
        Rate = pool.get('currency.currency.rate')
        values = getattr(self, 'fetch_%s' % self.source)(date)

        exp = Decimal(Decimal(1) / 10 ** Rate.rate.digits[1])
        rates = Rate.search([
                ('date', '=', date),
                ])
        code2rates = {r.currency.code: r for r in rates}

        def get_rate(currency):
            if currency.code in code2rates:
                rate = code2rates[currency.code]
            else:
                rate = Rate(date=date, currency=currency)
            return rate

        rate = get_rate(self.currency)
        rate.rate = Decimal(1).quantize(exp, rounding=rounding)
        yield rate

        for currency in self.currencies:
            if currency.code not in values:
                continue
            value = values[currency.code]
            rate = get_rate(currency)
            rate.rate = value.quantize(exp, rounding=rounding)
            yield rate

    def fetch_ecb(self, date):
        try:
            return get_rates(self.currency.code, date)
        except RatesNotAvailableError as e:
            raise CronFetchError() from e


class Cron_Currency(ModelSQL):
    "Currency Cron - Currency"
    __name__ = 'currency.cron-currency.currency'

    cron = fields.Many2One(
        'currency.cron', "Cron",
        required=True, select=True, ondelete='CASCADE')
    currency = fields.Many2One(
        'currency.currency', "Currency",
        required=True, ondelete='CASCADE')
