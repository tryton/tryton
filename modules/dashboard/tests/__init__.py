# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.dashboard.tests.test_dashboard import suite
except ImportError:
    from .test_dashboard import suite

__all__ = ['suite']
