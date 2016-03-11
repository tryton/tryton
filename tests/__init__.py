# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.timesheet_cost.tests.test_timesheet_cost import suite
except ImportError:
    from .test_timesheet_cost import suite

__all__ = ['suite']
