# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from dateutil.relativedelta import relativedelta

from proteus import Model, Wizard
from trytond.modules.company.tests.tools import get_company

__all__ = ['create_fiscalyear', 'create_chart', 'get_accounts',
    'create_tax', 'create_tax_code']


def create_fiscalyear(company=None, today=None, config=None):
    "Create a fiscal year for the company on today or range"
    FiscalYear = Model.get('account.fiscalyear', config=config)
    Sequence = Model.get('ir.sequence', config=config)
    SequenceType = Model.get('ir.sequence.type', config=config)

    if not company:
        company = get_company(config=config)

    if not today:
        today = datetime.date.today()
    if isinstance(today, datetime.date):
        start_date = end_date = today
    else:
        start_date, end_date = today
        today = start_date + (end_date - start_date) / 2
    start_date = min(start_date, today - relativedelta(months=6, day=1))
    end_date = max(end_date, today + relativedelta(months=5, day=31))
    assert start_date <= end_date

    fiscalyear = FiscalYear(name=str(today.year))
    fiscalyear.start_date = start_date
    fiscalyear.end_date = end_date
    fiscalyear.company = company

    sequence_type, = SequenceType.find(
        [('name', '=', "Account Move")], limit=1)
    post_move_sequence = Sequence(
        name=str(today.year),
        sequence_type=sequence_type,
        company=company)
    post_move_sequence.save()
    fiscalyear.post_move_sequence = post_move_sequence
    return fiscalyear


def create_chart(
        company=None, chart='account.account_template_root_en', config=None):
    "Create chart of accounts"
    AccountTemplate = Model.get('account.account.template', config=config)
    ModelData = Model.get('ir.model.data', config=config)

    if not company:
        company = get_company(config=config)

    module, xml_id = chart.split('.')
    data, = ModelData.find([
            ('module', '=', module),
            ('fs_id', '=', xml_id),
            ], limit=1)

    account_template = AccountTemplate(data.db_id)

    create_chart = Wizard('account.create_chart', config=config)
    create_chart.execute('account')
    create_chart.form.account_template = account_template
    create_chart.form.company = company
    create_chart.execute('create_account')

    accounts = get_accounts(company, config=config)

    if accounts['receivable'].party_required:
        create_chart.form.account_receivable = accounts['receivable']
    if accounts['payable'].party_required:
        create_chart.form.account_payable = accounts['payable']
    create_chart.execute('create_properties')
    return create_chart


def get_accounts(company=None, config=None):
    "Return accounts per kind"
    Account = Model.get('account.account', config=config)

    if not company:
        company = get_company(config=config)

    accounts = {}
    for type in ['receivable', 'payable', 'revenue', 'expense']:
        try:
            accounts[type], = Account.find([
                    ('type.%s' % type, '=', True),
                    ('company', '=', company.id),
                    ('closed', '!=', True),
                    ], limit=1)
        except ValueError:
            pass
    try:
        accounts['cash'], = Account.find([
                ('company', '=', company.id),
                ('name', '=', 'Main Cash'),
                ('closed', '!=', True),
                ], limit=1)
    except ValueError:
        pass
    try:
        accounts['tax'], = Account.find([
                ('company', '=', company.id),
                ('name', '=', 'Main Tax'),
                ('closed', '!=', True),
                ], limit=1)
    except ValueError:
        pass
    return accounts


def create_tax(rate, company=None, config=None):
    "Create a tax of rate"
    Tax = Model.get('account.tax', config=config)

    if not company:
        company = get_company(config=config)

    accounts = get_accounts(company, config=config)

    tax = Tax()
    tax.name = 'Tax %s' % rate
    tax.description = tax.name
    tax.type = 'percentage'
    tax.rate = rate
    tax.invoice_account = accounts['tax']
    tax.credit_note_account = accounts['tax']
    return tax


def create_tax_code(
        tax, amount='tax', type='invoice', operator='+', config=None):
    "Create a tax code for the tax"
    TaxCode = Model.get('account.tax.code', config=config)

    tax_code = TaxCode(name="Tax Code %s" % tax.name)
    tax_code.company = tax.company
    line = tax_code.lines.new()
    line.operator = '+'
    line.tax = tax
    line.amount = amount
    line.type = type
    return tax_code
