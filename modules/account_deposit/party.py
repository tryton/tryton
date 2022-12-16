# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from sql import Null, Literal, For
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool
from trytond.model import fields
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.tools import grouped_slice, reduce_ids

from trytond.modules.party.exceptions import EraseError


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    deposit = fields.Function(fields.Numeric('Deposit',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_deposit', searcher='search_deposit')

    @classmethod
    def get_deposit(cls, parties, name):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Account = pool.get('account.account')
        AccountType = pool.get('account.account.type')
        User = pool.get('res.user')
        cursor = Transaction().connection.cursor()

        line = MoveLine.__table__()
        account = Account.__table__()
        account_type = AccountType.__table__()

        values = {p.id: Decimal(0) for p in parties}

        user = User(Transaction().user)
        if not user.company:
            return values
        currency = user.company.currency

        line_clause, _ = MoveLine.query_get(line)

        for sub_parties in grouped_slice(parties):
            party_clause = reduce_ids(line.party, [p.id for p in sub_parties])
            cursor.execute(*line
                .join(account, condition=account.id == line.account)
                .join(account_type, condition=account.type == account_type.id)
                .select(line.party,
                    # Use credit - debit to positive deposit amount
                    Sum(Coalesce(line.credit, 0) - Coalesce(line.debit, 0)),
                    where=account_type.deposit
                    & party_clause
                    & (line.reconciliation == Null)
                    & (account.company == user.company.id)
                    & line_clause,
                    group_by=line.party))
            for party_id, value in cursor.fetchall():
                # SQLite uses float for SUM
                if not isinstance(value, Decimal):
                    value = currency.round(Decimal(str(value)))
                values[party_id] = value
        return values

    @classmethod
    def search_deposit(cls, name, clause):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Account = pool.get('account.account')
        AccountType = pool.get('account.account.type')
        User = pool.get('res.user')

        line = MoveLine.__table__()
        account = Account.__table__()
        account_type = AccountType.__table__()

        user = User(Transaction().user)
        if not user.company:
            return []

        line_clause, _ = MoveLine.query_get(line)
        Operator = fields.SQL_OPERATORS[clause[1]]

        query = (line
            .join(account, condition=account.id == line.account)
            .join(account_type, condition=account.type == account_type.id)
            .select(line.party,
                where=account.active
                & account_type.deposit
                & (line.party != Null)
                & (line.reconciliation == Null)
                & (account.company == user.company.id)
                & line_clause,
                group_by=line.party,
                having=Operator(
                    Sum(Coalesce(line.debit, 0) - Coalesce(line.credit, 0)),
                    Decimal(clause[2] or 0))))
        return [('id', 'in', query)]

    def get_deposit_balance(self, deposit_account):
        'Return the deposit account balance (debit - credit) for the party'
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        transaction = Transaction()
        cursor = transaction.connection.cursor()

        line = MoveLine.__table__()
        assert deposit_account.type.deposit

        where = ((line.account == deposit_account.id)
            & (line.party == self.id)
            & (line.reconciliation == Null))
        if transaction.database.has_select_for():
            cursor.execute(*line.select(
                    Literal(1),
                    where=where,
                    for_=For('UPDATE', nowait=True)))
        else:
            transaction.database.lock(transaction.connection, MoveLine._table)
        cursor.execute(*line.select(
                Sum(Coalesce(line.debit, 0) - Coalesce(line.credit, 0)),
                where=where))
        amount, = cursor.fetchone()
        if amount and not isinstance(amount, Decimal):
            currency = deposit_account.company.currency
            amount = currency.round(Decimal(str(amount)))
        return amount or Decimal(0)

    def check_deposit(self, deposit_account, sign=1):
        '''Check if the deposit account balance (debit - credit) has the same
        sign for the party'''
        assert sign in (1, -1)
        amount = self.get_deposit_balance(deposit_account)
        return not amount or ((amount < 0) == (sign < 0))


class Erase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def check_erase_company(self, party, company):
        if party.deposit:
            raise EraseError(
                gettext('account_deposit.msg_erase_party_deposit',
                    party=party.rec_name,
                    company=company.rec_name))
