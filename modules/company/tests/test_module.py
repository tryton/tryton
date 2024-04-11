# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt
from collections import defaultdict
from contextlib import contextmanager

from trytond.model import ModelStorage, ModelView
from trytond.modules.company.model import CompanyMultiValueMixin
from trytond.modules.currency.tests import add_currency_rate, create_currency
from trytond.modules.party.tests import PartyCheckEraseMixin
from trytond.pool import Pool, isregisteredby
from trytond.pyson import Eval, PYSONEncoder
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import Transaction


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
            'companies': [('add', [company.id])],
            'company': company.id,
                })
    with Transaction().set_context(User.get_preferences(context_only=True)):
        yield


class PartyCompanyCheckEraseMixin(PartyCheckEraseMixin):

    def setup_check_erase_party(self):
        create_company()
        return super().setup_check_erase_party()


class CompanyTestMixin:

    @with_transaction()
    def test_company_multivalue_context(self):
        "Test context of company multivalue target"
        pool = Pool()
        Company = pool.get('company.company')
        for mname, model in pool.iterobject():
            if (not isregisteredby(model, self.module)
                    or issubclass(model, Company)):
                continue
            company = None
            for fname, field in model._fields.items():
                if (field._type == 'many2one'
                        and issubclass(field.get_target(), Company)):
                    company = fname
                    break
            else:
                continue
            for fname, field in model._fields.items():
                if not hasattr(field, 'get_target'):
                    continue
                Target = field.get_target()
                if not issubclass(Target, CompanyMultiValueMixin):
                    continue
                if company in model._fields:
                    self.assertIn(
                        'company', list(field.context.keys()),
                        msg="Missing '%s' value as company "
                        'in "%s"."%s" context' % (
                            company, mname, fname))

    @property
    def _skip_company_rule(self):
        """Return a set of couple field name and model name
        for which no company rules are needed."""
        return {
            ('company.employee', 'company'),
            ('res.user', 'company'),
            }

    @with_transaction()
    def test_company_rule(self):
        "Test missing company rule"
        pool = Pool()
        Rule = pool.get('ir.rule')
        Company = pool.get('company.company')

        to_check = defaultdict(set)
        for mname, model in pool.iterobject():
            if (not isregisteredby(model, self.module)
                    or model.__access__
                    or not (issubclass(model, ModelView)
                        and issubclass(model, ModelStorage))):
                continue
            for fname, field in model._fields.items():
                if (mname, fname) in self._skip_company_rule:
                    continue
                if (field._type == 'many2one'
                        and issubclass(field.get_target(), Company)):
                    to_check[fname].add(mname)

        for fname, models in to_check.items():
            rules = Rule.search([
                    ('rule_group', 'where', [
                            ('model', 'in', list(models)),
                            ('global_p', '=', True),
                            ('perm_read', '=', True),
                            ]),
                    ('domain', '=', PYSONEncoder(sort_keys=True).encode(
                            [(fname, 'in', Eval('companies', []))])),
                    ])
            with_rules = {r.rule_group.model for r in rules}
            self.assertGreaterEqual(with_rules, models,
                msg='Models %(models)s are missing a global rule '
                'for field "%(field)s"' % {
                    'models': ', '.join(
                        f'"{m}"' for m in (models - with_rules)),
                    'field': fname,
                    })


class CompanyTestCase(
        PartyCompanyCheckEraseMixin, CompanyTestMixin, ModuleTestCase):
    'Test Company module'
    module = 'company'

    @with_transaction()
    def test_company(self):
        'Create company'
        company = create_company()
        self.assertTrue(company)

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
        company2.save()
        company3 = create_company()

        user1, user2 = User.create([{
                    'name': 'Jim Halper',
                    'login': 'jim',
                    'companies': [('add', [company1.id, company2.id])],
                    'company': company1.id,
                    }, {
                    'name': 'Pam Beesly',
                    'login': 'pam',
                    'companies': [('add', [company2.id])],
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
                self.assertEqual(user1.company, None)
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
        root.companies = None
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
                    'companies': [('add', [company.id])],
                    'company': company.id,
                    'employees': [('add', [employee1.id, employee2.id])],
                    'employee': employee1.id,
                    }, {
                    'name': "Pam Beesly",
                    'login': "pam",
                    'companies': [('add', [company.id])],
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
                self.assertEqual(user1.employee, None)
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

    @with_transaction()
    def test_company_header(self):
        "Test company header"
        company = create_company()
        company.party.email = 'company@example.com'
        company.party.save()
        company.header = "${name} - ${email}"
        company.save()

        self.assertEqual(
            company.header_used, "Dunder Mifflin - company@example.com")

    @with_transaction()
    def test_company_footer(self):
        "Test company footer"
        company = create_company()
        company.party.email = 'company@example.com'
        company.party.save()
        company.footer = "${name} - ${email}"
        company.save()

        self.assertEqual(
            company.footer_used, "Dunder Mifflin - company@example.com")

    @with_transaction()
    def test_employee_active_no_dates(self):
        "Test employee active with dates"
        pool = Pool()
        Employee = pool.get('company.employee')

        company = create_company()
        employee = create_employee(company, "Jim Halper")

        self.assertEqual(employee.active, True)
        self.assertEqual(Employee.search([
                    ('active', '=', True),
                    ]), [employee])
        self.assertEqual(Employee.search([
                    ('active', '!=', False),
                    ]), [employee])
        self.assertEqual(Employee.search([
                    ('active', '=', False),
                    ]), [])
        self.assertEqual(Employee.search([
                    ('active', '!=', True),
                    ]), [])

    @with_transaction()
    def test_employee_active_start_date(self):
        "Test employee active with start date"
        pool = Pool()
        Employee = pool.get('company.employee')

        company = create_company()
        employee = create_employee(company, "Jim Halper")
        employee.start_date = dt.date.today()
        employee.save()

        with Transaction().set_context(date=employee.start_date):
            self.assertEqual(Employee(employee).active, True)
            self.assertEqual(Employee.search([
                        ('active', '=', True),
                        ]), [employee])
        with Transaction().set_context(
                date=employee.start_date - dt.timedelta(days=1)):
            self.assertEqual(Employee(employee).active, False)
            self.assertEqual(Employee.search([
                        ('active', '=', True),
                        ]), [])
        with Transaction().set_context(
                date=employee.start_date + dt.timedelta(days=1)):
            self.assertEqual(Employee(employee).active, True)
            self.assertEqual(Employee.search([
                        ('active', '=', True),
                        ]), [employee])

    @with_transaction()
    def test_employee_active_end_date(self):
        "Test employee active with end date"
        pool = Pool()
        Employee = pool.get('company.employee')

        company = create_company()
        employee = create_employee(company, "Jim Halper")
        employee.end_date = dt.date.today()
        employee.save()

        with Transaction().set_context(date=employee.end_date):
            self.assertEqual(Employee(employee).active, True)
            self.assertEqual(Employee.search([
                        ('active', '=', True),
                        ]), [employee])
        with Transaction().set_context(
                date=employee.end_date - dt.timedelta(days=1)):
            self.assertEqual(Employee(employee).active, True)
            self.assertEqual(Employee.search([
                        ('active', '=', True),
                        ]), [employee])
        with Transaction().set_context(
                date=employee.end_date + dt.timedelta(days=1)):
            self.assertEqual(Employee(employee).active, False)
            self.assertEqual(Employee.search([
                        ('active', '=', True),
                        ]), [])


del ModuleTestCase
