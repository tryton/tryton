# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.sale_shipment_tolerance.tests.test_sale_shipment_tolerance import suite  # noqa: E501
except ImportError:
    from .test_sale_shipment_tolerance import suite

__all__ = ['suite']
