# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import argparse
import os
import logging
import logging.config
import logging.handlers
from contextlib import contextmanager

from trytond import __version__

logger = logging.getLogger(__name__)


def get_parser():
    parser = argparse.ArgumentParser()

    parser.add_argument('--version', action='version',
        version='%(prog)s ' + __version__)
    parser.add_argument("-c", "--config", dest="configfile", metavar='FILE',
        default=os.environ.get('TRYTOND_CONFIG'), help="specify config file")
    parser.add_argument("-v", "--verbose", action="store_true",
        dest="verbose", help="enable verbose mode")
    parser.add_argument('--dev', dest='dev', action='store_true',
        help='enable development mode')

    parser.add_argument("-d", "--database", dest="database_names", nargs='+',
        default=[], metavar='DATABASE', help="specify the database name")
    parser.add_argument("--logconf", dest="logconf", metavar='FILE',
        help="logging configuration file (ConfigParser format)")

    return parser


def get_parser_daemon():
    parser = get_parser()
    parser.add_argument("--pidfile", dest="pidfile", metavar='FILE',
        help="file where the server pid will be stored")
    return parser


def get_parser_admin():
    parser = get_parser()

    parser.add_argument("-u", "--update", dest="update", nargs='+', default=[],
        metavar='MODULE', help="update a module")
    parser.add_argument("--all", dest="update", action="append_const",
        const="ir", help="update all installed modules")

    parser.epilog = ('The first time a database is initialized admin '
        'password is read from file defined by TRYTONPASSFILE '
        'environment variable or interactively ask user.\n'
        'The config file can be specified in the TRYTOND_CONFIG '
        'environment variable.\n'
        'The database URI can be specified in the TRYTOND_DATABASE_URI '
        'environment variable.')
    return parser


def config_log(options):
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
