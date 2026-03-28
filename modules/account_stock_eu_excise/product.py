# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import DeactivableMixin, ModelSQL, ModelView, Unique, fields
from trytond.pool import PoolMeta
from trytond.pyson import Bool, Eval, If
from trytond.transaction import Transaction


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    eu_excise_code = fields.Many2One(
        'product.eu.excise_code', "Excise Code",
        states={
            'invisible': Eval('type') != 'goods',
            })
    eu_excise_taxes = fields.One2Many(
        'product-account.stock.eu.excise.tax', 'template', "Excise Tax",
        states={
            'invisible': (
                (Eval('type') != 'goods')
                | ~Eval('eu_excise_code')),
            })

    def get_eu_excise_tax(self, country):
        for line in self.eu_excise_taxes:
            if line.country == country:
                return line.excise_tax

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('//page[@id="eu_excise"]', 'states', {
                    'invisible': Eval('type') != 'goods',
                    }),
            ]


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    def get_eu_excise_tax(self, country):
        return self.template.get_eu_excise_tax(country)


class EUExciseCode(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'product.eu.excise_code'
    _rec_name = 'code'

    code = fields.Char(
        "Code", required=True,
        help="The code from the System for Exchange of Excise Data")
    description = fields.Char('Description', translate=True)

    @classmethod
    def __setup__(cls):
        cls.code.search_unaccented = False
        super().__setup__()
        cls._order.insert(0, ('code', 'ASC'))


class Product_EUExciseTax(ModelSQL, ModelView):
    __name__ = 'product-account.stock.eu.excise.tax'

    template = fields.Many2One(
        'product.template', "Product", required=True, ondelete='CASCADE')
    excise_tax = fields.Many2One(
        'account.stock.eu.excise.tax', "Tax", required=True,
        domain=[
            If(Eval('country'),
                ('country', '=', Eval('country', -1)),
                ()),
            ])
    country = fields.Many2One(
        'country.country', "Country", required=True,
        states={
            'readonly': Bool(Eval('excise_tax')),
            })

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('template')
        t = cls.__table__()
        cls._sql_constraints += [
            ('template_country_unique', Unique(t, t.template, t.country),
                'account_stock_eu_excise.'
                'msg_excise_tax_template_country_unique'),
            ]
        cls._order.insert(0, ('country', None))

    @fields.depends('excise_tax')
    def on_change_excise_tax(self):
        if self.excise_tax:
            self.country = self.excise_tax.country

    @fields.depends('excise_tax')
    def on_change_with_country(self, name=None):
        if self.excise_tax:
            return self.excise_tax.country

    def get_rec_name(self, name):
        return self.excise_tax.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('excise_tax.rec_name', *clause[1:])]


class PriceList(metaclass=PoolMeta):
    __name__ = 'product.price_list'

    def compute(self, product, quantity, uom, pattern=None):
        context = Transaction().context
        pattern = pattern.copy() if pattern is not None else {}
        pattern.setdefault('eu_excise_tax', context.get('eu_excise_tax'))
        pattern.setdefault('eu_excise_duty', context.get('eu_excise_duty'))
        return super().compute(product, quantity, uom, pattern=pattern)


class PriceListLine(metaclass=PoolMeta):
    __name__ = 'product.price_list.line'

    eu_excise_tax = fields.Many2One(
        'account.stock.eu.excise.tax', "Excise Tax")
    eu_excise_duty = fields.Selection([
            (None, ""),
            ('suspension', "Suspension"),
            ], "Excise Duty Suspension")
