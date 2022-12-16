# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.sale_supply_drop_shipment.tests.test_sale_supply_drop_shipment import suite  # noqa: E501
except ImportError:
    from .test_sale_supply_drop_shipment import suite

__all__ = ['suite']
