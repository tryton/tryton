#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"""
%prog [options]
"""
import logging
import logging.handlers
import sys, os, signal
import time
from trytond.config import CONFIG
from getpass import getpass
try:
    import hashlib
except ImportError:
    hashlib = None
    import sha
import threading
import string
import random


class TrytonServer(object):

    def __init__(self, options):
        format = '[%(asctime)s] %(levelname)s:%(name)s:%(message)s'
        datefmt = '%a %b %d %H:%M:%S %Y'
        logging.basicConfig(level=logging.DEBUG, format=format,
                datefmt=datefmt)

        CONFIG.update_etc(options['configfile'])
        CONFIG.update_cmdline(options)

        if CONFIG['logfile']:
            logf = CONFIG['logfile']
            # test if the directories exist, else create them
            try:
                diff = 0
                if os.path.isfile(logf):
                    diff = int(time.time()) - int(os.stat(logf)[-1])
                handler = logging.handlers.TimedRotatingFileHandler(
                    logf, 'D', 1, 30)
                handler.rolloverAt -= diff
            except Exception, exception:
                sys.stderr.write(\
                        "ERROR: couldn't create the logfile directory:" \
                        + str(exception))
            else:
                formatter = logging.Formatter(format, datefmt)
                # tell the handler to use this format
                handler.setFormatter(formatter)

                # add the handler to the root logger
                logging.getLogger().addHandler(handler)
                logging.getLogger().setLevel(logging.INFO)
        elif os.name != 'nt':
            reverse = '\x1b[7m'
            reset = '\x1b[0m'
            # reverse color for error and critical messages
            for level in logging.ERROR, logging.CRITICAL:
                msg = reverse + logging.getLevelName(level) + reset
                logging.addLevelName(level, msg)

        self.logger = logging.getLogger("server")

        if CONFIG.configfile:
            self.logger.info('using %s as configuration file' % \
                    CONFIG.configfile)
        else:
            self.logger.info('using default configuration')
        self.logger.info('initialising distributed objects services')

    def run(self):
        "Run the server and never return"
        from trytond.backend import Database
        from trytond.pool import Pool
        from trytond.monitor import monitor

        update = False
        init = {}

        if not CONFIG["db_name"] \
                and bool(CONFIG['init'] or CONFIG['update']):
            raise Exception('Missing database option!')

        for db_name in CONFIG["db_name"]:
            init[db_name] = False
            database = Database(db_name).connect()
            cursor = database.cursor()

            try:
                if CONFIG['init']:
                    if not cursor.test():
                        self.logger.info("init db")
                        Database.init(cursor)
                        init[db_name] = True
                    cursor.commit()
                elif not cursor.test():
                    raise Exception("'%s' is not a Tryton database!" % db_name)
            finally:
                cursor.close()

        Pool.start()

        for db_name in CONFIG["db_name"]:
            cursor = Database(db_name).connect().cursor()
            try:
                if not cursor.test():
                    raise Exception("'%s' is not a Tryton database!" % db_name)
                cursor.execute('SELECT code FROM ir_lang ' \
                        'WHERE translatable')
                lang = [x[0] for x in cursor.fetchall()]
            finally:
                cursor.close()
            update = bool(CONFIG['init'] or CONFIG['update'])
            Pool(db_name).init(update=update, lang=lang)

        for kind in ('init', 'update'):
            CONFIG[kind] = {}

        for db_name in CONFIG['db_name']:
            if init[db_name]:
                while True:
                    password = getpass('Admin Password for %s: ' % db_name)
                    password2 = getpass('Admin Password Confirmation: ')
                    if password != password2:
                        sys.stderr.write('Admin Password Confirmation ' \
                                'doesn\'t match Admin Password!\n')
                        continue
                    if not password:
                        sys.stderr.write('Admin Password is required!\n')
                        continue
                    break

                database = Database(db_name).connect()
                cursor = database.cursor()
                try:
                    salt = ''.join(random.sample(
                        string.letters + string.digits, 8))
                    password += salt
                    if hashlib:
                        password = hashlib.sha1(password).hexdigest()
                    else:
                        password = sha.new(password).hexdigest()
                    cursor.execute('UPDATE res_user ' \
                            'SET password = %s, salt = %s ' \
                            'WHERE login = \'admin\'', (password, salt))
                    cursor.commit()
                finally:
                    cursor.close()

        if update:
            self.logger.info('Update/Init succeed!')
            logging.shutdown()
            sys.exit(0)

        # Launch Server
        jsonrpcd = []
        if CONFIG['jsonrpc']:
            from trytond.protocols.jsonrpc import JSONRPCDaemon
            for hostname, port in CONFIG['jsonrpc']:
                jsonrpcd.append(JSONRPCDaemon(hostname, port,
                    CONFIG['ssl_jsonrpc']))
                self.logger.info("starting JSON-RPC%s protocol on %s:%d" %
                    (CONFIG['ssl_jsonrpc'] and ' SSL' or '', hostname or '*',
                        port))

        xmlrpcd = []
        if CONFIG['xmlrpc']:
            from trytond.protocols.xmlrpc import XMLRPCDaemon
            for hostname, port in CONFIG['xmlrpc']:
                xmlrpcd.append(XMLRPCDaemon(hostname, port,
                    CONFIG['ssl_xmlrpc']))
                self.logger.info("starting XML-RPC%s protocol on %s:%d" %
                    (CONFIG['ssl_xmlrpc'] and ' SSL' or '', hostname or '*',
                        port))

        webdavd = []
        if CONFIG['webdav']:
            from trytond.protocols.webdav import WebDAVServerThread
            for hostname, port in CONFIG['webdav']:
                webdavd.append(WebDAVServerThread(hostname, port,
                    CONFIG['ssl_webdav']))
                self.logger.info("starting WebDAV%s protocol on %s:%d" %
                    (CONFIG['ssl_webdav'] and ' SSL' or '', hostname or '*',
                        port))

        def handler(signum, frame):
            if hasattr(signal, 'SIGUSR1'):
                if signum == signal.SIGUSR1:
                    Pool.start()
                    return
            for servers in (xmlrpcd, jsonrpcd, webdavd):
                for server in servers:
                    server.stop()
                    server.join()
            if CONFIG['pidfile']:
                os.unlink(CONFIG['pidfile'])
            logging.getLogger('server').info('stopped')
            logging.shutdown()
            sys.exit(0)

        if CONFIG['pidfile']:
            with open(CONFIG['pidfile'], 'w') as fd_pid:
                fd_pid.write("%d" % (os.getpid()))

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)
        if hasattr(signal, 'SIGQUIT'):
            signal.signal(signal.SIGQUIT, handler)
        if hasattr(signal, 'SIGUSR1'):
            signal.signal(signal.SIGUSR1, handler)

        self.logger.info('waiting for connections...')
        for servers in (xmlrpcd, jsonrpcd, webdavd):
            for server in servers:
                server.start()

        if CONFIG['psyco']:
            import psyco
            psyco.full()

        threads = {}
        while True:
            if CONFIG['auto_reload'] and monitor():
                try:
                    Pool.start()
                except Exception:
                    pass
            if CONFIG['cron']:
                for dbname in Pool.database_list():
                    thread = threads.get(dbname)
                    if thread and thread.is_alive():
                        continue
                    pool = Pool(dbname)
                    if 'ir.cron' not in pool.object_name_list():
                        continue
                    cron_obj = pool.get('ir.cron')
                    thread = threading.Thread(
                            target=cron_obj.run,
                            args=(dbname,), kwargs={})
                    thread.start()
                    threads[dbname] = thread
            time.sleep(60)
