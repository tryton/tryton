# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import ConfigParser
import urlparse

__all__ = ['config', 'get_hostname', 'get_port', 'split_netloc',
    'parse_listen', 'parse_uri']


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
        self.add_section('jsonrpc')
        self.set('jsonrpc', 'listen', 'localhost:8000')
        self.set('jsonrpc', 'data', '/var/www/localhost/tryton')
        self.add_section('xmlrpc')
        self.add_section('webdav')
        self.add_section('database')
        self.set('database', 'uri',
            os.environ.get('TRYTOND_DATABASE_URI', 'sqlite://'))
        self.set('database', 'path', '/var/lib/trytond')
        self.set('database', 'list', 'True')
        self.set('database', 'retry', 5)
        self.set('database', 'language', 'en_US')
        self.add_section('cache')
        self.set('cache', 'model', 200)
        self.set('cache', 'record', 2000)
        self.set('cache', 'field', 100)
        self.add_section('ssl')
        self.add_section('email')
        self.set('email', 'uri', 'smtp://localhost:25')
        self.add_section('session')
        self.set('session', 'timeout', 600)
        self.add_section('report')
        self.set('report', 'unoconv',
            'pipe,name=trytond;urp;StarOffice.ComponentContext')

    def update_etc(self, configfile=os.environ.get('TRYTOND_CONFIG')):
        if not configfile:
            return
        self.read(configfile)

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
