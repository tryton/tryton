# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import smtplib
import ssl
import time
from email.message import EmailMessage, Message
from email.utils import formatdate
from urllib.parse import parse_qs, unquote_plus

from trytond.config import config, parse_uri
from trytond.transaction import Transaction

__all__ = [
    'sendmail_transactional', 'sendmail',
    'send_message_transactional', 'send_message',
    'SMTPDataManager']
logger = logging.getLogger(__name__)
retry = config.getint('email', 'retry', default=5)


def sendmail_transactional(
        from_addr, to_addrs, msg, transaction=None, datamanager=None,
        strict=False):
    send_message_transactional(
        msg, from_addr, to_addrs, transaction, datamanager, strict)


def send_message_transactional(
        msg, from_addr=None, to_addrs=None, transaction=None, datamanager=None,
        strict=False):
    if transaction is None:
        transaction = Transaction()
    assert isinstance(transaction, Transaction), transaction
    if datamanager is None:
        datamanager = SMTPDataManager(strict=strict)
    datamanager = transaction.join(datamanager)
    datamanager.put(from_addr, to_addrs, msg)


def sendmail(from_addr, to_addrs, msg, server=None, strict=False):
    return send_message(msg, from_addr, to_addrs, server, strict)


def send_message(
        msg, from_addr=None, to_addrs=None, server=None, strict=False):
    if server is None:
        server = get_smtp_server(strict=strict)
        if not server:
            return
        quit = True
    else:
        assert server.uri
        quit = False
    if 'Date' not in msg:
        msg['Date'] = formatdate()
    for count in range(retry, -1, -1):
        if count != retry:
            time.sleep(0.02 * (retry - count))
        try:
            senderrs = server.send_message(msg, from_addr, to_addrs)
        except smtplib.SMTPServerDisconnected:
            if count:
                server = get_smtp_server(strict=strict)
                if server:
                    continue
            if strict:
                raise
            logger.error('fail to send email', exc_info=True)
        except smtplib.SMTPResponseException as e:
            if count and 400 <= e.smtp_code <= 499 and hasattr(server, 'uri'):
                server.quit()
                server = get_smtp_server(server.uri, strict=strict)
                if server:
                    continue
            if strict:
                raise
            logger.error('fail to send email', exc_info=True)
        except Exception:
            if strict:
                raise
            logger.error('fail to send email', exc_info=True)
        else:
            if senderrs:
                logger.warning('fail to send email to %s', senderrs)
        break
    if quit:
        server.quit()
    else:
        return server


def send_test_email(to_addrs, server=None):
    from_ = config.get('email', 'from')
    msg = EmailMessage()
    msg.set_content('Success!\nYour email settings work correctly.')
    msg['From'] = from_
    msg['To'] = to_addrs
    msg['Subject'] = 'Tryton test email'
    send_message(msg, server=server, strict=True)


def get_smtp_server(uri=None, strict=False):
    if uri is None:
        uri = config.get('email', 'uri')
    ini_uri = uri
    uri = parse_uri(uri)
    extra = {}
    if uri.query:
        cast = {'timeout': int}
        for key, value in parse_qs(uri.query, strict_parsing=True).items():
            extra[key] = cast.get(key, lambda a: a)(value[0])
    if uri.scheme.startswith('smtps'):
        connector = smtplib.SMTP_SSL
        extra['context'] = ssl.create_default_context()
    else:
        connector = smtplib.SMTP
    try:
        server = connector(uri.hostname, uri.port, **extra)
    except Exception:
        if strict:
            raise
        logger.error('fail to connect to %s', uri, exc_info=True)
        return

    if 'tls' in uri.scheme:
        server.starttls(context=ssl.create_default_context())

    if uri.username and uri.password:
        server.login(
            unquote_plus(uri.username),
            unquote_plus(uri.password))
    server.uri = ini_uri
    return server


class SMTPDataManager(object):

    def __init__(self, uri=None, strict=False):
        self.uri = uri
        self.strict = strict
        self.queue = []
        self._server = None

    def put(self, from_addr, to_addrs, msg):
        assert isinstance(msg, Message), msg
        self.queue.append((from_addr, to_addrs, msg))

    def __eq__(self, other):
        if not isinstance(other, SMTPDataManager):
            return NotImplemented
        return (self.uri == other.uri) and (self.strict == other.strict)

    def abort(self, trans):
        self._finish()

    def tpc_begin(self, trans):
        pass

    def commit(self, trans):
        pass

    def tpc_vote(self, trans):
        if self._server is None:
            self._server = get_smtp_server(self.uri, strict=self.strict)

    def tpc_finish(self, trans):
        if self._server is not None:
            for from_addr, to_addrs, msg in self.queue:
                new_server = send_message(
                    msg, from_addr, to_addrs, server=self._server)
                if new_server:
                    self._server = new_server
            self._server.quit()
            self._finish()

    def tpc_abort(self, trans):
        if self._server:
            self._server.close()
        self._finish()

    def _finish(self):
        self._server = None
        self.queue = []
