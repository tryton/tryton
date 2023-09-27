# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import os
import random
import sys
from getpass import getpass

from sql import Literal, Table

from trytond import backend
from trytond.config import config
from trytond.pool import Pool
from trytond.sendmail import send_test_email
from trytond.transaction import Transaction, TransactionError, inactive_records

__all__ = ['run']
logger = logging.getLogger(__name__)


def run(options):
    main_lang = config.get('database', 'language')
    init = {}

    if options.test_email:
        send_test_email(options.test_email)

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
            with Transaction().start(db_name, 0) as transaction, \
                    transaction.connection.cursor() as cursor:
                database = backend.Database(db_name)
                database.connect()
                if not database.test():
                    raise Exception('"%s" is not a Tryton database.' % db_name)
                lang = Table('ir_lang')
                cursor.execute(*lang.select(lang.code,
                        where=lang.translatable == Literal(True)))
                lang = set([x[0] for x in cursor])
            lang.add(main_lang)
        else:
            lang = set()
        lang |= set(options.languages)
        pool = Pool(db_name)
        pool.init(update=options.update, lang=list(lang),
            activatedeps=options.activatedeps,
            indexes=options.indexes)

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
        if options.email is not None:
            email = options.email
        elif init[db_name]:
            email = input(
                '"admin" email for "%s": ' % db_name)
        else:
            email = None

        password = ''
        if init[db_name] or options.password:
            # try to read password from environment variable
            # TRYTONPASSFILE, empty TRYTONPASSFILE ignored
            passpath = os.getenv('TRYTONPASSFILE')
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

        transaction_extras = {}
        while True:
            with Transaction().start(
                    db_name, 0, **transaction_extras) as transaction:
                try:
                    pool = Pool()
                    User = pool.get('res.user')
                    Configuration = pool.get('ir.configuration')
                    configuration = Configuration(1)
                    with inactive_records():
                        admin, = User.search([('login', '=', 'admin')])

                    if email is not None:
                        admin.email = email
                    if init[db_name] or options.password:
                        configuration.language = main_lang
                        if not options.reset_password:
                            admin.password = password
                    admin.save()
                    if options.reset_password:
                        User.reset_password([admin])
                    if options.hostname is not None:
                        configuration.hostname = options.hostname or None
                    configuration.save()
                except TransactionError as e:
                    transaction.rollback()
                    e.fix(transaction_extras)
                    continue
                break
        with Transaction().start(db_name, 0, readonly=True):
            if options.validate is not None:
                validate(options.validate, options.validate_percentage)


def validate(models, percentage=100):
    from trytond.model import ModelSingleton, ModelStorage
    from trytond.model.exceptions import ValidationError
    logger = logging.getLogger('validate')
    pool = Pool()
    if not models:
        models = sorted([n for n, _ in pool.iterobject()])
    ratio = min(100, percentage) / 100
    in_max = Transaction().database.IN_MAX
    for name in models:
        logger.info("validate: %s", name)
        Model = pool.get(name)
        if not issubclass(Model, ModelStorage):
            continue
        offset = 0
        limit = in_max
        while True:
            records = Model.search(
                [], order=[('id', 'ASC')], offset=offset, limit=limit)
            if not records:
                break
            records = Model.browse(
                random.sample(records, int(len(records) * ratio)))
            try:
                for record in records:
                    try:
                        Model._validate([record])
                    except ValidationError as exception:
                        logger.error("%s: KO '%s'", record, exception)
                    else:
                        logger.info("%s: OK", record)
            except TransactionError:
                logger.info("%s: SKIPPED", name)
                break
            if issubclass(Model, ModelSingleton):
                break
            offset += limit
