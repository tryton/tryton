# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null

from trytond.pool import PoolMeta, Pool
from trytond.model import ModelSQL, ModelView, fields
from trytond.pyson import Eval, Or
from trytond.tools import grouped_slice

__all__ = ['Category', 'Template', 'Product_TariffCode', 'Product']


class Category:
    __metaclass__ = PoolMeta
    __name__ = 'product.category'
    tariff_codes_parent = fields.Boolean("Use Parent's Tariff Codes",
        help='Use the tariff codes defined on the parent category')
    tariff_codes = fields.One2Many('product-customs.tariff.code',
        'product', 'Tariff Codes', order=[('sequence', 'ASC'), ('id', 'ASC')],
        states={
            'invisible': Eval('tariff_codes_parent', False),
            },
        depends=['tariff_codes_parent'])

    @classmethod
    def __setup__(cls):
        super(Category, cls).__setup__()
        cls.parent.states['required'] = Or(
            cls.parent.states.get('required', False),
            Eval('tariff_codes_parent', False))
        cls.parent.depends.append('tariff_codes_parent')

    @classmethod
    def default_tariff_codes_parent(cls):
        return False

    def get_tariff_code(self, pattern):
        if not self.tariff_codes_parent:
            for link in self.tariff_codes:
                if link.tariff_code.match(pattern):
                    return link.tariff_code
        else:
            return self.parent.get_tariff_code(pattern)

    @classmethod
    def delete(cls, categories):
        pool = Pool()
        Product_TariffCode = pool.get('product-customs.tariff.code')
        products = [str(t) for t in categories]

        super(Category, cls).delete(categories)

        for products in grouped_slice(products):
            product_tariffcodes = Product_TariffCode.search([
                    'product', 'in', list(products),
                    ])
            Product_TariffCode.delete(product_tariffcodes)


class Template:
    __metaclass__ = PoolMeta
    __name__ = 'product.template'
    tariff_codes_category = fields.Boolean("Use Category's Tariff Codes",
        help='Use the tariff codes defined on the category')
    tariff_codes = fields.One2Many('product-customs.tariff.code',
        'product', 'Tariff Codes', order=[('sequence', 'ASC'), ('id', 'ASC')],
        states={
            'invisible': ((Eval('type') == 'service') |
                Eval('tariff_codes_category', False)),
            },
        depends=['type', 'tariff_codes_category'])

    @classmethod
    def __setup__(cls):
        super(Template, cls).__setup__()
        cls.category.states['required'] = Or(
            cls.category.states.get('required', False),
            Eval('tariff_codes_category', False))
        cls.category.depends.append('tariff_codes_category')

    @classmethod
    def default_tariff_codes_category(cls):
        return False

    def get_tariff_code(self, pattern):
        if not self.tariff_codes_category:
            for link in self.tariff_codes:
                if link.tariff_code.match(pattern):
                    return link.tariff_code
        else:
            return self.category.get_tariff_code(pattern)

    @classmethod
    def view_attributes(cls):
        return super(Template, cls).view_attributes() + [
            ('//page[@id="customs"]', 'states', {
                    'invisible': Eval('type') == 'service',
                    }),
            ]

    @classmethod
    def delete(cls, templates):
        pool = Pool()
        Product_TariffCode = pool.get('product-customs.tariff.code')
        products = [str(t) for t in templates]

        super(Template, cls).delete(templates)

        for products in grouped_slice(products):
            product_tariffcodes = Product_TariffCode.search([
                    'product', 'in', list(products),
                    ])
            Product_TariffCode.delete(product_tariffcodes)


class Product_TariffCode(ModelSQL, ModelView):
    'Product - Tariff Code'
    __name__ = 'product-customs.tariff.code'
    product = fields.Reference('Product', selection=[
            ('product.template', 'Template'),
            ('product.category', 'Category'),
            ], required=True, select=True)
    tariff_code = fields.Many2One('customs.tariff.code', 'Tariff Code',
        required=True, ondelete='CASCADE')
    sequence = fields.Integer('Sequence')

    @classmethod
    def __setup__(cls):
        super(Product_TariffCode, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    def get_rec_name(self, name):
        return self.tariff_code.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('tariff_code.rec_name',) + tuple(clause[1:])]

    @staticmethod
    def order_sequence(tables):
        table, _ = tables[None]
        return [table.sequence == Null, table.sequence]


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'product.product'
