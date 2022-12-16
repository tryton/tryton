# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.modules.company.model import CompanyValueMixin
from trytond.pool import PoolMeta
from trytond.pyson import Eval


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'
    purchase_price_list = fields.MultiValue(fields.Many2One(
            'product.price_list', "Purchase Price List",
            domain=[
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': ~Eval('context', {}).get('company'),
                },
            help="The price list for new purchases."))
    purchase_price_lists = fields.One2Many(
        'party.party.purchase_price_list', 'party', "Purchase Price Lists")


class PartyPurchasePriceList(ModelSQL, CompanyValueMixin):
    "Party Purchase Price List"
    __name__ = 'party.party.purchase_price_list'

    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE', select=True,
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    purchase_price_list = fields.Many2One(
        'product.price_list', "Purchase Price List",
        domain=[
            ('company', '=', Eval('company', -1)),
            ])
