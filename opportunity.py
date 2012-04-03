#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Sales extension for managing leads and opportunities"
import datetime
import time
from trytond.model import ModelView, ModelSQL, Workflow, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.backend import FIELDS
from trytond.pyson import Equal, Eval, Not, In, If, Get, PYSONEncoder
from trytond.transaction import Transaction
from trytond.pool import Pool

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
    _name = "sale.opportunity"
    _description = __doc__
    _history = True
    _rec_name = 'description'

    party = fields.Many2One('party.party', 'Party', required=True, select=True,
            states=_STATES_STOP, depends=_DEPENDS_STOP)
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

    def __init__(self):
        super(SaleOpportunity, self).__init__()
        self._order.insert(0, ('start_date', 'DESC'))
        self._sql_constraints += [
            ('check_percentage',
                'CHECK(probability >= 0 AND probability <= 100)',
                'Probability must be between 0 and 100!')
        ]
        self._error_messages.update({
                'delete_cancel': 'Sale Opportunity "%s" must be cancelled '\
                    'before deletion!',
                })
        self._transitions |= set((
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
        self._buttons.update({
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

    def default_state(self):
        return 'lead'

    def default_start_date(self):
        date_obj = Pool().get('ir.date')
        return date_obj.today()

    def default_probability(self):
        return 50

    def default_company(self):
        return Transaction().context.get('company')

    def default_employee(self):
        user_obj = Pool().get('res.user')

        if Transaction().context.get('employee'):
            return Transaction().context['employee']
        else:
            user = user_obj.browse(Transaction().user)
            if user.employee:
                return user.employee.id

    def default_payment_term(self):
        payment_term_obj = Pool().get('account.invoice.payment_term')
        payment_term_ids = payment_term_obj.search(self.payment_term.domain)
        if len(payment_term_ids) == 1:
            return payment_term_ids[0]

    def get_currency(self, ids, name):
        res = {}
        for opportunity in self.browse(ids):
            res[opportunity.id] = opportunity.company.currency.id
        return res

    def get_currency_digits(self, ids, name):
        res = {}
        for opportunity in self.browse(ids):
            res[opportunity.id] = opportunity.company.currency.digits
        return res

    def on_change_company(self, values):
        company_obj = Pool().get('company.company')

        res = {}
        if values.get('company'):
            company = company_obj.browse(values['company'])
            res['currency'] = company.currency.id
            res['currency.rec_name'] = company.currency.rec_name
            res['currency_digits'] = company.currency.digits
        return res

    def on_change_party(self, values):
        party_obj = Pool().get('party.party')
        payment_term_obj = Pool().get('account.invoice.payment_term')

        res = {
            'payment_term': None,
        }
        if values.get('party'):
            party = party_obj.browse(values['party'])
            if party.customer_payment_term:
                res['payment_term'] = party.customer_payment_term.id
        if not res['payment_term']:
            res['payment_term'] = self.default_payment_term()
        if res['payment_term']:
            res['payment_term.rec_name'] = payment_term_obj.browse(
                    res['payment_term']).rec_name
        return res

    def _get_sale_line_opportunity_line(self, opportunity):
        '''
        Return sale line values for each opportunity line

        :param opportunity: the BrowseRecord of opportunity

        :return: a dictionary with opportunity line id as key
            and a dictionary of sale line values as value
        '''
        line_obj = Pool().get('sale.opportunity.line')
        res = {}
        for line in opportunity.lines:
            if line.sale_line:
                continue
            val = line_obj.get_sale_line(line)
            if val:
                res[line.id] = val
        return res

    def _get_sale_opportunity(self, opportunity):
        '''
        Return sale values for an opportunity

        :param opportunity: the BrowseRecord of the opportunity

        :return: a dictionary with sale fields as key and sale values as value
        '''
        res = {
            'description': opportunity.description,
            'party': opportunity.party.id,
            'payment_term': opportunity.payment_term.id,
            'company': opportunity.company.id,
            'invoice_address': opportunity.address and opportunity.address.id,
            'shipment_address': opportunity.address and opportunity.address.id,
            'currency': opportunity.company.currency.id,
            'comment': opportunity.comment,
        }
        return res

    def create_sale(self, opportunity):
        '''
        Create a sale for the opportunity and return the sale id
        '''
        pool = Pool()
        sale_obj = pool.get('sale.sale')
        sale_line_obj = pool.get('sale.line')
        line_obj = pool.get('sale.opportunity.line')

        if opportunity.sale:
            return

        values = self._get_sale_opportunity(opportunity)
        sale_line_values = self._get_sale_line_opportunity_line(opportunity)

        with Transaction().set_user(0, set_context=True):
            sale_id = sale_obj.create(values)

        for line_id, values in sale_line_values.iteritems():
            values['sale'] = sale_id
            with Transaction().set_user(0, set_context=True):
                sale_line_id = sale_line_obj.create(values)
            line_obj.write(line_id, {
                'sale_line': sale_line_id,
                })

        self.write(opportunity.id, {
            'sale': sale_id,
            })
        return sale_id

    def delete(self, ids):
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Cancel before delete
        self.cancel(ids)
        for opportunity in self.browse(ids):
            if opportunity.state != 'cancel':
                self.raise_user_error('delete_cancel', opportunity.rec_name)
        return super(SaleOpportunity, self).delete(ids)

    @ModelView.button
    @Workflow.transition('lead')
    def lead(self, ids):
        pass

    @ModelView.button
    @Workflow.transition('opportunity')
    def opportunity(self, ids):
        pass

    @ModelView.button
    @Workflow.transition('converted')
    def convert(self, ids):
        date_obj = Pool().get('ir.date')
        self.write(ids, {
                'end_date': date_obj.today(),
                })
        for opportunity in self.browse(ids):
            self.create_sale(opportunity)

    @ModelView.button
    @Workflow.transition('lost')
    def lost(self, ids):
        date_obj = Pool().get('ir.date')
        self.write(ids, {
                'end_date': date_obj.today(),
                })

    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(self, ids):
        date_obj = Pool().get('ir.date')
        self.write(ids, {
                'end_date': date_obj.today(),
                })

SaleOpportunity()


class SaleOpportunityLine(ModelSQL, ModelView):
    'Sale Opportunity Line'
    _name = "sale.opportunity.line"
    _description = __doc__
    _rec_name = "product"
    _history = True

    opportunity = fields.Many2One('sale.opportunity', 'Opportunity')
    sequence = fields.Integer('Sequence', required=True)
    product = fields.Many2One('product.product', 'Product', required=True,
            domain=[('salable', '=', True)], on_change=['product', 'unit'])
    quantity = fields.Float('Quantity', required=True,
            digits=(16, Eval('unit_digits', 2)), depends=['unit_digits'])
    unit = fields.Many2One('product.uom', 'Unit', required=True)
    unit_digits = fields.Function(fields.Integer('Unit Digits',
        on_change_with=['unit']), 'get_unit_digits')
    sale_line = fields.Many2One('sale.line', 'Sale Line', readonly=True,
        states={
            'invisible': (Eval('_parent_opportunity', {}).get('state')
                != 'converted'),
            })

    def __init__(self):
        super(SaleOpportunityLine, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

    def on_change_with_unit_digits(self, vals):
        uom_obj = Pool().get('product.uom')
        if vals.get('unit'):
            uom = uom_obj.browse(vals['unit'])
            return uom.digits
        return 2

    def get_unit_digits(self, ids, name):
        res = {}
        for line in self.browse(ids):
            if line.unit:
                res[line.id] = line.unit.digits
            else:
                res[line.id] = 2
        return res

    def on_change_product(self, vals):
        product_obj = Pool().get('product.product')

        if not vals.get('product'):
            return {}
        res = {}

        product = product_obj.browse(vals['product'])
        category = product.sale_uom.category
        if not vals.get('unit') \
                or vals.get('unit') not in [x.id for x in category.uoms]:
            res['unit'] = product.sale_uom.id
            res['unit.rec_name'] = product.sale_uom.rec_name
            res['unit_digits'] = product.sale_uom.digits
        return res

    def get_sale_line(self, line):
        '''
        Return sale line values for opportunity line

        :param line: the BrowseRecord of the line

        :return: a dictionary with sale line fields as key
            and sale line values as value
        '''
        sale_line_obj = Pool().get('sale.line')
        res = {
            'type': 'line',
            'quantity': line.quantity,
            'unit': line.unit.id,
            'product': line.product.id,
        }
        res.update(sale_line_obj.on_change_product({
            'product': line.product.id,
            'unit': line.unit.id,
            'quantity': line.quantity,
            '_parent_sale.party': line.opportunity.party.id,
            '_parent_sale.currency': line.opportunity.company.currency.id,
            }))
        for field_name, field in sale_line_obj._columns.iteritems():
            if field._type not in ('one2many', 'many2many'):
                continue
            if field_name not in res:
                continue
            res[field_name] = [('add', res[field_name])]
        return res

SaleOpportunityLine()


class SaleOpportunityHistory(ModelSQL, ModelView):
    'Sale Opportunity History'
    _name = 'sale.opportunity.history'
    _description = __doc__

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

    def __init__(self):
        super(SaleOpportunityHistory, self).__init__()
        self._order.insert(0, ('date', 'DESC'))

    def _table_query_fields(self):
        opportunity_obj = Pool().get('sale.opportunity')
        table = '%s__history' % opportunity_obj._table
        return [
            'MIN("%s".__id) AS id' % table,
            '"%s".id AS opportunity' % table,
            ('MIN(COALESCE("%s".write_date, "%s".create_date)) AS date'
                % (table, table)),
            ('COALESCE("%s".write_uid, "%s".create_uid) AS user'
                % (table, table)),
            ] + ['"%s"."%s"' % (table, name)
                for name, field in self._columns.iteritems()
                if name not in ('id', 'opportunity', 'date', 'user')
                and not hasattr(field, 'set')]

    def _table_query_group(self):
        opportunity_obj = Pool().get('sale.opportunity')
        table = '%s__history' % opportunity_obj._table
        return [
            '"%s".id' % table,
            'COALESCE("%s".write_uid, "%s".create_uid)' % (table, table),
        ] + ['"%s"."%s"' % (table, name)
                for name, field in self._columns.iteritems()
                if name not in ('id', 'opportunity', 'date', 'user')
                and not hasattr(field, 'set')]

    def table_query(self):
        opportunity_obj = Pool().get('sale.opportunity')
        return (('SELECT ' + \
                (', '.join(self._table_query_fields())) + \
                ' FROM "%s__history" '
                'GROUP BY ' + \
                (', '.join(self._table_query_group()))) % \
                opportunity_obj._table, [])

    def get_lines(self, ids, name):
        line_obj = Pool().get('sale.opportunity.line')
        histories = self.browse(ids)
        result = {}
        # We will always have only one id per call due to datetime_field
        for history in histories:
            result[history.id] = line_obj.search([
                ('opportunity', '=', history.opportunity.id),
            ])
        return result

    def read(self, ids, fields_names=None):
        res = super(SaleOpportunityHistory, self).read(ids,
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

SaleOpportunityHistory()


class SaleOpportunityEmployee(ModelSQL, ModelView):
    'Sale Opportunity per Employee'
    _name = 'sale.opportunity_employee'
    _description = __doc__

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

    def _converted_state(self):
        return ['converted']

    def _lost_state(self):
        return ['lost']

    def table_query(self):
        opportunity_obj = Pool().get('sale.opportunity')
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
                        for x in self._converted_state()) + ') '
                        'THEN 1 ELSE 0 END) AS converted, '
                    'SUM(CASE WHEN state IN (' + ','.join("'%s'" % x
                        for x in self._lost_state()) + ') '
                        'THEN 1 ELSE 0 END) AS lost, '
                    'SUM(amount) AS amount, '
                    'SUM(CASE WHEN state IN (' + ','.join("'%s'" % x
                        for x in self._converted_state()) + ') '
                        'THEN amount ELSE 0 END) AS converted_amount '
                'FROM "' + opportunity_obj._table + '" '
                'WHERE %s ' \
                + clause + \
                'GROUP BY employee, company', args)

    def get_conversion_rate(self, ids, name):
        res = {}
        for record in self.browse(ids):
            if record.number:
                res[record.id] = (float(record.converted)
                    / record.number * 100.0)
            else:
                res[record.id] = 0.0
        return res

    def get_currency(self, ids, name):
        res = {}
        for record in self.browse(ids):
            res[record.id] = record.company.currency.id
        return res

    def get_currency_digits(self, ids, name):
        res = {}
        for record in self.browse(ids):
            res[record.id] = record.company.currency.digits
        return res

    def get_conversion_amount_rate(self, ids, name):
        res = {}
        for record in self.browse(ids):
            if record.amount:
                res[record.id] = (float(record.converted_amount) /
                        float(record.amount) * 100.0)
            else:
                res[record.id] = 0.0
        return res

SaleOpportunityEmployee()


class OpenSaleOpportunityEmployeeStart(ModelView):
    'Open Sale Opportunity per Employee'
    _name = 'sale.opportunity_employee.open.start'
    _description = __doc__
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')

OpenSaleOpportunityEmployeeStart()


class OpenSaleOpportunityEmployee(Wizard):
    'Open Sale Opportunity per Employee'
    _name = 'sale.opportunity_employee.open'

    start = StateView('sale.opportunity_employee.open.start',
        'sale_opportunity.opportunity_employee_open_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open_', 'tryton-ok', default=True),
            ])
    open_ = StateAction('sale_opportunity.act_opportunity_employee_form')

    def do_open_(self, session, action):
        action['pyson_context'] = PYSONEncoder().encode({
                'start_date': session.start.start_date,
                'end_date': session.start.end_date,
                })
        return action, {}

OpenSaleOpportunityEmployee()


class SaleOpportunityMonthly(ModelSQL, ModelView):
    'Sale Opportunity per Month'
    _name = 'sale.opportunity_monthly'
    _description = __doc__

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

    def __init__(self):
        super(SaleOpportunityMonthly, self).__init__()
        self._order.insert(0, ('year', 'DESC'))
        self._order.insert(1, ('month', 'DESC'))

    def _converted_state(self):
        return ['converted']

    def _lost_state(self):
        return ['lost']

    def table_query(self):
        opportunity_obj = Pool().get('sale.opportunity')
        type_id = FIELDS[self.id._type].sql_type(self.id)[0]
        type_year = FIELDS[self.year._type].sql_type(self.year)[0]
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
                        for x in self._converted_state()) + ') '
                        'THEN 1 ELSE 0 END) AS converted, '
                        'SUM(CASE WHEN state IN (' + ','.join("'%s'" % x
                        for x in self._lost_state()) + ') '
                        'THEN 1 ELSE 0 END) AS lost, '
                        'SUM(amount) AS amount, '
                        'SUM(CASE WHEN state IN (' + ','.join("'%s'" % x
                        for x in self._converted_state()) + ') '
                        'THEN amount ELSE 0 END) AS converted_amount '
                    'FROM "' + opportunity_obj._table + '" '
                    'GROUP BY year, month, company) AS "' + self._table + '"',
                [])

    def get_conversion_rate(self, ids, name):
        res = {}
        for record in self.browse(ids):
            if record.number:
                res[record.id] = (float(record.converted)
                    / record.number * 100.0)
            else:
                res[record.id] = 0.0
        return res

    def get_year_month(self, ids, name):
        res = {}
        for record in self.browse(ids):
            res[record.id] = '%s-%s' % (record.year, int(record.month))
        return res

    def get_currency(self, ids, name):
        res = {}
        for record in self.browse(ids):
            res[record.id] = record.company.currency.id
        return res

    def get_currency_digits(self, ids, name):
        res = {}
        for record in self.browse(ids):
            res[record.id] = record.company.currency.digits
        return res

    def get_conversion_amount_rate(self, ids, name):
        res = {}
        for record in self.browse(ids):
            if record.amount:
                res[record.id] = (float(record.converted_amount) /
                        float(record.amount) * 100.0)
            else:
                res[record.id] = 0.0
        return res

SaleOpportunityMonthly()


class SaleOpportunityEmployeeMonthly(ModelSQL, ModelView):
    'Sale Opportunity per Employee per Month'
    _name = 'sale.opportunity_employee_monthly'
    _description = __doc__

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

    def __init__(self):
        super(SaleOpportunityEmployeeMonthly, self).__init__()
        self._order.insert(0, ('year', 'DESC'))
        self._order.insert(1, ('month', 'DESC'))
        self._order.insert(2, ('employee', 'ASC'))

    def _converted_state(self):
        return ['converted']

    def _lost_state(self):
        return ['lost']

    def table_query(self):
        opportunity_obj = Pool().get('sale.opportunity')
        type_id = FIELDS[self.id._type].sql_type(self.id)[0]
        type_year = FIELDS[self.year._type].sql_type(self.year)[0]
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
                        for x in self._converted_state()) + ') '
                        'THEN 1 ELSE 0 END) AS converted, '
                        'SUM(CASE WHEN state IN (' + ','.join("'%s'" % x
                        for x in self._lost_state()) + ') '
                        'THEN 1 ELSE 0 END) AS lost, '
                        'SUM(amount) AS amount, '
                        'SUM(CASE WHEN state IN (' + ','.join("'%s'" % x
                        for x in self._converted_state()) + ') '
                        'THEN amount ELSE 0 END) AS converted_amount '
                    'FROM "' + opportunity_obj._table + '" '
                    'GROUP BY year, month, employee, company) '
                'AS "' + self._table + '"', [])

    def get_conversion_rate(self, ids, name):
        res = {}
        for record in self.browse(ids):
            if record.number:
                res[record.id] = (float(record.converted)
                    / record.number * 100.0)
            else:
                res[record.id] = 0.0
        return res

    def get_currency(self, ids, name):
        res = {}
        for record in self.browse(ids):
            res[record.id] = record.company.currency.id
        return res

    def get_currency_digits(self, ids, name):
        res = {}
        for record in self.browse(ids):
            res[record.id] = record.company.currency.digits
        return res

    def get_conversion_amount_rate(self, ids, name):
        res = {}
        for record in self.browse(ids):
            if record.amount:
                res[record.id] = (float(record.converted_amount) /
                        float(record.amount) * 100.0)
            else:
                res[record.id] = 0.0
        return res

SaleOpportunityEmployeeMonthly()
