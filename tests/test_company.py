# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction


class CompanyTestCase(ModuleTestCase):
    'Test Company module'
    module = 'company'

    def setUp(self):
        super(CompanyTestCase, self).setUp()
        self.party = POOL.get('party.party')
        self.company = POOL.get('company.company')
        self.employee = POOL.get('company.employee')
        self.currency = POOL.get('currency.currency')
        self.user = POOL.get('res.user')

    def test0010company(self):
        'Create company'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            currency1, = self.currency.search([
                    ('code', '=', 'cu1'),
                    ], 0, 1, None)

            party1, = self.party.create([{
                        'name': 'Dunder Mifflin',
                        'addresses': [('create', [{}])],
                        }])
            company1, = self.company.create([{
                        'party': party1.id,
                        'currency': currency1.id,
                        }])
            self.assert_(company1)
            transaction.cursor.commit()

    def test0020company_recursion(self):
        'Test company recursion'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            currency1, = self.currency.search([
                ('code', '=', 'cu1'),
                ], 0, 1, None)

            company1, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ], 0, 1, None)

            party2, = self.party.create([{
                        'name': 'Michael Scott Paper Company',
                        }])
            company2, = self.company.create([{
                        'party': party2.id,
                        'parent': company1.id,
                        'currency': currency1.id,
                        }])
            self.assert_(company2)

            self.assertRaises(Exception, self.company.write,
                [company1], {
                    'parent': company2.id,
                    })

    def test0030employe(self):
        'Create employee'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            company1, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ], 0, 1, None)

            party, = self.party.create([{
                        'name': 'Pam Beesly',
                        }])
            self.employee.create([{
                        'party': party.id,
                        'company': company1.id,
                        }])
            transaction.cursor.commit()

    def test0040user(self):
        'Test user company'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            currency1, = self.currency.search([
                    ('code', '=', 'cu1'),
                    ], 0, 1, None)

            company1, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ], 0, 1, None)

            party2, = self.party.create([{
                        'name': 'Michael Scott Paper Company',
                        }])
            company2, = self.company.create([{
                        'party': party2.id,
                        'parent': company1.id,
                        'currency': currency1.id,
                        }])
            user1, user2 = self.user.create([{
                        'name': 'Jim Halper',
                        'login': 'jim',
                        'main_company': company1.id,
                        'company': company1.id,
                        }, {
                        'name': 'Pam Beesly',
                        'login': 'pam',
                        'main_company': company2.id,
                        'company': company2.id,
                        }])
            self.assert_(user1)

            with transaction.set_user(user1.id):
                user1, user2 = self.user.browse([user1.id, user2.id])
                self.assertEqual(user1.company, company1)
                self.assertEqual(user2.company, company2)

                with transaction.set_context({'company': company2.id}):
                    user1, user2 = self.user.browse([user1.id, user2.id])
                    self.assertEqual(user1.company, company2)
                    self.assertEqual(user2.company, company2)

                with transaction.set_context({'company': None}):
                    user1, user2 = self.user.browse([user1.id, user2.id])
                    self.assertEqual(user1.company, None)
                    self.assertEqual(user2.company, company2)


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.currency.tests import test_currency
    for test in test_currency.suite():
        if test not in suite and not isinstance(test, doctest.DocTestCase):
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            CompanyTestCase))
    return suite
