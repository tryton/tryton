# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.company.tests import CompanyTestMixin
except ImportError:
    class CompanyTestMixin:
        pass
from trytond.tests.test_tryton import ModuleTestCase


class PartyAvatarTestCase(CompanyTestMixin, ModuleTestCase):
    'Test Party Avatar module'
    module = 'party_avatar'
    extras = ['company']


del ModuleTestCase
