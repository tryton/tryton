# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, fields
from trytond.modules.company.model import CompanyValueMixin
from trytond.pool import Pool, PoolMeta


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    peppol_types = fields.MultiValue(fields.MultiSelection(
            'get_peppol_types', "Peppol Types",
            help="Send the documents to the customer via the Peppol network."))
    peppol = fields.One2Many('party.party.peppol', 'party', "Peppol")

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'peppol_types':
            return pool.get('party.party.peppol')
        return super().multivalue_model(field)

    @classmethod
    def get_peppol_types(cls):
        pool = Pool()
        Peppol = pool.get('edocument.peppol')
        return [
            (v, l) for v, l in Peppol.fields_get(['type'])['type']['selection']
            if v is not None]


class PartyPeppol(ModelSQL, CompanyValueMixin):
    __name__ = 'party.party.peppol'

    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE', required=True)
    peppol_types = fields.MultiSelection('get_peppol_types', "Peppol Types")

    @classmethod
    def get_peppol_types(cls):
        pool = Pool()
        Peppol = pool.get('edocument.peppol')
        return [
            (v, l) for v, l in Peppol.fields_get(['type'])['type']['selection']
            if v is not None]
