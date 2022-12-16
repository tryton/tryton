#!/usr/bin/env python3
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import argparse
import os
import time
import unittest
import sys

from trytond.config import config

if __name__ != '__main__':
    raise ImportError('%s can not be imported' % __name__)

logging.disable(logging.CRITICAL)
parser = argparse.ArgumentParser()
parser.add_argument("-c", "--config", dest="config",
    help="specify config file")
parser.add_argument("-f", "--failfast", action="store_true", dest="failfast",
    help="Stop the test run on the first error or failure")
parser.add_argument("-m", "--modules", action="store_true", dest="modules",
    default=False, help="Run also modules tests")
parser.add_argument("--no-doctest", action="store_false", dest="doctest",
    default=True, help="Don't run doctest")
parser.add_argument("-v", action="count", default=0, dest="verbosity",
    help="Increase verbosity")
parser.add_argument('tests', metavar='test', nargs='*')
parser.epilog = ('The database name can be specified in the DB_NAME '
    'environment variable.\n'
    "A database dump cache directory can be specified in the DB_CACHE "
    "environment variable. Dumps will be used to speed up re-run of tests.")
opt = parser.parse_args()

config.update_etc(opt.config)

# Import after application is configured
from trytond import backend  # noqa: E402
if backend.name == 'sqlite':
    database_name = ':memory:'
else:
    database_name = 'test_' + str(int(time.time()))
os.environ.setdefault('DB_NAME', database_name)

from trytond.tests.test_tryton import all_suite, modules_suite  # noqa: E402
if not opt.modules:
    suite = all_suite(opt.tests)
else:
    suite = modules_suite(opt.tests, doc=opt.doctest)
result = unittest.TextTestRunner(
    verbosity=opt.verbosity, failfast=opt.failfast).run(suite)
sys.exit(not result.wasSuccessful())
