# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, test_view,\
    test_depends, test_menu_action
from trytond.transaction import Transaction


class PartyTestCase(unittest.TestCase):
    'Test Party module'

    def setUp(self):
        trytond.tests.test_tryton.install_module('party')
        self.category = POOL.get('party.category')
        self.party = POOL.get('party.party')
        self.address = POOL.get('party.address')

    def test0005views(self):
        'Test views'
        test_view('party')

    def test0006depends(self):
        'Test depends'
        test_depends()

    def test0007menu_actions(self):
        'Test menu actions'
        test_menu_action('party')

    def test0010category(self):
        'Create category'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            category1, = self.category.create([{
                        'name': 'Category 1',
                        }])
            self.assert_(category1.id)
            transaction.cursor.commit()

    def test0020category_recursion(self):
        'Test category recursion'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            category1, = self.category.search([
                ('name', '=', 'Category 1'),
                ], limit=1)

            category2, = self.category.create([{
                        'name': 'Category 2',
                        'parent': category1.id,
                        }])
            self.assert_(category2.id)

            self.assertRaises(Exception, self.category.write,
                [category1], {
                    'parent': category2.id,
                })

    def test0030party(self):
        'Create party'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            party1, = self.party.create([{
                        'name': 'Party 1',
                        }])
            self.assert_(party1.id)
            transaction.cursor.commit()

    def test0040party_code(self):
        'Test party code constraint'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            party1, = self.party.search([], limit=1)

            code = party1.code

            party2, = self.party.create([{
                        'name': 'Party 2',
                        }])

            self.assertRaises(Exception, self.party.write,
                [party2], {
                    'code': code,
                })

    def test0050address(self):
        'Create address'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            party1, = self.party.search([], limit=1)

            address, = self.address.create([{
                        'party': party1.id,
                        'street': 'St sample, 15',
                        'city': 'City',
                        }])
            self.assert_(address.id)

    def test0060party_label_report(self):
        'Test party label report'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            party1, = self.party.search([], limit=1)
            report = POOL.get('party.label', type='report')
            oext, content, _, _ = report.execute([party1.id], {})
            self.assertEqual(oext, 'odt')
            self.assertTrue(content)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(PartyTestCase))
    return suite
