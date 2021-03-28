# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import lazy_gettext
from trytond.model import fields
from trytond.pool import Pool


def avatar_mixin(size=64, default=None):
    class AvatarMixin:

        avatars = fields.One2Many(
            'ir.avatar', 'resource', lazy_gettext('ir.msg_avatars'), size=1)
        avatar = fields.Function(
            fields.Binary(lazy_gettext('ir.msg_avatar')),
            '_get_avatar', setter='_set_avatar')
        avatar_url = fields.Function(
            fields.Char(lazy_gettext('ir.msg_avatar_url')), '_get_avatar_url')

        @property
        def has_avatar(self):
            if self.avatars:
                avatar, = self.avatars
                return bool(avatar.image_id or avatar.image)
            return False

        def _get_avatar(self, name):
            if self.avatars:
                avatar, = self.avatars
                return avatar.get(size=size)
            return None

        @classmethod
        def _set_avatar(cls, records, name, value):
            pool = Pool()
            Avatar = pool.get('ir.avatar')
            avatars = []
            image = Avatar.convert(value)
            for record in records:
                if record.avatars:
                    avatar, = record.avatars
                else:
                    avatar = Avatar(resource=record)
                avatars.append(avatar)
            Avatar.save(avatars)
            # Use write the image to store only once in filestore
            Avatar.write(avatars, {
                    'image': image,
                    })

        def _get_avatar_url(self, name):
            if self.avatars:
                avatar, = self.avatars
                return avatar.url

        @classmethod
        def generate_avatar(cls, records, field='rec_name'):
            from trytond.ir.avatar import generate, PIL
            if not PIL:
                return
            records = [r for r in records if not r.has_avatar]
            if not records:
                return
            for record in records:
                record.avatar = generate(size, getattr(record, field))
            cls.save(records)

        if default:

            @classmethod
            def create(cls, vlist):
                records = super().create(vlist)
                cls.generate_avatar(records, field=default)
                return records

            @classmethod
            def write(cls, *args):
                records = sum(args[0:None:2], [])
                super().write(*args)
                cls.generate_avatar(records, field=default)

    return AvatarMixin
