#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.pyson import Eval
from trytond.pool import PoolMeta

__all__ = ['PartyConfiguration']
__metaclass__ = PoolMeta


class PartyConfiguration:
    __name__ = 'party.configuration'

    @classmethod
    def __setup__(cls):
        super(PartyConfiguration, cls).__setup__()

        cls.party_sequence.domain = [
            cls.party_sequence.domain,
            ('company', 'in', [Eval('context', {}).get('company'), None]),
            ]
