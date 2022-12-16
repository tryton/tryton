# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from proteus import Model

from trytond.modules.company.tests.tools import get_company


def add_deposit_accounts(accounts, company=None, config=None):
    'Add deposit to accounts'
    Account = Model.get('account.account', config=config)

    if not company:
        company = get_company()

    accounts['deposit'], = Account.find([
            ('type.deposit', '=', True),
            ('company', '=', company.id),
            ('name', '=', 'Deposit'),
            ])
    return accounts
