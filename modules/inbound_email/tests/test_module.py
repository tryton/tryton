# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import json
import uuid
from email.message import EmailMessage
from unittest.mock import patch

from trytond.pool import Pool
from trytond.protocols.wrappers import HTTPStatus
from trytond.tests.test_tryton import (
    ModuleTestCase, RouteTestCase, with_transaction)
from trytond.transaction import Transaction


class InboundEmailTestCase(ModuleTestCase):
    "Test Inbound Email module"
    module = 'inbound_email'

    def get_message(self):
        message = EmailMessage()
        message['From'] = "John Doe <john.doe@example.com>"
        message['To'] = (
            "Michael Scott <michael@example.com>, pam@example.com")
        message['Cc'] = 'jim@example.com'
        message['Subject'] = "The office"

        message.set_content("Hello")
        message.add_attachment(
            b'bin', maintype='application', subtype='octet-stream',
            filename='data.bin')
        return message

    def get_message_dict(self, headers):
        return {
            'from': 'john.doe@example.com',
            'to': ['michael@example.com', 'pam@example.com'],
            'cc': ['jim@example.com'],
            'subject': 'The office',
            'text': 'Hello\n',
            'attachments': [{
                    'filename': 'data.bin',
                    'type': 'application/octet-stream',
                    'data': b'bin',
                    }],
            'headers': dict(headers.items()),
            }

    @with_transaction()
    def test_inbox_identifier(self):
        "Test inbox identifier"
        pool = Pool()
        Inbox = pool.get('inbound.email.inbox')

        inbox = Inbox(name="Test")
        inbox.save()

        self.assertFalse(inbox.identifier)
        self.assertFalse(inbox.endpoint)

        Inbox.new_identifier([inbox])

        self.assertTrue(inbox.identifier)
        self.assertTrue(inbox.endpoint)

        Inbox.new_identifier([inbox])

        self.assertFalse(inbox.identifier)
        self.assertFalse(inbox.endpoint)

    @with_transaction()
    def test_email_from_webhook(self):
        "Test email from webhook"
        pool = Pool()
        Email = pool.get('inbound.email')
        Inbox = pool.get('inbound.email.inbox')

        message = self.get_message()
        inbox = Inbox()
        data = message.as_bytes()

        for data_type in ['raw', 'mailpace', 'postmark', 'sendgrid']:
            with self.subTest(data_type=data_type):
                emails = Email.from_webhook(inbox, data, data_type=data_type)
                email, = emails
                self.assertEqual(email.inbox, inbox)
                self.assertEqual(email.data, data)
                self.assertEqual(email.data_type, data_type)

        with self.subTest(data_type='mailchimp'):
            data = json.dumps({
                    'mandrill_events': [{
                            'event': 'inbound',
                            }, {
                            'event': 'inbound',
                            }],
                    })
            emails = Email.from_webhook(inbox, data, data_type='mailchimp')
            self.assertEqual(len(emails), 2)
            email = emails[0]
            self.assertEqual(email.inbox, inbox)
            self.assertEqual(json.loads(email.data), {'event': 'inbound'})
            self.assertEqual(email.data_type, 'mailchimp')

    @with_transaction()
    def test_email_as_dict_raw(self):
        "Test raw email as dict"
        pool = Pool()
        Email = pool.get('inbound.email')

        message = self.get_message()
        email = Email(data=message.as_bytes(), data_type='raw')

        self.assertDictEqual(email.as_dict(), self.get_message_dict(message))

    @with_transaction()
    def test_email_as_dict_mailchimp(self):
        "Test mailchimp email as dict"
        pool = Pool()
        Email = pool.get('inbound.email')

        message = self.get_message()
        data = json.dumps({
                'event': 'inbound',
                'raw_msg': message.as_string(),
                }).encode('utf-8')
        email = Email(data=data, data_type='mailchimp')

        self.assertDictEqual(email.as_dict(), self.get_message_dict(message))

    @with_transaction()
    def test_email_as_dict_mailpace(self):
        "Test mailpace email as dict"
        pool = Pool()
        Email = pool.get('inbound.email')

        message = self.get_message()
        data = json.dumps({
                'raw': message.as_string(),
                }).encode('utf-8')
        email = Email(data=data, data_type='mailpace')

        self.assertDictEqual(email.as_dict(), self.get_message_dict(message))

    @with_transaction()
    def test_email_as_dict_postmark(self):
        "Test postmark email as dict"
        pool = Pool()
        Email = pool.get('inbound.email')

        data = json.dumps({
                'FromFull': {
                    'Name': 'John Doe',
                    'Email': 'john.doe@example.com',
                    },
                'ToFull': [{
                        'Name': 'Michael',
                        'Email': 'michael@example.com',
                        }, {
                        'Email': 'pam@example.com',
                        },
                    ],
                'CcFull': [{
                        'Email': 'jim@example.com',
                        }],
                'Subject': 'The office',
                'TextBody': 'Hello\n',
                'Attachments': [{
                        'Name': 'data.bin',
                        'Content': 'Ymlu',
                        'ContentType': 'application/octet-stream',
                        }],
                'Headers': [{
                        'Name': 'Message-ID',
                        'Value': '12345@example.com',
                        }],
                }).encode('utf-8')
        email = Email(data=data, data_type='postmark')

        self.assertDictEqual(
            email.as_dict(),
            self.get_message_dict({'Message-ID': '12345@example.com'}))

    @with_transaction()
    def test_email_as_dict_sendgrid(self):
        "Test sendgrid email as dict"
        pool = Pool()
        Email = pool.get('inbound.email')

        message = self.get_message()
        data = json.dumps({
                'email': message.as_string(),
                }).encode('utf-8')
        email = Email(data=data, data_type='sendgrid')

        self.assertDictEqual(email.as_dict(), self.get_message_dict(message))

    @with_transaction()
    def test_email_process(self):
        "Test email process"
        pool = Pool()
        Inbox = pool.get('inbound.email.inbox')
        Rule = pool.get('inbound.email.rule')
        Email = pool.get('inbound.email')

        inbox = Inbox(name="Test")
        inbox.rules = [Rule()]
        inbox.save()

        message = self.get_message()
        email = Email(inbox=inbox, data=message.as_bytes(), data_type='raw')
        email.save()

        with patch.object(Rule, 'run') as run:
            Email.process([email])

            run.assert_called_once_with(email)

    def _get_rule(self, **values):
        pool = Pool()
        Rule = pool.get('inbound.email.rule')
        for name in Rule._fields:
            values.setdefault(name, None)
        return Rule(**values)

    @with_transaction()
    def test_rule_match_origin(self):
        "Test rule match origin"
        rule = self._get_rule(origin="foo.*@example.com")

        self.assertTrue(rule.match({'from': "foo@example.com"}))
        self.assertFalse(rule.match({'from': "bar@example.com"}))
        self.assertFalse(rule.match({}))

    @with_transaction()
    def test_rule_match_destination(self):
        "Test rule match destination"
        rule = self._get_rule(destination="foo.*@example.com")

        self.assertTrue(rule.match({'to': ["foo@example.com"]}))
        self.assertTrue(rule.match({'to': [
                        "bar@example.com", "foo@example.com"]}))
        self.assertTrue(rule.match({'cc': ["foo@example.com"]}))
        self.assertTrue(rule.match({'bcc': ["foo@example.com"]}))
        self.assertFalse(rule.match({'to': ["bar@example.com"]}))
        self.assertFalse(rule.match({}))

    @with_transaction()
    def test_rule_match_subject(self):
        "Test rule match subject"
        rule = self._get_rule(subject="Test")

        self.assertTrue(rule.match({'subject': "Email test subject"}))
        self.assertFalse(rule.match({'subject': "Email subject"}))
        self.assertFalse(rule.match({}))

    @with_transaction()
    def test_rule_match_attachment_name(self):
        "Test rule match attachment name"
        rule = self._get_rule(attachment_name="foo")

        self.assertTrue(rule.match({'attachments': [
                        {'filename': "foo.pdf"}]}))
        self.assertTrue(rule.match({'attachments': [
                        {'filename': "bar.pdf"}, {'filename': "foo.pdf"}]}))
        self.assertFalse(rule.match({'attachments': [
                        {'filename': "bar.pdf"}]}))
        self.assertFalse(rule.match({}))

    @with_transaction()
    def test_rule_match_headers(self):
        "Test rule match headers"
        rule = self._get_rule(
            headers=[{'name': 'Message-ID', 'value': 'tryton-'}])

        self.assertTrue(rule.match({'headers': {'Message-ID': 'tryton-42'}}))
        self.assertTrue(rule.match({'headers': {
                        'From': 'foo@example.com',
                        'Message-ID': 'tryton-42',
                        }}))
        self.assertFalse(rule.match({'headers': {'Message-ID': 'bar-42'}}))
        self.assertFalse(rule.match({'headers': {
                        'From': 'tryton-test@example.com',
                        'Message-ID': 'bar-42',
                        }}))
        self.assertFalse(rule.match({}))

    @with_transaction()
    def test_rule_run(self):
        "Test run rule"
        pool = Pool()
        Rule = pool.get('inbound.email.rule')
        Email = pool.get('inbound.email')

        rule = Rule(action='inbound.email|test')
        email = Email()

        with patch.object(Email, 'test', create=True) as func:
            func.return_value = result = Rule()

            rule.run(email)

            func.assert_called_once_with(email, rule)
            self.assertEqual(email.result, result)


class InboundEmailRouteTestCase(RouteTestCase):
    "Test Inbound Email route"
    module = 'inbound_email'

    identifier = uuid.uuid4().hex

    @classmethod
    def setUpDatabase(cls):
        pool = Pool()
        Inbox = pool.get('inbound.email.inbox')
        Inbox(name="Test", identifier=cls.identifier).save()

    def test_inbound_email_route_data(self):
        "Test inbound email route with data"

        client = self.client()

        response = client.post(
            f'/{self.db_name}/inbound_email/inbox/{self.identifier}',
            data=b'data')

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

        @with_transaction()
        def check():
            pool = Pool()
            Email = pool.get('inbound.email')
            email, = Email.search([])

            try:
                self.assertEqual(email.data, b'data')
                self.assertEqual(email.data_type, 'raw')
                self.assertTrue(email.inbox)
            finally:
                Email.delete([email])
            Transaction().commit()
        check()

    def test_inbound_email_route_form(self):
        "Test inbound email route with form"
        client = self.client()

        response = client.post(
            f'/{self.db_name}/inbound_email/inbox/{self.identifier}',
            data={
                'email': 'data',
                })

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

        @with_transaction()
        def check():
            pool = Pool()
            Email = pool.get('inbound.email')
            email, = Email.search([])

            try:
                self.assertEqual(email.data, b'{"email": "data"}')
                self.assertEqual(email.data_type, 'raw')
                self.assertTrue(email.inbox)
            finally:
                Email.delete([email])
            Transaction().commit()
        check()

    def test_inbound_email_route_not_found(self):
        "Test inbound email route not found"
        client = self.client()

        response = client.post(
            f'/{self.db_name}/inbound_email/inbox/unknown',
            data=b'foo')

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)


del ModuleTestCase, RouteTestCase
