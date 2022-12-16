# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.web_shop_shopify.tests.test_web_shop_shopify import suite  # noqa: E501
except ImportError:
    from .test_web_shop_shopify import suite

__all__ = ['suite']
