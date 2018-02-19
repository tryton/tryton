# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from __future__ import unicode_literals
from collections import defaultdict

from trytond.model import ModelSQL, ModelView, Workflow, fields
from trytond.pyson import Eval, If, Bool
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond import backend

from trytond.modules.product import price_digits

__all__ = ['Type', 'Complaint', 'Action',
    'Action_SaleLine', 'Action_InvoiceLine']


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
        cls._error_messages.update({
                'delete_draft': ('Complaint "%s" must be in draft '
                    'to be deleted.'),
                })
        cls._transitions |= set((
                ('draft', 'waiting'),
                ('waiting', 'draft'),
                ('waiting', 'approved'),
                ('waiting', 'rejected'),
                ('approved', 'done'),
                ('draft', 'cancelled'),
                ('waiting', 'cancelled'),
                ('done', 'draft'),
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
                        'tryton-clear', 'tryton-go-previous'),
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
        for model, domain in cls._origin_domains().iteritems():
            origin_domain = If(Eval('origin_model') == model,
                domain, origin_domain)
        cls.origin.domain = [origin_domain]

        actions_domains = cls._actions_domains()
        actions_domain = [('action', 'in', actions_domains.pop(None))]
        for model, actions in actions_domains.iteritems():
            actions_domain = If(Eval('origin_model') == model,
                [('action', 'in', actions)], actions_domain)
        cls.actions.domain = [actions_domain]

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        table_h = TableHandler(cls, module_name)

        # Migration from 3.8: rename reference into number
        if (table_h.column_exist('reference')
                and not table_h.column_exist('number')):
            table_h.column_rename('reference', 'number')

        super(Complaint, cls).__register__(module_name)

    @classmethod
    def _origin_domains(cls):
        return {
            'sale.sale': [
                ('party', '=', Eval('customer')),
                ('company', '=', Eval('company')),
                ('state', 'in', ['confirmed', 'processing', 'done']),
                ],
            'sale.line': [
                ('sale.party', '=', Eval('customer')),
                ('sale.company', '=', Eval('company')),
                ('sale.state', 'in', ['confirmed', 'processing', 'done']),
                ],
            'account.invoice': [
                ('party', '=', Eval('customer')),
                ('company', '=', Eval('company')),
                ('type', '=', 'out'),
                ('state', 'in', ['posted', 'paid']),
                ],
            'account.invoice.line': [
                ('invoice.party', '=', Eval('customer')),
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

    @fields.depends('origin')
    def on_change_with_origin_id(self, name=None):
        if self.origin:
            return self.origin.id

    @fields.depends('origin')
    def on_change_with_origin_model(self, name=None):
        if self.origin:
            return self.origin.__class__.__name__

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
        default = default.copy()
        default['number'] = None
        return super(Complaint, cls).copy(complaints, default=default)

    @classmethod
    def delete(cls, complaints):
        for complaint in complaints:
            if complaint.state != 'draft':
                cls.raise_user_error('delete_draft', complaint.rec_name)
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
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('rejected')
    def reject(cls, complaints):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def process(cls, complaints):
        results = defaultdict(list)
        actions = defaultdict(list)
        for complaint in complaints:
            for action in complaint.actions:
                if action.result:
                    continue
                result = action.do()
                results[result.__class__].append(result)
                actions[result.__class__].append(action)
        for kls, records in results.iteritems():
            kls.save(records)
            for action, record in zip(actions[kls], records):
                action.result = record
        Action.save(sum(actions.values(), []))


class Action(ModelSQL, ModelView):
    'Customer Complaint Action'
    __name__ = 'sale.complaint.action'

    _states = {
        'readonly': Bool(Eval('result')),
        }
    _depends = ['result']
    _line_states = {
        'invisible': Eval('_parent_complaint', {}
            ).get('origin_model', 'sale.line') != 'sale.line',
        'readonly': _states['readonly'],
        }
    _line_depends = _depends

    complaint = fields.Many2One('sale.complaint', 'Complaint', required=True,
        states=_states, depends=_depends)
    action = fields.Selection([
            ('sale_return', 'Create Sale Return'),
            ('credit_note', 'Create Credit Note'),
            ], 'Action')

    sale_lines = fields.Many2Many('sale.complaint.action-sale.line',
        'action', 'line', 'Sale Lines',
        domain=[('sale', '=', Eval('_parent_complaint', {}).get('origin_id'))],
        states={
            'invisible': Eval('_parent_complaint', {}
                ).get('origin_model', 'sale.sale') != 'sale.sale',
            'readonly': _states['readonly'],
            },
        depends=_depends,
        help='Leave empty for all lines')

    invoice_lines = fields.Many2Many(
        'sale.complaint.action-account.invoice.line', 'action', 'line',
        'Invoice Lines',
        domain=[('invoice', '=', Eval('_parent_complaint', {}
                    ).get('origin_id'))],
        states={
            'invisible': Eval('_parent_complaint', {}
                ).get('origin_model', 'account.invoice.line'
                ) != 'account.invoice',
            'readonly': _states['readonly'],
            },
        depends=_depends,
        help='Leave empty for all lines')

    quantity = fields.Float('Quantity',
        digits=(16, Eval('unit_digits', 2)),
        states=_line_states, depends=_line_depends + ['unit_digits'],
        help='Leave empty for the same quantity')
    unit = fields.Function(fields.Many2One('product.uom', 'Unit',
            states=_line_states, depends=_line_depends),
        'on_change_with_unit')
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'get_unit_digits')
    unit_price = fields.Numeric('Unit Price', digits=price_digits,
        states=_line_states, depends=_line_depends,
        help='Leave empty for the same price')

    result = fields.Reference('Result', selection='get_result', readonly=True)

    @classmethod
    def __setup__(cls):
        super(Action, cls).__setup__()
        cls._error_messages.update({
                'delete_result': ('Action "%s" must not have result '
                    'to be deleted.'),
                })

    @fields.depends('complaint')
    def on_change_with_unit(self, name=None):
        if self.complaint and self.complaint.origin_model == 'sale.line':
            return self.complaint.origin.unit.id

    @fields.depends('complaint')
    def get_unit_digits(self, name=None):
        if self.complaint.origin_model == 'sale.line':
            return self.complaint.origin.unit.digits
        return 2

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
                sale_lines = self.sale_lines or sale.lines
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
            if isinstance(self.complaint.origin, Invoice):
                invoice = self.complaint.origin
                invoice_lines = self.invoice_lines or invoice.lines
            elif isinstance(self.complaint.origin, Line):
                invoice_line = self.complaint.origin
                invoice = invoice_line.invoice
                invoice_lines = [invoice_line]
            credit_note = invoice._credit()
            credit_lines = []
            for invoice_line in invoice_lines:
                credit_line = invoice_line._credit()
                credit_lines.append(credit_line)
                # Remove product as it is not a return
                credit_line.product = None
                credit_line.origin = self.complaint
            if isinstance(self.complaint.origin, Line):
                if self.quantity is not None:
                    credit_lines[0].quantity = -self.quantity
                if self.unit_price is not None:
                    credit_lines[0].unit_price = self.unit_price
            credit_note.lines = credit_lines
            credit_note.taxes = None
            credit_note.save()
            Invoice.update_taxes([credit_note])
        else:
            return
        return credit_note

    @classmethod
    def delete(cls, actions):
        for action in actions:
            if action.result:
                cls.raise_user_error('delete_result', action.rec_name)
        super(Action, cls).delete(actions)


class Action_SaleLine(ModelSQL):
    'Customer Complaint Action - Sale Line'
    __name__ = 'sale.complaint.action-sale.line'

    action = fields.Many2One('sale.complaint.action', 'Action',
        ondelete='CASCADE', select=True, required=True)
    line = fields.Many2One('sale.line', 'Sale Line', ondelete='RESTRICT',
        required=True)


class Action_InvoiceLine(ModelSQL):
    'Customer Complaint Action - Invoice Line'
    __name__ = 'sale.complaint.action-account.invoice.line'

    action = fields.Many2One('sale.complaint.action', 'Action',
        ondelete='CASCADE', select=True, required=True)
    line = fields.Many2One('account.invoice.line', 'Invoice Line',
        ondelete='RESTRICT', required=True)
