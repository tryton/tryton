# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from proteus import Model

from trytond.modules.company.tests.tools import get_company


def add_asset_accounts(accounts, company=None, config=None):
    "Add asset kind to accounts"
    Account = Model.get('account.account', config=config)

    if not company:
        company = get_company()

    expense_accounts = Account.find([
            ('kind', '=', 'expense'),
            ('company', '=', company.id),
            ])
    for account in expense_accounts:
        if account.name == 'Expense':
            accounts['expense'] = account
        elif account.name == 'Assets':
            accounts['asset'] = account
    depreciation, = Account.find([
            ('kind', '=', 'other'),
            ('name', '=', 'Depreciation'),
            ])
    accounts['depreciation'] = depreciation
    return accounts
