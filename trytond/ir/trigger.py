# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import time
from sql import Literal, Null, Select
from sql.aggregate import Count, Max
from sql.functions import CurrentTimestamp
from sql.operators import Concat

from trytond.model.exceptions import ValidationError
from trytond.i18n import gettext
from ..model import (
    ModelView, ModelSQL, DeactivableMixin, fields, EvalEnvironment, Check)
from ..pyson import Eval, PYSONDecoder
from ..tools import grouped_slice
from ..tools import reduce_ids
from ..transaction import Transaction
from ..cache import Cache
from ..pool import Pool

__all__ = [
    'Trigger', 'TriggerLog',
    ]


class ConditionError(ValidationError):
    pass


class Trigger(DeactivableMixin, ModelSQL, ModelView):
    "Trigger"
    __name__ = 'ir.trigger'
    name = fields.Char('Name', required=True, translate=True)
    model = fields.Many2One('ir.model', 'Model', required=True, select=True)
    on_time = fields.Boolean('On Time', select=True, states={
            'invisible': (Eval('on_create', False)
                | Eval('on_write', False)
                | Eval('on_delete', False)),
            }, depends=['on_create', 'on_write', 'on_delete'])
    on_create = fields.Boolean('On Create', select=True, states={
        'invisible': Eval('on_time', False),
        }, depends=['on_time'])
    on_write = fields.Boolean('On Write', select=True, states={
        'invisible': Eval('on_time', False),
        }, depends=['on_time'])
    on_delete = fields.Boolean('On Delete', select=True, states={
        'invisible': Eval('on_time', False),
        }, depends=['on_time'])
    condition = fields.Char('Condition', required=True,
        help='A PYSON statement evaluated with record represented by '
        '"self"\nIt triggers the action if true.')
    limit_number = fields.Integer('Limit Number', required=True,
        help='Limit the number of call to "Action Function" by records.\n'
        '0 for no limit.')
    minimum_time_delay = fields.TimeDelta('Minimum Delay',
        help='Set a minimum time delay between call to "Action Function" '
        'for the same record.\n'
        'empty for no delay.')
    action = fields.Selection([], "Action", required=True)
    _get_triggers_cache = Cache('ir_trigger.get_triggers')

    @classmethod
    def __setup__(cls):
        super(Trigger, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('on_exclusive',
                Check(t, ~((t.on_time == Literal(True))
                        & ((t.on_create == Literal(True))
                            | (t.on_write == Literal(True))
                            | (t.on_delete == Literal(True))))),
                '"On Time" and others are mutually exclusive!'),
            ]
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        table = cls.__table_handler__(cls, module_name)
        sql_table = cls.__table__()

        super(Trigger, cls).__register__(module_name)

        table_h = cls.__table_handler__(module_name)

        # Migration from 3.4:
        # change minimum_delay into timedelta minimum_time_delay
        if table.column_exist('minimum_delay'):
            cursor.execute(*sql_table.select(
                    sql_table.id, sql_table.minimum_delay,
                    where=sql_table.minimum_delay != Null))
            for id_, delay in cursor.fetchall():
                delay = datetime.timedelta(hours=delay)
                cursor.execute(*sql_table.update(
                        [sql_table.minimum_time_delay],
                        [delay],
                        where=sql_table.id == id_))
            table.drop_column('minimum_delay')

        # Migration from 5.4: merge action
        if (table_h.column_exist('action_model')
                and table_h.column_exist('action_function')):
            pool = Pool()
            Model = pool.get('ir.model')
            model = Model.__table__()
            action_model = model.select(
                model.model, where=model.id == sql_table.action_model)
            cursor.execute(*sql_table.update(
                    [sql_table.action],
                    [Concat(action_model, Concat(
                                '|', sql_table.action_function))]))
            table_h.drop_column('action_model')
            table_h.drop_column('action_function')

    @classmethod
    def validate(cls, triggers):
        super(Trigger, cls).validate(triggers)
        cls.check_condition(triggers)

    @classmethod
    def check_condition(cls, triggers):
        '''
        Check condition
        '''
        for trigger in triggers:
            try:
                PYSONDecoder(noeval=True).decode(trigger.condition)
            except Exception:
                raise ConditionError(
                    gettext('ir.msg_trigger_invalid_condition',
                        condition=trigger.condition,
                        trigger=trigger.rec_name))

    @staticmethod
    def default_limit_number():
        return 0

    @fields.depends('on_time')
    def on_change_on_time(self):
        if self.on_time:
            self.on_create = False
            self.on_write = False
            self.on_delete = False

    @fields.depends('on_create')
    def on_change_on_create(self):
        if self.on_create:
            self.on_time = False

    @fields.depends('on_write')
    def on_change_on_write(self):
        if self.on_write:
            self.on_time = False

    @fields.depends('on_delete')
    def on_change_on_delete(self):
        if self.on_delete:
            self.on_time = False

    @classmethod
    def get_triggers(cls, model_name, mode):
        """
        Return triggers for a model and a mode
        """
        assert mode in ['create', 'write', 'delete', 'time'], \
            'Invalid trigger mode'

        if Transaction().context.get('_no_trigger'):
            return []

        key = (model_name, mode)
        trigger_ids = cls._get_triggers_cache.get(key)
        if trigger_ids is not None:
            return cls.browse(trigger_ids)

        triggers = cls.search([
                ('model.model', '=', model_name),
                ('on_%s' % mode, '=', True),
                ])
        cls._get_triggers_cache.set(key, list(map(int, triggers)))
        return triggers

    def eval(self, record):
        """
        Evaluate the condition of trigger
        """
        env = {}
        env['current_date'] = datetime.datetime.today()
        env['time'] = time
        env['context'] = Transaction().context
        env['self'] = EvalEnvironment(record, record.__class__)
        return bool(PYSONDecoder(env).decode(self.condition))

    def queue_trigger_action(self, records):
        trigger_records = Transaction().trigger_records[self.id]
        ids = set(map(int, records)) - trigger_records
        self.__class__.__queue__.trigger_action(self, list(ids))
        trigger_records.update(ids)

    def trigger_action(self, ids):
        """
        Trigger the action define on trigger for the records
        """
        pool = Pool()
        TriggerLog = pool.get('ir.trigger.log')
        Model = pool.get(self.model.model)
        model, method = self.action.split('|')
        ActionModel = pool.get(model)
        cursor = Transaction().connection.cursor()
        trigger_log = TriggerLog.__table__()

        ids = [r.id for r in Model.browse(ids) if self.eval(r)]

        # Filter on limit_number
        if self.limit_number:
            new_ids = []
            for sub_ids in grouped_slice(ids):
                sub_ids = list(sub_ids)
                red_sql = reduce_ids(trigger_log.record_id, sub_ids)
                cursor.execute(*trigger_log.select(
                        trigger_log.record_id, Count(Literal(1)),
                        where=red_sql & (trigger_log.trigger == self.id),
                        group_by=trigger_log.record_id))
                number = dict(cursor.fetchall())
                for record_id in sub_ids:
                    if record_id not in number:
                        new_ids.append(record_id)
                        continue
                    if number[record_id] < self.limit_number:
                        new_ids.append(record_id)
            ids = new_ids

        def cast_datetime(value):
            datepart, timepart = value.split(" ")
            year, month, day = map(int, datepart.split("-"))
            timepart_full = timepart.split(".")
            hours, minutes, seconds = map(
                int, timepart_full[0].split(":"))
            if len(timepart_full) == 2:
                microseconds = int(timepart_full[1])
            else:
                microseconds = 0
            return datetime.datetime(
                year, month, day, hours, minutes, seconds, microseconds)

        # Filter on minimum_time_delay
        if self.minimum_time_delay:
            new_ids = []
            # Use now from the transaction to compare with create_date
            timestamp_cast = self.__class__.create_date.sql_cast
            cursor.execute(*Select([timestamp_cast(CurrentTimestamp())]))
            now, = cursor.fetchone()
            if isinstance(now, str):
                now = cast_datetime(now)
            for sub_ids in grouped_slice(ids):
                sub_ids = list(sub_ids)
                red_sql = reduce_ids(trigger_log.record_id, sub_ids)
                cursor.execute(*trigger_log.select(
                        trigger_log.record_id, Max(trigger_log.create_date),
                        where=(red_sql & (trigger_log.trigger == self.id)),
                        group_by=trigger_log.record_id))
                delay = dict(cursor.fetchall())
                for record_id in sub_ids:
                    if record_id not in delay:
                        new_ids.append(record_id)
                        continue
                    # SQLite return string for MAX
                    if isinstance(delay[record_id], str):
                        delay[record_id] = cast_datetime(delay[record_id])
                    if now - delay[record_id] >= self.minimum_time_delay:
                        new_ids.append(record_id)
            ids = new_ids

        records = Model.browse(ids)
        if records:
            getattr(ActionModel, method)(records, self)
        if self.limit_number or self.minimum_time_delay:
            to_create = []
            for record in records:
                to_create.append({
                        'trigger': self.id,
                        'record_id': record.id,
                        })
            if to_create:
                TriggerLog.create(to_create)

    @classmethod
    def trigger_time(cls):
        '''
        Trigger time actions
        '''
        pool = Pool()
        triggers = cls.search([
                ('on_time', '=', True),
                ])
        for trigger in triggers:
            Model = pool.get(trigger.model.model)
            # TODO add a domain
            records = Model.search([])
            trigger.trigger_action(records)

    @classmethod
    def create(cls, vlist):
        res = super(Trigger, cls).create(vlist)
        # Restart the cache on the get_triggers method of ir.trigger
        cls._get_triggers_cache.clear()
        return res

    @classmethod
    def write(cls, triggers, values, *args):
        super(Trigger, cls).write(triggers, values, *args)
        # Restart the cache on the get_triggers method of ir.trigger
        cls._get_triggers_cache.clear()

    @classmethod
    def delete(cls, records):
        super(Trigger, cls).delete(records)
        # Restart the cache on the get_triggers method of ir.trigger
        cls._get_triggers_cache.clear()


class TriggerLog(ModelSQL):
    'Trigger Log'
    __name__ = 'ir.trigger.log'
    trigger = fields.Many2One(
        'ir.trigger', 'Trigger', required=True, ondelete='CASCADE')
    record_id = fields.Integer('Record ID', required=True)

    @classmethod
    def __register__(cls, module_name):
        super(TriggerLog, cls).__register__(module_name)

        table = cls.__table_handler__(module_name)
        table.index_action(['trigger', 'record_id'], 'add')
