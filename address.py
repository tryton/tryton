#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta
from . import luhn

__all__ = ['Address']
__metaclass__ = PoolMeta


class Address:
    __name__ = 'party.address'

    siret_nic = fields.Char('SIRET NIC', select=True, states={
            'readonly': ~Eval('active', True),
            }, size=5, depends=['active'])
    siret = fields.Function(fields.Char('SIRET'), 'get_siret')

    @classmethod
    def __setup__(cls):
        super(Address, cls).__setup__()
        cls._error_messages.update({
                'invalid_siret': ('Invalid SIRET number "%(siret)s" on address '
                    '"%(address)s"'),
                })

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
                self.raise_user_error('invalid_siret', {
                        'siret': self.siret,
                        'address': self.rec_name,
                        })
