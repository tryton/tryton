# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from proteus import Model

__all__ = ['set_fiscalyear_invoice_sequences']


def set_fiscalyear_invoice_sequences(fiscalyear, config=None):
    "Set invoice sequences to fiscalyear"
    SequenceStrict = Model.get('ir.sequence.strict', config=config)

    invoice_seq = SequenceStrict(name=fiscalyear.name, code='account.invoice',
        company=fiscalyear.company)
    invoice_seq.save()
    fiscalyear.out_invoice_sequence = invoice_seq
    fiscalyear.in_invoice_sequence = invoice_seq
    fiscalyear.out_credit_note_sequence = invoice_seq
    fiscalyear.in_credit_note_sequence = invoice_seq
    return fiscalyear


def create_payment_term(config=None):
    "Create a direct payment term"
    PaymentTerm = Model.get('account.invoice.payment_term')

    payment_term = PaymentTerm(name='Direct')
    payment_term.lines.new(type='remainder')
    return payment_term
