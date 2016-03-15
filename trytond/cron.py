# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import threading
import logging

from trytond.pool import Pool
from trytond.transaction import Transaction

__all__ = ['run']
logger = logging.getLogger(__name__)


def run(options):
    database_list = Pool.database_list()
    for dbname in options.database_names:
        thread = _threads.get(dbname)
        if thread and thread.is_alive():
            logger.info('skip "%s" as previous cron still running', dbname)
            continue
        pool = Pool(dbname)
        if dbname not in database_list:
            with Transaction().start(dbname, 0, readonly=True):
                pool.init()
        if not pool.lock.acquire(0):
            logger.warning('can not acquire lock on "%s"', dbname)
            continue
        try:
            try:
                Cron = pool.get('ir.cron')
            except KeyError:
                logger.error(
                    'missing "ir.cron" on "%s"', dbname, exc_info=True)
                continue
        finally:
            pool.lock.release()
        thread = threading.Thread(
                target=Cron.run,
                args=(dbname,), kwargs={})
        logger.info('start thread for "%s"', dbname)
        thread.start()
        _threads[dbname] = thread
_threads = {}
Pool.start()
