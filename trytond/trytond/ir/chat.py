# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import json
import uuid
from email.message import EmailMessage
from email.utils import getaddresses, make_msgid
from operator import itemgetter

from sql import Null
from sql.conditionals import NullIf

import trytond.config as config
from trytond.bus import Bus
from trytond.i18n import gettext
from trytond.model import ChatMixin, Check, ModelSQL, ModelView, Unique, fields
from trytond.model.exceptions import ValidationError
from trytond.pool import Pool
from trytond.pyson import Bool, Eval
from trytond.rpc import RPC
from trytond.sendmail import send_message_transactional
from trytond.tools import cached_property, firstline
from trytond.tools.email_ import (
    EmailNotValidError, normalize_email, set_from_header, validate_email)
from trytond.transaction import Transaction
from trytond.url import host

FOLLOWER_SEARCH_LIMIT = 20


class InvalidEMailError(ValidationError):
    pass


class Channel(ModelSQL, ModelView):
    "Chat Channel"
    __name__ = 'ir.chat.channel'

    resource = fields.Reference(
        "Resource", selection='get_models', required=True)
    followers = fields.One2Many(
        'ir.chat.follower', 'channel', "Followers")
    identifier = fields.Char("Identifier", readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('resource_unique', Unique(t, t.resource),
                'ir.msg_chat_channel_resource_unique'),
            ('identifier_unique', Unique(t, t.identifier),
                'ir.msg_chat_channel_identifier_unique'),
            ]
        cls.__rpc__.update(
            subscribe=RPC(readonly=False),
            unsubscribe=RPC(readonly=False),
            subscribe_email=RPC(readonly=False),
            unsubscribe_email=RPC(readonly=False),
            get_followers=RPC(),
            search_followers=RPC(),
            post=RPC(readonly=False, result=int),
            get_models=RPC(),
            get=RPC(),
            )
        cls._buttons.update({
                'reset_identifier': {
                    'icon': 'tryton-refresh',
                    },
                })

    @classmethod
    def preprocess_values(cls, mode, values):
        values = super().preprocess_values(mode, values)
        if mode == 'create' and 'identifier' not in values:
            values['identifier'] = uuid.uuid4().hex
        return values

    @cached_property
    def language(self):
        pool = Pool()
        Configuration = pool.get('ir.configuration')

        language = self.resource.chat_language(audience='public')
        if language is None:
            language = Configuration.get_language()
        return language

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
        model, id_ = str(resource).split(',')
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
        elif not Transaction().readonly:
            channel = cls(resource=str(resource))
            channel.save()
        else:
            return
        return channel

    @classmethod
    def subscribe(cls, resource, username=None):
        cls.check_access(resource)

        pool = Pool()
        Follower = pool.get('ir.chat.follower')
        User = pool.get('res.user')
        Message = pool.get('ir.message')
        ModelData = pool.get('ir.model.data')

        if username is not None:
            user, = User.search([
                    ('login', '=', username),
                    ])
        else:
            user = User(Transaction().user)
        channel = cls._get_channel(resource)
        Follower.add_user(channel, user)

        with Transaction().set_context(
                language=channel.language, user=0, _notify=False):
            msg = Message(ModelData.get_id('ir', 'msg_chat_follower_joined'))
            cls.post(resource, msg.text % {'name': user.login})

    @classmethod
    def unsubscribe(cls, resource, username=None):
        pool = Pool()
        Follower = pool.get('ir.chat.follower')
        User = pool.get('res.user')
        Message = pool.get('ir.message')
        ModelData = pool.get('ir.model.data')

        if username:
            cls.check_access(resource)
            try:
                user, = User.search([('login', '=', username)], limit=1)
            except ValueError:
                return None
        else:
            user = User(Transaction().user)

        channel = cls._get_channel(resource)
        Follower.remove_user(channel, user)

        with Transaction().set_context(
                language=channel.language, user=0, _notify=False):
            msg = Message(ModelData.get_id('ir', 'msg_chat_follower_left'))
            cls.post(resource, msg.text % {'name': user.login})

    @classmethod
    def subscribe_email(cls, resource, email):
        cls.check_access(resource)

        pool = Pool()
        Follower = pool.get('ir.chat.follower')
        Message = pool.get('ir.message')
        ModelData = pool.get('ir.model.data')

        channel = cls._get_channel(resource)
        Follower.add_email(channel, email)

        with Transaction().set_context(
                language=channel.language, user=0, _notify=False):
            msg = Message(ModelData.get_id('ir', 'msg_chat_follower_joined'))
            cls.post(resource, msg.text % {'name': email})

    @classmethod
    def unsubscribe_email(cls, resource, email):
        cls.check_access(resource)

        pool = Pool()
        Follower = pool.get('ir.chat.follower')
        Message = pool.get('ir.message')
        ModelData = pool.get('ir.model.data')

        channel = cls._get_channel(resource)
        Follower.remove_email(channel, email)

        with Transaction().set_context(
                language=channel.language, user=0, _notify=False):
            msg = Message(ModelData.get_id('ir', 'msg_chat_follower_left'))
            cls.post(resource, msg.text % {'name': email})

    @classmethod
    def _get_followers(cls, resource):
        pool = Pool()
        Follower = pool.get('ir.chat.follower')
        followers = {}
        channel = cls._get_channel(resource)
        if channel:
            chan_followers = Follower.search([
                    ('channel', '=', channel),
                    ])
            for f in chan_followers:
                if f.user:
                    followers['user', f.user.login] = {
                        'type': 'user',
                        'key': f.user.login,
                        'name': f'{f.user.name or f.user.login}',
                        'avatar_url': f.user.avatar_url,
                        }
                elif f.email:
                    followers['email', f.email] = {
                        'type': 'email',
                        'key': f.email,
                        'name': f.email,
                        'avatar_url': None,
                        }
        return followers

    @classmethod
    def get_followers(cls, resource):
        return sorted(
            cls._get_followers(resource).values(), key=itemgetter('name'))

    @classmethod
    def _search_followers(cls, resource, text):
        pool = Pool()
        User = pool.get('res.user')

        users = User.search([('rec_name', 'ilike', f'%{text}%')])
        return {
            ('user', u.login): {
                'type': 'user',
                'key': u.login,
                'name': f'{u.name or u.login}',
                'avatar_url': u.avatar_url,
                }
            for u in users}

    @classmethod
    def search_followers(cls, resource, text, limit=FOLLOWER_SEARCH_LIMIT):
        potential_followers = cls._search_followers(resource, text)
        current_followers = cls.get_followers(resource)

        for follower in current_followers:
            potential_followers.pop((follower['type'], follower['key']), None)

        return list(potential_followers.values())[:limit]

    @classmethod
    def post(cls, resource, content, audience='internal'):
        pool = Pool()
        Message = pool.get('ir.chat.message')
        User = pool.get('res.user')
        transaction = Transaction()
        ctx_user = User(transaction.context.get('user', transaction.user))
        channel = cls._get_channel(resource)
        message = Message(
            channel=channel,
            user=ctx_user,
            content=content,
            audience=audience)
        message.save()

        cls.dispatch_message(message, lambda u: u == ctx_user)

        return message

    @classmethod
    def _email_channel(cls, email):
        return None

    @classmethod
    def _email_content(cls, body):
        return body

    @classmethod
    def post_from_email(cls, email):
        pool = Pool()
        Message = pool.get('ir.chat.message')

        if 'From' in email:
            from_ = getaddresses([email.get('From')])[0][1]
        else:
            from_ = None
        channel = cls._email_channel(email)
        if channel is None:
            return

        if email.get_content_maintype() != 'multipart':
            content = email.get_payload()
        for part in email.walk():
            if part.get_content_type() == 'text/plain':
                content = part.get_payload()
                break

        message = Message(
            channel=channel,
            email=from_,
            audience='public',
            content=cls._email_content(content))
        message.save()

        cls.dispatch_message(message, lambda u: u == from_)

        return message

    @classmethod
    def _email_from(cls, message):
        return config.get('email', 'from')

    @classmethod
    def _email_reply_to(cls, message):
        return None

    @classmethod
    def _email_body(cls, message):
        return message.content

    @classmethod
    def dispatch_message(cls, message, is_sender):
        pool = Pool()
        Message = pool.get('ir.message')
        ModelData = pool.get('ir.model.data')

        Bus.publish(
            f'chat:{str(message.channel.resource)}', {
                'type': 'message',
                'message': message.as_dict(),
                })

        if not Transaction().context.get('_notify', True):
            return

        to_email = []
        for follower in message.channel.followers:
            if follower.user is not None and not is_sender(follower.user):
                follower.notify(message)
            if (message.audience != 'internal'
                    and follower.email is not None
                    and not is_sender(follower.email)):
                to_email.append(follower.email)

        if to_email:
            with Transaction().set_context(language=message.channel.language):
                subject_msg = Message(ModelData.get_id('ir', 'msg_subject'))
                subject = subject_msg.text

            from_ = cls._email_from(message)
            msg = EmailMessage()
            set_from_header(msg, from_, from_)
            if (reply_to := cls._email_reply_to(message)):
                msg['Reply-To'] = reply_to
            msg['Bcc'] = to_email
            msg['Auto-Submitted'] = 'auto-generated'
            msg['Message-ID'] = message.reference = make_msgid(domain=host())
            msg['Subject'] = subject % {
                'author': message.author,
                'resource': message.channel.resource.rec_name,
                }
            msg.set_content(cls._email_body(message))
            send_message_transactional(msg)

            message.save()

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

    @classmethod
    @ModelView.button
    def reset_identifier(cls, channels):
        for channel in channels:
            channel.identifier = uuid.uuid4().hex
        cls.save(channels)


class AuthorMixin:
    __slots__ = ()

    author = fields.Function(fields.Char("Author"), 'on_change_with_author')
    user = fields.Many2One(
        'res.user', "User", ondelete='CASCADE',
        states={
            'invisible': Bool(Eval('email')),
            })
    email = fields.Char(
        "Email",
        states={
            'invisible': Bool(Eval('user')),
            })

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
            if not self.user.id:
                return
            return self.user.name
        elif self.email:
            return self.email

    @property
    def avatar_url(self):
        if self.user:
            return self.user.avatar_url


class Follower(AuthorMixin, ModelView, ModelSQL):
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
        cls.__access__.add('channel')

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
        pool = Pool()
        Notification = pool.get('res.notification')

        if self.user:
            Notification(
                user=self.user,
                label=message.author,
                description=firstline(message.content),
                icon='tryton-chat',
                model=message.channel.resource.__name__,
                records=json.dumps([message.channel.resource.id])
                ).save()


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
    reference = fields.Char("Reference", readonly=True)

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
