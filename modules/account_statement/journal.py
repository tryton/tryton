# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql import Window
from sql.functions import FirstValue

from trytond import backend
from trytond.model import DeactivableMixin, ModelSQL, ModelView, Unique, fields
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.rpc import RPC
from trytond.tools import (
    cursor_dict, grouped_slice, reduce_ids, sqlite_apply_types)
from trytond.transaction import Transaction


class Journal(DeactivableMixin, ModelSQL, ModelView):
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
            ['OR',
                ('currency', '=', Eval('currency', -1)),
                ('currency', '=', None),
                ],
            ])
    account = fields.Many2One('account.account', "Account", required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', '=', Eval('company', -1)),
            ('party_required', '=', False),
            ])

    last_date = fields.Function(fields.Date("Last Date"), 'get_last_statement')
    last_amount = fields.Function(Monetary(
            "Last Amount", currency='currency', digits='currency',
            states={
                'invisible': ~Eval('validation').in_(['balance']),
                }),
        'get_last_statement')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('name', 'ASC'))
        t = cls.__table__()
        cls._sql_constraints = [
            ('bank_account_unique',
                Unique(t, t.bank_account, t.company),
                'account_statement.msg_journal_bank_account_unique'),
            ]
        cls.__rpc__.update(
            get_by_bank_account=RPC(
                result=lambda r: int(r) if r is not None else None),
            )

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
    def get_by_bank_account(cls, company, number, currency=None):
        domain = [
            ('company', '=', company),
            ['OR',
                ('bank_account.numbers.number', '=', number),
                ('bank_account.numbers.number_compact', '=', number),
                ],
            ]
        if currency:
            domain.append(['OR',
                    ('currency.code', '=', currency),
                    ('currency.numeric_code', '=', currency),
                    ])
        journals = cls.search(domain)
        if journals:
            journal, = journals
            return journal

    @classmethod
    def get_last_statement(cls, journals, names):
        pool = Pool()
        Statement = pool.get('account.statement')
        statement = Statement.__table__()
        transaction = Transaction()
        cursor = transaction.connection.cursor()

        id2currency = {j.id: j.currency for j in journals}

        result = {}
        for name in names:
            result[name] = dict.fromkeys(id2currency.keys(), None)

        for sub_ids in grouped_slice(id2currency.keys()):
            columns = [statement.journal]
            w = Window(
                partition=[statement.journal],
                order_by=[statement.date.desc, statement.id.desc])
            if 'last_amount' in names:
                columns.append(
                    FirstValue(statement.end_balance,
                        window=w).as_('last_amount'))
            if 'last_date' in names:
                columns.append(
                    FirstValue(statement.date, window=w).as_('last_date'))
            query = statement.select(*columns,
                    distinct=True,
                    where=reduce_ids(statement.journal, sub_ids)
                    & (statement.state != 'cancelled'))
            if backend.name == 'sqlite':
                types = [None]
                if 'last_amount' in names:
                    types.append('NUMERIC')
                if 'last_date' in names:
                    types.append('DATE')
                sqlite_apply_types(query, types)
            cursor.execute(*query)
            for row in cursor_dict(cursor):
                journal = row['journal']
                if 'last_amount' in names:
                    result['last_amount'][journal] = (
                        id2currency[journal].round(row['last_amount']))
                if 'last_date' in names:
                    result['last_date'][journal] = row['last_date']
        return result
