# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import encodings.idna
import socket
import urllib.parse

from trytond.config import config
from trytond.transaction import Transaction

__all__ = ['URLMixin', 'is_secure', 'host', 'http_host']

HOSTNAME = (config.get('web', 'hostname')
    or socket.getfqdn())
HOSTNAME = '.'.join(encodings.idna.ToASCII(part).decode('ascii')
    if part else '' for part in HOSTNAME.split('.'))


class URLAccessor(object):
    __slots__ = ('_protocol',)

    def __init__(self, protocol='tryton'):
        self._protocol = protocol

    @classmethod
    def is_secure(cls):
        context = Transaction().context
        if context:
            request = context.get('_request')
            if request:
                return request['is_secure']
        return bool(config.get('ssl', 'certificate'))

    @classmethod
    def host(cls):
        context = Transaction().context
        if context:
            request = context.get('_request')
            if request:
                return request['http_host']
        return HOSTNAME

    @classmethod
    def http_host(cls):
        return urllib.parse.urlunsplit((
                'http' + ('s' if cls.is_secure() else ''),
                cls.host(), '', '', ''))

    @property
    def protocol(self):
        if self._protocol == 'http':
            return 'http' + ('s' if self.is_secure() else '')
        return self._protocol

    @property
    def separator(self):
        if self._protocol == 'http':
            return '#'
        return ''

    def __get__(self, inst, cls):
        from trytond.model import Model
        from trytond.wizard import Wizard
        from trytond.report import Report

        url_part = {}
        if issubclass(cls, Model):
            url_part['type'] = 'model'
        elif issubclass(cls, Wizard):
            url_part['type'] = 'wizard'
        elif issubclass(cls, Report):
            url_part['type'] = 'report'
        else:
            raise NotImplementedError

        url_part['name'] = cls.__name__
        url_part['database'] = Transaction().database.name

        local_part = urllib.parse.quote(
            '%(database)s/%(type)s/%(name)s' % url_part)
        if isinstance(inst, Model) and inst.id:
            local_part += '/%d' % inst.id
        return '%s://%s/%s%s' % (
            self.protocol, self.host(), self.separator, local_part)


is_secure = URLAccessor.is_secure
host = URLAccessor.host
http_host = URLAccessor.http_host


class URLMixin:
    __slots__ = ()
    __url__ = URLAccessor()
    __href__ = URLAccessor('http')
