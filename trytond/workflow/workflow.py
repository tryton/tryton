#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Workflow"
import os
from trytond.model import ModelView, ModelSQL, fields
from trytond.report import Report
from trytond.tools import exec_command_pipe
from trytond.backend import TableHandler
from trytond.pyson import Eval, Equal, Not
import expr
import base64


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

    def init(self, cursor, module_name):
        super(Workflow, self).init(cursor, module_name)
        table = TableHandler(cursor, self, module_name)

        # Migration from 1.2 rename osv into model
        if table.column_exist('osv'):
            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET model = osv')
            table.drop_column('osv', exception=True)

    def default_on_create(self, cursor, user, context=None):
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
    kind = fields.Selection([
       ('dummy', 'Dummy'),
       ('function', 'Function'),
       ('subflow', 'Subflow'),
       ('stopall', 'Stop All'),
       ], 'Kind', required=True)
    action = fields.Text('Action', states={
        'readonly': Equal(Eval('kind'), 'dummy'),
        'required': Equal(Eval('kind'), 'function'),
        })
    flow_start = fields.Boolean('Flow Start')
    flow_stop = fields.Boolean('Flow Stop')
    subflow =  fields.Many2One('workflow', 'Subflow', states={
        'readonly': Not(Equal(Eval('kind'), 'subflow')),
        'required': Equal(Eval('kind'), 'subflow'),
        })
    signal_send = fields.Char('Signal (subflow.*)')
    out_transitions = fields.One2Many('workflow.transition', 'act_from',
       'Outgoing transitions')
    in_transitions = fields.One2Many('workflow.transition', 'act_to',
       'Incoming transitions')

    #TODO add a _constraint on subflow without action
    #to have the same model than the workflow

    def default_kind(self, cursor, user, context=None):
        return 'dummy'

    def default_join_mode(self, cursor, user, context=None):
        return 'XOR'

    def default_split_mode(self, cursor, user, context=None):
        return 'XOR'

    def default_flow_start(self, cursor, user, context=None):
        return False

    def default_flow_stop(self, cursor, user, context=None):
        return False

WorkflowActivity()


class WorkflowTransition(ModelSQL, ModelView):
    "Workflow transition"
    _table = "wkf_transition"
    _name = "workflow.transition"
    _rec_name = 'signal'
    _description = __doc__
    trigger_model = fields.Char('Trigger Type')
    trigger_expr_id = fields.Char('Trigger Expr ID')
    signal = fields.Char('Signal (button Name)')
    group = fields.Many2One('res.group', 'Group Required')
    condition = fields.Char('Condition', required=True)
    act_from = fields.Many2One('workflow.activity', 'Source Activity',
       required=True, select=1, ondelete='CASCADE')
    act_to = fields.Many2One('workflow.activity', 'Destination Activity',
       required=True, select=1, ondelete='CASCADE')
    instances = fields.Many2Many('workflow.transition-workflow.instance',
            'trans_id', 'inst_id', 'Instances')

    def default_condition(self, cursor, user, context=None):
        return 'True'

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

    def init(self, cursor, module_name):
        super(WorkflowInstance, self).init(cursor, module_name)

        table = TableHandler(cursor, self, module_name)
        table.index_action(['res_id', 'res_type', 'state'], 'add')
        table.index_action(['res_id', 'workflow'], 'add')

    def fields_get(self, cursor, user, fields_names=None, context=None):
        res = super(WorkflowInstance, self).fields_get(cursor, user,
                fields_names=fields_names, context=context)
        for field in res:
            res[field]['readonly'] = True
        return res

    def create(self, cursor, user, values, context=None):
        activity_obj = self.pool.get('workflow.activity')
        workitem_obj = self.pool.get('workflow.workitem')

        instance_id = super(WorkflowInstance, self).create(cursor, user, values,
                context=context)

        if 'workflow' in values:
            activity_ids = activity_obj.search(cursor, 0, [
                ('flow_start', '=', True),
                ('workflow', '=', values['workflow']),
                ], context=context)
            for activity_id in activity_ids:
                workitem_obj.create(cursor, user, {
                    'activity': activity_id,
                    'instance': instance_id,
                    'state': 'active',
                    }, context=context)
        instance = self.browse(cursor, user, instance_id, context=context)
        self.update(cursor, user, instance, context=context)
        return instance_id

    def update(self, cursor, user, instance, context=None):
        '''
        '''
        workitem_obj = self.pool.get('workflow.workitem')
        for workitem in instance.workitems:
            workitem_obj.process(cursor, user, workitem, context=context)
        instance = self.browse(cursor, user, instance.id, context=context)
        return self._update_end(cursor, user, instance, context=context)

    def validate(self, cursor, user, instance, signal, force_running=False,
            context=None):
        '''
        '''
        workitem_obj = self.pool.get('workflow.workitem')
        for workitem in instance.workitems:
            workitem_obj.process(cursor, user, workitem, signal=signal,
                    force_running=force_running, context=context)
        instance = self.browse(cursor, user, instance.id, context=context)
        return self._update_end(cursor, user, instance, context=context)

    def _update_end(self, cursor, user, instance, context=None):
        workitem_obj = self.pool.get('workflow.workitem')
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
            self.write(cursor, 0, instance.id, {
                'state': 'complete',
                }, context=context)
            workitem_ids = workitem_obj.search(cursor, 0, [
                ('subflow', '=', instance.id),
                ], context=context)
            workitem_obj.write(cursor, 0, workitem_ids, {
                'state': 'complete',
                }, context=context)
            for workitem in workitem_obj.browse(cursor, user,
                    workitem_ids, context=context):
                for act_name in act_names:
                    self.validate(cursor, user, workitem.instance,
                            signal='subflow.' + act_name, context=context)
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

    def fields_get(self, cursor, user, fields_names=None, context=None):
        res = super(WorkflowTransitionInstance, self).fields_get(cursor, user,
                fields_names=fields_names, context=context)
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

    def fields_get(self, cursor, user, fields_names=None, context=None):
        res = super(WorkflowWorkitem, self).fields_get(cursor, user,
                fields_names=fields_names, context=context)
        for field in res:
            res[field]['readonly'] = True
        return res

    def create(self, cursor, user, values, context=None):
        workitem_id = super(WorkflowWorkitem, self).create(cursor, user, values,
                context=context)
        workitem = self.browse(cursor, 0, workitem_id, context=context)
        self.process(cursor, user, workitem, context=context)
        return workitem_id

    def process(self, cursor, user, workitem, signal=None, force_running=False,
            context=None):
        '''
        Process a workitem

        :param cursor: the database cursor
        :param user: the user id
        :param workitem: a BrowseRecord of the workflow.workitem
        :param signal: the signal
        :param force_running: a boolean
        :param context: the context
        '''
        trigger_obj = self.pool.get('workflow.trigger')
        activity = workitem.activity
        triggers = False
        if workitem.state == 'active':
            triggers = True
            if not self._execute(cursor, user, workitem, activity,
                    context=context):
                return False
        elif workitem.state == 'running':
            pass

        if workitem.state == 'complete' or force_running:
            res = self._split_test(cursor, user, workitem, activity.split_mode,
                    signal, context=context)
            triggers = triggers and not res

        if triggers:
            for transition in activity.out_transitions:
                if transition.trigger_model:
                    ids = expr.eval_expr(cursor, user,
                            workitem.instance.res_type,
                            workitem.instance.res_id,
                            transition.trigger_expr_id, context=context)
                    for res_id in ids:
                        trigger_obj.create(cursor, 0, {
                            'model': transition.trigger_model,
                            'res_id': res_id,
                            'instance': workitem.instance.id,
                            'workitem': workitem.id,
                            }, context=context)
        return True

    def _state_set(self, cursor, user, workitem, state):
        self.write(cursor, user, workitem.id, {
            'state': state,
            })
        #XXX must be changed with a cache reset on BrowseRecord
        workitem._data[workitem.id]['state'] = state

    def _execute(self, cursor, user, workitem, activity, context=None):
        instance_obj = self.pool.get('workflow.instance')
        #send a signal to overflow
        if (workitem.state == 'active') and activity.signal_send:
            for overflow in workitem.overflows:
                instance_obj.validate(cursor, user, overflow.instance,
                        activity.signal_send, force_running=True,
                        context=context)

        if activity.kind == 'dummy':
            if workitem.state == 'active':
                self._state_set(cursor, user, workitem, 'complete')
        elif activity.kind == 'function':
            if workitem.state == 'active':
                self._state_set(cursor, user, workitem, 'running')
                expr.execute(cursor, user, workitem.instance.res_type,
                        workitem.instance.res_id, activity,
                        context=context)
                self._state_set(cursor, user, workitem, 'complete')
        elif activity.kind == 'stopall':
            if workitem.state == 'active':
                self._state_set(cursor, user, workitem, 'running')
                #XXX check if delete must not be replace by _state_set 'complete'
                self.delete(cursor, 0,
                        self.search(cursor, user, [
                            ('instance', '=', workitem.instance.id),
                            ('id', '!=', workitem.id),
                            ], context=context), context=context)
                if activity.action:
                    expr.execute(cursor, user, workitem.instance.res_type,
                            workitem.instance.res_id, activity,
                            context=context)
                self._state_set(cursor, user, workitem, 'complete')
        elif activity.kind == 'subflow':
            if workitem.state == 'active':
                self._state_set(cursor, workitem, 'running')
                if activity.action:
                    id_new = expr.execute(cursor, user,
                            workitem.instance.res_type,
                            workitem.instance.res_id, activity,
                            context=context)
                    if not id_new:
                        self.delete(cursor, 0, workitem.id, context=context)
                        return False
                    instance_id = instance_obj.search(cursor, 0, [
                        ('res_id', '=', id_new),
                        ('workflow', '=', activity.subflow.id),
                        ], limit=1, context=context)[0]
                else:
                    instance_id = instance_obj.create(cursor, user, {
                        'res_type': workitem.instance.res_type,
                        'res_id': workitem.instance.res_id,
                        'workflow': activity.subflow.id,
                        }, context=context)
                self.write(cursor, user, workitem.id, {
                    'subflow': instance_id,
                    }, context=context)
                #XXX must be changed with a cache reset on BrowseRecord
                workitem._data[workitem.id]['subflow'] = instance_id
            elif workitem.state == 'running':
                if workitem.subflow.state == 'complete':
                    self._state_set(cursor, user, workitem, 'complete')
        return True

    def _split_test(self, cursor, user, workitem, split_mode, signal=None,
            context=None):
        instance_obj = self.pool.get('workflow.instance')
        test = False
        transitions = []
        if split_mode == 'XOR' or split_mode == 'OR':
            for transition in workitem.activity.out_transitions:
                if expr.check(cursor, user, workitem.instance.res_type,
                        workitem.instance.res_id, transition, signal,
                        context=context):
                    test = True
                    transitions.append(transition)
                    if split_mode == 'XOR':
                        break
        else:
            test = True
            for transition in workitem.activity.out_transitions:
                if not expr.check(cursor, user, workitem.instance.res_type,
                        workitem.instance.res_id, transition, signal,
                        context=context):
                    test = False
                    break
                if transition.id not in \
                        [x.id for x in workitem.instance.transitions]:
                    transitions.append(transition)
        if test and len(transitions):
            instance_obj.write(cursor, 0, workitem.instance.id, {
                'transitions': [('add', [x.id for x in transitions])],
                }, context=context)
            instance = workitem.instance
            self.delete(cursor, 0, workitem.id, context=context)
            for transition in transitions:
                self._join_test(cursor, user, transition, instance,
                        context=context)
            return True
        return False

    def _join_test(self, cursor, user, transition, instance, context=None):
        instance_obj = self.pool.get('workflow.instance')
        activity = transition.act_to
        if activity.join_mode == 'XOR':
            self.create(cursor, user, {
                'activity': activity.id,
                'instance': instance.id,
                'state': 'active',
                }, context=context)
            instance_obj.write(cursor, 0, instance.id, {
                'transitions': [('unlink', transition.id)],
                }, context=context)
        else:
            delete = True
            for transition in activity.in_transitions:
                if instance.id not in \
                        [x.id for x in transition.instances]:
                    delete = False
                    break
            if delete:
                instance_obj.write(cursor, 0, instance.id, {
                    'transitions': [('unlink', [x.id
                        for x in activity.in_transitions])],
                    }, context=context)
                self.create(cursor, user, {
                    'activity': activity.id,
                    'instance': instance.id,
                    'state': 'active',
                    }, context=context)

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

    def init(self, cursor, module_name):
        super(WorkflowTrigger, self).init(cursor, module_name)

        table = TableHandler(cursor, self, module_name)
        table.index_action(['res_id', 'model'], 'add')

    def fields_get(self, cursor, user, fields_names=None, context=None):
        res = super(WorkflowTrigger, self).fields_get(cursor, user,
                fields_names=fields_names, context=context)
        for field in res:
            res[field]['readonly'] = True
        return res

WorkflowTrigger()


class InstanceGraph(Report):
    _name = 'workflow.instance.graph'

    def execute(self, cursor, user, ids, datas, context=None):
        import pydot
        lang_obj = self.pool.get('ir.lang')
        workflow_obj = self.pool.get('workflow')
        instance_obj = self.pool.get('workflow.instance')

        if context is None:
            context = {}

        lang_id = lang_obj.search(cursor, user, [
            ('code', '=', context.get('language', 'en_US')),
            ], limit=1, context=context)[0]
        lang = lang_obj.browse(cursor, user, lang_id, context=context)

        workflow_id = workflow_obj.search(cursor, user, [
            ('model', '=', datas['model']),
            ], limit=1, context=context)
        if not workflow_id:
            workflow_obj.raise_user_error(cursor, 'no_workflow_defined',
                    context=context)
        workflow_id = workflow_id[0]
        workflow = workflow_obj.browse(cursor, user, workflow_id,
                context=context)
        instance_id = instance_obj.search(cursor, user, [
            ('res_id', '=', datas['id']),
            ('workflow', '=', workflow.id),
            ], order=[('id', 'DESC')], limit=1, context=context)
        if not instance_id:
            instance_obj.raise_user_error(cursor, 'no_instance_defined',
                    context=context)
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
        self.graph_instance_get(cursor, user, graph, instance_id,
                datas.get('nested', False), context=context)
        data = graph.create(prog='dot', format='png')
        return ('png', base64.encodestring(data), False, workflow.name)

    def graph_instance_get(self, cursor, user, graph, instance_id, nested=False,
            context=None):
        instance_obj = self.pool.get('workflow.instance')
        instance = instance_obj.browse(cursor, user, instance_id,
                context=context)
        self.graph_get(cursor, user, graph, instance.workflow.id, nested,
                self.workitem_get(cursor, user, instance.id, context=context),
                context=context)

    def workitem_get(self, cursor, user, instance_id, context=None):
        res = {}
        workitem_obj = self.pool.get('workflow.workitem')
        workitem_ids = workitem_obj.search(cursor, user, [
            ('instance', '=', instance_id),
            ], context=context)
        workitems = workitem_obj.browse(cursor, user, workitem_ids,
                context=context)
        for workitem in workitems:
            res.setdefault(workitem.activity.id, 0)
            res[workitem.activity.id] += 1
            if workitem.subflow:
                res.update(self.workitem_get(cursor, user,
                    workitem.subflow.id, context=context))
        return res

    def graph_get(self, cursor, user, graph, workflow_id, nested=False,
            workitem=None, context=None):
        import pydot
        if workitem is None:
            workitem = {}
        activity_obj = self.pool.get('workflow.activity')
        workflow_obj = self.pool.get('workflow')
        transition_obj = self.pool.get('workflow.transition')
        activity_ids = activity_obj.search(cursor, user, [
            ('workflow', '=', workflow_id),
            ], context=context)
        id2activities = {}
        actfrom = {}
        actto = {}
        activities = activity_obj.browse(cursor, user, activity_ids,
                context=context)
        start = 0
        stop = {}
        for activity in activities:
            if activity.flow_start:
                start = activity.id
            if activity.flow_stop:
                stop['subflow.' + activity.name] =  activity.id
            id2activities[activity.id] = activity
            if activity.subflow and nested:
                workflow = workflow_obj.browse(cursor, user,
                        activity.subflow.id, context=context)
                subgraph = pydot.Cluster('subflow' + str(workflow.id),
                        fontsize='12',
                        label="Subflow: " + activity.name.encode('ascii', 'replace'))
                (substart, substop) = self.graph_get(cursor, user,
                        subgraph, workflow.id, nested, workitem,
                        context=context)
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
        transition_ids = transition_obj.search(cursor, user, [
            ('act_from', 'in', [x.id for x in activities]),
            ], context=context)
        transitions = transition_obj.browse(cursor, user, transition_ids,
                context=context)
        for transition in transitions:
            args = {}
            args['label'] = ' '
            if transition.condition != 'True':
                args['label'] += str(transition.condition).replace(' or ',
                        '\\nor ').replace(' and ', '\\nand ')
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
