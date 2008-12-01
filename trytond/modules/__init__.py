#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import os, sys, imp
import itertools
from sets import Set
from trytond.config import CONFIG
import trytond.tools as tools
import zipfile
import zipimport
import traceback
import logging

OPJ = os.path.join
MODULES_PATH = os.path.dirname(__file__)
sys.path.insert(1, MODULES_PATH)

MODULES = []

EGG_MODULES = {}
try:
    import pkg_resources
    for ep in pkg_resources.iter_entry_points('trytond.modules'):
        mod_name = ep.module_name.split('.')[-1]
        EGG_MODULES[mod_name] = ep
except ImportError:
    pass


class Graph(dict):

    def add_node(self, name, deps):
        for i in [Node(x, self) for x in deps]:
            i.add_child(name)
        if not deps:
            Node(name, self)

    def __iter__(self):
        level = 0
        done = Set(self.keys())
        while done:
            level_modules = [(name, module) for name, module in self.items() \
                    if module.depth==level]
            for name, module in level_modules:
                done.remove(name)
                yield module
            level += 1

    def __str__(self):
        res = ''
        for i in self:
            res += str(i)
            res += '\n'
        return res


class Singleton(object):

    def __new__(cls, name, graph):
        if name in graph:
            inst = graph[name]
        else:
            inst = object.__new__(cls)
            graph[name] = inst
        return inst


class Node(Singleton):

    def __init__(self, name, graph):
        super(Node, self).__init__()
        self.name = name
        self.graph = graph
        if not hasattr(self, 'datas'):
            self.datas = None
        if not hasattr(self, 'childs'):
            self.childs = []
        if not hasattr(self, 'depth'):
            self.depth = 0

    def add_child(self, name):
        node = Node(name, self.graph)
        node.depth = max(self.depth + 1, node.depth)
        if node not in self.all_childs():
            self.childs.append(node)
        for attr in ('init', 'update'):
            if hasattr(self, attr):
                setattr(node, attr, True)
        self.childs.sort(lambda x, y: cmp(x.name, y.name))

    def all_childs(self):
        res = []
        for child in self.childs:
            res.append(child)
            res += child.all_childs()
        return res

    def has_child(self, name):
        return Node(name, self.graph) in self.childs or \
                bool([c for c in self.childs if c.has_child(name)])

    def __setattr__(self, name, value):
        super(Node, self).__setattr__(name, value)
        if name in ('init', 'update'):
            for child in self.childs:
                setattr(child, name, value)
        if name == 'depth':
            for child in self.childs:
                setattr(child, name, value + 1)

    def __iter__(self):
        return itertools.chain(iter(self.childs),
                *[iter(x) for x in self.childs])

    def __str__(self):
        return self.pprint()

    def pprint(self, depth=0):
        res = '%s\n' % self.name
        for child in self.childs:
            res += '%s`-> %s' % ('    ' * depth, child.pprint(depth + 1))
        return res

def create_graph(module_list, force=None):
    if force is None:
        force = []
    graph = Graph()
    packages = []

    for module in module_list:
        if module[-4:] == '.zip':
            module = module[:-4]
        tryton_file = OPJ(MODULES_PATH, module, '__tryton__.py')
        mod_path = OPJ(MODULES_PATH, module)
        if module in ('ir', 'workflow', 'res', 'webdav'):
            root_path = os.path.dirname(os.path.dirname(__file__))
            tryton_file = OPJ(root_path, module, '__tryton__.py')
            mod_path = OPJ(root_path, module)
        elif module in EGG_MODULES:
            ep = EGG_MODULES[module]
            tryton_file = OPJ(ep.dist.location, 'trytond', 'modules', module,
                    '__tryton__.py')
            mod_path = OPJ(ep.dist.location, 'trytond', 'modules', module)
        if os.path.isfile(tryton_file) or zipfile.is_zipfile(mod_path+'.zip'):
            try:
                info = eval(tools.file_open(tryton_file, subdir='').read())
            except:
                logging.getLogger('init').error(
                    'module:%s:eval file %s' % (module, tryton_file))
                raise
            packages.append((module, info.get('depends', []), info))
        elif module != 'all':
            logging.getLogger('init').error(
                'module:%s:Module not found!' % (module,))

    current, later = Set([x[0] for x in packages]), Set()
    while packages and current > later:
        package, deps, datas = packages[0]

        # if all dependencies of 'package' are already in the graph,
        # add 'package' in the graph
        if reduce(lambda x, y: x and y in graph, deps, True):
            if not package in current:
                packages.pop(0)
                continue
            later.clear()
            current.remove(package)
            graph.add_node(package, deps)
            node = Node(package, graph)
            node.datas = datas
            for kind in ('init', 'update'):
                if (package in CONFIG[kind]) \
                        or ('all' in CONFIG[kind]) \
                        or (kind in force):
                    setattr(node, kind, True)
        else:
            later.add(package)
            packages.append((package, deps, datas))
        packages.pop(0)

    for package, deps, datas in packages:
        if package not in later:
            continue
        missings = [x for x in deps if x not in graph]
        logging.getLogger('init').error(
            'module:%s:Unmet dependency %s' % (package, missings))
    return graph, packages, later

def init_module_objects(cursor, module_name, obj_list):
    logging.getLogger('init').info(
        'module:%s:creating or updating database tables' % module_name)
    for obj in obj_list:
        obj.auto_init(cursor, module_name)

def init_module_wizards(cursor, module_name, wizard_list):
    logging.getLogger('init').info(
        'module:%s:creating or updating wizards' % module_name)
    for wizard in wizard_list:
        wizard.auto_init(cursor, module_name)

def load_module_graph(cursor, graph, pool, pool_wizard, pool_report, lang=None):
    if lang is None:
        lang = ['en_US']
    modules_todo = []
    for package in graph:
        module = package.name
        if module not in MODULES:
            continue
        logging.getLogger('init').info('module:%s' % module)
        sys.stdout.flush()
        modules = pool.instanciate(module)
        wizards = pool_wizard.instanciate(module, pool)
        reports = pool_report.instanciate(module, pool)
        cursor.execute('SELECT state FROM ir_module_module WHERE name = %s',
                (module,))
        package_state = (cursor.rowcount and cursor.fetchone()[0]) \
                or 'uninstalled'
        idref = {}
        if hasattr(package, 'init') \
                or hasattr(package, 'update') \
                or (package_state in ('to install', 'to upgrade')):
            init_module_objects(cursor, module, modules)
            init_module_wizards(cursor, module, wizards)

            #Instanciate a new parser for the package:
            tryton_parser = tools.TrytondXmlHandler(
                cursor=cursor,
                pool=pool,
                module=module,)

            for filename in package.datas.get('xml', []):
                mode = 'update'
                if hasattr(package, 'init') or package_state=='to install':
                    mode = 'init'
                logging.getLogger('init').info(
                    'module:%s:loading %s' % (module, filename))
                ext = os.path.splitext(filename)[1]
                if ext == '.sql':
                    if mode == 'init':
                        queries = tools.file_open(OPJ(module,
                            filename)).read().split(';')
                        for query in queries:
                            new_query = ' '.join(query.split())
                            if new_query:
                                cursor.execute(new_query)
                else:
                    # Feed the parser with xml content:
                    tryton_parser.parse_xmlstream(
                        tools.file_open(OPJ(module, filename)))

            modules_todo.append((module, tryton_parser.to_delete))

            for filename in package.datas.get('translation', []):
                lang2 = os.path.splitext(filename)[0]
                if lang2 not in lang:
                    continue
                try:
                    trans_file = tools.file_open(OPJ(module, filename))
                except IOError:
                    logging.getLogger('init').error(
                        'module:%s:file %s not found!' % (module, filename))
                    continue
                logging.getLogger('init').info(
                    'module:%s:loading %s' % (module, filename))
                translation_obj = pool.get('ir.translation')
                translation_obj.translation_import(cursor, 0, lang2, module, 
                                                   trans_file)

            cursor.execute("UPDATE ir_module_module SET state = 'installed' " \
                    "WHERE name = %s", (package.name,))
        cursor.commit()


    # Vacuum :
    while modules_todo:
        (module, to_delete) = modules_todo.pop()
        tools.post_import(cursor, pool, module, to_delete)


    cursor.commit()

def get_module_list():
    module_list = set()
    if os.path.exists(MODULES_PATH) and os.path.isdir(MODULES_PATH):
        for file in os.listdir(MODULES_PATH):
            if os.path.isdir(OPJ(MODULES_PATH, file)):
                module_list.add(file)
            elif file[-4:] == '.zip':
                module_list.add(file)
    for ep in pkg_resources.iter_entry_points('trytond.modules'):
         mod_name = ep.module_name.split('.')[-1]
         module_list.add(mod_name)
    module_list.add('ir')
    module_list.add('workflow')
    module_list.add('res')
    module_list.add('webdav')
    return list(module_list)

def register_classes():
    import trytond.ir
    import trytond.workflow
    import trytond.res
    import trytond.webdav

    for package in create_graph(get_module_list())[0]:
        module = package.name
        logging.getLogger('init').info(
            'module:%s:registering classes' % module)

        if module in ('ir', 'workflow', 'res', 'webdav'):
            MODULES.append(module)
            continue

        if os.path.isfile(OPJ(MODULES_PATH, module + '.zip')):
            mod_path = OPJ(MODULES_PATH, module + '.zip')
            try:
                zimp = zipimport.zipimporter(mod_path)
                zimp.load_module(module)
            except zipimport.ZipImportError:
                tb_s = ''
                for line in traceback.format_exception(*sys.exc_info()):
                    try:
                        line = line.encode('utf-8', 'ignore')
                    except:
                        continue
                    tb_s += line
                for path in sys.path:
                    tb_s = tb_s.replace(path, '')
                if CONFIG['debug_mode']:
                    import pdb
                    traceb = sys.exc_info()[2]
                    pdb.post_mortem(traceb)
                logging.getLogger('init').error(
                    'Couldn\'t import module %s:\n%s' % (module, tb_s))
                break
        elif os.path.isdir(OPJ(MODULES_PATH, module)):
            try:
                imp.load_module(module, *imp.find_module(module,
                    [MODULES_PATH]))
            except ImportError:
                tb_s = ''
                for line in traceback.format_exception(*sys.exc_info()):
                    try:
                        line = line.encode('utf-8', 'ignore')
                    except:
                        continue
                    tb_s += line
                for path in sys.path:
                    tb_s = tb_s.replace(path, '')
                if CONFIG['debug_mode']:
                    import pdb
                    traceb = sys.exc_info()[2]
                    pdb.post_mortem(traceb)
                logging.getLogger('init').error(
                    'Couldn\'t import module %s:\n%s' % (module, tb_s))
                break
        elif module in EGG_MODULES:
            ep = EGG_MODULES[module]
            mod_path = os.path.join(ep.dist.location,
                    *ep.module_name.split('.')[:-1])
            imp.load_module(module, *imp.find_module(module, [mod_path]))
        else:
            logging.getLogger('init').error(
                    'Couldn\'t find module %s' % module)
            break
        MODULES.append(module)

def load_modules(database, pool, pool_wizard, pool_report, update_module=False,
        lang=None):
    res = True
    cursor = database.cursor()
    try:
        force = []
        if update_module:
            if 'all' in CONFIG['init']:
                cursor.execute("SELECT name FROM ir_module_module")
            else:
                cursor.execute("SELECT name FROM ir_module_module " \
                        "WHERE state IN ('installed', 'to install', " \
                            "'to upgrade', 'to remove')")
        else:
            cursor.execute("SELECT name FROM ir_module_module " \
                    "WHERE state IN ('installed', 'to upgrade', 'to remove')")
        module_list = [name for (name,) in cursor.fetchall()]
        if update_module:
            for module in CONFIG['init'].keys():
                if CONFIG['init'][module]:
                    module_list.append(module)
            for module in CONFIG['update'].keys():
                if CONFIG['update'][module]:
                    module_list.append(module)
        graph = create_graph(module_list, force)[0]

        try:
            load_module_graph(cursor, graph, pool, pool_wizard, pool_report,
                    lang)
        except:
            cursor.rollback()
            raise

        if update_module:
            cursor.execute("SELECT name FROM ir_module_module " \
                    "WHERE state IN ('to remove')")
            if cursor.rowcount:
                for (mod_name,) in cursor.fetchall():
                    #TODO check if ressource not updated by the user
                    cursor.execute('SELECT model, db_id FROM ir_model_data ' \
                            'WHERE module = %s ' \
                            'ORDER BY id DESC', (mod_name,))
                    for rmod, rid in cursor.fetchall():
                        pool.get(rmod).delete(cursor, 0, rid)
                    cursor.commit()
                cursor.execute("UPDATE ir_module_module SET state = %s " \
                        "WHERE state IN ('to remove')", ('uninstalled',))
                cursor.commit()
                res = False

        module_obj = pool.get('ir.module.module')
        module_obj.update_list(cursor, 0)
        cursor.commit()
    finally:
        cursor.close()
    return res
