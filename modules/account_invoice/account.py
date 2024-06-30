# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import OrderedDict
from itertools import islice

from trytond.i18n import gettext
from trytond.model import (
    MatchMixin, ModelSQL, ModelView, Workflow, fields, sequence_ordered)
from trytond.modules.account.exceptions import ClosePeriodError
from trytond.modules.company.model import CompanyValueMixin
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, Id, If
from trytond.tools import grouped_slice
from trytond.transaction import Transaction

from .exceptions import CancelInvoiceMoveWarning


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'

    default_customer_payment_term = fields.MultiValue(
        fields.Many2One(
            'account.invoice.payment_term', "Default Customer Payment Term"))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in 'default_customer_payment_term':
            return pool.get('account.configuration.default_payment_term')
        return super().multivalue_model(field)


class ConfigurationDefaultPaymentTerm(ModelSQL, CompanyValueMixin):
    "Account Configuration Default Payment Term"
    __name__ = 'account.configuration.default_payment_term'

    default_customer_payment_term = fields.Many2One(
        'account.invoice.payment_term', "Default Customer Payment Term")


class FiscalYear(metaclass=PoolMeta):
    __name__ = 'account.fiscalyear'
    invoice_sequences = fields.One2Many(
        'account.fiscalyear.invoice_sequence', 'fiscalyear',
        "Invoice Sequences",
        domain=[
            ('company', '=', Eval('company', -1)),
            ])

    @staticmethod
    def default_invoice_sequences():
        if Transaction().user == 0:
            return []
        return [{}]


class Period(metaclass=PoolMeta):
    __name__ = 'account.period'

    @classmethod
    @ModelView.button
    @Workflow.transition('closed')
    def close(cls, periods):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        company_ids = list({p.company.id for p in periods})
        invoices = Invoice.search([
                ('company', 'in', company_ids),
                ('state', '=', 'posted'),
                ('move', '=', None),
                ])
        if invoices:
            names = ', '.join(i.rec_name for i in invoices[:5])
            if len(invoices) > 5:
                names += '...'
            raise ClosePeriodError(
                gettext('account_invoice.msg_close_period_non_posted_invoices',
                    invoices=names))
        super().close(periods)


class InvoiceSequence(sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    'Invoice Sequence'
    __name__ = 'account.fiscalyear.invoice_sequence'
    company = fields.Many2One('company.company', "Company", required=True)
    fiscalyear = fields.Many2One(
        'account.fiscalyear', "Fiscal Year", required=True, ondelete='CASCADE',
        domain=[
            ('company', '=', Eval('company', -1)),
            ])
    period = fields.Many2One('account.period', 'Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ('type', '=', 'standard'),
            ])
    in_invoice_sequence = fields.Many2One('ir.sequence.strict',
        'Supplier Invoice Sequence', required=True,
        domain=[
            ('sequence_type', '=',
                Id('account_invoice', 'sequence_type_account_invoice')),
            ('company', '=', Eval('company')),
            ])
    in_credit_note_sequence = fields.Many2One('ir.sequence.strict',
        'Supplier Credit Note Sequence', required=True,
        domain=[
            ('sequence_type', '=',
                Id('account_invoice', 'sequence_type_account_invoice')),
            ('company', '=', Eval('company')),
            ])
    out_invoice_sequence = fields.Many2One('ir.sequence.strict',
        'Customer Invoice Sequence', required=True,
        domain=[
            ('sequence_type', '=',
                Id('account_invoice', 'sequence_type_account_invoice')),
            ('company', '=', Eval('company')),
            ])
    out_credit_note_sequence = fields.Many2One('ir.sequence.strict',
        'Customer Credit Note Sequence', required=True,
        domain=[
            ('sequence_type', '=',
                Id('account_invoice', 'sequence_type_account_invoice')),
            ('company', '=', Eval('company')),
            ])

    @classmethod
    def __setup__(cls):
        super(InvoiceSequence, cls).__setup__()
        cls._order.insert(0, ('fiscalyear', 'ASC'))

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')


class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    @classmethod
    def _get_origin(cls):
        return super(Move, cls)._get_origin() + ['account.invoice']


class MoveLine(metaclass=PoolMeta):
    __name__ = 'account.move.line'

    invoice_payment = fields.Function(fields.Many2One(
            'account.invoice', "Invoice Payment",
            domain=[
                ('account', '=', Eval('account', -1)),
                If(Bool(Eval('party')),
                    ('party', '=', Eval('party')),
                    (),
                    ),
                ],
            states={
                'invisible': Bool(Eval('reconciliation')),
                }),
        'get_invoice_payment',
        setter='set_invoice_payment',
        searcher='search_invoice_payment')
    invoice_payments = fields.Many2Many(
        'account.invoice-account.move.line', 'line', 'invoice',
        "Invoice Payments", readonly=True)

    @classmethod
    def __setup__(cls):
        super(MoveLine, cls).__setup__()
        cls._check_modify_exclude.add('invoice_payment')

    @classmethod
    def _view_reconciliation_muted(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        muted = super()._view_reconciliation_muted()
        muted.add(ModelData.get_id(
            'account_invoice', 'move_line_view_list_to_pay'))
        return muted

    @classmethod
    def _get_origin(cls):
        return super()._get_origin() + [
            'account.invoice.line', 'account.invoice.tax']

    @classmethod
    def copy(cls, lines, default=None):
        default = {} if default is None else default.copy()
        default.setdefault('invoice_payments', None)
        return super().copy(lines, default=default)

    @classmethod
    def get_invoice_payment(cls, lines, name):
        pool = Pool()
        InvoicePaymentLine = pool.get('account.invoice-account.move.line')

        ids = list(map(int, lines))
        result = dict.fromkeys(ids, None)
        for sub_ids in grouped_slice(ids):
            payment_lines = InvoicePaymentLine.search([
                    ('line', 'in', list(sub_ids)),
                    ])
            result.update({p.line.id: p.invoice.id for p in payment_lines})
        return result

    @classmethod
    def set_invoice_payment(cls, lines, name, value):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Invoice.remove_payment_lines(lines)
        if value:
            Invoice.add_payment_lines({Invoice(value): lines})

    @classmethod
    def search_invoice_payment(cls, name, clause):
        nested = clause[0][len(name):]
        return [('invoice_payments' + nested, *clause[1:])]

    @property
    def product(self):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        product = super().product
        if (isinstance(self.origin, InvoiceLine)
                and self.origin.product):
            product = self.origin.product
        return product


def _invoices_to_process(reconciliations):
    pool = Pool()
    Reconciliation = pool.get('account.move.reconciliation')
    Invoice = pool.get('account.invoice')

    move_ids = set()
    others = set()
    for reconciliation in reconciliations:
        for line in reconciliation.lines:
            move_ids.add(line.move.id)
            others.update(line.reconciliations_delegated)

    invoices = set()
    for sub_ids in grouped_slice(move_ids):
        sub_ids = list(sub_ids)
        invoices.update(Invoice.search(['OR',
                    ('move', 'in', sub_ids),
                    ('additional_moves', 'in', sub_ids),
                    ]))
    if others:
        invoices.update(_invoices_to_process(Reconciliation.browse(others)))

    return invoices


class Reconciliation(metaclass=PoolMeta):
    __name__ = 'account.move.reconciliation'

    @classmethod
    def create(cls, vlist):
        Invoice = Pool().get('account.invoice')
        transaction = Transaction()
        context = transaction.context
        reconciliations = super(Reconciliation, cls).create(vlist)
        with transaction.set_context(
                queue_batch=context.get('queue_batch', True)):
            Invoice.__queue__.process(
                list(_invoices_to_process(reconciliations)))
        return reconciliations

    @classmethod
    def delete(cls, reconciliations):
        Invoice = Pool().get('account.invoice')
        transaction = Transaction()
        context = transaction.context
        invoices_to_process = _invoices_to_process(reconciliations)
        super(Reconciliation, cls).delete(reconciliations)
        with transaction.set_context(
                queue_batch=context.get('queue_batch', True)):
            Invoice.__queue__.process(list(invoices_to_process))


class RenewFiscalYear(metaclass=PoolMeta):
    __name__ = 'account.fiscalyear.renew'

    def fiscalyear_defaults(self):
        defaults = super(RenewFiscalYear, self).fiscalyear_defaults()
        defaults['invoice_sequences'] = None
        return defaults

    @property
    def invoice_sequence_fields(self):
        return ['out_invoice_sequence', 'out_credit_note_sequence',
            'in_invoice_sequence', 'in_credit_note_sequence']

    def create_fiscalyear(self):
        pool = Pool()
        Sequence = pool.get('ir.sequence.strict')
        InvoiceSequence = pool.get('account.fiscalyear.invoice_sequence')
        fiscalyear = super(RenewFiscalYear, self).create_fiscalyear()

        def standard_period(period):
            return period.type == 'standard'

        period_mapping = {}
        for previous, new in zip(
                filter(
                    standard_period, self.start.previous_fiscalyear.periods),
                filter(standard_period, fiscalyear.periods)):
            period_mapping[previous] = new.id

        InvoiceSequence.copy(
            self.start.previous_fiscalyear.invoice_sequences,
            default={
                'fiscalyear': fiscalyear.id,
                'period': lambda data: period_mapping.get(data['period']),
                })

        if not self.start.reset_sequences:
            return fiscalyear
        sequences = OrderedDict()
        for invoice_sequence in fiscalyear.invoice_sequences:
            for field in self.invoice_sequence_fields:
                sequence = getattr(invoice_sequence, field, None)
                sequences[sequence.id] = sequence
        copies = Sequence.copy(list(sequences.values()), default={
                'name': lambda data: data['name'].replace(
                    self.start.previous_fiscalyear.name,
                    self.start.name)
                })
        Sequence.write(copies, {
                'number_next': Sequence.default_number_next(),
                })

        mapping = {}
        for previous_id, new_sequence in zip(sequences.keys(), copies):
            mapping[previous_id] = new_sequence.id
        to_write = []
        for new_sequence, old_sequence in zip(
                fiscalyear.invoice_sequences,
                self.start.previous_fiscalyear.invoice_sequences):
            values = {}
            for field in self.invoice_sequence_fields:
                sequence = getattr(old_sequence, field, None)
                values[field] = mapping[sequence.id]
            to_write.extend(([new_sequence], values))
        if to_write:
            InvoiceSequence.write(*to_write)
        return fiscalyear


class RescheduleLines(metaclass=PoolMeta):
    __name__ = 'account.move.line.reschedule'

    @classmethod
    def reschedule_lines(cls, lines, journal, terms):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        move, balance_line = super().reschedule_lines(lines, journal, terms)

        move_ids = list({l.move.id for l in lines})
        invoices = Invoice.search(['OR',
                ('move', 'in', move_ids),
                ('additional_moves', 'in', move_ids),
                ])
        Invoice.write(invoices, {
                'additional_moves': [('add', [move.id])],
                })
        return move, balance_line


class DelegateLines(metaclass=PoolMeta):
    __name__ = 'account.move.line.delegate'

    @classmethod
    def delegate_lines(cls, lines, party, journal, date=None):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        move = super().delegate_lines(lines, party, journal, date=None)

        move_ids = list({l.move.id for l in lines})
        invoices = Invoice.search(['OR',
                ('move', 'in', move_ids),
                ('additional_moves', 'in', move_ids),
                ])
        Invoice.write(invoices, {
                'alternative_payees': [('add', [party.id])],
                'additional_moves': [('add', [move.id])],
                })
        return move


class CancelMoves(metaclass=PoolMeta):
    __name__ = 'account.move.cancel'

    def transition_cancel(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Warning = pool.get('res.user.warning')

        moves_w_invoices = {
            m: m.origin for m in self.records
            if (isinstance(m.origin, Invoice)
                and m.origin.state not in {'paid', 'cancelled'})}
        if moves_w_invoices:
            move_names = ', '.join(m.rec_name
                for m in islice(moves_w_invoices, None, 5))
            invoice_names = ', '.join(i.rec_name
                for i in islice(moves_w_invoices.values(), None, 5))
            if len(moves_w_invoices) > 5:
                move_names += '...'
                invoice_names += '...'
            key = Warning.format('cancel_invoice_move', moves_w_invoices)
            if Warning.check(key):
                raise CancelInvoiceMoveWarning(key,
                    gettext('account_invoice.msg_cancel_invoice_move',
                        moves=move_names, invoices=invoice_names),
                    gettext(
                        'account_invoice.msg_cancel_invoice_move_description'))

        return super().transition_cancel()
