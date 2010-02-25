#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.
"Currency"
from trytond.model import ModelView, ModelSQL, fields
from trytond.tools import safe_eval, datetime_strftime
import time
from decimal import Decimal, ROUND_HALF_EVEN
import datetime


class Currency(ModelSQL, ModelView):
    'Currency'
    _name = 'currency.currency'
    _description = __doc__
    name = fields.Char('Name', required=True, translate=True)
    symbol = fields.Char('Symbol', size=10, required=True)
    code = fields.Char('Code', size=3, required=True)
    numeric_code = fields.Char('Numeric Code', size=3)
    rate = fields.Function('get_rate', type='numeric', string='Current rate',
            digits=(12, 6), on_change_with=['rates'])
    rates = fields.One2Many('currency.currency.rate', 'currency', 'Rates')
    rounding = fields.Numeric('Rounding factor', digits=(12, 6), required=True)
    digits = fields.Integer('Display Digits')
    active = fields.Boolean('Active')

    # monetary formatting
    mon_grouping = fields.Char('Grouping', required=True)
    mon_decimal_point = fields.Char('Decimal Separator', required=True)
    mon_thousands_sep = fields.Char('Thousands Separator')
    p_sign_posn = fields.Integer('Positive Sign Position')
    n_sign_posn = fields.Integer('Negative Sign Position')
    positive_sign = fields.Char('Positive Sign')
    negative_sign = fields.Char('Negative Sign')
    p_cs_precedes = fields.Boolean('Positive Currency Symbol Precedes')
    n_cs_precedes = fields.Boolean('Negative Currency Symbol Precedes')
    p_sep_by_space = fields.Boolean('Positive Separate by Space')
    n_sep_by_space = fields.Boolean('Negative Separate by Space')

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
        self._rpc.update({
            'compute': False,
            })

    def default_active(self, cursor, user, context=None):
        return True

    def default_rounding(self, cursor, user, context=None):
        return Decimal('0.01')

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
                grouping = safe_eval(currency.mon_grouping)
                for i in grouping:
                    if not isinstance(i, int):
                        return False
            except:
                return False
        return True

    def check_xml_record(self, cursor, user, ids, values, context=None):
        return True

    def search_rec_name(self, cursor, user, name, args, context=None):
        args2 = []
        i = 0
        while i < len(args):
            ids = []
            field = None
            for field in ('code', 'numeric_code'):
                ids = self.search(cursor, user,
                        [(field, args[i][1], args[i][2])],
                        limit=1, context=context)
                if len(ids):
                    break
            if len(ids):
                args2.append((field, args[i][1], args[i][2]))
            else:
                args2.append((self._rec_name, args[i][1], args[i][2]))
            i += 1
        return args2

    def on_change_with_rate(self, cursor, user, ids, vals, context=None):
        now = datetime.date.today()
        closer = datetime.date.min
        res = Decimal('0.0')
        for rate in vals.get('rates', []):
            if 'date' not in rate or 'rate' not in rate:
                continue
            if rate['date'] <= now and rate['date'] > closer:
                res = rate['rate']
                closer = rate['date']
        return res

    def get_rate(self, cursor, user, ids, name, arg, context=None):
        '''
        Return the rate at the date from the context or the current date
        '''
        rate_obj = self.pool.get('currency.currency.rate')
        date_obj = self.pool.get('ir.date')

        res = {}
        if context is None:
            context = {}
        date = context.get('date', date_obj.today(cursor, user,
            context=context))
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

    def round(self, cursor, user, currency, amount, rounding=ROUND_HALF_EVEN):
        '''
        Round the amount depending of the currency

        :param cursor: the database cursor
        :param user: the user id
        :param currency: a BrowseRecord of currency.currency
        :param amout: a Decimal
        :param rounding: the rounding option
        :return: a Decimal
        '''
        return (amount / currency.rounding).quantize(Decimal('1.'),
                rounding=rounding) * currency.rounding

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
        date_obj = self.pool.get('ir.date')
        lang_obj = self.pool.get('ir.lang')

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
            date = context.get('date', date_obj.today(cursor, user,
                context=context))
            if not from_currency.rate:
                name = from_currency.name
            else:
                name = to_currency.name

            for code in [context.get('language', False) or 'en_US', 'en_US']:
                lang_ids = lang_obj.search(cursor, user, [
                    ('code', '=', code),
                    ], context=context)
                if lang_ids:
                    break
            lang = lang_obj.browse(cursor, user, lang_ids[0], context=context)

            self.raise_user_error(cursor, 'no_rate', (name,
                datetime_strftime(date, str(lang.date))), context=context)
        if round:
            return self.round(cursor, user, to_currency,
                    amount * to_currency.rate / from_currency.rate)
        else:
            return amount * to_currency.rate / from_currency.rate

Currency()


class Rate(ModelSQL, ModelView):
    'Rate'
    _name = 'currency.currency.rate'
    _description = __doc__
    _rec_name = 'date'
    date = fields.Date('Date', required=True, select=1)
    rate = fields.Numeric('Rate', digits=(12, 6), required=1)
    currency = fields.Many2One('currency.currency', 'Currency',
            ondelete='CASCADE',)

    def __init__(self):
        super(Rate, self).__init__()
        self._sql_constraints = [
            ('date_currency_uniq', 'UNIQUE(date, currency)',
                'A currency can only have one rate by date!'),
        ]
        self._order.insert(0, ('date', 'DESC'))

    def default_date(self, cursor, user, context=None):
        date_obj = self.pool.get('ir.date')
        return date_obj.today(cursor, user, context=context)

    def check_xml_record(self, cursor, user, ids, values, context=None):
        return True

Rate()

