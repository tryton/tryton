# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import fields
from trytond.pool import PoolMeta
from . import luhn
from .exceptions import SIRENValidationError


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    siren = fields.Char("SIREN", select=True, size=9)

    @classmethod
    def validate(cls, parties):
        super(Party, cls).validate(parties)
        for party in parties:
            party.check_siren()

    def check_siren(self):
        '''
        Check validity of SIREN
        '''
        if self.siren:
            if len(self.siren) != 9 or not luhn.validate(self.siren):
                raise SIRENValidationError(
                    gettext('party_siret.msg_invalid_siren',
                        number=self.siren,
                        party=self.rec_name))
