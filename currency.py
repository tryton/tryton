#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal, ROUND_HALF_EVEN
from trytond.model import ModelView, ModelSQL, fields
from trytond.tools import safe_eval, datetime_strftime
from trytond.transaction import Transaction
from trytond.pool import Pool


class Currency(ModelSQL, ModelView):
    'Currency'
    _name = 'currency.currency'
    _description = __doc__
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

    def default_active(self):
        return True

    def default_rounding(self):
        return Decimal('0.01')

    def default_digits(self):
        return 2

    def default_mon_grouping(self):
        return '[]'

    def default_mon_thousands_sep(self):
        return ','

    def default_mon_decimal_point(self):
        return '.'

    def default_p_sign_posn(self):
        return 1

    def default_n_sign_posn(self):
        return 1

    def default_negative_sign(self):
        return '-'

    def default_positive_sign(self):
        return ''

    def default_p_cs_precedes(self):
        return True

    def default_n_cs_precedes(self):
        return True

    def default_p_sep_by_space(self):
        return False

    def default_n_sep_by_space(self):
        return False

    def check_mon_grouping(self, ids):
        '''
        Check if mon_grouping is list of numbers
        '''
        for currency in self.browse(ids):
            try:
                grouping = safe_eval(currency.mon_grouping)
                for i in grouping:
                    if not isinstance(i, int):
                        return False
            except Exception:
                return False
        return True

    def check_xml_record(self, ids, values):
        return True

    def search_rec_name(self, name, clause):
        ids = []
        field = None
        for field in ('code', 'numeric_code'):
            ids = self.search([(field,) + clause[1:]], limit=1)
            if ids:
                break
        if ids:
            return [(field,) + clause[1:]]
        return [(self._rec_name,) + clause[1:]]

    def on_change_with_rate(self, vals):
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

    def get_rate(self, ids, name):
        '''
        Return the rate at the date from the context or the current date
        '''
        rate_obj = Pool().get('currency.currency.rate')
        date_obj = Pool().get('ir.date')

        res = {}
        date = Transaction().context.get('date', date_obj.today())
        for currency_id in ids:
            rate_ids = rate_obj.search([
                ('currency', '=', currency_id),
                ('date', '<=', date),
                ], limit=1, order=[('date', 'DESC')])
            if rate_ids:
                res[currency_id] = rate_ids[0]
            else:
                res[currency_id] = 0.0
        rate_ids = [x for x in res.values() if x]
        rates = rate_obj.browse(rate_ids)
        id2rate = {}
        for rate in rates:
            id2rate[rate.id] = rate
        for currency_id in res.keys():
            if res[currency_id]:
                res[currency_id] = id2rate[res[currency_id]].rate
        return res

    def round(self, currency, amount, rounding=ROUND_HALF_EVEN):
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

    def is_zero(self, currency, amount):
        'Return True if the amount can be considered as zero for the currency'
        return abs(self.round(currency, amount)) < currency.rounding

    def compute(self, from_currency, amount, to_currency, round=True):
        '''
        Take a currency and an amount
        Return the amount to the new currency
        Use the rate of the date of the context or the current date if ids are
        given
        '''
        date_obj = Pool().get('ir.date')
        lang_obj = Pool().get('ir.lang')

        if isinstance(from_currency, (int, long)):
            from_currency = self.browse(from_currency)
        if isinstance(to_currency, (int, long)):
            to_currency = self.browse(to_currency)
        if to_currency == from_currency:
            if round:
                return self.round(to_currency, amount)
            else:
                return amount
        if (not from_currency.rate) or (not to_currency.rate):
            date = Transaction().context.get('date', date_obj.today())
            if not from_currency.rate:
                name = from_currency.name
            else:
                name = to_currency.name

            lang_id, = lang_obj.search([
                    ('code', '=', Transaction().language),
                    ])
            lang = lang_obj.browse(lang_id)

            self.raise_user_error('no_rate', (name,
                datetime_strftime(date, str(lang.date))))
        if round:
            return self.round(to_currency,
                    amount * to_currency.rate / from_currency.rate)
        else:
            return amount * to_currency.rate / from_currency.rate

Currency()


class Rate(ModelSQL, ModelView):
    'Rate'
    _name = 'currency.currency.rate'
    _description = __doc__
    _rec_name = 'date'
    date = fields.Date('Date', required=True, select=True)
    rate = fields.Numeric('Rate', digits=(12, 6), required=1)
    currency = fields.Many2One('currency.currency', 'Currency',
            ondelete='CASCADE',)

    def __init__(self):
        super(Rate, self).__init__()
        self._sql_constraints = [
            ('date_currency_uniq', 'UNIQUE(date, currency)',
                'A currency can only have one rate by date!'),
            ('check_currency_rate', 'CHECK(rate >= 0)',
                'The currency rate must greater than or equal to 0'),
        ]
        self._order.insert(0, ('date', 'DESC'))

    def default_date(self):
        date_obj = Pool().get('ir.date')
        return date_obj.today()

    def check_xml_record(self, ids, values):
        return True

Rate()

