# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.currency_ro.tests.test_currency_ro import suite  # noqa: E501
except ImportError:
    from .test_currency_ro import suite

__all__ = ['suite']
