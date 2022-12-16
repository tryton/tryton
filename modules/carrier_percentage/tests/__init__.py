# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.carrier_percentage.tests.test_carrier_percentage import suite  # noqa: E501
except ImportError:
    from .test_carrier_percentage import suite

__all__ = ['suite']
