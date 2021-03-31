# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from stdnum import get_cc_module
try:
    import phonenumbers
    from phonenumbers import PhoneNumberFormat, NumberParseException
except ImportError:
    phonenumbers = None

from trytond.i18n import gettext
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from .exceptions import BadRequest
from .web import split_name, join_name


class Address(metaclass=PoolMeta):
    __name__ = 'party.address'

    vsf_telephone = fields.Many2One(
        'party.contact_mechanism', "Telephone",
        domain=[
            ('party', '=', Eval('party', -1)),
            ('type', 'in', ['phone', 'mobile']),
            ],
        depends=['party'])

    def get_vsf(self, for_party=None):
        if for_party and for_party != self.party:
            firstname, lastname = split_name(
                self.party_name or for_party.name)
        else:
            firstname, lastname = split_name(
                self.party_name or self.party.name)
        address = {
            'id': self.id,
            'firstname': firstname,
            'lastname': lastname,
            'street': self.street.splitlines(),
            'city': self.city,
            'country_id': self.country.code if self.country else None,
            'postcode': self.postal_code,
            }
        if self.subdivision:
            address['region'] = {
                'region': self.subdivision.name,
                }
        if self.vsf_telephone:
            address['telephone'] = self.vsf_telephone.value
        if for_party:
            address['company'] = self.party.name
            address['vat_id'] = (
                self.party.tax_identifier.code
                if self.party.tax_identifier else None)
        return address

    def set_vsf(self, data, for_party=None):
        pool = Pool()
        Country = pool.get('country.country')
        Subdivision = pool.get('country.subdivision')
        ContactMechanism = pool.get('party.contact_mechanism')

        name = join_name(data['firstname'], data['lastname'])
        party = for_party or self.party
        if name != party.name:
            self.party_name = name
        self.street = '\n'.join(map(str, data['street']))
        self.city = data['city']
        if data['country_id']:
            try:
                self.country, = Country.search([
                        ('code', '=', data['country_id']),
                        ], limit=1)
            except ValueError:
                raise BadRequest(gettext(
                        'web_shop_vue_storefront.msg_unknown_country_code',
                        code=data['country_id']))
        self.postal_code = data['postcode']

        if data.get('region') and data['region']['region']:
            domain = [
                ('name', '=', data['region']['region']),
                ]
            if self.country:
                domain.append(('country', '=', self.country.id))
            subdivisions = Subdivision.search(domain, limit=1)
            if subdivisions:
                self.subdivision, = subdivisions

        if data.get('telephone'):
            value = data['telephone']
            if phonenumbers:
                try:
                    phonenumber = phonenumbers.parse(
                        data['telephone'], data['country_id'])
                    value = phonenumbers.format_number(
                        phonenumber, PhoneNumberFormat.INTERNATIONAL)
                except NumberParseException:
                    pass
            contacts = ContactMechanism.search([
                    ('party', '=', self.party.id),
                    ('type', 'in', ['phone', 'mobile']),
                    ('value', '=', value),
                    ], limit=1)
            if contacts:
                self.vsf_telephone, = contacts
            else:
                contact = ContactMechanism(
                    party=self.party,
                    type='phone',
                    value=value)
                contact.save()
                self.vsf_telephone = contact


class Identifier(metaclass=PoolMeta):
    __name__ = 'party.identifier'

    def set_vsf_tax_identifier(self, code):
        pool = Pool()
        Party = pool.get('party.party')
        for type in Party.tax_identifier_types():
            module = get_cc_module(*type.split('_', 1))
            if module and module.is_valid(code):
                self.type = type
                self.code = code
                break
        else:
            raise BadRequest(gettext(
                    'web_shop_vue_storefront.msg_invalid_tax_identifier',
                    code=code))
