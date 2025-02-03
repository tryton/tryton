# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
try:
    import phonenumbers
except ImportError:
    phonenumbers = None

from trytond.pool import PoolMeta


class Company(metaclass=PoolMeta):
    __name__ = 'company.company'

    @property
    def es_aeat_contact_phone(self):
        phone = ''
        for contact_mechanism in self.party.contact_mechanisms:
            if contact_mechanism.type in {'phone', 'mobile'}:
                if phonenumbers:
                    try:
                        phonenumber = phonenumbers.parse(
                            contact_mechanism.value, 'ES')
                    except phonenumbers.NumberParseException:
                        continue
                    if phonenumber and phonenumber.country_code == 34:
                        phone = phonenumbers.format_number(
                            phonenumber,
                            phonenumbers.PhoneNumberFormat.NATIONAL)
                        break
                elif contact_mechanism.value:
                    phone = contact_mechanism.value
                    break
        phone = phone.replace(' ', '')
        return phone[:9].rjust(9, '0')

    @property
    def es_tax_identifier(self):
        valid_types = {'es_cif', 'es_dni', 'es_nie', 'es_vat', 'eu_vat'}
        for identifier in self.party.identifiers:
            if identifier.type in valid_types:
                if (identifier.type == 'eu_vat'
                        and not identifier.code.startswith('ES')):
                    continue
                return identifier
