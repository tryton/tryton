# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import io
import math
import os
import uuid
from random import Random
from urllib.parse import quote, urljoin

try:
    import PIL
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    PIL = None

from trytond.config import config
from trytond.model import ModelSQL, Unique, fields
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.wsgi import Base64Converter

from .resource import ResourceMixin

if config.getboolean('database', 'avatar_filestore', default=False):
    file_id = 'image_id'
    store_prefix = config.get('database', 'avatar_prefix', default=None)
else:
    file_id = None
    store_prefix = None
URL_BASE = config.get('web', 'avatar_base', default='')
FONT = os.path.join(os.path.dirname(__file__), 'fonts', 'karla.ttf')


class ImageMixin:
    __slots__ = ()
    image = fields.Binary(
        "Image", file_id=file_id, store_prefix=store_prefix)
    image_id = fields.Char("Image ID", readonly=True)


class Avatar(ImageMixin, ResourceMixin, ModelSQL):
    "Avatar"
    __name__ = 'ir.avatar'

    uuid = fields.Char("UUID", required=True)
    cache = fields.One2Many('ir.avatar.cache', 'avatar', "Cache")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('resource_unique', Unique(t, t.resource),
                'ir.msg_avatar_resource_unique'),
            ]

    @classmethod
    def default_uuid(cls):
        return uuid.uuid4().hex

    @classmethod
    def create(cls, vlist):
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            values.setdefault('uuid', cls.default_uuid())
        return super().create(vlist)

    @classmethod
    def write(cls, *args):
        avatars = sum(args[0:None:2], [])
        super().write(*args)
        cls.clear_cache(avatars)

    @classmethod
    def copy(cls, avatars, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('uuid', None)
        default.setdefault('cache', None)
        return super().copy(avatars, default=default)

    @property
    def url(self):
        if self.image_id or self.image:
            return urljoin(
                URL_BASE, quote('/avatar/%(database)s/%(uuid)s' % {
                        'database': Base64Converter(None).to_url(
                            Transaction().database.name),
                        'uuid': self.uuid,
                        }))

    def get(self, size=64):
        size = min((
                2 ** math.ceil(math.log2(size)),
                10 * math.ceil(size / 10) if size <= 100
                else 50 * math.ceil(size / 50)))
        if not (0 < size <= 2048):
            raise ValueError("Invalid size")
        for avatar in self.cache:
            if avatar.size == size:
                return avatar.image
        if not self.image:
            return None
        if PIL:
            with Transaction().new_transaction():
                cache = self._store_cache(size, self._resize(size))
                # Save cache only if record is already committed
                if self.__class__.search([('id', '=', self.id)]):
                    cache.save()
                return cache.image
        else:
            return self.image

    @classmethod
    def convert(cls, image, **_params):
        if not PIL or not image:
            return image
        data = io.BytesIO()
        img = Image.open(io.BytesIO(image))
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
            img.convert('RGBA')
            background = Image.new('RGBA', img.size, (255, 255, 255))
            background.alpha_composite(img)
            img = background.convert('RGB')
        img.save(data, format='jpeg', optimize=True, **_params)
        return data.getvalue()

    def _resize(self, size=64, **_params):
        if not PIL:
            return self.image
        data = io.BytesIO()
        img = Image.open(io.BytesIO(self.image))
        img = img.resize((size, size))
        img.save(data, format='jpeg', optimize=True, **_params)
        return data.getvalue()

    def _store_cache(self, size, image):
        pool = Pool()
        Cache = pool.get('ir.avatar.cache')
        return Cache(
            avatar=self,
            image=image,
            size=size)

    @classmethod
    def clear_cache(cls, avatars):
        pool = Pool()
        Cache = pool.get('ir.avatar.cache')
        caches = [c for a in avatars for c in a.cache]
        Cache.delete(caches)


class AvatarCache(ImageMixin, ModelSQL):
    "Avatar Cache"
    __name__ = 'ir.avatar.cache'

    avatar = fields.Many2One(
        'ir.avatar', "Avatar", required=True, ondelete='CASCADE')
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
            ('size_unique', Unique(t, t.avatar, t.size),
                'ir.msg_avatar_size_unique'),
            ]
        cls._order.append(('size', 'ASC'))


def generate(size, string):
    if not PIL:
        return

    def background_color(string):
        random = Random(string)
        r = v = b = 255
        # Skip too bright color
        while r + v + b > 255 * 2:
            r = random.randint(0, 255)
            v = random.randint(0, 255)
            b = random.randint(0, 255)
        return r, v, b

    try:
        font = ImageFont.truetype(FONT, size=int(0.65 * size))
    except ImportError:
        return
    white = (255, 255, 255)
    image = Image.new('RGB', (size, size), background_color(string))
    draw = ImageDraw.Draw(image)
    letter = string[0].upper() if string else ''
    draw.text(
        (size / 2, size / 2), letter, fill=white, font=font, anchor='mm')
    data = io.BytesIO()
    image.save(data, format='jpeg', optimize=True)
    return data.getvalue()
