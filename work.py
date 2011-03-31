#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Project"
from trytond.model import ModelView, ModelSQL, fields
from trytond.model.modelstorage import OPERATORS
from trytond.pyson import Not, Bool, Eval, Get, Equal
import copy


class TimesheetWork(ModelSQL, ModelView):
    _name = 'timesheet.work'

    timesheet_lines = fields.One2Many('timesheet.line', 'work',
            'Timesheet Lines',
            depends=['timesheet_available', 'active'],
            states={
                'invisible': Not(Bool(Eval('timesheet_available'))),
                'readonly': Not(Bool(Eval('active'))),
            })
    sequence = fields.Integer('Sequence')

    def __init__(self):
        super(TimesheetWork, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

        self.parent = copy.copy(self.parent)
        self.parent.context = copy.copy(self.parent.context)
        self.parent.context['type'] = Eval('type')
        self._reset_columns()

TimesheetWork()


class Work(ModelSQL, ModelView):
    'Work Effort'
    _name = 'project.work'
    _description = __doc__
    _inherits = {'timesheet.work': 'work'}

    work = fields.Many2One('timesheet.work', 'Work', required=True,
            ondelete='CASCADE')
    type = fields.Selection([
            ('project', 'Project'),
            ('task', 'Task')
            ],
            'Type', required=True, select=1,
            states={
                'invisible': Get(Eval('context', {}), 'type', False),
            })
    party = fields.Many2One('party.party', 'Party',
            states={
                'invisible': Not(Equal(Eval('type'), 'project')),
            }, depends=['type'])
    party_address = fields.Many2One('party.address', 'Contact Address',
            domain=[('party', '=', Eval('party'))],
            states={
                'invisible': Not(Equal(Eval('type'), 'project')),
            }, depends=['party', 'type'])
    effort = fields.Float("Effort",
            states={
                'invisible': Not(Equal(Eval('type'), 'task')),
            }, depends=['type'], help="Estimated Effort for this work")
    total_effort = fields.Function(fields.Float('Total Effort',
        help="Estimated total effort for this work and the sub-works"),
        'get_total_effort')
    comment = fields.Text('Comment')
    parent = fields.Function(fields.Many2One('project.work', 'Parent'),
            'get_parent', setter='set_parent', searcher='search_parent')
    children = fields.One2Many('project.work', 'parent', 'Children')
    state = fields.Selection([
            ('opened', 'Opened'),
            ('done', 'Done'),
            ], 'State',
            states={
                'invisible': Not(Equal(Eval('type'), 'task')),
                'required': Equal(Eval('type'), 'task'),
            }, select=1, depends=['type'])

    def default_type(self, cursor, user, context=None):
        if context.get('type') == 'project':
            return 'project'
        return 'task'

    def default_state(self, cursor, user, context=None):
        return 'opened'

    def __init__(self):
        super(Work, self).__init__()
        self._sql_constraints += [
            ('work_uniq', 'UNIQUE(work)', 'There should be only one '\
                 'timesheet work by task/project!'),
        ]
        self._order.insert(0, ('sequence', 'ASC'))
        if 'company' in self._inherit_fields:
            company_field = copy.copy(
                self._inherit_fields['company'])
            company_field[2].states = copy.copy(company_field[2].states)
            company_field[2].states.update({
                'invisible': Bool(Get(Eval('context', {}), 'type')),
                'readonly': Not(Bool(Eval('active'))),
            })

            self._inherit_fields['company'] = company_field

    def get_parent(self, cursor, user, ids, name, context=None):
        res = dict.fromkeys(ids, None)
        project_works = self.browse(cursor, user, ids, context=context)

        # ptw2pw is "parent timesheet work to project works":
        ptw2pw = {}
        for project_work in project_works:
            if project_work.work.parent.id in ptw2pw:
                ptw2pw[project_work.work.parent.id].append(project_work.id)
            else:
                ptw2pw[project_work.work.parent.id] = [project_work.id]

        ctx = context and context.copy() or {}
        ctx['active_test'] = False
        parent_project_ids = self.search(cursor, user, [
                ('work', 'in', ptw2pw.keys()),
                ], context=ctx)
        parent_projects = self.browse(cursor, user, parent_project_ids,
                context=context)
        for parent_project in parent_projects:
            if parent_project.work.id in ptw2pw:
                child_projects = ptw2pw[parent_project.work.id]
                for child_project in child_projects:
                    res[child_project] = parent_project.id

        return res

    def set_parent(self, cursor, user, ids, name, value, context=None):
        timesheet_work_obj = self.pool.get('timesheet.work')
        if value:
            project_works = self.browse( cursor, user, ids + [value],
                    context=context)
            child_timesheet_work_ids = [x.work.id for x in project_works[:-1]]
            parent_timesheet_work_id = project_works[-1].work.id
        else:
            child_project_works = self.browse( cursor, user, ids, context=context)
            child_timesheet_work_ids = [x.work.id for x in child_project_works]
            parent_timesheet_work_id = False

        timesheet_work_obj.write(cursor, user, child_timesheet_work_ids, {
                'parent': parent_timesheet_work_id
                },
                context=context)

    def search_parent(self, cursor, user, name, domain=None, context=None):
        timesheet_work_obj = self.pool.get('timesheet.work')

        project_work_domain = []
        timesheet_work_domain = []
        if domain[0].startswith('parent.'):
            project_work_domain.append(
                    (domain[0].replace('parent.', ''),)
                    + domain[1:])
        elif domain[0] == 'parent':
            timesheet_work_domain.append(domain)

        # ids timesheet_work_domain in operand are project_work ids,
        # we need to convert them to timesheet_work ids
        operands = set()
        for _, _, operand in timesheet_work_domain:
            if isinstance(operand, (int, long)) and not isinstance(operand, bool):
                operands.add(operand)
            elif isinstance(operand, list):
                for o in operand:
                    if isinstance(o, (int, long)) and not isinstance(o, bool):
                        operands.add(o)
        pw2tw = {}
        if operands:
            operands = list(operands)
            # filter out non-existing ids:
            operands = self.search(cursor, user, [
                    ('id', 'in', operands)
                    ], context=context)
            # create project_work > timesheet_work mapping
            for pw in self.browse(cursor, user, operands, context=context):
                pw2tw[pw.id] = pw.work.id

            for i, d in enumerate(timesheet_work_domain):
                if isinstance(d[2], (int, long)):
                    new_d2 = pw2tw.get(d[2], 0)
                elif isinstance(d[2], list):
                    new_d2 = []
                    for item in d[2]:
                        item = pw2tw.get(item, 0)
                        new_d2.append(item)
                timesheet_work_domain[i] = (d[0], d[1], new_d2)

        if project_work_domain:
            pw_ids = self.search(
                cursor, user, project_work_domain, context=context)
            project_works = self.browse(cursor, user, pw_ids, context=context)
            timesheet_work_domain.append(
                ('id', 'in', [pw.work.id for pw in project_works]))

        tw_ids = timesheet_work_obj.search(
            cursor, user, timesheet_work_domain, context=context)

        return [('work', 'in', tw_ids)]

    def get_total_effort(self, cursor, user, ids, name, context=None):

        all_ids = self.search(cursor, user, [
                ('parent', 'child_of', ids),
                ('active', '=', True)], context=context) + ids
        all_ids = list(set(all_ids))

        works = self.browse(cursor, user, all_ids, context=context)

        res = {}
        id2work = {}
        leafs = set()
        for work in works:
            res[work.id] = work.effort
            id2work[work.id] = work
            if not work.children:
                leafs.add(work.id)

        while leafs:
            parents = set()
            for work_id in leafs:
                work = id2work[work_id]
                if not work.active:
                    continue
                if work.parent and work.parent.id in res:
                    res[work.parent.id] += res[work_id]
                    parents.add(work.parent.id)
            leafs = parents

        return res


    def delete(self, cursor, user, ids, context=None):
        timesheet_work_obj = self.pool.get('timesheet.work')

        if isinstance(ids, (int, long)):
            ids = [ids]

        # Get the timesheet works linked to the project works
        project_works = self.browse(cursor, user, ids, context=context)
        timesheet_work_ids = [pw.work.id for pw in project_works]

        res = super(Work, self).delete(cursor, user, ids, context=context)

        timesheet_work_obj.delete(
            cursor, user, timesheet_work_ids, context=context)
        return res


Work()
