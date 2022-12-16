# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

import pyactiveresource
import shopify

from trytond.i18n import gettext
from trytond.model import ModelSQL, ModelView, fields
from trytond.model.exceptions import AccessError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, If
from trytond.tools import grouped_slice, slugify
from trytond.transaction import Transaction

from .common import IdentifiersMixin, IdentifiersUpdateMixin


class Category(IdentifiersMixin, metaclass=PoolMeta):
    __name__ = 'product.category'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._shopify_fields.add('name')

    def get_shopify(self, shop):
        shopify_id = self.get_shopify_identifier(shop)
        custom_collection = None
        if shopify_id:
            try:
                custom_collection = shopify.CustomCollection.find(shopify_id)
            except pyactiveresource.connection.ResourceNotFound:
                pass
        if custom_collection is None:
            custom_collection = shopify.CustomCollection()
        custom_collection.title = self.name[:255]
        custom_collection.published = False
        return custom_collection

    def get_shopify_metafields(self, shop):
        return {}


class TemplateCategory(IdentifiersUpdateMixin, metaclass=PoolMeta):
    __name__ = 'product.template-product.category'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._shopify_fields.update(['template', 'category'])

    @classmethod
    def create(cls, vlist):
        records = super().create(vlist)
        cls.set_shopify_to_update(records)
        return records

    @classmethod
    def delete(cls, records):
        cls.set_shopify_to_update(records)
        super().delete(records)

    @classmethod
    def get_shopify_identifier_to_update(cls, records):
        return sum((list(r.template.shopify_identifiers) for r in records), [])


class Template(IdentifiersMixin, metaclass=PoolMeta):
    __name__ = 'product.template'

    shopify_uom = fields.Many2One(
        'product.uom', "Shopify UOM",
        states={
            'readonly': Bool(Eval('shopify_identifiers', [-1])),
            'invisible': ~Eval('salable', False),
            },
        depends={'default_uom_category'})

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._shopify_fields.update([
                'name', 'web_shop_description', 'attribute_set',
                'customs_category', 'tariff_codes_category',
                'country_of_origin'])
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

    def get_shopify(self, shop):
        shopify_id = self.get_shopify_identifier(shop)
        product = None
        if shopify_id:
            try:
                product = shopify.Product.find(shopify_id)
            except pyactiveresource.connection.ResourceNotFound:
                pass
        if product is None:
            product = shopify.Product()
        product.title = self.name
        product.body_html = self.web_shop_description
        options = []
        for attribute in self.shopify_attributes:
            options.append({'name': attribute.string})
        product.options = options[:3] or [{'name': "Title"}]
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
        cls._shopify_fields.update([
                'code', 'weight', 'weight_uom', 'attributes'])

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
            self, shop, price, tax, shop_taxes_included=True,
            shop_weight_unit=None):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Uom = pool.get('product.uom')
        shopify_id = self.get_shopify_identifier(shop)
        variant = None
        if shopify_id:
            try:
                variant = shopify.Variant.find(shopify_id)
            except pyactiveresource.connection.ResourceNotFound:
                pass
        if variant is None:
            variant = shopify.Variant()
        product_id = self.template.get_shopify_identifier(shop)
        if product_id is not None:
            variant.product_id = product_id
        variant.sku = self.shopify_sku
        price = self.shopify_price(
            price, tax, taxes_included=shop_taxes_included)
        if price is not None:
            variant.price = str(price.quantize(Decimal('.00')))
        else:
            variant.price = None
        variant.taxable = bool(tax)
        for identifier in self.identifiers:
            if identifier.type == 'ean':
                variant.barcode = identifier.code
                break
        for i, attribute in enumerate(self.template.shopify_attributes, 1):
            if self.attributes:
                value = self.attributes.get(attribute.name)
            else:
                value = None
            value = attribute.format(value)
            setattr(variant, 'option%i' % i, value)
        if getattr(self, 'weight', None) and shop_weight_unit:
            units = {}
            units['kg'] = ModelData.get_id('product', 'uom_kilogram')
            units['g'] = ModelData.get_id('product', 'uom_gram')
            units['lb'] = ModelData.get_id('product', 'uom_pound')
            units['oz'] = ModelData.get_id('product', 'uom_ounce')
            weight = self.weight
            weight_unit = self.weight_uom
            if self.weight_uom.id not in units.values():
                weight_unit = Uom(units[shop_weight_unit])
                weight = Uom.compute_qty(self.weight_uom, weight, weight_unit)
            variant.weight = weight
            variant.weight_unit = {
                v: k for k, v in units.items()}[weight_unit.id]
        for image in getattr(self, 'images_used', []):
            if image.web_shop:
                variant.image_id = image.get_shopify_identifier(shop)
                break
        else:
            variant.image_id = None
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

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        for products, values in zip(actions, actions):
            if 'template' in values:
                for product in products:
                    if (product.template.id != values.get('template')
                            and product.shopify_identifiers):
                        raise AccessError(gettext(
                                'web_shop_shopify.msg_product_change_template',
                                product=product.rec_name))
        super().write(*args)


class ShopifyInventoryItem(IdentifiersMixin, ModelSQL, ModelView):
    "Shopify Inventory Item"
    __name__ = 'product.shopify_inventory_item'

    product = fields.Function(
        fields.Many2One('product.product', "Product"), 'get_product')

    @classmethod
    def table_query(cls):
        return Pool().get('product.product').__table__()

    def get_product(self, name):
        return self.id

    def get_shopify(self, shop):
        pool = Pool()
        Product = pool.get('product.product')
        Move = pool.get('stock.move')
        # TODO: replace with product_types from sale line
        move_types = Move.get_product_types()

        shopify_id = self.get_shopify_identifier(shop)
        inventory_item = None
        if shopify_id:
            try:
                inventory_item = shopify.InventoryItem.find(shopify_id)
            except pyactiveresource.connection.ResourceNotFound:
                pass
        if inventory_item is None:
            product = Product(self.id)
            variant_id = product.get_shopify_identifier(shop)
            if not variant_id:
                return
            try:
                variant = shopify.Variant.find(variant_id)
            except pyactiveresource.connection.ResourceNotFound:
                return
            inventory_item = shopify.InventoryItem.find(
                variant.inventory_item_id)
        inventory_item.tracked = (
            self.product.type in move_types and not self.product.consumable)
        inventory_item.requires_shipping = self.product.type in move_types
        return inventory_item


class ShopifyInventoryItem_Customs(metaclass=PoolMeta):
    __name__ = 'product.shopify_inventory_item'

    def get_shopify(self, shop):
        pool = Pool()
        Date = pool.get('ir.date')
        inventory_item = super().get_shopify(shop)
        if inventory_item:
            with Transaction().set_context(company=shop.company.id):
                today = Date.today()
            inventory_item.country_code_of_origin = (
                self.product.country_of_origin.code
                if self.product.country_of_origin else None)
            tariff_code = self.product.get_tariff_code(
                {'date': today, 'country': None})
            inventory_item.harmonized_system_code = (
                tariff_code.code if tariff_code else None)
            country_harmonized_system_codes = []
            countries = set()
            for tariff_code in self.product.get_tariff_codes({'date': today}):
                if (tariff_code.country
                        and tariff_code.country not in countries):
                    country_harmonized_system_codes.append({
                            'harmonized_system_code': tariff_code.code,
                            'country_code': tariff_code.country.code,
                            })
                    countries.add(tariff_code.country)
            inventory_item.country_harmonized_system_codes = (
                country_harmonized_system_codes)
        return inventory_item


class Product_TariffCode(IdentifiersUpdateMixin, metaclass=PoolMeta):
    __name__ = 'product-customs.tariff.code'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._shopify_fields.update(['product', 'tariff_code'])

    @classmethod
    def create(cls, vlist):
        identifiers = super().create(vlist)
        cls.set_shopify_to_update(identifiers)
        return identifiers

    @classmethod
    def delete(cls, records):
        cls.set_shopify_to_update(records)
        super().delete(records)

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
    def create(cls, vlist):
        identifiers = super().create(vlist)
        cls.set_shopify_to_update(identifiers)
        return identifiers

    @classmethod
    def delete(cls, identifiers):
        cls.set_shopify_to_update(identifiers)
        super().delete(identifiers)

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


class Image(IdentifiersMixin, metaclass=PoolMeta):
    __name__ = 'product.image'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._shopify_fields.update(['template', 'product', 'attributes'])

    @classmethod
    def create(cls, vlist):
        images = super().create(vlist)
        cls.set_shopify_to_update(images)
        return images

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Identifier = pool.get('web.shop.shopify_identifier')
        actions = iter(args)
        to_delete = []
        for images, values in zip(actions, actions):
            if values.keys() & {'image', 'template', 'web_shop'}:
                for image in images:
                    to_delete.extend(image.shopify_identifiers)
        super().write(*args)
        Identifier.delete(to_delete)

    @classmethod
    def delete(cls, images):
        cls.set_shopify_to_update(images)
        super().delete(images)

    @classmethod
    def get_shopify_identifier_to_update(cls, images):
        return (
            sum((list(i.template.shopify_identifiers) for i in images), [])
            + sum(
                (list(p.shopify_identifiers)
                    for i in images for p in i.template.products), []))

    def get_shopify(self, shop):
        shopify_id = self.get_shopify_identifier(shop)
        product_id = self.template.get_shopify_identifier(shop)
        product_image = None
        if shopify_id and product_id:
            try:
                product_image = shopify.Image.find(
                    shopify_id, product_id=product_id)
            except pyactiveresource.connection.ResourceNotFound:
                pass
        if product_image is None:
            product_image = shopify.Image()
            product_image.attach_image(
                self.image, filename=slugify(self.shopify_name))
        product_image.product_id = self.template.get_shopify_identifier(shop)
        product_image.alt = self.shopify_name
        return product_image

    @property
    def shopify_name(self):
        if self.product:
            return self.product.name
        else:
            return self.template.name


class Image_Attribute(metaclass=PoolMeta):
    __name__ = 'product.image'

    @property
    def shopify_name(self):
        name = super().shopify_filename
        if self.product:
            attributes_name = self.product.attributes_name
        else:
            attributes_name = self.attributes_name
        if attributes_name:
            name += ' ' + attributes_name
        return name
