# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest
try:
    import phonenumbers
except ImportError:
    phonenumbers = None

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import doctest_teardown
from trytond.tests.test_tryton import doctest_checker
from trytond.pool import Pool
from trytond.exceptions import UserError
from trytond.transaction import Transaction


class PartyTestCase(ModuleTestCase):
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
        self.assert_(category1.id)

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
        self.assert_(category2.id)

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
        self.assert_(party1.id)

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
        self.assert_(address.id)
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
        self.assert_(party2.id)
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


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(PartyTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_party_replace.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
