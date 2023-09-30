# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from unittest.mock import patch

from stdnum import get_cc_module

try:
    import phonenumbers
except ImportError:
    phonenumbers = None

from trytond.exceptions import UserError
from trytond.model.exceptions import AccessError
from trytond.modules.party.party import IDENTIFIER_TYPES
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import Transaction


class PartyCheckEraseMixin:

    @with_transaction()
    def test_check_erase_party(self):
        "Test check erase of party"
        pool = Pool()
        Erase = pool.get('party.erase', type='wizard')
        Session = pool.get('ir.session.wizard')
        party = self.setup_check_erase_party()

        session = Session()
        session.save()

        Erase(session.id).check_erase(party)

    def setup_check_erase_party(self):
        pool = Pool()
        Party = pool.get('party.party')

        party = Party(active=False)
        party.save()
        return party


class PartyTestCase(PartyCheckEraseMixin, ModuleTestCase):
    'Test Party module'
    module = 'party'

    @with_transaction()
    def test_category(self):
        'Create category'
        pool = Pool()
        Category = pool.get('party.category')
        category1, = Category.create([{
                    'name': 'Category 1',
                    }])
        self.assertTrue(category1.id)

    @with_transaction()
    def test_category_recursion(self):
        'Test category recursion'
        pool = Pool()
        Category = pool.get('party.category')
        category1, = Category.create([{
                    'name': 'Category 1',
                    }])
        category2, = Category.create([{
                    'name': 'Category 2',
                    'parent': category1.id,
                    }])
        self.assertTrue(category2.id)

        self.assertRaises(Exception, Category.write, [category1], {
                'parent': category2.id,
                })

    @with_transaction()
    def test_party(self):
        'Create party'
        pool = Pool()
        Party = pool.get('party.party')
        party1, = Party.create([{
                    'name': 'Party 1',
                    }])
        self.assertTrue(party1.id)

    @with_transaction()
    def test_party_code(self):
        'Test party code constraint'
        pool = Pool()
        Party = pool.get('party.party')
        party1, = Party.create([{
                    'name': 'Party 1',
                    }])

        code = party1.code

        party2, = Party.create([{
                    'name': 'Party 2',
                    }])

        self.assertRaises(Exception, Party.write, [party2], {
                'code': code,
                })

    @with_transaction()
    def test_party_autocomplete_eu_vat(self):
        "Test party autocomplete eu_vat"
        pool = Pool()
        Party = pool.get('party.party')

        self.assertEqual(
            Party.autocomplete('BE500923836'), [{
                    'id': None,
                    'name': 'BE0500923836',
                    'defaults': {
                        'identifiers': [{
                                'type': 'eu_vat',
                                'code': 'BE0500923836',
                                }],
                        },
                    }])

    @with_transaction()
    def test_party_autocomplete_eu_vat_without_country(self):
        "Test party autocomplete eu_vat without country"
        pool = Pool()
        Party = pool.get('party.party')

        self.assertIn({
                'id': None,
                'name': 'BE0500923836',
                'defaults': {
                    'identifiers': [{
                            'type': 'eu_vat',
                            'code': 'BE0500923836',
                            }],
                    },
                },
            Party.autocomplete('500923836'))

    @with_transaction()
    def test_party_autocomplete_be_vat(self):
        "Test party autocomplete be_vat"
        pool = Pool()
        Party = pool.get('party.party')
        Configuration = pool.get('party.configuration')

        configuration = Configuration(1)
        configuration.identifier_types = ['be_vat']
        configuration.save()

        self.assertEqual(
            Party.autocomplete('BE500923836'), [{
                    'id': None,
                    'name': '0500923836',
                    'defaults': {
                        'identifiers': [{
                                'type': 'be_vat',
                                'code': '0500923836',
                                }],
                        },
                    }])

    @with_transaction()
    def test_party_default_get_eu_vat(self):
        "Test party default_get eu_vat"
        pool = Pool()
        Party = pool.get('party.party')
        Country = pool.get('country.country')

        belgium = Country(code='BE', name="Belgium")
        belgium.save()

        eu_vat = get_cc_module('eu', 'vat')
        with patch.object(eu_vat, 'check_vies') as check_vies:
            check_vies.return_value = {
                'valid': True,
                'name': "Tryton Foundation",
                'address': "Street",
                }
            with Transaction().set_context(default_identifiers=[{
                            'type': 'eu_vat',
                            'code': 'BE0500923836',
                            }]):
                self.assertEqual(
                    Party.default_get(['name', 'addresses', 'identifiers']), {
                        'name': "Tryton Foundation",
                        'addresses': [{
                                'street': "Street",
                                'country': belgium.id,
                                'country.': {
                                    'rec_name': "🇧🇪 Belgium",
                                    },
                                }],
                        'identifiers': [{
                                'type': 'eu_vat',
                                'code': 'BE0500923836',
                                }],
                        })

    @with_transaction()
    def test_address(self):
        'Create address'
        pool = Pool()
        Party = pool.get('party.party')
        Address = pool.get('party.address')
        party1, = Party.create([{
                    'name': 'Party 1',
                    }])

        address, = Address.create([{
                    'party': party1.id,
                    'street': 'St sample, 15',
                    'city': 'City',
                    }])
        self.assertTrue(address.id)
        self.assertMultiLineEqual(address.full_address,
            "St sample, 15\n"
            "City")
        with Transaction().set_context(address_with_party=True):
            address = Address(address.id)
            self.assertMultiLineEqual(address.full_address,
                "Party 1\n"
                "St sample, 15\n"
                "City")

    @with_transaction()
    def test_full_address_country_subdivision(self):
        'Test full address with country and subdivision'
        pool = Pool()
        Party = pool.get('party.party')
        Country = pool.get('country.country')
        Subdivision = pool.get('country.subdivision')
        Address = pool.get('party.address')
        party, = Party.create([{
                    'name': 'Party',
                    }])
        country = Country(name='Country')
        country.save()
        subdivision = Subdivision(
            name='Subdivision', country=country, code='SUB', type='area')
        subdivision.save()
        address, = Address.create([{
                    'party': party.id,
                    'subdivision': subdivision.id,
                    'country': country.id,
                    }])
        self.assertMultiLineEqual(address.full_address,
            "Subdivision\n"
            "COUNTRY")

    @with_transaction()
    def test_address_get_no_type(self):
        "Test address_get with no type"
        pool = Pool()
        Party = pool.get('party.party')
        Address = pool.get('party.address')
        party, = Party.create([{}])
        address1, address2 = Address.create([{
                    'party': party.id,
                    'sequence': 1,
                    }, {
                    'party': party.id,
                    'sequence': 2,
                    }])

        address = party.address_get()

        self.assertEqual(address, address1)

    @with_transaction()
    def test_address_get_no_address(self):
        "Test address_get with no address"
        pool = Pool()
        Party = pool.get('party.party')
        party, = Party.create([{}])

        address = party.address_get()

        self.assertEqual(address, None)

    @with_transaction()
    def test_address_get_inactive(self):
        "Test address_get with inactive"
        pool = Pool()
        Party = pool.get('party.party')
        Address = pool.get('party.address')
        party, = Party.create([{}])
        address1, address2 = Address.create([{
                    'party': party.id,
                    'sequence': 1,
                    'active': False,
                    }, {
                    'party': party.id,
                    'sequence': 2,
                    'active': True,
                    }])

        address = party.address_get()

        self.assertEqual(address, address2)

    @with_transaction()
    def test_address_get_type(self):
        "Test address_get with type"
        pool = Pool()
        Party = pool.get('party.party')
        Address = pool.get('party.address')
        party, = Party.create([{}])
        address1, address2 = Address.create([{
                    'party': party.id,
                    'sequence': 1,
                    'postal_code': None,
                    }, {
                    'party': party.id,
                    'sequence': 2,
                    'postal_code': '1000',
                    }])

        address = party.address_get(type='postal_code')

        self.assertEqual(address, address2)

    @with_transaction()
    def test_party_label_report(self):
        'Test party label report'
        pool = Pool()
        Party = pool.get('party.party')
        Label = pool.get('party.label', type='report')
        party1, = Party.create([{
                    'name': 'Party 1',
                    }])
        oext, content, _, _ = Label.execute([party1.id], {})
        self.assertEqual(oext, 'odt')
        self.assertTrue(content)

    @with_transaction()
    def test_party_without_name(self):
        'Create party without name'
        pool = Pool()
        Party = pool.get('party.party')
        party2, = Party.create([{}])
        self.assertTrue(party2.id)
        code = party2.code
        self.assertEqual(party2.rec_name, '[' + code + ']')

    @unittest.skipIf(phonenumbers is None, 'requires phonenumbers')
    @with_transaction()
    def test_phone_number_format(self):
        'Test phone number format'
        pool = Pool()
        Party = pool.get('party.party')
        ContactMechanism = pool.get('party.contact_mechanism')
        transaction = Transaction()

        def create(mtype, mvalue):
            party1, = Party.create([{
                        'name': 'Party 1',
                        }])
            return ContactMechanism.create([{
                        'party': party1.id,
                        'type': mtype,
                        'value': mvalue,
                        }])[0]

        # Test format on create
        mechanism = create('phone', '+442083661177')
        self.assertEqual(mechanism.value, '+44 20 8366 1177')
        self.assertEqual(mechanism.value_compact, '+442083661177')

        # Test format on write
        mechanism.value = '+442083661178'
        mechanism.save()
        self.assertEqual(mechanism.value, '+44 20 8366 1178')
        self.assertEqual(mechanism.value_compact, '+442083661178')

        ContactMechanism.write([mechanism], {
                'value': '+442083661179',
                })
        self.assertEqual(mechanism.value, '+44 20 8366 1179')
        self.assertEqual(mechanism.value_compact, '+442083661179')

        # Test rejection of a phone type mechanism to non-phone value
        with self.assertRaises(UserError):
            mechanism.value = 'notaphone@example.com'
            mechanism.save()
        transaction.rollback()

        # Test rejection of invalid phone number creation
        with self.assertRaises(UserError):
            mechanism = create('phone', 'alsonotaphone@example.com')
        transaction.rollback()

        # Test acceptance of a non-phone value when type is non-phone
        mechanism = create('email', 'name@example.com')

    @with_transaction()
    def test_set_contact_mechanism(self):
        "Test set_contact_mechanism"
        pool = Pool()
        Party = pool.get('party.party')

        party = Party(email='test@example.com')
        party.save()

        self.assertEqual(party.email, 'test@example.com')

    @with_transaction()
    def test_set_contact_mechanism_with_value(self):
        "Test set_contact_mechanism"
        pool = Pool()
        Party = pool.get('party.party')

        party = Party(email='foo@example.com')
        party.save()

        party.email = 'bar@example.com'
        with self.assertRaises(AccessError):
            party.save()

    @with_transaction()
    def test_contact_mechanism_get_no_usage(self):
        "Test contact_mechanism_get with no usage"
        pool = Pool()
        Party = pool.get('party.party')
        ContactMechanism = pool.get('party.contact_mechanism')
        party, = Party.create([{}])
        contact1, contact2 = ContactMechanism.create([{
                    'party': party.id,
                    'sequence': 1,
                    'type': 'email',
                    'value': 'test1@example.com',
                    }, {
                    'party': party.id,
                    'sequence': 2,
                    'type': 'email',
                    'value': 'test2@example.com',
                    }])

        contact = party.contact_mechanism_get('email')

        self.assertEqual(contact, contact1)

    @with_transaction()
    def test_contact_mechanism_get_many_types(self):
        "Test contact_mechanism_get with many types"
        pool = Pool()
        Party = pool.get('party.party')
        ContactMechanism = pool.get('party.contact_mechanism')
        party, = Party.create([{}])
        contact1, contact2 = ContactMechanism.create([{
                    'party': party.id,
                    'sequence': 1,
                    'type': 'other',
                    'value': 'test',
                    }, {
                    'party': party.id,
                    'sequence': 2,
                    'type': 'email',
                    'value': 'test2@example.com',
                    }])

        contact = party.contact_mechanism_get({'email', 'phone'})

        self.assertEqual(contact, contact2)

    @with_transaction()
    def test_contact_mechanism_get_no_contact_mechanism(self):
        "Test contact_mechanism_get with no contact mechanism"
        pool = Pool()
        Party = pool.get('party.party')
        party, = Party.create([{}])

        contact = party.contact_mechanism_get()

        self.assertEqual(contact, None)

    @with_transaction()
    def test_contact_mechanism_get_no_type(self):
        "Test contact_mechanism_get with no type"
        pool = Pool()
        Party = pool.get('party.party')
        ContactMechanism = pool.get('party.contact_mechanism')
        party, = Party.create([{}])
        ContactMechanism.create([{
                    'party': party.id,
                    'type': 'email',
                    'value': 'test1@example.com',
                    }])

        contact = party.contact_mechanism_get('phone')

        self.assertEqual(contact, None)

    @with_transaction()
    def test_contact_mechanism_get_any_type(self):
        "Test contact_mechanism_get with any type"
        pool = Pool()
        Party = pool.get('party.party')
        ContactMechanism = pool.get('party.contact_mechanism')
        party, = Party.create([{}])
        email1, = ContactMechanism.create([{
                    'party': party.id,
                    'type': 'email',
                    'value': 'test1@example.com',
                    }])

        contact = party.contact_mechanism_get()

        self.assertEqual(contact, email1)

    @with_transaction()
    def test_contact_mechanism_get_inactive(self):
        "Test contact_mechanism_get with inactive"
        pool = Pool()
        Party = pool.get('party.party')
        ContactMechanism = pool.get('party.contact_mechanism')
        party, = Party.create([{}])
        contact1, contact2 = ContactMechanism.create([{
                    'party': party.id,
                    'sequence': 1,
                    'type': 'email',
                    'value': 'test1@example.com',
                    'active': False,
                    }, {
                    'party': party.id,
                    'sequence': 2,
                    'type': 'email',
                    'value': 'test2@example.com',
                    'active': True,
                    }])

        contact = party.contact_mechanism_get()

        self.assertEqual(contact, contact2)

    @with_transaction()
    def test_contact_mechanism_get_usage(self):
        "Test contact_mechanism_get with usage"
        pool = Pool()
        Party = pool.get('party.party')
        ContactMechanism = pool.get('party.contact_mechanism')
        party, = Party.create([{}])
        contact1, contact2 = ContactMechanism.create([{
                    'party': party.id,
                    'sequence': 1,
                    'type': 'email',
                    'value': 'test1@example.com',
                    'name': None,
                    }, {
                    'party': party.id,
                    'sequence': 2,
                    'type': 'email',
                    'value': 'test2@example.com',
                    'name': 'email',
                    }])

        contact = party.contact_mechanism_get(usage='name')

        self.assertEqual(contact, contact2)

    @with_transaction()
    def test_tax_identifier_types(self):
        "Ensure tax identifier types are in identifier types"
        pool = Pool()
        Party = pool.get('party.party')
        self.assertFalse(
            set(Party.tax_identifier_types())
            - set(dict(IDENTIFIER_TYPES).keys()))

    @with_transaction()
    def test_party_distance(self):
        "Test party distance"
        pool = Pool()
        Party = pool.get('party.party')

        A, B, = Party.create([{
                    'name': 'A',
                    }, {
                    'name': 'B',
                    }])

        parties = Party.search([])
        self.assertEqual([p.distance for p in parties], [None] * 2)

        with Transaction().set_context(related_party=A.id):
            parties = Party.search([])
            self.assertEqual(
                [(p.name, p.distance) for p in parties],
                [('A', 0), ('B', None)])


del ModuleTestCase
