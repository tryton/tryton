# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import sys
import importlib
import itertools
import logging
import configparser
from glob import iglob
from collections import defaultdict
from importlib.machinery import FileFinder, SourceFileLoader, SOURCE_SUFFIXES

from sql import Table
from sql.functions import CurrentTimestamp

import trytond.tools as tools
from trytond.config import config
from trytond.exceptions import MissingDependenciesException
from trytond.transaction import Transaction
import trytond.convert as convert

logger = logging.getLogger(__name__)

ir_module = Table('ir_module')
ir_model_data = Table('ir_model_data')

OPJ = os.path.join
MODULES_PATH = os.path.abspath(os.path.dirname(__file__))

MODULES = []

EGG_MODULES = {}


def update_egg_modules():
    global EGG_MODULES
    try:
        import pkg_resources
        for ep in pkg_resources.iter_entry_points('trytond.modules'):
            EGG_MODULES[ep.name] = ep
    except ImportError:
        pass


update_egg_modules()


def import_module(name, fullname=None):
    if fullname is None:
        fullname = 'trytond.modules.' + name
    try:
        module = importlib.import_module(fullname)
    except ImportError:
        if name not in EGG_MODULES:
            raise
        ep = EGG_MODULES[name]
        # Can not use ep.load because modules are declared in an importable
        # path and it can not import submodule.
        path = os.path.join(
            ep.dist.location, *ep.module_name.split('.')[:-1])
        if not os.path.isdir(path):
            # Find module in path
            for path in sys.path:
                path = os.path.join(
                    path, *ep.module_name.split('.')[:-1])
                if os.path.isdir(os.path.join(path, name)):
                    break
            else:
                # When testing modules from setuptools location is the
                # module directory
                path = os.path.dirname(ep.dist.location)
        spec = FileFinder(
            path, (SourceFileLoader, SOURCE_SUFFIXES)
            ).find_spec(fullname)
        if spec.loader:
            module = spec.loader.load_module()
        else:
            raise
    return module


def get_module_info(name):
    "Return the content of the tryton.cfg"
    module_config = configparser.ConfigParser()
    with tools.file_open(os.path.join(name, 'tryton.cfg')) as fp:
        module_config.read_file(fp)
        directory = os.path.dirname(fp.name)
    info = dict(module_config.items('tryton'))
    info['directory'] = directory
    for key in ('depends', 'extras_depend', 'xml'):
        if key in info:
            info[key] = info[key].strip().splitlines()
    return info


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
        super(Node, self).__init__()
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
        super(Node, self).append(node)


def create_graph(module_list):
    module_list = set(module_list)
    all_deps = set()
    graph = Graph()
    for module in module_list:
        info = get_module_info(module)
        deps = info.get('depends', []) + [
            d for d in info.get('extras_depend', []) if d in module_list]
        node = graph.add(module, deps)
        assert node.info is None
        node.info = info
        all_deps.update(deps)

    missing = all_deps - module_list
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
        logger.info('%s:loading %s', module, ','.join(filenames))
        Translation = pool.get('ir.translation')
        Translation.translation_import(language, module, files)


def load_module_graph(graph, pool, update=None, lang=None):
    # Prevent to import backend when importing module
    from trytond.cache import Cache
    from trytond.ir.lang import get_parent_language

    if lang is None:
        lang = [config.get('database', 'language')]
    if update is None:
        update = []
    modules_todo = []
    models_to_update_history = set()

    # Load also parent languages
    lang = set(lang)
    for code in list(lang):
        while code:
            lang.add(code)
            code = get_parent_language(code)

    transaction = Transaction()
    with transaction.connection.cursor() as cursor:
        modules = [x.name for x in graph]
        module2state = dict()
        for sub_modules in tools.grouped_slice(modules):
            cursor.execute(*ir_module.select(ir_module.name, ir_module.state,
                    where=ir_module.name.in_(list(sub_modules))))
            module2state.update(cursor)
        modules = set(modules)

        for node in graph:
            module = node.name
            if module not in MODULES:
                continue
            logger.info(module)
            classes = pool.fill(module, modules)
            if update:
                pool.setup(classes)
            package_state = module2state.get(module, 'not activated')
            if (is_module_to_install(module, update)
                    or (update
                        and package_state in ('to activate', 'to upgrade'))):
                if package_state not in ('to activate', 'to upgrade'):
                    if package_state == 'activated':
                        package_state = 'to upgrade'
                    elif package_state != 'to remove':
                        package_state = 'to activate'
                for child in node:
                    module2state[child.name] = package_state
                for type in list(classes.keys()):
                    for cls in classes[type]:
                        logger.info('%s:register %s', module, cls.__name__)
                        cls.__register__(module)
                for model in classes['model']:
                    if hasattr(model, '_history'):
                        models_to_update_history.add(model.__name__)

                # Instanciate a new parser for the module
                tryton_parser = convert.TrytondXmlHandler(
                    pool, module, package_state, modules, lang)

                for filename in node.info.get('xml', []):
                    filename = filename.replace('/', os.sep)
                    logger.info('%s:loading %s', module, filename)
                    # Feed the parser with xml content:
                    with tools.file_open(OPJ(module, filename), 'rb') as fp:
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

            # Avoid clearing cache to prevent dead lock on ir.cache table
            Cache.rollback(transaction)
            transaction.commit()
            # Clear transaction cache to update default_factory
            transaction.cache.clear()

        if not update:
            pool.setup()
        else:
            # Remove unknown models and fields
            Model = pool.get('ir.model')
            Model.clean()
            ModelField = pool.get('ir.model.field')
            ModelField.clean()
            transaction.commit()

        pool.setup_mixin(modules)

        for model_name in models_to_update_history:
            model = pool.get(model_name)
            if model._history:
                logger.info('history:update %s', model.__name__)
                model._update_history_table()

        # Vacuum :
        while modules_todo:
            (module, to_delete) = modules_todo.pop()
            convert.post_import(pool, module, to_delete)

        if update:
            # Ensure cache is clear for other instances
            Cache.clear_all()
            Cache.refresh_pool(transaction)
    logger.info('all modules loaded')


def get_module_list():
    module_list = set()
    if os.path.exists(MODULES_PATH) and os.path.isdir(MODULES_PATH):
        for file in os.listdir(MODULES_PATH):
            if file.startswith('.'):
                continue
            if file == '__pycache__':
                continue
            if os.path.isdir(OPJ(MODULES_PATH, file)):
                module_list.add(file)
    update_egg_modules()
    module_list.update(EGG_MODULES.keys())
    module_list.add('ir')
    module_list.add('res')
    module_list.add('tests')
    return list(module_list)


def register_classes():
    '''
    Import modules to register the classes in the Pool
    '''
    import trytond.ir
    trytond.ir.register()
    import trytond.res
    trytond.res.register()
    import trytond.tests
    trytond.tests.register()

    for node in create_graph(get_module_list()):
        module = node.name
        logger.info('%s:registering classes', module)

        if module in ('ir', 'res', 'tests'):
            MODULES.append(module)
            continue

        the_module = import_module(module)
        # Some modules register nothing in the Pool
        if hasattr(the_module, 'register'):
            the_module.register()
        MODULES.append(module)


def load_modules(
        database_name, pool, update=None, lang=None, activatedeps=False):
    # Do not import backend when importing module
    from trytond import backend
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
            # Migration from 3.6: remove double module
            old_table = 'ir_module_module'
            new_table = 'ir_module'
            if backend.TableHandler.table_exist(old_table):
                backend.TableHandler.table_rename(old_table, new_table)

            # Migration from 4.0: rename installed to activated
            cursor.execute(*ir_module.select(ir_module.name,
                    where=ir_module.state.in_(('installed', 'uninstalled'))))
            if cursor.fetchone():
                cursor.execute(*ir_module.update(
                        [ir_module.state], ['activated'],
                        where=ir_module.state == 'installed'))
                cursor.execute(*ir_module.update(
                        [ir_module.state], ['not activated'],
                        where=ir_module.state == 'uninstalled'))

            if update:
                cursor.execute(*ir_module.select(ir_module.name,
                        where=ir_module.state.in_(('activated', 'to activate',
                                'to upgrade', 'to remove'))))
            else:
                cursor.execute(*ir_module.select(ir_module.name,
                        where=ir_module.state.in_(('activated', 'to upgrade',
                                'to remove'))))
            module_list = [name for (name,) in cursor]
            graph = None
            while graph is None:
                module_list += update
                try:
                    graph = create_graph(module_list)
                except MissingDependenciesException as e:
                    if not activatedeps:
                        raise
                    update += e.missings

            load_module_graph(graph, pool, update, lang)

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
        # Need to commit to unlock SQLite database
        transaction.commit()

    if not Transaction().connection:
        with Transaction().start(database_name, 0):
            _load_modules(update)
    else:
        with Transaction().new_transaction(), \
                Transaction().set_user(0), \
                Transaction().reset_context():
            _load_modules(update)

    return res
