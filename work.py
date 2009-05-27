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
            }, depends=['type'])
    total_effort = fields.Function('get_total_effort', type='float',
            string='Total Effort',
            states={
                'invisible': "type != 'project'"
            }, depends=['type'])
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

        # ptw2pw is "parent timesheet work to project work":
        ptw2pw = {}
        for project_work in project_works:
            ptw2pw[project_work.work.parent.id] = project_work.id

        ctx = context and context.copy() or {}
        ctx['active_test'] = False
        parent_project_ids = self.search(cursor, user, [
                ('work', 'in', ptw2pw.keys()),
                ], context=ctx)
        parent_projects = self.browse(cursor, user, parent_project_ids,
                context=context)
        for parent_project in parent_projects:
            if parent_project.work.id in ptw2pw:
                res[ptw2pw[parent_project.work.id]] = parent_project.id

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
        ids = domain[0][2]
        clauses = []
        args = []
        for d in domain:
            if d[1] in ('in', 'not in'):
                clause = 'parent.id ' + d[1] + \
                    '(' + ','.join('%s' for i in d[2]) + ')'
                clauses.append(clause)
                args.extend(d[2])

            elif d[1] in ('child_of', 'not child_of'):
                raise Exception('Domain not implemented')

            elif d[1] in ('=', '!=') and not d[2]:
                op = d[1] == '=' and 'is' or 'is not'
                clauses.append('twc.parent %s null' % op)

            elif d[1] in OPERATORS:
                clauses.append('parent.id %s %%s' % d[1])
                args.append(d[2])

        query = \
            'SELECT child.id '\
            'FROM project_work child '\
                'JOIN timesheet_work twc on (twc.id = child.work) '\
                'LEFT JOIN timesheet_work twp on (twc.parent = twp.id) '\
                'LEFT JOIN project_work parent on (twp.id = parent.work) '

        if clauses:
            query = query + 'WHERE ' + ' AND '.join(clauses)

        cursor.execute(query, args)

        res = [('id', 'in', [x[0] for x in cursor.fetchall()])]
        return res

    def get_total_effort(self, cursor, user, ids, name, arg, context=None):
        timesheet_work_obj = self.pool.get('timesheet.work')

        projects = self.browse(cursor, user, ids, context=context)
        w2p = dict((p.work.id, p.id) for p in projects)

        query_ids, args_ids = timesheet_work_obj.search(cursor, user, [
            ('parent', 'child_of', w2p.keys()),
            ], context=context, query_string=True)

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

