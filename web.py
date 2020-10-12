# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from sql import Literal
from sql.operators import Equal

from trytond.cache import Cache
from trytond.model import (
    ModelSQL, ModelView, DeactivableMixin, Exclude, fields)
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


class Many2ManyInactive(fields.Many2Many):

    def get(self, ids, model, name, values=None):
        with Transaction().set_context(inactive_test=True):
            return super().get(ids, model, name, values=values)

    def set(self, Model, name, ids, values, *args):
        with Transaction().set_context(inactive_test=True):
            return super().set(Model, name, ids, values, *args)


class Inactivate(ModelSQL, DeactivableMixin):

    @classmethod
    def search_domain(cls, domain, active_test=True, tables=None):
        context = Transaction().context
        if context.get('inactive_test'):
            domain = [domain, ('active', '=', False)]
        return super().search_domain(
            domain, active_test=active_test, tables=tables)

    @classmethod
    def delete(cls, records):
        cls.copy([r for r in records if r.active and r.shop.to_sync],
            default={
                'active': False,
                })
        super().delete(records)


class Shop(DeactivableMixin, ModelSQL, ModelView):
    "Web Shop"
    __name__ = 'web.shop'

    name = fields.Char("Name", required=True)
    company = fields.Many2One('company.company', "Company", required=True)
    currency = fields.Many2One('currency.currency', "Currency", required=True)
    language = fields.Many2One(
        'ir.lang', "Language",
        domain=[
            ('translatable', '=', True),
            ])
    type = fields.Selection([
            (None, ""),
            ], "Type",
        help="The front-end used for the web shop.")
    warehouses = fields.Many2Many(
        'web.shop-stock.location', 'shop', 'warehouse', "Warehouses",
        domain=[
            ('type', '=', 'warehouse'),
            ])
    guest_party = fields.Many2One('party.party', "Guest Party")

    products = fields.Many2Many(
        'web.shop-product.product', 'shop', 'product', "Products",
        domain=[
            ('salable', '=', True),
            ],
        help="The list of products to publish.")
    products_removed = Many2ManyInactive(
        'web.shop-product.product', 'shop', 'product', "Products Removed",
        help="The list of products to unpublish.")

    categories = fields.Many2Many(
        'web.shop-product.category', 'shop', 'category', "Categories",
        help="The list of categories to publish.")
    categories_removed = Many2ManyInactive(
        'web.shop-product.category', 'shop', 'category', "Categories Removed",
        help="The list of categories to unpublish.")

    _name_cache = Cache('web.shop.name', context=False)

    @property
    def warehouse(self):
        if self.warehouses:
            return self.warehouses[0]

    @classmethod
    def __setup__(cls):
        super().__setup__()

        t = cls.__table__()
        cls._sql_constraints = [
            ('name_unique', Exclude(t, (t.name, Equal),
                    where=t.active == Literal(True)),
                'web_shop.msg_shop_name_unique'),
            ]

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_currency(cls):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = cls.default_company()
        if company_id:
            company = Company(company_id)
            return company.currency.id

    @classmethod
    def get(cls, name):
        shop_id = cls._name_cache.get(name)
        if not shop_id:
            shop, = cls.search([('name', '=', name)])
            cls._name_cache.set(name, shop.id)
        else:
            shop = cls(shop_id)
        return shop

    @classmethod
    def write(cls, *args):
        cls._name_cache.clear()
        super().write(*args)

    @classmethod
    def delete(cls, shops):
        cls._name_cache.clear()
        super().delete(shops)

    @property
    def to_sync(self):
        return False

    def _customer_taxe_rule(self):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        config = Configuration(1)
        return config.default_customer_tax_rule

    def get_context(self):
        pool = Pool()
        Date = pool.get('ir.date')
        today = Date.today()
        return {
            'language': self.language.code if self.language else None,
            'company': self.company.id,
            'currency': self.currency.id,
            'locations': [w.id for w in self.warehouses],
            'stock_date_end': today,
            'stock_assign': True,
            }

    def get_products(self, pattern=None):
        "Return the list of products with corresponding prices and taxes"
        pool = Pool()
        Product = pool.get('product.product')
        Tax = pool.get('account.tax')
        if pattern is None:
            pattern = {}

        with Transaction().set_context(**self.get_context()):
            all_products = Product.browse(self.products)

        customer_tax_rule = self._customer_taxe_rule()
        taxes2products = defaultdict(list)
        for product in all_products:
            taxes = []
            for tax in product.customer_taxes_used:
                if customer_tax_rule:
                    tax_ids = customer_tax_rule.apply(tax, pattern)
                    if tax_ids:
                        taxes.extend(tax_ids)
                    continue
                taxes.append(tax.id)
            if customer_tax_rule:
                tax_ids = customer_tax_rule.apply(None, pattern)
                if tax_ids:
                    taxes.extend(tax_ids)
            taxes2products[tuple(taxes)].append(product)

        prices, taxes = {}, {}
        for tax_ids, products in taxes2products.items():
            products = Product.browse(products)
            with Transaction().set_context(taxes=tax_ids):
                prices.update(Product.get_sale_price(products))
            taxes_ = Tax.browse(tax_ids)
            for product in products:
                taxes[product.id] = sum(
                    t['amount']
                    for t in Tax.compute(taxes_, prices[product.id], 1))

        return all_products, prices, taxes

    def get_categories(self):
        "Return the list of categories"
        pool = Pool()
        Category = pool.get('product.category')
        with Transaction().set_context(**self.get_context()):
            return Category.browse(self.categories)

    def get_sale(self, party=None):
        pool = Pool()
        Sale = pool.get('sale.sale')
        if not party:
            party = self.guest_party
        sale = Sale(party=party)
        sale.company = self.company
        sale.currency = self.currency
        sale.warehouse = self.warehouse
        sale.invoice_method = 'order'
        sale.shipment_method = 'order'
        sale.web_shop = self
        sale.on_change_party()
        sale.on_change_web_shop()
        return sale


class Shop_Warehouse(ModelSQL):
    "Web Shop - Warehouse"
    __name__ = 'web.shop-stock.location'

    shop = fields.Many2One(
        'web.shop', "Shop", ondelete='CASCADE', required=True)
    warehouse = fields.Many2One(
        'stock.location', "Warehouse", ondelete='CASCADE', required=True,
        domain=[
            ('type', '=', 'warehouse'),
            ])


class Shop_Product(Inactivate):
    "Web Shop - Product"
    __name__ = 'web.shop-product.product'

    shop = fields.Many2One(
        'web.shop', "Shop", ondelete='CASCADE', required=True)
    product = fields.Many2One(
        'product.product', "Product",
        ondelete='RESTRICT', select=True, required=True)


class Shop_ProductCategory(Inactivate):
    "Web Shop - Product Category"
    __name__ = 'web.shop-product.category'

    shop = fields.Many2One(
        'web.shop', "Shop", ondelete='CASCADE', required=True)
    category = fields.Many2One(
        'product.category', "Category",
        ondelete='RESTRICT', select=True, required=True)


class ShopAttribute(metaclass=PoolMeta):
    __name__ = 'web.shop'

    attributes = fields.Many2Many(
        'web.shop-product.attribute', 'shop', 'attribute', "Attributes",
        help="The list of attributes to publish.")
    attributes_removed = Many2ManyInactive(
        'web.shop-product.attribute', 'shop', 'attribute',
        "Attributes Removed",
        help="The list of attributes to unpublish.")

    def get_attributes(self):
        "Return the list of attributes"
        pool = Pool()
        Attribute = pool.get('product.attribute')
        with Transaction().set_context(**self.get_context()):
            return Attribute.browse(self.attributes)


class Shop_Attribute(Inactivate):
    "Web Shop - Attribute"
    __name__ = 'web.shop-product.attribute'

    shop = fields.Many2One(
        'web.shop', "Shop", ondelete='CASCADE', required=True)
    attribute = fields.Many2One(
        'product.attribute', "Attribute",
        ondelete='RESTRICT', select=True, required=True)


class User(metaclass=PoolMeta):
    __name__ = 'web.user'

    invoice_address = fields.Many2One(
        'party.address', "Invoice Address",
        domain=['OR',
            ('party', '=', Eval('party', -1)),
            ('party', 'in', Eval('secondary_parties', [])),
            ],
        depends=['party', 'secondary_parties'])
    shipment_address = fields.Many2One(
        'party.address', "Shipment Address",
        domain=['OR',
            ('party', '=', Eval('party', -1)),
            ('party', 'in', Eval('secondary_parties', [])),
            ],
        depends=['party', 'secondary_parties'])
