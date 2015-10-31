# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import sys
import unittest
import doctest
from itertools import chain
import operator
from lxml import etree

from trytond.pool import Pool
from trytond import backend
from trytond.model import Workflow
from trytond.model.fields import get_eval_fields
from trytond.protocols.dispatcher import create, drop
from trytond.tools import is_instance_method
from trytond.transaction import Transaction
from trytond import security

__all__ = ['POOL', 'DB_NAME', 'USER', 'USER_PASSWORD', 'CONTEXT',
    'install_module', 'ModuleTestCase',
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
        assert modules, "%s not found" % name

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


class ModuleTestCase(unittest.TestCase):
    'Trytond Test Case'
    module = None

    def setUp(self):
        install_module(self.module)

    def test_rec_name(self):
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            for mname, model in Pool().iterobject():
                # Don't test model not registered by the module
                if not any(issubclass(model, cls) for cls in
                        Pool().classes['model'].get(self.module, [])):
                    continue
                # Skip testing default value even if the field doesn't exist
                # as there is a fallback to id
                if model._rec_name == 'name':
                    continue
                assert model._rec_name in model._fields, (
                    'Wrong _rec_name "%s" for %s'
                    % (model._rec_name, mname))

    def test_view(self):
        'Test validity of all views of the module'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            View = POOL.get('ir.ui.view')
            views = View.search([
                    ('module', '=', self.module),
                    ('model', '!=', ''),
                    ])
            for view in views:
                if view.inherit and view.inherit.model == view.model:
                    view_id = view.inherit.id
                else:
                    view_id = view.id
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
                                assert field in res['fields'], (
                                    'Missing field: %s' % field)
            transaction.cursor.rollback()

    def test_depends(self):
        'Test for missing depends'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            for mname, model in Pool().iterobject():
                # Don't test model not registered by the module
                if not any(issubclass(model, cls) for cls in
                        Pool().classes['model'].get(self.module, [])):
                    continue
                for fname, field in model._fields.iteritems():
                    fields = set()
                    fields |= get_eval_fields(field.domain)
                    if hasattr(field, 'digits'):
                        fields |= get_eval_fields(field.digits)
                    if hasattr(field, 'add_remove'):
                        fields |= get_eval_fields(field.add_remove)
                    fields.discard(fname)
                    fields.discard('context')
                    fields.discard('_user')
                    depends = set(field.depends)
                    assert fields <= depends, (
                        'Missing depends %s in "%s"."%s"' % (
                            list(fields - depends), mname, fname))
                    assert depends <= set(model._fields), (
                        'Unknown depends %s in "%s"."%s"' % (
                            list(depends - set(model._fields)), mname, fname))

    def test_menu_action(self):
        'Test that menu actions are accessible to menu\'s group'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            pool = Pool()
            Menu = pool.get('ir.ui.menu')
            ModelData = pool.get('ir.model.data')

            module_menus = ModelData.search([
                    ('model', '=', 'ir.ui.menu'),
                    ('module', '=', self.module),
                    ])
            menus = Menu.browse([mm.db_id for mm in module_menus])
            for menu, module_menu in zip(menus, module_menus):
                if not menu.action_keywords:
                    continue
                menu_groups = set(menu.groups)
                actions_groups = reduce(operator.or_,
                    (set(k.action.groups) for k in menu.action_keywords
                        if k.keyword == 'tree_open'))
                if not actions_groups:
                    continue
                assert menu_groups <= actions_groups, (
                    'Menu "%(menu_xml_id)s" actions are not accessible to '
                    '%(groups)s' % {
                        'menu_xml_id': module_menu.fs_id,
                        'groups': ','.join(g.name
                            for g in menu_groups - actions_groups),
                        })

    def test_model_access(self):
        'Test missing default model access'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            Access = POOL.get('ir.model.access')
            no_groups = {a.model.name for a in Access.search([
                        ('group', '=', None),
                        ])}
            with_groups = {a.model.name for a in Access.search([
                        ('group', '!=', None),
                        ])}

            assert no_groups >= with_groups, (
                'Model "%(models)s" are missing a default access' % {
                    'models': list(with_groups - no_groups),
                    })

    def test_workflow_transitions(self):
        'Test all workflow transitions exist'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            for mname, model in Pool().iterobject():
                # Don't test model not registered by the module
                if not any(issubclass(model, cls) for cls in
                        Pool().classes['model'].get(self.module, [])):
                    continue
                if not issubclass(model, Workflow):
                    continue
                field = getattr(model, model._transition_state)
                if isinstance(field.selection, (tuple, list)):
                    values = field.selection
                else:
                    # instance method may not return all the possible values
                    if is_instance_method(model, field.selection):
                        continue
                    values = getattr(model, field.selection)()
                states = set(dict(values))
                transition_states = set(chain(*model._transitions))
                assert transition_states <= states, (
                    ('Unknown transition states "%(states)s" '
                        'in model "%(model)s". ') % {
                        'states': list(transition_states - states),
                        'model': model.__name__,
                        })


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


def modules_suite(modules=None, doc=True):
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
            if doc:
                doc_tests.append(test)
        else:
            tests.append(test)
    tests.extend(doc_tests)
    return unittest.TestSuite(tests)
