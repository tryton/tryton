# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
import logging
import signal
import sys
import time
from concurrent import futures
from multiprocessing import cpu_count

from trytond.pool import Pool
from trytond.transaction import Transaction

__all__ = ['run']
logger = logging.getLogger(__name__)


def run(options):
    try:
        processes = options.processes or cpu_count()
    except NotImplementedError:
        processes = 1
    logger.info("start %d crons", processes)
    executor_options = dict(
        max_workers=processes,
        mp_context=None,
        initializer=initializer,
        initargs=(options.database_names,),
        max_tasks_per_child=options.maxtasksperchild,
        )
    if sys.version_info < (3, 11):
        del executor_options["max_tasks_per_child"]

    with futures.ProcessPoolExecutor(**executor_options) as executor:
        while True:
            for database_name in options.database_names:
                executor.submit(run_cron, database_name)
            if options.once:
                break
            else:
                now = dt.datetime.now()
                time.sleep(60 - (now.second + now.microsecond / 10**6))


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


def run_cron(database_name):
    database_list = Pool.database_list()
    pool = Pool(database_name)
    if database_name not in database_list:
        with Transaction().start(database_name, 0, readonly=True):
            pool.init()
    Cron = pool.get('ir.cron')
    Cron.run(database_name)
