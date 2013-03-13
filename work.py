#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
from collections import deque, defaultdict
from heapq import heappop, heappush

from trytond.model import ModelSQL, fields
from trytond.wizard import Wizard, StateTransition
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['Work', 'PredecessorSuccessor', 'Leveling']
__metaclass__ = PoolMeta


def intfloor(x):
    return int(round(x, 4))


class Work:
    __name__ = 'project.work'
    predecessors = fields.Many2Many('project.predecessor_successor',
        'successor', 'predecessor', 'Predecessors',
        domain=[
            ('parent', '=', Eval('parent')),
            ('id', '!=', Eval('id')),
            ],
        depends=['parent', 'id'])
    successors = fields.Many2Many('project.predecessor_successor',
        'predecessor', 'successor', 'Successors',
        domain=[
            ('parent', '=', Eval('parent')),
            ('id', '!=', Eval('id')),
            ],
        depends=['parent', 'id'])
    leveling_delay = fields.Float("Leveling Delay")
    back_leveling_delay = fields.Float("Back Leveling Delay")
    allocations = fields.One2Many('project.allocation', 'work', 'Allocations',
        states={
            'invisible': Eval('type') != 'task',
            }, depends=['type'])
    duration = fields.Function(fields.Float('Duration'), 'get_function_fields')
    early_start_time = fields.DateTime("Early Start Time", readonly=True)
    late_start_time = fields.DateTime("Late Start Time", readonly=True)
    early_finish_time = fields.DateTime("Early Finish Time", readonly=True)
    late_finish_time = fields.DateTime("Late Finish Time", readonly=True)
    actual_start_time = fields.DateTime("Actual Start Time")
    actual_finish_time = fields.DateTime("Actual Finish Time")
    constraint_start_time = fields.DateTime("Constraint Start Time")
    constraint_finish_time = fields.DateTime("Constraint  Finish Time")
    early_start_date = fields.Function(fields.Date('Early Start'),
            'get_function_fields')
    late_start_date = fields.Function(fields.Date('Late Start'),
            'get_function_fields')
    early_finish_date = fields.Function(fields.Date('Early Finish'),
            'get_function_fields')
    late_finish_date = fields.Function(fields.Date('Late Finish'),
            'get_function_fields')
    actual_start_date = fields.Function(fields.Date('Actual Start'),
            'get_function_fields', setter='set_function_fields')
    actual_finish_date = fields.Function(fields.Date('Actual Finish'),
            'get_function_fields', setter='set_function_fields')
    constraint_start_date = fields.Function(fields.Date('Constraint Start',
        depends=['type']), 'get_function_fields',
        setter='set_function_fields')
    constraint_finish_date = fields.Function(fields.Date('Constraint Finish',
        depends=['type']), 'get_function_fields',
        setter='set_function_fields')
    requests = fields.Function(fields.One2Many('res.request', None,
        'Requests'), 'get_function_fields', setter='set_function_fields')

    @classmethod
    def __setup__(cls):
        super(Work, cls).__setup__()

    @classmethod
    def validate(cls, works):
        super(Work, cls).validate(works)
        cls.check_recursion(works)

    @classmethod
    def check_recursion(cls, records, parent='successors'):
        return super(Work, cls).check_recursion(records, parent=parent)

    @classmethod
    def get_function_fields(cls, works, names):
        '''
        Function to compute function fields
        '''
        RequestReference = Pool().get('res.request.reference')

        cursor = Transaction().cursor

        res = {}

        ids = [w.id for w in works]
        if 'requests' in names:
            requests = dict((i, []) for i in ids)

            for i in range(0, len(ids), cursor.IN_MAX):
                sub_ids = ids[i:i + cursor.IN_MAX]

                req_refs = RequestReference.search([
                        ('reference', 'in', [
                                'project.work,%s' % i for i in sub_ids
                                ]
                         ),
                        ])
                for req_ref in req_refs:
                    work_id = req_ref.reference.id
                    requests[work_id].append(req_ref.request.id)

            res['requests'] = requests

        if 'duration' in names:
            all_works = cls.search([
                    ('parent', 'child_of', ids),
                    ('active', '=', True)]) + works
            all_works = set(all_works)

            durations = {}
            id2work = {}
            leafs = set()
            for work in all_works:
                id2work[work.id] = work
                if not work.children:
                    leafs.add(work.id)

                total_allocation = 0
                if not work.allocations:
                    durations[work.id] = work.effort
                    continue
                for allocation in work.allocations:
                    total_allocation += allocation.percentage
                durations[work.id] = work.effort / (total_allocation / 100.0)

            while leafs:
                for work_id in leafs:
                    work = id2work[work_id]
                    all_works.remove(work)
                    if not work.active:
                        continue
                    if work.parent and work.parent.id in durations:
                        durations[work.parent.id] += durations[work_id]
                next_leafs = set(w.id for w in all_works)
                for work in all_works:
                    if not work.parent:
                        continue
                    if work.parent.id in next_leafs and work.parent in works:
                        next_leafs.remove(work.parent.id)
                leafs = next_leafs
            res['duration'] = durations

        fun_fields = ('early_start_date', 'early_finish_date',
                      'late_start_date', 'late_finish_date',
                      'actual_start_date', 'actual_finish_date',
                      'constraint_start_date', 'constraint_finish_date')
        db_fields = ('early_start_time', 'early_finish_time',
                  'late_start_time', 'late_finish_time',
                  'actual_start_time', 'actual_finish_time',
                  'constraint_start_time', 'constraint_finish_time')

        for fun_field, db_field in zip(fun_fields, db_fields):
            if fun_field in names:
                values = {}
                for work in works:
                    values[work.id] = getattr(work, db_field) \
                        and getattr(work, db_field).date() or None
                res[fun_field] = values

        return res

    @classmethod
    def set_function_fields(cls, works, name, value):
        pool = Pool()
        Request = pool.get('res.request')
        RequestReference = pool.get('res.request.reference')

        if name == 'requests':
            currents = dict((req.id, req) for work in works for req in
                    work.requests)
            if not value:
                return
            for v in value:
                to_unlink = []
                to_link = []
                operator = v[0]

                target_ids = len(v) > 1 and v[1] or []
                if operator == 'create':
                    request, = Request.create(v[1])
                    to_link.append(request.id)
                elif operator == 'write':
                    Request.write([Request(v[1])], v[2])
                elif operator == 'delete':
                    Request.delete([Request(v[1])])
                elif operator == 'delete_all':
                    target_ids = []
                    for work in works:
                        refs = RequestReference.search([
                                ('reference', '=', str(work)),
                                ])
                        target_ids.extend(ref.request.id for ref in refs)
                    Request.delete(Request.browse(target_ids))
                elif operator == 'unlink':
                    to_unlink.extend((i for i in target_ids if i in currents))
                elif operator == 'add':
                    to_link.extend((i for i in target_ids if i not in
                        currents))
                elif operator == 'unlink_all':
                    to_unlink.extend(currents)
                elif operator == 'set':
                    to_link.extend((i for i in target_ids
                        if i not in currents))
                    to_unlink.extend((i for i in currents
                        if i not in target_ids))
                else:
                    raise Exception('Operation not supported')

                req_refs = []
                for i in to_unlink:
                    request = currents[i]
                    for ref in request.references:
                        if ref.reference in works:
                            req_refs.append(ref)
                RequestReference.delete(req_refs)

                to_create = []
                for i in to_link:
                    for work in works:
                        to_create.append({
                                'request': i,
                                'reference': str(work),
                                })
                if to_create:
                    RequestReference.create(to_create)
            return

        fun_fields = ('actual_start_date', 'actual_finish_date',
                      'constraint_start_date', 'constraint_finish_date')
        db_fields = ('actual_start_time', 'actual_finish_time',
                     'constraint_start_time', 'constraint_finish_time')
        for fun_field, db_field in zip(fun_fields, db_fields):
            if fun_field == name:
                cls.write(works, {
                        db_field: (value
                            and datetime.datetime.combine(value,
                                datetime.time())
                            or None),
                        })
                break

    @classmethod
    def add_minutes(cls, company, date, minutes):
        minutes = int(round(minutes))
        minutes = date.minute + minutes

        hours = minutes // 60
        if hours:
            date = cls.add_hours(company, date, hours)

        minutes = minutes % 60

        date = datetime.datetime(
            date.year,
            date.month,
            date.day,
            date.hour,
            minutes,
            date.second)

        return date

    @classmethod
    def add_hours(cls, company, date, hours):
        while hours:
            if hours != intfloor(hours):
                minutes = (hours - intfloor(hours)) * 60
                date = cls.add_minutes(company, date, minutes)
            hours = intfloor(hours)

            hours = date.hour + hours
            days = hours // company.hours_per_work_day
            if days:
                date = cls.add_days(company, date, days)

            hours = hours % company.hours_per_work_day

            date = datetime.datetime(
                date.year,
                date.month,
                date.day,
                intfloor(hours),
                date.minute,
                date.second)

            hours = hours - intfloor(hours)

        return date

    @classmethod
    def add_days(cls, company, date, days):
        day_per_week = company.hours_per_work_week / company.hours_per_work_day

        while days:
            if days != intfloor(days):
                hours = (days - intfloor(days)) * company.hours_per_work_day
                date = cls.add_hours(company, date, hours)
            days = intfloor(days)

            days = date.weekday() + days

            weeks = days // day_per_week
            days = days % day_per_week

            if weeks:
                date = cls.add_weeks(company, date, weeks)

            date += datetime.timedelta(days=-date.weekday() + intfloor(days))

            days = days - intfloor(days)

        return date

    @classmethod
    def add_weeks(cls, company, date, weeks):
        day_per_week = company.hours_per_work_week / company.hours_per_work_day

        if weeks != intfloor(weeks):
            days = (weeks - intfloor(weeks)) * day_per_week
            if days:
                date = cls.add_days(company, date, days)

        date += datetime.timedelta(days=7 * intfloor(weeks))

        return date

    def compute_dates(self):
        values = {}
        get_early_finish = lambda work: values.get(work, {}).get(
            'early_finish_time', work.early_finish_time)
        get_late_start = lambda work: values.get(work, {}).get(
            'late_start_time', work.late_start_time)
        maxdate = lambda x, y: x and y and max(x, y) or x or y
        mindate = lambda x, y: x and y and min(x, y) or x or y

        # propagate constraint_start_time
        constraint_start = reduce(maxdate, (pred.early_finish_time
                for pred in self.predecessors), None)

        if constraint_start is None and self.parent:
            constraint_start = self.parent.early_start_time

        constraint_start = maxdate(constraint_start,
            self.constraint_start_time)

        works = deque([(self, constraint_start)])
        work2children = {}
        parent = None

        while works or parent:
            if parent:
                work = parent
                parent = None

                # Compute early_finish
                if work.children:
                    early_finish_time = reduce(
                        maxdate, map(get_early_finish, work.children), None)
                else:
                    early_finish_time = None
                    if values[work]['early_start_time']:
                        early_finish_time = self.add_hours(work.company,
                                values[work]['early_start_time'],
                                work.duration)
                values[work]['early_finish_time'] = early_finish_time

                # Propagate constraint_start on successors
                for w in work.successors:
                    works.append((w, early_finish_time))

                if not work.parent:
                    continue

                # housecleaning work2children
                if work.parent not in work2children:
                    work2children[work.parent] = set()
                work2children[work.parent].update(work.successors)

                if work in work2children[work.parent]:
                    work2children[work.parent].remove(work)

                # if no sibling continue to walk up the tree
                if not work2children.get(work.parent):
                    if not work.parent in values:
                        values[work.parent] = {}
                    parent = work.parent

                continue

            work, constraint_start = works.popleft()
            # take constraint define on the work into account
            constraint_start = maxdate(constraint_start,
                                       work.constraint_start_time)

            if constraint_start:
                early_start = self.add_hours(work.company, constraint_start,
                        work.leveling_delay)
            else:
                early_start = None

            # update values
            if not work in values:
                values[work] = {}
            values[work]['early_start_time'] = early_start

            # Loop on children if they exist
            if work.children and work not in work2children:
                work2children[work] = set(work.children)
                # Propagate constraint_start on children
                for w in work.children:
                    if w.predecessors:
                        continue
                    works.append((w, early_start))
            else:
                parent = work

        # propagate constraint_finish_time
        constraint_finish = reduce(mindate, (succ.late_start_time
                for succ in self.successors), None)

        if constraint_finish is None and self.parent:
            constraint_finish = self.parent.late_finish_time

        constraint_finish = mindate(constraint_finish,
            self.constraint_finish_time)

        works = deque([(self, constraint_finish)])
        work2children = {}
        parent = None

        while works or parent:
            if parent:
                work = parent
                parent = None

                # Compute late_start
                if work.children:
                    reduce(mindate, map(get_late_start, work.children), None)
                else:
                    late_start_time = None
                    if values[work]['late_finish_time']:
                        late_start_time = self.add_hours(work.company,
                                values[work]['late_finish_time'],
                                -work.duration)
                values[work]['late_start_time'] = late_start_time

                # Propagate constraint_finish on predecessors
                for w in work.predecessors:
                    works.append((w, late_start_time))

                if not work.parent:
                    continue

                # housecleaning work2children
                if work.parent not in work2children:
                    work2children[work.parent] = set()
                work2children[work.parent].update(work.predecessors)

                if work in work2children[work.parent]:
                    work2children[work.parent].remove(work)

                # if no sibling continue to walk up the tree
                if not work2children.get(work.parent):
                    if not work.parent in values:
                        values[work.parent] = {}
                    parent = work.parent

                continue

            work, constraint_finish = works.popleft()
            # take constraint define on the work into account
            constraint_finish = mindate(constraint_finish,
                                        work.constraint_finish_time)

            if constraint_finish:
                late_finish = self.add_hours(work.company, constraint_finish,
                        -work.back_leveling_delay)
            else:
                late_finish = None

            # update values
            if not work in values:
                values[work] = {}
            values[work]['late_finish_time'] = late_finish

            # Loop on children if they exist
            if work.children and work not in work2children:
                work2children[work] = set(work.children)
                # Propagate constraint_start on children
                for w in work.children:
                    if w.successors:
                        continue
                    works.append((w, late_finish))
            else:
                parent = work

        # write values
        write_fields = ('early_start_time', 'early_finish_time',
                        'late_start_time', 'late_finish_time')
        for work, val in values.iteritems():
            write_cond = False
            for field in write_fields:
                if field in val and getattr(work, field) != val[field]:
                    write_cond = True
                    break

            if write_cond:
                self.write([work], val)

    def reset_leveling(self):
        get_key = lambda w: (set(p.id for p in w.predecessors),
                             set(s.id for s in w.successors))

        parent_id = self.parent and self.parent.id or None
        siblings = self.search([
                ('parent', '=', parent_id)
                ])
        to_clean = []

        ref_key = get_key(self)
        for sibling in siblings:
            if sibling.leveling_delay == sibling.back_leveling_delay == 0:
                continue
            if get_key(sibling) == ref_key:
                to_clean.append(sibling)

        if to_clean:
            self.write(to_clean, {
                    'leveling_delay': 0,
                    'back_leveling_delay': 0,
                    })

    def create_leveling(self):
        # define some helper functions
        get_key = lambda w: (set(p.id for p in w.predecessors),
                             set(s.id for s in w.successors))
        over_alloc = lambda current_alloc, work: (
            reduce(lambda res, alloc: (res
                    or (current_alloc[alloc.employee.id]
                        + alloc.percentage) > 100),
                work.allocations,
                False))

        def sum_allocs(current_alloc, work):
            res = defaultdict(float)
            for alloc in work.allocations:
                empl = alloc.employee.id
                res[empl] = current_alloc[empl] + alloc.percentage
            return res

        def compute_delays(siblings):
            # time_line is a list [[end_delay, allocations], ...], this
            # mean that allocations is valid between the preceding end_delay
            # (or 0 if it doesn't exist) and the current end_delay.
            timeline = []
            for sibling in siblings:
                delay = 0
                ignored = []
                overloaded = []
                item = None

                while timeline:
                    # item is [end_delay, allocations]
                    item = heappop(timeline)
                    if over_alloc(item[1], sibling):
                        ignored.extend(overloaded)
                        ignored.append(item)
                        delay = item[0]
                        continue
                    elif item[1] >= delay + sibling.duration:
                        overloaded.append(item)
                    else:
                        #Succes!
                        break

                heappush(timeline,
                         [delay + sibling.duration,
                          sum_allocs(defaultdict(float), sibling),
                          sibling.id])

                for i in ignored:
                    heappush(timeline, i)
                for i in overloaded:
                    i[1] = sum_allocs(i[1], sibling)
                    heappush(timeline, i)

                yield sibling, delay

        parent = self.parent and self.parent.id or None
        siblings = self.search([
                ('parent', '=', parent.id)
                ])

        refkey = get_key(self)
        siblings = [s for s in siblings if get_key(s) == refkey]

        for sibling, delay in compute_delays(siblings):
            self.write([sibling], {
                    'leveling_delay': delay,
                    })

        siblings.reverse()
        for sibling, delay in compute_delays(siblings):
            self.write([sibling], {
                    'back_leveling_delay': delay,
                    })

        if parent:
            parent.compute_dates()

    @classmethod
    def write(cls, works, values):
        super(Work, cls).write(works, values)

        if 'effort' in values:
            for work in works:
                work.reset_leveling()
        fields = ('constraint_start_time', 'constraint_finish_time',
                  'effort')
        if reduce(lambda x, y: x or y in values, fields, False):
            for work in works:
                work.compute_dates()

    @classmethod
    def create(cls, vlist):
        works = super(Work, cls).create(vlist)
        for work in works:
            work.reset_leveling()
            work.compute_dates()
        return works

    @classmethod
    def delete(cls, works):
        to_update = set()
        for work in works:
            if work.parent and work.parent not in works:
                to_update.add(work.parent)
                to_update.update(c for c in work.parent.children
                    if c not in works)
        super(Work, cls).delete(works)

        for work in to_update:
            work.reset_leveling()
            work.compute_dates()


class PredecessorSuccessor(ModelSQL):
    'Predecessor - Successor'
    __name__ = 'project.predecessor_successor'
    predecessor = fields.Many2One('project.work', 'Predecessor',
            ondelete='CASCADE', required=True, select=True)
    successor = fields.Many2One('project.work', 'Successor',
            ondelete='CASCADE', required=True, select=True)

    @classmethod
    def write(cls, pred_succs, values):
        Work = Pool().get('project.work')
        super(PredecessorSuccessor, cls).write(pred_succs, values)

        works = Work.browse(values.itervalues())
        for work in works:
            work.reset_leveling()
        for work in works:
            work.compute_dates()

    @classmethod
    def delete(cls, pred_succs):
        works = set()
        parents = set()
        for pred_succ in pred_succs:
            works.update((pred_succ.predecessor,
                    pred_succ.successor))

            if pred_succ.predecessor.parent:
                parents.add(pred_succ.predecessor.parent)

        super(PredecessorSuccessor, cls).delete(pred_succs)

        for work in works:
            work.reset_leveling()

        for parent in parents:
            parent.compute_dates()

    @classmethod
    def create(cls, vlist):
        pred_succs = super(PredecessorSuccessor, cls).create(vlist)

        for pred_succ in pred_succs:
            pred_succ.predecessor.reset_leveling()
            pred_succ.successor.reset_leveling()

            if pred_succ.predecessor.parent:
                pred_succ.predecessor.parent.compute_dates()
        return pred_succs


class Leveling(Wizard):
    'Tasks Leveling'
    __name__ = 'project_plan.work.leveling'
    start_state = 'leveling'
    leveling = StateTransition()

    def transition_leveling(self):
        Work = Pool().get('project.work')
        Work(Transaction().context['active_id']).create_leveling()
        return 'end'
