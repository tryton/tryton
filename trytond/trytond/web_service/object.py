#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
from trytond.netsvc import Service, LocalService
from trytond import security
from trytond.tools import Cache

class Object(Service):

    def __init__(self, name="object"):
        Service.__init__(self, name)
        Service.join_group(self, 'web-service')
        Service.export_method(self, self.execute)
        Service.export_method(self, self.exec_workflow)
        Service.export_method(self, self.obj_list)

    def exec_workflow(self, database, user, session, object_name, method,
            object_id, *args):
        security.check(database, user, session)
        Cache.clean(database)
        service = LocalService("object_proxy")
        res = service.exec_workflow(database, user, object_name, method,
                object_id, *args)
        Cache.resets(database)
        return res

    def execute(self, database, user, session, object_name, method, *args):
        if object_name == 'res.request' and method == 'request_get':
            security.check(database, user, session, False)
        else:
            security.check(database, user, session)
        Cache.clean(database)
        service = LocalService("object_proxy")
        res = service.execute(database, user, object_name, method, *args)
        Cache.resets(database)
        return res

    def obj_list(self, database, user, session):
        security.check(database, user, session)
        Cache.clean(database)
        service = LocalService("object_proxy")
        res = service.obj_list()
        Cache.resets(database)
        return res
