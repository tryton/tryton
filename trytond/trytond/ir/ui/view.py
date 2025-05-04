# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import json
import os

from lxml import etree
from sql import Literal, Null

from trytond.cache import Cache, MemoryCache
from trytond.i18n import gettext
from trytond.model import Index, ModelSQL, ModelView, fields, sequence_ordered
from trytond.model.exceptions import ValidationError
from trytond.pool import Pool
from trytond.pyson import PYSON, Bool, Eval, If, PYSONDecoder
from trytond.rpc import RPC
from trytond.tools import file_open
from trytond.transaction import Transaction
from trytond.wizard import Button, StateView, Wizard

from ..action import DomainError, ViewError

# Numbers taken from Bootstrap's breakpoints
WIDTH_BREAKPOINTS = [
    1400,
    1200,
    992,
    768,
    576,
    ]


class XMLError(ValidationError):
    pass


class View(
        fields.fmany2one(
            'model_ref', 'model', 'ir.model,name', "Model",
            ondelete='CASCADE'),
        fields.fmany2one(
            'field_children', 'field_childs,model',
            'ir.model.field,name,model',
            "Children Field",
            domain=[
                ('model', '=', Eval('model')),
                ],
            states={
                'invisible': Eval('type') != 'tree',
                }),
        fields.fmany2one(
            'module_ref', 'module', 'ir.module,name', "Module",
            readonly=True, ondelete='CASCADE'),
        sequence_ordered('priority', "Priority"), ModelSQL, ModelView):
    "View"
    __name__ = 'ir.ui.view'
    model = fields.Char('Model', states={
            'required': Eval('type') != 'board',
            })
    type = fields.Selection([
            (None, ''),
            ('tree', 'Tree'),
            ('form', 'Form'),
            ('graph', 'Graph'),
            ('calendar', 'Calendar'),
            ('board', 'Board'),
            ('list-form', "List Form"),
            ], 'View Type',
        domain=[
            If(Bool(Eval('inherit')),
                ('type', '=', None),
                ('type', '!=', None)),
            ],
        depends=['inherit'])
    type_string = type.translated('type')
    data = fields.Text('Data')
    name = fields.Char('Name', states={
            'invisible': ~(Eval('module') & Eval('name')),
            }, depends=['module'], readonly=True)
    arch = fields.Function(fields.Text('View Architecture', states={
                'readonly': Bool(Eval('name')),
                }, depends=['name']), 'get_arch', setter='set_arch')
    basis = fields.Function(fields.Boolean("Basis"), 'get_basis')
    inherit = fields.Many2One('ir.ui.view', 'Inherited View',
            ondelete='CASCADE')
    extensions = fields.One2Many(
        'ir.ui.view', 'inherit', "Extensions",
        filter=[
            ('basis', '=', False),
            ],
        domain=[
            ('model', '=', Eval('model')),
            ('type', '=', None),
            ],
        states={
            'invisible': ~Eval('type'),
            },
        order=[('id', None)])
    field_childs = fields.Char('Children Field', states={
            'invisible': Eval('type') != 'tree',
            }, depends=['type'])
    module = fields.Char('Module', states={
            'invisible': ~Eval('module'),
            }, readonly=True)
    domain = fields.Char('Domain', states={
            'invisible': ~Eval('inherit'),
            }, depends=['inherit'])
    _get_rng_cache = MemoryCache('ir_ui_view.get_rng', context=False)
    _view_get_cache = Cache('ir_ui_view.view_get')
    __module_index = None

    @classmethod
    def __setup__(cls):
        super().__setup__()
        table = cls.__table__()
        cls.priority.required = True

        cls.__rpc__['view_get'] = RPC(instantiate=0, cache=dict(days=1))
        cls._buttons.update({
                'show': {
                    'readonly': Eval('type') != 'form',
                    'invisible': ~Eval('basis', False),
                    'depends': ['type', 'basis'],
                    },
                })
        cls._sql_indexes.update({
                Index(table,
                    (table.model, Index.Equality()),
                    (table.inherit, Index.Range())),
                Index(
                    table,
                    (table.id, Index.Range()),
                    (table.inherit, Index.Range())),
                })

    @staticmethod
    def default_priority():
        return 16

    @staticmethod
    def default_module():
        return Transaction().context.get('module')

    def get_basis(self, name):
        return not self.inherit or self.model != self.inherit.model

    @classmethod
    def domain_basis(cls, domain, tables):
        table, _ = tables[None]
        if 'inherit' not in tables:
            inherit = cls.__table__()
            tables['inherit'] = {
                None: (inherit, table.inherit == inherit.id),
                }
        else:
            inherit, _ = tables['inherit'][None]
        expression = (table.inherit == Null) | (table.model != inherit.model)

        _, operator, value = domain
        if operator in {'=', '!='}:
            if (operator == '=') != value:
                expression = ~expression
        elif operator in {'in', 'not in'}:
            if True in value and False not in value:
                pass
            elif False in value and True not in value:
                expression = ~expression
            else:
                expression = Literal(True)
        else:
            expression = Literal(True)
        return expression

    def get_rec_name(self, name):
        return ' '.join(filter(None, [
                    self.model_ref.rec_name if self.model_ref else '',
                    '(%s)' % (
                        self.inherit.rec_name if self.inherit else
                        self.type_string),
                    ]))

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('model_ref.rec_name', *clause[1:])]

    @classmethod
    @ModelView.button_action('ir.act_view_show')
    def show(cls, views):
        pass

    @classmethod
    def get_rng(cls, type_):
        key = (cls.__name__, type_)
        rng = cls._get_rng_cache.get(key)
        if rng is None:
            if type_ == 'list-form':
                type_ = 'form'
            rng_name = os.path.join(os.path.dirname(__file__), type_ + '.rng')
            with open(rng_name, 'rb') as fp:
                rng = etree.fromstring(fp.read())
            cls._get_rng_cache.set(key, rng)
        return rng

    @property
    def rng_type(self):
        if self.inherit:
            return self.inherit.rng_type
        return self.type

    @classmethod
    def validate(cls, views):
        super().validate(views)
        cls.check_xml(views)

    @classmethod
    def check_xml(cls, views):
        "Check XML"
        for view in views:
            if not view.arch:
                continue
            xml = view.arch.strip()
            if not xml:
                continue
            tree = etree.fromstring(xml)

            if hasattr(etree, 'RelaxNG'):
                validator = etree.RelaxNG(etree=cls.get_rng(view.rng_type))
                if not validator.validate(tree):
                    error_log = '\n'.join(map(str,
                            validator.error_log.filter_from_errors()))
                    raise XMLError(
                        gettext('ir.msg_view_invalid_xml', name=view.rec_name),
                        error_log)
            root_element = tree.getroottree().getroot()

            # validate pyson attributes
            validates = {
                'states': fields.states_validate,
            }

            def encode(element):
                for attr in ('states', 'domain', 'spell'):
                    if not element.get(attr):
                        continue
                    try:
                        value = PYSONDecoder().decode(element.get(attr))
                        validates.get(attr, lambda a: True)(value)
                    except Exception as e:
                        error_log = '%s: <%s %s="%s"/>' % (
                            e, element.get('id') or element.get('name'), attr,
                            element.get(attr))
                        raise XMLError(
                            gettext(
                                'ir.msg_view_invalid_xml', name=view.rec_name),
                            error_log) from e
                for child in element:
                    encode(child)
            encode(root_element)

    def get_arch(self, name):
        value = None
        if self.name and self.module:
            path = os.path.join(self.module, 'view', self.name + '.xml')
            try:
                with file_open(path,
                        subdir='modules', mode='r', encoding='utf-8') as fp:
                    value = fp.read()
            except IOError:
                pass
        if not value:
            value = self.data
        return value

    @classmethod
    def set_arch(cls, views, name, value):
        cls.write(views, {'data': value})

    @classmethod
    def on_modification(cls, mode, records, field_names=None):
        super().on_modification(mode, records, field_names=field_names)
        cls._view_get_cache.clear()
        ModelView._fields_view_get_cache.clear()

    @property
    def _module_index(self):
        from trytond.modules import create_graph, get_modules
        if self.__class__.__module_index is None:
            graph = create_graph(get_modules(with_test=Pool.test))
            modules = [m.name for m in graph]
            self.__class__.__module_index = {
                m: i for i, m in enumerate(reversed(modules))}
        return self.__class__.__module_index

    def view_get(self, model=None):
        key = (self.id, model)
        result = self._view_get_cache.get(key)
        if result:
            return result
        if self.inherit:
            if self.inherit.model == model:
                return self.inherit.view_get(model=model)
            else:
                arch = self.inherit.view_get(self.inherit.model)['arch']
        else:
            arch = self.arch

        views = self.__class__.search(['OR', [
                    ('inherit', '=', self.id),
                    ('model', '=', model),
                    ], [
                    ('id', '=', self.id),
                    ('inherit', '!=', None),
                    ],
                ])
        views.sort(
            key=lambda v: self._module_index.get(v.module, -1), reverse=True)
        parser = etree.XMLParser(remove_comments=True, resolve_entities=False)
        tree = etree.fromstring(arch, parser=parser)
        decoder = PYSONDecoder({'context': Transaction().context})
        for view in views:
            if view.domain and not decoder.decode(view.domain):
                continue
            if not view.arch or not view.arch.strip():
                continue
            tree_inherit = etree.fromstring(view.arch, parser=parser)
            tree = self.inherit_apply(tree, tree_inherit)
        if model:
            root = tree.getroottree().getroot()
            self._translate(root, model, Transaction().language)
        arch = etree.tostring(tree, encoding='utf-8').decode('utf-8')
        result = {
            'type': self.rng_type,
            'view_id': self.id,
            'arch': arch,
            'field_childs': self.field_childs,
            }
        self._view_get_cache.set(key, result)
        return result

    @classmethod
    def inherit_apply(cls, tree, inherit):
        root_inherit = inherit.getroottree().getroot()
        for element in root_inherit:
            expr = element.get('expr')
            targets = tree.xpath(expr)
            assert targets, "No elements found for expression %r" % expr
            for target in targets:
                position = element.get('position', 'inside')
                new_tree = getattr(cls, '_inherit_apply_%s' % position)(
                    tree, element, target)
                if new_tree:
                    tree = new_tree
        return tree

    @classmethod
    def _inherit_apply_replace(cls, tree, element, target):
        parent = target.getparent()
        if parent is None:
            tree, = element
            return tree
        cls._inherit_apply_after(tree, element, target)
        parent.remove(target)

    @classmethod
    def _inherit_apply_replace_attributes(cls, tree, element, target):
        child, = element
        for attr in child.attrib:
            target.set(attr, child.get(attr))

    @classmethod
    def _inherit_apply_inside(cls, tree, element, target):
        target.extend(list(element))

    @classmethod
    def _inherit_apply_after(cls, tree, element, target):
        parent = target.getparent()
        next_ = target.getnext()
        if next_ is not None:
            for child in element:
                index = parent.index(next_)
                parent.insert(index, child)
        else:
            parent.extend(list(element))

    @classmethod
    def _inherit_apply_before(cls, tree, element, target):
        parent = target.getparent()
        for child in element:
            index = parent.index(target)
            parent.insert(index, child)

    @classmethod
    def _translate(cls, element, model, language):
        pool = Pool()
        Translation = pool.get('ir.translation')
        for attr in ['string', 'sum', 'confirm', 'help']:
            if element.get(attr):
                translation = Translation.get_source(
                    model, 'view', language, element.get(attr))
                if translation:
                    element.set(attr, translation)
        for child in element:
            cls._translate(child, model, language)


class ShowViewStart(ModelView):
    'Show view'
    __name__ = 'ir.ui.view.show.start'
    __no_slots__ = True


class ShowView(Wizard):
    'Show view'
    __name__ = 'ir.ui.view.show'

    class ShowStateView(StateView):

        def __init__(self, model_name, buttons):
            StateView.__init__(self, model_name, None, buttons)

        def get_view(self, wizard, state_name):
            pool = Pool()
            View = pool.get('ir.ui.view')
            view_id = Transaction().context.get('active_id')
            if not view_id:
                # Set type to please ModuleTestCase.test_wizards
                return {'type': 'form'}
            view = View(view_id)
            Model = pool.get(view.model)
            return Model.fields_view_get(view_id=view.id)

        def get_defaults(self, wizard, state_name, fields):
            return {}

    start = ShowStateView('ir.ui.view.show.start', [
            Button('Close', 'end', 'tryton-close', default=True),
            ])


class ViewTreeWidth(
        fields.fmany2one(
            'model_ref', 'model', 'ir.model,name', "Model",
            required=True, ondelete='CASCADE'),
        fields.fmany2one(
            'field_ref', 'field,model', 'ir.model.field,name,model', "Field",
            required=True, ondelete='CASCADE',
            domain=[
                ('model', '=', Eval('model')),
                ]),
        ModelSQL, ModelView):
    "View Tree Width"
    __name__ = 'ir.ui.view_tree_width'
    model = fields.Char('Model', required=True)
    field = fields.Char('Field', required=True)
    user = fields.Many2One('res.user', 'User', required=True,
        ondelete='CASCADE')
    screen_width = fields.Integer("Screen Width")
    width = fields.Integer('Width', required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        table = cls.__table__()
        cls.__rpc__.update({
                'set_width': RPC(readonly=False),
                'reset_width': RPC(readonly=False),
                })
        cls._sql_indexes.add(
            Index(
                table,
                (table.user, Index.Range()),
                (table.model, Index.Equality()),
                (table.field, Index.Equality())))

    def get_rec_name(self, name):
        return f'{self.field_ref.rec_name} @ {self.model_ref.rec_name}'

    @classmethod
    def search_rec_name(cls, name, clause):
        operator = clause[1]
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('model_ref.rec_name', *clause[1:]),
            ('field_ref.rec_name', *clause[1:]),
            ]

    @classmethod
    def on_modification(cls, mode, records, field_names=None):
        super().on_modification(mode, records, field_names=field_names)
        ModelView._fields_view_get_cache.clear()

    @classmethod
    def get_width(cls, model, width):
        for screen_width in WIDTH_BREAKPOINTS:
            if width >= screen_width:
                break
        else:
            screen_width = 0

        user = Transaction().user
        records = cls.search([
            ('user', '=', user),
            ('model', '=', model),
            ('screen_width', '=', screen_width),
            ])

        if not records:
            records = cls.search([
                ('user', '=', user),
                ('model', '=', model),
                ['OR',
                    ('screen_width', '<=', screen_width),
                    ('screen_width', '=', None),
                    ],
                ],
                order=[
                    ('screen_width', 'DESC NULLS LAST'),
                    ])
        widths = {}
        for width in records:
            if width.field not in widths:
                widths[width.field] = width.width
        return widths

    @classmethod
    def set_width(cls, model, fields, width):
        '''
        Set width for the current user on the model.
        fields is a dictionary with key: field name and value: width.
        '''
        for screen_width in WIDTH_BREAKPOINTS:
            if width >= screen_width:
                break
        else:
            screen_width = 0

        user_id = Transaction().user
        records = cls.search([
                ('user', '=', user_id),
                ('model', '=', model),
                ('field', 'in', list(fields.keys())),
                ['OR',
                    ('screen_width', '=', screen_width),
                    ('screen_width', '=', None),
                    ],
                ])

        fields = fields.copy()
        to_save, to_delete = [], []
        for tree_width in records:
            if tree_width.screen_width == screen_width:
                if tree_width.field in fields:
                    tree_width.width = fields.pop(tree_width.field)
                    to_save.append(tree_width)
                else:
                    to_delete.append(tree_width)

        for name, width in fields.items():
            to_save.append(cls(
                    user=user_id,
                    model=model,
                    field=name,
                    screen_width=screen_width,
                    width=width))

        if to_save:
            cls.save(to_save)
        if to_delete:
            cls.delete(to_delete)

    @classmethod
    def reset_width(cls, model, width):
        for screen_width in WIDTH_BREAKPOINTS:
            if width >= screen_width:
                break
        else:
            screen_width = 0

        user_id = Transaction().user
        records = cls.search([
                ('user', '=', user_id),
                ('model', '=', model),
                ['OR',
                    ('screen_width', '=', screen_width),
                    ('screen_width', '=', None),
                    ],
                ])
        cls.delete(records)


class ViewTreeOptional(
        fields.fmany2one(
            'model_ref', 'model', 'ir.model,name', "Model",
            required=True, ondelete='CASCADE'),
        fields.fmany2one(
            'field_ref', 'field,model', 'ir.model.field,name,model', "Field",
            required=True, ondelete='CASCADE',
            domain=[
                ('model', '=', Eval('model')),
                ]),
        ModelSQL, ModelView):
    "View Tree Optional"
    __name__ = 'ir.ui.view_tree_optional'
    view = fields.Many2One(
        'ir.ui.view', "View", required=True, ondelete='CASCADE')
    user = fields.Many2One(
        'res.user', "User", required=True, ondelete='CASCADE')
    model = fields.Char("Model", required=True)
    field = fields.Char("Field", required=True)
    value = fields.Boolean("Value")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__rpc__.update({
                'set_optional': RPC(readonly=False),
                })
        table = cls.__table__()
        cls._sql_indexes.add(
            Index(
                table,
                (table.user, Index.Range()),
                (table.view, Index.Range())))

    @classmethod
    def __register__(cls, module):
        pool = Pool()
        View = pool.get('ir.ui.view')
        table = cls.__table__()
        view = View.__table__()
        table_h = cls.__table_handler__(module)
        cursor = Transaction().connection.cursor()

        # Migration from 7.2: rename view_id into view
        table_h.column_rename('view_id', 'view')

        super().__register__(module)

        # Migration from 7.2: add model
        cursor.execute(*table.update(
                [table.model],
                [view.select(view.model, where=view.id == table.view)],
                where=table.model == Null))

    @classmethod
    def validate_fields(cls, records, fields_names):
        super().validate_fields(records, fields_names)
        cls.check_view(records, fields_names)

    @classmethod
    def check_view(cls, records, fields_names=None):
        if fields_names and 'view' not in fields_names:
            return
        for record in records:
            if record.view and record.view.rng_type != 'tree':
                raise ViewError(gettext(
                        'ir.msg_view_tree_optional_type',
                        view=record.view.rec_name))

    @classmethod
    def on_modification(cls, mode, record, field_names=None):
        super().on_modification(mode, record, field_names=field_names)
        ModelView._fields_view_get_cache.clear()

    @classmethod
    def set_optional(cls, view_id, fields):
        "Store optional field that must be displayed"
        pool = Pool()
        View = pool.get('ir.ui.view')
        user = Transaction().user
        view = View(view_id)
        records = cls.search([
                ('view', '=', view.id),
                ('user', '=', user),
                ('field', 'in', list(fields)),
                ])
        cls.delete(records)
        to_create = []
        for field, value in fields.items():
            to_create.append({
                    'view': view,
                    'user': user,
                    'model': view.model,
                    'field': field,
                    'value': bool(value),
                    })
        if to_create:
            cls.create(to_create)


class ViewTreeState(
        fields.fmany2one(
            'model_ref', 'model', 'ir.model,name', "Model",
            required=True, ondelete='CASCADE'),
        fields.fmany2one(
            'child_field', 'child_name,model', 'ir.model.field,name,model',
            "Child Field", ondelete='CASCADE',
            domain=[
                ('model', '=', Eval('model')),
                ]),
        ModelSQL, ModelView):
    'View Tree State'
    __name__ = 'ir.ui.view_tree_state'
    _rec_name = 'model'
    model = fields.Char('Model', required=True)
    domain = fields.Char('Domain', required=True)
    user = fields.Many2One('res.user', 'User', required=True,
            ondelete='CASCADE')
    child_name = fields.Char('Child Name')
    nodes = fields.Text('Expanded Nodes')
    selected_nodes = fields.Text('Selected Nodes')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__rpc__.update({
                'set': RPC(readonly=False, check_access=False),
                'get': RPC(check_access=False, cache=dict(days=1)),
                })

        table = cls.__table__()
        cls._sql_indexes.add(
            Index(
                table,
                (table.user, Index.Range()),
                (table.model, Index.Equality()),
                (table.child_name, Index.Equality()),
                (table.domain, Index.Equality())))

    @staticmethod
    def default_nodes():
        return '[]'

    @staticmethod
    def default_selected_nodes():
        return '[]'

    @classmethod
    def set(cls, model, domain, child_name, nodes, selected_nodes):
        # Normalize the json domain
        domain = json.dumps(json.loads(domain), separators=(',', ':'))
        current_user = Transaction().user
        records = cls.search([
                ('user', '=', current_user),
                ('model', '=', model),
                ('domain', '=', domain),
                ('child_name', '=', child_name),
                ])
        cls.delete(records)
        cls.create([{
                    'user': current_user,
                    'model': model,
                    'domain': domain,
                    'child_name': child_name,
                    'nodes': nodes,
                    'selected_nodes': selected_nodes,
                    }])

    @classmethod
    def get(cls, model, domain, child_name):
        # Normalize the json domain
        domain = json.dumps(json.loads(domain), separators=(',', ':'))
        current_user = Transaction().user
        try:
            expanded_info, = cls.search([
                    ('user', '=', current_user),
                    ('model', '=', model),
                    ('domain', '=', domain),
                    ('child_name', '=', child_name),
                    ],
                limit=1)
        except ValueError:
            return (cls.default_nodes(), cls.default_selected_nodes())
        state = cls(expanded_info)
        return (state.nodes or cls.default_nodes(),
            state.selected_nodes or cls.default_selected_nodes())


class ViewSearch(
        fields.fmany2one(
            'model_ref', 'model', 'ir.model,name', "Model",
            required=True, ondelete='CASCADE'),
        ModelSQL, ModelView):
    "View Search"
    __name__ = 'ir.ui.view_search'

    name = fields.Char('Name', required=True)
    model = fields.Char('Model', required=True)
    domain = fields.Char('Domain', help="The PYSON domain.")
    user = fields.Many2One('res.user', 'User', ondelete='CASCADE')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__rpc__.update({
                'get': RPC(check_access=False),
                'set': RPC(check_access=False, readonly=False),
                'unset': RPC(check_access=False, readonly=False),
                })

    @staticmethod
    def default_user():
        return Transaction().user

    @classmethod
    def validate_fields(cls, searches, field_names):
        super().validate_fields(searches, field_names)
        cls.check_domain(searches, field_names)

    @classmethod
    def check_domain(cls, searches, field_names):
        decoder = PYSONDecoder()
        if field_names and 'domain' not in field_names:
            return
        for search in searches:
            try:
                value = decoder.decode(search.domain)
            except Exception as exception:
                raise DomainError(
                    gettext('ir.msg_view_search_invalid_domain',
                        domain=search.domain,
                        search=search.rec_name)) from exception
            if isinstance(value, PYSON):
                if not value.types() == set([list]):
                    raise DomainError(
                        gettext('ir.msg_view_search_invalid_domain',
                            domain=search.domain,
                            search=search.rec_name))
            elif not isinstance(value, list):
                raise DomainError(
                    gettext('ir.msg_view_search_invalid_domain',
                        domain=search.domain,
                        search=search.rec_name))
            else:
                try:
                    fields.domain_validate(value)
                except Exception as exception:
                    raise DomainError(
                        gettext('ir.msg_view_search_invalid_domain',
                            domain=search.domain,
                            search=search.rec_name)) from exception

    @classmethod
    def get(cls):
        decoder = PYSONDecoder()
        user = Transaction().user
        searches = cls.search_read(['OR',
                ('user', '=', user),
                ('user', '=', None),
                ],
            order=[('model', 'ASC'), ('name', 'ASC')],
            fields_names=['id', 'name', 'model', 'domain', '_delete'])
        result = {}
        for search in searches:
            result.setdefault(search['model'], []).append((
                    search['id'],
                    search['name'],
                    decoder.decode(search['domain']),
                    search['_delete']))
        return result

    @classmethod
    def set(cls, name, model, domain):
        user = Transaction().user
        search, = cls.create([{
                    'name': name,
                    'model': model,
                    'domain': domain,
                    'user': user,
                    }])
        return search.id

    @classmethod
    def unset(cls, id):
        user = Transaction().user
        cls.delete(cls.search([
                    ('id', '=', id),
                    ('user', '=', user),
                    ]))
