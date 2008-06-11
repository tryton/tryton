"Statement Journal"

from trytond.osv import fields, OSV

class Journal(OSV):
    'Statement Journal'
    _name = 'statement.journal'
    _description = __doc__

    name = fields.Char('Name', size=None, required=True)
    journal = fields.Many2One(
        'account.journal', 'Bank Journal', required=True,
        domain="[('type', '=', 'bank')]")
    balance = fields.Numeric('Balance', digits=(12, 6))
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    company = fields.Many2One('company.company', 'Company', required=True)

    def default_currency(self, cursor, user, context=None):
        if context and context.get('company'):
            company_obj = self.pool.get('company.company')
            currency_obj = self.pool.get('currency.currency')
            company = company_obj.browse(cursor, user, context['company'],
                    context=context)
            return currency_obj.name_get(cursor, user, company.currency.id,
                    context=context)[0]
        return False

    def default_company(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        if context and context.get('company'):
            return company_obj.name_get(cursor, user, context['company'],
                    context=context)[0]
        return False

Journal()
