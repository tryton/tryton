# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
import io
import unittest
import urllib.request

import PIL.Image

from trytond.pool import Pool
from trytond.tests.test_tryton import (
    TEST_NETWORK, ModuleTestCase, with_transaction)


class ProductImageTestCase(ModuleTestCase):
    'Test Product Image module'
    module = 'product_image'

    @unittest.skipUnless(TEST_NETWORK, "requires network")
    @with_transaction()
    def test_image_square(self):
        "Test image square"
        pool = Pool()
        Image = pool.get('product.image')
        Template = pool.get('product.template')
        Uom = pool.get('product.uom')

        template = Template(name="Template")
        template.default_uom, = Uom.search([], limit=1)
        template.save()

        image = Image(template=template)
        image.image = urllib.request.urlopen(
            'https://picsum.photos/200').read()
        image.save()

        self.assertEqual(template.image_url, None)
        template.code = "CODE"
        template.save()
        self.assertRegex(
            template.image_url,
            r'/product/image/CODE/.*/Template\?s=64')

        img = PIL.Image.open(io.BytesIO(image.get(size=100)))
        self.assertEqual(img.size, (100, 100))

        img = PIL.Image.open(io.BytesIO(image.get(size=(150, 200))))
        self.assertEqual(img.size, (150, 150))

    @unittest.skipUnless(TEST_NETWORK, "requires network")
    @with_transaction()
    def test_image_non_square(self):
        "Test image non square"
        pool = Pool()
        Image = pool.get('product.image')
        Template = pool.get('product.template')
        Uom = pool.get('product.uom')

        template = Template(name="Template")
        template.default_uom, = Uom.search([], limit=1)
        template.save()

        image = Image(template=template)
        image.image = urllib.request.urlopen(
            'https://picsum.photos/200/400').read()
        image.save()

        self.assertEqual(template.image_url, None)
        template.code = "CODE"
        template.save()
        self.assertRegex(
            template.image_url,
            r'/product/image/CODE/.*/Template\?s=64')

        img = PIL.Image.open(io.BytesIO(image.get(size=100)))
        self.assertEqual(img.size, (50, 100))

        img = PIL.Image.open(io.BytesIO(image.get(size=(100, 200))))
        self.assertEqual(img.size, (100, 200))

    @with_transaction()
    def test_round_size(self):
        "Test round size"
        pool = Pool()
        Image = pool.get('product.image')
        for size, result in [
                (1, 1),
                (2, 2),
                (19, 20),
                (45, 50),
                (101, 128),
                (129, 150),
                ]:
            with self.subTest(size=size):
                self.assertEqual(Image._round_size(size), result)

    @unittest.skipUnless(TEST_NETWORK, "requires network")
    @with_transaction()
    def test_get_image_url(self):
        "Test get_image_url"
        pool = Pool()
        Image = pool.get('product.image')
        Template = pool.get('product.template')
        Uom = pool.get('product.uom')

        template = Template(name="Template", code="CODE")
        template.default_uom, = Uom.search([], limit=1)
        template.save()

        for _ in range(3):
            image = Image(template=template)
            image.image = urllib.request.urlopen(
                'https://picsum.photos/200').read()
            image.save()

        template.write_date = dt.datetime(2025, 1, 1)  # fix timestamp

        self.assertRegex(
            template.get_image_url(i=2),
            r'^/product/image/CODE/.*/Template\?i=2&t=AAAAAGd0hYA$')
        self.assertRegex(
            template.get_image_url(s=400),
            r'^/product/image/CODE/.*/Template\?s=400&t=AAAAAGd0hYA$')


del ModuleTestCase
