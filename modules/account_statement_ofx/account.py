# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from io import BytesIO

import ofxparse

from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool

from trytond.modules.account_statement.exceptions import ImportStatementError


class StatementImportStart(metaclass=PoolMeta):
    __name__ = 'account.statement.import.start'

    @classmethod
    def __setup__(cls):
        super(StatementImportStart, cls).__setup__()
        cls.file_format.selection.append(('ofx', "OFX"))


class StatementImport(metaclass=PoolMeta):
    __name__ = 'account.statement.import'

    def parse_ofx(self):
        file_ = BytesIO(self.start.file_)
        ofx = ofxparse.OfxParser.parse(file_)

        for account in ofx.accounts:
            statement = self.ofx_statement(ofx, account)
            origins = []
            for transaction in account.statement.transactions:
                origins.extend(self.ofx_origin(account, transaction))
            statement.origins = origins
            yield statement

    def ofx_statement(self, ofx, ofx_account):
        pool = Pool()
        Statement = pool.get('account.statement')
        Journal = pool.get('account.statement.journal')

        statement = Statement()
        statement.name = ofx.trnuid
        statement.company = self.start.company
        statement.journal = Journal.get_by_bank_account(
            statement.company, ofx_account.number)
        if not statement.journal:
            raise ImportStatementError(
                gettext('account_statement.msg_import_no_journal',
                    account=ofx_account.number))
        if statement.journal.currency.code != ofx_account.curdef:
            raise ImportStatementError(
                gettext('account_statement.msg_import_wrong_currency',
                    journal=statement.journal.rec_name,
                    currency=statement.journal.currency.rec_name,
                    journal_currency=ofx_account.curdef))
        if not isinstance(ofx_account.statement, ofxparse.Statement):
            raise ImportStatementError(
                gettext('account_statement_ofx.msg_import_no_statement'))
        try:
            statement.date = ofx_account.statement.balance_date.date()
        except AttributeError:
            pass
        total_amount = sum(
            t.amount for t in ofx_account.statement.transactions)
        statement.total_amount = total_amount
        statement.start_balance = ofx_account.statement.balance - total_amount
        statement.end_balance = ofx_account.statement.balance
        statement.number_of_lines = len(ofx_account.statement.transactions)
        return statement

    def ofx_origin(self, ofx_account, transaction):
        pool = Pool()
        Origin = pool.get('account.statement.origin')

        origin = Origin()
        origin.number = transaction.id
        origin.date = transaction.date.date()
        origin.amount = transaction.amount
        origin.party = self.ofx_party(ofx_account, transaction)
        if origin.party:
            origin.description = transaction.memo
        else:
            origin.description = '|'.join(
                filter(None, [transaction.payee, transaction.memo]))
        origin.information = self.ofx_information(ofx_account, transaction)
        return [origin]

    def ofx_party(self, ofx_account, transaction):
        pool = Pool()
        Party = pool.get('party.party')

        if not transaction.payee:
            return
        parties = Party.search([('rec_name', 'ilike', transaction.payee)])
        if len(parties) == 1:
            party, = parties
            return party

    def ofx_information(self, ofx_account, transaction):
        information = {}
        for name in [
                'checknum',
                'mcc',
                'sic',
                'type',
                ]:
            value = getattr(transaction, name)
            if value:
                information['ofx_' + name] = value
        return information
