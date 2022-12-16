# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import OrderedDict

from sql import Literal
from sql.conditionals import Coalesce

from trytond.model import (fields, ModelView, ModelSQL, MatchMixin,
    sequence_ordered)
from trytond.pyson import Eval, If, Bool
from trytond.pool import Pool, PoolMeta
from trytond.tools import grouped_slice
from trytond.transaction import Transaction


class FiscalYear(metaclass=PoolMeta):
    __name__ = 'account.fiscalyear'
    invoice_sequences = fields.One2Many(
        'account.fiscalyear.invoice_sequence', 'fiscalyear',
        "Invoice Sequences",
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Sequence = pool.get('account.fiscalyear.invoice_sequence')
        sequence = Sequence.__table__()
        sql_table = cls.__table__()

        super(FiscalYear, cls).__register__(module_name)
        cursor = Transaction().connection.cursor()
        table = cls.__table_handler__(module_name)

        # Migration from 4.2: Use Match pattern for sequences
        if (table.column_exist('in_invoice_sequence')
                and table.column_exist('in_credit_note_sequence')
                and table.column_exist('out_invoice_sequence')
                and table.column_exist('out_credit_note_sequence')):
            cursor.execute(*sequence.insert(columns=[
                        sequence.sequence, sequence.fiscalyear,
                        sequence.company,
                        sequence.out_invoice_sequence,
                        sequence.out_credit_note_sequence,
                        sequence.in_invoice_sequence,
                        sequence.in_credit_note_sequence],
                    values=sql_table.select(
                        Literal(20), sql_table.id,
                        sql_table.company,
                        sql_table.out_invoice_sequence,
                        sql_table.out_credit_note_sequence,
                        sql_table.in_invoice_sequence,
                        sql_table.in_credit_note_sequence)))
            table.drop_column('out_invoice_sequence')
            table.drop_column('out_credit_note_sequence')
            table.drop_column('in_invoice_sequence')
            table.drop_column('in_credit_note_sequence')

    @staticmethod
    def default_invoice_sequences():
        if Transaction().user == 0:
            return []
        return [{}]


class Period(metaclass=PoolMeta):
    __name__ = 'account.period'

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Sequence = pool.get('account.fiscalyear.invoice_sequence')
        FiscalYear = pool.get('account.fiscalyear')
        sequence = Sequence.__table__()
        fiscalyear = FiscalYear.__table__()
        sql_table = cls.__table__()

        super(Period, cls).__register__(module_name)
        cursor = Transaction().connection.cursor()
        table = cls.__table_handler__(module_name)

        # Migration from 4.2: Use Match pattern for sequences
        if (table.column_exist('in_invoice_sequence')
                and table.column_exist('in_credit_note_sequence')
                and table.column_exist('out_invoice_sequence')
                and table.column_exist('out_credit_note_sequence')):
            cursor.execute(*sequence.insert(columns=[
                        sequence.sequence, sequence.fiscalyear,
                        sequence.company, sequence.period,
                        sequence.out_invoice_sequence,
                        sequence.out_credit_note_sequence,
                        sequence.in_invoice_sequence,
                        sequence.in_credit_note_sequence],
                    values=sql_table.join(fiscalyear,
                            condition=(fiscalyear.id == sql_table.fiscalyear)
                        ).select(
                        Literal(10), sql_table.fiscalyear,
                        fiscalyear.company, sql_table.id,
                        Coalesce(sql_table.out_invoice_sequence,
                            fiscalyear.out_invoice_sequence),
                        Coalesce(sql_table.out_credit_note_sequence,
                            fiscalyear.out_credit_note_sequence),
                        Coalesce(sql_table.in_invoice_sequence,
                            fiscalyear.in_invoice_sequence),
                        Coalesce(sql_table.in_credit_note_sequence,
                            fiscalyear.in_credit_note_sequence))))
            table.drop_column('out_invoice_sequence')
            table.drop_column('out_credit_note_sequence')
            table.drop_column('in_invoice_sequence')
            table.drop_column('in_credit_note_sequence')


class InvoiceSequence(sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    'Invoice Sequence'
    __name__ = 'account.fiscalyear.invoice_sequence'
    company = fields.Many2One('company.company', "Company", required=True)
    fiscalyear = fields.Many2One(
        'account.fiscalyear', "Fiscal Year", required=True, ondelete='CASCADE',
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    period = fields.Many2One('account.period', 'Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ('type', '=', 'standard'),
            ],
        depends=['fiscalyear'])
    in_invoice_sequence = fields.Many2One('ir.sequence.strict',
        'Supplier Invoice Sequence', required=True,
        domain=[
            ('code', '=', 'account.invoice'),
            ['OR',
                ('company', '=', Eval('company')),
                ('company', '=', None),
                ],
            ],
        depends=['company'])
    in_credit_note_sequence = fields.Many2One('ir.sequence.strict',
        'Supplier Credit Note Sequence', required=True,
        domain=[
            ('code', '=', 'account.invoice'),
            ['OR',
                ('company', '=', Eval('company')),
                ('company', '=', None),
                ],
            ],
        depends=['company'])
    out_invoice_sequence = fields.Many2One('ir.sequence.strict',
        'Customer Invoice Sequence', required=True,
        domain=[
            ('code', '=', 'account.invoice'),
            ['OR',
                ('company', '=', Eval('company')),
                ('company', '=', None),
                ],
            ],
        depends=['company'])
    out_credit_note_sequence = fields.Many2One('ir.sequence.strict',
        'Customer Credit Note Sequence', required=True,
        domain=[
            ('code', '=', 'account.invoice'),
            ['OR',
                ('company', '=', Eval('company')),
                ('company', '=', None),
                ],
            ],
        depends=['company'])

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
                },
            depends=['account', 'party', 'reconciliation']),
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
    def _get_origin(cls):
        return super()._get_origin() + [
            'account.invoice.line', 'account.invoice.tax']

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
    def search_invoice_payment(cls, name, domain):
        return [('invoice_payments',) + tuple(domain[1:])]

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
        invoices.update(Invoice.search([
                    ('move', 'in', list(sub_ids)),
                    ]))
    if others:
        invoices.update(_invoices_to_process(Reconciliation.browse(others)))

    return invoices


class Reconciliation(metaclass=PoolMeta):
    __name__ = 'account.move.reconciliation'

    @classmethod
    def create(cls, vlist):
        Invoice = Pool().get('account.invoice')
        reconciliations = super(Reconciliation, cls).create(vlist)
        Invoice.process(list(_invoices_to_process(reconciliations)))
        return reconciliations

    @classmethod
    def delete(cls, reconciliations):
        Invoice = Pool().get('account.invoice')

        invoices_to_process = _invoices_to_process(reconciliations)
        super(Reconciliation, cls).delete(reconciliations)
        Invoice.process(list(invoices_to_process))


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
                'next_number': 1,
                'name': lambda data: data['name'].replace(
                    self.start.previous_fiscalyear.name,
                    self.start.name)
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
