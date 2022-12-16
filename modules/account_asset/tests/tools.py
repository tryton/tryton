# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from proteus import Model

from trytond.modules.company.tests.tools import get_company


def add_asset_accounts(accounts, company=None, config=None):
    "Add asset kind to accounts"
    Account = Model.get('account.account', config=config)

    if not company:
        company = get_company()

    accounts['asset'], = Account.find([
            ('type.fixed_asset', '=', True),
            ('name', '=', "Assets"),
            ('company', '=', company.id),
            ], limit=1)
    accounts['depreciation'], = Account.find([
            ('type.fixed_asset', '=', True),
            ('name', '=', "Depreciation"),
            ('company', '=', company.id),
            ], limit=1)
    return accounts
