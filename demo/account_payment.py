# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import random

from proteus import Model, Wizard


def setup(config, modules, company):
    Currency = Model.get('currency.currency')
    Journal = Model.get('account.payment.journal')
    Line = Model.get('account.move.line')
    Payment = Model.get('account.payment')

    usd, = Currency.find([('code', '=', 'USD')])
    journal = Journal(name='Manual', currency=usd, company=company,
        process_method='manual')
    journal.save()

    lines = Line.find([
            ('account.type.payable', '=', True),
            ('party', '!=', None),
            ('reconciliation', '=', None),
            ('payment_amount', '!=', 0),
            ])
    lines = random.sample(lines, len(lines) * 2 // 3)
    if not lines:
        return

    pay_line = Wizard('account.move.line.pay', lines)
    pay_line.execute('next_')
    pay_line.form.journal = journal
    pay_line.execute('next_')

    payments = Payment.find([])
    payments = random.sample(payments, len(payments) * 2 // 3)

    for payment in payments:
        payment.click('approve')

    payments = random.sample(payments, len(payments) * 2 // 3)
    i = j = 0
    while i < len(payments):
        j = random.randint(1, 5)
        Wizard('account.payment.process', payments[i:i + j])
        i += j
