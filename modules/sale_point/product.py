# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.modules.company.model import CompanyValueMixin
from trytond.modules.product import price_digits, round_price
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


class _GrossPriceMixin:
    __slots__ = ()

    @fields.depends(
        'gross_price', 'account_category', '_parent_account_category.id',
        methods=['customer_taxes_used'])
    def on_change_gross_price(self):
        pool = Pool()
        Date = pool.get('ir.date')
        Tax = pool.get('account.tax')
        if self.gross_price is None or not self.account_category:
            return
        today = Date.today()
        self.list_price = round_price(Tax.reverse_compute(
                self.gross_price,
                self.customer_taxes_used,
                today))


class Template(_GrossPriceMixin, metaclass=PoolMeta):
    __name__ = 'product.template'

    gross_price = fields.MultiValue(fields.Numeric(
            "Gross Price", digits=price_digits,
            states={
                'invisible': ~Eval('salable', False),
                },
            help="The price with default taxes included."))
    gross_prices = fields.One2Many(
        'product.gross_price', 'template', "Gross Prices")

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'gross_price':
            return pool.get('product.gross_price')
        return super().multivalue_model(field)


class Product(_GrossPriceMixin, metaclass=PoolMeta):
    __name__ = 'product.product'

    gross_price = fields.MultiValue(fields.Numeric(
            "Gross Price", digits=price_digits,
            states={
                'invisible': ~Eval('salable', False),
                },
            help="The price with default taxes included.\n"
            "Leave empty to use the gross price of the product."))
    gross_prices = fields.One2Many(
        'product.gross_price', 'product', "Gross Prices")
    gross_price_used = fields.Function(fields.Numeric(
            "Gross Price", digits=price_digits,
            help="The price with default taxes included."),
        'get_gross_price_used')

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'gross_price':
            return pool.get('product.gross_price')
        return super().multivalue_model(field)

    def set_multivalue(self, name, value, save=True, **pattern):
        if name == 'gross_price':
            pattern.setdefault('template', self.template.id)
        return super().set_multivalue(name, value, save=save, **pattern)

    def get_multivalue(self, name, **pattern):
        if name == 'gross_price':
            pattern.setdefault('template', self.template.id)
        return super().get_multivalue(name, **pattern)

    @fields.depends('_parent_template.id')
    def on_change_gross_price(self):
        return super().on_change_gross_price()

    def get_gross_price_used(self, name):
        gross_price = self.get_multivalue('gross_price')
        if gross_price is None:
            gross_price = self.template.get_multivalue('gross_price')
        return gross_price


class GrossPrice(ModelSQL, CompanyValueMixin):
    __name__ = 'product.gross_price'
    template = fields.Many2One(
        'product.template', "Template", ondelete='CASCADE', required=True,
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])
    product = fields.Many2One(
        'product.product', "Product", ondelete='CASCADE',
        domain=[
            ('template', '=', Eval('template', -1)),
            ],
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])
    gross_price = fields.Numeric("Gross Price", digits=price_digits)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.company.required = True
