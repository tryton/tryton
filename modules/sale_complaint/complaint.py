# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from sql import Null
from sql.functions import CharLength

from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, Index, ModelSQL, ModelView, Workflow, fields)
from trytond.model.exceptions import AccessError
from trytond.modules.company.model import (
    employee_field, reset_employee, set_employee)
from trytond.modules.currency.fields import Monetary
from trytond.modules.product import price_digits
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, If
from trytond.tools import grouped_slice
from trytond.transaction import Transaction

from .exceptions import ComplaintSimilarWarning


class Type(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'sale.complaint.type'

    name = fields.Char('Name', required=True)
    origin = fields.Many2One('ir.model', 'Origin', required=True,
        domain=[('name', 'in', [
                    'sale.sale', 'sale.line',
                    'account.invoice', 'account.invoice.line'])])


class Complaint(Workflow, ModelSQL, ModelView):
    __name__ = 'sale.complaint'
    _rec_name = 'number'

    _states = {
        'readonly': Eval('state') != 'draft',
        }

    number = fields.Char("Number", readonly=True)
    reference = fields.Char("Reference")
    date = fields.Date('Date', states=_states)
    customer = fields.Many2One(
        'party.party', "Customer", required=True, states=_states,
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    company = fields.Many2One(
        'company.company', 'Company', required=True,
        states={
            'readonly': _states['readonly'] | Eval('origin'),
            })
    type = fields.Many2One('sale.complaint.type', 'Type', required=True,
        states=_states)
    origin = fields.Reference('Origin', selection='get_origin',
        domain={
            'sale.sale': [
                If(Eval('customer'),
                    ('party', '=', Eval('customer', -1)),
                    ()),
                ('company', '=', Eval('company', -1)),
                ('state', 'in', ['confirmed', 'processing', 'done']),
                ],
            'sale.line': [
                ('type', '=', 'line'),
                If(Eval('customer'),
                    ('sale.party', '=', Eval('customer')),
                    ()),
                ('sale.company', '=', Eval('company')),
                ('sale.state', 'in', ['confirmed', 'processing', 'done']),
                ],
            'account.invoice': [
                If(Eval('customer'),
                    ('party', '=', Eval('customer', -1)),
                    ()),
                ('company', '=', Eval('company', -1)),
                ('type', '=', 'out'),
                ('state', 'in', ['posted', 'paid']),
                ],
            'account.invoice.line': [
                ('type', '=', 'line'),
                If(Eval('customer'),
                    ('invoice.party', '=', Eval('customer')),
                    ()),
                ('invoice.company', '=', Eval('company')),
                ('invoice.type', '=', 'out'),
                ('invoice.state', 'in', ['posted', 'paid']),
                ],
            },
        states={
            'readonly': ((Eval('state') != 'draft')
                | Bool(Eval('actions', [0]))),
            'required': Bool(Eval('origin_model')),
            },
        depends={'origin_model'})
    origin_id = fields.Function(fields.Integer('Origin ID'),
        'on_change_with_origin_id')
    origin_model = fields.Function(fields.Char('Origin Model'),
        'on_change_with_origin_model')
    description = fields.Text('Description', states=_states)
    actions = fields.One2Many('sale.complaint.action', 'complaint', 'Actions',
        states={
            'readonly': ((Eval('state') != 'draft')
                | (If(~Eval('origin_id', 0), 0, Eval('origin_id', 0)) <= 0)),
            },
        depends={'origin_model'})
    submitted_by = employee_field(
        "Submitted By",
        states=['waiting', 'approved', 'rejected', 'done', 'cancelled'])
    approved_by = employee_field(
        "Approved By",
        states=['approved', 'rejected', 'done', 'cancelled'])
    rejected_by = employee_field(
        "Rejected By",
        states=['approved', 'rejected', 'done', 'cancelled'])
    cancelled_by = employee_field(
        "Cancelled By",
        states=['cancelled'])
    state = fields.Selection([
            ('draft', 'Draft'),
            ('waiting', 'Waiting'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
            ], "State", readonly=True, required=True, sort=False)

    @classmethod
    def __setup__(cls):
        cls.number.search_unaccented = False
        cls.reference.search_unaccented = False
        super().__setup__()
        t = cls.__table__()
        cls._sql_indexes.update({
                Index(t, (t.reference, Index.Similarity())),
                Index(
                    t,
                    (t.state, Index.Equality(cardinality='low')),
                    where=t.state.in_(['draft', 'waiting', 'approved'])),
                })
        cls._order.insert(0, ('date', 'DESC'))
        cls._transitions |= set((
                ('draft', 'waiting'),
                ('waiting', 'draft'),
                ('waiting', 'approved'),
                ('waiting', 'rejected'),
                ('approved', 'done'),
                ('approved', 'draft'),
                ('draft', 'cancelled'),
                ('waiting', 'cancelled'),
                ('done', 'draft'),
                ('rejected', 'draft'),
                ('cancelled', 'draft'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': ~Eval('state').in_(['draft', 'waiting']),
                    'depends': ['state'],
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(
                        ['waiting', 'done', 'cancelled']),
                    'icon': If(Eval('state').in_(['done', 'cancelled']),
                        'tryton-undo', 'tryton-back'),
                    'depends': ['state'],
                    },
                'wait': {
                    'invisible': ~Eval('state').in_(['draft']),
                    'depends': ['state'],
                    },
                'approve': {
                    'invisible': ~Eval('state').in_(['waiting']),
                    'depends': ['state'],
                    },
                'reject': {
                    'invisible': ~Eval('state').in_(['waiting']),
                    'depends': ['state'],
                    },
                'process': {
                    'invisible': ~Eval('state').in_(['approved']),
                    'depends': ['state'],
                    },
                })

        actions_domains = cls._actions_domains()
        actions_domain = [('action', 'in', actions_domains.pop(None))]
        for model, actions in actions_domains.items():
            actions_domain = If(Eval('origin_model') == model,
                [('action', 'in', actions)], actions_domain)
        cls.actions.domain = [actions_domain]

    @classmethod
    def __register__(cls, module_name):
        table_h = cls.__table_handler__(module_name)

        # Migration from 6.4: rename employee into submitted_by
        if (table_h.column_exist('employee')
                and not table_h.column_exist('submitted_by')):
            table_h.column_rename('employee', 'submitted_by')

        super().__register__(module_name)

    @classmethod
    def _actions_domains(cls):
        return {
            None: [],
            'sale.sale': ['sale_return'],
            'sale.line': ['sale_return'],
            'account.invoice': ['credit_note'],
            'account.invoice.line': ['credit_note'],
            }

    @classmethod
    def order_number(cls, tables):
        table, _ = tables[None]
        return [
            ~((table.state == 'cancelled') & (table.number == Null)),
            CharLength(table.number), table.number]

    @staticmethod
    def default_date():
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_state():
        return 'draft'

    @fields.depends('type')
    def get_origin(self):
        if self.type:
            origin = self.type.origin
            return [('', ''), (origin.name, origin.name)]
        else:
            return []

    @fields.depends('origin', 'customer')
    def on_change_origin(self):
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')
        Invoice = pool.get('account.invoice')
        InvoiceLine = pool.get('account.invoice.line')
        if not self.customer and self.origin and self.origin.id >= 0:
            if isinstance(self.origin, Sale):
                self.customer = self.origin.party
            elif isinstance(self.origin, SaleLine):
                self.customer = self.origin.sale.party
            elif isinstance(self.origin, Invoice):
                self.customer = self.origin.party
            elif isinstance(self.origin, InvoiceLine) and self.origin.invoice:
                self.customer = self.origin.invoice.party

    @fields.depends('origin')
    def on_change_with_origin_id(self, name=None):
        if self.origin:
            return self.origin.id

    @fields.depends('origin')
    def on_change_with_origin_model(self, name=None):
        if self.origin:
            return self.origin.__class__.__name__

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/tree', 'visual', If(Eval('state') == 'cancelled', 'muted', '')),
            ]

    @classmethod
    def preprocess_values(cls, mode, values):
        pool = Pool()
        Configuration = pool.get('sale.configuration')
        values = super().preprocess_values(mode, values)
        if mode == 'create' and not values.get('number'):
            company_id = values.get('company', cls.default_company())
            if company_id is not None:
                configuration = Configuration(1)
                if sequence := configuration.get_multivalue(
                        'complaint_sequence', company=company_id):
                    values['number'] = sequence.get()
        return values

    @classmethod
    def check_modification(cls, mode, complaints, values=None, external=False):
        super().check_modification(
            mode, complaints, values=values, external=external)
        if mode == 'delete':
            for complaint in complaints:
                if complaint.state != 'draft':
                    raise AccessError(gettext(
                            'sale_complaint.msg_complaint_delete_draft',
                            complaint=complaint.rec_name))

    @classmethod
    def copy(cls, complaints, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('number', None)
        default.setdefault('submitted_by')
        default.setdefault('approved_by')
        default.setdefault('rejected_by')
        default.setdefault('cancelled_by')
        return super().copy(complaints, default=default)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    @set_employee('cancelled_by')
    def cancel(cls, complaints):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    @reset_employee(
        'submitted_by', 'approved_by', 'rejected_by', 'cancelled_by')
    def draft(cls, complaints):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('waiting')
    @set_employee('submitted_by')
    def wait(cls, complaints):
        cls._check_similar(complaints)

    @classmethod
    @ModelView.button
    @Workflow.transition('approved')
    @set_employee('approved_by')
    def approve(cls, complaints):
        pool = Pool()
        Configuration = pool.get('sale.configuration')
        transaction = Transaction()
        context = transaction.context
        config = Configuration(1)
        with transaction.set_context(
                queue_scheduled_at=config.sale_process_after,
                queue_batch=context.get('queue_batch', True)):
            cls.__queue__.process(complaints)

    @classmethod
    @ModelView.button
    @Workflow.transition('rejected')
    @set_employee('rejected_by')
    def reject(cls, complaints):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def process(cls, complaints):
        pool = Pool()
        Action = pool.get('sale.complaint.action')
        results = defaultdict(list)
        actions = defaultdict(list)
        for complaint in complaints:
            for action in complaint.actions:
                if action.result:
                    continue
                result = action.do()
                results[result.__class__].append(result)
                actions[result.__class__].append(action)
        for kls, records in results.items():
            kls.save(records)
            for action, record in zip(actions[kls], records):
                action.result = record
        Action.save(sum(list(actions.values()), []))

    @classmethod
    def _check_similar(cls, complaints):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        for sub_complaints in grouped_slice(complaints):
            sub_complaints = list(sub_complaints)
            domain = list(filter(None,
                    (c._similar_domain() for c in sub_complaints)))
            if not domain:
                continue
            if cls.search(['OR'] + domain, order=[]):
                for complaint in sub_complaints:
                    domain = complaint._similar_domain()
                    if not domain:
                        continue
                    try:
                        similar, = cls.search(domain, limit=1)
                    except ValueError:
                        continue
                    warning_key = Warning.format(
                        'complaint_similar', [complaint])
                    if Warning.check(warning_key):
                        raise ComplaintSimilarWarning(warning_key,
                            gettext('sale_complaint.msg_complaint_similar',
                                similar=similar.rec_name,
                                complaint=complaint.rec_name))

    def _similar_domain(self):
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')
        Invoice = pool.get('account.invoice')
        InvoiceLine = pool.get('account.invoice.line')
        domain = ['OR',
            ('origin', '=', str(self.origin)),
            ]
        if isinstance(self.origin, Sale):
            domain.append(('origin.sale', '=', self.origin.id, 'sale.line'))
        elif isinstance(self.origin, SaleLine):
            domain.append(('origin', '=', str(self.origin.sale)))
        elif isinstance(self.origin, Invoice):
            domain.append(
                ('origin.invoice', '=', self.origin.id,
                    'account.invoice.line'))
        elif isinstance(self.origin, InvoiceLine):
            domain.append(('origin', '=', str(self.origin.invoice)))
        return [
            domain,
            ('id', '!=', self.id),
            ]


class Action(ModelSQL, ModelView):
    __name__ = 'sale.complaint.action'

    _states = {
        'readonly': ((Eval('complaint_state') != 'draft')
            | Bool(Eval('result'))),
        }
    _line_states = {
        'invisible': ~Eval('_parent_complaint', {}
            ).get('origin_model', 'sale.line').in_(
            ['sale.line', 'account.invoice.line']),
        'readonly': _states['readonly'],
        }

    complaint = fields.Many2One(
        'sale.complaint', 'Complaint', required=True, ondelete='CASCADE',
        states=_states)
    action = fields.Selection([
            ('sale_return', 'Create Sale Return'),
            ('credit_note', 'Create Credit Note'),
            ], 'Action', states=_states)

    sale_lines = fields.One2Many(
        'sale.complaint.action-sale.line', 'action', "Sale Lines",
        states={
            'invisible': Eval('_parent_complaint', {}
                ).get('origin_model', 'sale.sale') != 'sale.sale',
            'readonly': _states['readonly'],
            },
        help='Leave empty for all lines.')

    invoice_lines = fields.One2Many(
        'sale.complaint.action-account.invoice.line', 'action',
        "Invoice Lines",
        states={
            'invisible': Eval('_parent_complaint', {}
                ).get('origin_model', 'account.invoice.line'
                ) != 'account.invoice',
            'readonly': _states['readonly'],
            },
        help='Leave empty for all lines.')

    quantity = fields.Float(
        "Quantity", digits='unit',
        states=_line_states,
        help='Leave empty for the same quantity.')
    unit = fields.Function(fields.Many2One('product.uom', 'Unit',
            states=_line_states),
        'on_change_with_unit')
    unit_price = Monetary(
        "Unit Price", currency='currency', digits=price_digits,
        states=_line_states,
        help='Leave empty for the same price.')

    amount = fields.Function(Monetary(
            "Amount", 'currency', digits='currency'),
        'on_change_with_amount')
    currency = fields.Function(fields.Many2One(
            'currency.currency', "Currency"),
        'on_change_with_currency')

    result = fields.Reference('Result', selection='get_result', readonly=True)

    complaint_state = fields.Function(
        fields.Selection('get_complaint_states', "Complaint State"),
        'on_change_with_complaint_state')
    company = fields.Function(
        fields.Many2One('company.company', "Company"),
        'on_change_with_company')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('complaint')

    @fields.depends('complaint',
        '_parent_complaint.origin_model', '_parent_complaint.origin')
    def on_change_with_unit(self, name=None):
        if (self.complaint
                and self.complaint.origin_model in {
                    'sale.line', 'account.invoice.line'}):
            return self.complaint.origin.unit

    @fields.depends(
        'quantity', 'unit_price', 'currency', 'sale_lines', 'invoice_lines',
        'complaint', '_parent_complaint.origin_model',
        '_parent_complaint.origin')
    def on_change_with_amount(self, name=None):
        if self.complaint:
            if self.complaint.origin_model in {
                    'sale.line', 'account.invoice.line'}:
                if self.quantity is not None:
                    quantity = self.quantity
                elif (self.complaint.origin_model == 'sale.line'
                        and self.complaint.origin.actual_quantity is not None):
                    quantity = self.complaint.origin.actual_quantity
                else:
                    quantity = self.complaint.origin.quantity
                if self.unit_price is not None:
                    unit_price = self.unit_price
                else:
                    unit_price = self.complaint.origin.unit_price
                amount = Decimal(str(quantity)) * unit_price
                if self.currency:
                    amount = self.currency.round(amount)
                return amount
            elif self.complaint.origin_model == 'sale.sale':
                if not self.sale_lines:
                    if self.complaint and self.complaint.origin:
                        sale = self.complaint.origin
                        amount = 0
                        for line in sale.lines:
                            if line.type != 'line':
                                continue
                            if line.actual_quantity is not None:
                                quantity = line.actual_quantity
                            else:
                                quantity = line.quantity
                            amount += sale.currency.round(
                                Decimal(str(quantity)) * line.unit_price)
                        return amount
                else:
                    return sum(
                        getattr(l, 'amount', None) or Decimal(0)
                        for l in self.sale_lines)
            elif self.complaint.origin_model == 'account.invoice':
                if not self.invoice_lines:
                    if self.complaint and self.complaint.origin:
                        return self.complaint.origin.untaxed_amount
                else:
                    return sum(
                        getattr(l, 'amount', None) or Decimal(0)
                        for l in self.invoice_lines)

    @fields.depends(
        'complaint',
        '_parent_complaint.origin_model', '_parent_complaint.origin')
    def on_change_with_currency(self, name=None):
        if (self.complaint
                and self.complaint.origin_model in {
                    'sale.sale', 'sale.line',
                    'account.invoice', 'account.invoice.line'}):
            return self.complaint.origin.currency

    @classmethod
    def get_complaint_states(cls):
        pool = Pool()
        Complaint = pool.get('sale.complaint')
        return Complaint.fields_get(['state'])['state']['selection']

    @fields.depends('complaint', '_parent_complaint.state')
    def on_change_with_complaint_state(self, name=None):
        if self.complaint:
            return self.complaint.state

    @fields.depends('complaint', '_parent_complaint.company')
    def on_change_with_company(self, name=None):
        if self.complaint:
            return self.complaint.company

    @classmethod
    def _get_result(cls):
        'Return list of Model names for result Reference'
        return ['sale.sale', 'account.invoice']

    @classmethod
    def get_result(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        get_name = Model.get_name
        models = cls._get_result()
        return [(None, '')] + [(m, get_name(m)) for m in models]

    @classmethod
    def copy(cls, actions, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('result', None)
        return super().copy(actions, default=default)

    def do(self):
        return getattr(self, 'do_%s' % self.action)()

    def do_sale_return(self):
        pool = Pool()
        Sale = pool.get('sale.sale')
        Line = pool.get('sale.line')

        if isinstance(self.complaint.origin, (Sale, Line)):
            default = {}
            if isinstance(self.complaint.origin, Sale):
                sale = self.complaint.origin
                if self.sale_lines:
                    sale_lines = [l.line for l in self.sale_lines]
                    line2qty = {
                        l.line.id: l.get_quantity() for l in self.sale_lines}
                    line2price = {
                        l.line.id: l.get_unit_price() for l in self.sale_lines}
                    default['quantity'] = lambda o: line2qty.get(o['id'])
                    default['unit_price'] = lambda o: line2price.get(o['id'])
                else:
                    sale_lines = [l for l in sale.lines if l.type == 'line']
                    default['quantity'] = lambda o: (
                        o['actual_quantity']
                        if o['actual_quantity'] is not None
                        else o['quantity'])
            elif isinstance(self.complaint.origin, Line):
                sale_line = self.complaint.origin
                sale = sale_line.sale
                sale_lines = [sale_line]
                if self.quantity is not None:
                    default['quantity'] = self.quantity
                else:
                    default['quantity'] = (
                        sale_line.actual_quantity
                        if sale_line.actual_quantity is not None
                        else sale_line.quantity)
                if self.unit_price is not None:
                    default['unit_price'] = self.unit_price
            return_sale, = Sale.copy([sale], default={'lines': None})
            default['sale'] = return_sale.id
            Line.copy(sale_lines, default=default)
        else:
            return
        return_sale.origin = self.complaint
        for line in return_sale.lines:
            if line.type == 'line':
                line.quantity *= -1
        return_sale.lines = return_sale.lines  # Force saving
        return return_sale

    def do_credit_note(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Line = pool.get('account.invoice.line')

        if isinstance(self.complaint.origin, (Invoice, Line)):
            line2qty = line2price = {}
            if isinstance(self.complaint.origin, Invoice):
                invoice = self.complaint.origin
                if self.invoice_lines:
                    invoice_lines = [l.line for l in self.invoice_lines]
                    line2qty = {l.line: l.quantity
                        for l in self.invoice_lines
                        if l.quantity is not None}
                    line2price = {l.line: l.unit_price
                        for l in self.invoice_lines
                        if l.unit_price is not None}
                else:
                    invoice_lines = [
                        l for l in invoice.lines if l.type == 'line']
            elif isinstance(self.complaint.origin, Line):
                invoice_line = self.complaint.origin
                invoice = invoice_line.invoice
                invoice_lines = [invoice_line]
                if self.quantity is not None:
                    line2qty = {invoice_line: self.quantity}
                if self.unit_price is not None:
                    line2price = {invoice_line: self.unit_price}
            with Transaction().set_context(_account_invoice_correction=True):
                credit_note, = Invoice.copy([invoice], default={
                        'lines': [],
                        'taxes': [],
                        })
                # Copy each line one by one to get negative and positive lines
                # following each other
                for invoice_line in invoice_lines:
                    qty = line2qty.get(invoice_line, invoice_line.quantity)
                    unit_price = invoice_line.unit_price - line2price.get(
                        invoice_line, invoice_line.unit_price)
                    Line.copy([invoice_line], default={
                            'invoice': credit_note.id,
                            'quantity': -qty,
                            'origin': str(self.complaint),
                            })
                    credit_line, = Line.copy([invoice_line], default={
                            'invoice': credit_note.id,
                            'quantity': qty,
                            'unit_price': unit_price,
                            'origin': str(self.complaint),
                            })
            credit_note.update_taxes()
        else:
            return
        return credit_note

    @classmethod
    def check_modification(cls, mode, actions, values=None, external=False):
        super().check_modification(
            mode, actions, values=values, external=external)
        if mode == 'delete':
            for action in actions:
                if action.result:
                    raise AccessError(gettext(
                            'sale_complaint.msg_action_delete_result',
                            action=action.rec_name))


class _Action_Line:
    __slots__ = ()
    _states = {
        'readonly': (
            (Eval('complaint_state') != 'draft')
            | Bool(Eval('_parent_action.result', True))),
        }

    action = fields.Many2One(
        'sale.complaint.action', "Action", ondelete='CASCADE', required=True)
    quantity = fields.Float(
        "Quantity", digits='unit', states=_states)
    unit = fields.Function(
        fields.Many2One('product.uom', "Unit"), 'on_change_with_unit')
    unit_price = Monetary(
        "Unit Price", currency='currency', digits=price_digits,
        states=_states,
        help='Leave empty for the same price.')

    amount = fields.Function(Monetary(
            "Amount", currency='currency', digits='currency'),
        'on_change_with_amount')
    currency = fields.Function(fields.Many2One(
            'currency.currency', "Currency"),
        'on_change_with_currency')

    complaint_state = fields.Function(
        fields.Selection('get_complaint_states', "Complaint State"),
        'on_change_with_complaint_state')
    complaint_origin_id = fields.Function(
        fields.Integer("Complaint Origin ID"),
        'on_change_with_complaint_origin_id')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('action')

    def on_change_with_unit(self, name=None):
        raise NotImplementedError

    @fields.depends('currency', methods=['get_quantity', 'get_unit_price'])
    def on_change_with_amount(self, name=None):
        quantity = self.get_quantity() or 0
        unit_price = self.get_unit_price() or Decimal(0)
        amount = Decimal(str(quantity)) * unit_price
        if self.currency:
            amount = self.currency.round(amount)
        return amount

    def get_quantity(self):
        raise NotImplementedError

    def get_unit_price(self):
        raise NotImplementedError

    @fields.depends('action', '_parent_action.currency')
    def on_change_with_currency(self, name=None):
        return self.action.currency if self.action else None

    @classmethod
    def get_complaint_states(cls):
        pool = Pool()
        Complaint = pool.get('sale.complaint')
        return Complaint.fields_get(['state'])['state']['selection']

    @fields.depends('action', '_parent_action.complaint',
        '_parent_action._parent_complaint.state')
    def on_change_with_complaint_state(self, name=None):
        if self.action and self.action.complaint:
            return self.action.complaint.state

    @fields.depends('action', '_parent_action.complaint',
        '_parent_action._parent_complaint.origin_id')
    def on_change_with_complaint_origin_id(self, name=None):
        if self.action and self.action.complaint:
            return self.action.complaint.origin_id


class Action_SaleLine(_Action_Line, ModelView, ModelSQL):
    __name__ = 'sale.complaint.action-sale.line'

    line = fields.Many2One(
        'sale.line', "Sale Line",
        ondelete='RESTRICT', required=True,
        domain=[
            ('type', '=', 'line'),
            ('sale', '=', Eval('complaint_origin_id', -1)),
            ])

    @fields.depends('line')
    def on_change_with_unit(self, name=None):
        return self.line.unit if self.line else None

    @fields.depends('quantity', 'line')
    def get_quantity(self):
        if self.quantity is not None:
            return self.quantity
        elif self.line:
            if self.line.actual_quantity is not None:
                return self.line.actual_quantity
            else:
                return self.line.quantity

    @fields.depends('unit_price', 'line')
    def get_unit_price(self):
        if self.unit_price is not None:
            return self.unit_price
        elif self.line:
            return self.line.unit_price


class Action_InvoiceLine(_Action_Line, ModelView, ModelSQL):
    __name__ = 'sale.complaint.action-account.invoice.line'

    line = fields.Many2One(
        'account.invoice.line', 'Invoice Line',
        ondelete='RESTRICT', required=True,
        domain=[
            ('type', '=', 'line'),
            ('invoice', '=', Eval('complaint_origin_id', -1)),
            ])

    @fields.depends('line')
    def on_change_with_unit(self, name=None):
        return self.line.unit if self.line else None

    @fields.depends('quantity', 'line')
    def get_quantity(self):
        if self.quantity is not None:
            return self.quantity
        elif self.line:
            return self.line.quantity

    @fields.depends('unit_price', 'line')
    def get_unit_price(self):
        if self.unit_price is not None:
            return self.unit_price
        elif self.line:
            return self.line.unit_price


class Complaint_PromotionCoupon(metaclass=PoolMeta):
    __name__ = 'sale.complaint'

    @classmethod
    def _actions_domains(cls):
        domains = super()._actions_domains()
        for name, domain in domains.items():
            domain.append('promotion_coupon')
        return domains


class Action_PromotionCoupon(metaclass=PoolMeta):
    __name__ = 'sale.complaint.action'

    _promtion_coupon_states = {
        'invisible': Eval('action') != 'promotion_coupon',
        'required': Eval('action') == 'promotion_coupon',
        }

    promotion_coupon = fields.Many2One(
        'sale.promotion.coupon', "Promotion Coupon",
        domain=[
            ('company', '=', Eval('company', -1)),
            ('number_of_use', '=', 1),
            ('per_party', '=', False),
            ],
        states=_promtion_coupon_states)
    promotion_coupon_number = fields.Char(
        "Number", states=_promtion_coupon_states)
    promotion_coupon_duration = fields.TimeDelta(
        "Duration", states=_promtion_coupon_states)

    del _promtion_coupon_states

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.action.selection.append(('promotion_coupon', "Promotion Coupon"))

    @classmethod
    def default_promotion_coupon_duration(cls):
        return dt.timedelta(days=90)

    @classmethod
    def _get_result(cls):
        return super()._get_result() + ['sale.promotion.coupon.number']

    def do_promotion_coupon(self):
        pool = Pool()
        PromotionCouponNumber = pool.get('sale.promotion.coupon.number')
        Date = pool.get('ir.date')

        with Transaction().set_context(company=self.company.id):
            today = Date.today()

        return PromotionCouponNumber(
            number=self.promotion_coupon_number,
            coupon=self.promotion_coupon,
            company=self.company,
            start_date=today,
            end_date=today + self.promotion_coupon_duration,
            )
