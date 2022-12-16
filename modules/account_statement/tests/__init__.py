# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.account_statement.tests.test_account_statement import suite
except ImportError:
    from .test_account_statement import suite

__all__ = ['suite']
