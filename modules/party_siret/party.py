#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta
from . import luhn

__all__ = ['Party']
__metaclass__ = PoolMeta


class Party:
    __name__ = 'party.party'

    siren = fields.Char('SIREN', select=True, states={
            'readonly': ~Eval('active', True),
            }, size=9, depends=['active'])

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._error_messages.update({
                'invalid_siren': ('Invalid SIREN number "%(siren)s" on party '
                    '"%(party)s".'),
                })

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
                self.raise_user_error('invalid_siren', {
                        'siren': self.siren,
                        'party': self.rec_name,
                        })
