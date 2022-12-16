# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


class Carrier(metaclass=PoolMeta):
    __name__ = 'carrier'

    @property
    def vsf_carrier_title(self):
        return self.party.name

    @property
    def vsf_method_title(self):
        return self.carrier_product.name

    def get_vsf(self):
        return {
            'carrier_code': str(self.id),
            'method_code': str(self.id),
            'carrier_title': self.vsf_carrier_title,
            'method_title': self.vsf_method_title,
            }
