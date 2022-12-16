# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    es_province_code = fields.Char("Spanish Province Code", size=2,
        help="Set 99 for non Spanish parties.")

    @fields.depends('addresses', 'es_province_code')
    def on_change_addresses(self):
        if not self.es_province_code:
            for address in self.addresses:
                country = getattr(address, 'country', None)
                postal_code = getattr(address, 'postal_code', None)
                if country and postal_code and country.code == 'ES':
                    self.es_province_code = postal_code[:2]
                    break


class Identifier(metaclass=PoolMeta):
    __name__ = 'party.identifier'

    def es_country(self):
        if self.type == 'eu_vat':
            return self.code[:2]
        if self.type in {'es_cif', 'es_dni', 'es_nie', 'es_nif'}:
            return 'ES'

    def es_code(self):
        if self.type == 'eu_vat':
            return self.code[2:]
        return self.code

    def es_vat_type(self):
        country = self.es_country()
        if country == 'ES':
            return ''
        type_ = '02'
        if country is None:
            type_ = '06'
        return type_
