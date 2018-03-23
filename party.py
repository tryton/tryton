# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.tools.multivalue import migrate_property
from trytond.transaction import Transaction

from .model import CompanyMultiValueMixin, CompanyValueMixin

__all__ = ['Configuration', 'PartyConfigurationLang', 'Party', 'PartyLang',
    'PartyReplace', 'PartyErase']


class Configuration(CompanyMultiValueMixin):
    __metaclass__ = PoolMeta
    __name__ = 'party.configuration'


class PartyConfigurationLang(CompanyValueMixin):
    __metaclass__ = PoolMeta
    __name__ = 'party.configuration.party_lang'

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        exist = TableHandler.table_exist(cls._table)
        if exist:
            table = TableHandler(cls, module_name)
            exist &= table.column_exist('company')

        super(PartyConfigurationLang, cls).__register__(module_name)

        if not exist:
            # Re-migrate with company
            migrate_property(
                'party.configuration', cls._configuration_value_field,
                cls, cls._configuration_value_field, fields=['company'])


class Party(CompanyMultiValueMixin):
    __metaclass__ = PoolMeta
    __name__ = 'party.party'


class PartyLang(CompanyValueMixin):
    __metaclass__ = PoolMeta
    __name__ = 'party.party.lang'

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        exist = TableHandler.table_exist(cls._table)
        if exist:
            table = TableHandler(cls, module_name)
            exist &= table.column_exist('company')

        super(PartyLang, cls).__register__(module_name)

        if not exist:
            # Re-migrate with company
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        fields.append('company')
        super(PartyLang, cls)._migrate_property(
            field_names, value_names, fields)


class PartyReplace:
    __metaclass__ = PoolMeta
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('company.company', 'party'),
            ('company.employee', 'party'),
            ]


class PartyErase:
    __metaclass__ = PoolMeta
    __name__ = 'party.erase'

    def check_erase(self, party):
        pool = Pool()
        Party = pool.get('party.party')
        Company = pool.get('company.company')

        super(PartyErase, self).check_erase(party)

        with Transaction().set_user(0):
            companies = Company.search([])
            for company in companies:
                with Transaction().set_context(company=company.id):
                    party = Party(party.id)
                    self.check_erase_company(party, company)

    def check_erase_company(self, party, company):
        pass
