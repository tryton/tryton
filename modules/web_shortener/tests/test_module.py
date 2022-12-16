# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import random
import sys

from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class WebShortenerTestCase(ModuleTestCase):
    'Test Web Shortener module'
    module = 'web_shortener'

    @with_transaction()
    def test_shorten(self):
        pool = Pool()
        ShortenedURL = pool.get('web.shortened_url')
        expand = ShortenedURL._expand
        shorten = ShortenedURL._shorten

        self.assertEqual(expand(shorten(0)), 0)
        self.assertEqual(expand(shorten(sys.maxsize)), sys.maxsize)

        for _ in range(10):
            x = random.randint(0, sys.maxsize)
            self.assertEqual(expand(shorten(x)), x)


del ModuleTestCase
