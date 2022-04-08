# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import io
import math
from urllib.parse import quote, urlencode, urljoin

import PIL.Image

from trytond.config import config
from trytond.model import (
    MatchMixin, ModelSQL, ModelView, Unique, fields, sequence_ordered)
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, If
from trytond.tools import slugify
from trytond.transaction import Transaction
from trytond.url import http_host
from trytond.wsgi import Base64Converter

if config.getboolean('product', 'image_filestore', default=False):
    file_id = 'image_id'
    store_prefix = config.get('product', 'image_prefix', default=None)
else:
    file_id = None
    store_prefix = None
URL_BASE = config.get('product', 'image_base', default='')
URL_EXTERNAL_BASE = config.get('product', 'image_base', default=http_host())


class ImageURLMixin:
    __slots__ = ()
    __image_url__ = None
    images = None
    image_url = fields.Function(fields.Char("Image URL"), '_get_image_url')

    def _get_image_url(self, name):
        return self.get_image_url(s=64)

    def _image_url(self, base, **args):
        if self.code and list(self.images_used):
            url = urljoin(
                base, quote('%(prefix)s/%(code)s/%(database)s/%(name)s' % {
                        'prefix': self.__image_url__,
                        'database': Base64Converter(None).to_url(
                            Transaction().database.name),
                        'code': quote(self.code, ''),
                        'name': slugify(self.name),
                        }))
            if args:
                size = args.pop('s', None)
                args = {k: int(bool(v)) for k, v in args.items()}
                if size:
                    args['s'] = size
                url += '?' + urlencode(args)
            return url

    def get_image_url(self, _external=False, **args):
        return self._image_url(
            URL_EXTERNAL_BASE if _external else URL_BASE, **args)

    @property
    def images_used(self):
        yield from self.images

    def get_images(self, pattern):
        pool = Pool()
        Image = pool.get('product.image')
        pattern = pattern.copy()
        for key in set(pattern.keys()) - Image.allowed_match_keys():
            del pattern[key]
        pattern = {k: bool(int(v)) for k, v in pattern.items()}
        for image in self.images_used:
            if image.match(pattern):
                yield image


class Template(ImageURLMixin, metaclass=PoolMeta):
    __name__ = 'product.template'
    __image_url__ = '/product/image'
    images = fields.One2Many('product.image', 'template', "Images")


class Product(ImageURLMixin, metaclass=PoolMeta):
    __name__ = 'product.product'
    __image_url__ = '/product/variant/image'
    images = fields.One2Many(
        'product.image', 'product', "Images",
        domain=[
            ('template', '=', Eval('template', -1)),
            ])

    @property
    def images_used(self):
        yield from super().images_used
        for image in self.template.images_used:
            if not image.product:
                yield image


class ImageMixin:
    __slots__ = ()
    image = fields.Binary(
        "Image", file_id=file_id, store_prefix=store_prefix, required=True)
    image_id = fields.Char("Image ID", readonly=True)


class Image(ImageMixin, sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    "Product Image"
    __name__ = 'product.image'
    template = fields.Many2One(
        'product.template', "Product",
        required=True, ondelete='CASCADE', select=True,
        domain=[
            If(Bool(Eval('product')),
                ('products', '=', Eval('product')),
                ()),
            ])
    product = fields.Many2One(
        'product.product', "Variant", select=True,
        domain=[
            If(Bool(Eval('template')),
                ('template', '=', Eval('template')),
                ()),
            ])
    cache = fields.One2Many(
        'product.image.cache', 'product_image', "Cache", readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.update(['product', 'template'])

    @classmethod
    def allowed_match_keys(cls):
        return set()

    @classmethod
    def create(cls, vlist):
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            if values.get('image'):
                values['image'] = cls.convert(values['image'])
        return super().create(vlist)

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        args = []
        for images, values in zip(actions, actions):
            if values.get('image'):
                values = values.copy()
                values['image'] = cls.convert(values['image'])
            args.append(images)
            args.append(values)
        super().write(*args)
        cls.clear_cache(sum(args[0:None:2], []))

    def get(self, size=400):
        size = min((
                2 ** math.ceil(math.log2(size)),
                10 * math.ceil(size / 10) if size <= 100
                else 50 * math.ceil(size / 50)))
        if not (0 < size <= 2048):
            raise ValueError("Invalid size")
        for cache in self.cache:
            if cache.size == size:
                return cache.image
        with Transaction().new_transaction():
            cache = self._store_cache(size, self._resize(size))
            # Save cache only if record is already committed
            if self.__class__.search([('id', '=', self.id)]):
                cache.save()
            return cache.image

    @classmethod
    def convert(cls, image, **_params):
        data = io.BytesIO()
        img = PIL.Image.open(io.BytesIO(image))
        width, height = img.size
        size = min(width, height)
        img = img.crop((
                (width - size) // 2,
                (height - size) // 2,
                (width + size) // 2,
                (height + size) // 2))
        if size > 2048:
            img = img.resize((2048, 2048))
        if img.mode in {'RGBA', 'P'}:
            img = img.convert('RGB')
        img.save(data, format='jpeg', optimize=True, **_params)
        return data.getvalue()

    def _resize(self, size=64, **_params):
        data = io.BytesIO()
        img = PIL.Image.open(io.BytesIO(self.image))
        img = img.resize((size, size))
        img.save(data, format='jpeg', optimize=True, **_params)
        return data.getvalue()

    def _store_cache(self, size, image):
        pool = Pool()
        Cache = pool.get('product.image.cache')
        return Cache(
            product_image=self,
            image=image,
            size=size)

    @classmethod
    def clear_cache(cls, images):
        pool = Pool()
        Cache = pool.get('product.image.cache')
        caches = [c for i in images for c in i.cache]
        Cache.delete(caches)


class ImageCache(ImageMixin, ModelSQL):
    "Product Image Cache"
    __name__ = 'product.image.cache'
    product_image = fields.Many2One(
        'product.image', "Product Image", required=True, ondelete='CASCADE')
    size = fields.Integer(
        "Size", required=True,
        domain=[
            ('size', '>', 0),
            ('size', '<=', 2048),
            ])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('size_unique', Unique(t, t.product_image, t.size),
                'ir.msg_product_image_size_unique'),
            ]
        cls._order.append(('size', 'ASC'))
