# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.transaction import Transaction


class UNCEFACTInvoice(metaclass=PoolMeta):
    __name__ = 'edocument.uncefact.invoice'

    def render(self, template):
        if Transaction().context.get('account_fr_chorus') and not template:
            template = '16B-CII'
        return super(UNCEFACTInvoice, self).render(template)

    @classmethod
    def party_legal_ids(cls, party, address):
        ids = super(UNCEFACTInvoice, cls).party_legal_ids(party, address)
        if Transaction().context.get('account_fr_chorus') and address:
            ids.append((address.siret, {'schemeID': '1'}))
        return ids
