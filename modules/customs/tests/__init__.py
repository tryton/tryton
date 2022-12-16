# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
try:
    from trytond.modules.customs.tests.test_customs import suite
except ImportError:
    from .test_customs import suite

__all__ = ['suite']
