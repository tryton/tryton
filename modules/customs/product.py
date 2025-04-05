# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, fields, sequence_ordered
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, Or
from trytond.tools import grouped_slice


class Category(metaclass=PoolMeta):
    __name__ = 'product.category'
    customs = fields.Boolean(
        "Customs",
        states={
            'readonly': Bool(Eval('childs', [0])) | Bool(Eval('parent')),
            })
    tariff_codes_parent = fields.Boolean("Use Parent's Tariff Codes",
        states={
            'invisible': ~Eval('customs', False),
            },
        help='Use the tariff codes defined on the parent category.')
    tariff_codes = fields.One2Many('product-customs.tariff.code',
        'product', "Tariff Codes",
        order=[
            ('sequence', 'ASC NULLS FIRST'),
            ('id', 'ASC'),
            ],
        states={
            'invisible': (Eval('tariff_codes_parent', False)
                | ~Eval('customs', False)),
            })

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.parent.domain = [
            ('customs', '=', Eval('customs', False)),
            cls.parent.domain or []]
        cls.parent.states['required'] = Or(
            cls.parent.states.get('required', False),
            Eval('tariff_codes_parent', False))

    @classmethod
    def default_customs(cls):
        return False

    @classmethod
    def default_tariff_codes_parent(cls):
        return False

    @fields.depends('parent', '_parent_parent.customs', 'customs')
    def on_change_with_customs(self):
        if self.parent:
            return self.parent.customs
        return self.customs

    def get_tariff_codes(self, pattern):
        if not self.tariff_codes_parent:
            for link in self.tariff_codes:
                if link.tariff_code.match(pattern):
                    yield link.tariff_code
        else:
            yield from self.parent.get_tariff_codes(pattern)

    def get_tariff_code(self, pattern):
        try:
            return next(self.get_tariff_codes(pattern))
        except StopIteration:
            pass

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/form/notebook/page[@id="customs"]', 'states', {
                    'invisible': ~Eval('customs', False),
                    }),
            ]

    @classmethod
    def on_delete(cls, categories):
        pool = Pool()
        Product_TariffCode = pool.get('product-customs.tariff.code')

        callback = super().on_delete(categories)

        product_tariffcodes = set()
        products = [str(t) for t in categories]
        for products in grouped_slice(products):
            product_tariffcodes.update(Product_TariffCode.search([
                        'product', 'in', list(products),
                        ]))
        if product_tariffcodes:
            product_tariffcodes = Product_TariffCode.browse(
                product_tariffcodes)
            callback.append(
                lambda: Product_TariffCode.delete(product_tariffcodes))
        return callback


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'
    customs_category = fields.Many2One('product.category', 'Customs Category',
        domain=[
            ('customs', '=', True),
            ],
        states={
            'required': Eval('tariff_codes_category', False),
            })
    tariff_codes_category = fields.Boolean("Use Category's Tariff Codes",
        help='Use the tariff codes defined on the category.')
    tariff_codes = fields.One2Many('product-customs.tariff.code',
        'product', "Tariff Codes",
        order=[
            ('sequence', 'ASC NULLS FIRST'),
            ('id', 'ASC'),
            ],
        states={
            'invisible': ((Eval('type') == 'service')
                | Eval('tariff_codes_category', False)),
            })
    country_of_origin = fields.Many2One(
        'country.country', "Country",
        states={
            'invisible': Eval('type') == 'service',
            },
        help="The country of origin of the product.")

    @classmethod
    def default_tariff_codes_category(cls):
        return False

    def get_tariff_codes(self, pattern):
        if not self.tariff_codes_category:
            for link in self.tariff_codes:
                if link.tariff_code.match(pattern):
                    yield link.tariff_code
        else:
            yield from self.customs_category.get_tariff_codes(pattern)

    def get_tariff_code(self, pattern):
        try:
            return next(self.get_tariff_codes(pattern))
        except StopIteration:
            pass

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('//page[@id="customs"]', 'states', {
                    'invisible': Eval('type') == 'service',
                    }),
            ]

    @classmethod
    def on_delete(cls, templates):
        pool = Pool()
        Product_TariffCode = pool.get('product-customs.tariff.code')

        callback = super().on_delete(templates)

        product_tariffcodes = set()
        products = [str(t) for t in templates]
        for products in grouped_slice(products):
            product_tariffcodes.update(Product_TariffCode.search([
                        'product', 'in', list(products),
                        ]))
        if product_tariffcodes:
            product_tariffcodes = Product_TariffCode.browse(
                product_tariffcodes)
            callback.append(
                lambda: Product_TariffCode.delete(product_tariffcodes))
        return callback


class Product_TariffCode(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'product-customs.tariff.code'
    product = fields.Reference('Product', selection=[
            ('product.template', 'Template'),
            ('product.category', 'Category'),
            ], required=True)
    tariff_code = fields.Many2One('customs.tariff.code', 'Tariff Code',
        required=True, ondelete='CASCADE')
    country = fields.Function(
        fields.Many2One('country.country', "Country"), 'get_tariff_code_field')
    organization = fields.Function(
        fields.Many2One('country.organization', "Organization"),
        'get_tariff_code_field')
    start_day = fields.Function(
        fields.Integer("Start Day"), 'get_tariff_code_field')
    start_month = fields.Function(
        fields.Many2One('ir.calendar.month', "Start Month"),
        'get_tariff_code_field')
    end_day = fields.Function(
        fields.Integer("End Day"), 'get_tariff_code_field')
    end_month = fields.Function(
        fields.Many2One('ir.calendar.month', "End Month"),
        'get_tariff_code_field')

    def get_tariff_code_field(self, name):
        field = getattr(self.__class__, name)
        value = getattr(self.tariff_code, name, None)
        if isinstance(value, ModelSQL):
            if field._type == 'reference':
                return str(value)
            return value.id
        return value

    def get_rec_name(self, name):
        return self.tariff_code.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('tariff_code.rec_name',) + tuple(clause[1:])]


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    def get_tariff_codes(self, pattern):
        yield from self.template.get_tariff_codes(pattern)

    def get_tariff_code(self, pattern):
        return self.template.get_tariff_code(pattern)
