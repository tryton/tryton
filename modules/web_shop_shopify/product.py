# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import re
from decimal import Decimal
from urllib.parse import urljoin

import shopify
from sql.conditionals import NullIf
from sql.operators import Equal

from trytond.i18n import gettext
from trytond.model import Exclude, ModelSQL, ModelView, fields
from trytond.modules.product.exceptions import TemplateValidationError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, If
from trytond.tools import grouped_slice, slugify
from trytond.transaction import Transaction

from . import graphql
from .common import IdentifiersMixin, IdentifiersUpdateMixin, id2gid

QUERY_COLLECTION = '''\
query GetCollection($id: ID!) {
    collection(id: $id) %(fields)s
}'''

QUERY_PRODUCT = '''\
query GetProduct($id: ID!) {
    product(id: $id) %(fields)s
}'''

QUERY_VARIANT = '''\
query GetProductVariant($id: ID!) {
    productVariant(id: $id) %(fields)s
}'''


class Category(IdentifiersMixin, metaclass=PoolMeta):
    __name__ = 'product.category'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._shopify_fields.add('name')

    def get_shopify(self, shop):
        shopify_id = self.get_shopify_identifier(shop)
        if shopify_id:
            shopify_id = id2gid('Collection', shopify_id)
            collection = shopify.GraphQL().execute(
                QUERY_COLLECTION % {
                    'fields': graphql.selection({
                            'id': None,
                            }),
                    }, {'id': shopify_id})['data']['collection'] or {}
        else:
            collection = {}
        collection['title'] = self.name[:255]
        collection['metafields'] = metafields = []
        managed_metafields = shop.managed_metafields()
        for key, value in self.get_shopify_metafields(shop).items():
            if key not in managed_metafields:
                continue
            namespace, key = key.split('.', 1)
            metafields.append({
                    'namespace': namespace,
                    'key': key,
                    'value': value,
                    })
        return collection

    def get_shopify_metafields(self, shop):
        return {}


class TemplateCategory(IdentifiersUpdateMixin, metaclass=PoolMeta):
    __name__ = 'product.template-product.category'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._shopify_fields.update(['template', 'category'])

    @classmethod
    def get_shopify_identifier_to_update(cls, records):
        return sum((list(r.template.shopify_identifiers) for r in records), [])


class Template(IdentifiersMixin, metaclass=PoolMeta):
    __name__ = 'product.template'

    shopify_uom = fields.Many2One(
        'product.uom', "Shopify UoM",
        states={
            'readonly': Bool(Eval('shopify_identifiers', [-1])),
            'invisible': ~Eval('salable', False),
            },
        help="The Unit of Measure of the product on Shopify.")
    shopify_handle = fields.Char(
        "Shopify Handle",
        states={
            'invisible': ~Eval('salable', False),
            },
        help="The string that's used to identify the product in URLs.\n"
        "Leave empty to let Shopify generate one.")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('shopify_handle_unique',
                Exclude(t,
                    (NullIf(t.shopify_handle, ''), Equal)),
                'web_shop_shopify.msg_template_shopify_handle_unique'),
            ]
        cls._shopify_fields.update([
                'name', 'web_shop_description', 'attribute_set',
                'customs_category', 'tariff_codes_category',
                'country_of_origin', 'weight', 'weight_uom'])
        categories = cls._shopify_uom_categories()
        cls.shopify_uom.domain = [
            ('category', 'in', [Eval(c, -1) for c in categories]),
            ('digits', '=', 0),
            ]

    @classmethod
    def _shopify_uom_categories(cls):
        return ['default_uom_category']

    def get_shopify_uom(self):
        return self.sale_uom

    @classmethod
    def get_shopify_identifier_to_update(cls, templates):
        pool = Pool()
        Product = pool.get('product.product')
        products = [p for t in templates for p in t.products]
        return (super().get_shopify_identifier_to_update(templates)
            + Product.get_shopify_identifier_to_update(products))

    def get_shopify(self, shop, categories):
        shopify_id = self.get_shopify_identifier(shop)
        product = {}
        if shopify_id:
            shopify_id = id2gid('Product', shopify_id)
            product = shopify.GraphQL().execute(
                QUERY_PRODUCT % {
                    'fields': graphql.selection({
                            'id': None,
                            'status': None,
                            }),
                    }, {'id': shopify_id})['data']['product'] or {}
            if product.get('status') == 'ARCHIVED':
                product['status'] = 'ACTIVE'
        product['title'] = self.name
        if self.web_shop_description:
            product['descriptionHtml'] = self.web_shop_description
        if self.shopify_handle:
            product['handle'] = self.shopify_handle

        product['productOptions'] = options = []
        for i, attribute in enumerate(self.shopify_attributes, 1):
            values = set()
            for p in self.products:
                if p.attributes and attribute.name in p.attributes:
                    values.add(p.attributes.get(attribute.name))
            values = [
                {'name': attribute.format(value)}
                for value in sorted(values)]
            options.append({
                    'name': attribute.string,
                    'position': i,
                    'values': values,
                    })

        product['collections'] = collections = []
        for category in categories:
            if collection_id := category.get_shopify_identifier(shop):
                collections.append(id2gid(
                        'Collection', collection_id))

        product['metafields'] = metafields = []
        managed_metafields = shop.managed_metafields()
        for key, value in self.get_shopify_metafields(shop).items():
            if key not in managed_metafields:
                continue
            namespace, key = key.split('.', 1)
            metafields.append({
                    'namespace': namespace,
                    'key': key,
                    **value
                    })
        return product

    def get_shopify_metafields(self, shop):
        return {}

    @property
    def shopify_attributes(self):
        if not self.attribute_set:
            return []
        return filter(None, [
                self.attribute_set.shopify_option1,
                self.attribute_set.shopify_option2,
                self.attribute_set.shopify_option3])

    @classmethod
    def validate_fields(cls, templates, field_names):
        super().validate_fields(templates, field_names)
        cls.check_shopify_handle(templates, field_names)

    @classmethod
    def check_shopify_handle(cls, templates, field_names):
        if field_names and 'shopify_handle' not in field_names:
            return
        for template in templates:
            if (template.shopify_handle
                    and not re.fullmatch(
                        r'[a-z0-9-]+', template.shopify_handle)):
                raise TemplateValidationError(gettext(
                        'web_shop_shopify.msg_template_shopify_handle_invalid',
                        template=template.rec_name,
                        handle=template.shopify_handle,
                        ))


class Template_SaleSecondaryUnit(metaclass=PoolMeta):
    __name__ = 'product.template'

    @classmethod
    def _shopify_uom_categories(cls):
        return super()._shopify_uom_categories() + [
            'sale_secondary_uom_category']

    def get_shopify_uom(self):
        uom = super().get_shopify_uom()
        if self.sale_secondary_uom and not self.sale_secondary_uom.digits:
            uom = self.sale_secondary_uom
        return uom


class Product(IdentifiersMixin, metaclass=PoolMeta):
    __name__ = 'product.product'

    shopify_sku = fields.Function(
        fields.Char("SKU"), 'get_shopify_sku', searcher='search_shopify_sku')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._shopify_fields.update(['code', 'attributes', 'position'])

    @classmethod
    def get_shopify_identifier_to_update(cls, records):
        pool = Pool()
        InventoryItem = pool.get('product.shopify_inventory_item')
        items = InventoryItem.browse(records)
        return (super().get_shopify_identifier_to_update(records)
            + sum((list(i.shopify_identifiers) for i in items), []))

    def set_shopify_identifier(self, web_shop, identifier=None):
        pool = Pool()
        InventoryItem = pool.get('product.shopify_inventory_item')
        if not identifier:
            inventory_item = InventoryItem(self.id)
            inventory_item.set_shopify_identifier(web_shop)
        return super().set_shopify_identifier(web_shop, identifier=identifier)

    def get_shopify_sku(self, name):
        return self.code

    @classmethod
    def search_shopify_sku(cls, name, clause):
        return [('code',) + tuple(clause[1:])]

    def get_shopify(
            self, shop, sale_price, sale_tax, price, tax,
            shop_taxes_included=True):
        shopify_id = self.get_shopify_identifier(shop)
        if shopify_id:
            shopify_id = id2gid('ProductVariant', shopify_id)
            variant = shopify.GraphQL().execute(
                QUERY_VARIANT % {
                    'fields': graphql.selection({
                            'id': None,
                            }),
                    }, {'id': shopify_id})['data']['productVariant'] or {}
        else:
            variant = {}
        sale_price = self.shopify_price(
            sale_price, sale_tax, taxes_included=shop_taxes_included)
        if sale_price is not None:
            variant['price'] = str(sale_price.quantize(Decimal('.00')))
        else:
            variant['price'] = None
        price = self.shopify_price(
            price, tax, taxes_included=shop_taxes_included)
        if price is not None:
            variant['compareAtPrice'] = str(
                price.quantize(Decimal('.00')))
        else:
            variant['compareAtPrice'] = None
        variant['taxable'] = bool(sale_tax)

        for identifier in self.identifiers:
            if identifier.type == 'ean':
                variant['barcode'] = identifier.code
                break

        variant['optionValues'] = options = []
        attributes = self.attributes or {}
        for attribute in self.template.shopify_attributes:
            value = attributes.get(attribute.name)
            value = attribute.format(value)
            options.append({
                    'optionName': attribute.string,
                    'name': value,
                    })

        variant['metafields'] = metafields = []
        managed_metafields = shop.managed_metafields()
        for key, value in self.get_shopify_metafields(shop).items():
            if key not in managed_metafields:
                continue
            namespace, key = key.split('.', 1)
            metafields.append({
                    'namespace': namespace,
                    'key': key,
                    'value': value,
                    })
        return variant

    def get_shopify_metafields(self, shop):
        return {}

    def shopify_price(self, price, tax, taxes_included=True):
        pool = Pool()
        Uom = pool.get('product.uom')
        if price is None or tax is None:
            return None
        if taxes_included:
            price += tax
        return Uom.compute_price(
            self.sale_uom, price, self.shopify_uom,
            factor=self.shopify_uom_factor, rate=self.shopify_uom_rate)

    @property
    def shopify_uom_factor(self):
        return None

    @property
    def shopify_uom_rate(self):
        return None

    @property
    def shopify_quantity(self):
        pool = Pool()
        Uom = pool.get('product.uom')
        quantity = self.forecast_quantity
        if quantity < 0:
            quantity = 0
        return Uom.compute_qty(
            self.default_uom, quantity, self.shopify_uom, round=True,
            factor=self.shopify_uom_factor, rate=self.shopify_uom_rate)


class ProductURL(metaclass=PoolMeta):
    __name__ = 'product.web_shop_url'

    def get_url(self, name):
        url = super().get_url(name)
        if (self.shop.type == 'shopify'
                and (handle := self.product.template.shopify_handle)):
            url = urljoin(self.shop.shopify_url + '/', f'products/{handle}')
        return url


class ShopifyInventoryItem(IdentifiersMixin, ModelSQL, ModelView):
    __name__ = 'product.shopify_inventory_item'

    product = fields.Function(
        fields.Many2One('product.product', "Product"), 'get_product')

    @classmethod
    def table_query(cls):
        return Pool().get('product.product').__table__()

    def get_product(self, name):
        return self.id

    def get_shopify(self, shop, shop_weight_unit=None):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        ModelData = pool.get('ir.model.data')
        Uom = pool.get('product.uom')

        movable_types = SaleLine.movable_types()

        inventory_item = {}
        inventory_item['sku'] = self.product.shopify_sku
        inventory_item['tracked'] = (
            self.product.type in movable_types and not self.product.consumable)
        inventory_item['requiresShipping'] = (
            self.product.type in movable_types)

        if getattr(self.product, 'weight', None) and shop_weight_unit:
            units = {}
            units['KILOGRAMS'] = ModelData.get_id('product', 'uom_kilogram')
            units['GRAMS'] = ModelData.get_id('product', 'uom_gram')
            units['POUNDS'] = ModelData.get_id('product', 'uom_pound')
            units['OUNCES'] = ModelData.get_id('product', 'uom_ounce')
            weight = self.product.weight
            weight_unit = self.product.weight_uom
            if self.product.weight_uom.id not in units.values():
                weight_unit = Uom(units[shop_weight_unit])
                weight = Uom.compute_qty(
                    self.product.weight_uom, weight, weight_unit)
            weight_unit = {
                v: k for k, v in units.items()}[weight_unit.id]
            inventory_item['measurement'] = {
                'weight': {
                    'unit': weight_unit,
                    'value': weight,
                    },
                }

        return inventory_item


class ShopifyInventoryItem_Customs(metaclass=PoolMeta):
    __name__ = 'product.shopify_inventory_item'

    def get_shopify(self, shop, shop_weight_unit=None):
        pool = Pool()
        Date = pool.get('ir.date')
        inventory_item = super().get_shopify(
            shop, shop_weight_unit=shop_weight_unit)
        with Transaction().set_context(company=shop.company.id):
            today = Date.today()
        inventory_item['countryCodeOfOrigin'] = (
            self.product.country_of_origin.code
            if self.product.country_of_origin else None)
        tariff_code = self.product.get_tariff_code(
            {'date': today, 'country': None})
        inventory_item['harmonizedSystemCode'] = (
            tariff_code.code if tariff_code else None)
        country_harmonized_system_codes = []
        countries = set()
        for tariff_code in self.product.get_tariff_codes({'date': today}):
            if (tariff_code.country
                    and tariff_code.country not in countries):
                country_harmonized_system_codes.append({
                        'harmonizedSystemCode': tariff_code.code,
                        'countryCode': tariff_code.country.code,
                        })
                countries.add(tariff_code.country)
        inventory_item['countryHarmonizedSystemCodes'] = (
            country_harmonized_system_codes)
        return inventory_item


class Product_TariffCode(IdentifiersUpdateMixin, metaclass=PoolMeta):
    __name__ = 'product-customs.tariff.code'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._shopify_fields.update(['product', 'tariff_code'])

    @classmethod
    def get_shopify_identifier_to_update(cls, records):
        pool = Pool()
        Template = pool.get('product.template')
        Category = pool.get('product.category')
        templates = set()
        categories = set()
        for record in records:
            if isinstance(record.product, Template):
                templates.add(record.product)
            elif isinstance(record.product, Category):
                categories.add(record.product)
        if categories:
            for sub_categories in grouped_slice(list(categories)):
                templates.update(Template.search([
                            ('customs_category', 'in',
                                [c.id for c in sub_categories]),
                            ]))
        templates = Template.browse(list(templates))
        return Template.get_shopify_identifier_to_update(templates)


class ProductIdentifier(IdentifiersUpdateMixin, metaclass=PoolMeta):
    __name__ = 'product.identifier'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._shopify_fields.update(['product', 'code'])

    @classmethod
    def get_shopify_identifier_to_update(cls, identifiers):
        return sum((
                list(i.product.shopify_identifiers) for i in identifiers), [])


class Product_SaleSecondaryUnit(metaclass=PoolMeta):
    __name__ = 'product.product'

    @property
    def shopify_uom_factor(self):
        factor = super().shopify_uom_factor
        if (self.sale_secondary_uom
                and self.shopify_uom.category
                == self.sale_secondary_uom.category):
            factor = self.sale_secondary_uom_normal_factor
        return factor

    @property
    def shopify_uom_rate(self):
        rate = super().shopify_uom_rate
        if (self.sale_secondary_uom
                and self.shopify_uom.category
                == self.sale_secondary_uom.category):
            rate = self.sale_secondary_uom_normal_rate
        return rate


class AttributeSet(IdentifiersUpdateMixin, metaclass=PoolMeta):
    __name__ = 'product.attribute.set'

    shopify_option1 = fields.Many2One(
        'product.attribute', "Option 1",
        domain=[
            ('id', 'in', Eval('attributes', [])),
            If(Eval('shopify_option2'),
                ('id', '!=', Eval('shopify_option2')),
                ()),
            If(Eval('shopify_option3'),
                ('id', '!=', Eval('shopify_option3')),
                ()),
            ])
    shopify_option2 = fields.Many2One(
        'product.attribute', "Option 2",
        domain=[
            ('id', 'in', Eval('attributes', [])),
            If(Eval('shopify_option1'),
                ('id', '!=', Eval('shopify_option1')),
                ('id', '=', None)),
            If(Eval('shopify_option3'),
                ('id', '!=', Eval('shopify_option3')),
                ()),
            ],
        states={
            'invisible': ~Eval('shopify_option1'),
            })
    shopify_option3 = fields.Many2One(
        'product.attribute', "Option 3",
        domain=[
            ('id', 'in', Eval('attributes', [])),
            If(Eval('shopify_option1'),
                ('id', '!=', Eval('shopify_option1')),
                ()),
            If(Eval('shopify_option2'),
                ('id', '!=', Eval('shopify_option2')),
                ('id', '=', None)),
            ],
        states={
            'invisible': ~Eval('shopify_option2'),
            })

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._shopify_fields.update(
            ['shopify_option1', 'shopify_option2', 'shopify_option3'])

    @classmethod
    def get_shopify_identifier_to_update(cls, sets):
        pool = Pool()
        Template = pool.get('product.template')
        templates = []
        for sub_sets in grouped_slice(sets):
            templates.extend(Template.search([
                        ('attribute_set', 'in', [s.id for s in sub_sets]),
                        ]))
        return Template.get_shopify_identifier_to_update(templates)


class Attribute(IdentifiersUpdateMixin, metaclass=PoolMeta):
    __name__ = 'product.attribute'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._shopify_fields.add('selection')
        domain = [
            ('type', '!=', 'shopify'),
            ]
        if cls.web_shops.domain:
            cls.web_shops.domain = [cls.web_shops.domain, domain]
        else:
            cls.web_shops.domain = domain

    @classmethod
    def get_shopify_identifier_to_update(cls, attributes):
        pool = Pool()
        Set = pool.get('product.attribute.set')
        sets = Set.browse(sum((a.sets for a in attributes), ()))
        return Set.get_shopify_identifier_to_update(sets)


class Template_Image(metaclass=PoolMeta):
    __name__ = 'product.template'

    @property
    def shopify_images(self):
        for image in self.images_used:
            if image.web_shop:
                yield image

    def get_shopify(self, shop, categories):
        product = super().get_shopify(shop, categories)
        product['files'] = files = []
        for image in self.shopify_images:
            file = {
                'alt': image.description,
                'contentType': 'IMAGE',
                'filename': image.shopify_name,
                }
            if image_id := image.get_shopify_identifier(shop):
                file['id'] = id2gid('MediaImage', image_id)
            else:
                file['originalSource'] = self.get_image_url(
                    _external=True, id=image.id)
            files.append(file)
        return product


class Product_Image(metaclass=PoolMeta):
    __name__ = 'product.product'

    @property
    def shopify_images(self):
        for image in self.images_used:
            if image.web_shop:
                yield image

    def get_shopify(
            self, shop, sale_price, sale_tax, price, tax,
            shop_taxes_included=True):
        variant = super().get_shopify(
            shop, sale_price, sale_tax, price, tax,
            shop_taxes_included=shop_taxes_included)
        for image in self.shopify_images:
            file = {
                'alt': image.description,
                'contentType': 'IMAGE',
                'filename': image.shopify_name,
                }
            if image_id := image.get_shopify_identifier(shop):
                file['id'] = id2gid('MediaImage', image_id)
            else:
                file['originalSource'] = self.get_image_url(
                    _external=True, id=image.id)
            variant['file'] = file
            break
        else:
            variant['file'] = None
        return variant


class Image(IdentifiersMixin, metaclass=PoolMeta):
    __name__ = 'product.image'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._shopify_fields.update(['template', 'product', 'attributes'])

    @classmethod
    def on_write(cls, images, values):
        pool = Pool()
        Identifier = pool.get('web.shop.shopify_identifier')
        callback = super().on_write(images, values)
        if values.keys() & {'image', 'template', 'web_shop'}:
            to_delete = []
            for image in images:
                to_delete.extend(image.shopify_identifiers)
            if to_delete:
                callback.append(lambda: Identifier.delete(to_delete))
        return callback

    @classmethod
    def get_shopify_identifier_to_update(cls, images):
        return (
            sum((list(i.template.shopify_identifiers) for i in images), [])
            + sum(
                (list(p.shopify_identifiers)
                    for i in images for p in i.template.products), []))

    @property
    def shopify_name(self):
        if self.product:
            name = self.product.name
        else:
            name = self.template.name
        name = slugify(name)
        return f'{name}.jpg'


class Image_Attribute(metaclass=PoolMeta):
    __name__ = 'product.image'

    @property
    def shopify_name(self):
        name = super().shopify_name
        if self.product:
            attributes_name = self.product.attributes_name
        else:
            attributes_name = self.attributes_name
        if attributes_name:
            name += ' ' + attributes_name
        return name
