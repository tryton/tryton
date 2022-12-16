#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Workflow service"
from trytond.netsvc import Service
import instance


class WorkflowService(Service):
    "Workflow service"

    def __init__(self, name='workflow'):
        Service.__init__(self, name)
        Service.export_method(self, self.clear_cache)
        Service.export_method(self, self.trg_write)
        Service.export_method(self, self.trg_delete)
        Service.export_method(self, self.trg_create)
        Service.export_method(self, self.trg_validate)
        Service.export_method(self, self.trg_redirect)
        Service.export_method(self, self.trg_trigger)
        self.wkf_on_create_cache = {}

    def clear_cache(self, cursor):
        "Clear workflow cache"
        self.wkf_on_create_cache[cursor.dbname] = {}

    def trg_write(self, user, res_type, res_id, cursor, context=None):
        "Trigger write"
        ident = (user, res_type, res_id)
        cursor.execute('SELECT id FROM wkf_instance ' \
                'WHERE res_id = %s AND res_type = %s AND state = %s',
                (res_id, res_type, 'active'))
        for (instance_id,) in cursor.fetchall():
            instance.update(cursor, instance_id, ident, context=context)

    def trg_trigger(self, user, res_type, res_id, cursor, context=None):
        "Trigger trigger"
        cursor.execute('SELECT instance FROM wkf_trigger ' \
                'WHERE res_id = %s AND model = %s', (res_id, res_type))
        # TODO remove the query from for statement
        for (instance_id,) in cursor.fetchall():
            cursor.execute('SELECT uid, res_type, res_id FROM wkf_instance ' \
                    'WHERE id = %s', (instance_id,))
            ident = cursor.fetchone()
            instance.update(cursor, instance_id, ident, context=context)

    def trg_delete(self, user, res_type, res_id, cursor, context=None):
        "Trigger delete"
        ident = (user, res_type, res_id)
        instance.delete(cursor, ident, context=context)

    def trg_create(self, user, res_type, res_id, cursor, context=None):
        "Trigger create"
        ident = (user, res_type, res_id)
        self.wkf_on_create_cache.setdefault(cursor.dbname, {})
        if res_type in self.wkf_on_create_cache[cursor.dbname]:
            wkf_ids = self.wkf_on_create_cache[cursor.dbname][res_type]
        else:
            cursor.execute('SELECT id FROM wkf ' \
                    'WHERE osv = %s AND on_create = True', (res_type,))
            wkf_ids = cursor.fetchall()
            self.wkf_on_create_cache[cursor.dbname][res_type] = wkf_ids
        for (wkf_id,) in wkf_ids:
            cursor.execute(
                "SELECT id FROM wkf_instance " \
                    "WHERE res_type = %s AND res_id = %s "\
                    "AND workflow = %s AND state = 'active'",
                (res_type, res_id, wkf_id,))
            if cursor.rowcount:
                raise Exception("Error", "Another active workflow already "\
                                    "exist for this record: %s@%s."% \
                                    (res_id, res_type))
            instance.create(cursor, ident, wkf_id, context=context)

    def trg_validate(self, user, res_type, res_id, signal, cursor,
            context=None):
        "Trigger validate"
        ident = (user, res_type, res_id)
        # ids of all active workflow instances
        # for a corresponding resource (id, model_name)
        cursor.execute('SELECT id FROM wkf_instance ' \
                'WHERE res_id = %s AND res_type = %s AND state = %s',
                (res_id, res_type, 'active'))
        for (instance_id,) in cursor.fetchall():
            instance.validate(cursor, instance_id, ident, signal,
                    context=context)

    def trg_redirect(self, user, res_type, res_id, new_rid, cursor,
            context=None):
        """
        Trigger redirect
        make all workitems which are waiting for a (subflow) workflow instance
        for the old resource point to the (first active) workflow instance for
        the new resource
        """
        # get ids of wkf instances for the old resource (res_id)
        # XXX shouldn't we get only active instances?
        cursor.execute('SELECT id, workflow FROM wkf_instance ' \
                'WHERE res_id = %s AND res_type = %s', (res_id, res_type))
        for old_inst_id, wkf_id in cursor.fetchall():
            # first active instance for new resource (new_rid), using same wkf
            cursor.execute(
                'SELECT id '\
                'FROM wkf_instance '\
                'WHERE res_id = %s AND res_type = %s ' \
                    'AND workflow = %s AND state = %s',
                (new_rid, res_type, wkf_id, 'active'))
            new_id = cursor.fetchone()
            if new_id:
                # select all workitems which "wait" for the old instance
                cursor.execute('SELECT id FROM wkf_workitem ' \
                        'WHERE subflow = %s', (old_inst_id,))
                for (item_id,) in cursor.fetchall():
                    # redirect all those workitems
                    # to the wkf instance of the new resource
                    cursor.execute('UPDATE wkf_workitem ' \
                            'SET subflow = %s ' \
                            'WHERE id = %s', (new_id[0], item_id))
