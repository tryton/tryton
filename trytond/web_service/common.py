#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
from trytond.netsvc import Service
from trytond import security
from trytond.version import VERSION
import time
from trytond.tools import Cache
import logging

class Common(Service):

    def __init__(self, name="common"):
        Service.__init__(self, name)
        Service.join_group(self, "web-service")
        Service.export_method(self, self.about)
        Service.export_method(self, self.login)
        Service.export_method(self, self.version)
        Service.export_method(self, self.timezone_get)

    def login(self, database, login, password):
        res = security.login(database, login, password)
        Cache.clean(database)
        logger = logging.getLogger("web-service")
        msg = res and 'successful login' or 'bad login or password'
        logger.info("%s from '%s' using database '%s'" % (msg, login, database))
        Cache.resets(database)
        return res or False

    def about(self):
        return '''
Tryton %s

The whole source code is distributed under the terms of the
GNU Public Licence v2.
''' % (VERSION,)

    def version(self):
        '''
        Return the server version
        '''
        return VERSION

    def timezone_get(self, database, login, password):
        return time.tzname[0]
