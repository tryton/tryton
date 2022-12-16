# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval, Not, Equal, Or, Bool
from trytond.pool import PoolMeta, Pool

__all__ = ['Sale', 'SaleLine']


class Sale:
    __metaclass__ = PoolMeta
    __name__ = 'sale.sale'
    price_list = fields.Many2One('product.price_list', 'Price List',
        help="Use to compute the unit price of lines.",
        domain=[('company', '=', Eval('company'))],
        states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('lines', [0]))),
            },
        depends=['state', 'company'])

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()
        cls.party.states['readonly'] = (cls.party.states['readonly']
            | Eval('lines', [0]))
        cls.lines.states['readonly'] = (cls.lines.states['readonly']
            | ~Eval('party'))
        if 'party' not in cls.lines.depends:
            cls.lines.depends.append('party')

    def on_change_party(self):
        pool = Pool()
        Configuration = pool.get('sale.configuration')
        super(Sale, self).on_change_party()
        if self.party and self.party.sale_price_list:
            self.price_list = self.party.sale_price_list
        else:
            config = Configuration(1)
            self.price_list = config.sale_price_list


class SaleLine:
    __metaclass__ = PoolMeta
    __name__ = 'sale.line'

    @classmethod
    def __setup__(cls):
        super(SaleLine, cls).__setup__()
        cls.quantity.on_change.add('_parent_sale.price_list')
        cls.unit.on_change.add('_parent_sale.price_list')
        cls.product.on_change.add('_parent_sale.price_list')
        cls.product.context['price_list'] = Eval(
            '_parent_sale', {}).get('price_list')

    def _get_context_sale_price(self):
        context = super(SaleLine, self)._get_context_sale_price()
        if self.sale and getattr(self.sale, 'price_list', None):
            context['price_list'] = self.sale.price_list.id
        return context
