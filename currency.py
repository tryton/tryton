#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal, ROUND_HALF_EVEN
from trytond.model import ModelView, ModelSQL, fields
from trytond.tools import safe_eval, datetime_strftime
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.rpc import RPC

__all__ = ['Currency', 'Rate']


class Currency(ModelSQL, ModelView):
    'Currency'
    __name__ = 'currency.currency'
    name = fields.Char('Name', required=True, translate=True)
    symbol = fields.Char('Symbol', size=10, required=True)
    code = fields.Char('Code', size=3, required=True)
    numeric_code = fields.Char('Numeric Code', size=3)
    rate = fields.Function(fields.Numeric('Current rate', digits=(12, 6),
        on_change_with=['rates']), 'get_rate')
    rates = fields.One2Many('currency.currency.rate', 'currency', 'Rates')
    rounding = fields.Numeric('Rounding factor', digits=(12, 6), required=True)
    digits = fields.Integer('Display Digits', required=True)
    active = fields.Boolean('Active')

    # monetary formatting
    mon_grouping = fields.Char('Grouping', required=True)
    mon_decimal_point = fields.Char('Decimal Separator', required=True)
    mon_thousands_sep = fields.Char('Thousands Separator')
    p_sign_posn = fields.Integer('Positive Sign Position', required=True)
    n_sign_posn = fields.Integer('Negative Sign Position', required=True)
    positive_sign = fields.Char('Positive Sign')
    negative_sign = fields.Char('Negative Sign')
    p_cs_precedes = fields.Boolean('Positive Currency Symbol Precedes')
    n_cs_precedes = fields.Boolean('Negative Currency Symbol Precedes')
    p_sep_by_space = fields.Boolean('Positive Separate by Space')
    n_sep_by_space = fields.Boolean('Negative Separate by Space')

    @classmethod
    def __setup__(cls):
        super(Currency, cls).__setup__()
        cls._order.insert(0, ('code', 'ASC'))
        cls._constraints += [
            ('check_mon_grouping', 'invalid_mon_grouping'),
            ]
        cls._error_messages.update({
                'no_rate': 'No rate found for the currency: ' \
                    '%s at the date: %s',
                'invalid_grouping': 'Invalid Grouping!',
                })
        cls.__rpc__.update({
                'compute': RPC(),
                })

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_rounding():
        return Decimal('0.01')

    @staticmethod
    def default_digits():
        return 2

    @staticmethod
    def default_mon_grouping():
        return '[]'

    @staticmethod
    def default_mon_thousands_sep():
        return ','

    @staticmethod
    def default_mon_decimal_point():
        return '.'

    @staticmethod
    def default_p_sign_posn():
        return 1

    @staticmethod
    def default_n_sign_posn():
        return 1

    @staticmethod
    def default_negative_sign():
        return '-'

    @staticmethod
    def default_positive_sign():
        return ''

    @staticmethod
    def default_p_cs_precedes():
        return True

    @staticmethod
    def default_n_cs_precedes():
        return True

    @staticmethod
    def default_p_sep_by_space():
        return False

    @staticmethod
    def default_n_sep_by_space():
        return False

    def check_mon_grouping(self):
        '''
        Check if mon_grouping is list of numbers
        '''
        try:
            grouping = safe_eval(self.mon_grouping)
            for i in grouping:
                if not isinstance(i, int):
                    return False
        except Exception:
            return False
        return True

    @classmethod
    def check_xml_record(cls, records, values):
        return True

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

    def on_change_with_rate(self):
        now = datetime.date.today()
        closer = datetime.date.min
        res = Decimal('0.0')
        for rate in self.rates or []:
            if 'date' not in rate or 'rate' not in rate:
                continue
            if rate['date'] <= now and rate['date'] > closer:
                res = rate['rate']
                closer = rate['date']
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
        '''
        Round the amount depending of the currency

        :param cursor: the database cursor
        :param user: the user id
        :param currency: a BrowseRecord of currency.currency
        :param amout: a Decimal
        :param rounding: the rounding option
        :return: a Decimal
        '''
        return (amount / self.rounding).quantize(Decimal('1.'),
                rounding=rounding) * self.rounding

    def is_zero(self, amount):
        'Return True if the amount can be considered as zero for the currency'
        return abs(self.round(amount)) < self.rounding

    @classmethod
    def compute(cls, from_currency, amount, to_currency, round=True):
        '''
        Take a currency and an amount
        Return the amount to the new currency
        Use the rate of the date of the context or the current date if ids are
        given
        '''
        Date = Pool().get('ir.date')
        Lang = Pool().get('ir.lang')
        from_currency = cls(from_currency.id)
        to_currency = cls(to_currency.id)

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

            lang, = Lang.search([
                    ('code', '=', Transaction().language),
                    ])

            cls.raise_user_error('no_rate', (name,
                    datetime_strftime(date, str(lang.date))))
        if round:
            return to_currency.round(
                amount * to_currency.rate / from_currency.rate)
        else:
            return amount * to_currency.rate / from_currency.rate


class Rate(ModelSQL, ModelView):
    'Rate'
    __name__ = 'currency.currency.rate'
    _rec_name = 'date'
    date = fields.Date('Date', required=True, select=True)
    rate = fields.Numeric('Rate', digits=(12, 6), required=1)
    currency = fields.Many2One('currency.currency', 'Currency',
            ondelete='CASCADE',)

    @classmethod
    def __setup__(cls):
        super(Rate, cls).__setup__()
        cls._sql_constraints = [
            ('date_currency_uniq', 'UNIQUE(date, currency)',
                'A currency can only have one rate by date!'),
            ('check_currency_rate', 'CHECK(rate >= 0)',
                'The currency rate must greater than or equal to 0'),
            ]
        cls._order.insert(0, ('date', 'DESC'))

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()

    @classmethod
    def check_xml_record(self, records, values):
        return True
