# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import sys
import unittest
import doctest
import re
from itertools import chain
import operator
from functools import wraps

from lxml import etree

from trytond.pool import Pool, isregisteredby
from trytond import backend
from trytond.model import Workflow
from trytond.model.fields import get_eval_fields
from trytond.protocols.dispatcher import create, drop
from trytond.tools import is_instance_method
from trytond.transaction import Transaction
from trytond import security
from trytond.cache import Cache

__all__ = ['POOL', 'DB_NAME', 'USER', 'USER_PASSWORD', 'CONTEXT',
    'install_module', 'ModuleTestCase', 'with_transaction',
    'doctest_setup', 'doctest_teardown', 'doctest_checker',
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
    with Transaction().start(DB_NAME, 1) as transaction:
        Module = POOL.get('ir.module')

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
        transaction.commit()

        InstallUpgrade = POOL.get('ir.module.install_upgrade',
            type='wizard')
        instance_id, _, _ = InstallUpgrade.create()
        transaction.commit()
        InstallUpgrade(instance_id).transition_upgrade()
        InstallUpgrade.delete(instance_id)
        transaction.commit()


def with_transaction(user=1, context=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            transaction = Transaction()
            with transaction.start(DB_NAME, user, context=context):
                result = func(*args, **kwargs)
                transaction.rollback()
                # Drop the cache as the transaction is rollbacked
                Cache.drop(DB_NAME)
                return result
        return wrapper
    return decorator


class ModuleTestCase(unittest.TestCase):
    'Trytond Test Case'
    module = None

    @classmethod
    def setUpClass(cls):
        drop_create()
        install_module(cls.module)
        super(ModuleTestCase, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        super(ModuleTestCase, cls).tearDownClass()
        drop_db()

    @with_transaction()
    def test_rec_name(self):
        for mname, model in Pool().iterobject():
            if not isregisteredby(model, self.module):
                continue
            # Skip testing default value even if the field doesn't exist
            # as there is a fallback to id
            if model._rec_name == 'name':
                continue
            assert model._rec_name in model._fields, (
                'Wrong _rec_name "%s" for %s'
                % (model._rec_name, mname))

    @with_transaction()
    def test_view(self):
        'Test validity of all views of the module'
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

            validator = etree.RelaxNG(etree=View.get_rng(res['type']))
            # Don't use assert_ because 2to3 convert to assertTrue
            validator.assertValid(tree)

            tree_root = tree.getroottree().getroot()

            for element in tree_root.iter():
                if element.tag in ('field', 'label', 'separator', 'group'):
                    for attr in ('name', 'icon'):
                        field = element.get(attr)
                        if field:
                            assert field in res['fields'], (
                                'Missing field: %s' % field)

    @with_transaction()
    def test_depends(self):
        'Test for missing depends'
        for mname, model in Pool().iterobject():
            if not isregisteredby(model, self.module):
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

    @with_transaction()
    def test_field_methods(self):
        'Test field methods'
        for mname, model in Pool().iterobject():
            if not isregisteredby(model, self.module):
                continue
            for attr in dir(model):
                for prefixes in [['default_'],
                        ['on_change_', 'on_change_with_'],
                        ['order_'], ['domain_'], ['autocomplete_']]:
                    if attr == 'on_change_with':
                        continue
                    # TODO those method should be renamed
                    if attr == 'default_get':
                        continue
                    if mname == 'ir.rule' and attr == 'domain_get':
                        continue

                    # Skip if it is a field
                    if attr in model._fields:
                        continue
                    fnames = [attr[len(prefix):] for prefix in prefixes
                        if attr.startswith(prefix)]
                    if not fnames:
                        continue
                    assert any(f in model._fields for f in fnames), (
                        'Field method "%s"."%s" for unknown field' % (
                            mname, attr))

                    if attr.startswith('default_'):
                        getattr(model, attr)()
                    elif attr.startswith('order_'):
                        tables = {None: (model.__table__(), None)}
                        getattr(model, attr)(tables)

    @with_transaction()
    def test_menu_action(self):
        'Test that menu actions are accessible to menu\'s group'
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

    @with_transaction()
    def test_model_access(self):
        'Test missing default model access'
        pool = Pool()
        Access = pool.get('ir.model.access')
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

    @with_transaction()
    def test_workflow_transitions(self):
        'Test all workflow transitions exist'
        for mname, model in Pool().iterobject():
            if not isregisteredby(model, self.module):
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
    return DB_NAME in database.list()


def create_db():
    if not db_exist():
        create(None, DB_NAME, None, 'en_US', USER_PASSWORD)


def drop_db():
    if db_exist():
        drop(None, DB_NAME, None)


def drop_create():
    if db_exist():
        drop_db()
    create_db()

doctest_setup = lambda test: drop_create()
doctest_teardown = lambda test: drop_db()


class Py23DocChecker(doctest.OutputChecker):
    def check_output(self, want, got, optionflags):
        if sys.version_info[0] > 2:
            want = re.sub("u'(.*?)'", "'\\1'", want)
            want = re.sub('u"(.*?)"', '"\\1"', want)
        return doctest.OutputChecker.check_output(self, want, got, optionflags)

doctest_checker = Py23DocChecker()


class TestSuite(unittest.TestSuite):
    def run(self, *args, **kwargs):
        exist = db_exist()
        result = super(TestSuite, self).run(*args, **kwargs)
        if not exist:
            drop_db()
        return result


def suite():
    '''
    Return test suite for other modules
    '''
    return TestSuite()


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
            if isinstance(test, doctest.DocTestCase) and not doc:
                continue
            suite_.addTest(test)
    return suite_
