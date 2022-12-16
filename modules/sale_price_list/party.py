# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.model import ModelSQL, fields
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.tools.multivalue import migrate_property
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
        context = Transaction().context
        default = default.copy() if default else {}
        if context.get('_check_access'):
            fields = ['sale_price_lists', 'sale_price_list']
            default_values = cls.default_get(fields, with_rec_name=False)
            for fname in fields:
                default.setdefault(fname, default_values.get(fname))
        return super().copy(parties, default=default)


class PartySalePriceList(ModelSQL, CompanyValueMixin):
    "Party Sale Price List"
    __name__ = 'party.party.sale_price_list'
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE', select=True,
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    sale_price_list = fields.Many2One(
        'product.price_list', "Sale Price List",
        domain=[
            ('company', '=', Eval('company', -1)),
            ])

    @classmethod
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)

        super(PartySalePriceList, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('sale_price_list')
        value_names.append('sale_price_list')
        fields.append('company')
        migrate_property(
            'party.party', field_names, cls, value_names,
            parent='party', fields=fields)
