#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.pool import Pool


class Journal(ModelSQL, ModelView):
    'Statement Journal'
    _name = 'account.statement.journal'
    _description = __doc__

    name = fields.Char('Name', required=True)
    journal = fields.Many2One('account.journal', 'Journal', required=True,
        domain=[('type', '=', 'statement')])
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    company = fields.Many2One('company.company', 'Company', required=True,
            select=True)

    def default_currency(self):
        if Transaction().context.get('company'):
            company_obj = Pool().get('company.company')
            company = company_obj.browse(Transaction().context['company'])
            return company.currency.id

    def default_company(self):
        return Transaction().context.get('company')

Journal()
