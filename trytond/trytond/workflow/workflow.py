#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import os
from trytond.model import ModelView, ModelSQL, fields
from trytond.report import Report
from trytond.tools import exec_command_pipe
from trytond.backend import TableHandler
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction
from trytond.pool import Pool


class Workflow(ModelSQL, ModelView):
    "Workflow"
    _name = "workflow"
    _table = "wkf"
    _description = __doc__
    name = fields.Char('Name', required=True, translate=True)
    model = fields.Char('Resource Model', required=True, select=1)
    on_create = fields.Boolean('On Create', select=2)
    activities = fields.One2Many('workflow.activity', 'workflow',
       'Activities')

    def __init__(self):
        super(Workflow, self).__init__()
        self._error_messages.update({
            'no_workflow_defined': 'No workflow defined!',
            })

    def init(self, module_name):
        super(Workflow, self).init(module_name)
        cursor = Transaction().cursor
        table = TableHandler(cursor, self, module_name)

        # Migration from 1.2 rename osv into model
        if table.column_exist('osv'):
            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET model = osv')
            table.drop_column('osv', exception=True)

    def default_on_create(self):
        return 1

Workflow()


class WorkflowActivity(ModelSQL, ModelView):
    "Workflow activity"
    _name = "workflow.activity"
    _table = "wkf_activity"
    _description = __doc__
    name = fields.Char('Name', required=True, translate=True)
    workflow = fields.Many2One('workflow', 'Workflow', required=True,
       select=1, ondelete='CASCADE')
    split_mode = fields.Selection([
       ('XOR', 'Xor'),
       ('OR', 'Or'),
       ('AND', 'And'),
       ], 'Split Mode', required=True)
    join_mode = fields.Selection([
       ('XOR', 'Xor'),
       ('AND', 'And'),
       ], 'Join Mode', required=True)
    method = fields.Char('Method')
    flow_start = fields.Boolean('Flow Start')
    flow_stop = fields.Boolean('Flow Stop')
    stop_other = fields.Boolean('Stop Other')
    subflow =  fields.Many2One('workflow', 'Subflow')
    signal_send = fields.Char('Signal (subflow.*)')
    out_transitions = fields.One2Many('workflow.transition', 'act_from',
       'Outgoing transitions')
    in_transitions = fields.One2Many('workflow.transition', 'act_to',
       'Incoming transitions')

    def init(self, module_name):
        super(WorkflowActivity, self).init(module_name)
        cursor = Transaction().cursor
        table = TableHandler(cursor, self, module_name)

        # Migration from 2.0
        if table.column_exist('kind'):
            cursor.execute('UPDATE "%s" SET stop_other = %%s '
                "WHERE kind='stopall'" % self._table, (True,))
            table.drop_column('kind', exception=True)

    def default_kind(self):
        return 'dummy'

    def default_join_mode(self):
        return 'XOR'

    def default_split_mode(self):
        return 'XOR'

    def default_flow_start(self):
        return False

    def default_flow_stop(self):
        return False

    def default_stop_other(self):
        return False

WorkflowActivity()


class WorkflowTransition(ModelSQL, ModelView):
    "Workflow transition"
    _table = "wkf_transition"
    _name = "workflow.transition"
    _rec_name = 'signal'
    _description = __doc__
    trigger_model = fields.Char('Trigger Type')
    trigger_ids = fields.Char('Trigger Expr ID', states={
            'required': Bool(Eval('trigger_model')),
            }, depends=['trigger_model'])
    signal = fields.Char('Signal (button Name)')
    group = fields.Many2One('res.group', 'Group Required')
    condition = fields.Char('Condition', required=True)
    act_from = fields.Many2One('workflow.activity', 'Source Activity',
       required=True, select=1, ondelete='CASCADE')
    act_to = fields.Many2One('workflow.activity', 'Destination Activity',
       required=True, select=1, ondelete='CASCADE')
    instances = fields.Many2Many('workflow.transition-workflow.instance',
            'trans_id', 'inst_id', 'Instances')

    def init(self, module_name):
        cursor = Transaction().cursor
        super(WorkflowTransition, self).init(module_name)

        # Migration from 2.0: condition is a method name
        cursor.execute('UPDATE "%s" SET "condition" = %%s '
            'WHERE "condition" = %%s' % self._table, ('', 'True'))

    def default_condition(self):
        return ''

WorkflowTransition()


class WorkflowInstance(ModelSQL, ModelView):
    "Workflow instance"
    _table = "wkf_instance"
    _name = "workflow.instance"
    _rec_name = 'res_type'
    _description = __doc__
    workflow = fields.Many2One('workflow', 'Workflow', ondelete="RESTRICT",
            select=1)
    uid = fields.Integer('User ID')
    res_id = fields.Integer('Resource ID', required=True, select=1)
    res_type = fields.Char('Resource Model', required=True, select=1)
    state = fields.Char('State', required=True, select=1)
    overflows = fields.One2Many('workflow.workitem', 'subflow',
            'Overflow')
    transitions = fields.Many2Many('workflow.transition-workflow.instance',
            'inst_id', 'trans_id', 'Transitions')
    workitems = fields.One2Many('workflow.workitem', 'instance', 'Workitems')

    def __init__(self):
        super(WorkflowInstance, self).__init__()
        self._error_messages.update({
            'no_instance_defined': 'No workflow instance defined!',
            })
        for i in ('create', 'write', 'delete', 'copy'):
            del self._rpc[i]
        #TODO add a constraint to have only one active instance by resource

    def init(self, module_name):
        super(WorkflowInstance, self).init(module_name)

        table = TableHandler(Transaction().cursor, self, module_name)
        table.index_action(['res_id', 'res_type', 'state'], 'add')
        table.index_action(['res_id', 'workflow'], 'add')

    def fields_get(self, fields_names=None):
        res = super(WorkflowInstance, self).fields_get(
                fields_names=fields_names)
        for field in res:
            res[field]['readonly'] = True
        return res

    def create(self, values):
        pool = Pool()
        activity_obj = pool.get('workflow.activity')
        workitem_obj = pool.get('workflow.workitem')

        instance_id = super(WorkflowInstance, self).create(values)

        if 'workflow' in values:
            with Transaction().set_user(0):
                activity_ids = activity_obj.search([
                    ('flow_start', '=', True),
                    ('workflow', '=', values['workflow']),
                    ])
            for activity_id in activity_ids:
                workitem_obj.create({
                    'activity': activity_id,
                    'instance': instance_id,
                    'state': 'active',
                    })
        instance = self.browse(instance_id)
        self.update(instance)
        return instance_id

    def update(self, instance):
        '''
        '''
        pool = Pool()
        workitem_obj = pool.get('workflow.workitem')
        for workitem in instance.workitems:
            workitem_obj.process(workitem)
        instance = self.browse(instance.id)
        return self._update_end(instance)

    def validate(self, instance, signal, force_running=False):
        '''
        '''
        pool = Pool()
        workitem_obj = pool.get('workflow.workitem')
        for workitem in instance.workitems:
            workitem_obj.process(workitem, signal=signal,
                    force_running=force_running)
        instance = self.browse(instance.id)
        return self._update_end(instance)

    def _update_end(self, instance):
        pool = Pool()
        workitem_obj = pool.get('workflow.workitem')
        res = True
        for workitem in instance.workitems:
            if (workitem.state != 'complete') \
                    or not workitem.activity.flow_stop:
                res = False
                break
        if res:
            act_names = set()
            for workitem in instance.workitems:
                act_names.add(workitem.activity.name)
            with Transaction().set_user(0):
                self.write(instance.id, {
                    'state': 'complete',
                    })
                workitem_ids = workitem_obj.search([
                    ('subflow', '=', instance.id),
                    ])
                workitem_obj.write(workitem_ids, {
                    'state': 'complete',
                    })
            for workitem in workitem_obj.browse(workitem_ids):
                for act_name in act_names:
                    self.validate(workitem.instance,
                            signal='subflow.' + act_name)
        return res

WorkflowInstance()


class WorkflowTransitionInstance(ModelSQL):
    "Workflow Transition - Instance"
    _name = 'workflow.transition-workflow.instance'
    _table = 'wkf_witm_trans'
    _description = __doc__
    trans_id = fields.Many2One('workflow.transition', 'Transition',
            ondelete='CASCADE', select=1, required=True)
    inst_id = fields.Many2One('workflow.instance', 'Instance',
            ondelete='CASCADE', select=1, required=True)

    def fields_get(self, fields_names=None):
        res = super(WorkflowTransitionInstance, self).fields_get(
                fields_names=fields_names)
        for field in res:
            res[field]['readonly'] = True
        return res

WorkflowTransitionInstance()


class WorkflowWorkitem(ModelSQL, ModelView):
    "Workflow workitem"
    _table = "wkf_workitem"
    _name = "workflow.workitem"
    _rec_name = 'state'
    _description = __doc__
    activity = fields.Many2One('workflow.activity', 'Activity',
       required=True, ondelete="CASCADE", select=1)
    subflow = fields.Many2One('workflow.instance', 'Subflow',
       ondelete="CASCADE", select=1)
    instance = fields.Many2One('workflow.instance', 'Instance',
       required=True, ondelete="CASCADE", select=1)
    state = fields.Char('State', select=1)

    def __init__(self):
        super(WorkflowWorkitem, self).__init__()
        for i in ('create', 'write', 'delete', 'copy'):
            del self._rpc[i]

    def fields_get(self, fields_names=None):
        res = super(WorkflowWorkitem, self).fields_get(
                fields_names=fields_names)
        for field in res:
            res[field]['readonly'] = True
        return res

    def create(self, values):
        workitem_id = super(WorkflowWorkitem, self).create(values)
        with Transaction().set_user(0):
            workitem = self.browse(workitem_id)
        self.process(workitem)
        return workitem_id

    def process(self, workitem, signal=None, force_running=False):
        '''
        Process a workitem

        :param workitem: a BrowseRecord of the workflow.workitem
        :param signal: the signal
        :param force_running: a boolean
        '''
        pool = Pool()
        trigger_obj = pool.get('workflow.trigger')
        activity = workitem.activity
        triggers = False
        if workitem.state == 'active':
            triggers = True
            if not self._execute(workitem, activity):
                return False

        if workitem.state == 'complete' or force_running:
            res = self._split_test(workitem, activity.split_mode, signal)
            triggers = triggers and not res

        if triggers:
            trigger_transitions = (t for t in activity.out_transitions
                if t.trigger_model)
            for transition in trigger_transitions:
                model_obj = pool.get(workitem.instance.res_type)
                model_ids_fct = getattr(model_obj, transition.trigger_ids)
                ids = model_ids_fct(model_obj.browse(workitem.instance.res_id))
                with Transaction().set_user(0):
                    for res_id in ids:
                        trigger_obj.create({
                            'model': transition.trigger_model,
                            'res_id': res_id,
                            'instance': workitem.instance.id,
                            'workitem': workitem.id,
                            })
        return True

    def _state_set(self, workitem, state):
        self.write(workitem.id, {
            'state': state,
            })
        #XXX must be changed with a cache reset on BrowseRecord
        workitem._data[workitem.id]['state'] = state

    def _execute(self, workitem, activity):
        pool = Pool()
        instance_obj = pool.get('workflow.instance')
        #send a signal to overflow
        if (workitem.state == 'active') and activity.signal_send:
            for overflow in workitem.overflows:
                instance_obj.validate(overflow.instance, activity.signal_send,
                        force_running=True)

        if workitem.state == 'active':
            self._state_set(workitem, 'running')
            if activity.stop_other:
                ids = self.search([
                    ('instance', '=', workitem.instance.id),
                    ('id', '!=', workitem.id),
                    ])
                #XXX check if delete must not be replace by _state_set 'complete'
                with Transaction().set_user(0):
                    self.delete(ids)
            if activity.method:
                id_new = self._execute_action(workitem, activity)
            else:
                id_new = None
            if activity.subflow:
                if activity.method and id_new:
                    with Transaction().set_user(0):
                        instance_id = instance_obj.search([
                            ('res_id', '=', id_new),
                            ('workflow', '=', activity.subflow.id),
                            ], limit=1)[0]
                elif not activity.method:
                    instance_id = instance_obj.create({
                        'res_type': workitem.instance.res_type,
                        'res_id': workitem.instance.res_id,
                        'workflow': activity.subflow.id,
                        })
                else:
                    with Transaction().set_user(0):
                        self.delete(workitem.id)
                    return False
                self.write(workitem.id, {
                    'subflow': instance_id,
                    })
                #XXX must be changed with a cache reset on BrowseRecord
                workitem._data[workitem.id]['subflow'] = instance_id
            else:
                self._state_set(workitem, 'complete')
        elif workitem.state == 'running' and activity.subflow:
            if workitem.subflow.state == 'complete':
                self._state_set(workitem, 'complete')

        return True

    def _execute_action(self, workitem, activity):
        model_obj = Pool().get(workitem.instance.res_type)
        wkf_action = getattr(model_obj, activity.method)
        return wkf_action(model_obj.browse(workitem.instance.res_id))

    def _activate_transition(self, workitem, transition, signal):
        pool = Pool()
        user_obj = pool.get('res.user')
        if transition.signal:
            if signal != transition.signal:
                return False

        if transition.group and Transaction().user != 0:
            user_groups = user_obj.get_groups()
            if transition.group.id not in user_groups:
                return False

        model_obj = pool.get(workitem.instance.res_type)
        if transition.condition:
            test_fct = getattr(model_obj, transition.condition)
            return test_fct(model_obj.browse(workitem.instance.res_id))
        else:
            return True

    def _split_test(self, workitem, split_mode, signal=None):
        pool = Pool()
        instance_obj = pool.get('workflow.instance')
        test = False
        transitions = []
        if split_mode == 'XOR' or split_mode == 'OR':
            for transition in workitem.activity.out_transitions:
                if self._activate_transition(workitem, transition, signal):
                    test = True
                    transitions.append(transition)
                    if split_mode == 'XOR':
                        break
        else:
            test = True
            for transition in workitem.activity.out_transitions:
                if not self._activate_transition(workitem, transition, signal):
                    test = False
                    break
                if transition.id not in \
                        [x.id for x in workitem.instance.transitions]:
                    transitions.append(transition)
        if test and len(transitions):
            with Transaction().set_user(0):
                instance_obj.write(workitem.instance.id, {
                    'transitions': [('add', [x.id for x in transitions])],
                    })
                instance = workitem.instance
                self.delete(workitem.id)
            for transition in transitions:
                self._join_test(transition, instance)
            return True
        return False

    def _join_test(self, transition, instance):
        pool = Pool()
        instance_obj = pool.get('workflow.instance')
        activity = transition.act_to
        if activity.join_mode == 'XOR':
            self.create({
                'activity': activity.id,
                'instance': instance.id,
                'state': 'active',
                })
            with Transaction().set_user(0):
                instance_obj.write(instance.id, {
                    'transitions': [('unlink', transition.id)],
                    })
        else:
            delete = True
            for transition in activity.in_transitions:
                if instance.id not in \
                        [x.id for x in transition.instances]:
                    delete = False
                    break
            if delete:
                with Transaction().set_user(0):
                    instance_obj.write(instance.id, {
                        'transitions': [('unlink', [x.id
                            for x in activity.in_transitions])],
                        })
                self.create({
                    'activity': activity.id,
                    'instance': instance.id,
                    'state': 'active',
                    })

WorkflowWorkitem()


class WorkflowTrigger(ModelSQL, ModelView):
    "Workflow trigger"
    _table = "wkf_trigger"
    _name = "workflow.trigger"
    _description = __doc__
    res_id = fields.Integer('Resource ID')
    model = fields.Char('Model')
    instance = fields.Many2One('workflow.instance',
       'Destination Instance', ondelete="CASCADE")
    workitem = fields.Many2One('workflow.workitem', 'Workitem',
       required=True, ondelete="CASCADE")

    def __init__(self):
        super(WorkflowTrigger, self).__init__()
        for i in ('create', 'write', 'delete', 'copy'):
            del self._rpc[i]

    def init(self, module_name):
        super(WorkflowTrigger, self).init(module_name)

        table = TableHandler(Transaction().cursor, self, module_name)
        table.index_action(['res_id', 'model'], 'add')

    def fields_get(self, fields_names=None):
        res = super(WorkflowTrigger, self).fields_get(
                fields_names=fields_names)
        for field in res:
            res[field]['readonly'] = True
        return res

WorkflowTrigger()


class InstanceGraph(Report):
    _name = 'workflow.instance.graph'

    def execute(self, ids, datas):
        import pydot
        pool = Pool()
        lang_obj = pool.get('ir.lang')
        workflow_obj = pool.get('workflow')
        instance_obj = pool.get('workflow.instance')

        lang_id = lang_obj.search([
            ('code', '=', Transaction().language),
            ], limit=1)[0]
        lang = lang_obj.browse(lang_id)

        workflow_id = workflow_obj.search([
            ('model', '=', datas['model']),
            ], limit=1)
        if not workflow_id:
            workflow_obj.raise_user_error('no_workflow_defined')
        workflow_id = workflow_id[0]
        workflow = workflow_obj.browse(workflow_id)
        instance_id = instance_obj.search([
            ('res_id', '=', datas['id']),
            ('workflow', '=', workflow.id),
            ], order=[('id', 'DESC')], limit=1)
        if not instance_id:
            instance_obj.raise_user_error('no_instance_defined')
        instance_id = instance_id[0]

        title = "Workflow: %s" % (workflow.name.encode('ascii', 'replace'),)
        if pydot.__version__ == '1.0.2':
            # version 1.0.2 doesn't quote correctly label on Dot object
            title = '"' + title + '"'
        graph = pydot.Dot(fontsize='16',
                label=title)
        graph.set('center', '1')
        graph.set('ratio', 'auto')
        if lang.direction == 'ltr':
            if hasattr(graph, 'set_rankdir'):
                graph.set_rankdir('LR')
            else:
                graph.set('rankdir', 'LR')
        else:
            if hasattr(graph, 'set_rankdir'):
                graph.set_rankdir('RL')
            else:
                graph.set('rankdir', 'RL')
        self.graph_instance_get(graph, instance_id, datas.get('nested', False))
        data = graph.create(prog='dot', format='png')
        return ('png', buffer(data), False, workflow.name)

    def graph_instance_get(self, graph, instance_id, nested=False):
        pool = Pool()
        instance_obj = pool.get('workflow.instance')
        instance = instance_obj.browse(instance_id)
        self.graph_get(graph, instance.workflow.id, nested,
                self.workitem_get(instance.id))

    def workitem_get(self, instance_id):
        res = {}
        pool = Pool()
        workitem_obj = pool.get('workflow.workitem')
        workitem_ids = workitem_obj.search([
            ('instance', '=', instance_id),
            ])
        workitems = workitem_obj.browse(workitem_ids)
        for workitem in workitems:
            res.setdefault(workitem.activity.id, 0)
            res[workitem.activity.id] += 1
            if workitem.subflow:
                res.update(self.workitem_get(workitem.subflow.id))
        return res

    def graph_get(self, graph, workflow_id, nested=False, workitem=None):
        import pydot
        if workitem is None:
            workitem = {}
        pool = Pool()
        activity_obj = pool.get('workflow.activity')
        workflow_obj = pool.get('workflow')
        transition_obj = pool.get('workflow.transition')
        activity_ids = activity_obj.search([
            ('workflow', '=', workflow_id),
            ])
        id2activities = {}
        actfrom = {}
        actto = {}
        activities = activity_obj.browse(activity_ids)
        start = 0
        stop = {}
        for activity in activities:
            if activity.flow_start:
                start = activity.id
            if activity.flow_stop:
                stop['subflow.' + activity.name] =  activity.id
            id2activities[activity.id] = activity
            if activity.subflow and nested:
                workflow = workflow_obj.browse(activity.subflow.id)
                subgraph = pydot.Cluster('subflow' + str(workflow.id),
                        fontsize='12',
                        label="Subflow: " + activity.name.encode('ascii', 'replace'))
                (substart, substop) = self.graph_get(subgraph, workflow.id,
                        nested, workitem)
                graph.add_subgraph(subgraph)
                actfrom[activity.id] = substart
                actto[activity.id] = substop
            else:
                args = {}
                args['label'] = activity.name.encode('ascii', 'replace')
                args['fontsize'] = '10'
                if activity.flow_start or activity.flow_stop:
                    args['style'] = 'filled'
                    args['color'] = 'lightgrey'
                if activity.subflow:
                    args['shape'] = 'box'
                else:
                    args['shape'] = 'octagon'
                if activity.id in workitem:
                    args['label'] += '\\nx ' + str(workitem[activity.id])
                    args['color'] = 'red'
                graph.add_node(pydot.Node(activity.id, **args))
                actfrom[activity.id] = (activity.id, {})
                actto[activity.id] = (activity.id, {})
        transition_ids = transition_obj.search([
            ('act_from', 'in', [x.id for x in activities]),
            ])
        transitions = transition_obj.browse(transition_ids)
        for transition in transitions:
            args = {}
            args['label'] = ' '
            if transition.condition:
                args['label'] += transition.condition
            if transition.signal:
                args['label'] += '\\n' + str(transition.signal)
                args['style'] = 'bold'
            if id2activities[transition.act_from.id].split_mode == 'AND':
                args['arrowtail'] = 'box'
            elif id2activities[transition.act_from.id].split_mode == 'OR':
                args['arrowtail'] = 'inv'
            if id2activities[transition.act_to.id].join_mode == 'AND':
                args['arrowhead'] = 'crow'

            activity_from = actfrom[transition.act_from.id][1].get(
                    transition.signal, actfrom[transition.act_from.id][0])
            activity_to = actto[transition.act_to.id][1].get(
                    transition.signal, actto[transition.act_to.id][0])
            graph.add_edge(pydot.Edge(str(activity_from), str(activity_to),
                fontsize='10', **args))
        return ((start, {}), (stop.values()[0], stop))

InstanceGraph()
