# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import collections
import json
import logging
import os
import selectors
import threading
import time
import uuid
from urllib.parse import urljoin

from trytond import backend
from trytond.config import config
from trytond.protocols.jsonrpc import JSONDecoder, JSONEncoder
from trytond.protocols.wrappers import (
    HTTPStatus, Response, exceptions, redirect)
from trytond.tools import resolve
from trytond.transaction import Transaction
from trytond.wsgi import app

logger = logging.getLogger(__name__)

_db_timeout = config.getint('database', 'timeout')
_cache_timeout = config.getint('bus', 'cache_timeout')
_select_timeout = config.getint('bus', 'select_timeout')
_long_polling_timeout = config.getint('bus', 'long_polling_timeout')
_allow_subscribe = config.getboolean('bus', 'allow_subscribe')
_url_host = config.get('bus', 'url_host')
_web_cache_timeout = config.getint('web', 'cache_timeout')


class _MessageQueue:

    Message = collections.namedtuple('Message', 'channel content timestamp')

    def __init__(self, timeout):
        super().__init__()
        self._lock = collections.defaultdict(threading.Lock)
        self._timeout = timeout
        self._messages = []

    def append(self, channel, element):
        self._messages.append(
            self.Message(channel, element, time.time()))

    def get_next(self, channels, from_id=None):
        oldest = time.time() - self._timeout
        to_delete_index = 0
        found = False
        first_message = None
        message = self.Message(None, None, None)
        for idx, item in enumerate(self._messages):
            if item.timestamp < oldest:
                to_delete_index = idx
                continue
            if item.channel not in channels:
                continue
            if not first_message:
                first_message = item
            if from_id is None or found:
                message = item
                break
            found = item.content['message_id'] == from_id
        else:
            if first_message and not found:
                message = first_message

        with self._lock[os.getpid()]:
            del self._messages[:to_delete_index]

        return message.channel, message.content


class LongPollingBus:

    _channel = 'bus'
    _queues_lock = collections.defaultdict(threading.Lock)
    _queues = collections.defaultdict(
        lambda: {'timeout': None, 'events': collections.defaultdict(list)})
    _messages = {}

    @classmethod
    def subscribe(cls, database, channels, last_message=None):
        pid = os.getpid()
        with cls._queues_lock[pid]:
            start_listener = (pid, database) not in cls._queues
            cls._queues[pid, database]['timeout'] = time.time() + _db_timeout
            if start_listener:
                listener = threading.Thread(
                    target=cls._listen, args=(database,), daemon=True)
                cls._queues[pid, database]['listener'] = listener
                listener.start()

        logger.info("subscribe to '%s' on '%s'", ','.join(channels), database)
        messages = cls._messages.get(database)
        if messages:
            channel, content = messages.get_next(channels, last_message)
            if content:
                return cls.create_response(channel, content)

        event = threading.Event()
        for channel in channels:
            if channel in cls._queues[pid, database]['events']:
                event_channel = cls._queues[pid, database]['events'][channel]
            else:
                with cls._queues_lock[pid]:
                    event_channel = cls._queues[pid, database][
                        'events'][channel]
            event_channel.append(event)

        triggered = event.wait(_long_polling_timeout)
        if not triggered:
            response = cls.create_response(None, None)
        else:
            response = cls.create_response(
                *cls._messages[database].get_next(channels, last_message))

        with cls._queues_lock[pid]:
            for channel in channels:
                events = cls._queues[pid, database]['events'][channel]
                for e in events[:]:
                    if e.is_set():
                        events.remove(e)

        return response

    @classmethod
    def create_response(cls, channel, message):
        response_data = {
            'message': message,
            'channel': channel,
            }
        logger.debug('Bus: %r', response_data)
        return response_data

    @classmethod
    def _listen(cls, database):
        db = backend.Database(database)
        if not db.has_channel():
            raise exceptions.NotImplemented

        logger.info("start listener for '%s'", database)
        conn = db.get_connection(autocommit=True)
        pid = os.getpid()
        selector = selectors.DefaultSelector()
        try:
            cursor = conn.cursor()
            cursor.execute('LISTEN "%s"' % cls._channel)

            cls._messages[database] = messages = _MessageQueue(_cache_timeout)

            now = time.time()
            selector.register(conn, selectors.EVENT_READ)
            while cls._queues[pid, database]['timeout'] > now:
                selector.select(timeout=_select_timeout)
                conn.poll()
                while conn.notifies:
                    notification = conn.notifies.pop()
                    payload = json.loads(
                        notification.payload,
                        object_hook=JSONDecoder())
                    channel = payload['channel']
                    message = payload['message']
                    messages.append(channel, message)

                    with cls._queues_lock[pid]:
                        events = cls._queues[pid, database][
                            'events'][channel].copy()
                        cls._queues[pid, database]['events'][channel].clear()
                    for event in events:
                        event.set()
                now = time.time()
                # Keep connected
                cursor.execute('SELECT 1')
        except Exception:
            logger.exception("bus listener on '%s' crashed", database)

            with cls._queues_lock[pid]:
                del cls._queues[pid, database]
            raise
        finally:
            selector.close()
            db.put_connection(conn)

        with cls._queues_lock[pid]:
            if cls._queues[pid, database]['timeout'] <= now:
                del cls._queues[pid, database]
            else:
                # A query arrived between the end of the while and here
                listener = threading.Thread(
                    target=cls._listen, args=(database,), daemon=True)
                cls._queues[pid, database]['listener'] = listener
                listener.start()

    @classmethod
    def publish(cls, channel, message):
        transaction = Transaction()
        if not transaction.database.has_channel():
            logger.info("database backend does not support channels")
            return

        cursor = transaction.connection.cursor()
        message['message_id'] = str(uuid.uuid4())
        payload = json.dumps({
                'channel': channel,
                'message': message,
                }, cls=JSONEncoder, separators=(',', ':'))
        cursor.execute('NOTIFY "%s", %%s' % cls._channel, (payload,))
        logger.debug(
            "publish %r to '%s' on '%s'",
            message, channel, transaction.database.name)


if config.get('bus', 'class'):
    Bus = resolve(config.get('bus', 'class'))
else:
    Bus = LongPollingBus


@app.route('/<string:database_name>/bus', methods=['POST'])
@app.auth_required
def subscribe(request, database_name):
    if not _allow_subscribe:
        raise exceptions.NotImplemented
    if _url_host and _url_host != request.host_url:
        response = redirect(
            urljoin(_url_host, request.path), HTTPStatus.PERMANENT_REDIRECT)
        # Allow to change the redirection after some time
        response.headers['Cache-Control'] = (
            'private, max-age=%s' % _web_cache_timeout)
        return response
    user = request.authorization.get('userid')
    channels = request.parsed_data.get('channels', [])
    if user is None:
        raise exceptions.BadRequest

    channels = set(filter(lambda c: not c.startswith('user:'), channels))
    channels.add('user:%s' % user)

    last_message = request.parsed_data.get('last_message')

    logger.info(
        "get bus messages for %s since %s from %s@%s%s",
        channels, last_message, request.authorization.username,
        request.remote_addr, request.path)
    bus_response = Bus.subscribe(database_name, channels, last_message)
    return Response(
        json.dumps(bus_response, cls=JSONEncoder, separators=(',', ':')),
        content_type='application/json')


def notify(title, body=None, priority=1, user=None, client=None):
    if user is None:
        if client is None:
            context_client = Transaction().context.get('client')
            if context_client:
                channel = 'client:%s' % context_client
            else:
                return
        else:
            channel = 'client:%s' % client
    elif client is None:
        channel = 'user:%s' % user
    else:
        channel = 'client:%s' % client

    return Bus.publish(channel, {
            'type': 'notification',
            'title': title,
            'body': body,
            'priority': priority,
            })
