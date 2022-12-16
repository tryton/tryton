#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval, Not, Equal


class FiscalYear(ModelSQL, ModelView):
    _name = 'account.fiscalyear'
    out_invoice_sequence = fields.Many2One('ir.sequence.strict',
            'Customer Invoice Sequence', required=True,
            domain=[
                ('code', '=', 'account.invoice'),
                ['OR',
                    ('company', '=', Eval('company')),
                    ('company', '=', False),
                ],
            ],
            context={
                'code': 'account.invoice',
                'company': Eval('company'),
            })
    in_invoice_sequence = fields.Many2One('ir.sequence.strict',
            'Supplier Invoice Sequence', required=True,
            domain=[
                ('code', '=', 'account.invoice'),
                ['OR',
                    ('company', '=', Eval('company')),
                    ('company', '=', False),
                ],
            ],
            context={
                'code': 'account.invoice',
                'company': Eval('company'),
            })
    out_credit_note_sequence = fields.Many2One('ir.sequence.strict',
            'Customer Credit Note Sequence', required=True,
            domain=[
                ('code', '=', 'account.invoice'),
                ['OR',
                    ('company', '=', Eval('company')),
                    ('company', '=', False),
                ],
            ],
            context={
                'code': 'account.invoice',
                'company': Eval('company'),
            })
    in_credit_note_sequence = fields.Many2One('ir.sequence.strict',
            'Supplier Credit Note Sequence', required=True,
            domain=[
                ('code', '=', 'account.invoice'),
                ['OR',
                    ('company', '=', Eval('company')),
                    ('company', '=', False),
                ],
            ],
            context={
                'code': 'account.invoice',
                'company': Eval('company'),
            })

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

    def check_invoice_sequences(self, cursor, user, ids):
        for fiscalyear in self.browse(cursor, user, ids):
            for sequence in ('out_invoice_sequence', 'in_invoice_sequence',
                    'out_credit_note_sequence', 'in_credit_note_sequence'):
                if self.search(cursor, user, [
                    (sequence, '=', fiscalyear[sequence].id),
                    ('id', '!=', fiscalyear.id),
                    ]):
                    return False
        return True

    def write(self, cursor, user, ids, vals, context=None):
        invoice_obj = self.pool.get('account.invoice')

        if isinstance(ids, (int, long)):
            ids = [ids]

        for sequence in ('out_invoice_sequence', 'in_invoice_sequence',
                'out_credit_note_sequence', 'in_credit_note_sequence'):
            if vals.get(sequence):
                for fiscalyear in self.browse(cursor, user, ids,
                        context=context):
                    if fiscalyear[sequence] and \
                            fiscalyear[sequence].id != \
                            vals[sequence]:
                        if invoice_obj.search(cursor, user, [
                            ('invoice_date', '>=', fiscalyear.start_date),
                            ('invoice_date', '<=', fiscalyear.end_date),
                            ('number', '!=', False),
                            ('type', '=', sequence[:-9]),
                            ], context=context):
                            self.raise_user_error(cursor,
                                    'change_invoice_sequence', context=context)
        return super(FiscalYear, self).write(cursor, user, ids, vals,
                context=context)

FiscalYear()


class Period(ModelSQL, ModelView):
    _name = 'account.period'
    out_invoice_sequence = fields.Many2One('ir.sequence.strict',
            'Customer Invoice Sequence',
            domain=[('code', '=', 'account.invoice')],
            context={'code': 'account.invoice'},
            states={
                'required': Equal(Eval('type'), 'standard'),
                'invisible': Not(Equal(Eval('type'), 'standard')),
            })
    in_invoice_sequence = fields.Many2One('ir.sequence.strict',
            'Supplier Invoice Sequence',
            domain=[('code', '=', 'account.invoice')],
            context={'code': 'account.invoice'},
            states={
                'required': Equal(Eval('type'), 'standard'),
                'invisible': Not(Equal(Eval('type'), 'standard')),
            })
    out_credit_note_sequence = fields.Many2One('ir.sequence.strict',
            'Customer Credit Note Sequence',
            domain=[('code', '=', 'account.invoice')],
            context={'code': 'account.invoice'},
            states={
                'required': Equal(Eval('type'), 'standard'),
                'invisible': Not(Equal(Eval('type'), 'standard')),
            })
    in_credit_note_sequence = fields.Many2One('ir.sequence.strict',
            'Supplier Credit Note Sequence',
            domain=[('code', '=', 'account.invoice')],
            context={'code': 'account.invoice'},
            states={
                'required': Equal(Eval('type'), 'standard'),
                'invisible': Not(Equal(Eval('type'), 'standard')),
            })

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

    def check_invoice_sequences(self, cursor, user, ids):
        for period in self.browse(cursor, user, ids):
            for sequence in ('out_invoice_sequence', 'in_invoice_sequence',
                    'out_credit_note_sequence', 'in_credit_note_sequence'):
                if self.search(cursor, user, [
                    (sequence, '=', period[sequence].id),
                    ('fiscalyear', '!=', period.fiscalyear.id),
                    ]):
                    return False
                if period[sequence].company \
                        and period[sequence].company.id != \
                        period.fiscalyear.company.id:
                    return False
        return True

    def create(self, cursor, user, vals, context=None):
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        vals = vals.copy()
        if vals.get('fiscalyear'):
            fiscalyear = fiscalyear_obj.browse(cursor, user, vals['fiscalyear'],
                    context=context)
            for sequence in ('out_invoice_sequence', 'in_invoice_sequence',
                    'out_credit_note_sequence', 'in_credit_note_sequence'):
                if not vals.get(sequence):
                    vals[sequence] = fiscalyear[sequence].id
        return super(Period, self).create(cursor, user, vals, context=context)

    def write(self, cursor, user, ids, vals, context=None):
        invoice_obj = self.pool.get('account.invoice')

        if isinstance(ids, (int, long)):
            ids = [ids]

        for sequence in ('out_invoice_sequence', 'in_invoice_sequence',
                'out_credit_note_sequence', 'in_credit_note_sequence'):
            if vals.get(sequence):
                for period in self.browse(cursor, user, ids, context=context):
                    if period[sequence] and \
                            period[sequence].id != \
                            vals[sequence]:
                        if invoice_obj.search(cursor, user, [
                            ('invoice_date', '>=', period.start_date),
                            ('invoice_date', '<=', period.end_date),
                            ('number', '!=', False),
                            ('type', '=', sequence[:-9]),
                            ], context=context):
                            self.raise_user_error(cursor,
                                    'change_invoice_sequence', context=context)
        return super(Period, self).write(cursor, user, ids, vals,
                context=context)

Period()
