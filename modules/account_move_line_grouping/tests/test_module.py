# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase


class AccountMoveLineGroupingTestCase(ModuleTestCase):
    'Test Account Move Line Grouping module'
    module = 'account_move_line_grouping'


del ModuleTestCase
