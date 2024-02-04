# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
import logging
import random
import selectors
import signal
import sys
import time
from concurrent import futures
from multiprocessing import cpu_count

from sql import Flavor

from trytond import backend
from trytond.config import config
from trytond.exceptions import UserError, UserWarning
from trytond.pool import Pool
from trytond.status import processing
from trytond.transaction import Transaction, TransactionError

__all__ = ['work']
logger = logging.getLogger(__name__)


class Queue(object):
    def __init__(self, database_name, executor):
        self.database = backend.Database(database_name).connect()
        self.connection = self.database.get_connection(autocommit=True)
        self.executor = executor

    def pull(self, name=None):
        database_list = Pool.database_list()
        pool = Pool(self.database.name)
        if self.database.name not in database_list:
            with Transaction().start(self.database.name, 0, readonly=True):
                pool.init()
        Queue = pool.get('ir.queue')
        return Queue.pull(self.database, self.connection, name=name)

    def run(self, task_id):
        return self.executor.submit(run_task, self.database.name, task_id)


class TaskList(list):
    def filter(self):
        for t in list(self):
            if not t.running():
                self.remove(t)
        return self


def _noop():
    pass


def work(options):
    Flavor.set(backend.Database.flavor)
    if not config.getboolean('queue', 'worker', default=False):
        return
    try:
        processes = options.processes or cpu_count()
    except NotImplementedError:
        processes = 1
    logger.info("start %d workers", processes)
    executor_options = dict(
        max_workers=processes,
        mp_context=None,
        initializer=initializer,
        initargs=(options.database_names,),
        max_tasks_per_child=options.maxtasksperchild,
        )
    if sys.version_info < (3, 11):
        del executor_options["max_tasks_per_child"]

    with \
            futures.ProcessPoolExecutor(**executor_options) as executor, \
            selectors.DefaultSelector() as selector:
        queues = [Queue(name, executor) for name in options.database_names]
        tasks = TaskList()

        for queue in queues:
            selector.register(queue.connection, selectors.EVENT_READ)

        while True:
            timeout = options.timeout
            # Add some randomness to avoid concurrent pulling
            time.sleep(0.1 * random.random())
            while len(tasks.filter()) >= processes:
                futures.wait(tasks, return_when=futures.FIRST_COMPLETED)

            # Probe process pool is still operative
            # before pulling a new task
            executor.submit(_noop).result()

            for queue in queues:
                try:
                    task_id, next_ = queue.pull(options.name)
                except backend.DatabaseOperationalError:
                    break
                if next_ is not None:
                    timeout = min(next_, timeout)
                if task_id:
                    tasks.append(queue.run(task_id))
                    break
            else:
                for key, _ in selector.select(timeout=timeout):
                    connection = key.fileobj
                    connection.poll()
                    while connection.notifies:
                        connection.notifies.pop(0)


def initializer(database_names, worker=True):
    if worker:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    pools = []
    database_list = Pool.database_list()
    for database_name in database_names:
        pool = Pool(database_name)
        if database_name not in database_list:
            with Transaction().start(database_name, 0, readonly=True):
                pool.init()
        pools.append(pool)
    return pools


def run_task(pool, task_id):
    if not isinstance(pool, Pool):
        database_list = Pool.database_list()
        pool = Pool(pool)
        if pool.database_name not in database_list:
            with Transaction().start(pool.database_name, 0, readonly=True):
                pool.init()
    Queue = pool.get('ir.queue')
    Error = pool.get('ir.error')

    def duration():
        return (time.monotonic() - started) * 1000
    started = time.monotonic()
    name = '<Task %s@%s>' % (task_id, pool.database_name)
    retry = config.getint('database', 'retry')
    try:
        count = 0
        transaction_extras = {}
        while True:
            if count:
                time.sleep(0.02 * (retry - count))
            with Transaction().start(
                    pool.database_name, 0,
                    **transaction_extras) as transaction:
                try:
                    try:
                        task, = Queue.search([('id', '=', task_id)])
                    except ValueError:
                        # the task was rollbacked, nothing to do
                        break
                    with processing(name):
                        task.run()
                    break
                except TransactionError as e:
                    transaction.rollback()
                    e.fix(transaction_extras)
                    continue
                except backend.DatabaseOperationalError:
                    if count < retry:
                        transaction.rollback()
                        count += 1
                        logger.debug("Retry: %i", count)
                        continue
                    raise
                except (UserError, UserWarning) as e:
                    Error.report(task, e)
                    raise
        logger.info("%s in %i ms", name, duration())
    except backend.DatabaseOperationalError:
        logger.info(
            "%s failed after %i ms, retrying", name, duration(),
            exc_info=logger.isEnabledFor(logging.DEBUG))
        if not config.getboolean('queue', 'worker', default=False):
            time.sleep(0.02 * retry)
        try:
            with Transaction().start(pool.database_name, 0) as transaction:
                if not transaction.database.has_channel():
                    logger.critical('%s failed', name, exc_info=True)
                    return
                task = Queue(task_id)
                if task.scheduled_at and task.enqueued_at < task.scheduled_at:
                    duration = (task.scheduled_at - task.enqueued_at) * 2
                else:
                    duration = dt.timedelta(seconds=2 * retry)
                duration = max(duration, dt.timedelta(hours=1))
                scheduled_at = dt.datetime.now() + duration * random.random()
                Queue.push(task.name, task.data, scheduled_at=scheduled_at)
        except Exception:
            logger.critical(
                "rescheduling %s failed", name, exc_info=True)
    except (UserError, UserWarning):
        logger.info(
            "%s failed after %i ms", name, duration(),
            exc_info=logger.isEnabledFor(logging.DEBUG))
    except Exception:
        logger.critical(
            "%s failed after %i ms", name, duration(), exc_info=True)
