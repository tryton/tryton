# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.web_shop_vue_storefront_stripe.tests.test_web_shop_vue_storefront_stripe import suite  # noqa: E501
except ImportError:
    from .test_web_shop_vue_storefront_stripe import suite

__all__ = ['suite']
