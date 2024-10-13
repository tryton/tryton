# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from proteus import Model
from trytond.modules.company.tests.tools import get_company


def add_stock_accounts(accounts, company=None, config=None):
    "Add stock kind to accounts"
    Account = Model.get('account.account', config=config)

    if not company:
        company = get_company(config=config)

    accounts['stock'], = Account.find([
            ('company', '=', company.id),
            ('code', '=', '1.3.1'),
            ])
    accounts['stock_expense'], = Account.find([
            ('company', '=', company.id),
            ('code', '=', '5.1.5'),
            ])
    return accounts
