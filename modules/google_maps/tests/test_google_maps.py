# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.pool import Pool


class GoogleMapsTestCase(ModuleTestCase):
    'Test GoogleMaps module'
    module = 'google_maps'

    @with_transaction()
    def test_google_maps_url(self):
        "Test Google Maps URL"
        pool = Pool()
        Address = pool.get('party.address')
        Party = pool.get('party.party')
        party = Party()
        party.save()
        address = Address()
        address.party = party
        address.street = "300 Cliff Street"
        address.zip = "18503"
        address.city = "Scranton"
        address.save()

        self.assertEqual(
            address.on_change_with_google_maps_url(),
            'http://maps.google.com/maps?hl=en&'
            'q=300%20Cliff%20Street%2018503%20Scranton')

        address = Address()
        address.party = party
        address.street = "Dépôt Street"
        address.zip = "18503"
        address.city = "Scranton"
        address.save()

        self.assertEqual(
            address.on_change_with_google_maps_url(),
            'http://maps.google.com/maps?hl=en&'
            'q=D%C3%A9p%C3%B4t%20Street%2018503%20Scranton')


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        GoogleMapsTestCase))
    return suite
