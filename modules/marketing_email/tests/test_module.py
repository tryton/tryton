# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from unittest.mock import ANY, Mock, patch

import trytond.config as config
from trytond.modules.marketing_email import marketing as marketing_module
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import inactive_records

SUBSCRIBE_URL = 'http://www.example.com/subscribe'
UNSUBSCRIBE_URL = 'http://www.example.com/unsubscribe'
FROM = 'marketing@example.com'


class MarketingEmailTestCase(ModuleTestCase):
    'Test Marketing Email module'
    module = 'marketing_email'

    def setUp(self):
        super().setUp()
        if not config.has_section('marketing'):
            config.add_section('marketing')
        subscribe_url = config.get(
            'marketing', 'email_subscribe_url', default='')
        config.set('marketing', 'email_subscribe_url', SUBSCRIBE_URL)
        self.addCleanup(
            config.set, 'marketing', 'email_subscribe_url', subscribe_url)
        unsubscribe_url = config.get(
            'marketing', 'email_unsubscribe_url', default='')
        config.set('marketing', 'email_unsubscribe_url', UNSUBSCRIBE_URL)
        self.addCleanup(
            config.set, 'marketing', 'email_unsubscribe_url', unsubscribe_url)
        spy_pixel = config.get('marketing', 'email_spy_pixel', default='')
        config.set('marketing', 'email_spy_pixel', 'true')
        self.addCleanup(
            config.set, 'marketing', 'email_spy_pixel', spy_pixel)
        from_ = config.get('email', 'from', default='')
        config.set('email', 'from', FROM)
        self.addCleanup(config.set, 'email', 'from', from_)

    @with_transaction()
    def test_subscribe(self):
        "Test subscribe"
        pool = Pool()
        Email = pool.get('marketing.email')
        EmailList = pool.get('marketing.email.list')

        email_list = EmailList(name="Test")
        email_list.save()

        with patch.object(
                marketing_module,
                'send_message_transactional') as send_message:
            email_list.request_subscribe('user@example.com')
            send_message.assert_called_once()

        with inactive_records():
            email, = Email.search([
                    ('list_', '=', email_list.id),
                    ])
        token = email.email_token
        self.assertTrue(token)
        self.assertFalse(email.active)
        self.assertEqual(email_list.subscribed, 0)

        self.assertEqual(
            email.get_email_subscribe_url(),
            '%s?token=%s' % (SUBSCRIBE_URL, token))

        Email.subscribe_url(SUBSCRIBE_URL)
        self.assertFalse(email.active)

        Email.subscribe_url('%s?token=12345' % SUBSCRIBE_URL)
        self.assertFalse(email.active)

        Email.subscribe_url(email.get_email_subscribe_url())
        self.assertTrue(email.active)
        self.assertEqual(email_list.subscribed, 1)

    @with_transaction()
    def test_unsubscribe(self):
        "Test unsubscribe"
        pool = Pool()
        Email = pool.get('marketing.email')
        EmailList = pool.get('marketing.email.list')

        email_list = EmailList(name="Test")
        email_list.save()

        email = Email(email='user@example.com', list_=email_list.id)
        email.save()

        token = email.email_token
        self.assertTrue(token)
        self.assertTrue(email.active)

        with patch.object(
                marketing_module,
                'send_message_transactional') as send_message:
            email_list.request_unsubscribe('user@example.com')
            send_message.assert_called_once()

        self.assertEqual(
            email.get_email_unsubscribe_url(),
            '%s?token=%s' % (UNSUBSCRIBE_URL, token))

        Email.unsubscribe_url(UNSUBSCRIBE_URL)
        self.assertTrue(email.active)

        Email.unsubscribe_url('%s?token=12345' % UNSUBSCRIBE_URL)
        self.assertTrue(email.active)

        Email.unsubscribe_url(email.get_email_unsubscribe_url())
        self.assertFalse(email.active)

    @with_transaction()
    def test_send_messages(self):
        "Test messages are sent to the list"
        pool = Pool()
        Email = pool.get('marketing.email')
        EmailList = pool.get('marketing.email.list')
        Message = pool.get('marketing.email.message')
        ShortenedURL = pool.get('web.shortened_url')

        email_list = EmailList(name="Test")
        email_list.save()

        email = Email(email='user@example.com', list_=email_list)
        email.save()
        message = Message(list_=email_list)
        message.title = 'Test'
        message.content = (
            '<html>'
            '<body>'
            '<a href="http://www.example.com/">Content</a>'
            '</body>'
            '</html>')
        message.save()
        Message.send([message])

        with patch.object(
                marketing_module,
                'send_message_transactional') as send_message:
            smtpd_datamanager = Mock()
            Message.process(smtpd_datamanager=smtpd_datamanager)

            send_message.assert_called_once_with(
                ANY, datamanager=smtpd_datamanager)
        urls = ShortenedURL.search([
                ('record', '=', str(message)),
                ])

        self.assertEqual(message.state, 'sent')
        self.assertEqual(len(urls), 2)


del ModuleTestCase
