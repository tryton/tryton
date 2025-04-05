# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import time

from sql import Literal, Select
from sql.aggregate import Count, Max
from sql.functions import CurrentTimestamp

from trytond.cache import Cache
from trytond.i18n import gettext
from trytond.model import (
    Check, DeactivableMixin, EvalEnvironment, Index, ModelSQL, ModelView,
    fields)
from trytond.model.exceptions import ValidationError
from trytond.pool import Pool
from trytond.pyson import Eval, If, PYSONDecoder, TimeDelta
from trytond.tools import grouped_slice, reduce_ids
from trytond.transaction import Transaction


class ConditionError(ValidationError):
    pass


class Trigger(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'ir.trigger'
    name = fields.Char('Name', required=True, translate=True)
    model = fields.Many2One('ir.model', 'Model', required=True)
    on_time_ = fields.Boolean(
        "On Time",
        domain=[
            If(Eval('on_create_', False)
                | Eval('on_write_', False)
                | Eval('on_delete_', False),
                ('on_time_', '=', False),
                ()),
            ])
    on_create_ = fields.Boolean(
        "On Create",
        domain=[
            If(Eval('on_time_', False),
                ('on_create_', '=', False),
                ()),
            ])
    on_write_ = fields.Boolean(
        "On Write",
        domain=[
            If(Eval('on_time_', False),
                ('on_write_', '=', False),
                ()),
            ])
    on_delete_ = fields.Boolean(
        "On Delete",
        domain=[
            If(Eval('on_time_', False),
                ('on_delete_', '=', False),
                ()),
            ])
    condition = fields.Char('Condition', required=True,
        help='A PYSON statement evaluated with record represented by '
        '"self"\nIt triggers the action if true.')
    limit_number = fields.Integer('Limit Number', required=True,
        help='Limit the number of call to "Action Function" by records.\n'
        '0 for no limit.')
    minimum_time_delay = fields.TimeDelta(
        "Minimum Delay",
        domain=['OR',
            ('minimum_time_delay', '=', None),
            ('minimum_time_delay', '>=', TimeDelta()),
            ],
        help='Set a minimum time delay between call to "Action Function" '
        'for the same record.\n'
        'empty for no delay.')
    action = fields.Selection([], "Action", required=True)
    _get_triggers_cache = Cache('ir_trigger.get_triggers')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('on_exclusive',
                Check(t, ~((t.on_time_ == Literal(True))
                        & ((t.on_create_ == Literal(True))
                            | (t.on_write_ == Literal(True))
                            | (t.on_delete_ == Literal(True))))),
                'ir.msg_trigger_exclusive'),
            ]
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        table_h = cls.__table_handler__(module_name)

        # Migration from 7.4: rename on_<event>
        for name in ['on_time', 'on_create', 'on_write', 'on_delete']:
            table_h.column_rename(name, name + '_')

        super().__register__(module_name)

    @classmethod
    def validate_fields(cls, triggers, field_names):
        super().validate_fields(triggers, field_names)
        cls.check_condition(triggers, field_names)

    @classmethod
    def check_condition(cls, triggers, field_names=None):
        '''
        Check condition
        '''
        if field_names and 'condition' not in field_names:
            return
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

    @fields.depends('on_time_')
    def on_change_on_time_(self):
        if self.on_time_:
            self.on_create_ = False
            self.on_write_ = False
            self.on_delete_ = False

    @fields.depends('on_create_')
    def on_change_on_create_(self):
        if self.on_create_:
            self.on_time_ = False

    @fields.depends('on_write_')
    def on_change_on_write_(self):
        if self.on_write_:
            self.on_time_ = False

    @fields.depends('on_delete_')
    def on_change_on_delete_(self):
        if self.on_delete_:
            self.on_time_ = False

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
                ('model.name', '=', model_name),
                (f'on_{mode}_', '=', True),
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
        ids = {r.id for r in records if self.eval(r)} - trigger_records
        if ids:
            self.__class__.__queue__.trigger_action(self, list(ids))
            trigger_records.update(ids)

    def trigger_action(self, ids):
        """
        Trigger the action define on trigger for the records
        """
        pool = Pool()
        TriggerLog = pool.get('ir.trigger.log')
        Model = pool.get(self.model.name)
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
                number = dict(cursor)
                for record_id in sub_ids:
                    if record_id not in number:
                        new_ids.append(record_id)
                        continue
                    if number[record_id] < self.limit_number:
                        new_ids.append(record_id)
            ids = new_ids

        # Filter on minimum_time_delay
        if self.minimum_time_delay:
            new_ids = []
            # Use now from the transaction to compare with create_date
            timestamp_cast = self.__class__.create_date.sql_cast
            cursor.execute(*Select([timestamp_cast(CurrentTimestamp())]))
            now, = cursor.fetchone()
            if isinstance(now, str):
                now = datetime.datetime.fromisoformat(now)
            for sub_ids in grouped_slice(ids):
                sub_ids = list(sub_ids)
                red_sql = reduce_ids(trigger_log.record_id, sub_ids)
                cursor.execute(*trigger_log.select(
                        trigger_log.record_id, Max(trigger_log.create_date),
                        where=(red_sql & (trigger_log.trigger == self.id)),
                        group_by=trigger_log.record_id))
                delay = dict(cursor)
                for record_id in sub_ids:
                    if record_id not in delay:
                        new_ids.append(record_id)
                        continue
                    # SQLite return string for MAX
                    if isinstance(delay[record_id], str):
                        delay[record_id] = datetime.datetime.fromisoformat(
                            delay[record_id])
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
                ('on_time_', '=', True),
                ])
        for trigger in triggers:
            Model = pool.get(trigger.model.name)
            # TODO add a domain
            records = Model.search([])
            trigger.trigger_action(records)

    @classmethod
    def on_modification(cls, mode, records, field_names=None):
        super().on_modification(mode, records, field_names=field_names)
        cls._get_triggers_cache.clear()


class TriggerLog(ModelSQL):
    __name__ = 'ir.trigger.log'
    trigger = fields.Many2One(
        'ir.trigger', 'Trigger', required=True, ondelete='CASCADE')
    record_id = fields.Integer('Record ID', required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('trigger')

        table = cls.__table__()
        cls._sql_indexes.add(
            Index(
                table,
                (table.trigger, Index.Range()),
                (table.record_id, Index.Range())))
