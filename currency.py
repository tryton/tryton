#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Currency"

from trytond.osv import fields, OSV
import time
from decimal import Decimal
import datetime


class Currency(OSV):
    'Currency'
    _name = 'currency.currency'
    _description = __doc__
    name = fields.Char('Name', required=True, translate=True)
    symbol = fields.Char('Symbol', size=10, required=True)
    code = fields.Char('Code', size=3, required=True)
    rate = fields.Function('get_rate', string='Current rate', digits=(12, 6))
    rates = fields.One2Many('currency.currency.rate', 'currency', 'Rates')
    rounding = fields.Numeric('Rounding factor', digits=(12, 6), required=True)
    digits = fields.Integer('Diplay Digits')
    active = fields.Boolean('Active')

    # monetary formatting
    mon_grouping = fields.Char('Grouping', required=True)
    mon_decimal_point = fields.Char('Decimal Separator', required=True)
    mon_thousands_sep = fields.Char('Thousands Separator')
    p_sign_posn = fields.Integer('Positive Sign Position')
    n_sign_posn = fields.Integer('Negative Sign Position')
    positive_sign = fields.Char('Positive Sign')
    negative_sign = fields.Char('Negative Sign')
    p_cs_precedes = fields.Boolean('Positive Sign Precedes')
    n_cs_precedes = fields.Boolean('Negative Sign Precedes')
    p_sep_by_space = fields.Boolean('Positive Sign Separate by Space')
    n_sep_by_space = fields.Boolean('Negative Sign Separate by Space')

    def __init__(self):
        super(Currency, self).__init__()
        self._order.insert(0, ('code', 'ASC'))
        self._constraints += [
            ('check_mon_grouping', 'invalid_mon_grouping'),
        ]
        self._error_messages.update({
            'no_rate': 'No rate found for the currency: %s at the date: %s',
            'invalid_grouping': 'Invalid Grouping!',
            })

    def default_active(self, cursor, user, context=None):
        return True

    def default_rounding(self, cursor, user, context=None):
        return 0.01

    def default_digits(self, cursor, user, context=None):
        return 2

    def default_mon_grouping(self, cursor, user, context=None):
        return '[]'

    def default_mon_thousands_sep(self, cursor, user, context=None):
        return ','

    def default_mon_decimal_point(self, cursor, user, context=None):
        return '.'

    def default_p_sign_posn(self, cursor, user, context=None):
        return 1

    def default_n_sign_posn(self, cursor, user, context=None):
        return 1

    def default_negative_sign(self, cursor, user, context=None):
        return '-'

    def default_positive_sign(self, cursor, user, context=None):
        return ''

    def default_p_cs_precedes(self, cursor, user, context=None):
        return True

    def default_n_cs_precedes(self, cursor, user, context=None):
        return True

    def default_p_sep_by_space(self, cursor, user, context=None):
        return False

    def default_n_sep_by_space(self, cursor, user, context=None):
        return False

    def check_mon_grouping(self, cursor, user, ids):
        '''
        Check if mon_grouping is list of numbers
        '''
        for currency in self.browse(cursor, user, ids):
            try:
                grouping = eval(currency.mon_grouping)
                for i in grouping:
                    if not isinstance(i, int):
                        return False
            except:
                return False
        return True

    def name_search(self, cursor, user, name, args=None, operator='ilike',
            context=None, limit=None):
        if args is None:
            args = []
        args_name = args[:]
        args_code = args[:]
        if name:
            args_name += [(self._rec_name, operator, name)]
            args_code += [('code', operator, name)]
        ids = self.search(cursor, user, args_code, limit=limit, context=context)
        if len(ids) != 1:
            ids += self.search(cursor, user, args_name, limit=limit,
                    context=context)
        res = self.name_get(cursor, user, ids, context=context)
        return res

    def get_rate(self, cursor, user, ids, name, arg, context=None):
        '''
        Return the rate at the date from the context or the current date
        '''
        res = {}
        rate_obj = self.pool.get('currency.currency.rate')
        if context is None:
            context = {}
        date = context.get('date', time.strftime('%Y-%m-%d'))
        for currency_id in ids:
            rate_ids = rate_obj.search(cursor, user, [
                ('currency', '=', currency_id),
                ('date', '<=', date),
                ], limit=1, order=[('date', 'DESC')])
            if rate_ids:
                res[currency_id] = rate_ids[0]
            else:
                res[currency_id] = 0.0
        rate_ids = [x for x in res.values() if x]
        rates = rate_obj.browse(cursor, user, rate_ids, context=context)
        id2rate = {}
        for rate in rates:
            id2rate[rate.id] = rate
        for currency_id in res.keys():
            if res[currency_id]:
                res[currency_id] = id2rate[res[currency_id]].rate
        return res

    def round(self, cursor, user, currency, amount):
        'Round the amount depending of the currency'
        return (amount / currency.rounding).quantize(Decimal('1.')) * currency.rounding

    def is_zero(self, cursor, user, currency, amount):
        'Return True if the amount can be considered as zero for the currency'
        return abs(self.round(cursor, user, currency, amount)) < currency.rounding

    def compute(self, cursor, user, from_currency, amount, to_currency,
            round=True, context=None):
        '''
        Take a currency and an amount
        Return the amount to the new currency
        Use the rate of the date of the context or the current date
        '''
        if context is None:
            context = {}
        if isinstance(from_currency, (int, long)):
            from_currency = self.browse(cursor, user, from_currency, context=context)
        if isinstance(to_currency, (int, long)):
            to_currency = self.browse(cursor, user, to_currency, context=context)
        if to_currency == from_currency:
            if round:
                return self.round(cursor, user, to_currency, amount)
            else:
                return amount
        if (not from_currency.rate) or (not to_currency.rate):
            date = context.get('date', time.strftime('%Y-%m-%d'))
            if not from_currency.rate:
                name = from_currency.name
            else:
                name = to_currency.name
            self.raise_user_error(cursor, 'no_rate', (name, date),
                    context=context)
        if round:
            return self.round(cursor, user, to_currency,
                    amount * to_currency.rate / from_currency.rate)
        else:
            return amount * to_currency.rate / from_currency.rate

Currency()


class Rate(OSV):
    'Rate'
    _name = 'currency.currency.rate'
    _description = __doc__
    _rec_name = 'date'
    date = fields.Date('Date', required=True, select=1)
    rate = fields.Numeric('Rate', digits=(12, 6), required=1)
    currency = fields.Many2One('currency.currency', 'Currency')

    def __init__(self):
        super(Rate, self).__init__()
        self._sql_constraints = [
            ('date_currency_uniq', 'UNIQUE(date, currency)',
                'A currency can only have one rate by date!'),
        ]
        self._order.insert(0, ('date', 'DESC'))

    def default_date(self, cursor, user, context=None):
        return datetime.date.today()

    def check_xml_record(self, cursor, user, ids, values, context=None):
        return True

Rate()

