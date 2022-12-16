#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model import ModelStorage


class ModelWorkflow(ModelStorage):
    '''
    Define a model with a workflow in Tryton.
    '''

    def __init__(self):
        super(ModelWorkflow, self).__init__()
        self._rpc.update({
            'workflow_trigger_validate': True,
        })

    def create(self, cursor, user, values, context=None):
        res = super(ModelWorkflow, self).create(cursor, user, values,
                context=context)
        self.workflow_trigger_create(cursor, user, res, context=context)
        return res

    def write(self, cursor, user, ids, values, context=None):
        res = super(ModelWorkflow, self).write(cursor, user, ids, values,
                context=context)
        self.workflow_trigger_write(cursor, user, ids, context=context)
        return res

    def delete(self, cursor, user, ids, context=None):
        instance_obj = self.pool.get('workflow.instance')

        if isinstance(ids, (int, long)):
            ids = [ids]

        if instance_obj.search(cursor, 0, [
            ('res_id', 'in', ids),
            ('res_type', '=', self._name),
            ('state', '!=', 'complete'),
            ], context=context):
            self.raise_user_error(cursor, 'delete_workflow_record',
                    context=context)
        res = super(ModelWorkflow, self).delete(cursor, user, ids,
                context=context)
        self.workflow_trigger_delete(cursor, user, ids, context=context)
        return res

    def workflow_trigger_create(self, cursor, user, ids, context=None):
        '''
        Trigger create event

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of id or an id
        :param context: the context
        '''
        workflow_obj = self.pool.get('workflow')
        instance_obj = self.pool.get('workflow.instance')

        if isinstance(ids, (int, long)):
            ids = [ids]

        workflow_ids = workflow_obj.search(cursor, 0, [
            ('model', '=', self._name),
            ('on_create', '=', True),
            ], context=context)
        for res_id in ids:
            for wkf_id in workflow_ids:
                instance_obj.create(cursor, user, {
                    'res_type': self._name,
                    'res_id': res_id,
                    'workflow': wkf_id,
                    'state': 'active',
                    }, context=context)


    def workflow_trigger_write(self, cursor, user, ids, context=None):
        '''
        Trigger write event

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of id or an id
        :param context: the context
        '''
        instance_obj = self.pool.get('workflow.instance')

        if isinstance(ids, (int, long)):
            ids = [ids]

        instance_ids = instance_obj.search(cursor, 0, [
            ('res_id', 'in', ids),
            ('res_type', '=', self._name),
            ('state', '=', 'active'),
            ], context=context)
        for instance in instance_obj.browse(cursor, 0, instance_ids,
                context=context):
            instance_obj.update(cursor, user, instance, context=context)

    def workflow_trigger_validate(self, cursor, user, ids, signal,
            context=None):
        '''
        Trigger validate event

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of id or an id
        :param context: the context
        '''
        instance_obj = self.pool.get('workflow.instance')

        if isinstance(ids, (int, long)):
            ids = [ids]

        instance_ids = instance_obj.search(cursor, 0, [
            ('res_id', 'in', ids),
            ('res_type', '=', self._name),
            ('state', '=', 'active'),
            ], context=context)
        for instance in instance_obj.browse(cursor, 0, instance_ids,
                context=context):
            instance_obj.validate(cursor, user, instance, signal=signal,
                    context=context)

    def workflow_trigger_delete(self, cursor, user, ids, context=None):
        '''
        Trigger delete event

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of id or an id
        :param context: the context
        '''
        if self._name == 'workflow.instance':
            return
        instance_obj = self.pool.get('workflow.instance')

        if isinstance(ids, (int, long)):
            ids = [ids]

        instance_ids = instance_obj.search(cursor, 0, [
            ('res_id', 'in', ids),
            ('res_type', '=', self._name),
            ], context=context)
        instance_obj.delete(cursor, 0, instance_ids, context=context)
