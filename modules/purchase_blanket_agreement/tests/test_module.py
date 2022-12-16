# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase


class PurchaseBlanketAgreementTestCase(ModuleTestCase):
    "Test Purchase Blanket Agreement module"
    module = 'purchase_blanket_agreement'


del ModuleTestCase
