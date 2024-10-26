# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt
import random
from itertools import chain

from dateutil.relativedelta import relativedelta

from proteus import Model

from .tools import skip_warning


def setup(config, modules, company):
    Party = Model.get('party.party')
    PaymentTerm = Model.get('account.invoice.payment_term')
    PaymentMethod = Model.get('account.invoice.payment.method')
    Journal = Model.get('account.journal')
    Account = Model.get('account.account')

    payment_term = PaymentTerm(name='30 days')
    line = payment_term.lines.new()
    line.type = 'remainder'
    delta = line.relativedeltas.new()
    delta.days = 30
    payment_term.save()

    parties = Party.find()
    Party.write([p.id for p in parties], {
            'customer_payment_term': payment_term.id,
            'supplier_payment_term': payment_term.id,
            }, config.context)

    cash_account, = Account.find([
            ('company', '=', company.id),
            ('code', '=', '1.1.1'),
            ], limit=1)

    payment_method = PaymentMethod()
    payment_method.name = "Cash"
    payment_method.journal, = Journal.find([('type', '=', 'cash')], limit=1)
    payment_method.credit_account = cash_account
    payment_method.debit_account = cash_account
    payment_method.save()


def setup_post(config, modules, company):
    Invoice = Model.get('account.invoice')

    invoices = Invoice.find([
            ('type', '=', 'out'),
            ('state', 'in', ['draft', 'validated']),
            ])
    invoices = random.sample(invoices, len(invoices) * 2 // 3)
    invoices = list(chain(*list(zip(invoices,
                Invoice.find([
                        ('type', '=', 'in'),
                        ('state', 'in', ['draft', 'validated']),
                        ])))))

    today = dt.date.today()
    invoice_date = today + relativedelta(months=-1)
    i = j = 0
    while invoice_date <= today:
        j = random.randint(1, 5)
        for invoice in invoices[i:i + j]:
            invoice.invoice_date = invoice_date
            invoice.save()
        i += j
        invoice_date += relativedelta(days=random.randint(1, 3))
    invoices = [inv for inv in invoices[0:i]]
    for invoice in invoices:
        skip_warning(config, 'invoice_payment_term', [invoice])
    skip_warning(config, 'invoice_date_future', invoices)
    Invoice.click(invoices, 'post')
