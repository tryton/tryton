#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval
from trytond.backend import TableHandler
from trytond.transaction import Transaction
from trytond.pool import Pool


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
        'Type', required=True, select=True)
    party = fields.Many2One('party.party', 'Party',
        states={
            'invisible': Eval('type') != 'project',
            }, depends=['type'])
    party_address = fields.Many2One('party.address', 'Contact Address',
        domain=[('party', '=', Eval('party'))],
        states={
            'invisible': Eval('type') != 'project',
            }, depends=['party', 'type'])
    effort = fields.Float("Effort",
        states={
            'invisible': Eval('type') != 'task',
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
            ], 'State', required=True, select=True)
    sequence = fields.Integer('Sequence', required=True)

    def default_type(self):
        return 'task'

    def default_state(self):
        return 'opened'

    def default_effort(self):
        return 0.0

    def init(self, module_name):
        timesheet_work_obj = Pool().get('timesheet.work')
        cursor = Transaction().cursor
        table_project_work = TableHandler(cursor, self, module_name)
        table_timesheet_work = TableHandler(cursor, timesheet_work_obj,
            module_name)
        migrate_sequence = (not table_project_work.column_exist('sequence')
            and table_timesheet_work.column_exist('sequence'))

        super(Work, self).init(module_name)

        # Migration from 2.0: copy sequence from timesheet to project
        if migrate_sequence:
            cursor.execute(
                'SELECT t.sequence, t.id '
                'FROM "%s" AS t '
                'JOIN "%s" AS p ON (p.work = t.id)' % (
                    timesheet_work_obj._table, self._table))
            for sequence, id_ in cursor.fetchall():
                sql = ('UPDATE "%s" '
                        'SET sequence = %%s '
                        'WHERE work = %%s' % self._table)
                cursor.execute(sql, (sequence, id_))

    def __init__(self):
        super(Work, self).__init__()
        self._sql_constraints += [
            ('work_uniq', 'UNIQUE(work)', 'There should be only one '\
                 'timesheet work by task/project!'),
        ]
        self._order.insert(0, ('sequence', 'ASC'))
        self._constraints += [
            ('check_state',
                'A work can not be closed if its children are still opened'),
            ]

    def check_state(self, ids):
        for work in self.browse(ids):
            if ((work.state == 'opened'
                        and (work.parent and work.parent.state == 'done'))
                    or (work.state == 'done'
                        and any(c.state == 'opened' for c in work.children))):
                return False
        return True

    def get_parent(self, ids, name):
        res = dict.fromkeys(ids, None)
        project_works = self.browse(ids)

        # ptw2pw is "parent timesheet work to project works":
        ptw2pw = {}
        for project_work in project_works:
            if project_work.work.parent.id in ptw2pw:
                ptw2pw[project_work.work.parent.id].append(project_work.id)
            else:
                ptw2pw[project_work.work.parent.id] = [project_work.id]

        with Transaction().set_context(active_test=False):
            parent_project_ids = self.search([
                    ('work', 'in', ptw2pw.keys()),
                    ])
        parent_projects = self.browse(parent_project_ids)
        for parent_project in parent_projects:
            if parent_project.work.id in ptw2pw:
                child_projects = ptw2pw[parent_project.work.id]
                for child_project in child_projects:
                    res[child_project] = parent_project.id

        return res

    def set_parent(self, ids, name, value):
        timesheet_work_obj = Pool().get('timesheet.work')
        if value:
            project_works = self.browse(ids + [value])
            child_timesheet_work_ids = [x.work.id for x in project_works[:-1]]
            parent_timesheet_work_id = project_works[-1].work.id
        else:
            child_project_works = self.browse(ids)
            child_timesheet_work_ids = [x.work.id for x in child_project_works]
            parent_timesheet_work_id = None

        timesheet_work_obj.write(child_timesheet_work_ids, {
                'parent': parent_timesheet_work_id
                })

    def search_parent(self, name, domain=None):
        timesheet_work_obj = Pool().get('timesheet.work')

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
            if (isinstance(operand, (int, long))
                    and not isinstance(operand, bool)):
                operands.add(operand)
            elif isinstance(operand, list):
                for o in operand:
                    if isinstance(o, (int, long)) and not isinstance(o, bool):
                        operands.add(o)
        pw2tw = {}
        if operands:
            operands = list(operands)
            # filter out non-existing ids:
            operands = self.search([
                    ('id', 'in', operands)
                    ])
            # create project_work > timesheet_work mapping
            for pw in self.browse(operands):
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
            pw_ids = self.search(project_work_domain)
            project_works = self.browse(pw_ids)
            timesheet_work_domain.append(
                ('id', 'in', [pw.work.id for pw in project_works]))

        tw_ids = timesheet_work_obj.search(timesheet_work_domain)

        return [('work', 'in', tw_ids)]

    def get_total_effort(self, ids, name):

        all_ids = self.search([
                ('parent', 'child_of', ids),
                ('active', '=', True),
                ]) + ids
        all_ids = list(set(all_ids))

        works = self.browse(all_ids)

        res = {}
        id2work = {}
        leafs = set()
        for work in works:
            res[work.id] = work.effort or 0
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

    def copy(self, ids, default=None):
        timesheet_work_obj = Pool().get('timesheet.work')

        int_id = isinstance(ids, (int, long))
        if int_id:
            ids = [ids]

        if default is None:
            default = {}

        timesheet_default = default.copy()
        for key in timesheet_default.keys():
            if key in self._columns:
                del timesheet_default[key]
        new_ids = []
        for project_work in self.browse(ids):
            timesheet_work_id = timesheet_work_obj.copy(project_work.work.id,
                default=timesheet_default)
            pwdefault = default.copy()
            pwdefault['work'] = timesheet_work_id
            new_ids.append(super(Work, self).copy(project_work.id,
                default=pwdefault))
        if int_id:
            return new_ids[0]
        return new_ids

    def delete(self, ids):
        timesheet_work_obj = Pool().get('timesheet.work')

        if isinstance(ids, (int, long)):
            ids = [ids]

        # Get the timesheet works linked to the project works
        project_works = self.browse(ids)
        timesheet_work_ids = [pw.work.id for pw in project_works]

        res = super(Work, self).delete(ids)

        timesheet_work_obj.delete(timesheet_work_ids)
        return res


Work()
