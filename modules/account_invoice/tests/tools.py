# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from proteus import Model

__all__ = ['set_fiscalyear_invoice_sequences']


def set_fiscalyear_invoice_sequences(fiscalyear, config=None):
    "Set invoice sequences to fiscalyear"
    SequenceStrict = Model.get('ir.sequence.strict', config=config)
    SequenceType = Model.get('ir.sequence.type', config=config)

    sequence_type, = SequenceType.find([
            ('name', '=', "Invoice"),
            ], limit=1)
    invoice_seq = SequenceStrict(
        name=fiscalyear.name,
        sequence_type=sequence_type,
        company=fiscalyear.company)
    invoice_seq.save()
    seq, = fiscalyear.invoice_sequences
    seq.out_invoice_sequence = invoice_seq
    seq.in_invoice_sequence = invoice_seq
    seq.out_credit_note_sequence = invoice_seq
    seq.in_credit_note_sequence = invoice_seq
    return fiscalyear


def create_payment_term(config=None):
    "Create a direct payment term"
    PaymentTerm = Model.get('account.invoice.payment_term')

    payment_term = PaymentTerm(name='Direct')
    payment_term.lines.new(type='remainder')
    return payment_term
