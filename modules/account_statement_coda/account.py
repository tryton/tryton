# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from io import StringIO

from coda import CODA

from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool

from trytond.modules.account_statement.exceptions import ImportStatementError


class StatementImportStart(metaclass=PoolMeta):
    __name__ = 'account.statement.import.start'

    @classmethod
    def __setup__(cls):
        super(StatementImportStart, cls).__setup__()
        cls.file_format.selection.append(('coda', "CODA"))


class StatementImport(metaclass=PoolMeta):
    __name__ = 'account.statement.import'

    def parse_coda(self, encoding='windows-1252'):
        file_ = self.start.file_
        if not isinstance(file_, str):
            file_ = file_.decode(encoding)
        file_ = StringIO(file_)
        coda = CODA(file_)
        for coda_statement in coda.statements:
            statement = self.coda_statement(coda_statement)
            origins = []
            for move in coda_statement.moves:
                origins.extend(self.coda_origin(coda_statement, move))
            statement.origins = origins
            yield statement

    def coda_statement(self, coda_statement):
        pool = Pool()
        Statement = pool.get('account.statement')
        Journal = pool.get('account.statement.journal')

        statement = Statement()
        statement.name = coda_statement.new_sequence
        statement.company = self.start.company
        statement.journal = Journal.get_by_bank_account(
            statement.company, coda_statement.account)
        if not statement.journal:
            raise ImportStatementError(
                gettext('account_statement.msg_import_no_journal',
                    account=coda_statement.account))
        if statement.journal.currency.code != coda_statement.account_currency:
            raise ImportStatementError(
                gettext('account_statement.msg_import_wrong_currency',
                    journal=statement.journal.rec_name,
                    currency=coda_statement.account_currency,
                    journal_currency=statement.journal.currency.rec_name))
        statement.date = coda_statement.creation_date
        statement.start_balance = coda_statement.old_balance
        statement.end_balance = coda_statement.new_balance
        statement.total_amount = (
            coda_statement.total_credit - coda_statement.total_debit)
        statement.number_of_lines = len(coda_statement.moves)
        return statement

    def coda_origin(self, coda_statement, move):
        pool = Pool()
        Origin = pool.get('account.statement.origin')

        origin = Origin()
        origin.number = move.sequence
        origin.date = move.entry_date
        origin.amount = move.amount
        origin.party = self.coda_party(coda_statement, move)
        # TODO select account using transaction codes
        origin.description = move.communication
        origin.information = self.coda_information(coda_statement, move)
        return [origin]

    def coda_party(self, coda_statement, move):
        pool = Pool()
        AccountNumber = pool.get('bank.account.number')

        if not move.counterparty_account:
            return
        numbers = AccountNumber.search(['OR',
                ('number', '=', move.counterparty_account),
                ('number_compact', '=', move.counterparty_account),
                ])
        if len(numbers) == 1:
            number, = numbers
            if number.account.owners:
                return number.account.owners[0]

    def coda_information(self, coda_statement, move):
        information = {}
        for name in [
                'bank_reference',
                'customer_reference',
                'counterparty_bic',
                'counterparty_account',
                'counterparty_name',
                'r_transaction',
                'category_purpose',
                'purpose',
                'transaction_family',
                'transaction_transaction',
                'transaction_category']:
            value = getattr(move, name)
            if value:
                information['coda_' + name] = value
        # TODO add move information
        return information
