# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Table

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

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        table = cls.__table_handler__(module_name)
        sql_table = cls.__table__()
        journal_account = Table('account_journal_account')

        created_account = not table.column_exist('account')

        super(Journal, cls).__register__(module_name)

        # Migration from 4.8: new account field
        if created_account and table.table_exist('account_journal_account'):
            value = journal_account.select(journal_account.credit_account,
                where=((journal_account.journal == sql_table.journal)
                    & (journal_account.credit_account
                        == journal_account.debit_account)))
            # Don't use UPDATE FROM because SQLite does not support it.
            cursor.execute(*sql_table.update([sql_table.account], [value]))

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
