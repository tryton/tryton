# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import csv
from io import BytesIO

from sql import Table

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.model import ModelView, fields


__all__ = ['TaxTemplate', 'TaxRuleTemplate',
    'AccountFrFEC', 'AccountFrFECStart', 'AccountFrFECResult']
__metaclass__ = PoolMeta


class TaxTemplate:
    __name__ = 'account.tax.template'

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
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


class TaxRuleTemplate:
    __name__ = 'account.tax.rule.template'

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        model_data = Table('ir_model_data')

        if module_name == 'account_fr':
            for old_id, new_id in (
                    ('tax_rule_ventes_intracommunautaires_19_6',
                        'tax_rule_ventes_intracommunautaires_taux_normal'),
                    ('tax_rule_ventes_intracommunautaires_7',
                        'tax_rule_ventes_intracommunautaires_taux_intermediaire'),
                    ):
                cursor.execute(*model_data.update(
                        columns=[model_data.fs_id],
                        values=[new_id],
                        where=(model_data.fs_id == old_id)
                        & (model_data.module == module_name)))

        super(TaxRuleTemplate, cls).__register__(module_name)


class AccountFrFEC(Wizard):
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
        fec = BytesIO()
        writer = self.get_writer(fec)
        format_date = self.get_format_date()
        format_number = self.get_format_number()
        for row in self.get_start_balance():
            writer.writerow([(c or '').encode('utf-8') for c in row])
        for line in self.get_lines():
            row = self.get_row(line, format_date, format_number)
            writer.writerow([(c or '').encode('utf-8') for c in row])
        self.result.file = fec.getvalue()
        return 'result'

    def default_result(self, fields):
        file_ = self.result.file
        self.result.file = None  # No need to store it in session
        format_date = self.get_format_date()
        filename = '%sFEC%s.csv' % (
            self.start.fiscalyear.company.party.siren or '',
            format_date(self.start.fiscalyear.end_date),
            )
        return {
            'file': file_,
            'filename': filename,
            }

    def get_writer(self, fd):
        return csv.writer(fd)

    def get_format_date(self):
        pool = Pool()
        Lang = pool.get('ir.lang')
        return lambda value: Lang.strftime(value, 'fr_FR', '%Y%m%d')

    def get_format_number(self):
        pool = Pool()
        Lang = pool.get('ir.lang')
        fr = Lang(
            decimal_point=',',
            thousands_sep='',
            grouping='[]',
            )
        return lambda value: Lang.format(fr, '%.2f', value)

    def get_start_balance(self):
        pool = Pool()
        Account = pool.get('account.account')
        format_date = self.get_format_date()
        format_number = self.get_format_number()

        with Transaction().set_context(
                periods=[-1],
                fiscalyear=self.start.fiscalyear.id,
                posted=True,
                cumulate=True):
            accounts = Account.search([])

        for account in accounts:
            if account.credit == account.debit:
                continue
            if account.debit > account.credit:
                debit, credit = account.debit - account.credit, 0
            else:
                debit, credit = 0, account.debit - account.credit
            yield [
                self.start.deferral_journal.code
                or self.start.deferral_journal.name,
                self.start.deferral_journal.name,
                self.start.deferral_post_number,
                format_date(self.start.fiscalyear.start_date),
                account.code,
                account.name,
                '',
                '',
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

        return Line.search([
                ('move.period.fiscalyear', '=', self.start.fiscalyear.id),
                ('move.state', '=', 'posted'),
                ],
            order=[
                ('move.post_number', 'ASC'),
                ])

    def get_row(self, line, format_date, format_number):
        def description():
            value = line.move.description or ''
            if line.description:
                if value:
                    value += ' - '
                value += line.description
            return value
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
            line.reconciliation.rec_name if line.reconciliation else '',
            format_date(line.reconciliation.create_date)
            if line.reconciliation else '',
            format_date(line.move.post_date),
            format_number(line.amount_second_currency)
            if line.amount_second_currency else '',
            line.second_currency.code if line.amount_second_currency else '',
            ]

    def get_reference(self, line):
        pool = Pool()
        try:
            Invoice = pool.get('account.invoice')
        except KeyError:
            Invoice = None
        if not line.move.origin:
            return ''
        if Invoice and isinstance(line.move.origin, Invoice):
            return line.move.origin.number
        return line.move.origin.rec_name

    def get_reference_date(self, line):
        pool = Pool()
        try:
            Invoice = pool.get('account.invoice')
        except KeyError:
            Invoice = None
        if Invoice and isinstance(line.move.origin, Invoice):
            return line.move.origin.invoice_date
        return line.move.post_date


class AccountFrFECStart(ModelView):
    'Generate FEC'
    __name__ = 'account.fr.fec.start'

    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
        required=True, domain=[
            ('state', '=', 'close'),
            ])
    type = fields.Selection([
            ('is-bic', 'IS-BIC'),
            ], 'Type', required=True)
    deferral_journal = fields.Many2One('account.journal',
        'Deferral Journal', required=True,
        help='Journal used for pseudo deferral move')
    deferral_post_number = fields.Char('Deferral Number', required=True,
        help='Post number used for pseudo deferral move')

    @classmethod
    def default_type(cls):
        return 'is-bic'

    @classmethod
    def default_deferral_post_number(cls):
        return '0'


class AccountFrFECResult(ModelView):
    'Generate FEC'
    __name__ = 'account.fr.fec.result'

    file = fields.Binary('File', readonly=True, filename='filename')
    filename = fields.Char('File Name', readonly=True)
