# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction


class Party(CompanyMultiValueMixin, metaclass=PoolMeta):
    __name__ = 'party.party'
    sale_price_list = fields.MultiValue(fields.Many2One(
            'product.price_list', "Sale Price List",
            help="The default price list for new sales.",
            domain=[
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': ~Eval('context', {}).get('company'),
                }))
    sale_price_lists = fields.One2Many(
        'party.party.sale_price_list', 'party', "Sale Price Lists")

    @classmethod
    def default_sale_price_list(cls, **pattern):
        pool = Pool()
        Configuration = pool.get('sale.configuration')
        config = Configuration(1)
        price_list = config.get_multivalue('sale_price_list', **pattern)
        return price_list.id if price_list else None

    @classmethod
    def copy(cls, parties, default=None):
        default = default.copy() if default else {}
        if Transaction().check_access:
            fields = ['sale_price_lists', 'sale_price_list']
            default_values = cls.default_get(fields, with_rec_name=False)
            for fname in fields:
                default.setdefault(fname, default_values.get(fname))
        return super().copy(parties, default=default)


class PartySalePriceList(ModelSQL, CompanyValueMixin):
    __name__ = 'party.party.sale_price_list'
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE',
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    sale_price_list = fields.Many2One(
        'product.price_list', "Sale Price List", ondelete='RESTRICT',
        domain=[
            ('company', '=', Eval('company', -1)),
            ])
