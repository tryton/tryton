# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.tests.test_tryton import ModuleTestCase


class SaleProjectTaskTestCase(ModuleTestCase):
    "Test Sale Project Task module"
    module = 'sale_project_task'
    extras = ['project_invoice', 'project_revenue']


del ModuleTestCase
