# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import smtplib
from email.message import Message
from mock import Mock, patch, call

from trytond.sendmail import (
    sendmail_transactional, sendmail, SMTPDataManager, get_smtp_server)
from trytond.transaction import Transaction
from .test_tryton import with_transaction, activate_module


class SendmailTestCase(unittest.TestCase):
    'Test sendmail'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_sendmail_transactional(self):
        'Test sendmail_transactional'
        message = Mock()
        datamanager = Mock()
        sendmail_transactional(
            'tryton@example.com', 'foo@example.com', message,
            datamanager=datamanager)

        datamanager.put.assert_called_once_with(
            'tryton@example.com', 'foo@example.com', message)

    def test_sendmail(self):
        'Test sendmail'
        message = Mock()
        server = Mock()
        sendmail(
            'tryton@example.com', 'foo@example.com', message, server=server)
        server.sendmail.assert_called_with(
            'tryton@example.com', 'foo@example.com', message.as_string())
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
            SMTP.assert_called_once_with('localhost', 25)

        with patch.object(smtplib, 'SMTP') as SMTP:
            SMTP.return_value = server = Mock()
            self.assertEqual(
                get_smtp_server('smtp+tls://localhost:25'), server)
            SMTP.assert_called_once_with('localhost', 25)
            server.starttls.assert_called_once_with()

    @patch('trytond.sendmail.get_smtp_server')
    @with_transaction()
    def test_SMTPDataManager(self, get_smtp_server):
        'Test SMTPDataManager'
        transaction = Transaction()
        get_smtp_server.return_value = server = Mock()

        datamanager = transaction.join(SMTPDataManager())

        # multiple join must return the same
        self.assertEqual(transaction.join(SMTPDataManager()), datamanager)

        msg1 = Mock(Message)
        msg2 = Mock(Message)
        datamanager.put('foo@example.com', 'bar@example.com', msg1)
        datamanager.put('bar@example.com', 'foo@example.com', msg2)

        transaction.commit()

        server.sendmail.assert_has_calls([
                call('foo@example.com', 'bar@example.com', msg1.as_string()),
                call('bar@example.com', 'foo@example.com', msg2.as_string()),
                ])
        server.quit.assert_called_once_with()
        self.assertFalse(datamanager.queue)

        server.reset_mock()

        datamanager.put('foo@example.com', 'bar@example.com', Mock(Message))
        transaction.rollback()

        server.sendmail.assert_not_called()
        self.assertFalse(datamanager.queue)


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(SendmailTestCase)
