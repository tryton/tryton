# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import configparser
import logging
import os
import sys
import urllib.parse
import warnings
from functools import cache
from getpass import getuser

__all__ = [
    'get_hostname', 'get_port', 'split_netloc',
    'parse_listen', 'parse_uri',
    'update_etc', 'has_section', 'add_section', 'remove_section',
    'set', 'get', 'getint', 'getfloat', 'getboolean']
logger = logging.getLogger(__name__)

# Needed so urlunsplit to always set netloc
for backend_name in ['postgresql', 'sqlite']:
    if backend_name not in urllib.parse.uses_netloc:
        urllib.parse.uses_netloc.append(backend_name)


def get_hostname(netloc):
    if '[' in netloc and ']' in netloc:
        return netloc.split(']')[0][1:]
    elif ':' in netloc:
        return netloc.split(':')[0]
    else:
        return netloc


def get_port(netloc):
    netloc = netloc.split(']')[-1]
    return int(netloc.split(':')[1])


def split_netloc(netloc):
    return get_hostname(netloc).replace('*', ''), get_port(netloc)


def parse_listen(value):
    for netloc in value.split(','):
        yield split_netloc(netloc)


def parse_uri(uri):
    return urllib.parse.urlparse(uri)


class TrytonConfigParser(configparser.ConfigParser):

    def __init__(self):
        super().__init__(interpolation=None)
        self.add_section('web')
        self.set('web', 'listen', 'localhost:8000')
        self.set('web', 'root', os.path.join(os.path.expanduser('~'), 'www'))
        self.set('web', 'num_proxies', '0')
        self.set('web', 'cache_timeout', str(60 * 60 * 12))
        self.add_section('database')
        self.set('database', 'uri',
            os.environ.get('TRYTOND_DATABASE_URI') or 'sqlite://')
        self.set('database', 'path', os.path.join(
                os.path.expanduser('~'), 'db'))
        self.set('database', 'list', 'True')
        self.set('database', 'retry', '5')
        self.set('database', 'language', 'en')
        self.set('database', 'timeout', str(30 * 60))
        self.set('database', 'subquery_threshold', str(1_000))
        self.add_section('request')
        self.set('request', 'max_size', str(2 * 1024 * 1024))
        self.set('request', 'max_size_authenticated',
            str(2 * 1024 * 1024 * 1024))
        self.set('request', 'timeout', str(60))
        self.add_section('cache')
        self.set('cache', 'transaction', '10')
        self.set('cache', 'model', '200')
        self.set('cache', 'record', '2000')
        self.set('cache', 'field', '100')
        self.set('cache', 'default', '1024')
        self.set('cache', 'ir.message', '10240')
        self.set('cache', 'ir.translation', '10240')
        self.set('cache', 'clean_timeout', '300')
        self.set('cache', 'select_timeout', '60')
        self.add_section('queue')
        self.set('queue', 'worker', 'False')
        self.add_section('ssl')
        self.add_section('email')
        self.set('email', 'uri', 'smtp://localhost:25')
        self.set('email', 'from', getuser())
        self.add_section('session')
        self.set('session', 'authentications', 'password')
        self.set('session', 'max_age', str(60 * 60 * 24 * 30))
        self.set('session', 'timeout', str(60 * 5))
        self.set('session', 'max_attempt', '5')
        self.set('session', 'max_attempt_ip_network', '300')
        self.set('session', 'ip_network_4', '32')
        self.set('session', 'ip_network_6', '56')
        self.add_section('password')
        self.set('password', 'length', '8')
        self.set('password', 'reset_timeout', str(24 * 60 * 60))
        self.add_section('bus')
        self.set('bus', 'allow_subscribe', 'False')
        self.set('bus', 'long_polling_timeout', str(5 * 60))
        self.set('bus', 'cache_timeout', '5')
        self.set('bus', 'select_timeout', '5')
        self.add_section('report')
        self.add_section('html')
        self.update_environ()
        self.update_etc()

    def update_environ(self):
        for key, value in os.environ.items():
            if not key.startswith('TRYTOND_'):
                continue
            try:
                section, option = key[len('TRYTOND_'):].lower().split('__', 1)
            except ValueError:
                continue
            if section.startswith('wsgi_'):
                section = section.replace('wsgi_', 'wsgi ')
            if not self.has_section(section):
                self.add_section(section)
            self.set(section, option, value)

    def update_etc(self, configfile=os.environ.get('TRYTOND_CONFIG')):
        if not configfile:
            return []
        if isinstance(configfile, str):
            configfile = [configfile]
        configfile = [
            os.path.expanduser(filename) for filename in configfile
            if filename]
        if not configfile:
            return []
        read_files = self.read(configfile)
        logger.info('using %s as configuration files', ', '.join(read_files))
        if configfile != read_files:
            logger.error('could not load %s',
                ','.join(set(configfile) - set(read_files)))
        return configfile


_config = TrytonConfigParser()


def update_etc(configfile=os.environ.get('TRYTOND_CONFIG')):
    configfile = _config.update_etc(configfile=configfile)
    _cache_clear()
    return configfile


has_section = _config.has_section
add_section = _config.add_section
remove_section = _config.remove_section


def set(section, option, value=None):
    _config.set(section, option, value=value)
    _cache_clear()


@cache
def get(section, option, default=None):
    return configparser.RawConfigParser.get(
        _config, section, option, fallback=default)


def _cache_clear():
    get.cache_clear()
    getint.cache_clear()
    getfloat.cache_clear()
    getboolean.cache_clear()


@cache
def getint(section, option, default=None):
    return configparser.RawConfigParser.getint(
        _config, section, option, fallback=default)


@cache
def getfloat(section, option, default=None):
    return configparser.RawConfigParser.getfloat(
        _config, section, option, fallback=default)


@cache
def getboolean(section, option, default=None):
    return configparser.RawConfigParser.getboolean(
        _config, section, option, fallback=default)


def __getattr__(name):
    if name == 'config':
        warnings.warn(
            "trytond.config.config is deprecated, "
            "use trytond.config", DeprecationWarning, stacklevel=2)
        return sys.modules[__name__]
    raise AttributeError(f"module {__name__} has no attribute {name}")
