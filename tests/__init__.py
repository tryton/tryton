# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.marketing.tests.test_marketing import suite
except ImportError:
    from .test_marketing import suite

__all__ = ['suite']
