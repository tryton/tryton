# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import smtplib
import unittest
from email.message import Message
from unittest.mock import ANY, MagicMock, Mock, call, patch

from trytond.sendmail import (
    SMTPDataManager, get_smtp_server, sendmail, sendmail_transactional)
from trytond.transaction import Transaction

from .test_tryton import activate_module, with_transaction


class SendmailTestCase(unittest.TestCase):
    'Test sendmail'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_sendmail_transactional(self):
        'Test sendmail_transactional'
        message = MagicMock()
        datamanager = Mock()
        sendmail_transactional(
            'tryton@example.com', 'foo@example.com', message,
            datamanager=datamanager)

        datamanager.put.assert_called_once_with(
            'tryton@example.com', 'foo@example.com', message)

    def test_sendmail(self):
        'Test sendmail'
        message = MagicMock()
        server = Mock()
        sendmail(
            'tryton@example.com', 'foo@example.com', message, server=server)
        server.send_message.assert_called_with(
            message, 'tryton@example.com', 'foo@example.com')
        server.quit.assert_not_called()

    def test_get_smtp_server(self):
        'Test get_smtp_server'
        with patch.object(smtplib, 'SMTP') as SMTP:
            SMTP.return_value = server = Mock()
            self.assertEqual(get_smtp_server('smtp://localhost:25'), server)
            SMTP.assert_called_once_with('localhost', 25)

        with patch.object(smtplib, 'SMTP') as SMTP:
            SMTP.return_value = server = Mock()
            self.assertEqual(
                get_smtp_server('smtp://foo:bar@localhost:25'), server)
            SMTP.assert_called_once_with('localhost', 25)
            server.login.assert_called_once_with('foo', 'bar')

        with patch.object(smtplib, 'SMTP_SSL') as SMTP:
            SMTP.return_value = server = Mock()
            self.assertEqual(
                get_smtp_server('smtps://localhost:25'), server)
            SMTP.assert_called_once_with('localhost', 25, context=ANY)

        with patch.object(smtplib, 'SMTP') as SMTP:
            SMTP.return_value = server = Mock()
            self.assertEqual(
                get_smtp_server('smtp+tls://localhost:25'), server)
            SMTP.assert_called_once_with('localhost', 25)
            server.starttls.assert_called_once_with(context=ANY)

    def test_get_smtp_server_extra_parameters(self):
        'Test get_smtp_server uri extra parameters'
        with patch.object(smtplib, 'SMTP') as SMTP:
            SMTP.return_value = server = Mock()
            params = 'timeout=30&local_hostname=smtp.example.com'
            self.assertEqual(
                get_smtp_server('smtp://localhost:25?%s' % params), server)
            SMTP.assert_called_once_with(
                'localhost', 25, timeout=30, local_hostname='smtp.example.com')

    @patch('trytond.sendmail.get_smtp_server')
    @with_transaction()
    def test_SMTPDataManager(self, get_smtp_server):
        'Test SMTPDataManager'
        transaction = Transaction()
        get_smtp_server.return_value = server = Mock()

        datamanager = transaction.join(SMTPDataManager())

        # multiple join must return the same
        self.assertEqual(transaction.join(SMTPDataManager()), datamanager)

        msg1 = MagicMock(Message)
        msg2 = MagicMock(Message)
        datamanager.put('foo@example.com', 'bar@example.com', msg1)
        datamanager.put('bar@example.com', 'foo@example.com', msg2)

        transaction.commit()

        server.send_message.assert_has_calls([
                call(msg1, 'foo@example.com', 'bar@example.com'),
                call(msg2, 'bar@example.com', 'foo@example.com'),
                ])
        server.quit.assert_called_once_with()
        self.assertFalse(datamanager.queue)

        server.reset_mock()

        datamanager.put(
            'foo@example.com', 'bar@example.com', MagicMock(Message))
        transaction.rollback()

        server.send_message.assert_not_called()
        self.assertFalse(datamanager.queue)
