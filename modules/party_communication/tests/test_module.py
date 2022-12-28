# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.tests.test_tryton import ModuleTestCase


class PartyCommunicationTestCase(ModuleTestCase):
    "Test Party Communication module"
    module = 'party_communication'
    extras = ['account_invoice', 'purchase', 'purchase_request_quotation',
        'sale', 'sale_complaint', 'sale_opportunity', 'sale_subscription']


del ModuleTestCase
