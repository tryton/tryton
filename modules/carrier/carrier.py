# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import (
    ModelView, ModelSQL, DeactivableMixin, MatchMixin, fields,
    sequence_ordered)
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.cache import Cache


class Carrier(DeactivableMixin, ModelSQL, ModelView):
    'Carrier'
    __name__ = 'carrier'
    party = fields.Many2One('party.party', 'Party', required=True,
            ondelete='CASCADE', help="The party which represents the carrier.")
    carrier_product = fields.Many2One('product.product', 'Carrier Product',
            required=True, domain=[
                ('type', '=', 'service'),
                ('template.type', '=', 'service'),
            ], help="The product to invoice the carrier service.")
    carrier_cost_method = fields.Selection([
        ('product', 'Product Price'),
        ], 'Carrier Cost Method', required=True,
        help='Method to compute carrier cost.')
    selections = fields.One2Many('carrier.selection', 'carrier', "Selections")

    @staticmethod
    def default_carrier_cost_method():
        return 'product'

    def get_rec_name(self, name):
        return '%s - %s' % (self.party.rec_name, self.carrier_product.rec_name)

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('party.rec_name',) + tuple(clause[1:]),
            ('carrier_product.rec_name',) + tuple(clause[1:]),
            ]

    def get_sale_price(self):
        'Compute carrier sale price with currency'
        pool = Pool()
        Company = pool.get('company.company')
        if self.carrier_cost_method == 'product':
            list_price = self.carrier_product.list_price_used
            if list_price is not None:
                company = Company(self.carrier_product._context['company'])
                return list_price, company.currency.id
        return 0, None

    def get_purchase_price(self):
        'Compute carrier purchase price with currency'
        pool = Pool()
        Company = pool.get('company.company')
        if self.carrier_cost_method == 'product':
            cost_price = self.carrier_product.cost_price
            if cost_price is not None:
                company = Company(self.carrier_product._context['company'])
                return cost_price, company.currency.id
        return 0, None

    @classmethod
    def create(cls, *args, **kwargs):
        pool = Pool()
        CarrierSelection = pool.get('carrier.selection')
        carriers = super(Carrier, cls).create(*args, **kwargs)
        CarrierSelection._get_carriers_cache.clear()
        return carriers

    @classmethod
    def delete(cls, *args, **kwargs):
        pool = Pool()
        CarrierSelection = pool.get('carrier.selection')
        super(Carrier, cls).delete(*args, **kwargs)
        CarrierSelection._get_carriers_cache.clear()


class Selection(
        DeactivableMixin, sequence_ordered(), MatchMixin, ModelSQL, ModelView):
    'Carrier Selection'
    __name__ = 'carrier.selection'
    _get_carriers_cache = Cache(
        'carrier.selection.get_carriers', context=False)

    from_country = fields.Many2One('country.country', 'From Country',
        ondelete='RESTRICT',
        help="Apply only when shipping from this country.\n"
        "Leave empty for any countries.")
    to_country = fields.Many2One('country.country', 'To Country',
        ondelete='RESTRICT',
        help="Apply only when shipping to this country.\n"
        "Leave empty for any countries.")
    carrier = fields.Many2One('carrier', 'Carrier', required=True,
        ondelete='CASCADE', help="The selected carrier.")

    @classmethod
    def create(cls, *args, **kwargs):
        selections = super().create(*args, **kwargs)
        cls._get_carriers_cache.clear()
        return selections

    @classmethod
    def write(cls, *args, **kwargs):
        super().write(*args, **kwargs)
        cls._get_carriers_cache.clear()

    @classmethod
    def delete(cls, *args, **kwargs):
        super().delete(*args, **kwargs)
        cls._get_carriers_cache.clear()

    @classmethod
    def get_carriers(cls, pattern):
        pool = Pool()
        Carrier = pool.get('carrier')

        key = tuple(sorted(pattern.items()))
        carriers = cls._get_carriers_cache.get(key)
        if carriers is not None:
            return Carrier.browse(carriers)

        carriers = []
        selections = cls.search([])
        if not selections:
            with Transaction().set_context(active_test=False):
                carriers = Carrier.search([])
        else:
            for selection in selections:
                if (selection.match(pattern)
                        and selection.carrier not in carriers):
                    carriers.append(selection.carrier)

        cls._get_carriers_cache.set(key, list(map(int, carriers)))
        return carriers
