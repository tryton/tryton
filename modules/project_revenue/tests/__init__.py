# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.project_revenue.tests.test_project_revenue import suite
except ImportError:
    from .test_project_revenue import suite

__all__ = ['suite']
