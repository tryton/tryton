# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import json
import logging
from threading import Lock

from tryton.config import get_config_dir, CONFIG

logger = logging.getLogger(__name__)
COOKIES_PATH = os.path.join(get_config_dir(), 'device_cookies')


_lock = Lock()


def renew():
    from tryton.common import common

    def set_cookie(new_cookie):
        try:
            new_cookie = new_cookie()
        except Exception:
            logger.error("Cannot renew device cookie", exc_info=True)
        else:
            _set(new_cookie)

    current_cookie = get()
    common.RPCExecute(
        'model', 'res.user.device', 'renew', current_cookie,
        process_exception=False, callback=set_cookie)


def get():
    cookies = _load()
    return cookies.get(_key())


def _key():
    from tryton import common

    host = CONFIG['login.host']
    hostname = common.get_hostname(host)
    port = common.get_port(host)
    database = CONFIG['login.db']
    username = CONFIG['login.login']

    return '%(username)s@%(hostname)s:%(port)s/%(database)s' % {
        'username': username,
        'hostname': hostname,
        'port': port,
        'database': database,
        }


def _set(cookie):
    cookies = _load()
    cookies[_key()] = cookie
    try:
        with _lock:
            with open(COOKIES_PATH, 'w') as cookies_file:
                json.dump(cookies, cookies_file)
    except Exception:
        logger.error('Unable to save cookies file')


def _load():
    if not os.path.isfile(COOKIES_PATH):
        return {}
    try:
        with open(COOKIES_PATH) as cookies:
            cookies = json.load(cookies)
    except Exception:
        logger.error("Unable to load device cookies file", exc_info=True)
        cookies = {}
    return cookies
