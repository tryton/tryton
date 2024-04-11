# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import threading
import time

from trytond.pool import Pool
from trytond.transaction import Transaction

__all__ = ['run']
logger = logging.getLogger(__name__)


def run(options):
    threads = []
    for name in options.database_names:
        thread = threading.Thread(target=lambda: Pool(name).init())
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()

    threads = {}
    while True:
        for db_name in options.database_names:
            thread = threads.get(db_name)
            if thread and thread.is_alive():
                logger.info(
                    'skip "%s" as previous cron still running', db_name)
                continue
            database_list = Pool.database_list()
            pool = Pool(db_name)
            if db_name not in database_list:
                with Transaction().start(db_name, 0, readonly=True):
                    pool.init()
            Cron = pool.get('ir.cron')
            thread = threading.Thread(
                    target=Cron.run,
                    args=(db_name,), kwargs={})
            logger.info('start thread for "%s"', db_name)
            thread.start()
            threads[db_name] = thread
        if options.once:
            break
        time.sleep(60)
    for thread in threads.values():
        thread.join()
