# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)


class Configuration(CompanyMultiValueMixin, metaclass=PoolMeta):
    __name__ = 'sale.configuration'
    sale_price_list = fields.MultiValue(fields.Many2One(
            'product.price_list', "Sale Price List",
            help="The default price list for new parties.",
            domain=[
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': ~Eval('context', {}).get('company'),
                }))


class ConfigurationSalePriceList(ModelSQL, CompanyValueMixin):
    "Sale Configuration Sale PriceList"
    __name__ = 'sale.configuration.sale_price_list'
    sale_price_list = fields.Many2One(
        'product.price_list', "Sale Price List",
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
