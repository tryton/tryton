# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.account.tests.test_account import (
        suite, create_chart, get_fiscalyear)
except ImportError:
    from .test_account import suite, create_chart, get_fiscalyear

__all__ = ['suite', 'create_chart', 'get_fiscalyear']
