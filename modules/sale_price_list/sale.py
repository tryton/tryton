# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Equal, Eval, Not, Or


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'
    price_list = fields.Many2One('product.price_list', 'Price List',
        help="Use to compute the unit price of lines.",
        domain=[('company', '=', Eval('company'))],
        states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('lines', [0]))),
            })

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()
        cls.party.states['readonly'] = (cls.party.states['readonly']
            | Eval('lines', [0]))
        cls.lines.states['readonly'] = (cls.lines.states['readonly']
            | ~Eval('party') | ~Eval('company'))

    @fields.depends('company')
    def on_change_party(self):
        pool = Pool()
        Configuration = pool.get('sale.configuration')
        super(Sale, self).on_change_party()
        if self.party and self.party.sale_price_list:
            self.price_list = self.party.sale_price_list
        else:
            config = Configuration(1)
            self.price_list = config.get_multivalue(
                'sale_price_list',
                company=self.company.id if self.company else None)

    @fields.depends('party')
    def on_change_company(self):
        pool = Pool()
        Configuration = pool.get('sale.configuration')
        super().on_change_company()
        if self.party and self.party.sale_price_list:
            self.price_list = self.party.sale_price_list
        else:
            config = Configuration(1)
            self.price_list = config.get_multivalue(
                'sale_price_list',
                company=self.company.id if self.company else None)


class Line(metaclass=PoolMeta):
    __name__ = 'sale.line'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.product.context['price_list'] = Eval(
            '_parent_sale', {}).get('price_list')

    @fields.depends('sale', '_parent_sale.price_list')
    def _get_context_sale_price(self):
        context = super()._get_context_sale_price()
        if self.sale:
            if getattr(self.sale, 'price_list', None):
                context['price_list'] = self.sale.price_list.id
        return context
