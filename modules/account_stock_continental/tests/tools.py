# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from proteus import Model

from trytond.modules.company.tests.tools import get_company


def add_stock_accounts(accounts, company=None, config=None):
    "Add stock kind to accounts"
    Account = Model.get('account.account', config=config)

    if not company:
        company = get_company()

    stock_accounts = Account.find([
            ('type.stock', '=', True),
            ('company', '=', company.id),
            ])
    for account in stock_accounts:
        name = account.name.lower().replace(' and ', '_').replace(' ', '_')
        accounts[name] = account
    return accounts
