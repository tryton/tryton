# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, ValueMixin, fields
from trytond.pool import Pool, PoolMeta

from .account import PROFILES


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    factur_x_profile = fields.MultiValue(fields.Selection(
            PROFILES, "Factur-X Profile", sort=False,
            help="Leave this field empty if you do want to include Factur-X."))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'factur_x_profile':
            return pool.get('party.party.factur_x')
        return super().multivalue_model(field)

    @classmethod
    def default_factur_x_profile(cls, **pattern):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        config = Configuration(1)
        return config.get_multivalue('default_factur_x_profile', **pattern)


class PartyFacturX(ModelSQL, ValueMixin):
    __name__ = 'party.party.factur_x'

    factur_x_profile = fields.Selection(PROFILES, "Factur-X Profile")
