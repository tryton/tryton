#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import encodings.idna
import urllib
import socket

from trytond.config import CONFIG
from trytond.transaction import Transaction


class URLMixin(object):

    def get_url(self):
        from trytond.model import Model
        from trytond.wizard import Wizard
        from trytond.report import Report

        hostname = (CONFIG['hostname_jsonrpc']
            or unicode(socket.getfqdn(), 'utf8'))
        hostname = '.'.join(encodings.idna.ToASCII(part) for part in
            hostname.split('.'))

        url_part = {}
        if isinstance(self, Model):
            url_part['type'] = 'model'
        elif isinstance(self, Wizard):
            url_part['type'] = 'wizard'
        elif isinstance(self, Report):
            url_part['type'] = 'report'
        else:
            raise NotImplementedError

        url_part['name'] = self._name
        url_part['database'] = Transaction().cursor.database_name

        local_part = urllib.quote('%(database)s/%(type)s/%(name)s' % url_part)
        return 'tryton://%s/%s' % (hostname, local_part)
