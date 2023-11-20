# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import lazy_gettext
from trytond.model import fields
from trytond.pool import Pool


class IdentifierMixin:
    __slots__ = ()

    shopify_identifier_signed = fields.Integer(
        lazy_gettext('web_shop_shopify.msg_shopify_identifier'))
    shopify_identifier_signed._sql_type = 'BIGINT'
    shopify_identifier = fields.Function(fields.Integer(
            lazy_gettext('web_shop_shopify.msg_shopify_identifier')),
        'get_shopify_identifier', setter='set_shopify_identifier',
        searcher='search_shopify_identifier')
    shopify_identifier_char = fields.Function(fields.Char(
            lazy_gettext('web_shop_shopify.msg_shopify_identifier')),
        'get_shopify_identifier', setter='set_shopify_identifier',
        searcher='search_shopify_identifier')

    def get_shopify_identifier(self, name):
        if self.shopify_identifier_signed is not None:
            value = self.shopify_identifier_signed + (1 << 63)
            if name == 'shopify_identifier_char':
                value = str(value)
            return value

    @classmethod
    def set_shopify_identifier(cls, records, name, value):
        if value is not None:
            value = int(value) - (1 << 63)
        cls.write(records, {
                'shopify_identifier_signed': value,
                })

    @classmethod
    def search_shopify_identifier(cls, name, domain):
        _, operator, value = domain
        if operator in {'in', 'not in'}:
            value = [
                int(v) - (1 << 63) if v is not None else None for v in value]
        elif value is not None:
            value = int(value) - (1 << 63)
        return [('shopify_identifier_signed', operator, value)]

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('shopify_identifier_signed')
        return super().copy(records, default=default)


class IdentifiersUpdateMixin:
    __slots__ = ()

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._shopify_fields = set()

    @classmethod
    def set_shopify_to_update(cls, records):
        pool = Pool()
        Identifier = pool.get('web.shop.shopify_identifier')
        identifiers = cls.get_shopify_identifier_to_update(records)
        Identifier.write(identifiers, {
                'to_update': True,
                })

    @classmethod
    def get_shopify_identifier_to_update(cls, records):
        raise NotImplementedError

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        to_update = set()
        for records, values in zip(actions, actions):
            if values.keys() & cls._shopify_fields:
                to_update.update(records)
        if to_update:
            cls.set_shopify_to_update(cls.browse(list(to_update)))
        super().write(*args)


class IdentifiersMixin(IdentifiersUpdateMixin):
    __slots__ = ()

    shopify_identifiers = fields.One2Many(
        'web.shop.shopify_identifier', 'record',
        lazy_gettext('web_shop_shopify.msg_shopify_identifiers'))

    def get_shopify_identifier(self, web_shop):
        for record in self.shopify_identifiers:
            if record.web_shop == web_shop:
                return record.shopify_identifier

    def set_shopify_identifier(self, web_shop, identifier=None):
        pool = Pool()
        Identifier = pool.get('web.shop.shopify_identifier')
        for record in self.shopify_identifiers:
            if record.web_shop == web_shop:
                if not identifier:
                    Identifier.delete([record])
                    return
                else:
                    if record.shopify_identifier != identifier:
                        record.shopify_identifier = identifier
                        record.save()
                    return record
        if identifier:
            record = Identifier(record=self, web_shop=web_shop)
            record.shopify_identifier = identifier
            record.save()
            return record

    @classmethod
    def search_shopify_identifier(cls, web_shop, identifier):
        records = cls.search([
                ('shopify_identifiers', 'where', [
                        ('web_shop', '=', web_shop.id),
                        ('shopify_identifier', '=', identifier),
                        ]),
                ])
        if records:
            record, = records
            return record

    def is_shopify_to_update(self, web_shop, **extra):
        for record in self.shopify_identifiers:
            if record.web_shop == web_shop:
                return (record.to_update
                    or (record.to_update_extra or {}) != extra)
        return True

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('shopify_identifiers')
        return super().copy(records, default=default)

    @classmethod
    def delete(cls, records):
        pool = Pool()
        Identifier = pool.get('web.shop.shopify_identifier')
        Identifier.delete(sum((r.shopify_identifiers for r in records), ()))
        super().delete(records)

    @classmethod
    def get_shopify_identifier_to_update(cls, records):
        return sum((list(r.shopify_identifiers) for r in records), [])


def setattr_changed(record, name, value):
    if getattr(record, name, None) != value:
        setattr(record, name, value)
