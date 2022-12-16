# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.pool import Pool


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


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(PartyTestCase))
    return suite
