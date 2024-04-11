# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"Sales extension for managing leads and opportunities"
import datetime
from itertools import groupby

from sql.functions import CharLength

from trytond.i18n import gettext
from trytond.ir.attachment import AttachmentCopyMixin
from trytond.ir.note import NoteCopyMixin
from trytond.model import (
    Index, ModelSQL, ModelView, Workflow, fields, sequence_ordered)
from trytond.model.exceptions import AccessError
from trytond.modules.company.model import employee_field, set_employee
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, Get, If, In
from trytond.tools import firstline
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

    number = fields.Char("Number", readonly=True, required=True)
    reference = fields.Char("Reference")
    party = fields.Many2One(
        'party.party', "Party",
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
    address = fields.Many2One(
        'party.address', "Address", states=_states_stop,
        domain=[('party', '=', Eval('party'))],
        help="The default address for the invoice and shipment.\n"
        "Leave empty to use the default values.")
    company = fields.Many2One(
        'company.company', "Company", required=True,
        states={
            'readonly': _states_stop['readonly'] | Eval('party', True),
            },
        domain=[
            ('id', If(In('company', Eval('context', {})), '=', '!='),
                Get(Eval('context', {}), 'company', 0)),
            ])
    currency = fields.Many2One(
        'currency.currency', "Currency", required=True, states=_states_start)
    amount = Monetary(
        "Amount", currency='currency', digits='currency',
        states=_states_stop,
        help='Estimated revenue amount.')
    payment_term = fields.Many2One(
        'account.invoice.payment_term', "Payment Term", ondelete='RESTRICT',
        states={
            'readonly': In(Eval('state'),
                ['converted', 'lost', 'cancelled']),
            })
    employee = fields.Many2One('company.employee', 'Employee',
        states={
            'readonly': _states_stop['readonly'],
            'required': ~Eval('state').in_(['lead', 'lost', 'cancelled']),
        },
        domain=[('company', '=', Eval('company'))])
    start_date = fields.Date("Start Date", required=True, states=_states_start)
    end_date = fields.Date("End Date", states=_states_stop)
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
            ], "State", required=True, sort=False, readonly=True)

    del _states_start
    del _states_stop

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Company = pool.get('company.company')
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        sql_table = cls.__table__()
        company = Company.__table__()

        table = cls.__table_handler__(module_name)
        currency_exists = table.column_exist('currency')

        super(SaleOpportunity, cls).__register__(module_name)

        # Migration from 5.0: drop required on description
        table.not_null_action('description', action='remove')

        # Migration from 6.4: store currency
        if not currency_exists:
            value = company.select(
                company.currency,
                where=(sql_table.company == company.id))
            cursor.execute(*sql_table.update(
                    [sql_table.currency],
                    [value]))

    @classmethod
    def __setup__(cls):
        cls.number.search_unaccented = False
        cls.reference.search_unaccented = False
        super(SaleOpportunity, cls).__setup__()
        t = cls.__table__()
        cls._sql_indexes.update({
                Index(t, (t.reference, Index.Similarity())),
                Index(t, (t.party, Index.Equality())),
                Index(
                    t,
                    (t.start_date, Index.Range(order='DESC')),
                    (t.end_date, Index.Range(order='DESC'))),
                Index(
                    t, (t.state, Index.Equality()),
                    where=t.state.in_(['lead', 'opportunity'])),
                })
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

    @classmethod
    def order_number(cls, tables):
        table, _ = tables[None]
        return [CharLength(table.number), table.number]

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

    @fields.depends('amount', 'company')
    def on_change_company(self):
        self.payment_term = self.default_payment_term(
            company=self.company.id if self.company else None)
        if not self.amount:
            self.currency = self.default_currency(
                company=self.company.id if self.company else None)

    @classmethod
    def default_currency(cls, **pattern):
        pool = Pool()
        Company = pool.get('company.company')
        company = pattern.get('company')
        if not company:
            company = cls.default_company()
        if company:
            return Company(company).currency.id

    @staticmethod
    def default_employee():
        return Transaction().context.get('employee')

    @classmethod
    def default_payment_term(cls, **pattern):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        config = Configuration(1)
        payment_term = config.get_multivalue(
            'default_customer_payment_term', **pattern)
        return payment_term.id if payment_term else None

    def get_rec_name(self, name):
        items = [self.number]
        if self.reference:
            items.append(f'[{self.reference}]')
        return ' '.join(items)

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, value = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        domain = [bool_op,
            ('number', operator, value),
            ('reference', operator, value),
            ]
        return domain

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

    @fields.depends('party', 'amount', 'company')
    def on_change_party(self):
        self.payment_term = self.default_payment_term(
            company=self.company.id if self.company else None)
        if self.party:
            if self.party.customer_payment_term:
                self.payment_term = self.party.customer_payment_term
            if not self.amount:
                if self.party.customer_currency:
                    self.currency = self.party.customer_currency

    def _get_sale_opportunity(self):
        '''
        Return sale for an opportunity
        '''
        pool = Pool()
        Sale = pool.get('sale.sale')
        sale = Sale(
            description=self.description,
            party=self.party,
            contact=self.contact,
            company=self.company,
            comment=self.comment,
            sale_date=None,
            origin=self,
            warehouse=Sale.default_warehouse(),
            )
        sale.on_change_party()
        if self.address:
            sale.invoice_address = sale.shipment_address = self.address
        if self.payment_term:
            sale.payment_term = self.payment_term
        sale.currency = self.currency
        return sale

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
    @ModelView.button_action('sale.act_sale_form')
    @Workflow.transition('converted')
    @set_employee('converted_by')
    def convert(cls, opportunities):
        pool = Pool()
        Sale = pool.get('sale.sale')
        sales = [o.create_sale() for o in opportunities if not o.sales]
        Sale.save(sales)
        for sale in sales:
            sale.origin.copy_resources_to(sale)
        return {
            'res_id': [s.id for s in sales],
            }

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

    opportunity = fields.Many2One(
        'sale.opportunity', "Opportunity", ondelete='CASCADE', required=True,
        states={
            'readonly': _states['readonly'] & Bool(Eval('opportunity')),
            })
    opportunity_state = fields.Function(
        fields.Selection('get_opportunity_states', "Opportunity State"),
        'on_change_with_opportunity_state')
    product = fields.Many2One(
        'product.product', "Product",
        domain=[
            If(Eval('opportunity_state').in_(['lead', 'opportunity'])
                & ~(Eval('quantity', 0) < 0),
                ('salable', '=', True),
                ()),
            ],
        states=_states)
    product_uom_category = fields.Function(
        fields.Many2One(
            'product.uom.category', "Product UoM Category"),
        'on_change_with_product_uom_category')
    quantity = fields.Float(
        "Quantity", digits='unit', required=True, states=_states)
    unit = fields.Many2One(
        'product.uom', "Unit",
        domain=[
            If(Eval('product_uom_category'),
                ('category', '=', Eval('product_uom_category', -1)),
                ('category', '=', -1)),
            ],
        states={
            'required': Bool(Eval('product')),
            'readonly': _states['readonly'],
            })
    description = fields.Text("Description", states=_states)
    summary = fields.Function(fields.Char("Summary"), 'on_change_with_summary')
    note = fields.Text("Note")

    del _states

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('opportunity')

    @classmethod
    def __register__(cls, module):
        table_h = cls.__table_handler__(module)
        super().__register__(module)
        # Migration from 7.0: remove required on product and unit
        table_h.not_null_action('product', 'remove')
        table_h.not_null_action('unit', 'remove')

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

    @fields.depends('product')
    def on_change_with_product_uom_category(self, name=None):
        return self.product.default_uom_category if self.product else None

    @fields.depends('description')
    def on_change_with_summary(self, name=None):
        return firstline(self.description or '')

    def get_sale_line(self, sale):
        '''
        Return sale line for opportunity line
        '''
        SaleLine = Pool().get('sale.line')
        sale_line = SaleLine(
            type='line',
            product=self.product,
            sale=sale,
            description=self.description,
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
        if self.product:
            return (lang.format_number_symbol(
                    self.quantity or 0, self.unit, digits=self.unit.digits)
                + ' %s @ %s' % (
                    self.product.rec_name, self.opportunity.rec_name))
        else:
            return self.opportunity.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('product.rec_name',) + tuple(clause[1:])]
