#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from trytond.model import ModelView, ModelSQL, fields
from trytond.backend import TableHandler
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool


class PaymentTerm(ModelSQL, ModelView):
    'Payment Term'
    _name = 'account.invoice.payment_term'
    _description = __doc__
    name = fields.Char('Payment Term', size=None, required=True,
        translate=True)
    active = fields.Boolean('Active')
    description = fields.Text('Description', translate=True)
    lines = fields.One2Many('account.invoice.payment_term.line', 'payment',
            'Lines')

    def __init__(self):
        super(PaymentTerm, self).__init__()
        self._order.insert(0, ('name', 'ASC'))
        self._error_messages.update({
            'invalid_line': 'Invalid payment term line!',
            'missing_remainder': 'Payment term missing a remainder line!',
            })

    def default_active(self):
        return True

    def compute(self, amount, currency, payment_term, date=None):
        """Calculate payment terms and return a list of tuples
        with (date, amount) for each payment term line.

        amount must be a Decimal used for the calculation and
        both currency and payment_term must be BrowseRecord. If
        specified, date will be used as the start date, otherwise
        current date will be used.
        """
        #TODO implement business_days
        # http://pypi.python.org/pypi/BusinessHours/
        pool = Pool()
        line_obj = pool.get('account.invoice.payment_term.line')
        currency_obj = pool.get('currency.currency')
        date_obj = pool.get('ir.date')

        sign = 1 if amount >= Decimal('0.0') else -1
        res = []
        if date is None:
            date = date_obj.today()
        remainder = amount
        for line in payment_term.lines:
            value = line_obj.get_value(line, remainder, amount, currency)
            value_date = line_obj.get_date(line, date)
            if not value or not value_date:
                if (not remainder) and line.amount:
                    self.raise_user_error('invalid_line')
                else:
                    continue
            if ((remainder - value) * sign) < Decimal('0.0'):
                res.append((value_date, remainder))
                break
            res.append((value_date, value))
            remainder -= value

        if not currency_obj.is_zero(currency, remainder):
            self.raise_user_error('missing_remainder')
        return res

PaymentTerm()


class PaymentTermLine(ModelSQL, ModelView):
    'Payment Term Line'
    _name = 'account.invoice.payment_term.line'
    _description = __doc__
    sequence = fields.Integer('Sequence', required=True,
            help='Use to order lines in ascending order')
    payment = fields.Many2One('account.invoice.payment_term', 'Payment Term',
            required=True, ondelete="CASCADE")
    type = fields.Selection([
            ('fixed', 'Fixed'),
            ('percent', 'Percentage on Remainder'),
            ('percent_on_total', 'Percentage on Total'),
            ('remainder', 'Remainder'),
            ], 'Type', required=True,
            on_change=['type'])
    percentage = fields.Numeric('Percentage', digits=(16, 8),
        states={
            'invisible': ~Eval('type').in_(['percent', 'percent_on_total']),
            'required': Eval('type').in_(['percent', 'percent_on_total']),
            }, on_change=['percentage'], depends=['type'])
    divisor = fields.Numeric('Divisor', digits=(16, 8),
        states={
            'invisible': ~Eval('type').in_(['percent', 'percent_on_total']),
            'required': Eval('type').in_(['percent', 'percent_on_total']),
            }, on_change=['divisor'], depends=['type'])
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
        states={
            'invisible': Eval('type') != 'fixed',
            'required': Eval('type') == 'fixed',
            }, depends=['type', 'currency_digits'])
    currency = fields.Many2One('currency.currency', 'Currency',
        states={
            'invisible': Eval('type') != 'fixed',
            'required': Eval('type') == 'fixed',
            }, depends=['type'])
    currency_digits = fields.Function(fields.Integer('Currency Digits',
        on_change_with=['currency']), 'get_currency_digits')
    day = fields.Integer('Day of Month')
    month = fields.Selection([
            (None, ''),
            ('1', 'January'),
            ('2', 'February'),
            ('3', 'March'),
            ('4', 'April'),
            ('5', 'May'),
            ('6', 'June'),
            ('7', 'July'),
            ('8', 'August'),
            ('9', 'September'),
            ('10', 'October'),
            ('11', 'November'),
            ('12', 'December'),
            ], 'Month', sort=False)
    weekday = fields.Selection([
            (None, ''),
            ('0', 'Monday'),
            ('1', 'Tuesday'),
            ('2', 'Wednesday'),
            ('3', 'Thursday'),
            ('4', 'Friday'),
            ('5', 'Saturday'),
            ('6', 'Sunday'),
            ], 'Day of Week', sort=False)
    months = fields.Integer('Number of Months', required=True)
    weeks = fields.Integer('Number of Weeks', required=True)
    days = fields.Integer('Number of Days', required=True)

    def __init__(self):
        super(PaymentTermLine, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))
        self._sql_constraints += [
            ('day', 'CHECK(day BETWEEN 1 AND 31)',
                'Day of month must be between 1 and 31.'),
            ]
        self._constraints += [
            ('check_percentage_and_divisor', 'invalid_percentage_and_divisor'),
            ]
        self._error_messages.update({
                'invalid_percentage_and_divisor': 'Percentage and '
                        'Divisor values are not consistent.',
                })

    def init(self, module_name):
        super(PaymentTermLine, self).init(module_name)
        cursor = Transaction().cursor
        table = TableHandler(cursor, self, module_name)

        # Migration from 1.0 percent change into percentage
        if table.column_exist('percent'):
            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET percentage = percent * 100')
            table.drop_column('percent', exception=True)

        # Migration from 2.2
        if table.column_exist('delay'):
            cursor.execute('UPDATE "' + self._table + '" SET day = 31 '
                "WHERE delay = 'end_month'")
            table.drop_column('delay', exception=True)
            ids = self.search([])
            for line in self.browse(ids):
                if line.percentage:
                    self.write(line.id, {
                            'divisor': self.round(Decimal('100.0') /
                                line.percentage, self.divisor.digits[1]),
                            })

    def default_currency_digits(self):
        return 2

    def default_type(self):
        return 'remainder'

    def default_months(self):
        return 0

    def default_weeks(self):
        return 0

    def default_days(self):
        return 0

    def on_change_type(self, vals):
        if not 'type' in vals:
            return {}
        res = {}
        if vals['type'] != 'fixed':
            res['amount'] = Decimal('0.0')
            res['currency'] = None
        if vals['type'] not in ('percent', 'percent_on_total'):
            res['percentage'] = Decimal('0.0')
            res['divisor'] = Decimal('0.0')
        return res

    def on_change_percentage(self, value):
        if not value.get('percentage'):
            return {'divisor': 0.0}
        return {
            'divisor': self.round(Decimal('100.0') / value['percentage'],
                self.divisor.digits[1]),
            }

    def on_change_divisor(self, value):
        if not value.get('divisor'):
            return {'percentage': 0.0}
        return {
            'percentage': self.round(Decimal('100.0') / value['divisor'],
                self.percentage.digits[1]),
            }

    def on_change_with_currency_digits(self, vals):
        currency_obj = Pool().get('currency.currency')
        if vals.get('currency'):
            currency = currency_obj.browse(vals['currency'])
            return currency.digits
        return 2

    def get_currency_digits(self, ids, name):
        res = {}
        for line in self.browse(ids):
            if line.currency:
                res[line.id] = line.currency.digits
            else:
                res[line.id] = 2
        return res

    def get_delta(self, line):
        return {
            'day': line.day,
            'month': int(line.month) if line.month else None,
            'days': line.days,
            'weeks': line.weeks,
            'months': line.months,
            'weekday': int(line.weekday) if line.weekday else None,
            }

    def get_date(self, line, date):
        return date + relativedelta(**self.get_delta(line))

    def get_value(self, line, remainder, amount, currency):
        currency_obj = Pool().get('currency.currency')
        if line.type == 'fixed':
            return currency_obj.compute(line.currency, line.amount, currency)
        elif line.type == 'percent':
            return currency_obj.round(currency,
                remainder * line.percentage / Decimal('100'))
        elif line.type == 'percent_on_total':
            return currency_obj.round(currency,
                amount * line.percentage / Decimal('100'))
        elif line.type == 'remainder':
            return currency_obj.round(currency, remainder)
        return None

    @staticmethod
    def round(number, digits):
        quantize = Decimal(10) ** -Decimal(digits)
        return Decimal(number).quantize(quantize)

    def check_percentage_and_divisor(self, ids):
        "Check consistency between percentage and divisor"
        percentage_digits = self.percentage.digits[1]
        divisor_digits = self.divisor.digits[1]
        for line in self.browse(ids):
            if line.type not in ('percent', 'percent_on_total'):
                continue
            if line.percentage is None or line.divisor is None:
                return False
            if line.percentage == line.divisor == Decimal('0.0'):
                continue
            percentage = line.percentage
            divisor = line.divisor
            calc_percentage = self.round(Decimal('100.0') / divisor,
                    percentage_digits)
            calc_divisor = self.round(Decimal('100.0') / percentage,
                    divisor_digits)
            if (percentage == Decimal('0.0') or divisor == Decimal('0.0')
                    or percentage != calc_percentage
                    and divisor != calc_divisor):
                return False
        return True

PaymentTermLine()
