# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from sql import With, Literal, Null
from sql.aggregate import Min
from sql.functions import CurrentTimestamp, Extract

from trytond.config import config
from trytond.model import ModelSQL, fields
from trytond.pool import Pool
from trytond.tools import grouped_slice
from trytond.transaction import Transaction

has_worker = config.getboolean('queue', 'worker', default=False)
clean_days = config.getint('queue', 'clean_days', default=30)


class Queue(ModelSQL):
    "Queue"
    __name__ = 'ir.queue'
    name = fields.Char("Name", required=True)

    data = fields.Dict(None, "Data")

    enqueued_at = fields.Timestamp("Enqueued at", required=True)
    dequeued_at = fields.Timestamp("Dequeued at")
    finished_at = fields.Timestamp("Finished at")

    scheduled_at = fields.Timestamp("Scheduled at",
        help="When the task can start.")
    expected_at = fields.Timestamp("Expected at",
        help="When the task should be done.")

    @classmethod
    def __register__(cls, module_name):
        queue = cls.__table__()
        super().__register__(module_name)
        table_h = cls.__table_handler__(module_name)

        # Add index for candidates
        table_h.index_action([
                queue.scheduled_at.nulls_first,
                queue.expected_at.nulls_first,
                queue.dequeued_at,
                queue.name,
                ], action='add')

    @classmethod
    def default_enqueued_at(cls):
        return datetime.datetime.now()

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('enqueued_at')
        default.setdefault('dequeued_at')
        default.setdefault('finished_at')
        return super(Queue, cls).copy(records, default=default)

    @classmethod
    def push(cls, name, data, scheduled_at=None, expected_at=None):
        transaction = Transaction()
        database = transaction.database
        cursor = transaction.connection.cursor()
        with transaction.set_user(0):
            record, = cls.create([{
                        'name': name,
                        'data': data,
                        'scheduled_at': scheduled_at,
                        'expected_at': expected_at,
                        }])
        if database.has_channel():
            cursor.execute('NOTIFY "%s"', (cls.__name__,))
        if not has_worker:
            transaction.tasks.append(record.id)
        return record.id

    @classmethod
    def pull(cls, database, connection, name=None):
        cursor = connection.cursor()
        queue = cls.__table__()
        queue_c = cls.__table__()
        queue_s = cls.__table__()

        candidates = With('id', 'scheduled_at', 'expected_at',
            query=queue_c.select(
                queue_c.id,
                queue_c.scheduled_at,
                queue_c.expected_at,
                where=((queue_c.name == name) if name else Literal(True))
                & (queue_c.dequeued_at == Null),
                order_by=[
                    queue_c.scheduled_at.nulls_first,
                    queue_c.expected_at.nulls_first]))
        selected = queue_s.select(
            queue_s.id,
            where=((queue_s.name == name) if name else Literal(True))
            & (queue_s.dequeued_at == Null)
            & ((queue_s.scheduled_at <= CurrentTimestamp())
                | (queue_s.scheduled_at == Null)),
            order_by=[
                queue_s.scheduled_at.nulls_first,
                queue_s.expected_at.nulls_first],
            limit=1)
        if database.has_select_for():
            For = database.get_select_for_skip_locked()
            selected.for_ = For('UPDATE')

        next_timeout = With('seconds', query=candidates.select(
                Min(Extract('EPOCH',
                        candidates.scheduled_at - CurrentTimestamp())
                    ),
                where=candidates.scheduled_at >= CurrentTimestamp()))

        task_id, seconds = None, None
        if database.has_returning():
            query = queue.update([queue.dequeued_at], [CurrentTimestamp()],
                where=queue.id.in_(selected),
                with_=[candidates, next_timeout],
                returning=[
                    queue.id, next_timeout.select(next_timeout.seconds)])
            cursor.execute(*query)
            row = cursor.fetchone()
            if row:
                task_id, seconds = row
        else:
            query = queue.select(queue.id,
                where=queue.id.in_(selected),
                with_=[candidates])
            cursor.execute(*query)
            row = cursor.fetchone()
            if row:
                task_id, = row
                query = queue.update([queue.dequeued_at], [CurrentTimestamp()],
                    where=queue.id == task_id)
                cursor.execute(*query)
            query = next_timeout.select(next_timeout.seconds)
            cursor.execute(*query)
            row = cursor.fetchone()
            if row:
                seconds, = row

        if not task_id and database.has_channel():
            cursor.execute('LISTEN "%s"', (cls.__name__,))
        return task_id, seconds

    def run(self):
        transaction = Transaction()
        Model = Pool().get(self.data['model'])
        with transaction.set_user(self.data['user']), \
                transaction.set_context(self.data['context']):
            instances = self.data['instances']
            # Ensure record ids still exist
            if isinstance(instances, int):
                with transaction.set_context(active_test=False):
                    if Model.search([('id', '=', instances)]):
                        instances = Model(instances)
                    else:
                        instances = None
            else:
                ids = set()
                with transaction.set_context(active_test=False):
                    for sub_ids in grouped_slice(instances):
                        records = Model.search([('id', 'in', list(sub_ids))])
                        ids.update(map(int, records))
                if ids:
                    instances = Model.browse(
                        [i for i in instances if i in ids])
                else:
                    instances = None
            if instances is not None:
                getattr(Model, self.data['method'])(
                    instances, *self.data['args'], **self.data['kwargs'])
        if not self.dequeued_at:
            self.dequeued_at = datetime.datetime.now()
        self.finished_at = datetime.datetime.now()
        self.save()

    @classmethod
    def clean(cls, date=None):
        if date is None:
            date = (
                datetime.datetime.now() - datetime.timedelta(days=clean_days))
        tasks = cls.search(['OR',
                ('dequeued_at', '<', date),
                ('finished_at', '<', date),
                ])
        cls.delete(tasks)

    @classmethod
    def caller(cls, model):
        return _Model(cls, model)


class _Model(object):
    def __init__(self, queue, model):
        self.__queue = queue
        self.__model = model

    def __getattr__(self, name):
        return _Method(self.__queue, self.__model, name)


class _Method(object):
    def __init__(self, queue, model, name):
        self.__queue = queue
        self.__model = model
        self.__name = name

    def __call__(self, instances, *args, **kwargs):
        transaction = Transaction()
        context = transaction.context.copy()
        name = context.pop('queue_name', 'default')
        now = datetime.datetime.now()
        scheduled_at = context.pop('queue_scheduled_at', None)
        if scheduled_at is not None:
            scheduled_at = now + scheduled_at
        expected_at = context.pop('queue_expected_at', None)
        context.pop('_check_access', None)
        if expected_at is not None:
            expected_at = now + expected_at
        try:
            instances = list(map(int, instances))
        except TypeError:
            instances = int(instances)
        data = {
            'model': self.__model.__name__,
            'method': self.__name,
            'user': transaction.user,
            'context': context,
            'instances': instances,
            'args': args,
            'kwargs': kwargs,
            }
        return self.__queue.push(
            name, data,
            scheduled_at=scheduled_at, expected_at=expected_at)
