# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.tools import remove_forbidden_chars

from .common import IdentifiersMixin, setattr_changed


class Party(IdentifiersMixin, metaclass=PoolMeta):
    __name__ = 'party.party'

    @classmethod
    def get_from_shopify(cls, shop, customer):
        pool = Pool()
        ContactMechanism = pool.get('party.contact_mechanism')
        party = cls.search_shopify_identifier(shop, customer.id)
        if not party:
            party = cls()
        setattr_changed(party, 'name', remove_forbidden_chars(
                ' '.join(filter(None, [
                        customer.first_name, customer.last_name]))))
        contact_mechanisms = list(getattr(party, 'contact_mechanisms', []))
        for types, value in [
                (['email'], customer.email),
                (['phone', 'mobile'], customer.phone),
                ]:
            value = remove_forbidden_chars(value)
            if not value:
                continue
            for contact_mechanism in contact_mechanisms:
                if (contact_mechanism.type in types
                        and contact_mechanism.value == value):
                    break
            else:
                contact_mechanisms.append(ContactMechanism(
                        type=types[0], value=value))
        party.contact_mechanisms = contact_mechanisms
        # TODO tax_exempt
        return party

    def get_address_from_shopify(self, shopify_address):
        pool = Pool()
        Address = pool.get('party.address')
        shopify_values = Address.get_shopify_values(shopify_address)
        for address in self.addresses:
            if address.shopify_values() == shopify_values:
                return address
        address = Address(**shopify_values)
        address.party = self
        address.save()
        return address


class Address(metaclass=PoolMeta):
    __name__ = 'party.address'

    @classmethod
    def get_shopify_values(self, address):
        pool = Pool()
        Country = pool.get('country.country')
        Subdivision = pool.get('country.subdivision')
        SubdivisionType = pool.get('party.address.subdivision_type')

        values = {}
        values['party_name'] = remove_forbidden_chars(address.name or '')
        values['name'] = remove_forbidden_chars(address.company or '')
        values['street'] = '\n'.join(filter(None, [
                    address.address1, address.address2]))
        values['city'] = remove_forbidden_chars(address.city or '')
        values['postal_code'] = address.zip or ''
        if address.country_code:
            country, = Country.search([
                    ('code', '=', address.country_code),
                    ], limit=1)
            values['country'] = country.id
            if address.province_code:
                subdivision_code = '-'.join(
                    [address.country_code, address.province_code])
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
        values['name'] = self.name or ''
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
