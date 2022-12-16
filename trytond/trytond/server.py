# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"""
%prog [options]
"""
import logging
import logging.config
import logging.handlers
import sys
import os
import signal
import time
from getpass import getpass
import threading

from sql import Table

from trytond.config import config, parse_listen
from trytond import backend
from trytond.pool import Pool
from trytond.monitor import monitor
from .transaction import Transaction


class TrytonServer(object):

    def __init__(self, options):

        config.update_etc(options.configfile)

        if options.logconf:
            logging.config.fileConfig(options.logconf)
            logging.getLogger('server').info('using %s as logging '
                'configuration file', options.logconf)
        else:
            logformat = ('%(process)s %(thread)s [%(asctime)s] '
                '%(levelname)s %(name)s %(message)s')
            if options.verbose:
                if options.dev:
                    level = logging.DEBUG
                else:
                    level = logging.INFO
            else:
                level = logging.ERROR
            logging.basicConfig(level=level, format=logformat)

        self.logger = logging.getLogger(__name__)

        if options.configfile:
            self.logger.info('using %s as configuration file',
                options.configfile)
        else:
            self.logger.info('using default configuration')
        self.logger.info('initialising distributed objects services')
        self.xmlrpcd = []
        self.jsonrpcd = []
        self.webdavd = []
        self.options = options

        if time.tzname[0] != 'UTC':
            self.logger.error('timezone is not set to UTC')

    def run(self):
        "Run the server and never return"
        init = {}

        signal.signal(signal.SIGINT, lambda *a: self.stop())
        signal.signal(signal.SIGTERM, lambda *a: self.stop())
        if hasattr(signal, 'SIGQUIT'):
            signal.signal(signal.SIGQUIT, lambda *a: self.stop())
        if hasattr(signal, 'SIGUSR1'):
            signal.signal(signal.SIGUSR1, lambda *a: self.restart())

        if self.options.pidfile:
            with open(self.options.pidfile, 'w') as fd_pid:
                fd_pid.write("%d" % (os.getpid()))

        if not self.options.update:
            self.start_servers()

        for db_name in self.options.database_names:
            init[db_name] = False
            try:
                with Transaction().start(db_name, 0) as transaction:
                    cursor = transaction.cursor
                    if self.options.update:
                        if not cursor.test():
                            self.logger.info("init db")
                            backend.get('Database').init(cursor)
                            init[db_name] = True
                        cursor.commit()
                    elif not cursor.test():
                        raise Exception("'%s' is not a Tryton database!" %
                            db_name)
            except Exception:
                self.stop(False)
                raise

        for db_name in self.options.database_names:
            if self.options.update:
                with Transaction().start(db_name, 0) as transaction:
                    cursor = transaction.cursor
                    if not cursor.test():
                        raise Exception("'%s' is not a Tryton database!"
                            % db_name)
                    lang = Table('ir_lang')
                    cursor.execute(*lang.select(lang.code,
                            where=lang.translatable == True))
                    lang = [x[0] for x in cursor.fetchall()]
            else:
                lang = None
            Pool(db_name).init(update=self.options.update, lang=lang)

        for db_name in self.options.database_names:
            if init[db_name]:
                # try to read password from environment variable
                # TRYTONPASSFILE, empty TRYTONPASSFILE ignored
                passpath = os.getenv('TRYTONPASSFILE')
                password = ''
                if passpath:
                    try:
                        with open(passpath) as passfile:
                            password = passfile.readline()[:-1]
                    except Exception, err:
                        sys.stderr.write('Can not read password '
                            'from "%s": "%s"\n' % (passpath, err))

                if not password:
                    while True:
                        password = getpass('Admin Password for %s: ' % db_name)
                        password2 = getpass('Admin Password Confirmation: ')
                        if password != password2:
                            sys.stderr.write('Admin Password Confirmation '
                                'doesn\'t match Admin Password!\n')
                            continue
                        if not password:
                            sys.stderr.write('Admin Password is required!\n')
                            continue
                        break

                with Transaction().start(db_name, 0) as transaction:
                    pool = Pool()
                    User = pool.get('res.user')
                    admin, = User.search([('login', '=', 'admin')])
                    User.write([admin], {
                            'password': password,
                            })
                    transaction.cursor.commit()

        if self.options.update:
            self.logger.info('Update/Init succeed!')
            logging.shutdown()
            sys.exit(0)

        threads = {}
        while True:
            if self.options.cron:
                for dbname in Pool.database_list():
                    thread = threads.get(dbname)
                    if thread and thread.is_alive():
                        continue
                    pool = Pool(dbname)
                    if not pool.lock.acquire(0):
                        continue
                    try:
                        try:
                            Cron = pool.get('ir.cron')
                        except KeyError:
                            continue
                    finally:
                        pool.lock.release()
                    thread = threading.Thread(
                            target=Cron.run,
                            args=(dbname,), kwargs={})
                    thread.start()
                    threads[dbname] = thread
            if self.options.dev:
                for _ in range(60):
                    if monitor([self.options.configfile]
                            if self.options.configfile else []):
                        self.restart()
                    time.sleep(1)
            else:
                time.sleep(60)

    def start_servers(self):
        ssl = config.get('ssl', 'privatekey')
        # Launch Server
        if config.get('jsonrpc', 'listen'):
            from trytond.protocols.jsonrpc import JSONRPCDaemon
            for hostname, port in parse_listen(
                    config.get('jsonrpc', 'listen')):
                self.jsonrpcd.append(JSONRPCDaemon(hostname, port, ssl))
                self.logger.info("starting JSON-RPC%s protocol on %s:%d",
                    ssl and ' SSL' or '', hostname or '*', port)

        if config.get('xmlrpc', 'listen'):
            from trytond.protocols.xmlrpc import XMLRPCDaemon
            for hostname, port in parse_listen(
                    config.get('xmlrpc', 'listen')):
                self.xmlrpcd.append(XMLRPCDaemon(hostname, port, ssl))
                self.logger.info("starting XML-RPC%s protocol on %s:%d",
                    ssl and ' SSL' or '', hostname or '*', port)

        if config.get('webdav', 'listen'):
            from trytond.protocols.webdav import WebDAVServerThread
            for hostname, port in parse_listen(
                    config.get('webdav', 'listen')):
                self.webdavd.append(WebDAVServerThread(hostname, port, ssl))
                self.logger.info("starting WebDAV%s protocol on %s:%d",
                    ssl and ' SSL' or '', hostname or '*', port)

        for servers in (self.xmlrpcd, self.jsonrpcd, self.webdavd):
            for server in servers:
                server.start()

    def stop(self, exit=True):
        for servers in (self.xmlrpcd, self.jsonrpcd, self.webdavd):
            for server in servers:
                server.stop()
                server.join()
        if exit:
            if self.options.pidfile:
                os.unlink(self.options.pidfile)
            logging.getLogger('server').info('stopped')
            logging.shutdown()
            sys.exit(0)

    def restart(self):
        self.stop(False)
        args = ([sys.executable] + ['-W%s' % o for o in sys.warnoptions]
            + sys.argv)
        if sys.platform == "win32":
            args = ['"%s"' % arg for arg in args]
        os.execv(sys.executable, args)
