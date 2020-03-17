# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import fields
from trytond.pool import PoolMeta
from . import luhn
from .exceptions import SIRETValidationError


class Address(metaclass=PoolMeta):
    __name__ = 'party.address'

    siret_nic = fields.Char("SIRET NIC", select=True, size=5)
    siret = fields.Function(fields.Char('SIRET'), 'get_siret')

    def get_siret(self, name):
        if self.party.siren and self.siret_nic:
            return self.party.siren + self.siret_nic

    @classmethod
    def validate(cls, addresses):
        super(Address, cls).validate(addresses)
        for address in addresses:
            address.check_siret()

    def check_siret(self):
        '''
        Check validity of SIRET
        '''
        if self.siret:
            if (len(self.siret) != 14
                    or not luhn.validate(self.siret)):
                raise SIRETValidationError(
                    gettext('party_siret.msg_invalid_siret',
                        number=self.siret,
                        address=self.rec_name))
