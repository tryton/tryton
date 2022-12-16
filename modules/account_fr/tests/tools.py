# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from proteus import Model, Wizard

from trytond.modules.company.tests.tools import get_company

__all__ = ['create_chart', 'get_accounts']


def create_chart(company=None, config=None):
    "Create chart of accounts"
    AccountTemplate = Model.get('account.account.template', config=config)
    ModelData = Model.get('ir.model.data')

    if not company:
        company = get_company()
    data, = ModelData.find([
            ('module', '=', 'account_fr'),
            ('fs_id', '=', 'root'),
            ], limit=1)

    account_template = AccountTemplate(data.db_id)

    create_chart = Wizard('account.create_chart')
    create_chart.execute('account')
    create_chart.form.account_template = account_template
    create_chart.form.company = company
    create_chart.execute('create_account')

    accounts = get_accounts(company, config=config)

    create_chart.form.account_receivable = accounts['receivable']
    create_chart.form.account_payable = accounts['payable']
    create_chart.execute('create_properties')
    return create_chart


def get_accounts(company=None, config=None):
    "Return accounts per kind"
    Account = Model.get('account.account', config=config)

    if not company:
        company = get_company()

    accounts = Account.find([
            ('kind', 'in', ['receivable', 'payable', 'revenue', 'expense']),
            ('company', '=', company.id),
            ])
    accounts = {a.kind: a for a in accounts}
    cash, = Account.find([
            ('kind', '=', 'other'),
            ('company', '=', company.id),
            ('code', '=', '5311'),
            ])
    accounts['cash'] = cash
    tax, = Account.find([
            ('kind', '=', 'other'),
            ('company', '=', company.id),
            ('code', '=', '44558'),
            ])
    accounts['tax'] = tax
    return accounts
