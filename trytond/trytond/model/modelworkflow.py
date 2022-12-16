#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelStorage
from trytond.transaction import Transaction
from trytond.pool import Pool


class ModelWorkflow(ModelStorage):
    '''
    Define a model with a workflow in Tryton.
    '''

    def __init__(self):
        super(ModelWorkflow, self).__init__()
        self._rpc.update({
            'workflow_trigger_validate': True,
        })

    def create(self, values):
        res = super(ModelWorkflow, self).create(values)
        self.workflow_trigger_create(res)
        return res

    def write(self, ids, values):
        res = super(ModelWorkflow, self).write(ids, values)
        self.workflow_trigger_write(ids)
        return res

    def delete(self, ids):
        instance_obj = Pool().get('workflow.instance')

        if isinstance(ids, (int, long)):
            ids = [ids]

        with Transaction().set_user(0):
            if instance_obj.search([
                ('res_id', 'in', ids),
                ('res_type', '=', self._name),
                ('state', '!=', 'complete'),
                ]):
                self.raise_user_error('delete_workflow_record')
        res = super(ModelWorkflow, self).delete(ids)
        self.workflow_trigger_delete(ids)
        return res

    def workflow_trigger_create(self, ids):
        '''
        Trigger create event

        :param ids: a list of id or an id
        '''
        pool = Pool()
        workflow_obj = pool.get('workflow')
        instance_obj = pool.get('workflow.instance')

        if isinstance(ids, (int, long)):
            ids = [ids]

        with Transaction().set_user(0):
            workflow_ids = workflow_obj.search([
                ('model', '=', self._name),
                ('on_create', '=', True),
                ])
        for res_id in ids:
            for wkf_id in workflow_ids:
                instance_obj.create({
                    'res_type': self._name,
                    'res_id': res_id,
                    'workflow': wkf_id,
                    'state': 'active',
                    })

    def workflow_trigger_write(self, ids):
        '''
        Trigger write event

        :param ids: a list of id or an id
        '''
        instance_obj = Pool().get('workflow.instance')

        if isinstance(ids, (int, long)):
            ids = [ids]

        with Transaction().set_user(0):
            instance_ids = instance_obj.search([
                ('res_id', 'in', ids),
                ('res_type', '=', self._name),
                ('state', '=', 'active'),
                ])
            instances = instance_obj.browse(instance_ids)
        for instance in instances:
            instance_obj.update(instance)

    def workflow_trigger_validate(self, ids, signal):
        '''
        Trigger validate event

        :param ids: a list of id or an id
        '''
        instance_obj = Pool().get('workflow.instance')

        if isinstance(ids, (int, long)):
            ids = [ids]

        with Transaction().set_user(0):
            instance_ids = instance_obj.search([
                ('res_id', 'in', ids),
                ('res_type', '=', self._name),
                ('state', '=', 'active'),
                ])
            instances = instance_obj.browse(instance_ids)
        for instance in instances:
            instance_obj.validate(instance, signal=signal)

    def workflow_trigger_delete(self, ids):
        '''
        Trigger delete event

        :param ids: a list of id or an id
        '''
        if self._name == 'workflow.instance':
            return
        instance_obj = Pool().get('workflow.instance')

        if isinstance(ids, (int, long)):
            ids = [ids]

        with Transaction().set_user(0):
            instance_ids = instance_obj.search([
                ('res_id', 'in', ids),
                ('res_type', '=', self._name),
                ])
            instance_obj.delete(instance_ids)
