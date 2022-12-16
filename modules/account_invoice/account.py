# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import Pool, PoolMeta

__all__ = ['FiscalYear',
    'Period', 'Move', 'Reconciliation']


class FiscalYear:
    __metaclass__ = PoolMeta
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
        cls._error_messages.update({
                'change_invoice_sequence': ('You can not change '
                    'invoice sequence in fiscal year "%s" because there are '
                    'already posted invoices in this fiscal year.'),
                'different_invoice_sequence': ('Fiscal year "%(first)s" and '
                    '"%(second)s" have the same invoice sequence.'),
                })

    @classmethod
    def validate(cls, years):
        super(FiscalYear, cls).validate(years)
        for year in years:
            year.check_invoice_sequences()

    def check_invoice_sequences(self):
        for sequence in ('out_invoice_sequence', 'in_invoice_sequence',
                'out_credit_note_sequence', 'in_credit_note_sequence'):
            fiscalyears = self.search([
                    (sequence, '=', getattr(self, sequence).id),
                    ('id', '!=', self.id),
                    ])
            if fiscalyears:
                self.raise_user_error('different_invoice_sequence', {
                        'first': self.rec_name,
                        'second': fiscalyears[0].rec_name,
                        })

    @classmethod
    def write(cls, *args):
        Invoice = Pool().get('account.invoice')

        actions = iter(args)
        for fiscalyears, values in zip(actions, actions):
            for sequence in ('out_invoice_sequence', 'in_invoice_sequence',
                    'out_credit_note_sequence', 'in_credit_note_sequence'):
                    if not values.get(sequence):
                        continue
                    for fiscalyear in fiscalyears:
                        if (getattr(fiscalyear, sequence)
                                and (getattr(fiscalyear, sequence).id !=
                                    values[sequence])):
                            if Invoice.search([
                                        ('invoice_date', '>=',
                                            fiscalyear.start_date),
                                        ('invoice_date', '<=',
                                            fiscalyear.end_date),
                                        ('number', '!=', None),
                                        ('type', '=', sequence[:-9]),
                                        ]):
                                cls.raise_user_error('change_invoice_sequence',
                                    (fiscalyear.rec_name,))
        super(FiscalYear, cls).write(*args)


class Period:
    __metaclass__ = PoolMeta
    __name__ = 'account.period'
    out_invoice_sequence = fields.Many2One('ir.sequence.strict',
        'Customer Invoice Sequence',
        domain=[('code', '=', 'account.invoice')],
        context={'code': 'account.invoice'},
        states={
            'invisible': Eval('type') != 'standard',
            },
        depends=['type'])
    in_invoice_sequence = fields.Many2One('ir.sequence.strict',
        'Supplier Invoice Sequence',
        domain=[('code', '=', 'account.invoice')],
        context={'code': 'account.invoice'},
        states={
            'invisible': Eval('type') != 'standard',
            },
        depends=['type'])
    out_credit_note_sequence = fields.Many2One('ir.sequence.strict',
        'Customer Credit Note Sequence',
        domain=[('code', '=', 'account.invoice')],
        context={'code': 'account.invoice'},
        states={
            'invisible': Eval('type') != 'standard',
            },
        depends=['type'])
    in_credit_note_sequence = fields.Many2One('ir.sequence.strict',
        'Supplier Credit Note Sequence',
        domain=[('code', '=', 'account.invoice')],
        context={'code': 'account.invoice'},
        states={
            'invisible': Eval('type') != 'standard',
            },
        depends=['type'])

    @classmethod
    def __setup__(cls):
        super(Period, cls).__setup__()
        cls._error_messages.update({
                'change_invoice_sequence': ('You can not change the invoice '
                    'sequence in period "%s" because there is already an '
                    'invoice posted in this period'),
                'different_invoice_sequence': ('Period "%(first)s" and '
                    '"%(second)s" have the same invoice sequence.'),
                'different_period_fiscalyear_company': ('Period "%(period)s" '
                    'must have the same company as its fiscal year '
                    '(%(fiscalyear)s).'),
                })

    @classmethod
    def validate(cls, periods):
        super(Period, cls).validate(periods)
        for period in periods:
            period.check_invoice_sequences()

    def check_invoice_sequences(self):
        for sequence_name in ('out_invoice_sequence', 'in_invoice_sequence',
                'out_credit_note_sequence', 'in_credit_note_sequence'):
            sequence = getattr(self, sequence_name)
            if not sequence:
                continue
            periods = self.search([
                    (sequence_name, '=', sequence.id),
                    ('fiscalyear', '!=', self.fiscalyear.id),
                    ])
            if periods:
                self.raise_user_error('different_invoice_sequence', {
                        'first': self.rec_name,
                        'second': periods[0].rec_name,
                        })
            if (sequence.company
                    and sequence.company != self.fiscalyear.company):
                self.raise_user_error('different_period_fiscalyear_company', {
                        'period': self.rec_name,
                        'fiscalyear': self.fiscalyear.rec_name,
                        })

    @classmethod
    def create(cls, vlist):
        FiscalYear = Pool().get('account.fiscalyear')
        vlist = [v.copy() for v in vlist]
        for vals in vlist:
            if vals.get('fiscalyear'):
                fiscalyear = FiscalYear(vals['fiscalyear'])
                for sequence in ('out_invoice_sequence', 'in_invoice_sequence',
                        'out_credit_note_sequence', 'in_credit_note_sequence'):
                    if not vals.get(sequence):
                        vals[sequence] = getattr(fiscalyear, sequence).id
        return super(Period, cls).create(vlist)

    @classmethod
    def write(cls, *args):
        Invoice = Pool().get('account.invoice')

        actions = iter(args)
        for periods, values in zip(actions, actions):
            for sequence_name in ('out_invoice_sequence',
                    'in_invoice_sequence', 'out_credit_note_sequence',
                    'in_credit_note_sequence'):
                if not values.get(sequence_name):
                    continue
                for period in periods:
                    sequence = getattr(period, sequence_name)
                    if (sequence and sequence.id != values[sequence_name]):
                        if Invoice.search([
                                    ('invoice_date', '>=', period.start_date),
                                    ('invoice_date', '<=', period.end_date),
                                    ('number', '!=', None),
                                    ('type', '=', sequence_name[:-9]),
                                    ]):
                            cls.raise_user_error('change_invoice_sequence',
                                (period.rec_name,))
        super(Period, cls).write(*args)

    def get_invoice_sequence(self, invoice_type):
        sequence = getattr(self, invoice_type + '_sequence')
        if sequence:
            return sequence
        return getattr(self.fiscalyear, invoice_type + '_sequence')


class Move:
    __metaclass__ = PoolMeta
    __name__ = 'account.move'

    @classmethod
    def _get_origin(cls):
        return super(Move, cls)._get_origin() + ['account.invoice']


class Reconciliation:
    __metaclass__ = PoolMeta
    __name__ = 'account.move.reconciliation'

    @classmethod
    def create(cls, vlist):
        Invoice = Pool().get('account.invoice')
        reconciliations = super(Reconciliation, cls).create(vlist)
        move_ids = set()
        account_ids = set()
        for reconciliation in reconciliations:
            move_ids |= {l.move.id for l in reconciliation.lines}
            account_ids |= {l.account.id for l in reconciliation.lines}
        invoices = Invoice.search([
                ('move', 'in', list(move_ids)),
                ('account', 'in', list(account_ids)),
                ])
        Invoice.process(invoices)
        return reconciliations

    @classmethod
    def delete(cls, reconciliations):
        Invoice = Pool().get('account.invoice')

        move_ids = set(l.move.id for r in reconciliations for l in r.lines)
        invoices = Invoice.search([
                ('move', 'in', list(move_ids)),
                ])
        super(Reconciliation, cls).delete(reconciliations)
        Invoice.process(invoices)
