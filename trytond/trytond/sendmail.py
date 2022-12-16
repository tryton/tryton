# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import smtplib
from email.message import Message
from email.utils import formatdate
from email.mime.text import MIMEText
from urllib.parse import parse_qs, unquote_plus

from .config import config, parse_uri
from .transaction import Transaction

__all__ = ['sendmail_transactional', 'sendmail', 'SMTPDataManager']
logger = logging.getLogger(__name__)


def sendmail_transactional(
        from_addr, to_addrs, msg, transaction=None, datamanager=None):
    if transaction is None:
        transaction = Transaction()
    assert isinstance(transaction, Transaction), transaction
    if datamanager is None:
        datamanager = SMTPDataManager()
    datamanager = transaction.join(datamanager)
    datamanager.put(from_addr, to_addrs, msg)


def sendmail(from_addr, to_addrs, msg, server=None):
    if server is None:
        server = get_smtp_server()
        if not server:
            return
        quit = True
    else:
        quit = False
    if 'Date' not in msg:
        msg['Date'] = formatdate()
    try:
        senderrs = server.sendmail(from_addr, to_addrs, msg.as_string())
    except Exception:
        logger.error('fail to send email', exc_info=True)
    else:
        if senderrs:
            logger.warning('fail to send email to %s', senderrs)
    if quit:
        server.quit()


def send_test_email(to_addrs, server=None):
    from_ = config.get('email', 'from')
    msg = MIMEText('Success!\nYour email settings work correctly.')
    msg['From'] = from_
    msg['To'] = to_addrs
    msg['Subject'] = 'Tryton test email'
    sendmail(config.get('email', 'from'), to_addrs, msg, server=server)


def get_smtp_server(uri=None):
    if uri is None:
        uri = config.get('email', 'uri')
    uri = parse_uri(uri)
    extra = {}
    if uri.query:
        cast = {'timeout': int}
        for key, value in parse_qs(uri.query, strict_parsing=True).items():
            extra[key] = cast.get(key, lambda a: a)(value[0])
    if uri.scheme.startswith('smtps'):
        connector = smtplib.SMTP_SSL
    else:
        connector = smtplib.SMTP
    try:
        server = connector(uri.hostname, uri.port, **extra)
    except Exception:
        logger.error('fail to connect to %s', uri, exc_info=True)
        return

    if 'tls' in uri.scheme:
        server.starttls()

    if uri.username and uri.password:
        server.login(
            unquote_plus(uri.username),
            unquote_plus(uri.password))
    return server


class SMTPDataManager(object):

    def __init__(self, uri=None):
        self.uri = uri
        self.queue = []
        self._server = None

    def put(self, from_addr, to_addrs, msg):
        assert isinstance(msg, Message), msg
        self.queue.append((from_addr, to_addrs, msg))

    def __eq__(self, other):
        if not isinstance(other, SMTPDataManager):
            return NotImplemented
        return self.uri == other.uri

    def abort(self, trans):
        self._finish()

    def tpc_begin(self, trans):
        pass

    def commit(self, trans):
        pass

    def tpc_vote(self, trans):
        if self._server is None:
            self._server = get_smtp_server(self.uri)

    def tpc_finish(self, trans):
        if self._server is not None:
            for from_addr, to_addrs, msg in self.queue:
                sendmail(from_addr, to_addrs, msg, server=self._server)
            self._server.quit()
            self._finish()

    def tpc_abort(self, trans):
        if self._server:
            self._server.close()
        self._finish()

    def _finish(self):
        self._server = None
        self.queue = []
