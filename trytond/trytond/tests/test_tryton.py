# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import os
import sys
import unittest
import doctest
from lxml import etree

from trytond.pool import Pool
from trytond import backend
from trytond.protocols.dispatcher import create, drop
from trytond.transaction import Transaction
from trytond.pyson import PYSONEncoder, Eval
from trytond.exceptions import UserError
from trytond import security

__all__ = ['POOL', 'DB_NAME', 'USER', 'USER_PASSWORD', 'CONTEXT',
    'install_module', 'test_view', 'test_depends',
    'doctest_setup', 'doctest_teardown',
    'suite', 'all_suite', 'modules_suite']

Pool.start()
USER = 1
USER_PASSWORD = 'admin'
CONTEXT = {}
DB_NAME = os.environ['DB_NAME']
DB = backend.get('Database')(DB_NAME)
Pool.test = True
POOL = Pool(DB_NAME)
security.check_super = lambda *a, **k: True


class ModelViewTestCase(unittest.TestCase):
    'Test ModelView'

    def setUp(self):
        install_module('ir')
        install_module('res')
        install_module('webdav')

    def test0000test(self):
        'Test test'
        self.assertRaises(UserError, install_module, 'nosuchmodule')
        self.assertRaises(UserError, test_view, 'nosuchmodule')

    def test0010ir(self):
        'Test ir'
        test_view('ir')

    def test0020res(self):
        'Test res'
        test_view('res')

    def test0040webdav(self):
        'Test webdav'
        test_view('webdav')


class FieldDependsTestCase(unittest.TestCase):
    'Test Field depends'

    def setUp(self):
        install_module('ir')
        install_module('res')
        install_module('webdav')

    def test0010depends(self):
        'Test depends'
        test_depends()


def install_module(name):
    '''
    Install module for the tested database
    '''
    create_db()
    with Transaction().start(DB_NAME, USER,
            context=CONTEXT) as transaction:
        Module = POOL.get('ir.module.module')

        modules = Module.search([
                ('name', '=', name),
                ])
        assert modules

        modules = Module.search([
                ('name', '=', name),
                ('state', '!=', 'installed'),
                ])

        if not modules:
            return

        Module.install(modules)
        transaction.cursor.commit()

        InstallUpgrade = POOL.get('ir.module.module.install_upgrade',
            type='wizard')
        instance_id, _, _ = InstallUpgrade.create()
        transaction.cursor.commit()
        InstallUpgrade(instance_id).transition_upgrade()
        InstallUpgrade.delete(instance_id)
        transaction.cursor.commit()


def test_view(module_name):
    '''
    Test validity of all views of the module
    '''
    with Transaction().start(DB_NAME, USER,
            context=CONTEXT) as transaction:
        View = POOL.get('ir.ui.view')
        views = View.search([
                ('module', '=', module_name),
                ('model', '!=', ''),
                ])
        assert views, "No views for %s" % module_name
        for view in views:
            view_id = view.inherit and view.inherit.id or view.id
            model = view.model
            Model = POOL.get(model)
            res = Model.fields_view_get(view_id)
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
            for fname, field in model._fields.iteritems():
                encoder = Encoder()
                encoder.encode(field.domain)
                if hasattr(field, 'digits'):
                    encoder.encode(field.digits)
                if hasattr(field, 'add_remove'):
                    encoder.encode(field.add_remove)
                encoder.fields.discard(fname)
                encoder.fields.discard('context')
                encoder.fields.discard('_user')
                depends = set(field.depends)
                assert encoder.fields <= depends, (
                    'Missing depends %s in "%s"."%s"' % (
                        list(encoder.fields - depends), mname, fname))
                assert depends <= set(model._fields), (
                    'Unknown depends %s in "%s"."%s"' % (
                        list(depends - set(model._fields)), mname, fname))


def db_exist():
    Database = backend.get('Database')
    database = Database().connect()
    cursor = database.cursor()
    databases = database.list(cursor)
    cursor.close()
    return DB_NAME in databases


def create_db():
    if not db_exist():
        create(DB_NAME, None, 'en_US', USER_PASSWORD)


def drop_db():
    if db_exist():
        drop(DB_NAME, None)


def drop_create():
    if db_exist():
        drop_db()
    create_db()

doctest_setup = lambda test: drop_create()
doctest_teardown = lambda test: drop_db()


def suite():
    '''
    Return test suite for other modules
    '''
    return unittest.TestSuite()


def all_suite(modules=None):
    '''
    Return all tests suite of current module
    '''
    suite_ = suite()
    for fn in os.listdir(os.path.dirname(__file__)):
        if fn.startswith('test_') and fn.endswith('.py'):
            if modules and fn[:-3] not in modules:
                continue
            modname = 'trytond.tests.' + fn[:-3]
            __import__(modname)
            module = module = sys.modules[modname]
            suite_.addTest(module.suite())
    return suite_


def modules_suite(modules=None):
    '''
    Return all tests suite of all modules
    '''
    if modules:
        suite_ = suite()
    else:
        suite_ = all_suite()
    from trytond.modules import create_graph, get_module_list, \
        MODULES_PATH, EGG_MODULES
    graph = create_graph(get_module_list())[0]
    for package in graph:
        module = package.name
        if modules and module not in modules:
            continue
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
