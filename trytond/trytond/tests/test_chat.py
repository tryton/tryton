# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from email.message import EmailMessage
from email.utils import getaddresses
from unittest.mock import patch

from trytond.pool import Pool
from trytond.transaction import Transaction

from .test_tryton import TestCase, activate_module, with_transaction


class NotificationTestCase(TestCase):
    "Test Notification"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        activate_module('tests')

    def run_tasks(self):
        pool = Pool()
        Queue = pool.get('ir.queue')
        transaction = Transaction()
        while transaction.tasks:
            task = Queue(transaction.tasks.pop())
            task.run()

    @with_transaction()
    def test_chat_post(self):
        "Test posting on chat"
        pool = Pool()
        User = pool.get('res.user')
        Room = pool.get('test.chat.room')
        Notification = pool.get('res.notification')
        Channel = pool.get('ir.chat.channel')
        Message = pool.get('ir.chat.message')

        alice, = User.create([{
                    'name': "Alice",
                    'login': 'alice',
                    }])
        room = Room()
        room.save()
        Channel.subscribe(room, alice.login)
        channel = Channel._get_channel(room)

        room.chat_post('tests.msg_chat', foo="Bar", audience='public')
        self.run_tasks()

        message, = Message.search([
                ('channel', '=', channel),
                ('audience', '=', 'public'),
                ])
        self.assertEqual(message.audience, 'public')
        self.assertEqual(message.content, "Chat Message: Bar")
        with Transaction().set_user(alice.id):
            self.assertEqual(Notification.get_count(), 1)
            notification, = Notification.get()
            self.assertEqual(notification, {
                    'id': notification['id'],
                    'label': None,
                    'description': "Chat Message: Bar",
                    'icon': 'tryton-chat',
                    'model': Room.__name__,
                    'records': [room.id],
                    'action': None,
                    'unread': True,
                    })

    @with_transaction()
    def test_chat_post_email(self):
        "Test posting on chat send email"
        pool = Pool()
        Room = pool.get('test.chat.room')
        Channel = pool.get('ir.chat.channel')

        room = Room()
        room.save()
        Channel.subscribe_email(room, "foo@example.org")
        Channel.subscribe_email(room, "bar@example.com")

        with patch('trytond.ir.chat.send_message_transactional') as p:
            room.chat_post('tests.msg_chat', foo="Bar", audience='public')
            self.run_tasks()

            (msg,), _ = p.call_args

        self.assertEqual(
            list(a for n, a in getaddresses([msg['Bcc']])),
            ['foo@example.org', 'bar@example.com'])
        self.assertEqual(msg.get_content().strip(), "Chat Message: Bar")

    @with_transaction()
    def test_chat_post_from_email(self):
        "Test posting on chat from an email"
        pool = Pool()
        User = pool.get('res.user')
        Room = pool.get('test.chat.room')
        Channel = pool.get('ir.chat.channel')
        Message = pool.get('ir.chat.message')

        alice, = User.create([{
                    'name': "Alice",
                    'login': 'alice',
                    }])

        room = Room()
        room.save()
        Channel.subscribe(room, alice.login)
        channel = Channel._get_channel(room)

        msg = EmailMessage()
        msg['From'] = 'foo@example.org'
        msg['Subject'] = 'New message!'
        msg.set_content("Test Content")

        with patch.object(Channel, '_email_channel') as find_channel:
            find_channel.return_value = channel
            Channel.post_from_email(msg)

        message, = Message.search([
                ('channel', '=', channel),
                ('audience', '=', 'public'),
                ])
        self.assertEqual(message.content, "Test Content\n")
