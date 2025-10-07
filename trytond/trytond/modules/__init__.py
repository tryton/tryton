# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import configparser
import itertools
import logging
import os
import pkgutil
import warnings
from collections import defaultdict
from functools import cache
from glob import iglob

from sql import Table
from sql.functions import CurrentTimestamp

from trytond import __series__, config, convert, tools
from trytond.const import MODULES_GROUP
from trytond.exceptions import MissingDependenciesException
from trytond.transaction import Transaction

logger = logging.getLogger(__name__)

ir_module = Table('ir_module')
ir_model_data = Table('ir_model_data')
ir_configuration = Table('ir_configuration')

MODULES_PATH = os.path.abspath(os.path.dirname(__file__))

MODULES = []


@cache
def parse_module_config(name):
    "Return a ConfigParser instance and directory of the module"
    config = configparser.ConfigParser()
    config.optionxform = lambda option: option
    with tools.file_open(os.path.join(name, 'tryton.cfg')) as fp:
        config.read_file(fp)
        directory = os.path.dirname(fp.name)
    return config, directory


def get_module_info(name):
    "Return the content of the tryton.cfg"
    module_config, directory = parse_module_config(name)
    info = dict(module_config.items('tryton'))
    info['directory'] = directory
    for key in ('depends', 'extras_depend', 'xml'):
        if key in info:
            info[key] = info[key].strip().splitlines()
    return info


def get_module_register(name):
    "Return classes to register from tryton.cfg"
    module_config, _ = parse_module_config(name)
    for section in module_config.sections():
        if section == 'register' or section.startswith('register '):
            depends = section[len('register'):].strip().split()
            for type_ in ['model', 'report', 'wizard']:
                if not module_config.has_option(section, type_):
                    continue
                classes = module_config.get(
                    section, type_).strip().splitlines()
                yield classes, {
                    'module': name,
                    'type_': type_,
                    'depends': depends,
                    }


def get_module_register_mixin(name):
    "Return classes to register_mixin from tryton.cfg"
    module_config, _ = parse_module_config(name)
    if module_config.has_section('register_mixin'):
        for mixin, classinfo in module_config.items('register_mixin'):
            yield [mixin, classinfo], {
                'module': name,
                }


class Graph(dict):
    def get(self, name):
        if name in self:
            node = self[name]
        else:
            node = self[name] = Node(name)
        return node

    def add(self, name, deps):
        node = self.get(name)
        for dep in deps:
            self.get(dep).append(node)
        return node

    def __iter__(self):
        for node in sorted(self.values(), key=lambda n: (n.depth, n.name)):
            yield node


class Node(list):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.info = None
        self.__depth = 0

    def __repr__(self):
        return str((self.name, self.depth, tuple(self)))

    @property
    def depth(self):
        return self.__depth

    @depth.setter
    def depth(self, value):
        if value > self.__depth:
            self.__depth = value
            for child in self:
                child.depth = value + 1

    def append(self, node):
        assert isinstance(node, Node)
        node.depth = self.depth + 1
        super().append(node)


def create_graph(modules):
    all_deps = set()
    graph = Graph()
    for module in modules:
        info = get_module_info(module)
        deps = info.get('depends', []) + [
            d for d in info.get('extras_depend', []) if d in modules]
        node = graph.add(module, deps)
        assert node.info is None
        node.info = info
        all_deps.update(deps)

    missing = all_deps - modules
    if missing:
        raise MissingDependenciesException(list(missing))
    return graph


def is_module_to_install(module, update):
    if module in update:
        return True
    return False


def load_translations(pool, node, languages):
    module = node.name
    localedir = '%s/%s' % (node.info['directory'], 'locale')
    lang2filenames = defaultdict(list)
    for filename in itertools.chain(
            iglob('%s/*.po' % localedir),
            iglob('%s/override/*.po' % localedir)):
        filename = filename.replace('/', os.sep)
        lang = os.path.splitext(os.path.basename(filename))[0]
        if lang not in languages:
            continue
        lang2filenames[lang].append(filename)
    base_path_position = len(node.info['directory']) + 1
    for language, files in lang2filenames.items():
        filenames = [f[base_path_position:] for f in files]
        logger.info('%s load %s', module, ','.join(filenames))
        Translation = pool.get('ir.translation')
        Translation.translation_import(language, module, files)


def load_module_graph(graph, pool, update=None, lang=None, indexes=None):
    # Prevent to import backend when importing module
    from trytond.cache import Cache
    from trytond.ir.lang import get_parent_language

    if lang is None:
        lang = [config.get('database', 'language')]
    if update is None:
        update = []
    modules_todo = []
    models_to_update_history = set()
    models_with_indexes = set()

    # Load also parent languages
    lang = set(lang)
    for code in list(lang):
        while code:
            lang.add(code)
            code = get_parent_language(code)

    transaction = Transaction()
    # Do not force to lock table at the transaction start
    # as the table may not exist yet
    transaction.lock_table = lambda t: transaction.database.lock(
        transaction.connection, t)
    with transaction.connection.cursor() as cursor:
        modules = [x.name for x in graph]
        module2state = defaultdict(lambda: 'not activated')
        for sub_modules in tools.grouped_slice(modules):
            cursor.execute(*ir_module.select(ir_module.name, ir_module.state,
                    where=ir_module.name.in_(list(sub_modules))))
            module2state.update(cursor)
        modules = set(modules)

        new_modules = modules - module2state.keys()
        if new_modules:
            cursor.execute(*ir_module.insert(
                    [ir_module.name, ir_module.state],
                    [[m, 'not activated'] for m in new_modules]))

        def register_classes(classes, module):
            for type in list(classes.keys()):
                for cls in classes[type]:
                    logger.info('%s register %s', module, cls.__name__)
                    cls.__register__(module)

        to_install_states = {'to activate', 'to upgrade'}
        early_modules = ['ir', 'res']
        early_classes = {}
        for module in early_modules:
            early_classes[module] = pool.fill(module, modules)
        if update:
            for module in early_modules:
                pool.setup(early_classes[module])
            for module in early_modules:
                if (is_module_to_install(module, update)
                        or module2state[module] in to_install_states):
                    register_classes(early_classes[module], module)

        for node in graph:
            module = node.name
            if module not in MODULES:
                continue
            logger.info('%s load', module)
            if module in early_modules:
                classes = early_classes[module]
            else:
                classes = pool.fill(module, modules)
                if update:
                    # Clear all caches to prevent _record with wrong schema to
                    # linger
                    transaction.cache.clear()
                    pool.setup(classes)
            package_state = module2state[module]
            if (is_module_to_install(module, update)
                    or (update and package_state in to_install_states)):
                if package_state not in to_install_states:
                    if package_state == 'activated':
                        package_state = 'to upgrade'
                    elif package_state != 'to remove':
                        package_state = 'to activate'
                for child in node:
                    module2state[child.name] = package_state
                if module not in early_modules:
                    register_classes(classes, module)
                for model in classes['model']:
                    if hasattr(model, '_history'):
                        models_to_update_history.add(model.__name__)
                    if hasattr(model, '_update_sql_indexes'):
                        models_with_indexes.add(model.__name__)

                # Instanciate a new parser for the module
                tryton_parser = convert.TrytondXmlHandler(
                    pool, module, package_state, modules, lang)

                for filename in node.info.get('xml', []):
                    filename = filename.replace('/', os.sep)
                    logger.info('%s load %s', module, filename)
                    # Feed the parser with xml content:
                    with tools.file_open(
                            os.path.join(module, filename), 'rb') as fp:
                        tryton_parser.parse_xmlstream(fp)

                modules_todo.append((module, list(tryton_parser.to_delete)))

                load_translations(pool, node, lang)

                if package_state == 'to remove':
                    continue
                cursor.execute(*ir_module.select(ir_module.id,
                        where=(ir_module.name == module)))
                try:
                    module_id, = cursor.fetchone()
                    cursor.execute(*ir_module.update([ir_module.state],
                            ['activated'], where=(ir_module.id == module_id)))
                except TypeError:
                    cursor.execute(*ir_module.insert(
                            [ir_module.create_uid, ir_module.create_date,
                                ir_module.name, ir_module.state],
                            [[0, CurrentTimestamp(), module, 'activated'],
                                ]))
                module2state[module] = 'activated'
            elif not update and indexes:
                for model in classes['model']:
                    if hasattr(model, '__setup_indexes__'):
                        models_with_indexes.add(model.__name__)

        if not update:
            pool.setup()
        else:
            # As the caches are cleared at the end of the process there's
            # no need to do it here.
            # It may deadlock on the ir_cache SELECT if the table schema has
            # been modified
            Cache._reset.clear()
            transaction.commit()
            # Remove unknown models and fields
            Model = pool.get('ir.model')
            Model.clean()
            ModelField = pool.get('ir.model.field')
            ModelField.clean()

        pool.setup_mixin()

        for model_name in models_with_indexes:
            model = pool.get(model_name)
            model.__setup_indexes__()

        def create_indexes(concurrently):
            for model_name in models_with_indexes:
                model = pool.get(model_name)
                if model._sql_indexes:
                    logger.info('update index for %s', model_name)
                    model._update_sql_indexes(concurrently=concurrently)

        if update:
            cursor.execute(*ir_configuration.update(
                    [ir_configuration.series], [__series__]))
            if indexes or indexes is None:
                create_indexes(concurrently=False)
            else:
                logger.info('skip indexes creation')
            for model_name in models_to_update_history:
                model = pool.get(model_name)
                if model._history:
                    logger.info('update history for %s', model.__name__)
                    model._update_history_table()
            transaction.commit()
        elif indexes:
            # Release any lock
            transaction.commit()
            with transaction.new_transaction(autocommit=True):
                create_indexes(concurrently=True)

        # Vacuum :
        while modules_todo:
            (module, to_delete) = modules_todo.pop()
            convert.post_import(pool, module, to_delete)

        if update:
            # Ensure cache is clear for other instances
            Cache.clear_all()
            Cache.refresh_pool(transaction)
    logger.info('all modules loaded')


def get_modules(with_test=False):
    modules = {'ir', 'res'}
    modules.update((m.name for m in pkgutil.iter_modules([MODULES_PATH])))
    for ep in tools.entry_points().select(group=MODULES_GROUP):
        modules.add(ep.name)
    if with_test:
        modules.add('tests')
    return modules


def register_classes(with_test=False):
    '''
    Import modules to register the classes in the Pool
    '''
    import trytond.ir
    import trytond.res
    from trytond.pool import Pool

    base_modules = ['ir', 'res']
    for module_name in base_modules:
        logger.info("%s register", module_name)
        for args, kwargs in get_module_register(module_name):
            Pool.register(*args, **kwargs)
        for args, kwargs in get_module_register_mixin(module_name):
            Pool.register_mixin(*args, **kwargs)
    if with_test:
        base_modules.append('tests')
        import trytond.tests
        logger.info("tests register")
        trytond.tests.register()

    for node in create_graph(get_modules(with_test=with_test)):
        module_name = node.name
        if module_name in base_modules:
            MODULES.append(module_name)
            continue
        logger.info("%s register", module_name)
        for args, kwargs in get_module_register(module_name):
            Pool.register(*args, **kwargs)
        for args, kwargs in get_module_register_mixin(module_name):
            Pool.register_mixin(*args, **kwargs)
        module = tools.import_module(module_name)
        if hasattr(module, 'register'):
            warnings.warn(
                "register method is deprecated, "
                f"use register in tryton.cfg of {module_name}",
                DeprecationWarning)
            module.register()
        MODULES.append(module_name)


def load_modules(
        database_name, pool, update=None, lang=None, indexes=None,
        activatedeps=False):
    # Do not import backend when importing module
    res = True
    if update:
        update = update[:]
    else:
        update = []

    def _load_modules(update):
        global res
        transaction = Transaction()

        with transaction.set_context(_no_trigger=True), \
                transaction.connection.cursor() as cursor:
            if update:
                cursor.execute(*ir_module.select(ir_module.name,
                        where=ir_module.state.in_(('activated', 'to activate',
                                'to upgrade', 'to remove'))))
            else:
                cursor.execute(*ir_module.select(ir_module.name,
                        where=ir_module.state.in_(('activated', 'to upgrade',
                                'to remove'))))
            modules = {name for (name,) in cursor}
            graph = None
            while graph is None:
                modules.update(update)
                try:
                    graph = create_graph(modules)
                except MissingDependenciesException as e:
                    if not activatedeps:
                        raise
                    update += e.missings

            load_module_graph(graph, pool, update, lang, indexes)

            Configuration = pool.get('ir.configuration')
            Configuration(1).check()

            if update:
                cursor.execute(*ir_module.select(ir_module.name,
                        where=(ir_module.state == 'to remove')))
                for mod_name, in cursor:
                    res = False
                    # TODO check if ressource not updated by the user
                    with transaction.connection.cursor() as cursor_delete:
                        cursor_delete.execute(*ir_model_data.select(
                                ir_model_data.model, ir_model_data.db_id,
                                where=(ir_model_data.module == mod_name),
                                order_by=ir_model_data.id.desc))
                        for rmod, rid in cursor_delete:
                            Model = pool.get(rmod)
                            Model.delete([Model(rid)])
                    transaction.connection.commit()
                cursor.execute(*ir_module.update([ir_module.state],
                        ['not activated'],
                        where=(ir_module.state == 'to remove')))
                transaction.connection.commit()

                Module = pool.get('ir.module')
                Module.update_list()

    if not Transaction().connection:
        with Transaction().start(database_name, 0, readonly=not update):
            _load_modules(update)
    else:
        with Transaction().new_transaction(readonly=not update), \
                Transaction().set_user(0), \
                Transaction().reset_context():
            _load_modules(update)

    return res
