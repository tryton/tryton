# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from io import BytesIO, TextIOWrapper

from aeb43 import AEB43

from trytond.i18n import gettext
from trytond.modules.account_statement.exceptions import ImportStatementError
from trytond.pool import Pool, PoolMeta


class ImportStatementStart(metaclass=PoolMeta):
    __name__ = 'account.statement.import.start'

    @classmethod
    def __setup__(cls):
        super(ImportStatementStart, cls).__setup__()
        aeb43 = ('aeb43', 'AEB Norm 43')
        cls.file_format.selection.append(aeb43)


class ImportStatement(metaclass=PoolMeta):
    __name__ = 'account.statement.import'

    def parse_aeb43(self, encoding='iso-8859-1'):
        file_ = TextIOWrapper(BytesIO(self.start.file_), encoding=encoding)
        aeb43 = AEB43(file_)

        for account in aeb43.accounts:
            statement = self.aeb43_statement(account)
            origins = []
            for transaction in account.transactions:
                origins.extend(self.aeb43_origin(statement, transaction))
            statement.origins = origins
            yield statement

    def aeb43_statement(self, account):
        pool = Pool()
        Statement = pool.get('account.statement')
        Journal = pool.get('account.statement.journal')

        journal = Journal.get_by_bank_account(
            self.start.company, account.ccc, currency=account.currency)
        if not journal:
            journal = Journal.get_by_bank_account(
                self.start.company, account.iban, currency=account.currency)
        if not journal:
            raise ImportStatementError(
                gettext('account_statement.msg_import_no_journal',
                    account=account.ccc))

        statement = Statement()
        statement.name = '%(start_date)s - %(end_date)s' % {
            'start_date': account.start_date,
            'end_date': account.end_date,
            }
        statement.company = self.start.company
        statement.journal = journal
        statement.date = account.end_date
        statement.start_balance = account.initial_balance
        statement.end_balance = account.final_balance
        statement.number_of_lines = len(account.transactions)
        statement.total_amount = (
            account.final_balance - account.initial_balance)
        return statement

    def aeb43_origin(self, statement, transaction):
        pool = Pool()
        Origin = pool.get('account.statement.origin')
        origin = Origin()
        origin.date = transaction.transaction_date
        origin.amount = transaction.amount
        origin.description = ''.join(transaction.items)
        origin.information = self.aeb43_information(statement, transaction)
        return [origin]

    def aeb43_information(self, statement, transaction):
        return {
            'aeb43_operation_date': transaction.transaction_date,
            'aeb43_record_type': transaction.shared_item,
            'aeb43_document_number': int(transaction.document),
            'aeb43_first_reference': transaction.reference1,
            'aeb43_second_reference': transaction.reference2,
            }
