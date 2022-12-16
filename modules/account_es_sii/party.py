# This file is part of Tryton. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


class Identifier(metaclass=PoolMeta):
    __name__ = 'party.identifier'

    def es_sii_values(self):
        if not self.type:
            return {}
        country = self.es_country()
        code = self.es_code()
        if country == 'ES':
            return {
                'NIF': code
                }
        if country is None:
            try:
                country, _ = self.type.split('_', 1)
                country = country.upper()
            except ValueError:
                country = ''
        # Greece uses ISO-639-1 as prefix (EL)
        country = country.replace('EL', 'GR')
        return {
            'IDOtro': {
                'ID': country + code,
                'IDType': self.es_vat_type(),
                'CodigoPais': country,
                }
            }
