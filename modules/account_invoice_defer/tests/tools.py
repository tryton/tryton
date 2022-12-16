# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from proteus import Model
from proteus.config import get_config

from trytond.modules.company.tests.tools import get_company


def add_deferred_accounts(accounts, company=None, config=None):
    "Add deferred to accounts"
    if not config:
        config = get_config()
    Account = Model.get('account.account', config=config)
    AccountType = Model.get('account.account.type')
    Configuration = Model.get('account.configuration', config=config)

    if not company:
        company = get_company(config=config)

    root, = Account.find([('parent', '=', None)], limit=1)
    asset_type, = AccountType.find([
            ('statement', '=', 'balance'),
            ('name', '=', "Asset"),
            ('company', '=', company.id),
            ], limit=1)
    liability_type, = AccountType.find([
            ('statement', '=', 'balance'),
            ('name', '=', "Liability"),
            ('company', '=', company.id),
            ], limit=1)

    accounts['deferred_revenue'] = Account(
        parent=root,
        name="Deferred Revenue",
        type=asset_type,
        company=company)
    accounts['deferred_revenue'].save()
    accounts['deferred_expense'] = Account(
        parent=root,
        name="Deferred Expense",
        type=liability_type,
        company=company)
    accounts['deferred_expense'].save()

    with config.set_context(company=company.id):
        configuration = Configuration(1)
        configuration.deferred_account_revenue = accounts['deferred_revenue']
        configuration.deferred_account_expense = accounts['deferred_expense']
        configuration.save()
    return accounts
