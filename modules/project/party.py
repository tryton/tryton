# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

__all__ = ['PartyReplace', 'PartyErase']


class PartyReplace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('project.work', 'party'),
            ]


class PartyErase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    @classmethod
    def __setup__(cls):
        super(PartyErase, cls).__setup__()
        cls._error_messages.update({
                'opened_project': (
                    'The party "%(party)s" can not be erased '
                    'because he has opened projects '
                    'for the company "%(company)s".'),
                })

    def check_erase_company(self, party, company):
        pool = Pool()
        Work = pool.get('project.work')
        super(PartyErase, self).check_erase_company(party, company)

        works = Work.search([
                ('party', '=', party.id),
                ('state', '!=', 'done'),
                ])
        if works:
            self.raise_user_error('opened_project', {
                    'party': party.rec_name,
                    'company': company.rec_name,
                    })
