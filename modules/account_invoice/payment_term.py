# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from sql import Column

from trytond.model import (
    ModelView, ModelSQL, DeactivableMixin, fields, sequence_ordered)
from trytond import backend
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.wizard import Wizard, StateView, Button
from trytond.config import config

__all__ = ['PaymentTerm', 'PaymentTermLine', 'PaymentTermLineRelativeDelta',
    'TestPaymentTerm', 'TestPaymentTermView', 'TestPaymentTermViewResult']


class PaymentTerm(DeactivableMixin, ModelSQL, ModelView):
    'Payment Term'
    __name__ = 'account.invoice.payment_term'
    name = fields.Char('Name', size=None, required=True, translate=True)
    description = fields.Text('Description', translate=True)
    lines = fields.One2Many('account.invoice.payment_term.line', 'payment',
            'Lines')

    @classmethod
    def __setup__(cls):
        super(PaymentTerm, cls).__setup__()
        cls._order.insert(0, ('name', 'ASC'))
        cls._error_messages.update({
                'invalid_line': ('Invalid line "%(line)s" in payment term '
                    '"%(term)s".'),
                'missing_remainder': ('Missing remainder line in payment term '
                    '"%s".'),
                'last_remainder': ('Last line of payment term "%s" must be of '
                    'type remainder.'),
                })

    @classmethod
    def validate(cls, terms):
        super(PaymentTerm, cls).validate(terms)
        for term in terms:
            term.check_remainder()

    def check_remainder(self):
        if not self.lines or not self.lines[-1].type == 'remainder':
            self.raise_user_error('last_remainder', self.rec_name)

    def compute(self, amount, currency, date=None):
        """Calculate payment terms and return a list of tuples
        with (date, amount) for each payment term line.

        amount must be a Decimal used for the calculation.
        If specified, date will be used as the start date, otherwise current
        date will be used.
        """
        # TODO implement business_days
        # http://pypi.python.org/pypi/BusinessHours/
        Date = Pool().get('ir.date')

        sign = 1 if amount >= Decimal('0.0') else -1
        res = []
        if date is None:
            date = Date.today()
        remainder = amount
        for line in self.lines:
            value = line.get_value(remainder, amount, currency)
            value_date = line.get_date(date)
            if value is None or not value_date:
                if (not remainder) and line.amount:
                    self.raise_user_error('invalid_line', {
                            'line': line.rec_name,
                            'term': self.rec_name,
                            })
                else:
                    continue
            if ((remainder - value) * sign) < Decimal('0.0'):
                res.append((value_date, remainder))
                break
            if value:
                res.append((value_date, value))
            remainder -= value
        else:
            # Enforce to have at least one term
            if not res:
                res.append((date, Decimal(0)))

        if not currency.is_zero(remainder):
            self.raise_user_error('missing_remainder', (self.rec_name,))
        return res


class PaymentTermLine(sequence_ordered(), ModelSQL, ModelView):
    'Payment Term Line'
    __name__ = 'account.invoice.payment_term.line'
    payment = fields.Many2One('account.invoice.payment_term', 'Payment Term',
            required=True, ondelete="CASCADE")
    type = fields.Selection([
            ('fixed', 'Fixed'),
            ('percent', 'Percentage on Remainder'),
            ('percent_on_total', 'Percentage on Total'),
            ('remainder', 'Remainder'),
            ], 'Type', required=True)
    ratio = fields.Numeric('Ratio', digits=(14, 10),
        states={
            'invisible': ~Eval('type').in_(['percent', 'percent_on_total']),
            'required': Eval('type').in_(['percent', 'percent_on_total']),
            }, depends=['type'])
    divisor = fields.Numeric('Divisor', digits=(10, 14),
        states={
            'invisible': ~Eval('type').in_(['percent', 'percent_on_total']),
            'required': Eval('type').in_(['percent', 'percent_on_total']),
            }, depends=['type'])
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
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    relativedeltas = fields.One2Many(
        'account.invoice.payment_term.line.delta', 'line', 'Deltas')

    @classmethod
    def __setup__(cls):
        super(PaymentTermLine, cls).__setup__()
        cls._error_messages.update({
                'invalid_ratio_and_divisor': ('Ratio and '
                    'Divisor values are not consistent in line "%(line)s" '
                    'of payment term "%(term)s".'),
                })

    @classmethod
    def __register__(cls, module_name):
        sql_table = cls.__table__()
        super(PaymentTermLine, cls).__register__(module_name)
        cursor = Transaction().connection.cursor()
        table = cls.__table_handler__(module_name)

        # Migration from 3.8: rename percentage into ratio
        if table.column_exist('percentage'):
            cursor.execute(*sql_table.update(
                    columns=[sql_table.ratio],
                    values=[sql_table.percentage / 100]))
            table.drop_column('percentage')

    @staticmethod
    def default_currency_digits():
        return 2

    @staticmethod
    def default_type():
        return 'remainder'

    @classmethod
    def default_relativedeltas(cls):
        if Transaction().user == 0:
            return []
        return [{}]

    @fields.depends('type')
    def on_change_type(self):
        if self.type != 'fixed':
            self.amount = Decimal('0.0')
            self.currency = None
        if self.type not in ('percent', 'percent_on_total'):
            self.ratio = Decimal('0.0')
            self.divisor = Decimal('0.0')

    @fields.depends('ratio')
    def on_change_ratio(self):
        if not self.ratio:
            self.divisor = Decimal('0.0')
        else:
            self.divisor = self.round(1 / self.ratio,
                self.__class__.divisor.digits[1])

    @fields.depends('divisor')
    def on_change_divisor(self):
        if not self.divisor:
            self.ratio = Decimal('0.0')
        else:
            self.ratio = self.round(1 / self.divisor,
                self.__class__.ratio.digits[1])

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    def get_delta(self):
        return {
            'day': self.day,
            'month': int(self.month) if self.month else None,
            'days': self.days,
            'weeks': self.weeks,
            'months': self.months,
            'weekday': int(self.weekday) if self.weekday else None,
            }

    def get_date(self, date):
        for relativedelta_ in self.relativedeltas:
            date += relativedelta_.get()
        return date

    def get_value(self, remainder, amount, currency):
        Currency = Pool().get('currency.currency')
        if self.type == 'fixed':
            fixed = Currency.compute(self.currency, self.amount, currency)
            return fixed.copy_sign(amount)
        elif self.type == 'percent':
            return currency.round(remainder * self.ratio)
        elif self.type == 'percent_on_total':
            return currency.round(amount * self.ratio)
        elif self.type == 'remainder':
            return currency.round(remainder)
        return None

    @staticmethod
    def round(number, digits):
        quantize = Decimal(10) ** -Decimal(digits)
        return Decimal(number).quantize(quantize)

    @classmethod
    def validate(cls, lines):
        super(PaymentTermLine, cls).validate(lines)
        cls.check_ratio_and_divisor(lines)

    @classmethod
    def check_ratio_and_divisor(cls, lines):
        "Check consistency between ratio and divisor"
        # Use a copy because on_change will change the records
        for line in cls.browse(lines):
            if line.type not in ('percent', 'percent_on_total'):
                continue
            if line.ratio is None or line.divisor is None:
                cls.raise_user_error('invalid_ratio_and_divisor', {
                        'line': line.rec_name,
                        'term': line.payment.rec_name,
                        })
            if (line.ratio != round(
                        1 / line.divisor, cls.ratio.digits[1])
                    and line.divisor != round(
                        1 / line.ratio, cls.divisor.digits[1])):
                cls.raise_user_error('invalid_ratio_and_divisor', {
                        'line': line.rec_name,
                        'term': line.payment.rec_name,
                        })


class PaymentTermLineRelativeDelta(sequence_ordered(), ModelSQL, ModelView):
    'Payment Term Line Relative Delta'
    __name__ = 'account.invoice.payment_term.line.delta'
    line = fields.Many2One('account.invoice.payment_term.line',
        'Payment Term Line', required=True, ondelete='CASCADE')
    day = fields.Integer('Day of Month',
        domain=['OR',
            ('day', '=', None),
            [('day', '>=', 1), ('day', '<=', 31)],
            ])
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

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        pool = Pool()
        Line = pool.get('account.invoice.payment_term.line')
        sql_table = cls.__table__()
        line = Line.__table__()

        # Migration from 4.0: rename long table
        old_model_name = 'account.invoice.payment_term.line.relativedelta'
        old_table = config.get(
            'table', old_model_name, default=old_model_name.replace('.', '_'))
        if TableHandler.table_exist(old_table):
            TableHandler.table_rename(old_table, cls._table)

        super(PaymentTermLineRelativeDelta, cls).__register__(module_name)

        line_table = Line.__table_handler__(module_name)

        # Migration from 3.4
        fields = ['day', 'month', 'weekday', 'months', 'weeks', 'days']
        if any(line_table.column_exist(f) for f in fields):
            columns = ([line.id.as_('line')]
                + [Column(line, f) for f in fields])
            cursor.execute(*sql_table.insert(
                    columns=[sql_table.line]
                    + [Column(sql_table, f) for f in fields],
                    values=line.select(*columns)))
            for field in fields:
                line_table.drop_column(field)

    @staticmethod
    def default_months():
        return 0

    @staticmethod
    def default_weeks():
        return 0

    @staticmethod
    def default_days():
        return 0

    def get(self):
        "Return the relativedelta"
        return relativedelta(
            day=self.day,
            month=int(self.month) if self.month else None,
            days=self.days,
            weeks=self.weeks,
            months=self.months,
            weekday=int(self.weekday) if self.weekday else None,
            )


class TestPaymentTerm(Wizard):
    'Test Payment Term'
    __name__ = 'account.invoice.payment_term.test'
    start_state = 'test'
    test = StateView('account.invoice.payment_term.test',
        'account_invoice.payment_term_test_view_form',
        [Button('Close', 'end', 'tryton-close', default=True)])

    def default_test(self, fields):
        context = Transaction().context
        default = {}
        if context['active_model'] == 'account.invoice.payment_term':
            default['payment_term'] = context['active_id']
        return default


class TestPaymentTermView(ModelView):
    'Test Payment Term'
    __name__ = 'account.invoice.payment_term.test'
    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term', required=True)
    date = fields.Date('Date')
    amount = fields.Numeric('Amount', required=True,
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    currency_digits = fields.Integer('Currency Digits')
    result = fields.One2Many('account.invoice.payment_term.test.result',
        None, 'Result', readonly=True)

    @staticmethod
    def default_currency():
        pool = Pool()
        Company = pool.get('company.company')
        company = Transaction().context.get('company')
        if company:
            return Company(company).currency.id

    @fields.depends('currency')
    def on_change_with_currency_digits(self):
        if self.currency:
            return self.currency.digits
        return 2

    @fields.depends('payment_term', 'date', 'amount', 'currency', 'result')
    def on_change_with_result(self):
        pool = Pool()
        Result = pool.get('account.invoice.payment_term.test.result')
        result = []
        if (self.payment_term and self.amount and self.currency):
            for date, amount in self.payment_term.compute(
                    self.amount, self.currency, self.date):
                result.append(Result(
                        date=date, amount=amount,
                        currency_digits=self.currency.digits))
        self.result = result
        return self._changed_values.get('result', [])


class TestPaymentTermViewResult(ModelView):
    'Test Payment Term'
    __name__ = 'account.invoice.payment_term.test.result'
    date = fields.Date('Date', readonly=True)
    amount = fields.Numeric('Amount', readonly=True,
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    currency_digits = fields.Integer('Currency Digits')
