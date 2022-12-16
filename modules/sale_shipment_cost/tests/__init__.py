# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.sale_shipment_cost.tests.test_sale_shipment_cost import suite  # noqa: E501
except ImportError:
    from .test_sale_shipment_cost import suite

__all__ = ['suite']
