# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import json
from operator import attrgetter

from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.tools import slugify

from .web import ShopVSFIdentifierMixin


class _ProductEntityMixin:

    vsf_sku = fields.Function(
        fields.Char("SKU"), 'get_vsf_sku', searcher='search_vsf_sku')

    def get_vsf_sku(self, name):
        return self.code

    @classmethod
    def search_vsf_sku(cls, name, clause):
        return [('code',) + tuple(clause[1:])]

    @property
    def vsf_image(self):
        if self.vsf_sku:
            return '/product/%(sku)s.jpg' % {
                'sku': slugify(self.vsf_sku.lower()),
                }

    @property
    def vsf_type_id(self):
        return 'virtual' if self.type == 'service' else 'simple'

    @property
    def vsf_quantity(self):
        pool = Pool()
        Uom = pool.get('product.uom')
        quantity = self.forecast_quantity
        if quantity < 0:
            quantity = 0
        return Uom.compute_qty(self.default_uom, quantity, self.sale_uom)

    def get_vsf_entity(self, shop, price, tax):
        categories = [
            c for c in self.categories_all
            if c in shop.categories]
        status = 1
        if not self.salable:
            status = 2
        quantity = self.vsf_quantity
        if quantity <= 0:
            status = 3
        return {
            'id': self.vsf_identifier.id,
            'name': self.name,
            'image': self.vsf_image,
            'sku': self.vsf_sku,
            'url_key': slugify(self.name.lower()),
            'url_path': '%s/%s' % (
                self.vsf_identifier.id, slugify(self.name.lower())),
            'type_id': self.vsf_type_id,
            'price': float(price),
            'price_tax': float(tax),
            'price_incl_tax': float(price + tax),
            'status': status,
            'visibility': 4,
            'category_ids': [c.vsf_identifier.id for c in categories],
            'category': [c.get_vsf_entity_product(shop) for c in categories],
            'stock': [{
                    'is_in_stock': quantity > 0,
                    'qty': quantity,
                    }],
            }

    def get_vsf_stock(self):
        quantity = self.vsf_quantity
        return {
            'product_id': self.vsf_identifier.id,
            'qty': quantity,
            'is_in_stock': quantity > 0,
            }


class Product(_ProductEntityMixin, ShopVSFIdentifierMixin, metaclass=PoolMeta):
    __name__ = 'product.product'

    def vsf_is_configurable(self, shop):
        return False


class Template(
        _ProductEntityMixin, ShopVSFIdentifierMixin, metaclass=PoolMeta):
    __name__ = 'product.template'

    @property
    def vsf_type_id(self):
        return 'configurable'

    def get_vsf_products(self, shop):
        return [p for p in self.products if shop in p.web_shops]


class Category(ShopVSFIdentifierMixin, metaclass=PoolMeta):
    __name__ = 'product.category'

    def get_vsf_entity(self, shop):
        pool = Pool()
        Product = pool.get('product.product')
        count = Product.search([
                ('categories_all', '=', self.id),
                ('web_shops', '=', shop.id),
                ], count=True)
        paths = self.get_vsf_paths(shop)

        def children(category):
            return [{
                    'id': c.vsf_identifier.id,
                    'children_data': children(c),
                    } for c in category.childs
                if c in shop.categories]
        return {
            'id': self.vsf_identifier.id,
            'name': self.name,
            'parent_id': (self.parent.vsf_identifier.id
                if self.parent in shop.categories else None),
            'path': '/'.join([str(p.vsf_identifier.id) for p in paths]),
            'url_key': slugify(self.name.lower()),
            'url_path': '/'.join(
                map(slugify, map(str.lower, map(attrgetter('name'), paths)))),
            'is_active': True,
            'position': self.id,
            'level': len(paths),
            'product_count': count,
            'children_data': children(self),
            }

    def get_vsf_entity_product(self, shop):
        return {
            'category_id': self.vsf_identifier.id,
            'name': self.name,
            'slug': slugify(self.name),
            'path': '/'.join(
                map(slugify, map(attrgetter('name'),
                        self.get_vsf_paths(shop)))),
            }

    def get_vsf_paths(self, shop):
        category = self
        paths = [category]
        while category.parent:
            if category.parent not in shop.categories:
                break
            category = category.parent
            paths.append(category)
        return list(reversed(paths))


class ProductAttribute(metaclass=PoolMeta):
    __name__ = 'product.product'

    def get_vsf_entity(self, shop, price, tax):
        entity = super().get_vsf_entity(shop, price, tax)
        if self.attribute_set:
            for attribute in self.attribute_set.attributes:
                if attribute not in shop.attributes:
                    continue
                name = attribute.name
                value = self.attributes.get(name)
                options = {
                    o['name']: o['value']
                    for o in attribute.get_vsf_options()}
                entity[name] = options.get(value, value)
        return entity

    def vsf_is_configurable(self, shop):
        configurable = super().vsf_is_configurable(shop)
        if self.template.attribute_set:
            template_products = self.template.get_vsf_products(shop)
            if len(template_products) > 1:
                names = [
                    a.name for a in self.template.attribute_set.attributes
                    if a in shop.attributes]
                values = {filter(
                        lambda k: k in names, sorted(p.attributes.keys()))
                    for p in template_products}
                configurable = len(values) == len(template_products)
        return configurable


class TemplateAttribute(metaclass=PoolMeta):
    __name__ = 'product.template'

    def get_vsf_entity(self, shop, price, tax):
        entity = super().get_vsf_entity(shop, price, tax)
        if self.attribute_set:
            for attribute in self.attribute_set.attributes:
                if attribute not in shop.attributes:
                    continue
                name = attribute.name
                p_attr_values = {
                    p.attributes[name]
                    for p in self.products
                    if name in p.attributes}
                if attribute.type_ == 'multiselection':
                    p_attr_values = set(sum(p_attr_values, []))
                options = [
                    o['value'] for o in attribute.get_vsf_options()
                    if o['name'] in p_attr_values]
                entity[name + '_options'] = options

                config_options = entity.setdefault('configurable_options', [])
                config_options.append(
                    attribute.get_vsf_entity_template(self, p_attr_values))
        return entity


class Attribute(ShopVSFIdentifierMixin, metaclass=PoolMeta):
    __name__ = 'product.attribute'

    def get_vsf_options(self):
        return [{
                'value': i,
                'name': n,
                'label': s,
                } for i, (n, s) in enumerate(
                json.loads(self.selection_json), 1)]

    def get_vsf_entity(self, shop):
        return {
            'id': self.vsf_identifier.id,
            'attribute_id': self.vsf_identifier.id,
            'attribute_code': self.name,
            'frontend_input': self.type_,
            'frontend_label': self.string,
            'is_comparable': True,
            'is_user_defined': True,
            'is_visible': True,
            'is_visible_on_front': True,
            'options': self.get_vsf_options(),
            }

    def get_vsf_entity_template(self, template, attribute_values):
        values = [{
                'value_index': o['value'],
                'label': o['label'],
                } for o in self.get_vsf_options()
            if o['name'] in attribute_values]
        return {
            'attribute_id': self.vsf_identifier.id,
            'attribute_code': self.name,
            'label': self.string,
            'product_id': template.vsf_identifier.id,
            'values': values,
            }
