# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.web_shop_vue_storefront.tests.test_web_shop_vue_storefront import suite  # noqa: E501
except ImportError:
    from .test_web_shop_vue_storefront import suite

__all__ = ['suite']
