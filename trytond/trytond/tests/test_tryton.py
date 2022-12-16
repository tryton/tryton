#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import logging
logging.basicConfig(level=logging.ERROR)
import sys, os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
from lxml import etree
import time
import imp
import zipimport

_MODULES = False
if __name__ == '__main__':
    if '--modules' in sys.argv:
        sys.argv.remove('--modules')
        _MODULES = True

from trytond.config import CONFIG
CONFIG['db_type'] = 'sqlite'
CONFIG.parse()
if not CONFIG['admin_passwd']:
    CONFIG['admin_passwd'] = 'admin'

from trytond.modules import register_classes
from trytond.pool import Pool
from trytond.backend import Database
from trytond.protocols.dispatcher import create

register_classes()

if CONFIG['db_type'] == 'sqlite':
    DB_NAME = ':memory:'
else:
    DB_NAME = 'test_' + str(int(time.time()))
USER = 1
USER_PASSWORD = 'admin'
CONTEXT = {}
DB = Database(DB_NAME)
Pool.test = True
POOL = Pool(DB_NAME)


class ModelViewTestCase(unittest.TestCase):
    '''
    Test ModelView
    '''

    def setUp(self):
        install_module('ir')
        install_module('res')
        install_module('workflow')
        install_module('webdav')

    def test0010ir(self):
        '''
        Test ir.
        '''
        test_view('ir')

    def test0020res(self):
        '''
        Test res.
        '''
        test_view('res')

    def test0030workflow(self):
        '''
        Test workflow.
        '''
        test_view('workflow')

    def test0040webdav(self):
        '''
        Test webdav.
        '''
        test_view('webdav')

def install_module(name):
    '''
    Install module for the tested database
    '''
    database = Database().connect()
    cursor = database.cursor()
    databases = database.list(cursor)
    cursor.close()
    if DB_NAME not in databases:
        create(DB_NAME, CONFIG['admin_passwd'], 'en_US', USER_PASSWORD)
    cursor = DB.cursor()
    module_obj = POOL.get('ir.module.module')
    module_ids = module_obj.search(cursor, USER, [
        ('name', '=', name),
        ('state', '!=', 'installed'),
        ])

    if not module_ids:
        cursor.close()
        return

    module_obj.button_install(cursor, USER, module_ids, CONTEXT)
    cursor.commit()

    install_upgrade_obj = POOL.get('ir.module.module.install_upgrade',
            type='wizard')
    wiz_id = install_upgrade_obj.create(cursor, USER)
    cursor.commit()
    install_upgrade_obj.execute(cursor, USER, wiz_id, {}, 'start', CONTEXT)
    cursor.commit()
    install_upgrade_obj.delete(cursor, USER, wiz_id)
    cursor.commit()
    cursor.close()

def test_view(module_name):
    '''
    Test validity of all views of the module
    '''
    cursor = DB.cursor()
    view_obj = POOL.get('ir.ui.view')
    view_ids = view_obj.search(cursor, USER, [
        ('module', '=', module_name),
        ])

    for view in view_obj.browse(cursor, USER, view_ids, context=CONTEXT):
        view_id = view.inherit and view.inherit.id or view.id
        model = view.model
        model_obj = POOL.get(model)
        res = model_obj.fields_view_get(cursor, USER, view_id, context=CONTEXT)
        assert res['model'] == model
        tree = etree.fromstring(res['arch'])
        tree_root = tree.getroottree().getroot()

        for element in tree_root.iter():
            if element.tag in ('field', 'label', 'separator', 'group'):
                for attr in ('name', 'icon'):
                    field = element.get(attr)
                    if field:
                        assert field in res['fields']
    cursor.rollback()
    cursor.close()

def suite():
    '''
    Return test suite for other modules
    '''
    return unittest.TestSuite()

def all_suite():
    '''
    Return all tests suite of current module
    '''
    suite_ = suite()
    import trytond.tests.test_tools as test_tools
    suite_.addTests(test_tools.suite())
    import trytond.tests.test_pyson as test_pyson
    suite_.addTests(test_pyson.suite())
    import trytond.tests.test_fields as test_fields
    suite_.addTests(test_fields.suite())
    import trytond.tests.test_modelsingleton as test_modelsingleton
    suite_.addTests(test_modelsingleton.suite())
    suite_.addTests(unittest.TestLoader(
        ).loadTestsFromTestCase(ModelViewTestCase))
    import trytond.tests.test_mptt as test_mptt
    suite_.addTests(test_mptt.suite())
    import trytond.tests.test_importdata as test_importdata
    suite_.addTests(test_importdata.suite())
    import trytond.tests.test_exportdata as test_exportdata
    suite_.addTests(test_exportdata.suite())
    import trytond.tests.test_protocols_datatype as test_protocols_datatype
    suite_.addTests(test_protocols_datatype.suite())
    return suite_

def modules_suite():
    '''
    Return all tests suite of all modules
    '''
    suite_ = all_suite()
    from trytond.modules import create_graph, get_module_list, \
            MODULES_PATH, EGG_MODULES
    graph = create_graph(get_module_list())[0]
    for package in graph:
        module = package.name
        test_module = 'trytond.modules.%s.tests' % module
        if os.path.isfile(os.path.join(MODULES_PATH, module + '.zip')):
            mod_path = os.path.join(MODULES_PATH, module + '.zip')
            zimp = zipimport.zipimporter(mod_path)
            try:
                test_mod = zimp.load_module(test_module)
            except zipimport.ZipImportError:
                continue
        elif os.path.isdir(os.path.join(MODULES_PATH, module)) or \
                module in EGG_MODULES:
            try:
                test_mod = __import__(test_module, fromlist=[''])
            except ImportError:
                continue
        else:
            continue
        for test in test_mod.suite():
            if hasattr(test, '__eq__'):
                if test not in suite_:
                    suite_.addTest(test)
            else:
                found = False
                for other in suite_:
                    if type(test) == type(other) and \
                            test._testMethodName == other._testMethodName:
                        found = True
                        break
                if not found:
                    suite_.addTest(test)
    return suite_

if __name__ == '__main__':
    if not _MODULES:
        _SUITE = all_suite()
    else:
        _SUITE = modules_suite()
    unittest.TextTestRunner(verbosity=2).run(_SUITE)
