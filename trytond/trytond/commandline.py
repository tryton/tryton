# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import argparse
import csv
import logging
import logging.config
import logging.handlers
import os
import os.path
from contextlib import contextmanager
from io import StringIO

from trytond import __version__

logger = logging.getLogger(__name__)


def database_completer(parsed_args, **kwargs):
    from trytond.config import config
    from trytond.transaction import Transaction
    config.update_etc(parsed_args.configfile)
    with Transaction().start(
            None, 0, readonly=True, close=True) as transaction:
        return transaction.database.list()


def module_completer(**kwargs):
    from trytond.modules import get_modules
    return get_modules()


def language_completer(**kwargs):
    files = os.listdir(os.path.join(os.path.dirname(__file__), 'ir', 'locale'))
    return [os.path.splitext(f)[0] for f in files]


def get_base_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', action='version',
        version='%(prog)s ' + __version__)
    parser.add_argument("-c", "--config", dest="configfile", metavar='FILE',
        nargs='+', default=[os.environ.get('TRYTOND_CONFIG')],
        help="specify configuration files")
    return parser


def get_parser():
    parser = get_base_parser()

    parser.add_argument("-v", "--verbose", action='count',
        dest="verbose", default=0, help="increase verbosity")
    parser.add_argument('--dev', dest='dev', action='store_true',
        help='enable development mode')

    logging_config = os.environ.get('TRYTOND_LOGGING_CONFIG')
    db_names = os.environ.get('TRYTOND_DATABASE_NAMES')
    if db_names:
        db_names = list(next(csv.reader(StringIO(db_names))))
    else:
        db_names = []
    parser.add_argument(
        "-d", "--database", dest="database_names", nargs='+',
        default=db_names, metavar='DATABASE',
        help="specify the database names").completer = database_completer
    parser.add_argument(
        "--logconf", dest="logconf", default=logging_config, metavar='FILE',
        help="set logging configuration file (ConfigParser format)")

    return parser


def get_parser_daemon():
    parser = get_parser()
    parser.add_argument("--pidfile", dest="pidfile", metavar='FILE',
        help="set file to store the process id")
    parser.add_argument(
        "--coroutine", action="store_true", dest="coroutine",
        default=bool(os.environ.get('TRYTOND_COROUTINE', False)),
        help="use coroutine for concurrency")
    return parser


def get_parser_worker():
    parser = get_parser_daemon()
    parser.add_argument("--name", dest='name',
        help="work only on the named queue")
    parser.add_argument("-n", dest='processes', type=int,
        help="set number of processes to use")
    parser.add_argument("--max", dest='maxtasksperchild', type=int,
        help="set number of tasks a worker process before being replaced")
    parser.add_argument("-t", "--timeout", dest='timeout', default=60,
        type=int, help="set maximum timeout when waiting notification")
    return parser


def get_parser_cron():
    parser = get_parser_daemon()
    parser.add_argument("-1", "--once", dest='once', action='store_true',
        help="run pending tasks and halt")
    return parser


def get_parser_admin():
    parser = get_parser()

    parser.add_argument(
        "-u", "--update", dest="update", nargs='+', default=[],
        metavar='MODULE',
        help="activate or update modules").completer = module_completer
    parser.add_argument(
        "--indexes", dest="indexes",
        action=getattr(argparse, 'BooleanOptionalAction', 'store_true'),
        default=None, help="update indexes")
    parser.add_argument("--all", dest="update", action="append_const",
        const="ir", help="update all activated modules")
    parser.add_argument("--activate-dependencies", dest="activatedeps",
        action="store_true",
        help="activate missing dependencies of updated modules")
    parser.add_argument("--email", dest="email", help="set the admin email")
    parser.add_argument("-p", "--password", dest="password",
        action='store_true', help="set the admin password")
    parser.add_argument("--reset-password", dest='reset_password',
        action='store_true', help="reset the admin password")
    parser.add_argument("--test-email", dest='test_email',
        help="send a test email to the specified address")
    parser.add_argument("-m", "--update-modules-list", action="store_true",
        dest="update_modules_list", help="update the list of tryton modules")
    parser.add_argument(
        "-l", "--language", dest="languages", nargs='+',
        default=[], metavar='CODE',
        help="load language translations").completer = language_completer
    parser.add_argument("--hostname", dest="hostname", default=None,
        help="limit database listing to the hostname")
    parser.add_argument("--validate", dest="validate", nargs='*',
        metavar='MODEL', help="validate records of models")
    parser.add_argument("--validate-percentage", dest="validate_percentage",
        type=float, default=100, metavar="PERCENTAGE",
        help="percentage of records to validate (default: 100)")

    parser.epilog = ('The first time a database is initialized '
        'or when the password is set, the admin password is read '
        'from file defined by TRYTONPASSFILE environment variable '
        'or interactively asked from the user.\n'
        'The config file can be specified in the TRYTOND_CONFIG '
        'environment variable.\n'
        'The database URI can be specified in the TRYTOND_DATABASE_URI '
        'environment variable.')
    return parser


def get_parser_console():
    parser = get_base_parser()
    parser.add_argument(
        "-d", "--database", dest="database_name",
        required=True, metavar='DATABASE',
        help="specify the database name").completer = database_completer
    parser.add_argument("--histsize", dest="histsize", type=int, default=500,
        help="set the number of commands to remember in the command history")
    parser.add_argument("--readonly", dest="readonly", action='store_true',
        help="start a readonly transaction")
    parser.add_argument(
        "--lock-table", dest="lock_tables", nargs='+', default=[],
        metavar='TABLE', help="lock tables")
    parser.epilog = "To store changes, `transaction.commit()` must be called."
    return parser


def get_parser_stat():
    parser = get_base_parser()
    parser.epilog = "To exit press 'q', to inverse sort order press 'r'."
    return parser


def config_log(options):
    if options.logconf:
        logging.config.fileConfig(
            options.logconf, disable_existing_loggers=False)
        logging.getLogger('server').info('using %s as logging '
            'configuration file', options.logconf)
    else:
        logformat = ('%(process)s %(thread)s [%(asctime)s] '
            '%(levelname)s %(name)s %(message)s')
        if not options.verbose and 'TRYTOND_LOGGING_LEVEL' in os.environ:
            logging_level = int(os.environ['TRYTOND_LOGGING_LEVEL'])
            level = max(logging_level, logging.NOTSET)
        else:
            level = max(logging.ERROR - options.verbose * 10, logging.NOTSET)
        logging.basicConfig(level=level, format=logformat)
    logging.captureWarnings(True)


@contextmanager
def pidfile(options):
    path = options.pidfile
    if not path:
        yield
    else:
        with open(path, 'w') as fd:
            fd.write('%d' % os.getpid())
        yield
        os.unlink(path)
