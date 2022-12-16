#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
# -*- coding: utf-8 -*-
import logging
import threading
from trytond.netsvc import Service
from trytond import security
from trytond import sql_db
from trytond import pooler
from trytond import tools
import base64
import os
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sha


class DB(Service):

    def __init__(self, name="db"):
        super(DB, self).__init__(name)
        self.join_group("web-service")
        self.export_method(self.create)
        self.export_method(self.drop)
        self.export_method(self.dump)
        self.export_method(self.restore)
        self.export_method(self.list)
        self.export_method(self.list_lang)
        self.export_method(self.db_exist)
        self.export_method(self.change_admin_password)

    def create(self, password, db_name, lang, admin_password):
        security.check_super(password)
        res = False
        logger = logging.getLogger('web-service')

        database = sql_db.db_connect('template1')
        cursor = database.cursor()
        cursor.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        try:
            try:
                cursor.execute('CREATE DATABASE "' + db_name + '" '\
                        'TEMPLATE template0 ENCODING \'unicode\'')
                cursor.commit()
                cursor.close()

                cursor = sql_db.db_connect(db_name).cursor()
                sql_db.init_db(cursor)
                cursor.commit()
                cursor.close()
                cursor = None
                pool = pooler.get_pool(db_name, update_module=True, lang=[lang])
                cursor = sql_db.db_connect(db_name).cursor()
                if lang != 'en_US':
                    cursor.execute('UPDATE ir_lang ' \
                            'SET translatable = True ' \
                            'WHERE code = %s', (lang,))
                cursor.execute('UPDATE res_user ' \
                        'SET language = ' \
                            '(SELECT id FROM ir_lang WHERE code = %s LIMIT 1) '\
                        'WHERE login <> \'root\'', (lang,))
                cursor.execute('UPDATE res_user ' \
                        'SET password = %s ' \
                        'WHERE login = \'admin\'',
                        (sha.new(admin_password).hexdigest(),))
                module_obj = pool.get('ir.module.module')
                if module_obj:
                    module_obj.update_list(cursor, 0)
                cursor.commit()
                res = True
            except:
                logger.error('CREATE DB: %s failed' % (db_name,))
                import traceback, sys
                tb_s = reduce(lambda x, y: x+y,
                        traceback.format_exception(*sys.exc_info()))
                logger.error('Exception in call: \n' + tb_s)
                raise
            else:
                logger.info('CREATE DB: %s' % (db_name,))
        finally:
            if cursor:
                cursor.close()
        return res

    def drop(self, password, db_name):
        security.check_super(password)
        pooler.close_db(db_name)
        logger = logging.getLogger('web-service')

        database = sql_db.db_connect('template1')
        cursor = database.cursor()
        cursor.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        try:
            try:
                cursor.execute('DROP DATABASE "' + db_name + '"')
                cursor.commit()
            except:
                logger.error('DROP DB: %s failed' % (db_name,))
                import traceback, sys
                tb_s = reduce(lambda x, y: x+y,
                        traceback.format_exception(*sys.exc_info()))
                logger.error('Exception in call: \n' + tb_s)
                raise
            else:
                logger.info('DROP DB: %s' % (db_name))
        finally:
            cursor.close()
        return True

    def dump(self, password, db_name):
        security.check_super(password)
        logger = logging.getLogger('web-service')

        if tools.CONFIG['db_password']:
            logger.error('DUMP DB: %s doesn\'t work with password' % (db_name,))
            raise Exception, "Couldn't dump database with password"

        cmd = ['pg_dump', '--format=c']
        if tools.CONFIG['db_user']:
            cmd.append('--username=' + tools.CONFIG['db_user'])
        if tools.CONFIG['db_host']:
            cmd.append('--host=' + tools.CONFIG['db_host'])
        if tools.CONFIG['db_port']:
            cmd.append('--port=' + tools.CONFIG['db_port'])
        cmd.append(db_name)

        stdin, stdout = tools.exec_pg_command_pipe(*tuple(cmd))
        stdin.close()
        data = stdout.read()
        res = stdout.close()
        if res:
            logger.error('DUMP DB: %s failed\n%s' % (db_name, data))
            raise Exception, "Couldn't dump database"
        logger.info('DUMP DB: %s' % (db_name))
        return base64.encodestring(data)

    def restore(self, password, db_name, data):
        security.check_super(password)
        logger = logging.getLogger('web-service')

        if self.db_exist(db_name):
            logger.warning('RESTORE DB: %s already exists' % (db_name,))
            raise Exception, "Database already exists"

        if tools.CONFIG['db_password']:
            logger.error(
                'RESTORE DB: %s doesn\'t work with password' % (db_name,))
            raise Exception, "Couldn't restore database with password"

        database = sql_db.db_connect('template1')
        cursor = database.cursor()
        cursor.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor.execute('CREATE DATABASE "' + db_name + '" ' \
                'TEMPLATE template0 ENCODING \'unicode\'')
        cursor.commit()
        cursor.close()

        cmd = ['pg_restore']
        if tools.CONFIG['db_user']:
            cmd.append('--username=' + tools.CONFIG['db_user'])
        if tools.CONFIG['db_host']:
            cmd.append('--host=' + tools.CONFIG['db_host'])
        if tools.CONFIG['db_port']:
            cmd.append('--port=' + tools.CONFIG['db_port'])
        cmd.append('--dbname=' + db_name)
        args2 = tuple(cmd)

        buf = base64.decodestring(data)
        if os.name == "nt":
            tmpfile = (os.environ['TMP'] or 'C:\\') + os.tmpnam()
            file(tmpfile, 'wb').write(buf)
            args2 = list(args2)
            args2.append(' ' + tmpfile)
            args2 = tuple(args2)
        stdin, stdout = tools.exec_pg_command_pipe(*args2)
        if not os.name == "nt":
            stdin.write(base64.decodestring(data))
        stdin.close()
        res = stdout.close()
        if res:
            raise Exception, "Couldn't restore database"
        cursor = pooler.get_db_only(db_name, verbose=False).cursor()
        if not cursor.test():
            cursor.close()
            pooler.close_db(db_name)
            raise Exception, "Couldn't restore database"
        cursor.close()
        pooler.close_db(db_name)
        logger.info('RESTORE DB: %s' % (db_name))
        return True

    def db_exist(self, db_name):
        try:
            database = sql_db.db_connect(db_name)
            cursor = database.cursor()
            cursor.close()
            return True
        except:
            return False

    def list(self):
        database = sql_db.db_connect('template1')
        try:
            cursor = database.cursor()
            db_user = tools.CONFIG["db_user"]
            if not db_user and os.name == 'posix':
                import pwd
                db_user = pwd.getpwuid(os.getuid())[0]
            if not db_user:
                cursor.execute("SELECT usename " \
                        "FROM pg_user " \
                        "WHERE usesysid = (" \
                            "SELECT datdba " \
                            "FROM pg_database " \
                            "WHERE datname = %s)",
                            (tools.CONFIG["db_name"],))
                res = cursor.fetchone()
                db_user = res and res[0]
            if db_user:
                cursor.execute("SELECT datname " \
                        "FROM pg_database " \
                        "WHERE datdba = (" \
                            "SELECT usesysid " \
                            "FROM pg_user " \
                            "WHERE usename=%s) " \
                            "AND datname not in " \
                                "('template0', 'template1', 'postgres') " \
                        "ORDER BY datname",
                                (db_user,))
            else:
                cursor.execute("SELECT datname " \
                        "FROM pg_database " \
                        "WHERE datname not in " \
                            "('template0', 'template1','postgres') " \
                        "ORDER BY datname")
            res = []
            for db_name, in cursor.fetchall():
                cursor2 = pooler.get_db_only(db_name, verbose=False).cursor()
                if not cursor2.test():
                    cursor2.close()
                    pooler.close_db(db_name)
                else:
                    cursor2.close()
                    res.append(db_name)
            cursor.close()
        except:
            res = []
        return res

    def change_admin_password(self, old_password, new_password):
        security.check_super(old_password)
        tools.CONFIG['admin_passwd'] = new_password
        tools.CONFIG.save()
        return True

    def list_lang(self):
        return [
            ('de_DE', 'Deutsch'),
            ('en_US', 'English'),
            ('fr_FR', 'Français'),
            ('es_ES', 'Español'),
        ]
