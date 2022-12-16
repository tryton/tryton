# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime

from sql import Literal
from sql.aggregate import Sum

from trytond.i18n import gettext
from trytond.model import (
    ModelView, ModelSQL, ModelStorage, DeactivableMixin, fields, Unique)
from trytond.pyson import Not, Bool, Eval, If
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.tools import reduce_ids, grouped_slice

from .exceptions import CompanyValidationError


class Work(DeactivableMixin, ModelSQL, ModelView):
    'Work'
    __name__ = 'timesheet.work'
    name = fields.Char('Name',
        states={
            'invisible': Bool(Eval('origin')),
            'required': ~Eval('origin'),
            },
        depends=['origin'],
        help="The main identifier of the work.")
    origin = fields.Reference('Origin', selection='get_origin',
        states={
            'invisible': Bool(Eval('name')),
            'required': ~Eval('name'),
            },
        depends=['name'],
        help="Use to relate the time spent to other records.")
    duration = fields.Function(fields.TimeDelta('Timesheet Duration',
            'company_work_time', help="Total time spent on this work."),
        'get_duration')
    timesheet_start_date = fields.Date('Timesheet Start',
        domain=[
            If(Eval('timesheet_start_date') & Eval('timesheet_end_date'),
                ('timesheet_start_date', '<=', Eval('timesheet_end_date')),
                ()),
            ],
        depends=['timesheet_end_date'],
        help="Restrict adding lines before the date.")
    timesheet_end_date = fields.Date('Timesheet End',
        domain=[
            If(Eval('timesheet_start_date') & Eval('timesheet_end_date'),
                ('timesheet_end_date', '>=', Eval('timesheet_start_date')),
                ()),
            ],
        depends=['timesheet_start_date'],
        help="Restrict adding lines after the date.")
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True, help="Make the work belong to the company.")
    timesheet_lines = fields.One2Many('timesheet.line', 'work',
        'Timesheet Lines',
        depends=['active'],
        states={
            'readonly': Not(Bool(Eval('active'))),
            },
        help="Spend time on this work.")
    # Self referring field to use for aggregation in graph view
    work = fields.Function(fields.Many2One('timesheet.work', 'Work'),
        'get_work')

    @classmethod
    def __setup__(cls):
        super(Work, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('origin_unique', Unique(t, t.origin, t.company),
                'timesheet.msg_work_origin_unique_company'),
            ]

    @classmethod
    def __register__(cls, module_name):
        table_h = cls.__table_handler__(module_name)
        table = cls.__table__()
        cursor = Transaction().connection.cursor()

        super(Work, cls).__register__(module_name)

        # Migration from 4.0: remove required on name
        table_h.not_null_action('name', 'remove')

        # Migration from 4.0: remove parent, left and right
        if table_h.column_exist('parent'):
            id2name = {}
            id2parent = {}
            cursor.execute(*table.select(
                    table.id, table.parent, table.name))
            for id_, parent, name in cursor:
                id2name[id_] = name
                id2parent[id_] = parent

            for id_, name in id2name.items():
                parent = id2parent[id_]
                while parent:
                    name = '%s\\%s' % (id2name[parent], name)
                    parent = id2parent[parent]
                cursor.execute(*table.update(
                        [table.name], [name],
                        where=table.id == id_))
            table_h.drop_column('parent')
        table_h.drop_column('left')
        table_h.drop_column('right')

        # Migration from 4.0: remove timesheet_available
        if table_h.column_exist('timesheet_available'):
            cursor.execute(*table.delete(
                    where=table.timesheet_available == Literal(False)))
            table_h.drop_column('timesheet_available')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        return []

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        models = cls._get_origin()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [('', '')] + [(m.model, m.name) for m in models]

    @classmethod
    def get_duration(cls, works, name):
        pool = Pool()
        Line = pool.get('timesheet.line')
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        context = transaction.context

        table_w = cls.__table__()
        line = Line.__table__()
        ids = [w.id for w in works]
        durations = dict.fromkeys(ids, None)
        where = Literal(True)
        if context.get('from_date'):
            where &= line.date >= context['from_date']
        if context.get('to_date'):
            where &= line.date <= context['to_date']
        if context.get('employees'):
            where &= line.employee.in_(context['employees'])

        query_table = table_w.join(line, 'LEFT',
            condition=line.work == table_w.id)

        for sub_ids in grouped_slice(ids):
            red_sql = reduce_ids(table_w.id, sub_ids)
            cursor.execute(*query_table.select(table_w.id, Sum(line.duration),
                    where=red_sql & where,
                    group_by=table_w.id))
            for work_id, duration in cursor.fetchall():
                # SQLite uses float for SUM
                if duration and not isinstance(duration, datetime.timedelta):
                    duration = datetime.timedelta(seconds=duration)
                durations[work_id] = duration
        return durations

    def get_work(self, name):
        return self.id

    def get_rec_name(self, name):
        if isinstance(self.origin, ModelStorage):
            return self.origin.rec_name
        else:
            return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('name',) + tuple(clause[1:]),
            ] + [
                ('origin.rec_name',) + tuple(clause[1:]) + (origin,)
                for origin in cls._get_origin()]

    @classmethod
    def copy(cls, works, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('timesheet_lines', None)
        return super(Work, cls).copy(works, default=default)

    @classmethod
    def validate(cls, works):
        super(Work, cls).validate(works)
        for work in works:
            if work.origin and not work._validate_company():
                raise CompanyValidationError(
                    gettext('timesheet.msg_work_company_different_origin',
                        work=work.rec_name))

    def _validate_company(self):
        return True

    @classmethod
    def search_global(cls, text):
        for record, rec_name, icon in super(Work, cls).search_global(text):
            icon = icon or 'tryton-clock'
            yield record, rec_name, icon

    @property
    def hours(self):
        if not self.duration:
            return 0
        return self.duration.total_seconds() / 60 / 60


class WorkContext(ModelView):
    'Work Context'
    __name__ = 'timesheet.work.context'
    from_date = fields.Date('From Date',
        help="Do not take into account lines before the date.")
    to_date = fields.Date('To Date',
        help="Do not take into account lines after the date.")
