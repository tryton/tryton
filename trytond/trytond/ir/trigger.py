#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
import time
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval
from trytond.tools import safe_eval
from trytond.backend import TableHandler
from trytond.tools import reduce_ids
from trytond.transaction import Transaction
from trytond.cache import Cache
from trytond.pool import Pool


class Trigger(ModelSQL, ModelView):
    "Trigger"
    _name = 'ir.trigger'
    _description = __doc__
    name = fields.Char('Name', required=True, translate=True)
    active = fields.Boolean('Active', select=2)
    model = fields.Many2One('ir.model', 'Model', required=True, select=1)
    on_time = fields.Boolean('On Time', select=1, states={
            'invisible': (Eval('on_create', False)
                | Eval('on_write', False)
                | Eval('on_delete', False)),
        }, depends=['on_create', 'on_write', 'on_delete'],
        on_change=['on_time'])
    on_create = fields.Boolean('On Create', select=1, states={
        'invisible': Eval('on_time', False),
        }, depends=['on_time'],
        on_change=['on_create'])
    on_write = fields.Boolean('On Write', select=1, states={
        'invisible': Eval('on_time', False),
        }, depends=['on_time'],
        on_change=['on_write'])
    on_delete = fields.Boolean('On Delete', select=1, states={
        'invisible': Eval('on_time', False),
        }, depends=['on_time'],
        on_change=['on_delete'])
    condition = fields.Char('Condition', required=True,
            help='A Python statement evaluated with record represented by '
            '"self"\nIt triggers the action if true.')
    limit_number = fields.Integer('Limit Number', help='Limit the number of '
            'call to "Action Function" by records.\n'
            '0 for no limit.')
    minimum_delay = fields.Float('Minimum Delay', help='Set a minimum delay '
            'in minutes between call to "Action Function" for the same record.\n'
            '0 for no delay.')
    action_model = fields.Many2One('ir.model', 'Action Model', required=True)
    action_function = fields.Char('Action Function', required=True)

    def __init__(self):
        super(Trigger, self).__init__()
        self._sql_constraints += [
            ('on_exclusive',
                'CHECK(NOT(on_time AND (on_create OR on_write OR on_delete)))',
                '"On Time" and others are mutually exclusive!'),
        ]
        self._constraints += [
            ('check_condition', 'invalid_condition'),
        ]
        self._error_messages.update({
            'invalid_condition': 'Condition must be a python expression!',
        })
        self._order.insert(0, ('name', 'ASC'))

    def check_condition(self, ids):
        '''
        Check condition
        '''
        for trigger in self.browse(ids):
            try:
                compile(trigger.condition, '', 'eval')
            except (SyntaxError, TypeError):
                return False
        return True

    def default_active(self):
        return True

    def on_change_on_time(self, values):
        if values.get('on_time'):
            return {
                    'on_create': False,
                    'on_write': False,
                    'on_delete': False,
                    }
        return {}

    def on_change_on_create(self, values):
        if values.get('on_create'):
            return {
                    'on_time': False,
                    }
        return {}

    def on_change_on_write(self, values):
        if values.get('on_write'):
            return {
                    'on_time': False,
                    }
        return {}

    def on_change_on_delete(self, values):
        if values.get('on_delete'):
            return {
                    'on_time': False,
                    }
        return {}

    @Cache('ir_trigger.get_triggers')
    def get_triggers(self, model_name, mode):
        """
        Return trigger ids for a model and a mode

        :param model_name: the name of the model
        :param mode: the mode that can be 'create', 'write', 'delete' or 'time'
        :return: a list of ir.trigger ids
        """
        assert mode in ['create', 'write', 'delete', 'time'], \
                'Invalid trigger mode'

        if Transaction().user == 0:
            return [] # XXX is it want we want?

        trigger_ids = self.search([
            ('model.model', '=', model_name),
            ('on_%s' % mode, '=', True),
            ])
        return trigger_ids

    def eval(self, trigger, record):
        """
        Evaluate the condition of trigger

        :param trigger: a BrowseRecord of ir.trigger
        :param record: a BrowseRecord of the tested model
        :return: a boolean
        """
        pool = Pool()
        model_obj = pool.get(trigger.model.model)
        env = {}
        env['current_date'] = datetime.datetime.today()
        env['time'] = time
        env['context'] = Transaction().context
        env['self'] = record
        return bool(safe_eval(trigger.condition, env))

    def trigger_action(self, ids, trigger_id):
        """
        Trigger the action define on trigger_id for the ids

        :param ids: the list of record ids triggered
        :param trigger_id: the trigger id
        """
        pool = Pool()
        trigger_log_obj = pool.get('ir.trigger.log')
        trigger = self.browse(trigger_id)
        model_obj = pool.get(trigger.action_model.model)
        cursor = Transaction().cursor

        # Filter on limit_number
        if trigger.limit_number:
            new_ids = []
            for i in range(0, len(ids), cursor.IN_MAX):
                sub_ids = ids[i:i + cursor.IN_MAX]
                red_sql, red_ids = reduce_ids('"record_id"', sub_ids)
                cursor.execute('SELECT "record_id", COUNT(1) FROM "%s" '
                        'WHERE %s AND "trigger" = %%s '
                        'GROUP BY "record_id"'
                        % (trigger_log_obj._table, red_sql),
                        red_ids + [trigger.id])
                number = dict(cursor.fetchall())
                for record_id in sub_ids:
                    if record_id not in number:
                        new_ids.append(record_id)
                        continue
                    if number[record_id] < trigger.limit_number:
                        new_ids.append(record_id)
            ids = new_ids

        # Filter on minimum_delay
        if trigger.minimum_delay:
            new_ids = []
            for i in range(0, len(ids), cursor.IN_MAX):
                sub_ids = ids[i:i + cursor.IN_MAX]
                red_sql, red_ids = reduce_ids('"record_id"', sub_ids)
                cursor.execute('SELECT "record_id", MAX("create_date") '
                        'FROM "%s" '
                        'WHERE %s AND "trigger" = %%s '
                        'GROUP BY "record_id"'
                        % (trigger_log_obj._table, red_sql),
                        red_ids + [trigger.id])
                delay = dict(cursor.fetchall())
                for record_id in sub_ids:
                    if record_id not in delay:
                        new_ids.append(record_id)
                        continue
                    # SQLite return string for MAX
                    if isinstance(delay[record_id], basestring):
                        datepart, timepart = delay[record_id].split(" ")
                        year, month, day = map(int, datepart.split("-"))
                        timepart_full = timepart.split(".")
                        hours, minutes, seconds = map(int, timepart_full[0].split(":"))
                        if len(timepart_full) == 2:
                            microseconds = int(timepart_full[1])
                        else:
                            microseconds = 0
                        delay[record_id] = datetime.datetime(year, month, day,
                                hours, minutes, seconds, microseconds)
                    if datetime.datetime.now() - delay[record_id] \
                            >= datetime.timedelta(minutes=trigger.minimum_delay):
                        new_ids.append(record_id)
            ids = new_ids

        if ids:
            getattr(model_obj, trigger.action_function)(ids, trigger_id)
        if trigger.limit_number or trigger.minimum_delay:
            for record_id in ids:
                trigger_log_obj.create({
                    'trigger': trigger.id,
                    'record_id': record_id,
                    })

    def trigger_time(self):
        '''
        Trigger time actions
        '''
        pool = Pool()
        trigger_ids = self.search([
            ('on_time', '=', True),
            ])
        for trigger in self.browse(trigger_ids):
            model_obj = pool.get(trigger.model.model)
            triggered_ids = []
            # TODO add a domain
            record_ids = model_obj.search([])
            for record in model_obj.browse(record_ids):
                if self.eval(trigger, record):
                    triggered_ids.append(record.id)
            if triggered_ids:
                self.trigger_action(triggered_ids, trigger.id)

    def create(self, values):
        res = super(Trigger, self).create(values)
        # Restart the cache on the get_triggers method of ir.trigger
        self.get_triggers.reset()
        return res

    def write(self, ids, values):
        res = super(Trigger, self).write(ids, values)
        # Restart the cache on the get_triggers method of ir.trigger
        self.get_triggers.reset()
        return res

    def delete(self, ids):
        res = super(Trigger, self).delete(ids)
        # Restart the cache on the get_triggers method of ir.trigger
        self.get_triggers.reset()
        return res

Trigger()


class TriggerLog(ModelSQL):
    'Trigger Log'
    _name = 'ir.trigger.log'
    _description = __doc__
    trigger = fields.Many2One('ir.trigger', 'Trigger', required=True)
    record_id = fields.Integer('Record ID', required=True)

    def init(self, module_name):
        super(TriggerLog, self).init(module_name)

        table = TableHandler(Transaction().cursor, self, module_name)
        table.index_action(['trigger', 'record_id'], 'add')

TriggerLog()
