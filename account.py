# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import csv
from io import StringIO

from sql import Table
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond.config import config
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.model import ModelView, ModelStorage, fields

OPENING_CODE = config.get('account_fr', 'fec_opening_code', default="OUV")
OPENING_NAME = config.get(
    'account_fr', 'fec_opening_name', default="Balance Initiale")
OPENING_NUMBER = config.get('account_fr', 'fec_opening_number', default="0")


class TaxTemplate(metaclass=PoolMeta):
    __name__ = 'account.tax.template'

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        model_data = Table('ir_model_data')

        # Migration from 3.0: new tax rates
        if module_name == 'account_fr':
            for old_id, new_id in (
                    ('tva_vente_19_6', 'tva_vente_taux_normal'),
                    ('tva_vente_7', 'tva_vente_taux_intermediaire'),
                    ('tva_vente_intracommunautaire_19_6',
                        'tva_vente_intracommunautaire_taux_normal'),
                    ('tva_vente_intracommunautaire_7',
                        'tva_vente_intracommunautaire_taux_intermediaire'),
                    ('tva_achat_19_6', 'tva_achat_taux_normal'),
                    ('tva_achat_7', 'tva_achat_taux_intermediaire'),
                    ('tva_achat_intracommunautaire_19_6',
                        'tva_achat_intracommunautaire_taux_normal'),
                    ):
                cursor.execute(*model_data.select(model_data.id,
                        where=(model_data.fs_id == new_id)
                        & (model_data.module == module_name)))
                if cursor.fetchone():
                    continue
                cursor.execute(*model_data.update(
                        columns=[model_data.fs_id],
                        values=[new_id],
                        where=(model_data.fs_id == old_id)
                        & (model_data.module == module_name)))

        super(TaxTemplate, cls).__register__(module_name)


class TaxRuleTemplate(metaclass=PoolMeta):
    __name__ = 'account.tax.rule.template'

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        model_data = Table('ir_model_data')

        if module_name == 'account_fr':
            for old_id, new_id in (
                    ('tax_rule_ventes_intracommunautaires_19_6',
                        'tax_rule_ventes_intracommunautaires_taux_normal'),
                    ('tax_rule_ventes_intracommunautaires_7',
                        'tax_rule_ventes_intracommunautaires_taux'
                        '_intermediaire'),
                    ):
                cursor.execute(*model_data.update(
                        columns=[model_data.fs_id],
                        values=[new_id],
                        where=(model_data.fs_id == old_id)
                        & (model_data.module == module_name)))

        super(TaxRuleTemplate, cls).__register__(module_name)


class FrFEC(Wizard):
    'Generate FEC'
    __name__ = 'account.fr.fec'

    start = StateView('account.fr.fec.start',
        'account_fr.fec_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Generate', 'generate', 'tryton-ok', default=True),
            ])
    generate = StateTransition()
    result = StateView('account.fr.fec.result',
        'account_fr.fec_result_view_form', [
            Button('Close', 'end', 'tryton-close'),
            ])

    def transition_generate(self):
        fec = StringIO()
        writer = self.get_writer(fec)
        writer.writerow(self.get_header())
        format_date = self.get_format_date()
        format_number = self.get_format_number()

        def convert(c):
            delimiter = writer.dialect.delimiter
            return (c or '').replace(delimiter, ' ').replace('\n', ' ')

        for row in self.get_start_balance():
            writer.writerow(map(convert, row))
        for line in self.get_lines():
            row = self.get_row(line, format_date, format_number)
            writer.writerow(map(convert, row))
        value = fec.getvalue()
        if not isinstance(value, bytes):
            value = value.encode('utf-8')
        self.result.file = self.result.__class__.file.cast(value)
        return 'result'

    def default_result(self, fields):
        file_ = self.result.file
        self.result.file = None  # No need to store it in session
        format_date = self.get_format_date()
        if self.start.fiscalyear.state == 'locked':
            filename = '%sFEC%s.csv' % (
                self.start.fiscalyear.company.party.siren or '',
                format_date(self.start.fiscalyear.end_date),
                )
        else:
            filename = None
        return {
            'file': file_,
            'filename': filename,
            }

    def get_writer(self, fd):
        return csv.writer(
            fd, delimiter='\t', doublequote=False, escapechar='\\',
            quoting=csv.QUOTE_NONE)

    def get_format_date(self):
        pool = Pool()
        Lang = pool.get('ir.lang')
        fr = Lang(code='fr_FR', date='%d.%m.%Y')
        return lambda value: fr.strftime(value, '%Y%m%d')

    def get_format_number(self):
        pool = Pool()
        Lang = pool.get('ir.lang')
        fr = Lang(
            decimal_point=',',
            thousands_sep='',
            grouping='[]',
            )
        return lambda value: fr.format('%.2f', value)

    def get_header(self):
        return [
            'JournalCode',
            'JournalLib',
            'EcritureNum',
            'EcritureDate',
            'CompteNum',
            'CompteLib',
            'CompAuxNum',
            'CompAuxLib',
            'PieceRef',
            'PieceDate',
            'EcritureLib',
            'Debit',
            'Credit',
            'EcritureLet',
            'DateLet',
            'ValidDate',
            'Montantdevise',
            'Idevise',
            ]

    def get_start_balance(self):
        pool = Pool()
        Account = pool.get('account.account')
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        FiscalYear = pool.get('account.fiscalyear')
        Period = pool.get('account.period')
        Party = pool.get('party.party')
        account = Account.__table__()
        move = Move.__table__()
        line = Line.__table__()
        period = Period.__table__()
        party = Party.__table__()
        cursor = Transaction().connection.cursor()
        format_date = self.get_format_date()
        format_number = self.get_format_number()

        company = self.start.fiscalyear.company
        fiscalyears = FiscalYear.search([
                ('end_date', '<', self.start.fiscalyear.start_date),
                ('company', '=', company.id),
                ])
        fiscalyear_ids = list(map(int, fiscalyears))
        if not fiscalyear_ids:
            return

        query = (account
            .join(line, condition=line.account == account.id)
            .join(move, condition=line.move == move.id)
            .join(period, condition=move.period == period.id)
            .join(party, 'LEFT', condition=line.party == party.id)
            .select(
                account.id,
                account.code,
                account.name,
                party.code,
                party.name,
                Sum(Coalesce(line.debit, 0) - Coalesce(line.credit, 0)),
                where=(account.company == company.id)
                & (move.state == 'posted')
                & (line.state != 'draft')
                & period.fiscalyear.in_(fiscalyear_ids),
                group_by=[
                    account.id, account.code, account.name,
                    party.code, party.name],
                order_by=account.code))
        cursor.execute(*query)
        for row in cursor:
            _, code, name, party_code, party_name, balance = row
            if not balance:
                continue
            if balance > 0:
                debit, credit = balance, 0
            else:
                debit, credit = 0, -balance
            yield [
                OPENING_CODE,
                OPENING_NAME,
                OPENING_NUMBER,
                format_date(self.start.fiscalyear.start_date),
                code,
                name,
                party_code or '',
                party_name or '',
                '-',
                format_date(self.start.fiscalyear.start_date),
                '-',
                format_number(debit),
                format_number(credit),
                '',
                '',
                format_date(self.start.fiscalyear.start_date),
                '',
                '',
                ]

    def get_lines(self):
        pool = Pool()
        Line = pool.get('account.move.line')

        domain = [
            ('move.period.fiscalyear', '=', self.start.fiscalyear.id),
            ('move.state', '=', 'posted'),
            ['OR', ('debit', '!=', 0), ('credit', '!=', 0)],
            ]
        if self.start.deferral_period:
            domain.append(('move.period', '!=', self.start.deferral_period.id))
        return Line.search(
            domain,
            order=[
                ('move.post_number', 'ASC'),
                ('id', 'ASC'),
                ])

    def get_row(self, line, format_date, format_number):
        def description():
            value = line.move.description or ''
            if line.description:
                if value:
                    value += ' - '
                value += line.description
            return value
        end_date = self.start.fiscalyear.end_date
        reconciliation = None
        if line.reconciliation and line.reconciliation.date <= end_date:
            reconciliation = line.reconciliation
        return [
            line.move.journal.code or line.move.journal.name,
            line.move.journal.name,
            line.move.post_number,
            format_date(line.move.date),
            line.account.code,
            line.account.name,
            line.party.code if line.party else '',
            line.party.name if line.party else '',
            self.get_reference(line) or '-',
            format_date(self.get_reference_date(line)),
            description() or '-',
            format_number(line.debit or 0),
            format_number(line.credit or 0),
            reconciliation.rec_name if reconciliation else '',
            format_date(reconciliation.create_date.date())
            if reconciliation else '',
            format_date(line.move.post_date),
            format_number(line.amount_second_currency)
            if line.amount_second_currency else '',
            line.second_currency.code if line.amount_second_currency else '',
            ]

    def get_reference(self, line):
        if isinstance(line.move.origin, ModelStorage):
            return line.move.origin.rec_name
        return line.move.origin

    def get_reference_date(self, line):
        pool = Pool()
        try:
            Invoice = pool.get('account.invoice')
        except KeyError:
            Invoice = None
        if Invoice and isinstance(line.move.origin, Invoice):
            return line.move.origin.invoice_date
        return line.move.date


class FrFECStart(ModelView):
    'Generate FEC'
    __name__ = 'account.fr.fec.start'

    fiscalyear = fields.Many2One(
        'account.fiscalyear', 'Fiscal Year', required=True)
    type = fields.Selection([
            ('is-bic', 'IS-BIC'),
            ], 'Type', required=True)
    deferral_period = fields.Many2One(
        'account.period', "Deferral Period", required=True,
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ('type', '=', 'adjustment'),
            ],
        depends=['fiscalyear'],
        help="The period to exclude which contains "
        "the moves to balance non-deferral account")

    @classmethod
    def default_type(cls):
        return 'is-bic'


class FrFECResult(ModelView):
    'Generate FEC'
    __name__ = 'account.fr.fec.result'

    file = fields.Binary('File', readonly=True, filename='filename')
    filename = fields.Char('File Name', readonly=True)
