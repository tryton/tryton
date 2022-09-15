# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt

from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class CountryTestCase(ModuleTestCase):
    'Test Country module'
    module = 'country'

    def create_membership(self, from_date=None, to_date=None):
        pool = Pool()
        Country = pool.get('country.country')
        Organization = pool.get('country.organization')
        OrganizationMember = pool.get('country.organization.member')

        organization = Organization(name="Organization")
        organization.save()
        country = Country(name="Country")
        country.save()
        member = OrganizationMember(
            organization=organization, country=country,
            from_date=from_date, to_date=to_date)
        member.save()
        return organization, country

    @with_transaction()
    def test_is_member_no_date(self):
        "Test is member without date"
        organization, country = self.create_membership()

        self.assertTrue(country.is_member(organization))
        self.assertTrue(country.is_member(organization, dt.date.min))
        self.assertTrue(country.is_member(organization, dt.date.max))

    @with_transaction()
    def test_is_member_with_from_date(self):
        "Test is member with from date"
        today = dt.date.today()
        yesterday = today - dt.timedelta(days=1)
        tomorrow = today + dt.timedelta(days=1)
        organization, country = self.create_membership(from_date=today)

        self.assertTrue(country.is_member(organization, today))
        self.assertFalse(country.is_member(organization, yesterday))
        self.assertTrue(country.is_member(organization, tomorrow))
        self.assertFalse(country.is_member(organization, dt.date.min))
        self.assertTrue(country.is_member(organization, dt.date.max))

    @with_transaction()
    def test_is_member_with_to_date(self):
        "Test is member with to date"
        today = dt.date.today()
        yesterday = today - dt.timedelta(days=1)
        tomorrow = today + dt.timedelta(days=1)
        organization, country = self.create_membership(to_date=today)

        self.assertTrue(country.is_member(organization, today))
        self.assertTrue(country.is_member(organization, yesterday))
        self.assertFalse(country.is_member(organization, tomorrow))
        self.assertTrue(country.is_member(organization, dt.date.min))
        self.assertFalse(country.is_member(organization, dt.date.max))

    @with_transaction()
    def test_is_member_with_dates(self):
        "Test is member with dates"
        today = dt.date.today()
        yesterday = today - dt.timedelta(days=1)
        tomorrow = today + dt.timedelta(days=1)
        organization, country = self.create_membership(
            from_date=yesterday, to_date=tomorrow)

        self.assertTrue(country.is_member(organization, today))
        self.assertTrue(country.is_member(organization, yesterday))
        self.assertFalse(country.is_member(organization, dt.date.min))
        self.assertFalse(country.is_member(organization, dt.date.max))


del ModuleTestCase
