#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.backend import TableHandler
from decimal import Decimal
import datetime
import mx.DateTime


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

    def default_active(self, cursor, user, context=None):
        return True

    def compute(self, cursor, user, amount, currency, payment_term, date=None,
            context=None):
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
            date = date_obj.today(cursor, user, context=context)
        remainder = amount
        for line in payment_term.lines:
            value = type_obj.get_value(cursor, user, line, remainder, currency,
                    context)
            value_date = delay_obj.get_date(cursor, user, line, date, context)
            if not value or not value_date:
                if (not remainder) and line.amount:
                    self.raise_user_error(cursor, 'invalid_line',
                            context=context)
                else:
                    continue
            res.append((value_date, value))
            remainder -= value
        if not currency_obj.is_zero(cursor, user, currency, remainder):
            self.raise_user_error(cursor, 'missing_remainder',
                    context=context)
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

    def get_value(self, cursor, user, line, amount, currency, context=None):
        currency_obj = self.pool.get('currency.currency')
        if line.type == 'fixed':
            return currency_obj.compute(cursor, user, line.currency,
                    line.amount, currency, context=context)
        elif line.type == 'percent':
            return currency_obj.round(cursor, user, currency,
                    amount * line.percentage / Decimal('100'))
        elif line.type == 'remainder':
            return currency_obj.round(cursor, user, currency, amount)
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

    def get_date(self, cursor, user, line, date, context=None):
        value = None
        if line.delay == 'net_days':
            value = mx.DateTime.strptime(str(date), '%Y-%m-%d') + \
                    mx.DateTime.RelativeDateTime(days=line.days)
        elif line.delay == 'end_month':
            value = mx.DateTime.strptime(str(date), '%Y-%m-%d') + \
                    mx.DateTime.RelativeDateTime(days=line.days) + \
                    mx.DateTime.RelativeDateTime(day=-1)
        if value:
            return datetime.date(value.year, value.month, value.day)
        return None

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
                'invisible': "type != 'percent'",
                'required': "type == 'percent'",
            }, help='In %')
    amount = fields.Numeric('Amount', digits="(16, currency_digits)",
            states={
                'invisible': "type != 'fixed'",
                'required': "type == 'fixed'",
            })
    currency = fields.Many2One('currency.currency', 'Currency',
            states={
                'invisible': "type != 'fixed'",
                'required': "type == 'fixed'",
            })
    currency_digits = fields.Function('get_currency_digits', type='integer',
            string='Currency Digits', on_change_with=['currency'])
    days = fields.Integer('Number of Days')
    delay = fields.Selection('get_delay', 'Condition', required=True)

    def __init__(self):
        super(PaymentTermLine, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

    def init(self, cursor, module_name):
        super(PaymentTermLine, self).init(cursor, module_name)
        table = TableHandler(cursor, self, module_name)

        # Migration from 1.0 percent change into percentage
        if table.column_exist('percent'):
            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET percentage = percent * 100')
            table.drop_column('percent', exception=True)

    def default_type(self, cursor, user, context=None):
        return 'remainder'

    def default_delay(self, cursor, user, context=None):
        return 'net_days'

    def get_type(self, cursor, user, context=None):
        type_obj = self.pool.get('account.invoice.payment_term.line.type')
        type_ids = type_obj.search(cursor, user, [], context=context)
        types = type_obj.browse(cursor, user, type_ids, context=context)
        return [(x.code, x.name) for x in types]

    def get_delay(self, cursor, user, context=None):
        delay_obj = self.pool.get('account.invoice.payment_term.line.delay')
        delay_ids = delay_obj.search(cursor, user, [], context=context)
        delays = delay_obj.browse(cursor, user, delay_ids,
                context=context)
        return [(x.code, x.name) for x in delays]

    def on_change_type(self, cursor, user, ids, vals, context=None):
        if not 'type' in vals:
            return {}
        res = {}
        if vals['type'] != 'fixed':
            res['amount'] = Decimal('0.0')
            res['currency'] =  False
        if vals['type'] != 'percent':
            res['percentage'] =  Decimal('0.0')
        return res

    def on_change_with_currency_digits(self, cursor, user, ids, vals,
            context=None):
        currency_obj = self.pool.get('currency.currency')
        if vals.get('currency'):
            currency = currency_obj.browse(cursor, user, vals['currency'],
                    context=context)
            return currency.digits
        return 2

    def get_currency_digits(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for line in self.browse(cursor, user, ids, context=context):
            if line.currency:
                res[line.id] = line.currency.digits
            else:
                res[line.id] = 2
        return res

PaymentTermLine()


