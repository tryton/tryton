#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import Pool, PoolMeta

__all__ = ['FiscalYear', 'Period', 'Move', 'Reconciliation']
__metaclass__ = PoolMeta


class FiscalYear:
    __name__ = 'account.fiscalyear'
    out_invoice_sequence = fields.Many2One('ir.sequence.strict',
        'Customer Invoice Sequence', required=True,
        domain=[
            ('code', '=', 'account.invoice'),
            ['OR',
                ('company', '=', Eval('company')),
                ('company', '=', None),
                ],
            ],
        context={
            'code': 'account.invoice',
            'company': Eval('company'),
            },
        depends=['company'])
    in_invoice_sequence = fields.Many2One('ir.sequence.strict',
        'Supplier Invoice Sequence', required=True,
        domain=[
            ('code', '=', 'account.invoice'),
            ['OR',
                ('company', '=', Eval('company')),
                ('company', '=', None),
                ],
            ],
        context={
            'code': 'account.invoice',
            'company': Eval('company'),
            },
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
        context={
            'code': 'account.invoice',
            'company': Eval('company'),
            }, depends=['company'])
    in_credit_note_sequence = fields.Many2One('ir.sequence.strict',
        'Supplier Credit Note Sequence', required=True,
        domain=[
            ('code', '=', 'account.invoice'),
            ['OR',
                ('company', '=', Eval('company')),
                ('company', '=', None),
                ],
            ],
        context={
            'code': 'account.invoice',
            'company': Eval('company'),
            }, depends=['company'])

    @classmethod
    def __setup__(cls):
        super(FiscalYear, cls).__setup__()
        cls._constraints += [
            ('check_invoice_sequences', 'different_invoice_sequence'),
            ]
        cls._error_messages.update({
            'change_invoice_sequence': 'You can not change ' \
                    'the invoice sequence if there is already ' \
                    'an invoice opened in the fiscalyear',
            'different_invoice_sequence': 'You must have different ' \
                    'invoice sequences per fiscal year!',
            })

    def check_invoice_sequences(self):
        for sequence in ('out_invoice_sequence', 'in_invoice_sequence',
                'out_credit_note_sequence', 'in_credit_note_sequence'):
            if self.search([
                        (sequence, '=', getattr(self, sequence).id),
                        ('id', '!=', self.id),
                        ]):
                return False
        return True

    @classmethod
    def write(cls, fiscalyears, vals):
        Invoice = Pool().get('account.invoice')

        for sequence in ('out_invoice_sequence', 'in_invoice_sequence',
                'out_credit_note_sequence', 'in_credit_note_sequence'):
            if vals.get(sequence):
                for fiscalyear in fiscalyears:
                    if (getattr(fiscalyear, sequence)
                            and (getattr(fiscalyear, sequence).id !=
                                vals[sequence])):
                        if Invoice.search([
                                    ('invoice_date', '>=',
                                        fiscalyear.start_date),
                                    ('invoice_date', '<=',
                                        fiscalyear.end_date),
                                    ('number', '!=', None),
                                    ('type', '=', sequence[:-9]),
                                    ]):
                            cls.raise_user_error('change_invoice_sequence')
        super(FiscalYear, cls).write(fiscalyears, vals)


class Period:
    __name__ = 'account.period'
    out_invoice_sequence = fields.Many2One('ir.sequence.strict',
        'Customer Invoice Sequence',
        domain=[('code', '=', 'account.invoice')],
        context={'code': 'account.invoice'},
        states={
            'required': Eval('type') == 'standard',
            'invisible': Eval('type') != 'standard',
            },
        depends=['type'])
    in_invoice_sequence = fields.Many2One('ir.sequence.strict',
        'Supplier Invoice Sequence',
        domain=[('code', '=', 'account.invoice')],
        context={'code': 'account.invoice'},
        states={
            'required': Eval('type') == 'standard',
            'invisible': Eval('type') != 'standard',
            },
        depends=['type'])
    out_credit_note_sequence = fields.Many2One('ir.sequence.strict',
        'Customer Credit Note Sequence',
        domain=[('code', '=', 'account.invoice')],
        context={'code': 'account.invoice'},
        states={
            'required': Eval('type') == 'standard',
            'invisible': Eval('type') != 'standard',
            },
        depends=['type'])
    in_credit_note_sequence = fields.Many2One('ir.sequence.strict',
        'Supplier Credit Note Sequence',
        domain=[('code', '=', 'account.invoice')],
        context={'code': 'account.invoice'},
        states={
            'required': Eval('type') == 'standard',
            'invisible': Eval('type') != 'standard',
            },
        depends=['type'])

    @classmethod
    def __setup__(cls):
        super(Period, cls).__setup__()
        cls._constraints += [
            ('check_invoice_sequences', 'check_invoice_sequences'),
            ]
        cls._error_messages.update({
            'change_invoice_sequence': 'You can not change ' \
                    'the invoice sequence if there is already ' \
                    'an invoice opened in the period',
            'check_invoice_sequences': 'You must have different ' \
                    'invoice sequences per fiscal year and ' \
                    'in the same company!',
            })

    def check_invoice_sequences(self):
        for sequence_name in ('out_invoice_sequence', 'in_invoice_sequence',
                'out_credit_note_sequence', 'in_credit_note_sequence'):
            sequence = getattr(self, sequence_name)
            if self.search([
                        (sequence_name, '=', sequence.id),
                        ('fiscalyear', '!=', self.fiscalyear.id),
                        ]):
                return False
            if (sequence.company
                    and sequence.company != self.fiscalyear.company):
                return False
        return True

    @classmethod
    def create(cls, vals):
        FiscalYear = Pool().get('account.fiscalyear')
        vals = vals.copy()
        if vals.get('fiscalyear'):
            fiscalyear = FiscalYear(vals['fiscalyear'])
            for sequence in ('out_invoice_sequence', 'in_invoice_sequence',
                    'out_credit_note_sequence', 'in_credit_note_sequence'):
                if not vals.get(sequence):
                    vals[sequence] = getattr(fiscalyear, sequence).id
        return super(Period, cls).create(vals)

    @classmethod
    def write(cls, periods, vals):
        Invoice = Pool().get('account.invoice')

        for sequence_name in ('out_invoice_sequence', 'in_invoice_sequence',
                'out_credit_note_sequence', 'in_credit_note_sequence'):
            if vals.get(sequence_name):
                for period in periods:
                    sequence = getattr(period, sequence_name)
                    if (sequence and
                            sequence.id != vals[sequence]):
                        if Invoice.search([
                                    ('invoice_date', '>=', period.start_date),
                                    ('invoice_date', '<=', period.end_date),
                                    ('number', '!=', None),
                                    ('type', '=', sequence_name[:-9]),
                                    ]):
                            cls.raise_user_error('change_invoice_sequence')
        super(Period, cls).write(periods, vals)


class Move:
    __name__ = 'account.move'

    @classmethod
    def _get_origin(cls):
        return super(Move, cls)._get_origin() + ['account.invoice']


class Reconciliation:
    __name__ = 'account.move.reconciliation'

    @classmethod
    def create(cls, values):
        Invoice = Pool().get('account.invoice')
        reconciliation = super(Reconciliation, cls).create(values)
        move_ids = set(l.move.id for l in reconciliation.lines)
        invoices = Invoice.search([
                ('move', 'in', list(move_ids)),
                ])
        Invoice.process(invoices)
        return reconciliation

    @classmethod
    def delete(cls, reconciliations):
        Invoice = Pool().get('account.invoice')

        move_ids = set(l.move.id for r in reconciliations for l in r.lines)
        invoices = Invoice.search([
                ('move', 'in', list(move_ids)),
                ])
        super(Reconciliation, cls).delete(reconciliations)
        Invoice.process(invoices)
