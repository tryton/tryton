# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.tools.multivalue import migrate_property
from trytond.transaction import Transaction

from trytond.report import Report
from .model import CompanyMultiValueMixin, CompanyValueMixin


class Configuration(CompanyMultiValueMixin, metaclass=PoolMeta):
    __name__ = 'party.configuration'


class ConfigurationLang(CompanyValueMixin, metaclass=PoolMeta):
    __name__ = 'party.configuration.party_lang'

    @classmethod
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)
        if exist:
            table = cls.__table_handler__(module_name)
            exist &= table.column_exist('company')

        super().__register__(module_name)

        if not exist:
            # Re-migrate with company
            migrate_property(
                'party.configuration', cls._configuration_value_field,
                cls, cls._configuration_value_field, fields=['company'])


class Party(CompanyMultiValueMixin, metaclass=PoolMeta):
    __name__ = 'party.party'


class PartyLang(CompanyValueMixin, metaclass=PoolMeta):
    __name__ = 'party.party.lang'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.party.context['company'] = Eval('company', -1)
        if 'company' not in cls.party.depends:
            cls.party.depends.append('company')

    @classmethod
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)
        if exist:
            table = cls.__table_handler__(module_name)
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


class Replace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super().fields_to_replace() + [
            ('company.company', 'party'),
            ('company.employee', 'party'),
            ]


class Erase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def check_erase(self, party):
        pool = Pool()
        Party = pool.get('party.party')
        Company = pool.get('company.company')

        super().check_erase(party)

        with Transaction().set_user(0):
            companies = Company.search([])
            for company in companies:
                with Transaction().set_context(company=company.id):
                    party = Party(party.id)
                    self.check_erase_company(party, company)

    def check_erase_company(self, party, company):
        pass


class ContactMechanism(CompanyMultiValueMixin, metaclass=PoolMeta):
    __name__ = 'party.contact_mechanism'

    def _phone_country_codes(self):
        pool = Pool()
        Company = pool.get('company.company')
        context = Transaction().context

        yield from super()._phone_country_codes()

        if context.get('company'):
            company = Company(context['company'])
            for address in company.party.addresses:
                if address.country:
                    yield address.country.code


class ContactMechanismLanguage(CompanyValueMixin, metaclass=PoolMeta):
    __name__ = 'party.contact_mechanism.language'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.contact_mechanism.context['company'] = Eval('company', -1)
        if 'company' not in cls.contact_mechanism.depends:
            cls.contact_mechanism.depends.append('company')


class LetterReport(Report):
    __name__ = 'party.letter'

    @classmethod
    def execute(cls, ids, data):
        with Transaction().set_context(address_with_party=True):
            return super(LetterReport, cls).execute(ids, data)
