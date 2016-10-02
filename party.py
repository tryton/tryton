# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pyson import Eval
from trytond.pool import PoolMeta

__all__ = ['PartyConfiguration', 'PartyReplace']


class PartyConfiguration:
    __metaclass__ = PoolMeta
    __name__ = 'party.configuration'

    @classmethod
    def __setup__(cls):
        super(PartyConfiguration, cls).__setup__()

        cls.party_sequence.domain = [
            cls.party_sequence.domain,
            ('company', 'in', [Eval('context', {}).get('company'), None]),
            ]


class PartyReplace:
    __metaclass__ = PoolMeta
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('company.company', 'party'),
            ('company.employee', 'party'),
            ]
