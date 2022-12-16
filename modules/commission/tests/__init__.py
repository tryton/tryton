# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
try:
    from trytond.modules.commission.tests.test_commission import suite
except ImportError:
    from .test_commission import suite

__all__ = ['suite']
