# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from collections import defaultdict

from trytond.i18n import gettext
from trytond.model import ModelSQL, ModelView, Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.pyson import Eval, If, Bool
from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.product import price_digits


class Type(ModelSQL, ModelView):
    'Customer Complaint Type'
    __name__ = 'sale.complaint.type'

    name = fields.Char('Name', required=True)
    origin = fields.Many2One('ir.model', 'Origin', required=True,
        domain=[('model', 'in', ['sale.sale', 'sale.line',
                    'account.invoice', 'account.invoice.line'])])


class Complaint(Workflow, ModelSQL, ModelView):
    'Customer Complaint'
    __name__ = 'sale.complaint'
    _rec_name = 'number'

    _states = {
        'readonly': Eval('state') != 'draft',
        }
    _depends = ['state']

    number = fields.Char('Number', readonly=True, select=True)
    reference = fields.Char('Reference', select=True)
    date = fields.Date('Date', states=_states, depends=_depends)
    customer = fields.Many2One('party.party', 'Customer', required=True,
        states=_states, depends=_depends)
    address = fields.Many2One('party.address', 'Address',
        domain=[('party', '=', Eval('customer'))],
        states=_states, depends=_depends + ['customer'])
    company = fields.Many2One('company.company', 'Company', required=True,
        states=_states, depends=_depends)
    employee = fields.Many2One('company.employee', 'Employee',
        states=_states, depends=_depends)
    type = fields.Many2One('sale.complaint.type', 'Type', required=True,
        states=_states, depends=_depends)
    origin = fields.Reference('Origin', selection='get_origin',
        states={
            'readonly': ((Eval('state') != 'draft')
                | Bool(Eval('actions', [0]))),
            'required': Bool(Eval('origin_model')),
            },
        depends=['state', 'customer', 'origin_model', 'company'])
    origin_id = fields.Function(fields.Integer('Origin ID'),
        'on_change_with_origin_id')
    origin_model = fields.Function(fields.Char('Origin Model'),
        'on_change_with_origin_model')
    description = fields.Text('Description', states=_states, depends=_depends)
    actions = fields.One2Many('sale.complaint.action', 'complaint', 'Actions',
        states={
            'readonly': ((Eval('state') != 'draft')
                | (If(~Eval('origin_id', 0), 0, Eval('origin_id', 0)) <= 0)),
            },
        depends=['state', 'origin_model', 'origin_id'])
    state = fields.Selection([
            ('draft', 'Draft'),
            ('waiting', 'Waiting'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
            ], 'State', readonly=True, required=True)

    @classmethod
    def __setup__(cls):
        super(Complaint, cls).__setup__()
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

        origin_domain = []
        for model, domain in cls._origin_domains().items():
            origin_domain = If(Eval('origin_model') == model,
                domain, origin_domain)
        cls.origin.domain = [origin_domain]

        actions_domains = cls._actions_domains()
        actions_domain = [('action', 'in', actions_domains.pop(None))]
        for model, actions in actions_domains.items():
            actions_domain = If(Eval('origin_model') == model,
                [('action', 'in', actions)], actions_domain)
        cls.actions.domain = [actions_domain]

    @classmethod
    def __register__(cls, module_name):
        table_h = cls.__table_handler__(module_name)

        # Migration from 3.8: rename reference into number
        if (table_h.column_exist('reference')
                and not table_h.column_exist('number')):
            table_h.column_rename('reference', 'number')

        super(Complaint, cls).__register__(module_name)

    @classmethod
    def _origin_domains(cls):
        return {
            'sale.sale': [
                If(Eval('customer'),
                    ('party', '=', Eval('customer')),
                    ()),
                ('company', '=', Eval('company')),
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
                    ('party', '=', Eval('customer')),
                    ()),
                ('company', '=', Eval('company')),
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
            }

    @classmethod
    def _actions_domains(cls):
        return {
            None: [],
            'sale.sale': ['sale_return'],
            'sale.line': ['sale_return'],
            'account.invoice': ['credit_note'],
            'account.invoice.line': ['credit_note'],
            }

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
            return [('', ''), (origin.model, origin.name)]
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
        return [
            ('/tree', 'visual', If(Eval('state') == 'cancelled', 'muted', '')),
            ]

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Configuration = pool.get('sale.configuration')

        config = Configuration(1)
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            if values.get('number') is None:
                values['number'] = Sequence.get_id(
                    config.complaint_sequence.id)
        return super(Complaint, cls).create(vlist)

    @classmethod
    def copy(cls, complaints, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('number', None)
        return super(Complaint, cls).copy(complaints, default=default)

    @classmethod
    def delete(cls, complaints):
        for complaint in complaints:
            if complaint.state != 'draft':
                raise AccessError(
                    gettext('sale_complaint.msg_complaint_delete_draft',
                        complaint=complaint.rec_name))
        super(Complaint, cls).delete(complaints)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, complaints):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, complaints):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('waiting')
    def wait(cls, complaints):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('approved')
    def approve(cls, complaints):
        pool = Pool()
        Configuration = pool.get('sale.configuration')
        config = Configuration(1)
        with Transaction().set_context(
                queue_name='sale',
                queue_scheduled_at=config.sale_process_after):
            cls.__queue__.process(complaints)

    @classmethod
    @ModelView.button
    @Workflow.transition('rejected')
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


class Action(ModelSQL, ModelView):
    'Customer Complaint Action'
    __name__ = 'sale.complaint.action'

    _states = {
        'readonly': ((Eval('complaint_state') != 'draft')
            | Bool(Eval('result'))),
        }
    _depends = ['complaint_state', 'result']
    _line_states = {
        'invisible': ~Eval('_parent_complaint', {}
            ).get('origin_model', 'sale.line').in_(
            ['sale.line', 'account.invoice.line']),
        'readonly': _states['readonly'],
        }
    _line_depends = _depends

    complaint = fields.Many2One('sale.complaint', 'Complaint', required=True,
        states=_states, depends=_depends)
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
        depends=_depends,
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
        depends=_depends,
        help='Leave empty for all lines.')

    quantity = fields.Float('Quantity',
        digits=(16, Eval('unit_digits', 2)),
        states=_line_states, depends=_line_depends + ['unit_digits'],
        help='Leave empty for the same quantity.')
    unit = fields.Function(fields.Many2One('product.uom', 'Unit',
            states=_line_states, depends=_line_depends),
        'on_change_with_unit')
    unit_digits = fields.Function(
        fields.Integer('Unit Digits'), 'on_change_with_unit_digits')
    unit_price = fields.Numeric('Unit Price', digits=price_digits,
        states=_line_states, depends=_line_depends,
        help='Leave empty for the same price.')

    result = fields.Reference('Result', selection='get_result', readonly=True)

    complaint_state = fields.Function(
        fields.Selection('get_complaint_states', "Complaint State"),
        'on_change_with_complaint_state')

    @fields.depends('complaint',
        '_parent_complaint.origin_model', '_parent_complaint.origin')
    def on_change_with_unit(self, name=None):
        if (self.complaint
                and self.complaint.origin_model in {
                    'sale.line', 'account.invoice.line'}):
            return self.complaint.origin.unit.id

    @fields.depends('complaint',
        '_parent_complaint.origin_model', '_parent_complaint.origin')
    def on_change_with_unit_digits(self, name=None):
        if (self.complaint
                and self.complaint.origin_model in {
                    'sale.line', 'account.invoice.line'}):
            return self.complaint.origin.unit.digits

    @classmethod
    def get_complaint_states(cls):
        pool = Pool()
        Complaint = pool.get('sale.complaint')
        return Complaint.fields_get(['state'])['state']['selection']

    @fields.depends('complaint', '_parent_complaint.state')
    def on_change_with_complaint_state(self, name=None):
        if self.complaint:
            return self.complaint.state

    @classmethod
    def _get_result(cls):
        'Return list of Model names for result Reference'
        return ['sale.sale', 'account.invoice']

    @classmethod
    def get_result(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        models = cls._get_result()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]

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
                    line2qty = {l.line.id: l.quantity
                        if l.quantity is not None else l.line.quantity
                        for l in self.sale_lines}
                    line2price = {l.line.id: l.unit_price
                        if l.unit_price is not None else l.line.unit_price
                        for l in self.sale_lines}
                    default['quantity'] = lambda o: line2qty.get(o['id'])
                    default['unit_price'] = lambda o: line2price.get(o['id'])
                else:
                    sale_lines = [l for l in sale.lines if l.type == 'line']
            elif isinstance(self.complaint.origin, Line):
                sale_line = self.complaint.origin
                sale = sale_line.sale
                sale_lines = [sale_line]
                if self.quantity is not None:
                    default['quantity'] = self.quantity
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
            credit_note = invoice._credit()
            credit_lines = []
            for invoice_line in invoice_lines:
                credit_line = invoice_line._credit()
                credit_lines.append(credit_line)
                credit_line.origin = self.complaint
                if invoice_line in line2qty:
                    credit_line.quantity = -line2qty[invoice_line]
                if invoice_line in line2price:
                    credit_line.unit_price = line2price[invoice_line]
            credit_note.lines = credit_lines
            credit_note.taxes = None
            credit_note.save()
            credit_note.update_taxes()
        else:
            return
        return credit_note

    @classmethod
    def delete(cls, actions):
        for action in actions:
            if action.result:
                raise AccessError(
                    gettext('sale_complaint.msg_action_delete_result',
                        action=action.rec_name))
        super(Action, cls).delete(actions)


class _Action_Line:

    _states = {
        'readonly': (
            (Eval('complaint_state') != 'draft')
            | Bool(Eval('_parent_action.result', True))),
        }
    _depends = ['complaint_state']

    action = fields.Many2One('sale.complaint.action', 'Action',
        ondelete='CASCADE', select=True, required=True)
    quantity = fields.Float(
        "Quantity",
        digits=(16, Eval('unit_digits', 2)),
        states=_states,
        depends=_depends + ['unit_digits'])
    unit = fields.Function(
        fields.Many2One('product.uom', "Unit"), 'on_change_with_unit')
    unit_digits = fields.Function(
        fields.Integer("Unit Digits"), 'on_change_with_unit_digits')
    unit_price = fields.Numeric(
        "Unit Price", digits=price_digits, states=_states, depends=_depends,
        help='Leave empty for the same price.')

    complaint_state = fields.Function(
        fields.Selection('get_complaint_states', "Complaint State"),
        'on_change_with_complaint_state')
    complaint_origin_id = fields.Function(
        fields.Integer("Complaint Origin ID"),
        'on_change_with_complaint_origin_id')

    def on_change_with_unit(self, name=None):
        raise NotImplementedError

    def on_change_with_unit_digits(self, name=None):
        raise NotImplementedError

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
    'Customer Complaint Action - Sale Line'
    __name__ = 'sale.complaint.action-sale.line'

    line = fields.Many2One(
        'sale.line', "Sale Line",
        ondelete='RESTRICT', required=True,
        domain=[
            ('type', '=', 'line'),
            ('sale', '=', Eval('complaint_origin_id', -1)),
            ],
        depends=['complaint_origin_id'])

    @fields.depends('line')
    def on_change_with_unit(self, name=None):
        if self.line:
            return self.line.unit.id

    @fields.depends('line')
    def on_change_with_unit_digits(self, name=None):
        if self.line:
            return self.line.unit.digits


class Action_InvoiceLine(_Action_Line, ModelView, ModelSQL):
    'Customer Complaint Action - Invoice Line'
    __name__ = 'sale.complaint.action-account.invoice.line'

    line = fields.Many2One(
        'account.invoice.line', 'Invoice Line',
        ondelete='RESTRICT', required=True,
        domain=[
            ('type', '=', 'line'),
            ('invoice', '=', Eval('complaint_origin_id', -1)),
            ],
        depends=['complaint_origin_id'])

    @fields.depends('line')
    def on_change_with_unit(self, name=None):
        if self.line:
            return self.line.unit.id

    @fields.depends('line')
    def on_change_with_unit_digits(self, name=None):
        if self.line:
            return self.line.unit.digits
