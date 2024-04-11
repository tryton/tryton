# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.tests.test_tryton import ModuleTestCase


class AccountExportWinbooksTestCase(ModuleTestCase):
    "Test Account Export Winbooks module"
    module = 'account_export_winbooks'
    extras = ['account_be']
    language = 'fr'


del ModuleTestCase
