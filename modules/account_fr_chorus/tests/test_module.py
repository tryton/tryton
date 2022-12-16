# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.company.tests import CompanyTestMixin
from trytond.tests.test_tryton import ModuleTestCase


class AccountFrChorusTestCase(CompanyTestMixin, ModuleTestCase):
    'Test Account Fr Chorus module'
    module = 'account_fr_chorus'
    extras = ['edocument_uncefact']


del ModuleTestCase
