# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"Sales extension for managing leads and opportunities"
import datetime
from itertools import groupby

from sql import Literal, Null
from sql.aggregate import Count, Max, Sum
from sql.conditionals import Case, Coalesce
from sql.functions import DateTrunc, Extract

from trytond.i18n import gettext
from trytond.ir.attachment import AttachmentCopyMixin
from trytond.ir.note import NoteCopyMixin
from trytond.model import (
    ModelSQL, ModelView, Workflow, fields, sequence_ordered)
from trytond.model.exceptions import AccessError
from trytond.modules.company.model import employee_field, set_employee
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, Get, If, In
from trytond.transaction import Transaction


class SaleOpportunity(
        Workflow, ModelSQL, ModelView,
        AttachmentCopyMixin, NoteCopyMixin):
    'Sale Opportunity'
    __name__ = "sale.opportunity"
    _history = True
    _rec_name = 'number'

    _states_start = {
        'readonly': Eval('state') != 'lead',
        }
    _states_stop = {
        'readonly': Eval('state').in_(
            ['converted', 'won', 'lost', 'cancelled']),
    }

    number = fields.Char('Number', readonly=True, required=True, select=True)
    reference = fields.Char('Reference', select=True)
    party = fields.Many2One(
        'party.party', "Party", select=True,
        states={
            'readonly': Eval('state').in_(['converted', 'lost', 'cancelled']),
            'required': ~Eval('state').in_(['lead', 'lost', 'cancelled']),
            },
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    contact = fields.Many2One(
        'party.contact_mechanism', "Contact",
        context={
            'company': Eval('company', -1),
            },
        search_context={
            'related_party': Eval('party'),
            },
        depends=['party', 'company'])
    address = fields.Many2One('party.address', 'Address',
        domain=[('party', '=', Eval('party'))],
        select=True,
        states=_states_stop)
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True,
        states={
            'readonly': _states_stop['readonly'] | Eval('party', True),
            },
        domain=[
            ('id', If(In('company', Eval('context', {})), '=', '!='),
                Get(Eval('context', {}), 'company', 0)),
            ])
    currency = fields.Function(fields.Many2One(
            'currency.currency', "Currency"),
        'on_change_with_currency')
    amount = Monetary(
        "Amount", currency='currency', digits='currency',
        states=_states_stop,
        help='Estimated revenue amount.')
    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term', states={
            'readonly': In(Eval('state'),
                ['converted', 'lost', 'cancelled']),
            })
    employee = fields.Many2One('company.employee', 'Employee',
        states={
            'readonly': _states_stop['readonly'],
            'required': ~Eval('state').in_(['lead', 'lost', 'cancelled']),
        },
        domain=[('company', '=', Eval('company'))])
    start_date = fields.Date('Start Date', required=True, select=True,
        states=_states_start)
    end_date = fields.Date('End Date', select=True, states=_states_stop)
    description = fields.Char('Description', states=_states_stop)
    comment = fields.Text('Comment', states=_states_stop)
    lines = fields.One2Many('sale.opportunity.line', 'opportunity', 'Lines',
        states=_states_stop)
    conversion_probability = fields.Float('Conversion Probability',
        digits=(1, 4), required=True,
        domain=[
            ('conversion_probability', '>=', 0),
            ('conversion_probability', '<=', 1),
            ],
        states={
            'readonly': ~Eval('state').in_(
                ['opportunity', 'lead', 'converted']),
            },
        help="Percentage between 0 and 100.")
    lost_reason = fields.Text('Reason for loss', states={
            'invisible': Eval('state') != 'lost',
            })
    sales = fields.One2Many('sale.sale', 'origin', 'Sales')

    converted_by = employee_field(
        "Converted By", states=['converted', 'won', 'lost', 'cancelled'])
    state = fields.Selection([
            ('lead', "Lead"),
            ('opportunity', "Opportunity"),
            ('converted', "Converted"),
            ('won', "Won"),
            ('lost', "Lost"),
            ('cancelled', "Cancelled"),
            ], "State", required=True, select=True, sort=False, readonly=True)

    del _states_start
    del _states_stop

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Sale = pool.get('sale.sale')
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        update = transaction.connection.cursor()
        sql_table = cls.__table__()
        sale = Sale.__table__()

        table = cls.__table_handler__(module_name)
        number_exists = table.column_exist('number')

        # Migration from 3.8: rename reference into number
        if table.column_exist('reference') and not number_exists:
            table.column_rename('reference', 'number')
            number_exists = True

        super(SaleOpportunity, cls).__register__(module_name)
        table = cls.__table_handler__(module_name)

        # Migration from 3.4: replace sale by origin
        if table.column_exist('sale'):
            cursor.execute(*sql_table.select(
                    sql_table.id, sql_table.sale,
                    where=sql_table.sale != Null))
            for id_, sale_id in cursor:
                update.execute(*sale.update(
                        columns=[sale.origin],
                        values=['%s,%s' % (cls.__name__, id_)],
                        where=sale.id == sale_id))
            table.drop_column('sale')

        # Migration from 4.0: change probability into conversion probability
        if table.column_exist('probability'):
            cursor.execute(*sql_table.update(
                    [sql_table.conversion_probability],
                    [sql_table.probability / 100.0]))
            table.drop_constraint('check_percentage')
            table.drop_column('probability')

        # Migration from 4.2: make employee not required
        table.not_null_action('employee', action='remove')

        # Migration from 5.0: drop required on description
        table.not_null_action('description', action='remove')

    @classmethod
    def __setup__(cls):
        super(SaleOpportunity, cls).__setup__()
        cls._order.insert(0, ('start_date', 'DESC'))
        cls._transitions |= set((
                ('lead', 'opportunity'),
                ('lead', 'lost'),
                ('lead', 'cancelled'),
                ('lead', 'converted'),
                ('opportunity', 'converted'),
                ('opportunity', 'lead'),
                ('opportunity', 'lost'),
                ('opportunity', 'cancelled'),
                ('converted', 'won'),
                ('converted', 'lost'),
                ('won', 'converted'),
                ('lost', 'converted'),
                ('lost', 'lead'),
                ('cancelled', 'lead'),
                ))
        cls._buttons.update({
                'lead': {
                    'invisible': ~Eval('state').in_(
                        ['cancelled', 'lost', 'opportunity']),
                    'icon': If(Eval('state').in_(['cancelled', 'lost']),
                        'tryton-undo', 'tryton-back'),
                    'depends': ['state'],
                    },
                'opportunity': {
                    'pre_validate': [
                        If(~Eval('party'),
                            ('party', '!=', None),
                            ()),
                        If(~Eval('employee'),
                            ('employee', '!=', None),
                            ()),
                        ],
                    'invisible': ~Eval('state').in_(['lead']),
                    'depends': ['state'],
                    },
                'convert': {
                    'invisible': ~Eval('state').in_(['opportunity']),
                    'depends': ['state'],
                    },
                'lost': {
                    'invisible': ~Eval('state').in_(['lead', 'opportunity']),
                    'depends': ['state'],
                    },
                'cancel': {
                    'invisible': ~Eval('state').in_(['lead', 'opportunity']),
                    'depends': ['state'],
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
    def default_conversion_probability():
        return 0.5

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_employee():
        return Transaction().context.get('employee')

    @classmethod
    def default_payment_term(cls):
        PaymentTerm = Pool().get('account.invoice.payment_term')
        payment_terms = PaymentTerm.search(cls.payment_term.domain)
        if len(payment_terms) == 1:
            return payment_terms[0].id

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/tree', 'visual', If(Eval('state') == 'cancelled', 'muted', '')),
            ]

    @classmethod
    def get_resources_to_copy(cls, name):
        return {
            'sale.sale',
            }

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Config = pool.get('sale.configuration')

        config = Config(1)
        vlist = [x.copy() for x in vlist]
        default_company = cls.default_company()
        for vals in vlist:
            if vals.get('number') is None:
                vals['number'] = config.get_multivalue(
                    'sale_opportunity_sequence',
                    company=vals.get('company', default_company)).get()
        return super(SaleOpportunity, cls).create(vlist)

    @classmethod
    def copy(cls, opportunities, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('number', None)
        default.setdefault('sales', None)
        default.setdefault('converted_by')
        return super(SaleOpportunity, cls).copy(opportunities, default=default)

    @fields.depends('company')
    def on_change_with_currency(self, name=None):
        if self.company:
            return self.company.currency.id

    @fields.depends('party')
    def on_change_party(self):
        if self.party and self.party.customer_payment_term:
            self.payment_term = self.party.customer_payment_term
        else:
            self.payment_term = self.default_payment_term()

    def _get_sale_opportunity(self):
        '''
        Return sale for an opportunity
        '''
        Sale = Pool().get('sale.sale')
        return Sale(
            description=self.description,
            party=self.party,
            contact=self.contact,
            payment_term=self.payment_term,
            company=self.company,
            invoice_address=self.address,
            shipment_address=self.address,
            currency=self.company.currency,
            comment=self.comment,
            sale_date=None,
            origin=self,
            warehouse=Sale.default_warehouse(),
            )

    def create_sale(self):
        '''
        Create a sale for the opportunity and return the sale
        '''
        sale = self._get_sale_opportunity()
        sale_lines = []
        for line in self.lines:
            sale_lines.append(line.get_sale_line(sale))
        sale.lines = sale_lines
        return sale

    @classmethod
    def delete(cls, opportunities):
        # Cancel before delete
        cls.cancel(opportunities)
        for opportunity in opportunities:
            if opportunity.state != 'cancelled':
                raise AccessError(
                    gettext('sale_opportunity.msg_opportunity_delete_cancel',
                        opportunity=opportunity.rec_name))
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
    @set_employee('converted_by')
    def convert(cls, opportunities):
        pool = Pool()
        Sale = pool.get('sale.sale')
        sales = [o.create_sale() for o in opportunities if not o.sales]
        Sale.save(sales)
        for sale in sales:
            sale.origin.copy_resources_to(sale)

    @property
    def is_forecast(self):
        pool = Pool()
        Date = pool.get('ir.date')
        with Transaction().set_context(company=self.company.id):
            today = Date.today()
        return self.end_date or datetime.date.max > today

    @classmethod
    @Workflow.transition('won')
    def won(cls, opportunities):
        pool = Pool()
        Date = pool.get('ir.date')
        for company, c_opportunities in groupby(
                opportunities, key=lambda o: o.company):
            with Transaction().set_context(company=company.id):
                today = Date.today()
            cls.write([o for o in c_opportunities if o.is_forecast], {
                    'end_date': today,
                    'state': 'won',
                    })

    @classmethod
    @ModelView.button
    @Workflow.transition('lost')
    def lost(cls, opportunities):
        pool = Pool()
        Date = pool.get('ir.date')
        for company, c_opportunities in groupby(
                opportunities, key=lambda o: o.company):
            with Transaction().set_context(company=company.id):
                today = Date.today()
            cls.write([o for o in c_opportunities if o.is_forecast], {
                    'end_date': today,
                    'state': 'lost',
                    })

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, opportunities):
        pool = Pool()
        Date = pool.get('ir.date')
        for company, c_opportunities in groupby(
                opportunities, key=lambda o: o.company):
            with Transaction().set_context(company=company.id):
                today = Date.today()
            cls.write([o for o in c_opportunities if o.is_forecast], {
                    'end_date': today,
                    'state': 'cancelled',
                    })

    @staticmethod
    def _sale_won_states():
        return ['confirmed', 'processing', 'done']

    @staticmethod
    def _sale_lost_states():
        return ['cancelled']

    def is_won(self):
        sale_won_states = self._sale_won_states()
        sale_lost_states = self._sale_lost_states()
        end_states = sale_won_states + sale_lost_states
        return (self.sales
            and all(s.state in end_states for s in self.sales)
            and any(s.state in sale_won_states for s in self.sales))

    def is_lost(self):
        sale_lost_states = self._sale_lost_states()
        return (self.sales
            and all(s.state in sale_lost_states for s in self.sales))

    @property
    def sale_amount(self):
        pool = Pool()
        Currency = pool.get('currency.currency')

        if not self.sales:
            return

        sale_lost_states = self._sale_lost_states()
        amount = 0
        for sale in self.sales:
            if sale.state not in sale_lost_states:
                amount += Currency.compute(sale.currency, sale.untaxed_amount,
                    self.currency)
        return amount

    @classmethod
    def process(cls, opportunities):
        won = []
        lost = []
        converted = []
        for opportunity in opportunities:
            sale_amount = opportunity.sale_amount
            if opportunity.amount != sale_amount:
                opportunity.amount = sale_amount
            if opportunity.is_won():
                won.append(opportunity)
            elif opportunity.is_lost():
                lost.append(opportunity)
            elif (opportunity.state != 'converted'
                    and opportunity.sales):
                converted.append(opportunity)
        cls.save(opportunities)
        if won:
            cls.won(won)
        if lost:
            cls.lost(lost)
        if converted:
            cls.convert(converted)


class SaleOpportunityLine(sequence_ordered(), ModelSQL, ModelView):
    'Sale Opportunity Line'
    __name__ = "sale.opportunity.line"
    _history = True
    _states = {
        'readonly': Eval('opportunity_state').in_(
            ['converted', 'won', 'lost', 'cancelled']),
        }

    opportunity = fields.Many2One('sale.opportunity', 'Opportunity',
        ondelete='CASCADE', select=True, required=True,
        states={
            'readonly': _states['readonly'] & Bool(Eval('opportunity')),
            })
    opportunity_state = fields.Function(
        fields.Selection('get_opportunity_states', "Opportunity State"),
        'on_change_with_opportunity_state')
    product = fields.Many2One('product.product', 'Product', required=True,
        domain=[('salable', '=', True)], states=_states)
    quantity = fields.Float(
        "Quantity", digits='unit', required=True, states=_states)
    unit = fields.Many2One('product.uom', 'Unit', required=True,
        states=_states)

    del _states

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('opportunity')

    @classmethod
    def get_opportunity_states(cls):
        pool = Pool()
        Opportunity = pool.get('sale.opportunity')
        return Opportunity.fields_get(['state'])['state']['selection']

    @fields.depends('opportunity', '_parent_opportunity.state')
    def on_change_with_opportunity_state(self, name=None):
        if self.opportunity:
            return self.opportunity.state

    @fields.depends('product', 'unit')
    def on_change_product(self):
        if not self.product:
            return

        category = self.product.sale_uom.category
        if not self.unit or self.unit.category != category:
            self.unit = self.product.sale_uom

    def get_sale_line(self, sale):
        '''
        Return sale line for opportunity line
        '''
        SaleLine = Pool().get('sale.line')
        sale_line = SaleLine(
            type='line',
            product=self.product,
            sale=sale,
            description=None,
            )
        sale_line.on_change_product()
        self._set_sale_line_quantity(sale_line)
        sale_line.on_change_quantity()
        return sale_line

    def _set_sale_line_quantity(self, sale_line):
        sale_line.quantity = self.quantity
        sale_line.unit = self.unit

    def get_rec_name(self, name):
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get()
        return (lang.format_number_symbol(
                self.quantity or 0, self.unit, digits=self.unit.digits)
            + ' %s @ %s' % (self.product.rec_name, self.opportunity.rec_name))

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('product.rec_name',) + tuple(clause[1:])]


class SaleOpportunityReportMixin:
    __slots__ = ()
    number = fields.Integer('Number')
    converted = fields.Integer('Converted')
    conversion_rate = fields.Function(fields.Float('Conversion Rate',
        digits=(1, 4)), 'get_conversion_rate')
    won = fields.Integer('Won')
    winning_rate = fields.Function(fields.Float('Winning Rate', digits=(1, 4)),
        'get_winning_rate')
    lost = fields.Integer('Lost')
    company = fields.Many2One('company.company', 'Company')
    currency = fields.Function(fields.Many2One('currency.currency',
        'Currency'), 'get_currency')
    amount = Monetary("Amount", currency='currency', digits='currency')
    converted_amount = Monetary(
        "Converted Amount", currency='currency', digits='currency')
    conversion_amount_rate = fields.Function(fields.Float(
        'Conversion Amount Rate', digits=(1, 4)), 'get_conversion_amount_rate')
    won_amount = Monetary("Won Amount", currency='currency', digits='currency')
    winning_amount_rate = fields.Function(fields.Float(
            'Winning Amount Rate', digits=(1, 4)), 'get_winning_amount_rate')

    @staticmethod
    def _converted_state():
        return ['converted', 'won']

    @staticmethod
    def _won_state():
        return ['won']

    @staticmethod
    def _lost_state():
        return ['lost']

    def get_conversion_rate(self, name):
        if self.number:
            digits = getattr(self.__class__, name).digits[1]
            return round(float(self.converted) / self.number, digits)
        else:
            return 0.0

    def get_winning_rate(self, name):
        if self.number:
            digits = getattr(self.__class__, name).digits[1]
            return round(float(self.won) / self.number, digits)
        else:
            return 0.0

    def get_currency(self, name):
        return self.company.currency.id

    def get_conversion_amount_rate(self, name):
        if self.amount:
            digits = getattr(self.__class__, name).digits[1]
            return round(
                float(self.converted_amount) / float(self.amount), digits)
        else:
            return 0.0

    def get_winning_amount_rate(self, name):
        if self.amount:
            digits = getattr(self.__class__, name).digits[1]
            return round(float(self.won_amount) / float(self.amount), digits)
        else:
            return 0.0

    @classmethod
    def table_query(cls):
        Opportunity = Pool().get('sale.opportunity')
        opportunity = Opportunity.__table__()
        return opportunity.select(
            Max(opportunity.create_uid).as_('create_uid'),
            Max(opportunity.create_date).as_('create_date'),
            Max(opportunity.write_uid).as_('write_uid'),
            Max(opportunity.write_date).as_('write_date'),
            opportunity.company,
            Count(Literal(1)).as_('number'),
            Sum(Case(
                    (opportunity.state.in_(cls._converted_state()),
                        Literal(1)), else_=Literal(0))).as_('converted'),
            Sum(Case(
                    (opportunity.state.in_(cls._won_state()),
                        Literal(1)), else_=Literal(0))).as_('won'),
            Sum(Case(
                    (opportunity.state.in_(cls._lost_state()),
                        Literal(1)), else_=Literal(0))).as_('lost'),
            Sum(opportunity.amount).as_('amount'),
            Sum(Case(
                    (opportunity.state.in_(cls._converted_state()),
                        opportunity.amount),
                    else_=Literal(0))).as_('converted_amount'),
            Sum(Case(
                    (opportunity.state.in_(cls._won_state()),
                        opportunity.amount),
                    else_=Literal(0))).as_('won_amount'))


class SaleOpportunityEmployee(SaleOpportunityReportMixin, ModelSQL, ModelView):
    'Sale Opportunity per Employee'
    __name__ = 'sale.opportunity_employee'
    employee = fields.Many2One('company.employee', 'Employee')

    @classmethod
    def table_query(cls):
        query = super(SaleOpportunityEmployee, cls).table_query()
        opportunity, = query.from_
        query.columns += (
            Coalesce(opportunity.employee, 0).as_('id'),
            opportunity.employee,
            )
        where = Literal(True)
        if Transaction().context.get('start_date'):
            where &= (opportunity.start_date
                >= Transaction().context['start_date'])
        if Transaction().context.get('end_date'):
            where &= (opportunity.start_date
                <= Transaction().context['end_date'])
        query.where = where
        query.group_by = (opportunity.employee, opportunity.company)
        return query


class SaleOpportunityEmployeeContext(ModelView):
    'Sale Opportunity per Employee Context'
    __name__ = 'sale.opportunity_employee.context'
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')


class MonthLabelMixin:
    __slots__ = ()

    month_label = fields.Function(fields.Char("Month"), 'get_month_label')

    @classmethod
    def order_month_label(cls, tables):
        table, _ = tables[None]
        return [table.month]

    def get_month_label(self, name):
        return self.month.strftime('%Y-%m')


class SaleOpportunityMonthly(
        MonthLabelMixin, SaleOpportunityReportMixin, ModelSQL, ModelView):
    'Sale Opportunity per Month'
    __name__ = 'sale.opportunity_monthly'
    month = fields.Date("Month")

    @classmethod
    def __setup__(cls):
        super(SaleOpportunityMonthly, cls).__setup__()
        cls._order.insert(0, ('month', 'DESC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        Month = pool.get('ir.calendar.month')
        month = Month.__table__()
        query = super(SaleOpportunityMonthly, cls).table_query()
        opportunity, = query.from_
        month_timestamp = DateTrunc('MONTH', opportunity.start_date)
        id_ = Extract('EPOCH', month_timestamp)
        month = cls.month.sql_cast(month_timestamp)
        query.columns += (
            id_.as_('id'),
            month.as_('month'),
            )
        query.group_by = [id_, month, opportunity.company]
        return query


class SaleOpportunityEmployeeMonthly(
        MonthLabelMixin, SaleOpportunityReportMixin, ModelSQL, ModelView):
    'Sale Opportunity per Employee per Month'
    __name__ = 'sale.opportunity_employee_monthly'
    month = fields.Date("Month")
    employee = fields.Many2One('company.employee', 'Employee')

    @classmethod
    def __setup__(cls):
        super(SaleOpportunityEmployeeMonthly, cls).__setup__()
        cls._order.insert(1, ('month', 'DESC'))
        cls._order.insert(2, ('employee', 'ASC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        Month = pool.get('ir.calendar.month')
        month = Month.__table__()
        query = super(SaleOpportunityEmployeeMonthly, cls).table_query()
        opportunity, = query.from_
        month_timestamp = DateTrunc('MONTH', opportunity.start_date)
        id_ = Extract('EPOCH', month_timestamp)
        month = cls.month.sql_cast(month_timestamp)
        query.columns += (
            id_.as_('id'),
            month.as_('month'),
            opportunity.employee,
            )
        query.group_by = [
            id_, month, opportunity.employee, opportunity.company]
        return query
