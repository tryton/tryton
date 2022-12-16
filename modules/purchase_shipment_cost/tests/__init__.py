# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.purchase_shipment_cost.tests.test_purchase_shipment_cost import suite
except ImportError:
    from .test_purchase_shipment_cost import suite

__all__ = ['suite']
