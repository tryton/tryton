# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sql import Column

from trytond import backend
from trytond.config import config
from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, ModelSQL, ModelView, fields, sequence_ordered)
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.wizard import Button, StateView, Wizard

from .exceptions import PaymentTermComputeError, PaymentTermValidationError


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

    @classmethod
    def validate_fields(cls, terms, field_names):
        super().validate_fields(terms, field_names)
        cls.check_remainder(terms, field_names)

    @classmethod
    def check_remainder(cls, terms, field_names=None):
        if field_names and 'lines' not in field_names:
            return
        for term in terms:
            if not term.lines or not term.lines[-1].type == 'remainder':
                raise PaymentTermValidationError(gettext(
                        'account_invoice'
                        '.msg_payment_term_missing_last_remainder',
                        payment_term=term.rec_name))

    def compute(self, amount, currency, date):
        """Calculate payment terms and return a list of tuples
        with (date, amount) for each payment term line.

        amount must be a Decimal used for the calculation.
        If specified, date will be used as the start date, otherwise current
        date will be used.
        """
        # TODO implement business_days
        # http://pypi.python.org/pypi/BusinessHours/
        sign = 1 if amount >= Decimal('0.0') else -1
        res = []
        remainder = amount
        for line in self.lines:
            value = line.get_value(remainder, amount, currency)
            value_date = line.get_date(date)
            if value is None or not value_date:
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
            raise PaymentTermComputeError(
                gettext('account_invoice.msg_payment_term_missing_remainder',
                    payment_term=self.rec_name))
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
            })
    divisor = fields.Numeric('Divisor', digits=(10, 14),
        states={
            'invisible': ~Eval('type').in_(['percent', 'percent_on_total']),
            'required': Eval('type').in_(['percent', 'percent_on_total']),
            })
    amount = Monetary(
        "Amount", currency='currency', digits='currency',
        states={
            'invisible': Eval('type') != 'fixed',
            'required': Eval('type') == 'fixed',
            })
    currency = fields.Many2One('currency.currency', 'Currency',
        states={
            'invisible': Eval('type') != 'fixed',
            'required': Eval('type') == 'fixed',
            })
    relativedeltas = fields.One2Many(
        'account.invoice.payment_term.line.delta', 'line', 'Deltas')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('payment')

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
    def validate_fields(cls, lines, field_names):
        super().validate_fields(lines, field_names)
        cls.check_ratio_and_divisor(lines, field_names)

    @classmethod
    def check_ratio_and_divisor(cls, lines, field_names=None):
        "Check consistency between ratio and divisor"
        if field_names and not (field_names & {'type', 'ratio', 'divisor'}):
            return
        for line in lines:
            if line.type not in ('percent', 'percent_on_total'):
                continue
            if line.ratio is None or line.divisor is None:
                raise PaymentTermValidationError(
                    gettext('account_invoice'
                        '.msg_payment_term_invalid_ratio_divisor',
                        line=line.rec_name))
            if (line.ratio != round(
                        1 / line.divisor, cls.ratio.digits[1])
                    and line.divisor != round(
                        1 / line.ratio, cls.divisor.digits[1])):
                raise PaymentTermValidationError(
                    gettext('account_invoice'
                        '.msg_payment_term_invalid_ratio_divisor',
                        line=line.rec_name))


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
    month = fields.Many2One('ir.calendar.month', "Month")
    weekday = fields.Many2One('ir.calendar.day', "Day of Week")
    months = fields.Integer('Number of Months', required=True)
    weeks = fields.Integer('Number of Weeks', required=True)
    days = fields.Integer('Number of Days', required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('line')

    @classmethod
    def __register__(cls, module_name):
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        pool = Pool()
        Line = pool.get('account.invoice.payment_term.line')
        Month = pool.get('ir.calendar.month')
        Day = pool.get('ir.calendar.day')
        sql_table = cls.__table__()
        line = Line.__table__()
        month = Month.__table__()
        day = Day.__table__()
        table_h = cls.__table_handler__(module_name)

        # Migration from 4.0: rename long table
        old_model_name = 'account.invoice.payment_term.line.relativedelta'
        old_table = config.get(
            'table', old_model_name, default=old_model_name.replace('.', '_'))
        if backend.TableHandler.table_exist(old_table):
            backend.TableHandler.table_rename(old_table, cls._table)

        # Migration from 5.0: use ir.calendar
        migrate_calendar = False
        if (backend.TableHandler.table_exist(cls._table)
                and table_h.column_exist('month')
                and table_h.column_exist('weekday')):
            migrate_calendar = (
                table_h.column_is_type('month', 'VARCHAR')
                or table_h.column_is_type('weekday', 'VARCHAR'))
            if migrate_calendar:
                table_h.column_rename('month', '_temp_month')
                table_h.column_rename('weekday', '_temp_weekday')

        super(PaymentTermLineRelativeDelta, cls).__register__(module_name)

        table_h = cls.__table_handler__(module_name)
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

        # Migration from 5.0: use ir.calendar
        if migrate_calendar:
            update = transaction.connection.cursor()
            cursor.execute(*month.select(month.id, month.index))
            for month_id, index in cursor:
                update.execute(*sql_table.update(
                        [sql_table.month], [month_id],
                        where=sql_table._temp_month == str(index)))
            table_h.drop_column('_temp_month')
            cursor.execute(*day.select(day.id, day.index))
            for day_id, index in cursor:
                update.execute(*sql_table.update(
                        [sql_table.weekday], [day_id],
                        where=sql_table._temp_weekday == str(index)))
            table_h.drop_column('_temp_weekday')

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
            month=int(self.month.index) if self.month else None,
            days=self.days,
            weeks=self.weeks,
            months=self.months,
            weekday=int(self.weekday.index) if self.weekday else None,
            )


class TestPaymentTerm(Wizard):
    'Test Payment Term'
    __name__ = 'account.invoice.payment_term.test'
    start_state = 'test'
    test = StateView('account.invoice.payment_term.test',
        'account_invoice.payment_term_test_view_form',
        [Button('Close', 'end', 'tryton-close', default=True)])

    def default_test(self, fields):
        default = {}
        if (self.model
                and self.model.__name__ == 'account.invoice.payment_term'):
            default['payment_term'] = self.record.id if self.record else None
        return default


class TestPaymentTermView(ModelView):
    'Test Payment Term'
    __name__ = 'account.invoice.payment_term.test'
    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term', required=True)
    date = fields.Date('Date')
    amount = Monetary(
        "Amount", currency='currency', digits='currency', required=True)
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    result = fields.One2Many('account.invoice.payment_term.test.result',
        None, 'Result', readonly=True)

    @staticmethod
    def default_currency():
        pool = Pool()
        Company = pool.get('company.company')
        company = Transaction().context.get('company')
        if company:
            return Company(company).currency.id

    @fields.depends('payment_term', 'date', 'amount', 'currency', 'result')
    def on_change_with_result(self):
        pool = Pool()
        Result = pool.get('account.invoice.payment_term.test.result')
        result = []
        if (self.payment_term and self.amount and self.currency):
            for date, amount in self.payment_term.compute(
                    self.amount, self.currency, self.date):
                result.append(Result(
                        date=date,
                        amount=amount,
                        currency=self.currency))
        self.result = result
        return self._changed_values.get('result', [])


class TestPaymentTermViewResult(ModelView):
    'Test Payment Term'
    __name__ = 'account.invoice.payment_term.test.result'
    date = fields.Date('Date', readonly=True)
    amount = Monetary(
        "Amount", currency='currency', digits='currency', readonly=True)
    currency = fields.Many2One('currency.currency', "Currency")
