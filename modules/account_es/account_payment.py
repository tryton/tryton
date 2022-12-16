# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval


class Journal(metaclass=PoolMeta):
    __name__ = 'account.payment.journal'
    es_sepa_bank_account_country_code = fields.Function(
        fields.Char("Bank Account Country Code"),
        'on_change_with_es_sepa_bank_account_country_code')
    es_sepa_request_advancement = fields.Boolean("Request Advancement",
        states={
            'invisible': ((Eval('process_method') != 'sepa')
                | (Eval('es_sepa_bank_account_country_code') != 'ES')),
            },
        depends=['process_method', 'es_sepa_bank_account_country_code'],
        help="Check to receive payments before the payment date.")

    @fields.depends('sepa_bank_account_number')
    def on_change_with_es_sepa_bank_account_country_code(self, name=None):
        if self.sepa_bank_account_number:
            return self.sepa_bank_account_number.number[:2]


class Group(metaclass=PoolMeta):
    __name__ = 'account.payment.group'

    @property
    def sepa_message_id(self):
        message_id = super().sepa_message_id
        if (self.kind == 'receivable'
                and self.journal.es_sepa_request_advancement):
            message_id = 'FSDD%s' % message_id
        return message_id
