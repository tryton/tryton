# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
from decimal import Decimal
from io import BytesIO

from lxml import etree

from trytond.i18n import gettext
from trytond.modules.account_statement.exceptions import ImportStatementError
from trytond.pool import Pool, PoolMeta


class StatementImportStart(metaclass=PoolMeta):
    __name__ = 'account.statement.import.start'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.file_format.selection.extend([
                ('camt_052_001', "CAMT.052.001"),
                ('camt_053_001', "CAMT.053.001"),
                ('camt_054_001', "CAMT.054.001"),
                ])


class StatementImport(metaclass=PoolMeta):
    __name__ = 'account.statement.import'

    def parse_camt(self):
        file_ = BytesIO(self.start.file_)
        tree = etree.parse(file_)
        root = tree.getroot()
        namespaces = dict(root.nsmap)
        namespaces['ns'] = namespaces.pop(None)
        for camt_statement in root.xpath(
                './ns:BkToCstmrStmt/ns:Stmt | '
                './ns:BkToCstmrAcctRpt/ns:Rpt | '
                './ns:BkToCstmrDbtCdtNtfctn/ns:Ntfctn', namespaces=namespaces):
            statement = self.camt_statement(camt_statement)
            origins = []
            for entry in camt_statement.iterfind('./{*}Ntry'):
                origins.extend(self.camt_origin(camt_statement, entry))
            if origins:
                statement.number_of_lines = len(origins)
                statement.origins = origins
                yield statement

    parse_camt_052_001 = parse_camt
    parse_camt_053_001 = parse_camt
    parse_camt_054_001 = parse_camt

    def camt_statement(self, camt_statement):
        pool = Pool()
        Statement = pool.get('account.statement')
        Journal = pool.get('account.statement.journal')

        statement = Statement()
        statement.name = camt_statement.findtext('./{*}Id')
        statement.company = self.start.company
        account_number = self.camt_account_number(camt_statement)
        account_currency = self.camt_account_currency(camt_statement)
        statement.journal = Journal.get_by_bank_account(
            statement.company, account_number, currency=account_currency)
        if not statement.journal:
            raise ImportStatementError(
                gettext('account_statement.msg_import_no_journal',
                    account=account_number))
        statement.date = self.camt_statement_date(camt_statement)
        statement.start_balance, statement.end_balance = (
            self.camt_statement_balances(camt_statement))
        statement.total_amount = self.camt_statement_total(camt_statement)
        return statement

    def _camt_amount(self, node):
        amount = Decimal(node.findtext('./{*}Amt'))
        if node.findtext('./{*}CdtDbtInd') == 'DBIT':
            amount *= -1
        return amount

    def camt_account_number(self, camt_statement):
        number = camt_statement.findtext('./{*}Acct/{*}Id/{*}IBAN')
        if not number:
            number = camt_statement.findtext('./{*}Acct/{*}Id/{*}Othr/{*}Id')
        return number

    def camt_account_currency(self, camt_statement):
        return camt_statement.findtext('./{*}Acct/{*}Ccy')

    def camt_statement_date(self, camt_statement):
        pool = Pool()
        Date = pool.get('ir.date')
        datetime = camt_statement.findtext('./{*}CreDtTm')
        if datetime:
            return dt.datetime.fromisoformat(datetime).date()
        else:
            return Date.today()

    def camt_statement_balances(self, camt_statement):
        namespaces = dict(camt_statement.nsmap)
        namespaces['ns'] = namespaces.pop(None)
        start_balance = end_balance = None
        for code in [
                'OPBD',  # Opening Balance
                'PRCD',  # Previous Closing Balance
                'CLBD',  # Closing Balance
                'ITBD',  # Interim Balance
                ]:
            balances = camt_statement.xpath(
                f'./ns:Bal/ns:Tp/ns:CdOrPrtry/ns:Cd[text()="{code}"]'
                '/../../..', namespaces=namespaces)
            if balances:
                if code in {'OPBD', 'PRCD'}:
                    start_balance = self._camt_amount(balances[0])
                elif code == 'CLBD':
                    end_balance = self._camt_amount(balances[-1])
                else:
                    start_balance = self._camt_amount(balances[0])
                    end_balance = self._camt_amount(balances[-1])
        return start_balance, end_balance

    def camt_statement_total(self, camt_statement):
        total = camt_statement.find(
            './{*}TxsSummry/{*}TtlNtries/{*}TtlNetNtry')
        if total is not None:
            return self._camt_amount(total)

    def camt_origin(self, camt_statement, entry):
        pool = Pool()
        Date = pool.get('ir.date')
        Origin = pool.get('account.statement.origin')

        details = entry.findall('./{*}NtryDtls/{*}TxDtls')
        if not details:
            details = [None]
        for detail in details:
            origin = Origin()
            origin.number = entry.findtext('./{*}NtryRef')
            origin.date = Date.today()
            booking_date = entry.find('./{*}BookgDt')
            if booking_date is not None:
                if booking_date.find('./{*}Dt') is not None:
                    origin.date = dt.date.fromisoformat(
                        booking_date.findtext('./{*}Dt'))
                elif booking_date.find('./{*}DtTm') is not None:
                    origin.date = dt.date.fromisoformat(
                        booking_date.findtext('./{*}DtTm')).date()
            origin.amount = self._camt_amount(entry)
            origin.description = self.camt_description(camt_statement, entry)
            if detail is not None:
                origin.party = self.camt_party(camt_statement, entry, detail)
                origin.information = self.camt_information(
                    camt_statement, entry, detail)

            yield origin

    def camt_description(self, camt_statement, entry):
        return entry.findtext('./{*}AddtlNtryInf')

    def camt_party(self, camt_statement, entry, detail):
        pool = Pool()
        AccountNumber = pool.get('bank.account.number')

        path = {
            'DBIT': './{*}RltdPties/{*}CdtrAcct/{*}Id/{*}IBAN',
            'CRDT': './{*}RltdPties/{*}DbtrAcct/{*}Id/{*}IBAN',
            }[entry.findtext('./{*}CdtDbtInd')]
        number = detail.findtext(path)
        if number:
            numbers = AccountNumber.search(['OR',
                    ('number', '=', number),
                    ('number_compact', '=', number),
                    ])
            if len(numbers) == 1:
                number, = numbers
                if number.account.owners:
                    return number.account.owners[0]

    def camt_information(self, camt_statement, entre, detail):
        information = {}
        for key, path in [
                ('camt_message_identification', './{*}Refs/{*}MsgId'),
                ('camt_account_service_reference', './{*}Refs/{*}AcctSvcrRef'),
                ('camt_payment_information_identification',
                    './{*}Refs/{*}PmtInfId'),
                ('camt_instruction_identification', './{*}Refs/{*}InstrId'),
                ('camt_end_to_end_identification', './{*}Refs/{*}EndToEndId'),
                ('camt_transaction_identification', './{*}Refs/{*}TxId'),
                ('camt_mandate_identification', './{*}Refs/{*}MndtId'),
                ('camt_cheque_number', './{*}Refs/{*}ChqNb'),
                ('camt_clearing_system_reference', './{*}Refs/{*}ClrSysRef'),
                ('camt_account_owner_transaction_identification',
                    './{*}Refs/{*}AcctOwnrTxId'),
                ('camt_account_servicer_transaction_identification',
                    './{*}Refs/{*}AcctSvcrTxId'),
                ('camt_market_infrastructure_transaction_identification',
                    './{*}Refs/{*}MktInfrstrctrTxId'),
                ('camt_processing_identification', './{*}Refs/{*}PrcgId'),
                ('camt_remittance_information', './{*}RmtInf/{*}Ustrd'),
                ('camt_additional_transaction_information', './{*}AddtlTxInf'),
                ('camt_debtor_name', './{*}RltdPties/{*}Dbtr//{*}Nm'),
                ('camt_ultimate_debtor_name',
                    './{*}RltdPties/{*}UltmtDbtr//{*}Nm'),
                ('camt_debtor_iban',
                    './{*}RltdPties/{*}DbtrAcct/{*}Id/{*}IBAN'),
                ('camt_creditor_name', './{*}RltdPties/{*}Cdtr//{*}Nm'),
                ('camt_ultimate_creditor_name',
                    './{*}RltdPties/{*}UltmtCdtr//{*}Nm'),
                ('camt_creditor_iban',
                    './{*}RltdPties/{*}CdtrAcct/{*}Id/{*}IBAN'),
                ]:
            value = detail.findtext(path)
            if value:
                information[key] = value
        return information
