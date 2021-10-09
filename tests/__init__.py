# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.currency_rs.tests.test_currency_rs import suite  # noqa: E501
except ImportError:
    from .test_currency_rs import suite

__all__ = ['suite']
