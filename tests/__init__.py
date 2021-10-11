# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.account_move_line_grouping.tests.test_account_move_line_grouping import suite  # noqa: E501
except ImportError:
    from .test_account_move_line_grouping import suite

__all__ = ['suite']
