# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import phonenumbers
from phonenumbers import NumberParseException

from trytond.pool import PoolMeta


class Company(metaclass=PoolMeta):
    __name__ = 'company.company'

    @property
    def es_aeat_contact_phone(self):
        phone = None
        for contact_mechanism in self.party.contact_mechanisms:
            if contact_mechanism.type in {'phone', 'mobile'}:
                try:
                    phonenumber = phonenumbers.parse(
                        contact_mechanism.value, None)
                except NumberParseException:
                    continue
                if phonenumber and phonenumber.country_code == 34:
                    phone = contact_mechanism.value
                    break
        return phone

    @property
    def es_tax_identifier(self):
        valid_types = {'es_cif', 'es_dni', 'es_nie', 'es_vat', 'eu_vat'}
        for identifier in self.party.identifiers:
            if identifier.type in valid_types:
                if (identifier.type == 'eu_vat'
                        and not identifier.code.startswith('ES')):
                    continue
                return identifier
