# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.purchase_secondary_unit.tests.test_purchase_secondary_unit import suite
except ImportError:
    from .test_purchase_secondary_unit import suite

__all__ = ['suite']
