# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import random
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from proteus import Model


def setup(config, modules, company):
    Journal = Model.get('account.statement.journal')
    Statement = Model.get('account.statement')
    AccountJournal = Model.get('account.journal')
    Account = Model.get('account.account')
    Invoice = Model.get('account.invoice')

    cash, = Account.find([
            ('company', '=', company.id),
            ('code', '=', '1.1.1'),
            ])

    account_journal = AccountJournal(name='Bank', type='statement')
    account_journal.save()

    journal = Journal(name='Bank',
        journal=account_journal,
        account=cash,
        validation='balance')
    journal.save()

    invoices = Invoice.find([
            ('state', '=', 'posted'),
            ])
    invoices = random.sample(invoices, len(invoices) * 2 // 3)

    total_amount = Decimal(0)
    statement = Statement(name='001',
        journal=journal,
        start_balance=Decimal(0))
    for i, invoice in enumerate(invoices):
        if not invoice.amount_to_pay:
            continue
        line = statement.lines.new()
        line.number = str(i)
        line.date = invoice.invoice_date + relativedelta(
            days=random.randint(1, 20))
        amount = invoice.amount_to_pay
        if invoice.type in ('in_invoice', 'out_credit_note'):
            amount = - amount
        line.amount = amount
        line.party = invoice.party
        if random.random() < 2. / 3.:
            line.related_to = invoice
        total_amount += line.amount

    statement.end_balance = total_amount
    statement.click('validate_statement')
