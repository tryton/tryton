# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from io import StringIO

from stdnum.es.ccc import calc_check_digits, to_iban
from csb43 import csb43

from trytond.pool import Pool, PoolMeta

__all__ = ['ImportStatementStart', 'ImportStatement']


class ImportStatementStart(metaclass=PoolMeta):
    __name__ = 'account.statement.import.start'

    @classmethod
    def __setup__(cls):
        super(ImportStatementStart, cls).__setup__()
        aeb43 = ('aeb43', 'AEB Norm 43')
        cls.file_format.selection.append(aeb43)


class ImportStatement(metaclass=PoolMeta):
    __name__ = 'account.statement.import'

    @classmethod
    def __setup__(cls):
        super(ImportStatement, cls).__setup__()
        cls._error_messages.update({
                'aeb43_no_journal': (
                    'No journal found for the bank account "%(account)s".'),
                })

    def parse_aeb43(self, encoding='iso-8859-1'):
        file_ = self.start.file_
        if not isinstance(file_, str):
            file_ = file_.decode(encoding)
        aeb43 = csb43.File(StringIO(file_), strict=False)

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

        # Compute IBAN code from spanish format
        bank_code = account.bankCode
        branch_code = account.branchCode
        account_number = account.accountNumber
        check_digits = calc_check_digits(
            bank_code + branch_code + '00' + account_number)
        bank_account = to_iban(
            bank_code + branch_code + check_digits + account_number)
        journal = Journal.get_by_bank_account(self.start.company, bank_account)
        if not journal:
            self.raise_user_error('aeb43_no_journal', {
                    'account': bank_account,
                    })

        statement = Statement()
        statement.name = '%(account)s@(%(start_date)s/%(end_date)s)' % {
            'account': bank_account,
            'start_date': account.initialDate,
            'end_date': account.finalDate,
            }
        statement.company = self.start.company
        statement.journal = journal
        statement.start_balance = account.initialBalance
        statement.end_balance = account.abstract.balance
        statement.number_of_lines = (
            account.abstract.incomeEntries + account.abstract.expenseEntries)
        statement.total_amount = (
            account.abstract.income - account.abstract.expense)
        return statement

    def aeb43_origin(self, statement, transaction):
        pool = Pool()
        Origin = pool.get('account.statement.origin')
        origin = Origin()
        origin.date = transaction.valueDate
        origin.amount = transaction.amount
        descriptions = []
        for item in transaction.optionalItems:
            if item.item1:
                descriptions.append(item.item1)
            if item.item2:
                descriptions.append(item.item2)
        origin.description = ''.join(descriptions)
        origin.informations = self.aeb43_informations(statement, transaction)
        return [origin]

    def aeb43_informations(self, statement, transaction):
        return {
            'aeb43_operation_date': transaction.transactionDate,
            'aeb43_record_type': transaction.sharedItem,
            'aeb43_document_number': transaction.documentNumber,
            'aeb43_first_reference': transaction.reference1,
            'aeb43_second_reference': transaction.reference2,
            }
