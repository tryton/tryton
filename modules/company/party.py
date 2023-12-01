# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.report import Report
from trytond.transaction import Transaction

from .model import CompanyMultiValueMixin, CompanyValueMixin


class Configuration(CompanyMultiValueMixin, metaclass=PoolMeta):
    __name__ = 'party.configuration'


class ConfigurationLang(CompanyValueMixin, metaclass=PoolMeta):
    __name__ = 'party.configuration.party_lang'


class Party(CompanyMultiValueMixin, metaclass=PoolMeta):
    __name__ = 'party.party'


class PartyLang(CompanyValueMixin, metaclass=PoolMeta):
    __name__ = 'party.party.lang'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.party.context['company'] = Eval('company', -1)
        cls.party.depends.add('company')


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
        cls.contact_mechanism.depends.add('company')


class LetterReport(Report):
    __name__ = 'party.letter'

    @classmethod
    def execute(cls, ids, data):
        with Transaction().set_context(address_with_party=True):
            return super(LetterReport, cls).execute(ids, data)
