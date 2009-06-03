#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Project"
from trytond.model import ModelView, ModelSQL, fields
from trytond.model.modelstorage import OPERATORS
import copy


class TimesheetWork(ModelSQL, ModelView):
    _name = 'timesheet.work'

    timesheet_lines = fields.One2Many('timesheet.line', 'work',
            'Timesheet Lines',
            depends=['timesheet_available', 'active'],
            states={
                'invisible': 'not bool(timesheet_available)',
                'readonly': '''not active'''
            })
    sequence = fields.Integer('Sequence')

    def __init__(self):
        super(TimesheetWork, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

        self.parent = copy.copy(self.parent)
        if not self.parent.context:
            self.parent.context = "{'type': locals().get('type')}"
        elif 'type' not in self.parent.context:
            sep = ''
            if self.parent.context[-2] != ',':
                sep = ','
            self.parent.context = self.parent.context[:-1] + \
                    sep + "'type': locals().get('type')" + \
                    self.parent.context[-1:]

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
                'invisible': 'context.get("type", False)',
            })
    party = fields.Many2One('party.party', 'Party',
            states={
                'invisible': "type!= 'project'"
            }, depends=['type'])
    party_address = fields.Many2One('party.address', 'Contact Address',
            domain="["\
                "('party', '=', party)"\
            "]",
            states={
                'invisible': "type != 'project'"
            }, depends=['party', 'type'])
    effort = fields.Float("Effort",
            states={
                'invisible': "type != 'task'"
            }, depends=['type'], help="Estimated Effort for this work")
    total_effort = fields.Function('get_total_effort', type='float',
            string='Total Effort',
            states={
                'invisible': "type != 'project'"
            }, depends=['type'],
            help="Estimated total effort for this work and the sub-works")
    comment = fields.Text('Comment')
    parent = fields.Function('get_parent', fnct_inv='set_parent',
            fnct_search='search_parent', string='Parent',
            relation='project.work', type="many2one")
    children = fields.One2Many('project.work', 'parent', 'Children')
    state = fields.Selection([
            ('opened', 'Opened'),
            ('done', 'Done'),
            ], 'State',
            states={
                'invisible': "type != 'task'",
                'required': "type == 'task'",
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

    def get_parent(self, cursor, user, ids, name, arg, context=None):
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

    def set_parent(self, cursor, user, id, name, value, arg, context=None):
        timesheet_work_obj = self.pool.get('timesheet.work')
        if value:
            child_project_work, parent_project_work = self.browse(
                cursor, user, [id, value], context=context)
            child_timesheet_work_id = child_project_work.work.id
            parent_timesheet_work_id = parent_project_work.work.id
        else:
            child_project_work = self.browse( cursor, user, id, context=context)
            child_timesheet_work_id = child_project_work.work.id
            parent_timesheet_work_id = False

        timesheet_work_obj.write(cursor, user, child_timesheet_work_id, {
                'parent': parent_timesheet_work_id
                },
                context=context)

    def search_parent(self, cursor, user, name, domain=None, context=None):
        timesheet_work_obj = self.pool.get('timesheet.work')

        project_work_domain = []
        timesheet_work_domain = []
        for field, operator, operand in domain:
            if field.startswith('parent.'):
                project_work_domain.append(
                    (field.replace('parent.', ''), operator, operand))
            elif field == 'parent':
                timesheet_work_domain.append(
                    (field, operator, operand))

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

    def get_total_effort(self, cursor, user, ids, name, arg, context=None):
        timesheet_work_obj = self.pool.get('timesheet.work')

        projects = self.browse(cursor, user, ids, context=context)
        w2p = dict((p.work.id, p.id) for p in projects)

        ctx = context and context.copy() or {}
        ctx['active_test'] = False
        query_ids, args_ids = timesheet_work_obj.search(cursor, user, [
            ('parent', 'child_of', w2p.keys()),
            ], context=ctx, query_string=True)

        cursor.execute(
                'SELECT task.work, ' \
                    'SUM(CASE WHEN task.type = \'task\' '\
                            'AND task.effort is not null '\
                        'THEN task.effort '\
                        'ELSE 0 END) '\
                'FROM project_work task ' \
                'WHERE task.work IN (' + query_ids + ') ' \
                'GROUP BY task.work', args_ids)
        work_effort = dict(cursor.fetchall())

        works = timesheet_work_obj.browse(
            cursor, user, work_effort.keys(), context=context)
        id2work = {}
        leafs = set()
        for work in works:
            id2work[work.id] = work
            if not work.children:
                leafs.add(work.id)

        while leafs:
            parents = set()
            for work_id in leafs:
                if not work.active:
                    continue
                work = id2work[work_id]
                if work.parent and work.parent.id in work_effort:
                    work_effort[work.parent.id] += work_effort[work_id]
                    parents.add(work.parent.id)
            leafs = parents

        return dict((w2p[w], e) for w,e in work_effort.iteritems() if w in w2p)


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
