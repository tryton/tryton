# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import csv
import io
import re
import zipfile
from collections import defaultdict
from decimal import Decimal
from enum import IntFlag

from sql.operators import Equal

from trytond.model import Exclude, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval

_ACT_FIELDNAMES = [
    'DOCTYPE', 'DBKCODE', 'DBKTYPE', 'DOCNUMBER', 'DOCORDER', 'OPCODE',
    'ACCOUNTGL', 'ACCOUNTRP', 'BOOKYEAR', 'PERIOD', 'DATE', 'DATEDOC',
    'DUEDATE', 'COMMENT', 'COMMENTEXT', 'AMOUNT', 'AMOUNTEUR', 'VATBASE',
    'VATCODE', 'CURRAMOUNT', 'CURRCODE', 'CUREURBASE', 'VATTAX', 'VATIMPUT',
    'CURRATE', 'REMINDLEV', 'MATCHNO', 'OLDDATE', 'ISMATCHED', 'ISLOCKED',
    'ISIMPORTED', 'ISIMPORTED', 'ISTEMP', 'MEMOTYPE', 'ISDOC', 'DOCSTATUS']


def _format_date(date):
    if date:
        return date.strftime('%Y%m%d')
    else:
        return ''


class DOCTYPE(IntFlag):
    CUSTOMER = 1
    SUPPLIER = 2
    GENERAL = 3
    VAT_0 = 4


class DBKTYPE(IntFlag):
    IN_INVOICE = 0
    IN_CREDIT_NOTE = 1
    OUT_INVOICE = 2
    OUT_CREDIT_NOTE = 3
    STATEMENT = 4
    MISC = 5


class Account(metaclass=PoolMeta):
    __name__ = 'account.account'

    winbooks_code = fields.Char("WinBooks Code", size=8)


class FiscalYear(metaclass=PoolMeta):
    __name__ = 'account.fiscalyear'

    winbooks_code = fields.Char("WinBooks Code", size=1)

    @classmethod
    def copy(cls, fiscalyears, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('winbooks_code')
        return super().copy(fiscalyears, default=default)


class RenewFiscalYear(metaclass=PoolMeta):
    __name__ = 'account.fiscalyear.renew'

    def fiscalyear_defaults(self):
        defaults = super().fiscalyear_defaults()
        if self.start.previous_fiscalyear.winbooks_code:
            if self.start.previous_fiscalyear.winbooks_code == '9':
                code = 'A'
            elif self.start.previous_fiscalyear.winbooks_code == 'Z':
                code = None
            else:
                i = ord(self.start.previous_fiscalyear.winbooks_code)
                code = chr(i + 1)
            defaults['winbooks_code'] = code
        return defaults


class Period(metaclass=PoolMeta):
    __name__ = 'account.period'

    @property
    def winbooks_code(self):
        if self.type == 'standard':
            periods = [
                p for p in self.fiscalyear.periods if p.type == self.type]
            i = periods.index(self) + 1
        else:
            middle_year = (
                self.fiscalyear.start_date
                + (self.fiscalyear.end_date
                    - self.fiscalyear.start_date) / 2)
            middle_period = (
                self.start_date + (self.end_date - self.start_date) / 2)
            i = 0 if middle_period < middle_year else 99
        return f'{i:02}'


class Journal(metaclass=PoolMeta):
    __name__ = 'account.journal'

    winbooks_code = fields.Char("WinBooks Code", size=6)
    winbooks_code_credit_note = fields.Char(
        "WinBooks Code Credit Note",
        states={
            'invisible': ~Eval('type').in_(['revenue', 'expense']),
            },
        help="The code to use for credit note.\n"
        "Leave empty to use the default code.")

    def get_winbooks_code(self, dbktype):
        code = self.winbooks_code
        if (dbktype in {DBKTYPE.IN_CREDIT_NOTE, DBKTYPE.OUT_CREDIT_NOTE}
                and self.winbooks_code_credit_note):
            code = self.winbooks_code_credit_note
        return code


class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    @property
    def winbooks_number(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        if isinstance(self.origin, Invoice):
            number = self.origin.number
        else:
            number = self.number
        return re.sub(r'[^0-9]', '', number)


class MoveLine(metaclass=PoolMeta):
    __name__ = 'account.move.line'

    @property
    def winbooks_comment(self):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        if isinstance(self.origin, InvoiceLine):
            comment = self.origin.rec_name
        else:
            comment = self.description_used or self.move_description_used or ''
        return comment


class TaxTemplate(metaclass=PoolMeta):
    __name__ = 'account.tax.template'

    winbooks_code = fields.Char("WinBooks Code", size=8)

    def _get_tax_value(self, tax=None):
        value = super()._get_tax_value(tax=tax)
        if not tax or tax.winbooks_code != self.winbooks_code:
            value['winbooks_code'] = self.winbooks_code
        return value


class Tax(metaclass=PoolMeta):
    __name__ = 'account.tax'

    winbooks_code = fields.Char(
        "WinBooks Code", size=10,
        states={
            'readonly': (
                Bool(Eval('template', -1)
                    & ~Eval('template_override', False))),
            })


class TaxLine(metaclass=PoolMeta):
    __name__ = 'account.tax.line'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('winbooks_tax_move_line_exclude', Exclude(
                    t, (t.move_line, Equal),
                    where=(t.type == 'tax')),
                'account_export_winbooks.'
                'msg_account_tax_line_tax_move_line_unique'),
            ]


class MoveExport(metaclass=PoolMeta):
    __name__ = 'account.move.export'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.type.selection.append(('winbooks', "WinBooks"))

    def get_filename(self, name):
        name = super().get_filename(name)
        if self.type == 'winbooks':
            name = f'{self.rec_name}-winbooks.zip'
        return name

    def _process_winbooks(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as file:
            file.writestr(
                'ACT.txt', self._process_winbooks_act(_ACT_FIELDNAMES))
        self.file = data.getvalue()

    def _process_winbooks_act(
            self, fieldnames, dialect='excel', delimiter=',', **fmtparams):
        data = io.BytesIO()
        writer = csv.DictWriter(
            io.TextIOWrapper(data, encoding='utf-8', write_through=True),
            fieldnames, extrasaction='ignore',
            dialect=dialect, delimiter=delimiter, quoting=csv.QUOTE_ALL,
            **fmtparams)
        writer.writerows(self._process_winbooks_act_rows())
        return data.getvalue()

    def _process_winbooks_act_rows(self):
        for move in self.moves:
            yield from self._process_winbooks_act_move(move)

    def _process_winbooks_act_move(self, move):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        try:
            Statement = pool.get('account.statement')
        except KeyError:
            Statement = None

        bases = defaultdict(Decimal)
        taxes = defaultdict(Decimal)
        for line in move.lines:
            for tax_line in line.tax_lines:
                if tax_line.type == 'base':
                    bases[tax_line.tax] += tax_line.amount
                else:
                    taxes[tax_line.tax] += tax_line.amount
        for line in move.lines:
            dbktype = ''
            if isinstance(move.origin, Invoice):
                invoice = move.origin
                sequence_field = f'{invoice.type}_{invoice.sequence_type}'
                dbktype = getattr(DBKTYPE, sequence_field.upper())
            elif isinstance(move.origin, Statement):
                dbktype = DBKTYPE.STATEMENT
            row = self._process_winbooks_act_line(line)
            move_row = {
                'DBKCODE': move.journal.get_winbooks_code(dbktype),
                'DBKTYPE': int(dbktype),
                'DOCNUMBER': move.winbooks_number,
                'BOOKYEAR': move.period.fiscalyear.winbooks_code,
                'PERIOD': move.period.winbooks_code,
                'DATEDOC': _format_date(move.date),
                }
            row.update(move_row)
            is_credit_note = (
                dbktype in {DBKTYPE.IN_CREDIT_NOTE, DBKTYPE.OUT_CREDIT_NOTE})
            if row['DOCTYPE'] == DOCTYPE.GENERAL:
                vatcode = ''
                vatbase = 0
                tax = None
                for tax_line in line.tax_lines:
                    if (tax_line.type == 'tax'
                            and tax_line.tax.winbooks_code):
                        tax = tax_line.tax
                        vatbase += bases[tax_line.tax]
                        break
                else:
                    tax_line = None
                if tax_line:
                    if taxes[tax] != tax_line.amount:
                        vatbase *= round(tax_line.amount / taxes[tax], 3)
                    vatcode = tax.winbooks_code
                if is_credit_note:
                    vatbase *= -1
                row.setdefault('VATBASE', vatbase)
                row.setdefault('VATCODE', vatcode)

            if row['DOCTYPE'] == DOCTYPE.GENERAL:
                for tax_line in line.tax_lines:
                    tax = tax_line.tax
                    if (tax_line.type == 'base'
                            and tax.type == 'percentage' and not tax.rate):
                        vatcode = tax.winbooks_code
                        vatbase = tax_line.amount
                        if is_credit_note:
                            vatbase *= -1
                        vat_0_row = {
                            'DOCTYPE': int(DOCTYPE.VAT_0),
                            'COMMENT': tax.description,
                            'AMOUNT': 0,
                            'AMOUNTEUR': 0,
                            'VATBASE': vatbase,
                            'VATCODE': vatcode,
                            }
                        vat_0_row.update(move_row)
                        yield vat_0_row
            yield row

    def _process_winbooks_act_line(self, line):
        accountrp = ''
        if line.account.type.receivable and line.party:
            doctype = DOCTYPE.CUSTOMER
            if identifier := line.party.winbooks_customer_identifier:
                accountrp = identifier.code
        elif line.account.type.payable and line.party:
            doctype = DOCTYPE.SUPPLIER
            if identifier := line.party.winbooks_supplier_identifier:
                accountrp = identifier.code
        else:
            doctype = DOCTYPE.GENERAL
        return {
            'DOCTYPE': int(doctype),
            'ACCOUNTGL': (
                line.account.winbooks_code or line.account.code),
            'ACCOUNTRP': accountrp,
            'DUEDATE': _format_date(line.maturity_date),
            'COMMENT': line.winbooks_comment[:40],
            'AMOUNT': 0,
            'AMOUNTEUR': line.debit - line.credit,
            'CURRAMOUNT': line.amount_second_currency,
            'CURRCODE': (
                line.second_currency.code if line.second_currency
                else ''),
            }
