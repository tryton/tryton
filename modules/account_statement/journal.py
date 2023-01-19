# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import DeactivableMixin, ModelSQL, ModelView, Unique, fields
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction


class Journal(DeactivableMixin, ModelSQL, ModelView):
    'Statement Journal'
    __name__ = 'account.statement.journal'
    name = fields.Char('Name', required=True)
    journal = fields.Many2One(
        'account.journal', 'Journal', required=True,
        domain=[('type', '=', 'statement')],
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    company = fields.Many2One('company.company', "Company", required=True)
    company_party = fields.Function(
        fields.Many2One(
            'party.party', "Company Party",
            context={
                'company': Eval('company', -1),
                },
            depends={'company'}),
        'on_change_with_company_party')
    validation = fields.Selection([
            ('balance', 'Balance'),
            ('amount', 'Amount'),
            ('number_of_lines', 'Number of Lines'),
            ], 'Validation Type', required=True)
    bank_account = fields.Many2One(
        'bank.account', "Bank Account",
        domain=[
            ('owners.id', '=', Eval('company_party', -1)),
            ('currency', '=', Eval('currency', -1)),
            ])
    account = fields.Many2One('account.account', "Account", required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', '=', Eval('company')),
            ('party_required', '=', False),
            ])

    @classmethod
    def __setup__(cls):
        super(Journal, cls).__setup__()
        cls._order.insert(0, ('name', 'ASC'))
        t = cls.__table__()
        cls._sql_constraints = [
            ('bank_account_unique',
                Unique(t, t.bank_account, t.company),
                'account_statement.msg_journal_bank_account_unique'),
            ]

    @staticmethod
    def default_currency():
        if Transaction().context.get('company'):
            Company = Pool().get('company.company')
            company = Company(Transaction().context['company'])
            return company.currency.id

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @fields.depends('company')
    def on_change_with_company_party(self, name=None):
        return self.company.party if self.company else None

    @staticmethod
    def default_validation():
        return 'balance'

    @classmethod
    def get_by_bank_account(cls, company, number):
        journals = cls.search([
                ('company', '=', company),
                ['OR',
                    ('bank_account.numbers.number', '=', number),
                    ('bank_account.numbers.number_compact', '=', number),
                    ],
                ])
        if journals:
            journal, = journals
            return journal
