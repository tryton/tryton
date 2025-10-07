# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import random
import time
from collections import defaultdict
from email.message import EmailMessage
from functools import lru_cache, partial
from urllib.parse import (
    parse_qs, parse_qsl, urlencode, urljoin, urlsplit, urlunsplit)

from genshi.core import END, START, Attrs, QName
from genshi.template import MarkupTemplate
from genshi.template import TemplateError as GenshiTemplateError
from sql import Literal
from sql.aggregate import Count

try:
    import html2text
except ImportError:
    html2text = None

import trytond.config as config
from trytond.i18n import gettext
from trytond.ir.session import token_hex
from trytond.model import (
    DeactivableMixin, Index, ModelSQL, ModelView, Unique, Workflow, fields)
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.report import Report, get_email
from trytond.sendmail import SMTPDataManager, send_message_transactional
from trytond.tools import grouped_slice, reduce_ids
from trytond.tools.email_ import (
    EmailNotValidError, format_address, normalize_email, set_from_header,
    validate_email)
from trytond.transaction import Transaction, inactive_records
from trytond.url import http_host
from trytond.wizard import Button, StateTransition, StateView, Wizard

from .exceptions import EMailValidationError, TemplateError


def _add_params(url, **params):
    parts = urlsplit(url)
    query = parse_qsl(parts.query)
    for key, value in sorted(params.items()):
        query.append((key, value))
    parts = list(parts)
    parts[3] = urlencode(query)
    return urlunsplit(parts)


def _extract_params(url):
    return parse_qsl(urlsplit(url).query)


class Email(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'marketing.email'
    _rec_name = 'email'

    email = fields.Char("Email", required=True)
    list_ = fields.Many2One('marketing.email.list', "List", required=True)
    email_token = fields.Char("Email Token", required=True)
    web_user = fields.Function(
        fields.Many2One('web.user', "Web User"), 'get_web_user')
    party = fields.Function(
        fields.Many2One('party.party', "Party"), 'get_web_user')

    @classmethod
    def __setup__(cls):
        super().__setup__()

        t = cls.__table__()
        cls._sql_constraints = [
            ('email_list_unique', Unique(t, t.email, t.list_),
                'marketing_email.msg_email_list_unique'),
            ]
        cls._sql_indexes.add(Index(
                t,
                (t.list_, Index.Range()),
                (t.email, Index.Equality(cardinality='high'))))

    @classmethod
    def default_email_token(cls, nbytes=None):
        return token_hex(nbytes)

    @classmethod
    def get_web_user(cls, records, names):
        pool = Pool()
        WebUser = pool.get('web.user')
        result = {}
        web_user = 'web_user' in names
        if web_user:
            web_users = dict.fromkeys(list(map(int, records)))
            result['web_user'] = web_users
        party = 'party' in names
        if party:
            parties = dict.fromkeys(list(map(int, records)))
            result['party'] = parties
        for sub_records in grouped_slice(records):
            email2id = {r.email: r.id for r in sub_records}
            users = WebUser.search([
                    ('email', 'in', list(email2id.keys())),
                    ])
            if web_user:
                web_users.update((email2id[u.email], u.id) for u in users)
            if party:
                parties.update(
                    (email2id[u.email], u.party.id)
                    for u in users if u.party)
        return result

    @classmethod
    def preprocess_values(cls, mode, values):
        values = super().preprocess_values(mode, values)
        if mode == 'create':
            # Ensure to get a different token for each record
            # default methods are called only once
            values.setdefault('email_token', cls.default_email_token())
        if values.get('email'):
            values['email'] = normalize_email(values['email']).lower()
        return values

    @classmethod
    def validate_fields(cls, records, fields_names):
        super().validate_fields(records, fields_names)
        cls.check_valid_email(records, fields_names)

    @classmethod
    def check_valid_email(cls, records, fields_names=None):
        if fields_names and 'email' not in fields_names:
            return
        for record in records:
            if record.email:
                try:
                    validate_email(record.email)
                except EmailNotValidError as e:
                    raise EMailValidationError(gettext(
                            'marketing_email.msg_email_invalid',
                            record=record.rec_name,
                            email=record.email),
                        str(e)) from e

    def get_email_subscribe(self, report_name='marketing.email.subscribe'):
        pool = Pool()
        ActionReport = pool.get('ir.action.report')
        report, = ActionReport.search([
            ('report_name', '=', report_name),
            ], limit=1)
        return get_email(report, self, [self.list_.language])

    def get_email_subscribe_url(self, url=None):
        if url is None:
            url = config.get('marketing', 'email_subscribe_url')
        return _add_params(url, token=self.email_token)

    @classmethod
    def subscribe_url(cls, url):
        parts = urlsplit(url)
        tokens = filter(
            None, parse_qs(parts.query).get('token', [None]))
        return cls.subscribe(list(tokens))

    @classmethod
    def subscribe(cls, tokens):
        # Make it slow to prevent brute force attacks
        delay = config.getint('marketing', 'subscribe_delay', default=1)
        Transaction().atexit(time.sleep, delay)
        with inactive_records():
            records = cls.search([
                    ('email_token', 'in', tokens),
                    ])
        cls.write(records, {'active': True})
        return bool(records)

    def get_email_unsubscribe(self, report_name='marketing.email.unsubscribe'):
        pool = Pool()
        ActionReport = pool.get('ir.action.report')
        report, = ActionReport.search([
                ('report_name', '=', report_name),
                ], limit=1)
        return get_email(report, self, [self.list_.language])

    def get_email_unsubscribe_url(self, url=None):
        if url is None:
            url = config.get('marketing', 'email_unsubscribe_url')
        return _add_params(url, token=self.email_token)

    @classmethod
    def unsubscribe_url(cls, url):
        parts = urlsplit(url)
        tokens = filter(
            None, parse_qs(parts.query).get('token', [None]))
        cls.unsubscribe(list(tokens))

    @classmethod
    def unsubscribe(cls, tokens):
        # Make it slow to prevent brute force attacks
        delay = config.getint('marketing', 'subscribe_delay', default=1)
        Transaction().atexit(time.sleep, delay)
        records = cls.search([
                ('email_token', 'in', tokens),
                ])
        cls.write(records, {'active': False})
        return bool(records)


class EmailSubscribe(Report):
    __name__ = 'marketing.email.subscribe'

    @classmethod
    def get_context(cls, records, header, data):
        context = super().get_context(records, header, data)
        context['extract_params'] = _extract_params
        return context


class EmailUnsubscribe(Report):
    __name__ = 'marketing.email.unsubscribe'

    @classmethod
    def get_context(cls, records, header, data):
        context = super().get_context(records, header, data)
        context['extract_params'] = _extract_params
        return context


class EmailList(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'marketing.email.list'

    name = fields.Char("Name", required=True)
    language = fields.Many2One('ir.lang', "Language", required=True)
    emails = fields.One2Many('marketing.email', 'list_', "Emails")
    subscribed = fields.Function(
        fields.Integer("Subscribed"), 'get_subscribed')

    @staticmethod
    def default_language():
        Lang = Pool().get('ir.lang')
        code = Transaction().context.get(
            'language', config.get('database', 'language'))
        try:
            lang, = Lang.search([
                    ('code', '=', code),
                    ('translatable', '=', True),
                    ], limit=1)
            return lang.id
        except ValueError:
            return None

    @classmethod
    def get_subscribed(cls, lists, name):
        pool = Pool()
        Email = pool.get('marketing.email')
        email = Email.__table__()
        cursor = Transaction().connection.cursor()

        subscribed = defaultdict(int)
        query = email.select(
            email.list_, Count(Literal('*')), group_by=[email.list_])
        for sub_lists in grouped_slice(lists):
            query.where = (
                reduce_ids(email.list_, sub_lists)
                & email.active)
            cursor.execute(*query)
            subscribed.update(cursor)
        return subscribed

    def request_subscribe(self, email, from_=None):
        pool = Pool()
        Email = pool.get('marketing.email')

        # Randomize processing time to prevent guessing whether the email
        # address is already subscribed to the list or not.
        Transaction().atexit(time.sleep, random.random())

        email = email.lower()
        with inactive_records():
            records = Email.search([
                    ('email', '=', email),
                    ('list_', '=', self.id),
                    ])
        if not records:
            record = Email(email=email, list_=self.id, active=False)
            record.save()
        else:
            record, = records
        if not record.active:
            from_cfg = (config.get('marketing', 'email_from')
                or config.get('email', 'from'))
            msg, title = record.get_email_subscribe()
            set_from_header(msg, from_cfg, from_ or from_cfg)
            msg['To'] = record.email
            msg['Subject'] = title
            send_message_transactional(msg)

    def request_unsubscribe(self, email, from_=None):
        pool = Pool()
        Email = pool.get('marketing.email')

        # Randomize processing time to prevent guessing whether the email
        # address was subscribed to the list or not.
        Transaction().atexit(time.sleep, random.random())

        email = email.lower()
        with inactive_records():
            records = Email.search([
                    ('email', '=', email),
                    ('list_', '=', self.id),
                    ])
        if records:
            record, = records
            if record.active:
                from_cfg = (config.get('marketing', 'email_from')
                    or config.get('email', 'from'))
                msg, title = record.get_email_unsubscribe()
                set_from_header(msg, from_cfg, from_ or from_cfg)
                msg['To'] = record.email
                msg['Subject'] = title
                send_message_transactional(msg)


class Message(Workflow, ModelSQL, ModelView):
    __name__ = 'marketing.email.message'
    _rec_name = 'title'

    _states = {
        'readonly': Eval('state') != 'draft',
        }
    from_ = fields.Char(
        "From", states=_states,
        help="Leave empty for the value defined in the configuration file.")
    list_ = fields.Many2One(
        'marketing.email.list', "List",
        required=True, states=_states)
    title = fields.Char(
        "Title", required=True, states=_states)
    content = fields.Text(
        "Content",
        states={
            'required': Eval('state') != 'draft',
            'readonly': _states['readonly'],
            })
    urls = fields.One2Many(
        'web.shortened_url', 'record', "URLs", readonly=True)
    state = fields.Selection([
            ('draft', "Draft"),
            ('sending', "Sending"),
            ('sent', "Sent"),
            ], "State", readonly=True, sort=False)
    del _states

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_indexes.add(
            Index(
                t, (t.state, Index.Equality(cardinality='low')),
                where=t.state.in_(['draft', 'sending'])))
        cls._transitions |= set([
                ('draft', 'sending'),
                ('sending', 'sent'),
                ('sending', 'draft'),
                ])
        cls._buttons.update({
                'draft': {
                    'invisible': Eval('state') != 'sending',
                    'depends': ['state'],
                    },
                'send': {
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                'send_test': {
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def default_state(cls):
        return 'draft'

    @classmethod
    def validate_fields(cls, messages, field_names):
        super().validate_fields(messages, field_names)
        cls.check_content(messages, field_names)

    @classmethod
    def check_content(cls, messages, field_names=None):
        if field_names and 'content' not in field_names:
            return
        for message in messages:
            if not message.content:
                continue
            try:
                MarkupTemplate(message.content)
            except GenshiTemplateError as exception:
                raise TemplateError(
                    gettext('marketing_email'
                        '.msg_message_invalid_content',
                        message=message.rec_name,
                        exception=exception)) from exception

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, messages):
        pass

    @classmethod
    @ModelView.button_action('marketing_email.wizard_send_test')
    def send_test(cls, messages):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('sending')
    def send(cls, messages):
        pass

    @classmethod
    @Workflow.transition('sent')
    def sent(cls, messages):
        pass

    @classmethod
    def process(cls, messages=None, emails=None, smtpd_datamanager=None):
        pool = Pool()
        WebShortener = pool.get('web.shortened_url')
        spy_pixel = config.getboolean(
            'marketing', 'email_spy_pixel', default=False)

        url_base = config.get('marketing', 'email_base', default=http_host())
        url_open = urljoin(url_base, '/m/empty.gif')

        @lru_cache(None)
        def short(url, record):
            url = WebShortener(
                record=record,
                redirect_url=url)
            url.save()
            return url.shortened_url

        def convert_href(message):
            def filter_(stream):
                for kind, data, pos in stream:
                    if kind is START:
                        tag, attrs = data
                        if tag == 'a' and attrs.get('href'):
                            href = attrs.get('href')
                            attrs -= 'href'
                            href = short(href, str(message))
                            attrs |= [(QName('href'), href)]
                            data = tag, attrs
                    elif kind is END and data == 'body' and spy_pixel:
                        yield START, (QName('img'), Attrs([
                                    (QName('src'), short(
                                            url_open, str(message))),
                                    (QName('height'), '1'),
                                    (QName('width'), '1'),
                                    ])), pos
                        yield END, QName('img'), pos
                    yield kind, data, pos
            return filter_

        if not smtpd_datamanager:
            smtpd_datamanager = SMTPDataManager()
        if messages is None:
            messages = cls.search([
                    ('state', '=', 'sending'),
                    ])

        for message in messages:
            try:
                template = MarkupTemplate(message.content)
            except GenshiTemplateError as exception:
                raise TemplateError(
                    gettext('marketing_email'
                        '.msg_message_invalid_content',
                        message=message.rec_name,
                        exception=exception)) from exception
            for email in (emails or message.list_.emails):
                content = (template
                    .generate(
                        email=email,
                        short=partial(short, record=message))
                    .filter(convert_href(message))
                    .render())

                name = email.party.rec_name if email.party else ''
                from_cfg = (config.get('marketing', 'email_from')
                    or config.get('email', 'from'))
                to = format_address(email.email, name)

                msg = EmailMessage()
                set_from_header(msg, from_cfg, message.from_ or from_cfg)
                msg['To'] = to
                msg['Subject'] = message.title
                msg['List-Unsubscribe'] = (
                    f'<{email.get_email_unsubscribe_url()}>')
                msg['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'
                if html2text:
                    converter = html2text.HTML2Text()
                    content_text = converter.handle(content)
                    msg.add_alternative(content_text, subtype='plain')
                if msg.is_multipart():
                    msg.add_alternative(content, subtype='html')
                else:
                    msg.set_content(content, subtype='html')

                send_message_transactional(msg, datamanager=smtpd_datamanager)
        if not emails:
            cls.sent(messages)


class SendTest(Wizard):
    __name__ = 'marketing.email.send_test'
    start = StateView(
        'marketing.email.send_test',
        'marketing_email.send_test_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Send", 'send', 'tryton-ok', default=True),
            ])
    send = StateTransition()

    def default_start(self, fields):
        pool = Pool()
        Message = pool.get('marketing.email.message')

        message = Message(Transaction().context.get('active_id'))
        return {
            'list_': message.list_.id,
            'message': message.id,
            }

    def transition_send(self):
        pool = Pool()
        Message = pool.get('marketing.email.message')
        Message.process([self.start.message], [self.start.email])
        return 'end'


class SendTestView(ModelView):
    __name__ = 'marketing.email.send_test'

    list_ = fields.Many2One(
        'marketing.email.list', "List", readonly=True)
    message = fields.Many2One(
        'marketing.email.message', "Message", readonly=True)
    email = fields.Many2One(
        'marketing.email', "Email", required=True,
        domain=[
            ('list_', '=', Eval('list_', -1)),
            ])
