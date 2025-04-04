# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.modules.company.model import CompanyValueMixin
from trytond.pool import PoolMeta
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
