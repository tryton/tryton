#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from lxml import etree
try:
    import hashlib
except ImportError:
    hashlib = None
    import md5
import copy
from trytond.model import Model
from trytond.tools import safe_eval
from trytond.pyson import PYSONEncoder, CONTEXT
from trytond.transaction import Transaction
from trytond.cache import Cache
from trytond.pool import Pool

def _find(tree, element):
    if element.tag == 'xpath':
        res = tree.xpath(element.get('expr'))
        if res:
            return res[0]
    return None


def _inherit_apply(src, inherit):
    tree_src = etree.fromstring(src)
    tree_inherit = etree.fromstring(inherit)
    root_inherit = tree_inherit.getroottree().getroot()
    for element2 in root_inherit:
        if element2.tag != 'xpath':
            continue
        element = _find(tree_src, element2)
        if element is not None:
            pos = element2.get('position', 'inside')
            if pos == 'replace':
                parent = element.getparent()
                enext = element.getnext()
                if enext is not None:
                    for child in element2:
                        index = parent.index(enext)
                        parent.insert(index, child)
                else:
                    parent.extend(element2.getchildren())
                parent.remove(element)
            elif pos == 'replace_attributes':
                child = element2.getchildren()[0]
                for attr in child.attrib:
                    element.set(attr, child.get(attr))
            elif pos == 'inside':
                element.extend(element2.getchildren())
            elif pos == 'after':
                parent = element.getparent()
                enext = element.getnext()
                if enext is not None:
                    for child in element2:
                        index = parent.index(enext)
                        parent.insert(index, child)
                else:
                    parent.extend(element2.getchildren())
            elif pos == 'before':
                parent = element.getparent()
                for child in element2:
                    index = parent.index(element)
                    parent.insert(index, child)
            else:
                raise AttributeError('Unknown position ' \
                        'in inherited view %s!' % pos)
        else:
            raise AttributeError(
                    'Couldn\'t find tag (%s: %s) in parent view!' % \
                            (element2.tag, element2.get('expr')))
    return etree.tostring(tree_src, encoding='utf-8')


class ModelView(Model):
    """
    Define a model with views in Tryton.
    """
    __modules_list = None # Cache for the modules list sorted by dependency

    @staticmethod
    def _reset_modules_list():
        ModelView.__modules_list = None

    def _get_modules_list(self):
        from trytond.modules import create_graph, get_module_list
        if ModelView.__modules_list:
            return ModelView.__modules_list
        graph = create_graph(get_module_list())[0]
        ModelView.__modules_list = [x.name for x in graph] + [None]
        return ModelView.__modules_list

    _modules_list = property(fget=_get_modules_list)

    def __init__(self):
        super(ModelView, self).__init__()
        self._rpc['fields_view_get'] = False
        self._rpc['view_toolbar_get'] = False

    @Cache('modelview.fields_view_get')
    def fields_view_get(self, view_id=None, view_type='form', hexmd5=None):
        '''
        Return a view definition.

        :param view_id: the id of the view, if None the first one will be used
        :param view_type: the type of the view if view_id is None
        :param hexmd5: if filled, the function will return True if the result
            has the same md5
        :return: a dictionary with keys:
           - model: the model name
           - arch: the xml description of the view
           - fields: a dictionary with the definition of each field in the view
           - md5: the check sum of the dictionary without this checksum
        '''
        result = {'model': self._name}
        pool = Pool()

        test = True
        model = True
        sql_res = False
        inherit_view_id = False
        cursor = Transaction().cursor
        while test:
            if view_id:
                where = (model and (" and model='%s'" % (self._name,))) or ''
                cursor.execute('SELECT arch, field_childs, id, type, ' \
                            'inherit, model ' \
                        'FROM ir_ui_view WHERE id = %s ' + where, (view_id,))
            else:
                cursor.execute('SELECT arch, field_childs, id, type, ' \
                        'inherit, model ' \
                        'FROM ir_ui_view ' \
                        'WHERE model = %s AND type = %s ' \
                        'ORDER BY inherit DESC, priority ASC, id ASC',
                        (self._name, view_type))
            sql_res = cursor.fetchone()
            if not sql_res:
                break
            test = sql_res[4]
            if test:
                inherit_view_id = sql_res[2]
            view_id = test or sql_res[2]
            model = False

        # if a view was found
        if sql_res:
            result['type'] = sql_res[3]
            result['view_id'] = view_id
            result['arch'] = sql_res[0]
            result['field_childs'] = sql_res[1] or False

            # Check if view is not from an inherited model
            if sql_res[5] != self._name:
                inherit_obj = pool.get(sql_res[5])
                result['arch'] = inherit_obj.fields_view_get(
                        result['view_id'])['arch']
                view_id = inherit_view_id

            # get all views which inherit from (ie modify) this view
            cursor.execute('SELECT arch, domain, module FROM ir_ui_view ' \
                    'WHERE (inherit = %s AND model = %s) OR ' \
                        ' (id = %s AND inherit IS NOT NULL) '
                    'ORDER BY priority ASC, id ASC',
                    (view_id, self._name, view_id))
            sql_inherit = cursor.fetchall()
            raise_p = False
            while True:
                try:
                    sql_inherit.sort(key=lambda x:
                        self._modules_list.index(x[2] or None))
                    break
                except ValueError:
                    if raise_p:
                        raise
                    # There is perhaps a new module in the directory
                    ModelView._reset_modules_list()
                    raise_p = True
            for arch, domain, _ in sql_inherit:
                if domain:
                    if not safe_eval(domain,
                            {'context': Transaction().context}):
                        continue
                if not arch or not arch.strip():
                    continue
                result['arch'] = _inherit_apply(result['arch'], arch)

        # otherwise, build some kind of default view
        else:
            if view_type == 'form':
                res = self.fields_get()
                xml = '''<?xml version="1.0"?>''' \
                '''<form string="%s">''' % (self._description,)
                for i in res:
                    if i in ('create_uid', 'create_date',
                            'write_uid', 'write_date', 'id', 'rec_name'):
                        continue
                    if res[i]['type'] not in ('one2many', 'many2many'):
                        xml += '<label name="%s"/>' % (i,)
                        xml += '<field name="%s"/>' % (i,)
                        if res[i]['type'] == 'text':
                            xml += "<newline/>"
                xml += "</form>"
            elif view_type == 'tree':
                field = 'id'
                if self._rec_name in self._columns:
                    field = self._rec_name
                xml = '''<?xml version="1.0"?>''' \
                '''<tree string="%s"><field name="%s"/></tree>''' \
                % (self._description, field)
            else:
                xml = ''
            result['type'] = view_type
            result['arch'] = xml
            result['field_childs'] = False
            result['view_id'] = 0

        # Update arch and compute fields from arch
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.fromstring(result['arch'], parser)
        xarch, xfields = self._view_look_dom_arch(tree, result['type'],
                result['field_childs'])
        result['arch'] = xarch
        result['fields'] = xfields

        # Compute md5
        if hashlib:
            result['md5'] = hashlib.md5(str(result)).hexdigest()
        else:
            result['md5'] = md5.new(str(result)).hexdigest()
        if hexmd5 == result['md5']:
            return True
        return result

    def view_toolbar_get(self):
        """
        Returns the model specific actions.

        :return: a dictionary with keys:
            - print: a list of available reports
            - action: a list of available actions
            - relate: a list of available relations
        """
        action_obj = Pool().get('ir.action.keyword')
        prints = action_obj.get_keyword('form_print', (self._name, -1))
        actions = action_obj.get_keyword('form_action', (self._name, -1))
        relates = action_obj.get_keyword('form_relate', (self._name, -1))
        return {
            'print': prints,
            'action': actions,
            'relate': relates,
        }

    def view_header_get(self, value, view_type='form'):
        """
        Overload this method if you need a window title.
        which depends on the context

        :param value: the default header string
        :param view_type: the type of the view
        :return: the header string of the view
        """
        return value

    def _view_look_dom_arch(self, tree, type, field_children=None):
        pool = Pool()
        model_access_obj = pool.get('ir.model.access')
        field_access_obj = pool.get('ir.model.field.access')

        fields_width = {}
        tree_root = tree.getroottree().getroot()

        # Find field without read access
        fread_accesses = field_access_obj.check(self._name,
                self._columns.keys(), 'read', access=True)
        fields_to_remove = list(x for x, y in fread_accesses.iteritems()
                if not y)

        def check_relation(model, field):
            if field._type in ('one2many', 'many2one'):
                if not model_access_obj.check(field.model_name, mode='read',
                        raise_exception=False):
                    return False
            if field._type in ('many2many', 'one2one'):
                if not model_access_obj.check(field.target, mode='read',
                        raise_exception=False):
                    return False
                elif not model_access_obj.check(field.relation_name,
                        mode='read', raise_exception=False):
                    return False
            if field._type == 'reference':
                selection = field.selection
                if isinstance(selection, basestring):
                    selection = getattr(model, field.selection)()
                for model_name, _ in selection:
                    if not model_access_obj.check(model_name, mode='read',
                            raise_exception=False):
                        return False
            return True

        # Find relation field without read access
        for name, field in self._columns.iteritems():
            if not check_relation(self, field):
                fields_to_remove.append(name)

        for name, field in self._columns.iteritems():
            for field_to_remove in fields_to_remove:
                if field_to_remove in field.depends:
                    fields_to_remove.append(name)

        # Find field inherited without read access
        for inherit_name in self._inherits:
            inherit_obj = pool.get(inherit_name)
            fread_accesses = field_access_obj.check(inherit_obj._name,
                    inherit_obj._columns.keys(), 'read', access=True)
            fields_to_remove += list(x for x, y in fread_accesses.iteritems()
                    if not y and x not in self._columns.keys())

            # Find relation field without read access
            for name, field in inherit_obj._columns.iteritems():
                if not check_relation(inherit_obj, field):
                    fields_to_remove.append(name)

            for name, field in inherit_obj._columns.iteritems():
                for field_to_remove in fields_to_remove:
                    if field_to_remove in field.depends:
                        fields_to_remove.append(name)

        # Remove field without read access
        for field in fields_to_remove:
            for element in tree.xpath(
                    '//field[@name="%s"] | //label[@name="%s"]'
                    % (field, field)):
                if type == 'form':
                    element.tag = 'label'
                    element.attrib.clear()
                elif type == 'tree':
                    parent = element.getparent()
                    parent.remove(element)

        if type == 'tree':
            viewtreewidth_obj = pool.get('ir.ui.view_tree_width')
            viewtreewidth_ids = viewtreewidth_obj.search([
                ('model', '=', self._name),
                ('user', '=', Transaction().user),
                ])
            for viewtreewidth in viewtreewidth_obj.browse(viewtreewidth_ids):
                if viewtreewidth.width > 0:
                    fields_width[viewtreewidth.field] = viewtreewidth.width

        fields_def = self.__view_look_dom(tree_root, type,
                fields_width=fields_width)

        if field_children:
            fields_def.setdefault(field_children, {'name': field_children})
            model, field = None, None
            if field_children in self._columns:
                model = self
                field = self._columns[field_children]
            elif field_children in self._inherit_fields:
                model_name, model, field = self._inherit_fields[field_children]
            if model and field and field.model_name == model._name:
                fields_def.setdefault(field.field, {'name': field.field})

        for field_name in fields_def.keys():
            if field_name in self._columns:
                field = self._columns[field_name]
            elif field_name in self._inherit_fields:
                field = self._inherit_fields[field_name][2]
            else:
                continue
            for depend in field.depends:
                fields_def.setdefault(depend, {'name': depend})

        if ('active' in self._columns) or ('active' in self._inherit_fields):
            fields_def.setdefault('active', {'name': 'active'})

        arch = etree.tostring(tree, encoding='utf-8', pretty_print=False)
        fields2 = self.fields_get(fields_def.keys())
        for field in fields_def:
            if field in fields2:
                fields2[field].update(fields_def[field])
        return arch, fields2

    def __view_look_dom(self, element, type, fields_width=None):
        pool = Pool()
        translation_obj = pool.get('ir.translation')

        if fields_width is None:
            fields_width = {}
        result = False
        fields_attrs = {}
        childs = True

        if element.tag in ('field', 'label', 'separator', 'group'):
            for attr in ('name', 'icon'):
                if element.get(attr):
                    attrs = {}
                    try:
                        if element.get(attr) in self._columns:
                            field = self._columns[element.get(attr)]
                        else:
                            field = self._inherit_fields[element.get(
                                attr)][2]
                        if hasattr(field, 'model_name'):
                            relation = field.model_name
                        else:
                            relation = field.get_target()._name
                    except Exception:
                        relation = False
                    if relation and element.tag == 'field':
                        childs = False
                        views = {}
                        for field in element:
                            if field.tag in ('form', 'tree', 'graph'):
                                field2 = copy.copy(field)

                                def _translate_field(field):
                                    if field.get('string'):
                                        trans = translation_obj._get_source(
                                                self._name, 'view',
                                                Transaction().language,
                                                field.get('string'))
                                        if trans:
                                            field.set('string', trans)
                                    if field.get('sum'):
                                        trans = translation_obj._get_source(
                                                self._name, 'view',
                                                Transaction().language,
                                                field.get('sum'))
                                        if trans:
                                            field.set('sum', trans)
                                    for field_child in field:
                                        _translate_field(field_child)
                                if Transaction().language != 'en_US':
                                    _translate_field(field2)

                                relation_obj = pool.get(relation)
                                if hasattr(relation_obj, '_view_look_dom_arch'):
                                    xarch, xfields = \
                                            relation_obj._view_look_dom_arch(
                                                    field2, field.tag)
                                    views[field.tag] = {
                                        'arch': xarch,
                                        'fields': xfields
                                    }
                                element.remove(field)
                        attrs = {'views': views}
                    fields_attrs[element.get(attr)] = attrs
            if element.get('name') in fields_width:
                element.set('width', str(fields_width[element.get('name')]))

        # convert attributes into pyson
        encoder = PYSONEncoder()
        for attr in ('states', 'domain', 'context', 'digits', 'add_remove',
                'spell', 'colors'):
            if element.get(attr):
                element.set(attr, encoder.encode(safe_eval(element.get(attr),
                    CONTEXT)))

        # translate view
        if Transaction().language != 'en_US' and not result:
            for attr in ('string', 'sum', 'confirm', 'help'):
                if element.get(attr):
                    trans = translation_obj._get_source(self._name, 'view',
                            Transaction().language, element.get(attr))
                    if trans:
                        element.set(attr, trans)

        # Set header string
        if element.tag in ('form', 'tree', 'graph'):
            element.set('string', self.view_header_get(
                element.get('string') or '', view_type=element.tag))

        if element.tag == 'tree' and element.get('sequence'):
            fields_attrs.setdefault(element.get('sequence'), {})

        if childs:
            for field in element:
                fields_attrs.update(self.__view_look_dom(field, type,
                    fields_width=fields_width))
        return fields_attrs
