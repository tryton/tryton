# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.marketing_automation.tests.test_marketing_automation import suite
except ImportError:
    from .test_marketing_automation import suite

__all__ = ['suite']
