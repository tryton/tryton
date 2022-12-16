# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import time
from sql import Literal, Null
from sql.aggregate import Count, Max

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
    action_model = fields.Many2One('ir.model', 'Action Model', required=True)
    action_function = fields.Char('Action Function', required=True)
    _get_triggers_cache = Cache('ir_trigger.get_triggers')

    @classmethod
    def __setup__(cls):
        super(Trigger, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('on_exclusive',
                Check(t, ~((t.on_time == True)
                        & ((t.on_create == True)
                            | (t.on_write == True)
                            | (t.on_delete == True)))),
                '"On Time" and others are mutually exclusive!'),
            ]
        cls._error_messages.update({
                'invalid_condition': ('Condition "%(condition)s" is not a '
                    'valid PYSON expression on trigger "%(trigger)s".'),
                })
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        table = cls.__table_handler__(cls, module_name)
        sql_table = cls.__table__()

        super(Trigger, cls).__register__(module_name)

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
                cls.raise_user_error('invalid_condition', {
                        'condition': trigger.condition,
                        'trigger': trigger.rec_name,
                        })

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

        if Transaction().user == 0 and not Transaction().context.get('user'):
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

    @staticmethod
    def eval(trigger, record):
        """
        Evaluate the condition of trigger
        """
        env = {}
        env['current_date'] = datetime.datetime.today()
        env['time'] = time
        env['context'] = Transaction().context
        env['self'] = EvalEnvironment(record, record.__class__)
        return bool(PYSONDecoder(env).decode(trigger.condition))

    @classmethod
    def trigger_action(cls, records, trigger):
        """
        Trigger the action define on trigger for the records
        """
        pool = Pool()
        TriggerLog = pool.get('ir.trigger.log')
        Model = pool.get(trigger.model.model)
        ActionModel = pool.get(trigger.action_model.model)
        cursor = Transaction().connection.cursor()
        trigger_log = TriggerLog.__table__()
        ids = list(map(int, records))

        # Filter on limit_number
        if trigger.limit_number:
            new_ids = []
            for sub_ids in grouped_slice(ids):
                sub_ids = list(sub_ids)
                red_sql = reduce_ids(trigger_log.record_id, sub_ids)
                cursor.execute(*trigger_log.select(
                        trigger_log.record_id, Count(Literal(1)),
                        where=red_sql & (trigger_log.trigger == trigger.id),
                        group_by=trigger_log.record_id))
                number = dict(cursor.fetchall())
                for record_id in sub_ids:
                    if record_id not in number:
                        new_ids.append(record_id)
                        continue
                    if number[record_id] < trigger.limit_number:
                        new_ids.append(record_id)
            ids = new_ids

        # Filter on minimum_time_delay
        if trigger.minimum_time_delay:
            new_ids = []
            for sub_ids in grouped_slice(ids):
                sub_ids = list(sub_ids)
                red_sql = reduce_ids(trigger_log.record_id, sub_ids)
                cursor.execute(*trigger_log.select(
                        trigger_log.record_id, Max(trigger_log.create_date),
                        where=(red_sql & (trigger_log.trigger == trigger.id)),
                        group_by=trigger_log.record_id))
                delay = dict(cursor.fetchall())
                for record_id in sub_ids:
                    if record_id not in delay:
                        new_ids.append(record_id)
                        continue
                    # SQLite return string for MAX
                    if isinstance(delay[record_id], str):
                        datepart, timepart = delay[record_id].split(" ")
                        year, month, day = map(int, datepart.split("-"))
                        timepart_full = timepart.split(".")
                        hours, minutes, seconds = map(
                            int, timepart_full[0].split(":"))
                        if len(timepart_full) == 2:
                            microseconds = int(timepart_full[1])
                        else:
                            microseconds = 0
                        delay[record_id] = datetime.datetime(year, month,
                            day, hours, minutes, seconds, microseconds)
                    if (datetime.datetime.now() - delay[record_id]
                            >= trigger.minimum_time_delay):
                        new_ids.append(record_id)
            ids = new_ids

        records = Model.browse(ids)
        if records:
            getattr(ActionModel, trigger.action_function)(records, trigger)
        if trigger.limit_number or trigger.minimum_time_delay:
            to_create = []
            for record in records:
                to_create.append({
                        'trigger': trigger.id,
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
            triggered = []
            # TODO add a domain
            records = Model.search([])
            for record in records:
                if cls.eval(trigger, record):
                    triggered.append(record)
            if triggered:
                cls.trigger_action(triggered, trigger)

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
    trigger = fields.Many2One('ir.trigger', 'Trigger', required=True)
    record_id = fields.Integer('Record ID', required=True)

    @classmethod
    def __register__(cls, module_name):
        super(TriggerLog, cls).__register__(module_name)

        table = cls.__table_handler__(module_name)
        table.index_action(['trigger', 'record_id'], 'add')
