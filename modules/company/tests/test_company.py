# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from contextlib import contextmanager

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import Transaction
from trytond.pool import Pool

from trytond.modules.currency.tests import create_currency, add_currency_rate


def create_company(name='Dunder Mifflin', currency=None):
    pool = Pool()
    Party = pool.get('party.party')
    Company = pool.get('company.company')

    if currency is None:
        currency = create_currency('usd')
        add_currency_rate(currency, 1)

    party, = Party.create([{
                'name': name,
                'addresses': [('create', [{}])],
                }])
    company = Company(party=party, currency=currency)
    company.save()
    return company


@contextmanager
def set_company(company):
    pool = Pool()
    User = pool.get('res.user')
    User.write([User(Transaction().user)], {
            'main_company': company.id,
            'company': company.id,
                })
    with Transaction().set_context(User.get_preferences(context_only=True)):
        yield


class CompanyTestCase(ModuleTestCase):
    'Test Company module'
    module = 'company'

    @with_transaction()
    def test_company(self):
        'Create company'
        company = create_company()
        self.assert_(company)

    @with_transaction()
    def test_company_recursion(self):
        'Test company recursion'
        pool = Pool()
        Company = pool.get('company.company')

        company1 = create_company()
        company2 = create_company('Michael Scott Paper Company')
        company2.parent = company1
        company2.save()
        self.assert_(company2)

        self.assertRaises(Exception, Company.write,
            [company1], {
                'parent': company2.id,
                })

    @with_transaction()
    def test_employe(self):
        'Create employee'
        pool = Pool()
        Party = pool.get('party.party')
        Employee = pool.get('company.employee')
        company1 = create_company()

        party, = Party.create([{
                    'name': 'Pam Beesly',
                    }])
        employee, = Employee.create([{
                    'party': party.id,
                    'company': company1.id,
                    }])
        self.assert_(employee)

    @with_transaction()
    def test_user(self):
        'Test user company'
        pool = Pool()
        User = pool.get('res.user')
        transaction = Transaction()

        company1 = create_company()
        company2 = create_company('Michael Scott Paper Company',
            currency=company1.currency)
        company2.parent = company1
        company2.save()

        user1, user2 = User.create([{
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
            user1, user2 = User.browse([user1.id, user2.id])
            self.assertEqual(user1.company, company1)
            self.assertEqual(user2.company, company2)

            with transaction.set_context({'company': company2.id}):
                user1, user2 = User.browse([user1.id, user2.id])
                self.assertEqual(user1.company, company2)
                self.assertEqual(user2.company, company2)

            with transaction.set_context({'company': None}):
                user1, user2 = User.browse([user1.id, user2.id])
                self.assertEqual(user1.company, None)
                self.assertEqual(user2.company, company2)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            CompanyTestCase))
    return suite
