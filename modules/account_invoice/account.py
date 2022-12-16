#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import Model, ModelView, ModelSQL, fields
from trytond.pyson import Eval
from trytond.pool import Pool


class FiscalYear(ModelSQL, ModelView):
    _name = 'account.fiscalyear'
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

    def __init__(self):
        super(FiscalYear, self).__init__()
        self._constraints += [
            ('check_invoice_sequences', 'different_invoice_sequence'),
        ]
        self._error_messages.update({
            'change_invoice_sequence': 'You can not change ' \
                    'the invoice sequence if there is already ' \
                    'an invoice opened in the fiscalyear',
            'different_invoice_sequence': 'You must have different ' \
                    'invoice sequences per fiscal year!',
            })

    def check_invoice_sequences(self, ids):
        for fiscalyear in self.browse(ids):
            for sequence in ('out_invoice_sequence', 'in_invoice_sequence',
                    'out_credit_note_sequence', 'in_credit_note_sequence'):
                if self.search([
                    (sequence, '=', fiscalyear[sequence].id),
                    ('id', '!=', fiscalyear.id),
                    ]):
                    return False
        return True

    def write(self, ids, vals):
        invoice_obj = Pool().get('account.invoice')

        if isinstance(ids, (int, long)):
            ids = [ids]

        for sequence in ('out_invoice_sequence', 'in_invoice_sequence',
                'out_credit_note_sequence', 'in_credit_note_sequence'):
            if vals.get(sequence):
                for fiscalyear in self.browse(ids):
                    if fiscalyear[sequence] and \
                            fiscalyear[sequence].id != \
                            vals[sequence]:
                        if invoice_obj.search([
                            ('invoice_date', '>=', fiscalyear.start_date),
                            ('invoice_date', '<=', fiscalyear.end_date),
                            ('number', '!=', None),
                            ('type', '=', sequence[:-9]),
                            ]):
                            self.raise_user_error('change_invoice_sequence')
        return super(FiscalYear, self).write(ids, vals)

FiscalYear()


class Period(ModelSQL, ModelView):
    _name = 'account.period'
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

    def __init__(self):
        super(Period, self).__init__()
        self._constraints += [
            ('check_invoice_sequences', 'check_invoice_sequences'),
        ]
        self._error_messages.update({
            'change_invoice_sequence': 'You can not change ' \
                    'the invoice sequence if there is already ' \
                    'an invoice opened in the period',
            'check_invoice_sequences': 'You must have different ' \
                    'invoice sequences per fiscal year and ' \
                    'in the same company!',
            })

    def check_invoice_sequences(self, ids):
        for period in self.browse(ids):
            for sequence in ('out_invoice_sequence', 'in_invoice_sequence',
                    'out_credit_note_sequence', 'in_credit_note_sequence'):
                if self.search([
                    (sequence, '=', period[sequence].id),
                    ('fiscalyear', '!=', period.fiscalyear.id),
                    ]):
                    return False
                if period[sequence].company \
                        and period[sequence].company.id != \
                        period.fiscalyear.company.id:
                    return False
        return True

    def create(self, vals):
        fiscalyear_obj = Pool().get('account.fiscalyear')
        vals = vals.copy()
        if vals.get('fiscalyear'):
            fiscalyear = fiscalyear_obj.browse(vals['fiscalyear'])
            for sequence in ('out_invoice_sequence', 'in_invoice_sequence',
                    'out_credit_note_sequence', 'in_credit_note_sequence'):
                if not vals.get(sequence):
                    vals[sequence] = fiscalyear[sequence].id
        return super(Period, self).create(vals)

    def write(self, ids, vals):
        invoice_obj = Pool().get('account.invoice')

        if isinstance(ids, (int, long)):
            ids = [ids]

        for sequence in ('out_invoice_sequence', 'in_invoice_sequence',
                'out_credit_note_sequence', 'in_credit_note_sequence'):
            if vals.get(sequence):
                for period in self.browse(ids):
                    if period[sequence] and \
                            period[sequence].id != \
                            vals[sequence]:
                        if invoice_obj.search([
                            ('invoice_date', '>=', period.start_date),
                            ('invoice_date', '<=', period.end_date),
                            ('number', '!=', None),
                            ('type', '=', sequence[:-9]),
                            ]):
                            self.raise_user_error('change_invoice_sequence')
        return super(Period, self).write(ids, vals)

Period()


class Reconciliation(Model):
    _name = 'account.move.reconciliation'

    def create(self, values):
        pool = Pool()
        invoice_obj = pool.get('account.invoice')

        result = super(Reconciliation, self).create(values)
        reconciliation = self.browse(result)
        move_ids = set(l.move.id for l in reconciliation.lines)
        invoice_ids = invoice_obj.search([
                ('move', 'in', list(move_ids)),
                ])
        invoice_obj.process(invoice_ids)
        return result

    def delete(self, ids):
        pool = Pool()
        invoice_obj = pool.get('account.invoice')

        if isinstance(ids, (int, long)):
            ids = [ids]
        reconciliations = self.browse(ids)
        move_ids = set(l.move.id for r in reconciliations for l in r.lines)
        invoice_ids = invoice_obj.search([
                ('move', 'in', list(move_ids)),
                ])
        result = super(Reconciliation, self).delete(ids)
        invoice_obj.process(invoice_ids)
        return result

Reconciliation()
