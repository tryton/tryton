# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql import Null
from sql.conditionals import NullIf

from trytond.bus import Bus
from trytond.i18n import gettext
from trytond.model import ChatMixin, Check, ModelSQL, Unique, fields
from trytond.model.exceptions import ValidationError
from trytond.pool import Pool
from trytond.rpc import RPC
from trytond.tools.email_ import (
    EmailNotValidError, normalize_email, validate_email)
from trytond.transaction import Transaction


class InvalidEMailError(ValidationError):
    pass


class Channel(ModelSQL):
    "Chat Channel"
    __name__ = 'ir.chat.channel'

    resource = fields.Reference(
        "Resource", selection='get_models', required=True)
    followers = fields.One2Many(
        'ir.chat.follower', 'channel', "Followers")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('resource_unique', Unique(t, t.resource),
                'ir.msg_chat_channel_resource_unique'),
            ]
        cls.__rpc__.update(
            subscribe=RPC(readonly=False),
            unsubscribe=RPC(readonly=False),
            subscribe_email=RPC(readonly=False),
            unsubscribe_email=RPC(readonly=False),
            post=RPC(readonly=False, result=int),
            get_models=RPC(),
            get=RPC(),
            )

    @classmethod
    def get_models(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        return [
            (m, n) for m, n in Model.get_name_items()
            if issubclass(pool.get(m), ChatMixin)]

    @classmethod
    def check_access(cls, resource):
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        model, id_ = resource.split(',')
        ModelAccess.check(model, mode='read')
        # TODO check record rule

    @classmethod
    def _get_channel(cls, resource):
        cls.check_access(resource)
        channels = cls.search([
                ('resource', '=', str(resource)),
                ])
        if channels:
            channel, = channels
        else:
            channel = cls(resource=str(resource))
            channel.save()
        return channel

    @classmethod
    def subscribe(cls, resource, username):
        pool = Pool()
        Follower = pool.get('ir.chat.follower')
        User = pool.get('res.user')
        user, = User.search([
                ('login', '=', username),
                ])
        channel = cls._get_channel(resource)
        Follower.add_user(channel, user)

    @classmethod
    def unsubscribe(cls, resource):
        pool = Pool()
        Follower = pool.get('ir.chat.follower')
        User = pool.get('res.user')
        user = User(Transaction().user)
        channel = cls._get_channel(resource)
        Follower.remove_user(channel, user)

    @classmethod
    def subscribe_email(cls, resource, email):
        pool = Pool()
        Follower = pool.get('ir.chat.follower')
        channel = cls._get_channel(resource)
        Follower.add_email(channel, email)

    @classmethod
    def unsubscribe_email(cls, resource, email):
        pool = Pool()
        Follower = pool.get('ir.chat.follower')
        channel = cls._get_channel(resource)
        Follower.remove_email(channel, email)

    @classmethod
    def post(cls, resource, content, audience='internal'):
        pool = Pool()
        Message = pool.get('ir.chat.message')
        User = pool.get('res.user')
        user = User(Transaction().user)
        channel = cls._get_channel(resource)
        message = Message(
            channel=channel,
            user=user,
            content=content,
            audience=audience)
        message.save()

        Bus.publish(
            f'chat:{str(resource)}', {
                'type': 'message',
                'message': message.as_dict(),
                })
        for follower in channel.followers:
            follower.notify(message)

        return message

    @classmethod
    def get(cls, resource, before=None, after=None):
        pool = Pool()
        Message = pool.get('ir.chat.message')
        cls.check_access(resource)
        domain = [
            ('channel.resource', '=', resource),
            ]
        if before is not None:
            domain.append(('id', '<', int(before)))
        if after is not None:
            domain.append(('id', '>', int(after)))
        messages = Message.search(domain)
        return [m.as_dict() for m in messages]


class AuthorMixin:
    __slots__ = ()

    author = fields.Function(fields.Char("Author"), 'on_change_with_author')
    user = fields.Many2One('res.user', "User", ondelete='CASCADE')
    email = fields.Char("Email")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('check_user_or_email',
                Check(t,
                    ((t.user == Null) & (NullIf(t.email, '') != Null))
                    | ((t.user != Null) & (NullIf(t.email, '') == Null))),
                'ir.msg_chat_user_or_email'),
            ]

    @classmethod
    def validate_fields(cls, authors, field_names):
        super().validate_fields(authors, field_names)
        cls.check_valid_email(authors, field_names)

    @classmethod
    def check_valid_email(cls, authors, field_names=None):
        if field_names and 'email' not in field_names:
            return
        for author in authors:
            if author.email:
                try:
                    validate_email(author.email)
                except EmailNotValidError as e:
                    raise InvalidEMailError(gettext(
                            'ir.msg_chat_author_email_invalid',
                            email=author.email),
                        str(e)) from e

    @fields.depends('user', 'email')
    def on_change_with_author(self, name=None):
        if self.user:
            return self.user.name
        elif self.email:
            return self.email

    @property
    def avatar_url(self):
        if self.user:
            return self.user.avatar_url


class Follower(AuthorMixin, ModelSQL):
    "Chat Follower"
    __name__ = 'ir.chat.follower'

    channel = fields.Many2One(
        'ir.chat.channel', "Channel", required=True, ondelete='CASCADE')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('channel_user_unique',
                Unique(t, t.channel, t.user),
                'ir.msg_chat_follower_channel_user_unique'),
            ('channel_email_unique',
                Unique(t, t.channel, t.email),
                'ir.msg_chat_follower_channel_email_unique'),
            ]

    @classmethod
    def add_user(cls, channel, user):
        if not cls.search([
                    ('channel', '=', channel),
                    ('user', '=', user),
                    ]):
            cls(channel=channel, user=user).save()

    @classmethod
    def remove_user(cls, channel, user):
        cls.delete(cls.search([
                    ('channel', '=', channel),
                    ('user', '=', user),
                    ]))

    @classmethod
    def add_email(cls, channel, email):
        email = normalize_email(email)
        if not cls.search([
                    ('channel', '=', channel),
                    ('email', '=', email),
                    ]):
            cls(channel=channel, email=email).save()

    @classmethod
    def remove_email(cls, channel, email):
        email = normalize_email(email)
        cls.delete(cls.search([
                    ('channel', '=', channel),
                    ('email', '=', email),
                    ]))

    def notify(self, message):
        pass


class Message(AuthorMixin, ModelSQL):
    "Chat Message"
    __name__ = 'ir.chat.message'

    channel = fields.Many2One(
        'ir.chat.channel', "Channel", required=True, ondelete='RESTRICT')
    content = fields.Text("Content", required=True)
    audience = fields.Selection([
            ('internal', "Internal"),
            ('public', "Public"),
            ], "Audience", required=True)

    @classmethod
    def default_audience(cls):
        return 'public'

    def as_dict(self):
        return {
            'id': self.id,
            'timestamp': self.create_date,
            'user': self.user.id if self.user else None,
            'author': self.author,
            'avatar_url': self.avatar_url,
            'content': self.content,
            'audience': self.audience,
            }
