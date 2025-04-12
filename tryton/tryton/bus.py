# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import base64
import json
import logging
import socket
import threading
import time
import uuid
from collections import defaultdict
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from gi.repository import GLib

from tryton.config import CONFIG
from tryton.jsonrpc import object_hook

logger = logging.getLogger(__name__)


class Bus:

    ID = str(uuid.uuid4())
    current_thread = None
    channel_actions = defaultdict(list)
    listening = False

    @classmethod
    def listen(cls, connection):
        if not CONFIG['thread']:
            return
        listener = threading.Thread(
            target=cls._listen, args=(connection,), daemon=True)
        listener.start()
        cls.current_thread = listener.ident

    @classmethod
    def _listen(cls, connection):
        bus_timeout = CONFIG['client.bus_timeout']
        session = connection.session
        authorization = base64.b64encode(session.encode('utf-8'))
        headers = {
            'Content-Type': 'application/json',
            'Authorization': b'Session ' + authorization,
            }

        thread_id = threading.get_ident()
        wait = 1
        last_message = None
        url = None
        while connection.session == session:
            if url is None:
                if connection.url is None:
                    time.sleep(1)
                    continue
                url = connection.url + '/bus'
            cls.listening = True

            channels = list(cls.channel_actions)
            request = Request(url,
                data=json.dumps({
                        'last_message': last_message,
                        'channels': channels,
                        }).encode('utf-8'),
                headers=headers)
            logger.info('poll channels %s with last message %s',
                channels, last_message)
            try:
                response = urlopen(request, timeout=bus_timeout)
                wait = 1
            except socket.timeout:
                wait = 1
                continue
            except Exception as error:
                if thread_id != cls.current_thread:
                    break
                if isinstance(error, HTTPError):
                    if error.code in (301, 302, 303, 307, 308):
                        url = error.headers.get('Location')
                        continue
                    elif error.code == 501:
                        logger.info("Bus not supported")
                        break
                logger.error(
                    "An exception occurred while connecting to the bus. "
                    "Sleeping for %s seconds",
                    wait, exc_info=error)
                cls.listening = False
                time.sleep(min(wait, bus_timeout))
                wait *= 2
                continue

            if connection.session != session:
                break
            if thread_id != cls.current_thread:
                break

            data = json.loads(response.read(), object_hook=object_hook)
            if data['message']:
                last_message = data['message']['message_id']
                GLib.idle_add(cls.handle, data['channel'], data['message'])
        cls.listening = False

    @classmethod
    def handle(cls, channel, message):
        for callback in cls.channel_actions[channel]:
            callback(message)

    @classmethod
    def register(cls, channel, function):
        from tryton import rpc

        restart = channel not in cls.channel_actions
        cls.channel_actions[channel].append(function)
        if restart:
            # We can not really abort a thread, so we will just start a new one
            # and ignore the result of the one already running
            Bus.listen(rpc.CONNECTION)

    @classmethod
    def unregister(cls, channel, function):
        try:
            cls.channel_actions[channel].remove(function)
        except ValueError:
            pass

        if not cls.channel_actions[channel]:
            del cls.channel_actions[channel]


def popup_notification(message):
    if message['type'] != 'notification':
        return

    from tryton.gui.main import Main
    app = Main()
    app.show_notification(
        message.get('title', ''), message.get('body', ''),
        message.get('priority', 1))


Bus.register(f'client:{Bus.ID}', popup_notification)
