#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Sales extension for managing leads and opportunities"
import datetime
import time
from trytond.model import ModelView, ModelSQL, Workflow, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.backend import FIELDS, TableHandler
from trytond.pyson import Equal, Eval, Not, In, If, Get, PYSONEncoder
from trytond.transaction import Transaction
from trytond.pool import Pool

__all__ = ['SaleOpportunity', 'SaleOpportunityLine',
    'SaleOpportunityHistory', 'SaleOpportunityEmployee',
    'OpenSaleOpportunityEmployeeStart', 'OpenSaleOpportunityEmployee',
    'SaleOpportunityMonthly', 'SaleOpportunityEmployeeMonthly']

STATES = [
    ('lead', 'Lead'),
    ('opportunity', 'Opportunity'),
    ('converted', 'Converted'),
    ('cancelled', 'Cancelled'),
    ('lost', 'Lost'),
]
_STATES_START = {
    'readonly': Eval('state') != 'lead',
    }
_DEPENDS_START = ['state']
_STATES_STOP = {
    'readonly': In(Eval('state'), ['converted', 'lost', 'cancelled']),
}
_DEPENDS_STOP = ['state']


class SaleOpportunity(Workflow, ModelSQL, ModelView):
    'Sale Opportunity'
    __name__ = "sale.opportunity"
    _history = True
    _rec_name = 'description'
    party = fields.Many2One('party.party', 'Party', required=True, select=True,
        on_change=['party'], states=_STATES_STOP, depends=_DEPENDS_STOP)
    address = fields.Many2One('party.address', 'Address',
        domain=[('party', '=', Eval('party'))],
        select=True, depends=['party', 'state'],
        states=_STATES_STOP)
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True, states=_STATES_STOP, domain=[
            ('id', If(In('company', Eval('context', {})), '=', '!='),
                Get(Eval('context', {}), 'company', 0)),
            ], on_change=['company'], depends=_DEPENDS_STOP)
    currency = fields.Function(fields.Many2One('currency.currency',
        'Currency'), 'get_currency')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
            'get_currency_digits')
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits'], help='Estimated revenue amount')
    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term', states={
            'required': Eval('state') == 'converted',
            'readonly': In(Eval('state'),
                ['converted', 'lost', 'cancelled']),
            },
        depends=['state'])
    employee = fields.Many2One('company.employee', 'Employee', required=True,
            states=_STATES_STOP, depends=['state', 'company'],
            domain=[('company', '=', Eval('company'))])
    start_date = fields.Date('Start Date', required=True, select=True,
        states=_STATES_START, depends=_DEPENDS_START)
    end_date = fields.Date('End Date', select=True, readonly=True, states={
        'invisible': Not(In(Eval('state'),
            ['converted', 'cancelled', 'lost'])),
    }, depends=['state'])
    description = fields.Char('Description', required=True,
        states=_STATES_STOP, depends=_DEPENDS_STOP)
    comment = fields.Text('Comment', states=_STATES_STOP,
        depends=_DEPENDS_STOP)
    lines = fields.One2Many('sale.opportunity.line', 'opportunity', 'Lines',
        states=_STATES_STOP, depends=_DEPENDS_STOP)
    state = fields.Selection(STATES, 'State', required=True, select=True,
            sort=False, readonly=True)
    probability = fields.Integer('Conversion Probability', required=True,
            states={
                'readonly': Not(In(Eval('state'), ['opportunity', 'lead'])),
            }, depends=['state'], help="Percentage between 0 and 100")
    history = fields.One2Many('sale.opportunity.history', 'opportunity',
            'History', readonly=True)
    lost_reason = fields.Text('Reason for loss', states={
            'invisible': Eval('state') != 'lost',
            }, depends=['state'])
    sale = fields.Many2One('sale.sale', 'Sale', readonly=True, states={
            'invisible': Eval('state') != 'converted',
            }, depends=['state'])

    @classmethod
    def __setup__(cls):
        super(SaleOpportunity, cls).__setup__()
        cls._order.insert(0, ('start_date', 'DESC'))
        cls._sql_constraints += [
            ('check_percentage',
                'CHECK(probability >= 0 AND probability <= 100)',
                'Probability must be between 0 and 100.')
            ]
        cls._error_messages.update({
                'delete_cancel': ('Sale Opportunity "%s" must be cancelled '
                    'before deletion.'),
                })
        cls._transitions |= set((
                ('lead', 'opportunity'),
                ('lead', 'lost'),
                ('lead', 'cancelled'),
                ('opportunity', 'converted'),
                ('opportunity', 'lead'),
                ('opportunity', 'lost'),
                ('opportunity', 'cancelled'),
                ('lost', 'lead'),
                ('cancelled', 'lead'),
                ))
        cls._buttons.update({
                'lead': {
                    'invisible': ~Eval('state').in_(
                        ['cancelled', 'lost', 'opportunity']),
                    'icon': If(Eval('state').in_(['cancelled', 'lost']),
                        'tryton-clear', 'tryton-go-previous'),
                    },
                'opportunity': {
                    'invisible': ~Eval('state').in_(['lead']),
                    },
                'convert': {
                    'invisible': ~Eval('state').in_(['opportunity']),
                    },
                'lost': {
                    'invisible': ~Eval('state').in_(['lead', 'opportunity']),
                    },
                'cancel': {
                    'invisible': ~Eval('state').in_(['lead', 'opportunity']),
                    },
                })

    @staticmethod
    def default_state():
        return 'lead'

    @staticmethod
    def default_start_date():
        Date = Pool().get('ir.date')
        return Date.today()

    @staticmethod
    def default_probability():
        return 50

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_employee():
        User = Pool().get('res.user')

        if Transaction().context.get('employee'):
            return Transaction().context['employee']
        else:
            user = User(Transaction().user)
            if user.employee:
                return user.employee.id

    @classmethod
    def default_payment_term(cls):
        PaymentTerm = Pool().get('account.invoice.payment_term')
        payment_terms = PaymentTerm.search(cls.payment_term.domain)
        if len(payment_terms) == 1:
            return payment_terms[0].id

    def get_currency(self, name):
        return self.company.currency.id

    def get_currency_digits(self, name):
        return self.company.currency.digits

    def on_change_company(self):
        res = {}
        if self.company:
            res['currency'] = self.company.currency.id
            res['currency.rec_name'] = self.company.currency.rec_name
            res['currency_digits'] = self.company.currency.digits
        return res

    def on_change_party(self):
        PaymentTerm = Pool().get('account.invoice.payment_term')

        res = {
            'payment_term': None,
            }
        if self.party:
            if self.party.customer_payment_term:
                res['payment_term'] = self.party.customer_payment_term.id
                res['payment_term.rec_name'] = \
                    self.party.customer_payment_term.rec_name
        if not res['payment_term']:
            res['payment_term'] = self.default_payment_term()
            res['payment_term.rec_name'] = PaymentTerm(
                res['payment_term']).rec_name
        return res

    def _get_sale_line_opportunity_line(self, sale):
        '''
        Return sale lines for each opportunity line
        '''
        res = {}
        for line in self.lines:
            if line.sale_line:
                continue
            sale_line = line.get_sale_line(sale)
            if sale_line:
                res[line.id] = sale_line
        return res

    def _get_sale_opportunity(self):
        '''
        Return sale for an opportunity
        '''
        Sale = Pool().get('sale.sale')
        with Transaction().set_user(0, set_context=True):
            return Sale(
                description=self.description,
                party=self.party,
                payment_term=self.payment_term,
                company=self.company,
                invoice_address=self.address,
                shipment_address=self.address,
                currency=self.company.currency,
                comment=self.comment,
                sale_date=None,
                )

    def create_sale(self):
        '''
        Create a sale for the opportunity and return the sale
        '''
        Line = Pool().get('sale.opportunity.line')

        if self.sale:
            return

        sale = self._get_sale_opportunity()
        sale_lines = self._get_sale_line_opportunity_line(sale)
        sale.save()

        for line_id, sale_line in sale_lines.iteritems():
            sale_line.sale = sale
            sale_line.save()
            Line.write([Line(line_id)], {
                    'sale_line': sale_line.id,
                    })

        self.write([self], {
                'sale': sale.id,
                })
        return sale

    @classmethod
    def delete(cls, opportunities):
        # Cancel before delete
        cls.cancel(opportunities)
        for opportunity in opportunities:
            if opportunity.state != 'cancel':
                cls.raise_user_error('delete_cancel', opportunity.rec_name)
        super(SaleOpportunity, cls).delete(opportunities)

    @classmethod
    @ModelView.button
    @Workflow.transition('lead')
    def lead(cls, opportunities):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('opportunity')
    def opportunity(cls, opportunities):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('converted')
    def convert(cls, opportunities):
        Date = Pool().get('ir.date')
        cls.write(opportunities, {
                'end_date': Date.today(),
                })
        for opportunity in opportunities:
            opportunity.create_sale()

    @classmethod
    @ModelView.button
    @Workflow.transition('lost')
    def lost(cls, opportunities):
        Date = Pool().get('ir.date')
        cls.write(opportunities, {
                'end_date': Date.today(),
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, opportunities):
        Date = Pool().get('ir.date')
        cls.write(opportunities, {
                'end_date': Date.today(),
                })


class SaleOpportunityLine(ModelSQL, ModelView):
    'Sale Opportunity Line'
    __name__ = "sale.opportunity.line"
    _rec_name = "product"
    _history = True
    opportunity = fields.Many2One('sale.opportunity', 'Opportunity')
    sequence = fields.Integer('Sequence',
        order_field='(%(table)s.sequence IS NULL) %(order)s, '
        '%(table)s.sequence %(order)s')
    product = fields.Many2One('product.product', 'Product', required=True,
            domain=[('salable', '=', True)], on_change=['product', 'unit'])
    quantity = fields.Float('Quantity', required=True,
            digits=(16, Eval('unit_digits', 2)), depends=['unit_digits'])
    unit = fields.Many2One('product.uom', 'Unit', required=True)
    unit_digits = fields.Function(fields.Integer('Unit Digits',
        on_change_with=['unit']), 'on_change_with_unit_digits')
    sale_line = fields.Many2One('sale.line', 'Sale Line', readonly=True,
        states={
            'invisible': (Eval('_parent_opportunity', {}).get('state')
                != 'converted'),
            })

    @classmethod
    def __setup__(cls):
        super(SaleOpportunityLine, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        super(SaleOpportunityLine, cls).__register__(module_name)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

    def on_change_with_unit_digits(self, name=None):
        if self.unit:
            return self.unit.digits
        return 2

    def on_change_product(self):
        if not self.product:
            return {}
        res = {}

        category = self.product.sale_uom.category
        if (not self.unit
                or self.unit not in category.uoms):
            res['unit'] = self.product.sale_uom.id
            res['unit.rec_name'] = self.product.sale_uom.rec_name
            res['unit_digits'] = self.product.sale_uom.digits
        return res

    def get_sale_line(self, sale):
        '''
        Return sale line for opportunity line
        '''
        SaleLine = Pool().get('sale.line')
        with Transaction().set_user(0, set_context=True):
            sale_line = SaleLine(
                type='line',
                quantity=self.quantity,
                unit=self.unit,
                product=self.product,
                sale=sale,
                description=None,
                )
        for k, v in sale_line.on_change_product().iteritems():
            setattr(sale_line, k, v)
        return sale_line


class SaleOpportunityHistory(ModelSQL, ModelView):
    'Sale Opportunity History'
    __name__ = 'sale.opportunity.history'
    date = fields.DateTime('Change Date')
    opportunity = fields.Many2One('sale.opportunity', 'Sale Opportunity')
    user = fields.Many2One('res.user', 'User')
    party = fields.Many2One('party.party', 'Party', datetime_field='date')
    address = fields.Many2One('party.address', 'Address',
            datetime_field='date')
    company = fields.Many2One('company.company', 'Company',
            datetime_field='date')
    employee = fields.Many2One('company.employee', 'Employee',
            datetime_field='date')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date', states={
        'invisible': Not(In(Eval('state'),
            ['converted', 'cancelled', 'lost'])),
    }, depends=['state'])
    description = fields.Char('Description')
    comment = fields.Text('Comment')
    lines = fields.Function(fields.One2Many('sale.opportunity.line', None,
            'Lines', datetime_field='date'), 'get_lines')
    state = fields.Selection(STATES, 'State')
    probability = fields.Integer('Conversion Probability')
    lost_reason = fields.Text('Reason for loss', states={
        'invisible': Not(Equal(Eval('state'), 'lost')),
    }, depends=['state'])

    @classmethod
    def __setup__(cls):
        super(SaleOpportunityHistory, cls).__setup__()
        cls._order.insert(0, ('date', 'DESC'))

    @classmethod
    def _table_query_fields(cls):
        Opportunity = Pool().get('sale.opportunity')
        table = '%s__history' % Opportunity._table
        return [
            'MIN("%s".__id) AS id' % table,
            '"%s".id AS opportunity' % table,
            ('MIN(COALESCE("%s".write_date, "%s".create_date)) AS date'
                % (table, table)),
            ('COALESCE("%s".write_uid, "%s".create_uid) AS user'
                % (table, table)),
            ] + ['"%s"."%s"' % (table, name)
                for name, field in cls._fields.iteritems()
                if name not in ('id', 'opportunity', 'date', 'user')
                and not hasattr(field, 'set')]

    @classmethod
    def _table_query_group(cls):
        Opportunity = Pool().get('sale.opportunity')
        table = '%s__history' % Opportunity._table
        return [
            '"%s".id' % table,
            'COALESCE("%s".write_uid, "%s".create_uid)' % (table, table),
        ] + ['"%s"."%s"' % (table, name)
            for name, field in cls._fields.iteritems()
            if (name not in ('id', 'opportunity', 'date', 'user')
                and not hasattr(field, 'set'))]

    @classmethod
    def table_query(cls):
        Opportunity = Pool().get('sale.opportunity')
        return (('SELECT ' + (', '.join(cls._table_query_fields()))
                + ' FROM "%s__history" GROUP BY '
                + (', '.join(cls._table_query_group())))
            % Opportunity._table, [])

    def get_lines(self, name):
        Line = Pool().get('sale.opportunity.line')
        # We will always have only one id per call due to datetime_field
        lines = Line.search([
                ('opportunity', '=', self.opportunity.id),
                ])
        return [l.id for l in lines]

    @classmethod
    def read(cls, ids, fields_names=None):
        res = super(SaleOpportunityHistory, cls).read(ids,
            fields_names=fields_names)

        # Remove microsecond from timestamp
        for values in res:
            if 'date' in values:
                if isinstance(values['date'], basestring):
                    values['date'] = datetime.datetime(
                        *time.strptime(values['date'],
                            '%Y-%m-%d %H:%M:%S.%f')[:6])
                values['date'] = values['date'].replace(microsecond=0)
        return res


class SaleOpportunityEmployee(ModelSQL, ModelView):
    'Sale Opportunity per Employee'
    __name__ = 'sale.opportunity_employee'
    employee = fields.Many2One('company.employee', 'Employee')
    number = fields.Integer('Number')
    converted = fields.Integer('Converted')
    conversion_rate = fields.Function(fields.Float('Conversion Rate',
        help='In %'), 'get_conversion_rate')
    lost = fields.Integer('Lost')
    company = fields.Many2One('company.company', 'Company')
    currency = fields.Function(fields.Many2One('currency.currency',
        'Currency'), 'get_currency')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
            'get_currency_digits')
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits'])
    converted_amount = fields.Numeric('Converted Amount',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits'])
    conversion_amount_rate = fields.Function(fields.Float(
        'Conversion Amount Rate', help='In %'), 'get_conversion_amount_rate')

    @staticmethod
    def _converted_state():
        return ['converted']

    @staticmethod
    def _lost_state():
        return ['lost']

    @classmethod
    def table_query(cls):
        Opportunity = Pool().get('sale.opportunity')
        clause = ' '
        args = [True]
        if Transaction().context.get('start_date'):
            clause += 'AND start_date >= %s '
            args.append(Transaction().context['start_date'])
        if Transaction().context.get('end_date'):
            clause += 'AND start_date <= %s '
            args.append(Transaction().context['end_date'])
        return ('SELECT DISTINCT(employee) AS id, '
                'MAX(create_uid) AS create_uid, '
                'MAX(create_date) AS create_date, '
                'MAX(write_uid) AS write_uid, '
                'MAX(write_date) AS write_date, '
                'employee, '
                'company, '
                'COUNT(1) AS number, '
                'SUM(CASE WHEN state IN (' + ','.join("'%s'" % x
                    for x in cls._converted_state()) + ') '
                    'THEN 1 ELSE 0 END) AS converted, '
                'SUM(CASE WHEN state IN (' + ','.join("'%s'" % x
                    for x in cls._lost_state()) + ') '
                    'THEN 1 ELSE 0 END) AS lost, '
                'SUM(amount) AS amount, '
                'SUM(CASE WHEN state IN (' + ','.join("'%s'" % x
                    for x in cls._converted_state()) + ') '
                    'THEN amount ELSE 0 END) AS converted_amount '
            'FROM "' + Opportunity._table + '" '
            'WHERE %s ' + clause +
            'GROUP BY employee, company', args)

    def get_conversion_rate(self, name):
        if self.number:
            return float(self.converted) / self.number * 100.0
        else:
            return 0.0

    def get_currency(self, name):
        return self.company.currency.id

    def get_currency_digits(self, name):
        return self.company.currency.digits

    def get_conversion_amount_rate(self, name):
        if self.amount:
            return float(self.converted_amount) / float(self.amount) * 100.0
        else:
            return 0.0


class OpenSaleOpportunityEmployeeStart(ModelView):
    'Open Sale Opportunity per Employee'
    __name__ = 'sale.opportunity_employee.open.start'
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')


class OpenSaleOpportunityEmployee(Wizard):
    'Open Sale Opportunity per Employee'
    __name__ = 'sale.opportunity_employee.open'
    start = StateView('sale.opportunity_employee.open.start',
        'sale_opportunity.opportunity_employee_open_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open_', 'tryton-ok', default=True),
            ])
    open_ = StateAction('sale_opportunity.act_opportunity_employee_form')

    def do_open_(self, action):
        action['pyson_context'] = PYSONEncoder().encode({
                'start_date': self.start.start_date,
                'end_date': self.start.end_date,
                })
        return action, {}


class SaleOpportunityMonthly(ModelSQL, ModelView):
    'Sale Opportunity per Month'
    __name__ = 'sale.opportunity_monthly'
    year = fields.Char('Year')
    month = fields.Integer('Month')
    year_month = fields.Function(fields.Char('Year-Month'),
            'get_year_month')
    number = fields.Integer('Number')
    converted = fields.Integer('Converted')
    conversion_rate = fields.Function(fields.Float('Conversion Rate',
        help='In %'), 'get_conversion_rate')
    lost = fields.Integer('Lost')
    company = fields.Many2One('company.company', 'Company')
    currency = fields.Function(fields.Many2One('currency.currency',
        'Currency'), 'get_currency')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
            'get_currency_digits')
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits'])
    converted_amount = fields.Numeric('Converted Amount',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits'])
    conversion_amount_rate = fields.Function(fields.Float(
        'Conversion Amount Rate', help='In %'), 'get_conversion_amount_rate')

    @classmethod
    def __setup__(cls):
        super(SaleOpportunityMonthly, cls).__setup__()
        cls._order.insert(0, ('year', 'DESC'))
        cls._order.insert(1, ('month', 'DESC'))

    @staticmethod
    def _converted_state():
        return ['converted']

    @staticmethod
    def _lost_state():
        return ['lost']

    @classmethod
    def table_query(cls):
        Opportunity = Pool().get('sale.opportunity')
        type_id = FIELDS[cls.id._type].sql_type(cls.id)[0]
        type_year = FIELDS[cls.year._type].sql_type(cls.year)[0]
        return ('SELECT CAST(id AS ' + type_id + ') AS id, create_uid, '
                'create_date, write_uid, write_date, '
                'CAST(year AS ' + type_year + ') AS year, month, company, '
                'number, converted, lost, amount, converted_amount '
            'FROM ('
                'SELECT EXTRACT(MONTH FROM start_date) + '
                        'EXTRACT(YEAR FROM start_date) * 100 AS id, '
                    'MAX(create_uid) AS create_uid, '
                    'MAX(create_date) AS create_date, '
                    'MAX(write_uid) AS write_uid, '
                    'MAX(write_date) AS write_date, '
                    'EXTRACT(YEAR FROM start_date) AS year, '
                    'EXTRACT(MONTH FROM start_date) AS month, '
                    'company, '
                    'COUNT(1) AS number, '
                    'SUM(CASE WHEN state IN (' + ','.join("'%s'" % x
                    for x in cls._converted_state()) + ') '
                    'THEN 1 ELSE 0 END) AS converted, '
                    'SUM(CASE WHEN state IN (' + ','.join("'%s'" % x
                    for x in cls._lost_state()) + ') '
                    'THEN 1 ELSE 0 END) AS lost, '
                    'SUM(amount) AS amount, '
                    'SUM(CASE WHEN state IN (' + ','.join("'%s'" % x
                    for x in cls._converted_state()) + ') '
                    'THEN amount ELSE 0 END) AS converted_amount '
                'FROM "' + Opportunity._table + '" '
                'GROUP BY year, month, company) AS "' + cls._table + '"',
            [])

    def get_conversion_rate(self, name):
        if self.number:
            return float(self.converted) / self.number * 100.0
        else:
            return 0.0

    def get_year_month(self, name):
        return '%s-%s' % (self.year, int(self.month))

    def get_currency(self, name):
        return self.company.currency.id

    def get_currency_digits(self, name):
        return self.company.currency.digits

    def get_conversion_amount_rate(self, name):
        if self.amount:
            return float(self.converted_amount) / float(self.amount) * 100.0
        else:
            return 0.0


class SaleOpportunityEmployeeMonthly(ModelSQL, ModelView):
    'Sale Opportunity per Employee per Month'
    __name__ = 'sale.opportunity_employee_monthly'
    year = fields.Char('Year')
    month = fields.Integer('Month')
    employee = fields.Many2One('company.employee', 'Employee')
    number = fields.Integer('Number')
    converted = fields.Integer('Converted')
    conversion_rate = fields.Function(fields.Float('Conversion Rate',
        help='In %'), 'get_conversion_rate')
    lost = fields.Integer('Lost')
    company = fields.Many2One('company.company', 'Company')
    currency = fields.Function(fields.Many2One('currency.currency',
        'Currency'), 'get_currency')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
            'get_currency_digits')
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits'])
    converted_amount = fields.Numeric('Converted Amount',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits'])
    conversion_amount_rate = fields.Function(fields.Float(
        'Conversion Amount Rate', help='In %'), 'get_conversion_amount_rate')

    @classmethod
    def __setup__(cls):
        super(SaleOpportunityEmployeeMonthly, cls).__setup__()
        cls._order.insert(0, ('year', 'DESC'))
        cls._order.insert(1, ('month', 'DESC'))
        cls._order.insert(2, ('employee', 'ASC'))

    @staticmethod
    def _converted_state():
        return ['converted']

    @staticmethod
    def _lost_state():
        return ['lost']

    @classmethod
    def table_query(cls):
        Opportunity = Pool().get('sale.opportunity')
        type_id = FIELDS[cls.id._type].sql_type(cls.id)[0]
        type_year = FIELDS[cls.year._type].sql_type(cls.year)[0]
        return ('SELECT CAST(id AS ' + type_id + ') AS id, create_uid, '
                'create_date, write_uid, write_date, '
                'CAST(year AS ' + type_year + ') AS year, month, '
                'employee, company, number, converted, lost, amount, '
                'converted_amount '
            'FROM ('
                'SELECT EXTRACT(MONTH FROM start_date) + '
                        'EXTRACT(YEAR FROM start_date) * 100 + '
                        'employee * 1000000 AS id, '
                    'MAX(create_uid) AS create_uid, '
                    'MAX(create_date) AS create_date, '
                    'MAX(write_uid) AS write_uid, '
                    'MAX(write_date) AS write_date, '
                    'EXTRACT(YEAR FROM start_date) AS year, '
                    'EXTRACT(MONTH FROM start_date) AS month, '
                    'employee, '
                    'company, '
                    'COUNT(1) AS number, '
                    'SUM(CASE WHEN state IN (' + ','.join("'%s'" % x
                    for x in cls._converted_state()) + ') '
                    'THEN 1 ELSE 0 END) AS converted, '
                    'SUM(CASE WHEN state IN (' + ','.join("'%s'" % x
                    for x in cls._lost_state()) + ') '
                    'THEN 1 ELSE 0 END) AS lost, '
                    'SUM(amount) AS amount, '
                    'SUM(CASE WHEN state IN (' + ','.join("'%s'" % x
                    for x in cls._converted_state()) + ') '
                    'THEN amount ELSE 0 END) AS converted_amount '
                'FROM "' + Opportunity._table + '" '
                'GROUP BY year, month, employee, company) '
            'AS "' + cls._table + '"', [])

    def get_conversion_rate(self, name):
        if self.number:
            return float(self.converted) / self.number * 100.0
        else:
            return 0.0

    def get_currency(self, name):
        return self.company.currency.id

    def get_currency_digits(self, name):
        return self.company.currency.digits

    def get_conversion_amount_rate(self, name):
        if self.amount:
            return float(self.converted_amount) / float(self.amount) * 100.0
        else:
            return 0.0
