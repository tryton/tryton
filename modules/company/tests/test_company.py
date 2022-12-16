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


def create_employee(company, name="Pam Beesly"):
    pool = Pool()
    Party = pool.get('party.party')
    Employee = pool.get('company.employee')

    party, = Party.create([{
                'name': name,
                'addresses': [('create', [{}])],
                }])
    employee = Employee(party=party, company=company)
    employee.save()
    return employee


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
        self.assertTrue(company)

    @with_transaction()
    def test_company_recursion(self):
        'Test company recursion'
        pool = Pool()
        Company = pool.get('company.company')

        company1 = create_company()
        company2 = create_company('Michael Scott Paper Company')
        company2.parent = company1
        company2.save()
        self.assertTrue(company2)

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
        self.assertTrue(employee)

    @with_transaction()
    def test_user_company(self):
        'Test user company'
        pool = Pool()
        User = pool.get('res.user')
        transaction = Transaction()

        company1 = create_company()
        company2 = create_company('Michael Scott Paper Company',
            currency=company1.currency)
        company2.parent = company1
        company2.save()
        company3 = create_company()

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
        self.assertTrue(user1)

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

            with transaction.set_context(company=company3.id):
                user1, user2 = User.browse([user1.id, user2.id])
                self.assertEqual(user1.company, company1)
                self.assertEqual(user2.company, company2)

    @with_transaction()
    def test_user_root_company(self):
        "Test root user company"
        pool = Pool()
        User = pool.get('res.user')
        transaction = Transaction()
        company = create_company()
        root = User(0)
        root.company = None
        root.main_company = None
        root.save()

        with transaction.set_user(0):
            with Transaction().set_context(company=company.id):
                root = User(0)
                self.assertEqual(root.company, company)

    @with_transaction()
    def test_user_employee(self):
        "Test user employee"
        pool = Pool()
        User = pool.get('res.user')
        transaction = Transaction()

        company = create_company()

        employee1 = create_employee(company, "Jim Halper")
        employee2 = create_employee(company, "Pam Bessly")
        employee3 = create_employee(company, "Michael Scott")

        user1, user2 = User.create([{
                    'name': "Jim Halper",
                    'login': "jim",
                    'main_company': company.id,
                    'company': company.id,
                    'employees': [('add', [employee1.id, employee2.id])],
                    'employee': employee1.id,
                    }, {
                    'name': "Pam Beesly",
                    'login': "pam",
                    'main_company': company.id,
                    'company': company.id,
                    'employees': [('add', [employee2.id])],
                    'employee': employee2.id,
                    }])

        with transaction.set_user(user1.id):
            user1, user2 = User.browse([user1.id, user2.id])
            self.assertEqual(user1.employee, employee1)
            self.assertEqual(user2.employee, employee2)

            with transaction.set_context(employee=employee2.id):
                user1, user2 = User.browse([user1.id, user2.id])
                self.assertEqual(user1.employee, employee2)
                self.assertEqual(user2.employee, employee2)

            with transaction.set_context(employee=None):
                user1, user2 = User.browse([user1.id, user2.id])
                self.assertEqual(user1.employee, None)
                self.assertEqual(user2.employee, employee2)

            with transaction.set_context(employee=employee3.id):
                user1, user2 = User.browse([user1.id, user2.id])
                self.assertEqual(user1.employee, employee1)
                self.assertEqual(user2.employee, employee2)

    @with_transaction()
    def test_user_root_employee(self):
        "Test root user employee"
        pool = Pool()
        User = pool.get('res.user')
        transaction = Transaction()
        company = create_company()
        employee = create_employee(company, "Jim Halper")
        root = User(0)
        root.employee = None
        root.employees = None
        root.save()

        with transaction.set_user(0):
            with Transaction().set_context(employee=employee.id):
                root = User(0)
                self.assertEqual(root.employee, employee)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            CompanyTestCase))
    return suite
