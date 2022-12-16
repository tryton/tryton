# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.pool import Pool

__all__ = ['Journal']


class Journal(ModelSQL, ModelView):
    'Statement Journal'
    __name__ = 'account.statement.journal'
    name = fields.Char('Name', required=True)
    journal = fields.Many2One('account.journal', 'Journal', required=True,
        domain=[('type', '=', 'statement')])
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    company = fields.Many2One('company.company', 'Company', required=True,
            select=True)
    validation = fields.Selection([
            ('balance', 'Balance'),
            ('amount', 'Amount'),
            ('number_of_lines', 'Number of Lines'),
            ], 'Validation Type', required=True)

    @staticmethod
    def default_currency():
        if Transaction().context.get('company'):
            Company = Pool().get('company.company')
            company = Company(Transaction().context['company'])
            return company.currency.id

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_validation():
        return 'balance'
