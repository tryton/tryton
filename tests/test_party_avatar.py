# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest

from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import suite as test_suite

from trytond.modules.company.tests import CompanyTestMixin


class PartyAvatarTestCase(CompanyTestMixin, ModuleTestCase):
    'Test Party Avatar module'
    module = 'party_avatar'
    extras = ['company']


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            PartyAvatarTestCase))
    return suite
