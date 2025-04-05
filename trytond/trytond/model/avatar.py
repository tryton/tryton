# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import lazy_gettext
from trytond.model import fields
from trytond.pool import Pool


def avatar_mixin(size=64, default=None):
    class AvatarMixin:
        __slots__ = ()
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
            from trytond.ir.avatar import PIL, generate
            if not PIL:
                return
            pool = Pool()
            Avatar = pool.get('ir.avatar')
            avatars = []
            records = [r for r in records if not r.has_avatar]
            if not records:
                return
            for record in records:
                image = generate(size, getattr(record, field))
                if image:
                    if record.avatars:
                        avatar, = record.avatars
                    else:
                        avatar = Avatar(resource=record)
                    avatar.image = image
                    avatars.append(avatar)
            Avatar.save(avatars)

        @classmethod
        def copy(cls, avatars, default=None):
            if default is None:
                default = {}
            else:
                default = default.copy()
            default.setdefault('avatars', [])
            return super().copy(avatars, default=default)

        if default:

            @classmethod
            def on_modification(cls, mode, records, field_names=None):
                super().on_modification(mode, records, field_names=field_names)
                if mode in {'create', 'write'}:
                    cls.generate_avatar(records, field=default)

    return AvatarMixin
