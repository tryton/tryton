# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from sql import Literal, Null
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond.i18n import gettext
from trytond.model import fields
from trytond.model.exceptions import AccessError
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool, PoolMeta
from trytond.tools import grouped_slice, reduce_ids
from trytond.transaction import Transaction


class Company(metaclass=PoolMeta):
    __name__ = 'company.company'

    receivable = fields.Function(Monetary(
            "Receivable", currency='currency', digits='currency'),
        'get_receivable_payable', searcher='search_receivable_payable')
    payable = fields.Function(Monetary(
            "Payable", currency='currency', digits='currency'),
        'get_receivable_payable', searcher='search_receivable_payable')
    receivable_today = fields.Function(Monetary(
            "Receivable Today", currency='currency', digits='currency'),
        'get_receivable_payable', searcher='search_receivable_payable')
    payable_today = fields.Function(Monetary(
            "Payable Today", currency='currency', digits='currency'),
        'get_receivable_payable', searcher='search_receivable_payable')

    @classmethod
    def get_receivable_payable(cls, companies, names):
        amounts = {}
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Account = pool.get('account.account')
        AccountType = pool.get('account.account.type')
        Date = pool.get('ir.date')
        cursor = Transaction().connection.cursor()

        line = MoveLine.__table__()
        account = Account.__table__()
        account_type = AccountType.__table__()

        for name in names:
            assert name in {
                'receivable', 'payable', 'receivable_today', 'payable_today'}
            amounts[name] = dict.fromkeys(map(int, companies), Decimal(0))

        exp = {
            c.id: Decimal(str(10.0 ** -c.currency.digits)) for c in companies}
        today = Date.today()

        amount = Sum(Coalesce(line.debit, 0) - Coalesce(line.credit, 0))
        for name in names:
            if name.endswith('_today'):
                code = name[:-len('_today')]
                today_where = (
                    (line.maturity_date <= today)
                    | (line.maturity_date == Null))
            else:
                code = name
                today_where = Literal(True)
            for sub_companies in grouped_slice(companies):
                sub_ids = [p.id for p in sub_companies]
                company_where = reduce_ids(account.company, sub_ids)
                cursor.execute(*line
                    .join(account,
                        condition=account.id == line.account)
                    .join(account_type,
                        condition=account.type == account_type.id)
                    .select(account.company, amount,
                        where=(getattr(account_type, code)
                            & (line.reconciliation == Null)
                            & company_where
                            & today_where),
                        group_by=account.company))
                for company_id, value in cursor:
                    # SQLite uses float for SUM
                    if not isinstance(value, Decimal):
                        value = Decimal(str(value))
                    amounts[name][company_id] = value.quantize(exp[company_id])
        return amounts

    @classmethod
    def search_receivable_payable(cls, name, clause):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Account = pool.get('account.account')
        AccountType = pool.get('account.account.type')
        Date = pool.get('ir.date')

        line = MoveLine.__table__()
        account = Account.__table__()
        account_type = AccountType.__table__()

        assert name in {
            'receivable', 'payable', 'receivable_today', 'payable_today'}
        _, operator, value = clause

        today = Date.today()

        if name.endswith('_today'):
            code = name[:-len('_today')]
            today_query = ((line.maturity_date <= today)
                | (line.maturity_date == Null))
        else:
            code = name
            today_query = Literal(True)

        Operator = fields.SQL_OPERATORS[operator]

        # Need to cast numeric for sqlite
        cast_ = MoveLine.debit.sql_cast
        amount = cast_(Sum(Coalesce(line.debit, 0) - Coalesce(line.credit, 0)))
        if operator in {'in', 'not in'}:
            value = [cast_(Literal(Decimal(v or 0))) for v in value]
        else:
            value = cast_(Literal(Decimal(value or 0)))
        query = (line
            .join(account, condition=account.id == line.account)
            .join(account_type, condition=account.type == account_type.id)
            .select(account.company,
                where=(getattr(account_type, code)
                    & (line.reconciliation == Null)
                    & today_query),
                group_by=account.company,
                having=Operator(amount, value)))
        return [('id', 'in', query)]

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Move = pool.get('account.move')
        transaction = Transaction()
        if transaction.user and transaction.check_access:
            actions = iter(args)
            for companies, values in zip(actions, actions):
                if 'currency' in values:
                    moves = Move.search([
                            ('company', 'in', [c.id for c in companies]),
                            ],
                        limit=1, order=[])
                    if moves:
                        raise AccessError(gettext(
                                'account.msg_company_change_currency'))

        super().write(*args)
