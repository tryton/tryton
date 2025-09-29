# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import base64
import io
import math
from urllib.parse import quote, urlencode, urljoin

import PIL
import PIL.Image

import trytond.config as config
from trytond.i18n import gettext
from trytond.model import (
    MatchMixin, ModelSQL, ModelView, Unique, fields, sequence_ordered)
from trytond.pool import PoolMeta
from trytond.pyson import Bool, Eval, If
from trytond.tools import slugify
from trytond.transaction import Transaction
from trytond.url import http_host
from trytond.wsgi import Base64Converter

from .exceptions import ImageValidationError

if config.getboolean('product', 'image_filestore', default=False):
    file_id = 'image_id'
    store_prefix = config.get('product', 'image_prefix', default=None)
else:
    file_id = None
    store_prefix = None
SIZE_MAX = config.getint('product', 'image_size_max', default=2048)


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
                width = args.pop('w', None)
                height = args.pop('h', None)
                index = args.pop('i', None)
                args = {k: int(bool(v)) for k, v in args.items()}
                if size:
                    args['s'] = size
                if width:
                    args['w'] = width
                if height:
                    args['h'] = height
                if index is not None:
                    args['i'] = index
            timestamp = int((self.write_date or self.create_date).timestamp())
            args['t'] = (
                base64.urlsafe_b64encode(timestamp.to_bytes(8, 'big'))
                .decode().rstrip('='))
            url += '?' + urlencode(args)
            return url

    def get_image_url(self, _external=False, **args):
        url_base = config.get(
            'product', 'image_base', default='')
        url_external_base = config.get(
            'product', 'image_base', default=http_host())
        return self._image_url(
            url_external_base if _external else url_base, **args)

    @property
    def images_used(self):
        yield from self.images

    def get_images(self, pattern):
        Image = self.__class__.images.get_target()
        pattern = pattern.copy()
        for key in set(pattern.keys()) - Image.allowed_match_keys():
            del pattern[key]
        pattern = {k: bool(int(v)) for k, v in pattern.items()}
        for image in self.images_used:
            if image.match(pattern, match_none=True):
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


class _ImageMixin:
    __slots__ = ()
    image = fields.Binary(
        "Image", file_id=file_id, store_prefix=store_prefix, required=True)
    image_id = fields.Char("Image ID", readonly=True)


class ImageMixin(_ImageMixin):
    __slots__ = ()
    cache = None

    description = fields.Char("Description", translate=True)

    @classmethod
    def allowed_match_keys(cls):
        return set()

    @classmethod
    def preprocess_values(cls, mode, values):
        values = super().preprocess_values(mode, values)
        if values.get('image'):
            values['image'] = cls.convert(values['image'])
        return values

    @classmethod
    def on_modification(cls, mode, images, field_names=None):
        super().on_modification(mode, images, field_names=field_names)
        if mode == 'write':
            cls.clear_cache(images)

    @classmethod
    def _round_size(cls, size):
        return min((
                2 ** math.ceil(math.log2(size)),
                10 * math.ceil(size / 10) if size <= 100
                else 50 * math.ceil(size / 50)))

    def get(self, size=400):
        if isinstance(size, int):
            size = (size, size)
        size = tuple(map(self._round_size, size))
        if not all(0 < s <= SIZE_MAX for s in size):
            raise ValueError(f"Invalid size {size}")
        for cache in self.cache:
            if (cache.width, cache.height) == size:
                # re-instantiate to fetch only one image
                return cache.__class__(cache.id).image
        with Transaction().new_transaction():
            cache = self._store_cache(size, self._resize(size))
            # Save cache only if record is already committed
            if self.__class__.search([('id', '=', self.id)]):
                cache.save()
            return cache.image

    @classmethod
    def convert(cls, image, **_params):
        data = io.BytesIO()
        try:
            img = PIL.Image.open(io.BytesIO(image))
        except PIL.UnidentifiedImageError as e:
            raise ImageValidationError(gettext(
                    'product_image.msg_product_image_error'), str(e)) from e
        img.thumbnail((SIZE_MAX, SIZE_MAX))
        if img.mode != 'RGB':
            img = img.convert('RGBA')
            background = PIL.Image.new('RGBA', img.size, (255, 255, 255))
            background.alpha_composite(img)
            img = background.convert('RGB')
        img.save(data, format='jpeg', optimize=True, dpi=(300, 300), **_params)
        return data.getvalue()

    def _resize(self, size=64, **_params):
        data = io.BytesIO()
        img = PIL.Image.open(io.BytesIO(self.image))
        if isinstance(size, int):
            size = (size, size)
        img.thumbnail(size)
        img.save(data, format='jpeg', optimize=True, dpi=(300, 300), **_params)
        return data.getvalue()

    def _store_cache(self, size, image):
        Cache = self.__class__.cache.get_target()
        if isinstance(size, int):
            width = height = size
        else:
            width, height = size
        return Cache(
            image=image,
            width=width,
            height=height)

    @classmethod
    def clear_cache(cls, images):
        Cache = cls.cache.get_target()
        caches = [c for i in images for c in i.cache]
        Cache.delete(caches)


class Image(ImageMixin, sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    __name__ = 'product.image'
    template = fields.Many2One(
        'product.template', "Product",
        required=True, ondelete='CASCADE',
        domain=[
            If(Bool(Eval('product')),
                ('products', '=', Eval('product')),
                ()),
            ])
    product = fields.Many2One(
        'product.product', "Variant",
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
        cls.__access__.add('template')

    def _store_cache(self, size, image):
        cache = super()._store_cache(size, image)
        cache.product_image = self
        return cache


class ImageCacheMixin(_ImageMixin):
    __slots__ = ()

    width = fields.Integer(
        "Width", required=True,
        domain=[
            ('width', '>', 0),
            ('width', '<=', SIZE_MAX),
            ])
    height = fields.Integer(
        "Height", required=True,
        domain=[
            ('height', '>', 0),
            ('height', '<=', SIZE_MAX),
            ])


class ImageCache(ImageCacheMixin, ModelSQL):
    __name__ = 'product.image.cache'
    product_image = fields.Many2One(
        'product.image', "Product Image", required=True, ondelete='CASCADE')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('dimension_unique', Unique(t, t.product_image, t.width, t.height),
                'product_image.msg_image_cache_size_unique'),
            ]

    @classmethod
    def __register__(cls, module):
        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        table_h = cls.__table_handler__(module)

        super().__register__(module)

        # Migration from 7.0: split size into width and height
        table_h.drop_constraint('size_unique')
        if table_h.column_exist('size'):
            cursor.execute(*table.update(
                    [table.width, table.height],
                    [table.size, table.size]))
            table_h.drop_column('size')


class Category(ImageURLMixin, metaclass=PoolMeta):
    __name__ = 'product.category'
    __image_url__ = '/product-category/image'
    images = fields.One2Many('product.category.image', 'category', "Images")


class CategoryImage(
        ImageMixin, sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    __name__ = 'product.category.image'
    category = fields.Many2One(
        'product.category', "Category",
        required=True, ondelete='CASCADE')
    cache = fields.One2Many(
        'product.category.image.cache', 'category_image', "Cache",
        readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('category')

    def _store_cache(self, size, image):
        cache = super()._store_cache(size, image)
        cache.category_image = self
        return cache


class CategoryImageCache(ImageCacheMixin, ModelSQL):
    __name__ = 'product.category.image.cache'
    category_image = fields.Many2One(
        'product.category.image', "Category Image", required=True,
        ondelete='CASCADE')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('dimension_unique',
                Unique(t, t.category_image, t.width, t.height),
                'product_image.msg_image_cache_size_unique'),
            ]
