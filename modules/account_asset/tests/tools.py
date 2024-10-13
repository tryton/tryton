# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from proteus import Model
from trytond.modules.company.tests.tools import get_company


def add_asset_accounts(accounts, company=None, config=None):
    "Add asset kind to accounts"
    Account = Model.get('account.account', config=config)

    if not company:
        company = get_company(config=config)

    accounts['asset'], = Account.find([
            ('company', '=', company.id),
            ('code', '=', '1.5.3'),
            ], limit=1)
    accounts['depreciation'], = Account.find([
            ('company', '=', company.id),
            ('code', '=', '1.4.1'),
            ], limit=1)
    return accounts
