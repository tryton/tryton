# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import random
import time
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, getaddresses
from functools import lru_cache
from urllib.parse import (
    parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit, urljoin)

from genshi.template import MarkupTemplate
from genshi.core import START, END, QName, Attrs
try:
    import html2text
except ImportError:
    html2text = None

from trytond.config import config
from trytond.i18n import gettext
from trytond.ir.session import token_hex
from trytond.model import (
    DeactivableMixin, Workflow, ModelSQL, ModelView, Unique, fields)
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.report import Report
from trytond.report import get_email
from trytond.sendmail import sendmail_transactional, SMTPDataManager
from trytond.tools import grouped_slice
from trytond.transaction import Transaction
from trytond.url import http_host
from trytond.wizard import Wizard, StateView, StateTransition, Button

from .exceptions import TemplateError

if not config.get(
        'html', 'plugins-marketing.email.message-content'):
    config.set(
        'html', 'plugins-marketing.email.message-content',
        'fullpage')

URL_BASE = config.get('marketing', 'email_base', default=http_host())
URL_OPEN = urljoin(URL_BASE, '/m/empty.gif')


def _formataddr(name, email):
    if name:
        name = str(Header(name, 'utf-8'))
    return formataddr((name, email))


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
    "Marketing E-mail"
    __name__ = 'marketing.email'
    _rec_name = 'email'

    email = fields.Char("E-mail", required=True)
    list_ = fields.Many2One('marketing.email.list', "List", required=True)
    email_token = fields.Char("E-mail Token", required=True)
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
                'marketing.msg_email_list_unique'),
            ]

    @classmethod
    def __register__(cls, module_name):
        super().__register__(module_name)

        table_h = cls.__table_handler__(module_name)
        table_h.index_action(['email', 'list_'], action='add')
        table_h.index_action(['list_', 'active'], action='add')

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
    def _format_email(cls, records):
        for record in records:
            email = record.email.lower()
            if email != record.email:
                record.email = email
        cls.save(records)

    @classmethod
    def create(cls, vlist):
        records = super().create(vlist)
        cls._format_email(records)
        return records

    @classmethod
    def write(cls, *args):
        super().write(*args)
        records = sum(args[0:None:2], [])
        cls._format_email(records)

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
        with Transaction().set_context(active_test=False):
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
    def get_context(cls, records, data):
        context = super().get_context(records, data)
        context['extract_params'] = _extract_params
        return context


class EmailUnsubscribe(Report):
    __name__ = 'marketing.email.unsubscribe'

    @classmethod
    def get_context(cls, records, data):
        context = super().get_context(records, data)
        context['extract_params'] = _extract_params
        return context


class EmailList(ModelSQL, ModelView):
    "Marketing Mailing List"
    __name__ = 'marketing.email.list'

    name = fields.Char("Name", required=True)
    active = fields.Boolean("Active", select=True)
    language = fields.Many2One('ir.lang', "Language", required=True)
    emails = fields.One2Many('marketing.email', 'list_', "Emails")

    @classmethod
    def default_active(cls):
        return True

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

    def request_subscribe(self, email, from_=None):
        pool = Pool()
        Email = pool.get('marketing.email')

        # Randomize processing time to prevent guessing whether the email
        # address is already subscribed to the list or not.
        Transaction().atexit(time.sleep, random.random())

        email = email.lower()
        with Transaction().set_context(active_test=False):
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
            from_ = (from_
                or config.get('marketing', 'email_from')
                or config.get('email', 'from'))
            msg, title = record.get_email_subscribe()
            msg['From'] = from_
            msg['To'] = record.email
            msg['Subject'] = Header(title, 'utf-8')
            sendmail_transactional(from_, [record.email], msg)

    def request_unsubscribe(self, email, from_=None):
        pool = Pool()
        Email = pool.get('marketing.email')

        # Randomize processing time to prevent guessing whether the email
        # address was subscribed to the list or not.
        Transaction().atexit(time.sleep, random.random())

        email = email.lower()
        with Transaction().set_context(active_test=False):
            records = Email.search([
                    ('email', '=', email),
                    ('list_', '=', self.id),
                    ])
        if records:
            record, = records
            if record.active:
                from_ = (from_
                    or config.get('marketing', 'email_from')
                    or config.get('email', 'from'))
                msg, title = record.get_email_unsubscribe()
                msg['From'] = from_
                msg['To'] = record.email
                msg['Subject'] = Header(title, 'utf-8')
                sendmail_transactional(from_, [record.email], msg)


class Message(Workflow, ModelSQL, ModelView):
    "Marketing E-mail Message"
    __name__ = 'marketing.email.message'
    _rec_name = 'title'

    _states = {
        'readonly': Eval('state') != 'draft',
        }
    _depends = ['state']
    from_ = fields.Char(
        "From", states=_states, depends=_depends,
        help="Leave empty for the value defined in the configuration file.")
    list_ = fields.Many2One(
        'marketing.email.list', "List",
        required=True, states=_states, depends=_depends)
    title = fields.Char(
        "Title", required=True, states=_states, depends=_depends)
    content = fields.Text(
        "Content",
        states={
            'required': Eval('state') != 'draft',
            'readonly': _states['readonly'],
            },
        depends=['state'] + _depends)
    urls = fields.One2Many(
        'web.shortened_url', 'record', "URLs", readonly=True)
    state = fields.Selection([
            ('draft', "Draft"),
            ('sending', "Sending"),
            ('sent', "Sent"),
            ], "State", readonly=True, select=True)
    del _states, _depends

    @classmethod
    def __setup__(cls):
        super().__setup__()
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
    def validate(cls, messages):
        super().validate(messages)
        for message in messages:
            message.check_content()

    def check_content(self):
        if not self.content:
            return
        try:
            MarkupTemplate(self.content)
        except Exception as exception:
            raise TemplateError(
                gettext('marketing_email'
                    '.msg_message_invalid_content',
                    message=self.rec_name,
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
                        if tag == 'a':
                            href = attrs.get('href')
                            attrs -= 'href'
                            href = short(href, str(message))
                            attrs |= [(QName('href'), href)]
                            data = tag, attrs
                    elif kind is END and data == 'body' and spy_pixel:
                        yield START, (QName('img'), Attrs([
                                    (QName('src'), short(
                                            URL_OPEN, str(message))),
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
            template = MarkupTemplate(message.content)
            for email in (emails or message.list_.emails):
                content = (template
                    .generate(email=email)
                    .filter(convert_href(message))
                    .render())

                name = email.party.rec_name if email.party else ''
                from_ = (message.from_
                    or config.get('marketing', 'email_from')
                    or config.get('email', 'from'))
                to = _formataddr(name, email.email)

                msg = MIMEMultipart('alternative')
                msg['From'] = from_
                msg['To'] = to
                msg['Subject'] = Header(message.title, 'utf-8')
                if html2text:
                    converter = html2text.HTML2Text()
                    part = MIMEText(
                        converter.handle(content), 'plain', _charset='utf-8')
                    msg.attach(part)
                part = MIMEText(content, 'html', _charset='utf-8')
                msg.attach(part)

                sendmail_transactional(
                    from_, getaddresses([to]), msg,
                    datamanager=smtpd_datamanager)
        if not emails:
            cls.sent(messages)


class SendTest(Wizard):
    "Send Test E-mail"
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
    "Send Test E-mail"
    __name__ = 'marketing.email.send_test'

    list_ = fields.Many2One(
        'marketing.email.list', "List", readonly=True)
    message = fields.Many2One(
        'marketing.email.message', "Message", readonly=True)
    email = fields.Many2One(
        'marketing.email', "E-Mail", required=True,
        domain=[
            ('list_', '=', Eval('list_')),
            ],
        depends=['list_'])
