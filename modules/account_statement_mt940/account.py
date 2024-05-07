# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from io import BytesIO, TextIOWrapper

from mt940 import (
    MT940, abn_amro_description, ing_description, regiobank_description)

from trytond.i18n import gettext
from trytond.model import fields
from trytond.modules.account_statement.exceptions import ImportStatementError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


class StatementImportStart(metaclass=PoolMeta):
    __name__ = 'account.statement.import.start'

    mt940_bank = fields.Selection([
            (None, ""),
            ('rabo', "Rabo"),
            ('abn_amro', "ABN AMRO"),
            ('ing', "ING"),
            ('regiobank', "RegioBank"),
            ], "Bank",
        states={
            'invisible': Eval('file_format') != 'mt940',
            })

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.file_format.selection.append(('mt940', "MT940"))


class StatementImport(metaclass=PoolMeta):
    __name__ = 'account.statement.import'

    def parse_mt940(self, encoding=None):
        file_ = TextIOWrapper(BytesIO(self.start.file_), encoding=encoding)
        mt940 = MT940(file_)
        for mt940_statement in mt940.statements:
            statement = self.mt940_statement(mt940_statement)
            origins = []
            for transaction in mt940_statement.transactions:
                origins.extend(self.mt940_origin(mt940_statement, transaction))
            statement.origins = origins
            yield statement

    def mt940_statement(self, mt940_statement):
        pool = Pool()
        Statement = pool.get('account.statement')
        Journal = pool.get('account.statement.journal')

        statement = Statement()
        statement.name = mt940_statement.information
        statement.company = self.start.company
        account, currency = (
            self.mt940_statement_account_currency(mt940_statement))
        start_balance = mt940_statement.start_balance
        end_balance = mt940_statement.end_balance
        statement.journal = Journal.get_by_bank_account(
            statement.company, account,
            currency=currency or start_balance.currency)
        if not statement.journal:
            raise ImportStatementError(
                gettext('account_statement.msg_import_no_journal',
                    account=mt940_statement.account))
        statement.date = end_balance.date
        statement.start_balance = start_balance.amount
        statement.end_balance = end_balance.amount
        statement.total_amount = (
            end_balance.amount - start_balance.amount)
        statement.number_of_lines = len(mt940_statement.transactions)
        return statement

    def mt940_statement_account_currency(self, mt940_statement):
        if self.start.mt940_bank == 'rabo':
            return mt940_statement.account.split(' ', 1)
        return mt940_statement.account, None

    def mt940_origin(self, mt940_statement, transaction):
        pool = Pool()
        Origin = pool.get('account.statement.origin')

        origin = Origin()
        origin.number = transaction.id
        origin.date = transaction.date
        origin.amount = transaction.amount
        origin.party = self.mt940_party(mt940_statement, transaction)
        origin.description = ''.join(transaction.description.splitlines())
        origin.information = self.mt940_information(
            mt940_statement, transaction)
        return [origin]

    def mt940_party(self, mt940_statement, transaction):
        pool = Pool()
        AccountNumber = pool.get('bank.account.number')

        account = self.mt940_account(mt940_statement, transaction)
        if account:
            numbers = AccountNumber.search(['OR',
                    ('number', '=', account),
                    ('number_compact', '=', account),
                    ])
            if len(numbers) == 1:
                number, = numbers
                if number.account.owners:
                    return number.account.owners[0]

    def mt940_account(self, mt940_statement, transaction):
        if self.start.mt940_bank == 'abn_amro':
            description = abn_amro_description(transaction.description)
            return description.get('account')
        elif self.start.mt940_bank == 'ing':
            description = ing_description(transaction.description)
            return description.get('cntp', {}).get('account_number')
        elif self.start.mt940_bank == 'regiobank':
            description = regiobank_description(transaction.description)
            return description.get('account')

    def mt940_information(self, mt940_statement, transaction):
        information = {}
        for name in [
                'reference',
                'institution_reference',
                'additional_data']:
            value = getattr(transaction, name)
            if value:
                information['mt940_' + name] = value
        return information
