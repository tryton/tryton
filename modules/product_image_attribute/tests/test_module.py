# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import urllib.request

from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class ProductImageAttributeTestCase(ModuleTestCase):
    'Test Product Image Attribute module'
    module = 'product_image_attribute'

    @with_transaction()
    def test_image_attribute(self):
        "Test image with attribute"
        pool = Pool()
        Attribute = pool.get('product.attribute')
        AttributeSet = pool.get('product.attribute.set')
        Image = pool.get('product.image')
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        Uom = pool.get('product.uom')

        attribute1 = Attribute(name='attr1', string="Attribute 1")
        attribute1.type_ = 'char'
        attribute1.save()
        attribute2 = Attribute(name='attr2', string="Attribute 2")
        attribute2.type_ = 'integer'
        attribute2.save()
        attribute_set = AttributeSet(name="Attribute Set")
        attribute_set.attributes = [attribute1, attribute2]
        attribute_set.save()
        template = Template(name="Template")
        template.default_uom, = Uom.search([], limit=1)
        template.attribute_set = attribute_set
        product = Product(template=template)
        product.attributes = {
            'attr1': 'foo',
            'attr2': 2,
            }
        product.save()
        image1 = Image(template=template)
        image1.image = urllib.request.urlopen(
            'https://picsum.photos/200').read()
        image1.save()
        image2 = Image(template=template, product=product)
        image2.image = urllib.request.urlopen(
            'https://picsum.photos/200').read()
        image2.save()
        image3 = Image(template=template)
        image3.image = urllib.request.urlopen(
            'https://picsum.photos/200').read()
        image3.attributes = {
            'attr1': 'foo',
            }
        image3.save()
        image4 = Image(template=template)
        image4.image = urllib.request.urlopen(
            'https://picsum.photos/200').read()
        image4.attributes = {
            'attr1': 'bar',
            }
        image4.save()

        self.assertEqual(list(product.images_used), [image2, image1, image3])


del ModuleTestCase
