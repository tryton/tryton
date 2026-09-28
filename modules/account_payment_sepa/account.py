# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql import Literal
from sql.operators import Exists

from trytond.i18n import gettext
from trytond.model import ModelSQL, fields
from trytond.modules.company.model import CompanyValueMixin
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Id


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'
    sepa_mandate_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "SEPA Mandate Sequence",
            domain=[
                ('sequence_type', '=', Id(
                        'account_payment_sepa', 'sequence_type_mandate')),
                ('company', 'in', [Eval('context', {}).get('company', -1),
                        None]),
                ]))


class ConfigurationSepaMandateSequence(ModelSQL, CompanyValueMixin):
    __name__ = 'account.configuration.sepa_mandate_sequence'
    sepa_mandate_sequence = fields.Many2One(
        'ir.sequence', "SEPA Mandate Sequence",
        domain=[
            ('sequence_type', '=', Id(
                    'account_payment_sepa', 'sequence_type_mandate')),
            ('company', 'in', [Eval('company', -1), None]),
            ])


class MoveLine(metaclass=PoolMeta):
    __name__ = 'account.move.line'

    sepa_mandate_available = fields.Function(fields.Boolean(
            "SEPA Mandate Available"))

    @classmethod
    def column_sepa_mandate_available(cls, tables):
        pool = Pool()
        Move = pool.get('account.move')
        Mandate = pool.get('account.payment.sepa.mandate')
        line, _ = tables[None]
        move_tables = tables.get('move')
        if move_tables is None:
            move = Move.__table__()
            tables['move'] = {
                None: (move, move.id == line.move),
                }
        else:
            move, _ = move_tables[None]
        mandate = Mandate.__table__()
        return Exists(mandate.select(Literal(1),
                where=(mandate.party == line.party)
                & (mandate.company == move.company)
                & (mandate.state == 'validated')))


class InvoicePaymentMean(metaclass=PoolMeta):
    __name__ = 'account.invoice.payment.mean'

    def get_rec_name(self, name):
        name = super().get_rec_name(name)
        if (self.instrument.__name__ == 'party.party.reception_direct_debit'
                and self.instrument.journal.process_method == 'sepa'
                and self.instrument.sepa_mandate):
            mandate = self.instrument.sepa_mandate
            name = gettext(
                'account_payment_sepa.msg_invoice_payment_mean_direct_debit',
                mandate=mandate.identification,
                account_number=mandate.account_number.number)
        return name

    def is_valid_with_payment(self, payment):
        pool = Pool()
        BankAccount = pool.get('bank.account')
        ReceptionDirectDebit = pool.get('party.party.reception_direct_debit')
        valid = super().is_valid_with_payment(payment)
        if payment.journal.process_method == 'sepa':
            if isinstance(self.instrument, BankAccount):
                bank_account = self.instrument
                valid = (
                    payment.sepa_bank_account_number in bank_account.numbers)
            elif isinstance(self.instrument, ReceptionDirectDebit):
                reception = self.instrument
                if reception.journal == payment.journal:
                    if payment.sepa_mandate and reception.sepa_mandate:
                        valid &= payment.sepa_mandate == reception.sepa_mandate
        return valid
