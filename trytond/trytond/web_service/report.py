#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
from trytond.netsvc import Service, LocalService
from trytond import security
from trytond.tools import Cache


class Report(Service):

    def __init__(self, name='report'):
        Service.__init__(self, name)
        Service.join_group(self, 'web-service')
        Service.export_method(self, self.execute)

    def execute(self, database, user, passwd, report_name, ids, datas,
            context=None):
        security.check(database, user, passwd)
        Cache.clean(database)
        report = LocalService('report_proxy')
        res = report.execute(database, user, report_name, ids, datas, context)
        Cache.resets(database)
        return res
