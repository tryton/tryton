# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import base64
import json
import logging
import socket
import threading
import time
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from gi.repository import GObject

from tryton.jsonrpc import object_hook
from tryton.config import CONFIG


logger = logging.getLogger(__name__)


ID = str(uuid.uuid4())
CHANNELS = [
    'client:%s' % ID,
    ]


def listen(connection):
    listener = threading.Thread(
        target=_listen, args=(connection,), daemon=True)
    listener.start()


def _listen(connection):
    bus_timeout = CONFIG['client.bus_timeout']
    session = connection.session
    authorization = base64.b64encode(session.encode('utf-8'))
    headers = {
        'Content-Type': 'application/json',
        'Authorization': b'Session ' + authorization,
        }

    wait = 1
    last_message = None
    url = None
    while connection.session == session:
        if url is None:
            if connection.url is None:
                time.sleep(1)
                continue
            url = connection.url + '/bus'
        request = Request(url,
            data=json.dumps({
                    'last_message': last_message,
                    'channels': CHANNELS,
                    }).encode('utf-8'),
            headers=headers)
        logger.info('poll channels %s with last message %s',
            CHANNELS, last_message)
        try:
            response = urlopen(request, timeout=bus_timeout)
            wait = 1
        except socket.timeout:
            wait = 1
            continue
        except Exception as error:
            if isinstance(error, HTTPError) and error.code == 501:
                logger.info("Bus not supported")
                break
            logger.error(
                "An exception occured while connecting to the bus."
                "Sleeping for %s seconds",
                wait, exc_info=error)
            time.sleep(min(wait, bus_timeout))
            wait *= 2
            continue

        if connection.session != session:
            break

        data = json.loads(response.read(), object_hook=object_hook)
        if data['message']:
            last_message = data['message']['message_id']
            GObject.idle_add(handle, data['message'])


def handle(message):
    from tryton.gui.main import Main

    app = Main()
    if message['type'] == 'notification':
        app.show_notification(
            message.get('title', ''), message.get('body', ''),
            message.get('priority', 1))
