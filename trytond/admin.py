# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import sys
import os
import logging
from getpass import getpass

from sql import Table

from trytond.transaction import Transaction
from trytond import backend
from trytond.pool import Pool

__all__ = ['run']
logger = logging.getLogger(__name__)


def run(options):
    Database = backend.get('Database')
    init = {}
    for db_name in options.database_names:
        init[db_name] = False
        with Transaction().start(db_name, 0):
            database = Database(db_name)
            database.connect()
            if options.update:
                if not database.test():
                    logger.info("init db")
                    database.init()
                    init[db_name] = True
            elif not database.test():
                raise Exception("'%s' is not a Tryton database!" % db_name)

    for db_name in options.database_names:
        if options.update:
            with Transaction().start(db_name, 0) as transaction,\
                    transaction.connection.cursor() as cursor:
                database = Database(db_name)
                database.connect()
                if not database.test():
                    raise Exception("'%s' is not a Tryton database!" % db_name)
                lang = Table('ir_lang')
                cursor.execute(*lang.select(lang.code,
                        where=lang.translatable == True))
                lang = [x[0] for x in cursor.fetchall()]
        else:
            lang = None
        Pool(db_name).init(update=options.update, lang=lang)

    for db_name in options.database_names:
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
