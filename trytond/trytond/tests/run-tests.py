#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import logging
import argparse
import os
import time
import unittest
import sys

from trytond.config import CONFIG

if __name__ != '__main__':
    raise ImportError('%s can not be imported' % __name__)

logging.basicConfig(level=logging.ERROR)
parser = argparse.ArgumentParser()
parser.add_argument("-c", "--config", dest="config",
    help="specify config file")
parser.add_argument("-m", "--modules", action="store_true", dest="modules",
    default=False, help="Run also modules tests")
parser.add_argument("-v", action="count", default=0, dest="verbosity",
    help="Increase verbosity")
parser.add_argument('tests', metavar='test', nargs='*')
opt = parser.parse_args()

CONFIG['db_type'] = 'sqlite'
CONFIG.update_etc(opt.config)
if not CONFIG['admin_passwd']:
    CONFIG['admin_passwd'] = 'admin'

if CONFIG['db_type'] == 'sqlite':
    database_name = ':memory:'
else:
    database_name = 'test_' + str(int(time.time()))
os.environ['DB_NAME'] = database_name

from trytond.tests.test_tryton import all_suite, modules_suite
if not opt.modules:
    suite = all_suite(opt.tests)
else:
    suite = modules_suite(opt.tests)
result = unittest.TextTestRunner(verbosity=opt.verbosity).run(suite)
sys.exit(not result.wasSuccessful())
