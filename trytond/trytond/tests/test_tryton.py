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
import doctest
from lxml import etree
import time
import imp

_MODULES = False
if __name__ == '__main__':
    if '--modules' in sys.argv:
        sys.argv.remove('--modules')
        _MODULES = True

from trytond.config import CONFIG
CONFIG['db_type'] = 'sqlite'
CONFIG.update_etc()
if not CONFIG['admin_passwd']:
    CONFIG['admin_passwd'] = 'admin'

from trytond.modules import register_classes
from trytond.pool import Pool
from trytond.backend import Database
from trytond.protocols.dispatcher import create
from trytond.transaction import Transaction
from trytond.pyson import PYSONEncoder, Eval

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

    def test0000test(self):
        self.assertRaises(Exception, install_module,'nosuchmodule')
        self.assertRaises(Exception, test_view, 'nosuchmodule')

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


class FieldDependsTestCase(unittest.TestCase):
    '''
    Test Field depends
    '''

    def setUp(self):
        install_module('ir')
        install_module('res')
        install_module('workflow')
        install_module('webdav')

    def test0010depends(self):
        test_depends()


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
    with Transaction().start(DB_NAME, USER,
            context=CONTEXT) as transaction:
        module_obj = POOL.get('ir.module.module')

        module_ids = module_obj.search([
            ('name', '=', name),
            ])
        assert module_ids

        module_ids = module_obj.search([
            ('name', '=', name),
            ('state', '!=', 'installed'),
            ])

        if not module_ids:
            return

        module_obj.button_install(module_ids)
        transaction.cursor.commit()

        install_upgrade_obj = POOL.get('ir.module.module.install_upgrade',
                type='wizard')
        wiz_id = install_upgrade_obj.create()
        transaction.cursor.commit()
        install_upgrade_obj.execute(wiz_id, {}, 'start')
        transaction.cursor.commit()
        install_upgrade_obj.delete(wiz_id)
        transaction.cursor.commit()

def test_view(module_name):
    '''
    Test validity of all views of the module
    '''
    with Transaction().start(DB_NAME, USER,
            context=CONTEXT) as transaction:
        view_obj = POOL.get('ir.ui.view')
        view_ids = view_obj.search([
            ('module', '=', module_name),
            ('model', '!=', ''),
            ])
        assert view_ids, "No views for %s" % module_name
        for view in view_obj.browse(view_ids):
            view_id = view.inherit and view.inherit.id or view.id
            model = view.model
            model_obj = POOL.get(model)
            res = model_obj.fields_view_get(view_id)
            assert res['model'] == model
            tree = etree.fromstring(res['arch'])
            tree_root = tree.getroottree().getroot()

            for element in tree_root.iter():
                if element.tag in ('field', 'label', 'separator', 'group'):
                    for attr in ('name', 'icon'):
                        field = element.get(attr)
                        if field:
                            assert field in res['fields'], ('Missing field: %s'
                                % field)
        transaction.cursor.rollback()

def test_depends():
    '''
    Test for missing depends
    '''
    class Encoder(PYSONEncoder):

        def __init__(self, *args, **kwargs):
            super(Encoder, self).__init__(*args, **kwargs)
            self.fields = set()

        def default(self, obj):
            if isinstance(obj, Eval):
                fname = obj._value
                if not fname.startswith('_parent_'):
                    self.fields.add(fname)
            return super(Encoder, self).default(obj)

    with Transaction().start(DB_NAME, USER, context=CONTEXT):
        for mname, model in Pool().iterobject():
            for fname, field in model._columns.iteritems():
                encoder = Encoder()
                for pyson in (field.domain, field.states):
                    encoder.encode(pyson)
                if hasattr(field, 'digits'):
                    encoder.encode(field.digits)
                encoder.fields.discard(fname)
                encoder.fields.discard('context')
                encoder.fields.discard('_user')
                depends = set(field.depends)
                assert encoder.fields <= depends, (
                    'Missing depends %s in "%s"."%s"' % (
                        list(encoder.fields - depends), mname, fname))

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
    suite_.addTests(unittest.TestLoader(
        ).loadTestsFromTestCase(FieldDependsTestCase))
    import trytond.tests.test_mptt as test_mptt
    suite_.addTests(test_mptt.suite())
    import trytond.tests.test_importdata as test_importdata
    suite_.addTests(test_importdata.suite())
    import trytond.tests.test_exportdata as test_exportdata
    suite_.addTests(test_exportdata.suite())
    import trytond.tests.test_trigger as test_trigger
    suite_.addTests(test_trigger.suite())
    import trytond.tests.test_protocols_datatype as test_protocols_datatype
    suite_.addTests(test_protocols_datatype.suite())
    import trytond.tests.test_sequence as test_sequence
    suite_.addTests(test_sequence.suite())
    import trytond.tests.test_access as test_access
    suite_.addTests(test_access.suite())
    import trytond.tests.test_mixins as test_mixins
    suite_.addTests(test_mixins.suite())
    import trytond.tests.test_workflow as test_workflow
    suite_.addTests(test_workflow.suite())
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
        if os.path.isdir(os.path.join(MODULES_PATH, module)) or \
                module in EGG_MODULES:
            try:
                test_mod = __import__(test_module, fromlist=[''])
            except ImportError:
                continue
        else:
            continue
        for test in test_mod.suite():
            found = False
            for other in suite_:
                if type(test) == type(other):
                    if isinstance(test, doctest.DocTestCase):
                        if str(test) == str(other):
                            found = True
                            break
                    elif test._testMethodName == other._testMethodName:
                        found = True
                        break
            if not found:
                suite_.addTest(test)
    tests = []
    doc_tests = []
    for test in suite_:
        if isinstance(test, doctest.DocTestCase):
            doc_tests.append(test)
        else:
            tests.append(test)
    tests.extend(doc_tests)
    return unittest.TestSuite(tests)

if __name__ == '__main__':
    if not _MODULES:
        _SUITE = all_suite()
    else:
        _SUITE = modules_suite()
    unittest.TextTestRunner(verbosity=2).run(_SUITE)
