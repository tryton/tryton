"Currency"

from trytond.osv import fields, OSV, ExceptOSV
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
    rounding = fields.Numeric('Rounding factor', digits=(12, 6))
    digits = fields.Integer('Diplay Digits')
    active = fields.Boolean('Active')

    def __init__(self):
        super(Currency, self).__init__()
        self._order.insert(0, ('code', 'ASC'))

    def default_active(self, cursor, user, context=None):
        return True

    def default_rounding(self, cursor, user, context=None):
        return 0.01

    def default_digits(self, cursor, user, context=None):
        return 2

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
        if (not from_currency.rate) or (not to_currency.rate):
            date = context.get('date', time.strftime('%Y-%m-%d'))
            if not from_currency.rate:
                name = from_currency.name
            else:
                name = to_currency.name
            raise ExceptOSV('UserError', 'No rate found \n' \
                    'for the currency: %s \n' \
                    'at the date: %s' % (name, date))
        if to_currency == from_currency:
            if round:
                return self.round(cursor, user, to_currency, amount)
            else:
                return amount
        else:
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

Rate()

