# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from collections import defaultdict, deque
from functools import reduce
from heapq import heappop, heappush

from trytond.model import ModelSQL, fields, tree
from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.wizard import StateTransition, Wizard


def intfloor(x):
    return int(round(x, 4))


class Work(tree(parent='successors'), metaclass=PoolMeta):
    __name__ = 'project.work'
    predecessors = fields.Many2Many('project.predecessor_successor',
        'successor', 'predecessor', 'Predecessors',
        domain=[
            ('parent', '=', Eval('parent', -1)),
            ('id', '!=', Eval('id', -1)),
            ])
    successors = fields.Many2Many('project.predecessor_successor',
        'predecessor', 'successor', 'Successors',
        domain=[
            ('parent', '=', Eval('parent', -1)),
            ('id', '!=', Eval('id', -1)),
            ])
    leveling_delay = fields.Float("Leveling Delay", required=True)
    back_leveling_delay = fields.Float("Back Leveling Delay", required=True)
    allocations = fields.One2Many('project.allocation', 'work', 'Allocations',
        states={
            'invisible': Eval('type') != 'task',
            })
    duration = fields.Function(
        fields.TimeDelta('Duration', 'company_work_time'),
        'get_function_fields')
    early_start_time = fields.DateTime("Early Start Time", readonly=True)
    late_start_time = fields.DateTime("Late Start Time", readonly=True)
    early_finish_time = fields.DateTime("Early Finish Time", readonly=True)
    late_finish_time = fields.DateTime("Late Finish Time", readonly=True)
    actual_start_time = fields.DateTime("Actual Start Time")
    actual_finish_time = fields.DateTime("Actual Finish Time")
    constraint_start_time = fields.DateTime("Constraint Start Time")
    constraint_finish_time = fields.DateTime("Constraint Finish Time")
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
        depends={'type'}), 'get_function_fields',
        setter='set_function_fields')
    constraint_finish_date = fields.Function(fields.Date('Constraint Finish',
        depends={'type'}), 'get_function_fields',
        setter='set_function_fields')

    @classmethod
    def __setup__(cls):
        super().__setup__()

    @staticmethod
    def default_leveling_delay():
        return 0.0

    @staticmethod
    def default_back_leveling_delay():
        return 0.0

    @classmethod
    def get_function_fields(cls, works, names):
        '''
        Function to compute function fields
        '''
        res = {}

        ids = [w.id for w in works]
        if 'duration' in names:
            all_works = cls.search([
                    ('parent', 'child_of', ids),
                    ])
            all_works = set(all_works)

            durations = {}
            id2work = {}
            leafs = set()
            for work in all_works:
                id2work[work.id] = work
                if not work.children:
                    leafs.add(work.id)

                total_allocation = 0
                effort = work.effort_duration or datetime.timedelta()
                if not work.allocations:
                    durations[work.id] = effort
                    continue
                for allocation in work.allocations:
                    total_allocation += allocation.percentage
                durations[work.id] = datetime.timedelta(
                    seconds=effort.total_seconds()
                    / (total_allocation / 100.0))

            while leafs:
                for work_id in leafs:
                    work = id2work[work_id]
                    all_works.remove(work)
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

    @property
    def hours(self):
        if not self.duration:
            return 0
        return self.duration.total_seconds() / 60 / 60

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

        def get_early_finish(work):
            return values.get(work, {}).get(
                'early_finish_time', work.early_finish_time)

        def get_late_start(work):
            return values.get(work, {}).get(
                'late_start_time', work.late_start_time)

        def maxdate(x, y):
            return x and y and max(x, y) or x or y

        def mindate(x, y):
            return x and y and min(x, y) or x or y

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
                                work.hours)
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
                    if work.parent not in values:
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
            if work not in values:
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
                                -work.hours)
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
                    if work.parent not in values:
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
            if work not in values:
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
        to_write = []
        for work, val in values.items():
            write_cond = False
            for field in write_fields:
                if field in val and getattr(work, field) != val[field]:
                    write_cond = True
                    break

            if write_cond:
                to_write.extend(([work], val))
        if to_write:
            self.write(*to_write)

    def reset_leveling(self):
        def get_key(w):
            return (
                set(p.id for p in w.predecessors),
                set(s.id for s in w.successors))

        if not self.parent:
            return
        siblings = self.search([
                ('parent', '=', self.parent.id)
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
        def get_key(w):
            return (
                set(p.id for p in w.predecessors),
                set(s.id for s in w.successors))

        def over_alloc(current_alloc, work):
            return reduce(lambda res, alloc: (
                    res
                    or (current_alloc[alloc.employee.id]
                        + alloc.percentage) > 100),
                work.allocations,
                False)

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
                        # Succes!
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

        siblings = self.search([
                ('parent', '=', self.parent.id if self.parent else None)
                ])

        refkey = get_key(self)
        siblings = [s for s in siblings if get_key(s) == refkey]

        for sibling, delay in compute_delays(siblings):
            sibling.leveling_delay = delay

        siblings.reverse()
        for sibling, delay in compute_delays(siblings):
            sibling.back_leveling_delay = delay
        self.__class__.save(siblings)

        if self.parent:
            self.parent.compute_dates()

    @classmethod
    def on_modification(cls, mode, works, field_names=None):
        super().on_modification(mode, works, field_names=field_names)
        if mode in {'create', 'write'}:
            for work in works:
                if not field_names or 'effort' in field_names:
                    work.reset_leveling()
                if not field_names or field_names & {
                        'constraint_start_time', 'constraint_finish_time',
                        'effort'}:
                    work.compute_dates()

    @classmethod
    def on_delete(cls, works):
        callback = super().on_delete(works)
        to_update = set()
        for work in works:
            if work.parent and work.parent not in works:
                to_update.add(work.parent)
                to_update.update(
                    c for c in work.parent.children if c not in works)

        def replan():
            for work in to_update:
                work.reset_leveling()
                work.compute_dates()
        callback.append(replan)
        return callback


class PredecessorSuccessor(ModelSQL):
    __name__ = 'project.predecessor_successor'
    predecessor = fields.Many2One(
        'project.work', "Predecessor", ondelete='CASCADE', required=True)
    successor = fields.Many2One(
        'project.work', "Successor", ondelete='CASCADE', required=True)

    @classmethod
    def on_modification(cls, mode, records, field_names=None):
        super().on_modification(mode, records, field_names=field_names)
        if mode == 'create':
            if not field_names or field_names & {
                    'predecessor', 'successor', 'parent'}:
                for record in records:
                    record.predecessor.reset_leveling()
                    record.successor.reset_leveling()
                    if record.predecessor.parent:
                        record.predecessor.parent.compute_dates()

    @classmethod
    def on_delete(cls, records):
        callback = super().on_delete(records)
        works = set()
        parents = set()
        for record in records:
            works.add(record.predecessor)
            works.add(record.successor)
            if record.predecessor.parent:
                parents.add(record.predecessor.parent)

        def replan():
            for work in works:
                work.reset_leveling()
            for parent in parents:
                parent.compute_dates()
        callback.append(replan)
        return callback


class Leveling(Wizard):
    __name__ = 'project_plan.work.leveling'
    start_state = 'leveling'
    leveling = StateTransition()

    def transition_leveling(self):
        self.record.create_leveling()
        return 'end'
