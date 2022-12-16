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

    def __init__(self):
        format = '[%(asctime)s] %(levelname)s:%(name)s:%(message)s'
        datefmt = '%a %b %d %H:%M:%S %Y'
        logging.basicConfig(level=logging.DEBUG, format=format,
                datefmt=datefmt)

        CONFIG.parse()

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

            if CONFIG['init']:
                if not cursor.test():
                    self.logger.info("init db")
                    Database.init(cursor)
                    init[db_name] = True
                cursor.commit()
                cursor.close()
            elif not cursor.test():
                raise Exception("'%s' is not a Tryton database!" % db_name)

        Pool.start()

        for db_name in CONFIG["db_name"]:
            cursor = Database(db_name).connect().cursor()
            if not cursor.test():
                raise Exception("'%s' is not a Tryton database!" % db_name)
            cursor.execute('SELECT code FROM ir_lang ' \
                    'WHERE translatable')
            lang = [x[0] for x in cursor.fetchall()]
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
                salt = ''.join(random.sample(string.letters + string.digits, 8))
                password += salt
                if hashlib:
                    password = hashlib.sha1(password).hexdigest()
                else:
                    password = sha.new(password).hexdigest()
                cursor.execute('UPDATE res_user ' \
                        'SET password = %s, salt = %s ' \
                        'WHERE login = \'admin\'', (password, salt))
                cursor.commit()
                cursor.close()

        if update:
            self.logger.info('Update/Init succeed!')
            logging.shutdown()
            sys.exit(0)

        # Launch Server
        if CONFIG['xmlrpc']:
            from trytond.protocols.xmlrpc import XMLRPCDaemon
            xmlrpcd = XMLRPCDaemon(CONFIG['interface'], CONFIG['xmlport'],
                    CONFIG['secure_xmlrpc'])
            self.logger.info("starting XML-RPC%s protocol, port %d" % \
                    (CONFIG['secure_xmlrpc'] and ' Secure' or '',
                        CONFIG['xmlport']))

        if CONFIG['jsonrpc']:
            from trytond.protocols.jsonrpc import JSONRPCDaemon
            jsonrpcd = JSONRPCDaemon(CONFIG['interface'], CONFIG['jsonport'],
                    CONFIG['secure_jsonrpc'])
            self.logger.info("starting JSON-RPC%s protocol, port %d" % \
                    (CONFIG['secure_jsonrpc'] and ' Secure' or '',
                        CONFIG['jsonport']))

        if CONFIG['netrpc']:
            from trytond.protocols.netrpc import NetRPCServerThread
            netrpcd = NetRPCServerThread(CONFIG['interface'], CONFIG['netport'],
                    CONFIG['secure_netrpc'])
            self.logger.info("starting NetRPC%s protocol, port %d" % \
                    (CONFIG['secure_netrpc']  and ' Secure' or '',
                        CONFIG['netport']))

        if CONFIG['webdav']:
            from trytond.protocols.webdav import WebDAVServerThread
            webdavd = WebDAVServerThread(CONFIG['interface'],
                    CONFIG['webdavport'], CONFIG['secure_webdav'])
            self.logger.info("starting WebDAV%s protocol, port %d" % \
                    (CONFIG['secure_webdav'] and ' Secure' or '',
                        CONFIG['webdavport']))

        def handler(signum, frame):
            if hasattr(signal, 'SIGUSR1'):
                if signum == signal.SIGUSR1:
                    Pool.start()
                    return
            if CONFIG['netrpc']:
                netrpcd.stop()
            if CONFIG['xmlrpc']:
                xmlrpcd.stop()
            if CONFIG['jsonrpc']:
                jsonrpcd.stop()
            if CONFIG['webdav']:
                webdavd.stop()
            if CONFIG['pidfile']:
                os.unlink(CONFIG['pidfile'])
            for thread in threading.enumerate():
                if thread == threading.currentThread():
                    continue
                thread.join()
            logging.getLogger('server').info('stopped')
            logging.shutdown()
            sys.exit(0)

        if CONFIG['pidfile']:
            fd_pid = open(CONFIG['pidfile'], 'w')
            pidtext = "%d" % (os.getpid())
            fd_pid.write(pidtext)
            fd_pid.close()

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)
        if hasattr(signal, 'SIGQUIT'):
            signal.signal(signal.SIGQUIT, handler)
        if hasattr(signal, 'SIGUSR1'):
            signal.signal(signal.SIGUSR1, handler)

        self.logger.info('waiting for connections...')
        if CONFIG['netrpc']:
            netrpcd.start()
        if CONFIG['xmlrpc']:
            xmlrpcd.start()
        if CONFIG['jsonrpc']:
            jsonrpcd.start()
        if CONFIG['webdav']:
            webdavd.start()

        if CONFIG['psyco']:
            import psyco
            psyco.full()

        while True:
            if CONFIG['auto_reload'] and monitor():
                try:
                    Pool.start()
                except:
                    pass
            for dbname in Pool.database_list():
                pool = Pool(dbname)
                if 'ir.cron' not in pool.object_name_list():
                    continue
                cron_obj = pool.get('ir.cron')
                thread = threading.Thread(
                        target=cron_obj.pool_jobs,
                        args=(dbname,), kwargs={})
                thread.start()
            time.sleep(60)

if __name__ == "__main__":
    SERVER = TrytonServer()
    SERVER.run()
