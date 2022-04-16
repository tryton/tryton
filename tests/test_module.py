# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import io
import urllib.request

import PIL.Image

from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class ProductImageTestCase(ModuleTestCase):
    'Test Product Image module'
    module = 'product_image'

    @with_transaction()
    def test_image(self):
        "Test image"
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


del ModuleTestCase
