# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import ConfigParser
import urlparse
import logging

__all__ = ['config', 'get_hostname', 'get_port', 'split_netloc',
    'parse_listen', 'parse_uri']
logger = logging.getLogger(__name__)


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
    return urlparse.urlparse(uri)


class TrytonConfigParser(ConfigParser.RawConfigParser):

    def __init__(self):
        ConfigParser.RawConfigParser.__init__(self)
        self.add_section('web')
        self.set('web', 'listen', 'localhost:8000')
        self.set('web', 'root', os.path.join(os.path.expanduser('~'), 'www'))
        self.set('web', 'num_proxies', 0)
        self.add_section('database')
        self.set('database', 'uri',
            os.environ.get('TRYTOND_DATABASE_URI', 'sqlite://'))
        self.set('database', 'path', os.path.join(
                os.path.expanduser('~'), 'db'))
        self.set('database', 'list', 'True')
        self.set('database', 'retry', 5)
        self.set('database', 'language', 'en')
        self.add_section('request')
        self.set('request', 'max_size', 2 * 1024 * 1024)
        self.set('request', 'max_size_authenticated', 2 * 1024 * 1024 * 1024)
        self.add_section('cache')
        self.set('cache', 'model', 200)
        self.set('cache', 'record', 2000)
        self.set('cache', 'field', 100)
        self.add_section('ssl')
        self.add_section('email')
        self.set('email', 'uri', 'smtp://localhost:25')
        self.add_section('session')
        self.set('session', 'authentications', 'password')
        self.set('session', 'timeout', 600)
        self.set('session', 'max_attempt', 5)
        self.set('session', 'max_attempt_ip_network', 300)
        self.set('session', 'ip_network_4', 32)
        self.set('session', 'ip_network_6', 56)
        self.add_section('password')
        self.set('password', 'length', 8)
        self.set('password', 'entropy', 0.75)
        self.set('password', 'reset_timeout', 24 * 60 * 60)
        self.update_etc()

    def update_etc(self, configfile=os.environ.get('TRYTOND_CONFIG')):
        if isinstance(configfile, basestring):
            configfile = [configfile]
        if not configfile or not filter(None, configfile):
            return
        read_files = self.read(configfile)
        logger.info('using %s as configuration files', ', '.join(read_files))

    def get(self, section, option, *args, **kwargs):
        default = kwargs.pop('default', None)
        try:
            return ConfigParser.RawConfigParser.get(self, section, option,
                *args, **kwargs)
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
            return default

    def getint(self, section, option, *args, **kwargs):
        default = kwargs.pop('default', None)
        try:
            return ConfigParser.RawConfigParser.getint(self, section, option,
                *args, **kwargs)
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError,
                TypeError):
            return default

    def getfloat(self, section, option, *args, **kwargs):
        default = kwargs.pop('default', None)
        try:
            return ConfigParser.RawConfigParser.getfloat(self, section, option,
                *args, **kwargs)
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError,
                TypeError):
            return default

    def getboolean(self, section, option, *args, **kwargs):
        default = kwargs.pop('default', None)
        try:
            return ConfigParser.RawConfigParser.getboolean(
                self, section, option, *args, **kwargs)
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError,
                AttributeError):
            return default

config = TrytonConfigParser()
