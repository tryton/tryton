# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import fields, ModelSQL
from trytond.pool import PoolMeta, Pool
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)

from trytond.modules.party.exceptions import EraseError


class Party(CompanyMultiValueMixin, metaclass=PoolMeta):
    __name__ = 'party.party'
    customer_code = fields.MultiValue(fields.Char('Customer Code',
            help="The code the party as supplier has assigned to the company"
            " as customer."))
    customer_codes = fields.One2Many(
        'party.party.customer_code', 'party', "Customer Codes")

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'customer_code':
            return pool.get('party.party.customer_code')
        return super().multivalue_model(field)


class CustomerCode(ModelSQL, CompanyValueMixin):
    "Party Customer Code"
    __name__ = 'party.party.customer_code'
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE', select=True)
    customer_code = fields.Char('Customer Code')


class PartyReplace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('purchase.product_supplier', 'party'),
            ('purchase.purchase', 'party'),
            ('purchase.purchase', 'invoice_party'),
            ]


class PartyErase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def check_erase_company(self, party, company):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        super(PartyErase, self).check_erase_company(party, company)

        purchases = Purchase.search([
                ('party', '=', party.id),
                ('company', '=', company.id),
                ('state', 'not in', ['done', 'cancelled']),
                ])
        if purchases:
            raise EraseError(
                gettext('purchase.msg_erase_party_pending_purchase',
                    party=party.rec_name,
                    company=company.rec_name))
