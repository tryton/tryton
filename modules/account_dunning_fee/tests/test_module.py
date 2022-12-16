# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase


class AccountDunningFeeTestCase(ModuleTestCase):
    'Test Account Dunning Fee module'
    module = 'account_dunning_fee'
    extras = ['account_dunning_letter']


del ModuleTestCase
