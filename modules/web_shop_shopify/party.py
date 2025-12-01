# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from trytond.model import sequence_reorder
from trytond.pool import Pool, PoolMeta
from trytond.tools import remove_forbidden_chars
from trytond.tools.email_ import EmailNotValidError, validate_email

from .common import IdentifiersMixin, gid2id, setattr_changed

logger = logging.getLogger(__name__)


class Party(IdentifiersMixin, metaclass=PoolMeta):
    __name__ = 'party.party'

    @classmethod
    def shopify_fields(cls):
        return {
            'id': None,
            'displayName': None,
            'email': None,
            'phone': None,
            'locale': None,
            }

    @classmethod
    def get_from_shopify(cls, shop, customer):
        pool = Pool()
        ContactMechanism = pool.get('party.contact_mechanism')
        Lang = pool.get('ir.lang')
        party = cls.search_shopify_identifier(
            shop, gid2id(customer['id']))
        if not party:
            party = cls()
        setattr_changed(party, 'name', remove_forbidden_chars(
                customer['displayName']))
        if customer['locale']:
            lang = Lang.get(customer['locale'])
        else:
            lang = None
        setattr_changed(party, 'lang', lang)
        contact_mechanisms = list(getattr(party, 'contact_mechanisms', []))
        for types, value in [
                (['email'], customer['email']),
                (['phone', 'mobile'], customer['phone']),
                ]:
            value = remove_forbidden_chars(value)
            if not value:
                continue
            index = len(contact_mechanisms)
            for i, contact_mechanism in enumerate(contact_mechanisms):
                if (contact_mechanism.type in types
                        and not contact_mechanism.address):
                    index = min(i, index)
                    if (contact_mechanism.value_compact
                            == contact_mechanism.format_value_compact(
                                value, contact_mechanism.type)):
                        contact_mechanisms.insert(
                            index,
                            contact_mechanisms.pop(i))
                        break
            else:
                if types[0] == 'email':
                    try:
                        validate_email(value)
                    except EmailNotValidError as e:
                        logger.info("Skip email %s", value, exc_info=e)
                        continue
                contact_mechanisms.insert(index, ContactMechanism(
                        type=types[0], value=value))
        party.contact_mechanisms = sequence_reorder(contact_mechanisms)
        # TODO tax_exempt
        return party

    def get_address_from_shopify(self, shopify_address):
        pool = Pool()
        Address = pool.get('party.address')
        ContactMechanism = pool.get('party.contact_mechanism')
        shopify_values = Address.get_shopify_values(shopify_address)
        for address in self.addresses:
            if address.shopify_values() == shopify_values:
                break
        else:
            address = Address(**shopify_values)
            address.party = self
            address.save()

        contact_mechanisms = list(self.contact_mechanisms)
        if phone := remove_forbidden_chars(shopify_address['phone']):
            index = len(contact_mechanisms)
            for i, contact_mechanism in enumerate(contact_mechanisms):
                if (contact_mechanism.type in ['phone', 'mobile']
                        and contact_mechanism.address == address):
                    index = min(i, index)
                    if (contact_mechanism.value_compact
                            == contact_mechanism.format_value_compact(
                                phone, contact_mechanism.type)):
                        contact_mechanisms.insert(
                            index,
                            contact_mechanisms.pop(i))
                        break
            else:
                contact_mechanisms.insert(index, ContactMechanism(
                        party=self, address=address,
                        type='phone', value=phone))
            ContactMechanism.save(sequence_reorder(
                    contact_mechanisms))
        return address


class Address(metaclass=PoolMeta):
    __name__ = 'party.address'

    @classmethod
    def shopify_fields(cls):
        return {
            'name': None,
            'company': None,
            'address1': None,
            'address2': None,
            'city': None,
            'zip': None,
            'countryCodeV2': None,
            'provinceCode': None,
            'phone': None,
            }

    @classmethod
    def get_shopify_values(self, address):
        pool = Pool()
        Country = pool.get('country.country')
        Subdivision = pool.get('country.subdivision')
        SubdivisionType = pool.get('party.address.subdivision_type')

        values = {}
        values['party_name'] = remove_forbidden_chars(address['name'] or '')
        if address['company']:
            values['party_name'] += (
                f"({remove_forbidden_chars(address['company'])})")
        values['street'] = '\n'.join(filter(None, [
                    address['address1'], address['address2']]))
        values['city'] = remove_forbidden_chars(address['city'] or '')
        values['postal_code'] = address['zip'] or ''
        if address['countryCodeV2']:
            country, = Country.search([
                    ('code', '=', address['countryCodeV2']),
                    ], limit=1)
            values['country'] = country.id
            if address['provinceCode']:
                subdivision_code = '-'.join(
                    [address['countryCodeV2'], address['provinceCode']])
                subdivision_domain = [
                    ('country', '=', country.id),
                    ('code', 'like', subdivision_code + '%'),
                    ]
                types = SubdivisionType.get_types(country)
                if types:
                    subdivision_domain.append(('type', 'in', types))
                subdivisions = Subdivision.search(subdivision_domain, limit=1)
                if subdivisions:
                    subdivision, = subdivisions
                    values['subdivision'] = subdivision.id
        return values

    def shopify_values(self):
        values = {}
        values['party_name'] = self.party_name or ''
        values['street'] = self.street or ''
        values['city'] = self.city or ''
        values['postal_code'] = self.postal_code or ''
        if self.country:
            values['country'] = self.country.id
        if self.subdivision:
            values['subdivision'] = self.subdivision.id
        return values


class Replace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super().fields_to_replace() + [
            ('web.shop.shopify_identifier', 'record'),
            ]
