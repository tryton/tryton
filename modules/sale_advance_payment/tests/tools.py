# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from datetime import timedelta

from proteus import Model

from trytond.modules.company.tests.tools import get_company


def create_advance_payment_term(
        name, formula, account, block_supply=False, block_shipping=False,
        delay=7, config=None):
    "Create an advance payment term"
    AdvancePaymentTerm = Model.get(
        'sale.advance_payment_term', config=config)

    advance_payment_term = AdvancePaymentTerm(name=name)
    line = advance_payment_term.lines.new()
    line.description = name
    line.account = account
    line.block_supply = block_supply
    line.block_shipping = block_shipping
    line.formula = formula
    line.invoice_delay = timedelta(days=delay)
    return advance_payment_term


def add_advance_payment_accounts(accounts, company=None, config=None):
    "Add advance payment to accounts"
    Account = Model.get('account.account', config=config)

    if not company:
        company = get_company()

    accounts['advance_payment'], = Account.find([
            ('type.unearned_revenue', '=', True),
            ('company', '=', company.id),
            ], limit=1)
    return accounts
