#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Statement Journal"
from trytond.model import ModelView, ModelSQL, fields


class Journal(ModelSQL, ModelView):
    'Statement Journal'
    _name = 'account.statement.journal'
    _description = __doc__

    name = fields.Char('Name', required=True)
    journal = fields.Many2One('account.journal', 'Journal', required=True,
        domain=[('type', '=', 'statement')])
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    company = fields.Many2One('company.company', 'Company', required=True)

    def default_currency(self, cursor, user, context=None):
        if context and context.get('company'):
            company_obj = self.pool.get('company.company')
            currency_obj = self.pool.get('currency.currency')
            company = company_obj.browse(cursor, user, context['company'],
                    context=context)
            return company.currency.id
        return False

    def default_company(self, cursor, user, context=None):
        if context and context.get('company'):
            return context['company']
        return False

Journal()
