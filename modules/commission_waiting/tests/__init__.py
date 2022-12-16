# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
try:
    from trytond.modules.commission_waiting.tests.test_commission_waiting import suite  # noqa: E501
except ImportError:
    from .test_commission_waiting import suite

__all__ = ['suite']
