# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import encodings.idna
import socket
import urllib.parse

from trytond.config import config
from trytond.transaction import Transaction

__all__ = ['URLMixin', 'HOSTNAME']

HOSTNAME = (config.get('web', 'hostname')
    or socket.getfqdn())
HOSTNAME = '.'.join(encodings.idna.ToASCII(part).decode('ascii')
    if part else '' for part in HOSTNAME.split('.'))


class URLAccessor(object):
    __slots__ = ()

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

        local_part = urllib.parse.quote('%(database)s/%(type)s/%(name)s' % url_part)
        if isinstance(inst, Model) and inst.id:
            local_part += '/%d' % inst.id
        return 'tryton://%s/%s' % (HOSTNAME, local_part)


class URLMixin(object):
    __slots__ = ()
    __url__ = URLAccessor()
