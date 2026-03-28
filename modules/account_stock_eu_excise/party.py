# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql import Literal

from trytond.model import ModelSQL, fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval

IDENTIFIER_TYPES = [
    ('eu_excise', "European Excise Number"),
    ('fr_excise', "French Excise Number"),
    ]

EXCISE_IDENTIFIER_TYPES = list(dict(IDENTIFIER_TYPES).keys())


class Configuration(metaclass=PoolMeta):
    __name__ = 'party.configuration'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.identifier_types.selection.extend(IDENTIFIER_TYPES)


class Address(metaclass=PoolMeta):
    __name__ = 'party.address'

    @classmethod
    def _type_identifiers(cls):
        return super()._type_identifiers() | set(EXCISE_IDENTIFIER_TYPES)


class Identifier(metaclass=PoolMeta):
    __name__ = 'party.identifier'

    eu_excise_codes = fields.Many2Many(
        'party.identifier-product.eu.excise_code',
        'identifier', 'excise_code', "Excise Codes",
        states={
            'invisible': ~Eval('type').in_(EXCISE_IDENTIFIER_TYPES),
            },
        help="Authorized codes for the excise number.")

    @classmethod
    def _type_addresses(cls):
        return super()._type_addresses() | set(EXCISE_IDENTIFIER_TYPES)

    def is_excise_product(self, product):
        return product.eu_excise_code in self.eu_excise_codes

    def is_excise_product_sql(self, product, template):
        if self.eu_excise_codes:
            return template.eu_excise_code.in_(
                [c.id for c in self.eu_excise_codes])
        else:
            return Literal(False)


class Identifier_EUExciseCode(ModelSQL):
    __name__ = 'party.identifier-product.eu.excise_code'

    identifier = fields.Many2One(
        'party.identifier', "Identifier", required=True, ondelete='CASCADE')
    excise_code = fields.Many2One(
        'product.eu.excise_code', "Excise Code", required=True)
