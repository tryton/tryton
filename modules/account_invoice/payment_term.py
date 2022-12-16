#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
import datetime
import time
from dateutil.relativedelta import relativedelta
from trytond.model import ModelView, ModelSQL, fields
from trytond.backend import TableHandler
from trytond.pyson import Not, Equal, Eval
from trytond.transaction import Transaction


class PaymentTerm(ModelSQL, ModelView):
    'Payment Term'
    _name = 'account.invoice.payment_term'
    _description = __doc__
    name = fields.Char('Payment Term', size=None, required=True, translate=True)
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
        '''
        Return list with (date, amount) for each payment term lines
        '''
        #TODO implement business_days
        # http://pypi.python.org/pypi/BusinessHours/
        type_obj = self.pool.get('account.invoice.payment_term.line.type')
        delay_obj = self.pool.get(
                'account.invoice.payment_term.line.delay')
        currency_obj = self.pool.get('currency.currency')
        date_obj = self.pool.get('ir.date')

        res = []
        if date is None:
            date = date_obj.today()
        remainder = amount
        for line in payment_term.lines:
            value = type_obj.get_value(line, remainder, currency)
            value_date = delay_obj.get_date(line, date)
            if not value or not value_date:
                if (not remainder) and line.amount:
                    self.raise_user_error('invalid_line')
                else:
                    continue
            res.append((value_date, value))
            remainder -= value
        if not currency_obj.is_zero(currency, remainder):
            self.raise_user_error('missing_remainder')
        return res

PaymentTerm()


class PaymentTermLineType(ModelSQL, ModelView):
    'Payment Term Line Type'
    _name = 'account.invoice.payment_term.line.type'
    _description = __doc__
    name = fields.Char('Name', size=None, translate=True, required=True)
    code = fields.Char('Code', size=None, required=True)

    def __init__(self):
        super(PaymentTermLineType, self).__init__()
        self._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
        ]
        self._order.insert(0, ('name', 'ASC'))

    def get_value(self, line, amount, currency):
        currency_obj = self.pool.get('currency.currency')
        if line.type == 'fixed':
            return currency_obj.compute(line.currency, line.amount, currency)
        elif line.type == 'percent':
            return currency_obj.round(currency,
                    amount * line.percentage / Decimal('100'))
        elif line.type == 'remainder':
            return currency_obj.round(currency, amount)
        return None

PaymentTermLineType()


class PaymentTermLineDelay(ModelSQL, ModelView):
    'Payment Term Line Delay'
    _name = 'account.invoice.payment_term.line.delay'
    _description = __doc__
    name = fields.Char('Name', size=None, translate=True, required=True)
    code = fields.Char('Code', size=None, required=True)

    def __init__(self):
        super(PaymentTermLineDelay, self).__init__()
        self._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
        ]
        self._order.insert(0, ('name', 'ASC'))

    def get_date(self, line, date):
        value = None
        if line.delay in ('net_days', 'end_month'):
            value = date + relativedelta(days=line.days)
            if line.delay == 'end_month':
                value += relativedelta(day=31)
        return value

PaymentTermLineDelay()


class PaymentTermLine(ModelSQL, ModelView):
    'Payment Term Line'
    _name = 'account.invoice.payment_term.line'
    _description = __doc__
    sequence = fields.Integer('Sequence',
            help='Use to order lines in ascending order')
    payment = fields.Many2One('account.invoice.payment_term', 'Payment Term',
            required=True, ondelete="CASCADE")
    type = fields.Selection('get_type', 'Type', required=True,
            on_change=['type'])
    percentage = fields.Numeric('Percentage', digits=(16, 8),
            states={
                'invisible': Not(Equal(Eval('type'), 'percent')),
                'required': Equal(Eval('type'), 'percent'),
            }, help='In %')
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
            states={
                'invisible': Not(Equal(Eval('type'), 'fixed')),
                'required': Equal(Eval('type'), 'fixed'),
            })
    currency = fields.Many2One('currency.currency', 'Currency',
            states={
                'invisible': Not(Equal(Eval('type'), 'fixed')),
                'required': Equal(Eval('type'), 'fixed'),
            })
    currency_digits = fields.Function(fields.Integer('Currency Digits',
        on_change_with=['currency']), 'get_currency_digits')
    days = fields.Integer('Number of Days')
    delay = fields.Selection('get_delay', 'Condition', required=True)

    def __init__(self):
        super(PaymentTermLine, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

    def init(self, module_name):
        super(PaymentTermLine, self).init(module_name)
        cursor = Transaction().cursor
        table = TableHandler(cursor, self, module_name)

        # Migration from 1.0 percent change into percentage
        if table.column_exist('percent'):
            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET percentage = percent * 100')
            table.drop_column('percent', exception=True)

    def default_type(self):
        return 'remainder'

    def default_delay(self):
        return 'net_days'

    def get_type(self):
        type_obj = self.pool.get('account.invoice.payment_term.line.type')
        type_ids = type_obj.search([])
        types = type_obj.browse(type_ids)
        return [(x.code, x.name) for x in types]

    def get_delay(self):
        delay_obj = self.pool.get('account.invoice.payment_term.line.delay')
        delay_ids = delay_obj.search([])
        delays = delay_obj.browse(delay_ids)
        return [(x.code, x.name) for x in delays]

    def on_change_type(self, vals):
        if not 'type' in vals:
            return {}
        res = {}
        if vals['type'] != 'fixed':
            res['amount'] = Decimal('0.0')
            res['currency'] =  False
        if vals['type'] != 'percent':
            res['percentage'] =  Decimal('0.0')
        return res

    def on_change_with_currency_digits(self, vals):
        currency_obj = self.pool.get('currency.currency')
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

PaymentTermLine()


