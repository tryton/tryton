# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.party.tests import PartyCheckReplaceMixin
from trytond.tests.test_tryton import ModuleTestCase


class AccountPaymentStripeTestCase(PartyCheckReplaceMixin, ModuleTestCase):
    'Test Account Payment Stripe module'
    module = 'account_payment_stripe'


del ModuleTestCase
