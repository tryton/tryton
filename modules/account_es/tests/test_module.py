# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase


class AccountTestCase(ModuleTestCase):
    'Test Account Es module'
    module = 'account_es'
    extras = ['account_asset', 'account_payment_sepa', 'sale_advance_payment']


del ModuleTestCase
