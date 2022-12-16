# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import sys
import os
import logging
from getpass import getpass

from sql import Table, Literal

from trytond import backend
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.config import config
from trytond.sendmail import send_test_email

__all__ = ['run']
logger = logging.getLogger(__name__)


def run(options):
    main_lang = config.get('database', 'language')
    init = {}
    for db_name in options.database_names:
        init[db_name] = False
        database = backend.Database(db_name)
        database.connect()
        if options.update:
            if not database.test():
                logger.info("init db")
                database.init()
                init[db_name] = True
        elif not database.test():
            raise Exception('"%s" is not a Tryton database.' % db_name)

    for db_name in options.database_names:
        if options.update:
            with Transaction().start(db_name, 0) as transaction,\
                    transaction.connection.cursor() as cursor:
                database = backend.Database(db_name)
                database.connect()
                if not database.test():
                    raise Exception('"%s" is not a Tryton database.' % db_name)
                lang = Table('ir_lang')
                cursor.execute(*lang.select(lang.code,
                        where=lang.translatable == Literal(True)))
                lang = set([x[0] for x in cursor.fetchall()])
            lang.add(main_lang)
        else:
            lang = set()
        lang |= set(options.languages)
        pool = Pool(db_name)
        pool.init(update=options.update, lang=list(lang),
            activatedeps=options.activatedeps)

        if options.update_modules_list:
            with Transaction().start(db_name, 0) as transaction:
                Module = pool.get('ir.module')
                Module.update_list()

        if lang:
            with Transaction().start(db_name, 0) as transaction:
                pool = Pool()
                Lang = pool.get('ir.lang')
                languages = Lang.search([
                        ('code', 'in', lang),
                        ])
                Lang.write(languages, {
                        'translatable': True,
                        })

    for db_name in options.database_names:
        with Transaction().start(db_name, 0) as transaction:
            pool = Pool()
            User = pool.get('res.user')
            Configuration = pool.get('ir.configuration')
            configuration = Configuration(1)
            with transaction.set_context(active_test=False):
                admin, = User.search([('login', '=', 'admin')])

            if options.email is not None:
                admin.email = options.email
            elif init[db_name]:
                admin.email = input(
                    '"admin" email for "%s": ' % db_name)
            if init[db_name] or options.password:
                configuration.language = main_lang
                # try to read password from environment variable
                # TRYTONPASSFILE, empty TRYTONPASSFILE ignored
                passpath = os.getenv('TRYTONPASSFILE')
                password = ''
                if passpath:
                    try:
                        with open(passpath) as passfile:
                            password, = passfile.read().splitlines()
                    except Exception as err:
                        sys.stderr.write('Can not read password '
                            'from "%s": "%s"\n' % (passpath, err))

                if not password and not options.reset_password:
                    while True:
                        password = getpass(
                            '"admin" password for "%s": ' % db_name)
                        password2 = getpass('"admin" password confirmation: ')
                        if password != password2:
                            sys.stderr.write('"admin" password confirmation '
                                'doesn\'t match "admin" password.\n')
                            continue
                        if not password:
                            sys.stderr.write('"admin" password is required.\n')
                            continue
                        break
                if not options.reset_password:
                    admin.password = password
            admin.save()
            if options.reset_password:
                User.reset_password([admin])
            if options.test_email:
                send_test_email(options.test_email)
            if options.hostname is not None:
                configuration.hostname = options.hostname or None
            configuration.save()
