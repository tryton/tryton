# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.production_work.tests.test_production_work import suite
except ImportError:
    from .test_production_work import suite

__all__ = ['suite']
