# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

__all__ = ['PartyReplace', 'PartyErase']


class PartyReplace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('web.user', 'party'),
            ]


class PartyErase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def to_erase(self, party_id):
        pool = Pool()
        User = pool.get('web.user')
        to_erase = super(PartyErase, self).to_erase(party_id)
        to_erase.append(
            (User, [('party', '=', party_id)], True,
                ['email'],
                [None]))
        return to_erase
