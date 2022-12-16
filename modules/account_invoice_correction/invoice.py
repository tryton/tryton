# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

__all__ = ['Invoice', 'InvoiceCorrectStart', 'InvoiceCorrect']


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls._buttons.update({
                'correct': {
                    'invisible': (
                        (Eval('state') != 'posted')
                        | (Eval('type') != 'out')),
                    'depends': ['state', 'type'],
                    },
                })

    @classmethod
    @ModelView.button_action(
        'account_invoice_correction.wizard_invoice_correct')
    def correct(cls, invoices):
        pass


class InvoiceCorrectStart(ModelView):
    "Correct Invoice"
    __name__ = 'account.invoice.correct.start'

    invoice = fields.Many2One('account.invoice', 'Invoice', readonly=True)
    lines = fields.Many2Many('account.invoice.line', None, None,
        'Invoice Lines',
        domain=[
            ('invoice', '=', Eval('invoice')),
            ('type', '=', 'line'),
            ],
        depends=['invoice'])


class InvoiceCorrect(Wizard):
    "Correct Invoice"
    __name__ = 'account.invoice.correct'

    start = StateView('account.invoice.correct.start',
        'account_invoice_correction.correct_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Correct', 'correct', 'tryton-ok', default=True),
            ])
    correct = StateAction('account_invoice.act_invoice_form')

    def default_start(self, fields):
        context = Transaction().context
        return {
            'invoice': context['active_id'],
            'lines': [],
            }

    def do_correct(self, action):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Line = pool.get('account.invoice.line')

        invoice = Invoice(Transaction().context['active_id'])
        correction, = Invoice.copy([invoice], default={
                'lines': [],
                })
        # Copy each line one by one to get negative and positive lines
        # following each other
        for line in self.start.lines:
            Line.copy([line], default={
                    'invoice': correction.id,
                    'quantity': -line.quantity,
                    })
            Line.copy([line], default={
                    'invoice': correction.id,
                    })
        Invoice.update_taxes([correction])
        data = {'res_id': [correction.id]}
        return action, data
