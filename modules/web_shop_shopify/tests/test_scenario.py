# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import os

from trytond.tests.test_tryton import TEST_NETWORK, load_doc_tests


def load_tests(*args, **kwargs):
    if (not TEST_NETWORK
            or not (os.getenv('SHOPIFY_PASSWORD')
                and os.getenv('SHOPIFY_URL'))):
        kwargs.setdefault('skips', set()).update({
                'scenario_web_shop_shopify.rst',
                'scenario_web_shop_shopify_secondary_unit.rst',
                })
    return load_doc_tests(__name__, __file__, *args, **kwargs)
