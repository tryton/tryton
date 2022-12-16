# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool


class Replace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super().fields_to_replace() + [
            ('web.user', 'party'),
            ]


class Erase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def to_erase(self, party_id):
        pool = Pool()
        User = pool.get('web.user')
        to_erase = super().to_erase(party_id)
        to_erase.append(
            (User, [('party', '=', party_id)], True,
                ['email'],
                [None]))
        return to_erase
