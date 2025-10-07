# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import base64
import email
import json
import re
import urllib
import uuid
from email.policy import default as email_policy_default
from email.utils import getaddresses
from functools import partial

import trytond.config as config
from trytond.model import (
    ModelSQL, ModelStorage, ModelView, fields, sequence_ordered)
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.url import http_host

if config.getboolean('inbound_email', 'filestore', default=True):
    file_id = 'data_id'
    store_prefix = config.get('inbound_email', 'store_prefix', default=None)
else:
    file_id = store_prefix = None


class Inbox(ModelSQL, ModelView):
    __name__ = 'inbound.email.inbox'

    name = fields.Char("Name", required=True)
    identifier = fields.Char("Identifier", readonly=True)
    endpoint = fields.Function(
        fields.Char(
            "Endpoint",
            help="The URL where the emails must be posted."),
        'on_change_with_endpoint')
    rules = fields.One2Many(
        'inbound.email.rule', 'inbox', "Rules",
        help="The action of the first matching line is run.")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update(
            new_identifier={
                'icon': 'tryton-refresh',
                },
            )

    @fields.depends('identifier')
    def on_change_with_endpoint(self, name=None):
        if self.identifier:
            url_part = {
                'identifier': self.identifier,
                'database_name': Transaction().database.name,
                }
            return http_host() + (
                urllib.parse.quote(
                    '/%(database_name)s/inbound_email/inbox/%(identifier)s'
                    % url_part))

    @classmethod
    @ModelView.button
    def new_identifier(cls, inboxes):
        for inbox in inboxes:
            if inbox.identifier:
                inbox.identifier = None
            else:
                inbox.identifier = uuid.uuid4().hex
        cls.save(inboxes)

    def process(self, email_):
        assert email_.inbox == self
        for rule in self.rules:
            if rule.match(email_.as_dict()):
                email_.rule = rule
                rule.run(email_)
                return


def _email_text(message, type_='plain'):
    if message.get_content_maintype() != 'multipart':
        return message.get_payload()
    for part in message.walk():
        if part.get_content_type() == f'text/{type_}':
            return part.get_payload()


def _email_attachments(message):
    if message.get_content_maintype() != 'multipart':
        return
    for i, part in enumerate(message.walk()):
        if part.get_content_maintype() == 'multipart':
            continue
        if 'attachment' not in part.get('Content-Disposition', '').lower():
            continue
        filename = part.get_filename()
        yield {
            'filename': filename,
            'type': part.get_content_type(),
            'data': part.get_payload(decode=True),
            }


class Email(ModelSQL, ModelView):
    __name__ = 'inbound.email'

    inbox = fields.Many2One(
        'inbound.email.inbox', "Inbox",
        required=True, readonly=True, ondelete='CASCADE')
    data = fields.Binary(
        "Data", file_id=file_id, store_prefix=store_prefix,
        required=True, readonly=True)
    data_id = fields.Char("Data ID", readonly=True)
    data_type = fields.Selection([
            ('mailchimp', "Mailchimp"),
            ('mailpace', "MailPace"),
            ('postmark', "Postmark"),
            ('raw', "Raw"),
            ('sendgrid', "SendGrid"),
            ], "Data Type", required=True, readonly=True, translate=False)
    rule = fields.Many2One('inbound.email.rule', "Rule", readonly=True)
    result = fields.Reference("Result", selection='get_models', readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [('id', 'DESC')]
        cls._buttons.update(
            process={
                'readonly': Eval('rule'),
                'depends': ['rule'],
                },
            )

    @classmethod
    def get_models(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        return [(None, "")] + Model.get_name_items((ModelStorage, ModelView))

    @classmethod
    def from_webhook(cls, inbox, data, data_type):
        emails = []
        if data_type in {'raw', 'mailpace', 'sendgrid', 'postmark'}:
            emails.append(cls(inbox=inbox, data=data, data_type=data_type))
        elif data_type == 'mailchimp':
            payload = json.loads(data)
            for event in payload['mandrill_events']:
                if event['event'] == 'inbound':
                    emails.append(cls(
                            inbox=inbox,
                            data=json.dumps(event).encode('utf-8'),
                            data_type=data_type))
        return emails

    @classmethod
    @ModelView.button
    def process(cls, emails):
        for email_ in emails:
            if not email_.rule:
                email_.inbox.process(email_)
        cls.save(emails)

    def as_dict(self):
        value = {}
        if self.data_type == 'raw':
            value.update(self._as_dict(self.data))
        elif self.data_type == 'mailchimp':
            event = json.loads(self.data)
            value.update(self._as_dict(event['raw_msg']))
        elif self.data_type == 'mailpace':
            payload = json.loads(self.data)
            value.update(self._as_dict(payload['raw']))
        elif self.data_type == 'postmark':
            payload = json.loads(self.data)
            value.update(self._as_dict_postmark(payload))
        elif self.data_type == 'sendgrid':
            payload = json.loads(self.data)
            value.update(self._as_dict(payload['email']))
        return value

    def _as_dict(self, raw):
        value = {}
        if isinstance(raw, str):
            message = email.message_from_string(
                raw, policy=email_policy_default)
        else:
            message = email.message_from_bytes(
                raw, policy=email_policy_default)
        if 'From' in message:
            value['from'] = getaddresses([message.get('From')])[0][1]
        for key in ['To', 'Cc', 'Bcc']:
            if key in message:
                value[key.lower()] = [
                    a for _, a in getaddresses(message.get_all(key))]
        if 'Subject' in message:
            value['subject'] = message['Subject']
        text = _email_text(message)
        if text is not None:
            value['text'] = text
        html = _email_text(message, 'html')
        if html is not None:
            value['html'] = html
        value['attachments'] = list(_email_attachments(message))
        value['headers'] = dict(message.items())
        return value

    def _as_dict_postmark(self, payload):
        value = {}
        if 'FromFull' in payload:
            value['from'] = payload['FromFull']['Email']
        for key in ['To', 'Cc', 'Bcc']:
            if f'{key}Full' in payload:
                value[key.lower()] = [
                    a['Email'] for a in payload[f'{key}Full']]
        if 'Subject' in payload:
            value['subject'] = payload['Subject']
        if 'TextBody' in payload:
            value['text'] = payload['TextBody']
        if 'HtmlBody' in payload:
            value['html'] = payload['HtmlBody']
        if 'Attachments' in payload:
            value['attachments'] = [{
                    'filename': a['Name'],
                    'type': a['ContentType'],
                    'data': base64.b64decode(a['Content']),
                    } for a in payload['Attachments']]
        if 'Headers' in payload:
            value['headers'] = {
                h['Name']: h['Value'] for h in payload['Headers']}
        return value


class Rule(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'inbound.email.rule'

    inbox = fields.Many2One(
        'inbound.email.inbox', "Inbox", required=True, ondelete='CASCADE')
    origin = fields.Char(
        "Origin",
        help="A regular expression to match the sender email address.")
    destination = fields.Char(
        "Destination",
        help="A regular expression to match any receiver email addresses.")
    subject = fields.Char(
        "Subject",
        help="A regular expression to match the subject.")
    attachment_name = fields.Char(
        "Attachment Name",
        help="A regular expression to match any attachment name.")
    headers = fields.One2Many('inbound.email.rule.header', 'rule', "Headers")

    action = fields.Selection([
            (None, ""),
            ], "Action")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('inbox')
        cls._order.insert(0, ('inbox.id', 'DESC'))

    def match(self, email_):
        flags = re.IGNORECASE
        search = partial(re.search, flags=flags)
        compile_ = partial(re.compile, flags=flags)
        if self.origin:
            if not search(self.origin, email_.get('from', '')):
                return False
        if self.destination:
            destinations = [
                *email_.get('to', []),
                *email_.get('cc', []),
                *email_.get('bcc', []),
                ]
            pattern = compile_(self.destination)
            if not any(pattern.search(d) for d in destinations):
                return False
        if self.subject:
            if not search(self.subject, email_.get('subject', '')):
                return False
        if self.attachment_name:
            pattern = compile_(self.attachment_name)
            if not any(
                    pattern.search(a.get('filename', ''))
                    for a in email_.get('attachments', [])):
                return False
        if self.headers:
            for header in self.headers:
                if not search(
                        header.value,
                        email_.get('headers', {}).get(header.name, '')):
                    return False
        return True

    def run(self, email_):
        pool = Pool()
        if self.action:
            model, method = self.action.split('|')
            Model = pool.get(model)
            email_.result = getattr(Model, method)(email_, self)


class RuleHeader(ModelSQL, ModelView):
    __name__ = 'inbound.email.rule.header'

    rule = fields.Many2One(
        'inbound.email.rule', "Rule", required=True, ondelete='CASCADE')
    name = fields.Char(
        "Name", required=True,
        help="The name of the header.")
    value = fields.Char(
        "Value",
        help="A regular expression to match the header value.")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('rule')
