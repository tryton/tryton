# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import heapq
import json
import logging
import re
from collections import defaultdict
from itertools import groupby

from sql import Literal, Null
from sql.aggregate import Max
from sql.conditionals import Case
from sql.operators import Equal

from trytond.cache import Cache
from trytond.config import config
from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, EvalEnvironment, Exclude, Index, ModelSingleton,
    ModelSQL, ModelView, Unique, Workflow, fields)
from trytond.model.exceptions import AccessError, ValidationError
from trytond.pool import Pool
from trytond.protocols.jsonrpc import JSONDecoder, JSONEncoder
from trytond.pyson import Bool, Eval, PYSONDecoder
from trytond.report import Report
from trytond.rpc import RPC
from trytond.tools import cursor_dict, grouped_slice, is_instance_method
from trytond.tools.string_ import StringMatcher
from trytond.transaction import Transaction, without_check_access
from trytond.wizard import Button, StateAction, StateView, Wizard

from .resource import ResourceAccessMixin

logger = logging.getLogger(__name__)
_request_timeout = config.getint('request', 'timeout', default=0)


class ConditionError(ValidationError):
    pass


class Model(
        fields.fmany2one(
            'module_ref', 'module', 'ir.module,name', "Module",
            readonly=True, ondelete='CASCADE',
            help="Module in which this model is defined."),
        ModelSQL, ModelView):
    "Model"
    __name__ = 'ir.model'
    _order_name = 'model'
    name = fields.Char('Model Description', translate=True, loading='lazy',
        states={
            'readonly': Bool(Eval('module')),
            },
        depends=['module'])
    model = fields.Char('Model Name', required=True,
        states={
            'readonly': Bool(Eval('module')),
            },
        depends=['module'])
    info = fields.Text('Information',
        states={
            'readonly': Bool(Eval('module')),
            },
        depends=['module'])
    module = fields.Char("Module", readonly=True)
    global_search_p = fields.Boolean('Global Search')
    fields = fields.One2Many('ir.model.field', 'model_ref', "Fields")
    _get_names_cache = Cache('ir.model.get_names')

    @classmethod
    def __setup__(cls):
        super(Model, cls).__setup__()
        table = cls.__table__()
        cls._sql_constraints += [
            ('model_uniq', Unique(table, table.model),
                'The model must be unique!'),
            ]
        cls._order.insert(0, ('model', 'ASC'))
        cls.__rpc__.update({
                'list_models': RPC(),
                'list_history': RPC(),
                'get_notification': RPC(),
                'get_names': RPC(),
                'global_search': RPC(timeout=_request_timeout),
                })

    @classmethod
    def register(cls, model, module_name):
        cursor = Transaction().connection.cursor()

        ir_model = cls.__table__()
        cursor.execute(*ir_model.select(ir_model.id,
                where=ir_model.model == model.__name__))
        model_id = None
        if cursor.rowcount == -1 or cursor.rowcount is None:
            data = cursor.fetchone()
            if data:
                model_id, = data
        elif cursor.rowcount != 0:
            model_id, = cursor.fetchone()
        if not model_id:
            cursor.execute(*ir_model.insert(
                    [ir_model.model, ir_model.name, ir_model.info,
                        ir_model.module],
                    [[
                            model.__name__, model._get_name(), model.__doc__,
                            module_name]]))
            cursor.execute(*ir_model.select(ir_model.id,
                    where=ir_model.model == model.__name__))
            (model_id,) = cursor.fetchone()
        elif model.__doc__:
            cursor.execute(*ir_model.update(
                    [ir_model.name, ir_model.info],
                    [model._get_name(), model.__doc__],
                    where=ir_model.id == model_id))
        cls._get_names_cache.clear()
        return model_id

    @classmethod
    def clean(cls):
        pool = Pool()
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        ir_model = cls.__table__()
        cursor.execute(*ir_model.select(ir_model.model, ir_model.id))
        for model, id_ in cursor:
            try:
                pool.get(model)
            except KeyError:
                logger.info("remove model: %s", model)
                try:
                    cls.delete([cls(id_)])
                    transaction.commit()
                except Exception:
                    transaction.rollback()
                    logger.error(
                        "could not delete model: %s", model, exc_info=True)

    @classmethod
    def list_models(cls):
        'Return a list of all models names'
        models = cls.search([], order=[
                ('module', 'ASC'),  # Optimization assumption
                ('model', 'ASC'),
                ('id', 'ASC'),
                ])
        return [m.model for m in models]

    @classmethod
    def list_history(cls):
        'Return a list of all models with history'
        return [name for name, model in Pool().iterobject()
            if getattr(model, '_history', False)]

    @classmethod
    def get_notification(cls):
        "Return a dictionary of model to notify with the depending fields"
        return {
            name: list(model._on_change_notify_depends)
            for name, model in Pool().iterobject()
            if issubclass(model, ModelView)
            and model._on_change_notify_depends}

    @classmethod
    def get_name_items(cls):
        "Return a list of couple mapping models to names"
        items = cls._get_names_cache.get('items')
        if items is None:
            models = cls.search([])
            items = [(m.model, m.name) for m in models]
            cls._get_names_cache.set('items', items)
        return items

    @classmethod
    def get_names(cls):
        "Return a dictionary mapping models to names"
        dict_ = cls._get_names_cache.get('dict')
        if dict_ is None:
            dict_ = dict(cls.get_name_items())
            cls._get_names_cache.set('dict', dict_)
        return dict_

    @classmethod
    def global_search(cls, text, limit, menu='ir.ui.menu'):
        """
        Search on models for text including menu
        Returns a list of tuple (ratio, model, model_name, id, name, icon)
        The size of the list is limited to limit
        """
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')

        if not limit > 0:
            raise ValueError('limit must be > 0: %r' % (limit,))

        models = cls.search(['OR',
                ('global_search_p', '=', True),
                ('model', '=', menu),
                ])
        access = ModelAccess.get_access([m.model for m in models])
        s = StringMatcher()
        if isinstance(text, bytes):
            text = text.decode('utf-8')
        s.set_seq2(text)

        def generate():
            for model in models:
                if not access[model.model]['read']:
                    continue
                Model = pool.get(model.model)
                if not hasattr(Model, 'search_global'):
                    continue
                for record, name, icon in Model.search_global(text):
                    if isinstance(name, bytes):
                        name = name.decode('utf-8')
                    s.set_seq1(name)
                    yield (s.ratio(), model.model, model.rec_name,
                        record.id, name, icon)
        return heapq.nlargest(int(limit), generate())

    @classmethod
    def get_name(cls, model):
        return cls.get_names().get(model, model)


class ModelField(
        fields.fmany2one(
            'model_ref', 'model', 'ir.model,model', "Model",
            required=True, ondelete='CASCADE'),
        fields.fmany2one(
            'module_ref', 'module', 'ir.module,name', "Module",
            readonly=True, ondelete='CASCADE',
            help="Module in which this field is defined."),
        ModelSQL, ModelView):
    "Model field"
    __name__ = 'ir.model.field'
    name = fields.Char('Name', required=True,
        states={
            'readonly': Bool(Eval('module')),
            },
        depends=['module'])
    relation = fields.Char('Model Relation',
        states={
            'readonly': Bool(Eval('module')),
            },
        depends=['module'])
    model = fields.Char(
        "Model", required=True,
        states={
            'readonly': Bool(Eval('module')),
            })
    field_description = fields.Char('Field Description', translate=True,
        loading='lazy',
        states={
            'readonly': Bool(Eval('module')),
            },
        depends=['module'])
    ttype = fields.Char('Field Type',
        states={
            'readonly': Bool(Eval('module')),
            },
        depends=['module'])
    help = fields.Text('Help', translate=True, loading='lazy',
        states={
            'readonly': Bool(Eval('module')),
            },
        depends=['module'])
    module = fields.Char("Module", readonly=True)
    access = fields.Boolean(
        "Access",
        states={
            'invisible': ~Eval('relation'),
            },
        depends=['relation'],
        help="If checked, the access right on the model of the field "
        "is also tested against the relation of the field.")

    _get_name_cache = Cache('ir.model.field.get_name')

    @classmethod
    def __setup__(cls):
        super(ModelField, cls).__setup__()
        cls.__access__.add('model_ref')
        table = cls.__table__()
        cls._sql_constraints += [
            ('name_model_uniq', Unique(table, table.name, table.model),
                'The field name in model must be unique!'),
            ]
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def __register__(cls, module):
        pool = Pool()
        Model = pool.get('ir.model')
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        table_h = cls.__table_handler__(module)
        table = cls.__table__()
        model = Model.__table__()

        # Migration from 7.0: model as char
        if (table_h.column_exist('model')
                and table_h.column_is_type('model', 'INTEGER')):
            table_h.column_rename('model', '_temp_model')
            table_h.add_column('model', 'VARCHAR')
            cursor.execute(*table.update(
                    [table.model], [model.model],
                    from_=[model],
                    where=table._temp_model == model.id))
            table_h.drop_column('_temp_model')

        super().__register__(module)

    @classmethod
    def register(cls, model, module_name, model_id):
        cursor = Transaction().connection.cursor()

        ir_model_field = cls.__table__()

        cursor.execute(*ir_model_field
            .select(
                ir_model_field.id.as_('id'),
                ir_model_field.name.as_('name'),
                ir_model_field.field_description.as_('field_description'),
                ir_model_field.ttype.as_('ttype'),
                ir_model_field.relation.as_('relation'),
                ir_model_field.module.as_('module'),
                ir_model_field.help.as_('help'),
                ir_model_field.access.as_('access'),
                where=ir_model_field.model == model.__name__))
        model_fields = {f['name']: f for f in cursor_dict(cursor)}

        for field_name, field in model._fields.items():
            if hasattr(field, 'model_name'):
                relation = field.model_name
            elif hasattr(field, 'relation_name'):
                relation = field.relation_name
            else:
                relation = None
            access = field_name in model.__access__

            if field_name not in model_fields:
                cursor.execute(*ir_model_field.insert([
                            ir_model_field.model,
                            ir_model_field.name,
                            ir_model_field.field_description,
                            ir_model_field.ttype,
                            ir_model_field.relation,
                            ir_model_field.help,
                            ir_model_field.module,
                            ir_model_field.access,
                            ], [[
                                model.__name__,
                                field_name,
                                field.string,
                                field._type,
                                relation,
                                field.help,
                                module_name,
                                access,
                                ]]))
            elif (model_fields[field_name]['field_description'] != field.string
                    or model_fields[field_name]['ttype'] != field._type
                    or model_fields[field_name]['relation'] != relation
                    or model_fields[field_name]['help'] != field.help
                    or model_fields[field_name]['access'] != access):
                cursor.execute(*ir_model_field.update([
                            ir_model_field.field_description,
                            ir_model_field.ttype,
                            ir_model_field.relation,
                            ir_model_field.help,
                            ir_model_field.access,
                            ], [
                            field.string,
                            field._type,
                            relation,
                            field.help,
                            access],
                        where=(ir_model_field.id
                            == model_fields[field_name]['id'])))

    @classmethod
    def clean(cls):
        pool = Pool()
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        ir_model_field = cls.__table__()
        cursor.execute(*ir_model_field.select(
                ir_model_field.model, ir_model_field.name, ir_model_field.id))
        for model, field, id_ in cursor:
            Model = pool.get(model)
            if field not in Model._fields:
                logger.info("remove field: %s.%s", model, field)
                try:
                    cls.delete([cls(id_)])
                    transaction.commit()
                except Exception:
                    transaction.rollback()
                    logger.error(
                        "could not delete field: %s.%s", model, field,
                        exc_info=True)

    @staticmethod
    def default_name():
        return 'No Name'

    @staticmethod
    def default_field_description():
        return 'No description available'

    def get_rec_name(self, name):
        if self.field_description:
            return '%s (%s)' % (self.field_description, self.name)
        else:
            return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('field_description',) + tuple(clause[1:]),
            ('name',) + tuple(clause[1:]),
            ]

    @classmethod
    def get_name(cls, model, field):
        name = cls._get_name_cache.get((model, field))
        if name is None:
            fields = cls.search([
                    ('model.model', '=', model),
                    ('name', '=', field),
                    ], limit=1)
            if fields:
                field, = fields
                name = field.field_description
                cls._get_name_cache.set((model, field), name)
            else:
                name = field
        return name

    @classmethod
    def read(cls, ids, fields_names):
        pool = Pool()
        Translation = pool.get('ir.translation')

        to_delete = []
        if Transaction().context.get('language'):
            if 'field_description' in fields_names \
                    or 'help' in fields_names:
                if 'model' not in fields_names:
                    fields_names.append('model')
                    to_delete.append('model')
                if 'name' not in fields_names:
                    fields_names.append('name')
                    to_delete.append('name')

        res = super(ModelField, cls).read(ids, fields_names)

        if (Transaction().context.get('language')
                and ('field_description' in fields_names
                    or 'help' in fields_names)):
            trans_args = []
            for rec in res:
                if 'field_description' in fields_names:
                    trans_args.append((
                            rec['model'] + ',' + rec['name'],
                            'field', Transaction().language, None))
                if 'help' in fields_names:
                    trans_args.append((
                            rec['model'] + ',' + rec['name'],
                            'help', Transaction().language, None))
            Translation.get_sources(trans_args)
            for rec in res:
                if 'field_description' in fields_names:
                    res_trans = Translation.get_source(
                            rec['model'] + ',' + rec['name'],
                            'field', Transaction().language)
                    if res_trans:
                        rec['field_description'] = res_trans
                if 'help' in fields_names:
                    res_trans = Translation.get_source(
                            rec['model'] + ',' + rec['name'],
                            'help', Transaction().language)
                    if res_trans:
                        rec['help'] = res_trans

        if to_delete:
            for rec in res:
                for field in to_delete:
                    del rec[field]
        return res


class ModelAccess(
        fields.fmany2one(
            'model_ref', 'model', 'ir.model,model', "Model",
            required=True, ondelete='CASCADE'),
        DeactivableMixin, ModelSQL, ModelView):
    "Model access"
    __name__ = 'ir.model.access'
    model = fields.Char("Model", required=True)
    group = fields.Many2One('res.group', 'Group',
            ondelete="CASCADE")
    perm_read = fields.Boolean('Read Access')
    perm_write = fields.Boolean('Write Access')
    perm_create = fields.Boolean('Create Access')
    perm_delete = fields.Boolean('Delete Access')
    description = fields.Text('Description')
    _get_access_cache = Cache('ir_model_access.get_access', context=False)

    @classmethod
    def __setup__(cls):
        super(ModelAccess, cls).__setup__()
        cls.__access__.add('model_ref')
        cls.__rpc__.update({
                'get_access': RPC(),
                })

    @classmethod
    def __register__(cls, module):
        pool = Pool()
        Model = pool.get('ir.model')
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        table_h = cls.__table_handler__(module)
        table = cls.__table__()
        model = Model.__table__()

        # Migration from 7.0: model as char
        if (table_h.column_exist('model')
                and table_h.column_is_type('model', 'INTEGER')):
            table_h.column_rename('model', '_temp_model')
            table_h.add_column('model', 'VARCHAR')
            cursor.execute(*table.update(
                    [table.model], [model.model],
                    from_=[model],
                    where=table._temp_model == model.id))
            table_h.drop_column('_temp_model')

        super().__register__(module)

    @classmethod
    def check_xml_record(cls, accesses, values):
        pass

    @staticmethod
    def default_perm_read():
        return False

    @staticmethod
    def default_perm_write():
        return False

    @staticmethod
    def default_perm_create():
        return False

    @staticmethod
    def default_perm_delete():
        return False

    def get_rec_name(self, name):
        return self.model_ref.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('model_ref.rec_name', *clause[1:])]

    @classmethod
    def get_access(cls, models):
        'Return access for models'
        # root user above constraint
        if Transaction().user == 0:
            return defaultdict(lambda: defaultdict(lambda: True))

        pool = Pool()
        User = pool.get('res.user')
        cursor = Transaction().connection.cursor()
        model_access = cls.__table__()

        groups = User.get_groups()

        access = {}
        for model in models:
            maccess = cls._get_access_cache.get((groups, model), default=-1)
            if maccess == -1:
                break
            access[model] = maccess
        else:
            return access

        def fill_models(Model, models):
            if Model.__name__ in models:
                return
            models.append(Model.__name__)
            for field_name in Model.__access__:
                field = getattr(Model, field_name)
                fill_models(field.get_target(), models)
        model2models = defaultdict(list)
        for model in models:
            fill_models(pool.get(model), model2models[model])

        all_models = list(set(sum(model2models.values(), [])))
        default = {'read': True, 'write': True, 'create': True, 'delete': True}
        default_singleton = {
            'read': True, 'write': True, 'create': False, 'delete': False}
        default_table_query = {
            'read': True, 'write': False, 'create': False, 'delete': False}
        access = {}
        for model in models:
            Model = pool.get(model)
            if callable(getattr(Model, 'table_query', None)):
                maccess = access[model] = default_table_query.copy()
                if Model.create.__func__ != ModelSQL.create.__func__:
                    maccess['create'] = default['create']
                if Model.write.__func__ != ModelSQL.write.__func__:
                    maccess['write'] = default['write']
                if Model.delete.__func__ != ModelSQL.delete.__func__:
                    maccess['delete'] = default['delete']
            elif issubclass(Model, ModelSingleton):
                access[model] = default_singleton
            else:
                access[model] = default
        cursor.execute(*model_access.select(
                model_access.model,
                Max(Case(
                        (model_access.perm_read == Literal(True), 1),
                        else_=0)),
                Max(Case(
                        (model_access.perm_write == Literal(True), 1),
                        else_=0)),
                Max(Case(
                        (model_access.perm_create == Literal(True), 1),
                        else_=0)),
                Max(Case(
                        (model_access.perm_delete == Literal(True), 1),
                        else_=0)),
                where=model_access.model.in_(all_models)
                & (model_access.active == Literal(True))
                & (model_access.group.in_(groups or [-1])
                    | (model_access.group == Null)),
                group_by=model_access.model))
        raw_access = {
            m: {'read': r, 'write': w, 'create': c, 'delete': d}
            for m, r, w, c, d in cursor}

        for model in models:
            access[model] = {
                perm: max(
                    (raw_access[m][perm] for m in model2models[model]
                        if m in raw_access),
                    default=access[model][perm])
                for perm in ['read', 'write', 'create', 'delete']}
        for model, maccess in access.items():
            cls._get_access_cache.set((groups, model), maccess)
        return access

    @classmethod
    def check(cls, model_name, mode='read', raise_exception=True):
        'Check access for model_name and mode'
        pool = Pool()
        Model = pool.get(model_name)
        assert mode in ['read', 'write', 'create', 'delete'], \
            'Invalid access mode for security'
        transaction = Transaction()
        if (transaction.user == 0
                or (raise_exception and not transaction.check_access)):
            return True

        User = pool.get('res.user')
        Group = pool.get('res.group')

        access = cls.get_access([model_name])[model_name][mode]
        if not access and access is not None:
            if raise_exception:
                groups = Group.browse(User.get_groups())
                raise AccessError(
                    gettext('ir.msg_access_rule_error', **Model.__names__()),
                    gettext(
                        'ir.msg_context_groups',
                        groups=', '.join(g.rec_name for g in groups)))
            else:
                return False
        return True

    @classmethod
    def check_relation(cls, model_name, field_name, mode='read'):
        'Check access to relation field for model_name and mode'
        pool = Pool()
        Model = pool.get(model_name)
        field = getattr(Model, field_name)
        if field._type in ('one2many', 'many2one'):
            return cls.check(field.model_name, mode=mode,
                raise_exception=False)
        elif field._type in ('many2many', 'one2one'):
            if not cls.check(
                    field.get_target().__name__, mode=mode,
                    raise_exception=False):
                return False
            elif (field.relation_name
                    and not cls.check(field.relation_name, mode=mode,
                        raise_exception=False)):
                return False
            else:
                return True
        elif field._type == 'reference':
            selection = field.selection
            if isinstance(selection, str):
                sel_func = getattr(Model, field.selection)
                if not is_instance_method(Model, field.selection):
                    selection = sel_func()
                else:
                    # XXX Can not check access right on instance method
                    selection = []
            for model_name, _ in selection:
                if model_name and not cls.check(model_name, mode=mode,
                        raise_exception=False):
                    return False
            return True
        else:
            return True

    @classmethod
    def write(cls, accesses, values, *args):
        super(ModelAccess, cls).write(accesses, values, *args)
        # Restart the cache
        cls._get_access_cache.clear()
        ModelView._fields_view_get_cache.clear()

    @classmethod
    def create(cls, vlist):
        res = super(ModelAccess, cls).create(vlist)
        # Restart the cache
        cls._get_access_cache.clear()
        ModelView._fields_view_get_cache.clear()
        return res

    @classmethod
    def delete(cls, accesses):
        super(ModelAccess, cls).delete(accesses)
        # Restart the cache
        cls._get_access_cache.clear()
        ModelView._fields_view_get_cache.clear()


class ModelFieldAccess(
        fields.fmany2one(
            'model_ref', 'model', 'ir.model,model', "Model",
            required=True, ondelete='CASCADE'),
        fields.fmany2one(
            'field_ref', 'field,model', 'ir.model.field,name,model', "Field",
            required=True, ondelete='CASCADE',
            domain=[
                ('model', '=', Eval('model')),
                ]),
        DeactivableMixin, ModelSQL, ModelView):
    "Model Field Access"
    __name__ = 'ir.model.field.access'
    model = fields.Char("Model", required=True)
    field = fields.Char("Field", required=True)
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE')
    perm_read = fields.Boolean('Read Access')
    perm_write = fields.Boolean('Write Access')
    perm_create = fields.Boolean('Create Access')
    perm_delete = fields.Boolean('Delete Access')
    description = fields.Text('Description')
    _get_access_cache = Cache('ir_model_field_access.check', context=False)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('field_ref')

    @classmethod
    def __register__(cls, module):
        pool = Pool()
        Field = pool.get('ir.model.field')
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        table_h = cls.__table_handler__(module)
        table = cls.__table__()
        field = Field.__table__()

        # Migration from 7.0: field as char
        if (table_h.column_exist('field')
                and table_h.column_is_type('field', 'INTEGER')):
            table_h.column_rename('field', '_temp_field')
            table_h.add_column('model', 'VARCHAR')
            table_h.add_column('field', 'VARCHAR')
            cursor.execute(*table.update(
                    [table.model, table.field],
                    [field.model, field.name],
                    from_=[field],
                    where=table._temp_field == field.id))
            table_h.drop_column('_temp_field')

        super().__register__(module)

    @classmethod
    def check_xml_record(cls, field_accesses, values):
        pass

    @staticmethod
    def default_perm_read():
        return False

    @staticmethod
    def default_perm_write():
        return False

    @staticmethod
    def default_perm_create():
        return True

    @staticmethod
    def default_perm_delete():
        return True

    def get_rec_name(self, name):
        return self.field_ref.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('field_ref.rec_name', *clause[1:])]

    @classmethod
    def get_access(cls, models):
        'Return fields access for models'
        # root user above constraint
        if Transaction().user == 0:
            return defaultdict(lambda: defaultdict(
                    lambda: defaultdict(lambda: True)))

        pool = Pool()
        User = pool.get('res.user')
        field_access = cls.__table__()

        groups = User.get_groups()

        accesses = {}
        for model in models:
            maccesses = cls._get_access_cache.get((groups, model))
            if maccesses is None:
                break
            accesses[model] = maccesses
        else:
            return accesses

        default = {}
        accesses = dict((m, default) for m in models)
        cursor = Transaction().connection.cursor()
        cursor.execute(*field_access.select(
                field_access.model,
                field_access.field,
                Max(Case(
                        (field_access.perm_read == Literal(True), 1),
                        else_=0)),
                Max(Case(
                        (field_access.perm_write == Literal(True), 1),
                        else_=0)),
                Max(Case(
                        (field_access.perm_create == Literal(True), 1),
                        else_=0)),
                Max(Case(
                        (field_access.perm_delete == Literal(True), 1),
                        else_=0)),
                where=field_access.model.in_(models)
                & (field_access.active == Literal(True))
                & (field_access.group.in_(groups or [-1])
                    | (field_access.group == Null)),
                group_by=[field_access.model, field_access.field]))
        for m, f, r, w, c, d in cursor:
            accesses[m][f] = {'read': r, 'write': w, 'create': c, 'delete': d}
        for model, maccesses in accesses.items():
            cls._get_access_cache.set((groups, model), maccesses)
        return accesses

    @classmethod
    def check(cls, model_name, fields, mode='read', raise_exception=True,
            access=False):
        '''
        Check access for fields on model_name.
        '''
        pool = Pool()
        Model = pool.get(model_name)
        assert mode in ('read', 'write', 'create', 'delete'), \
            'Invalid access mode'
        transaction = Transaction()
        if (transaction.user == 0
                or (raise_exception and not transaction.check_access)):
            if access:
                return dict((x, True) for x in fields)
            return True

        User = pool.get('res.user')
        Group = pool.get('res.group')

        accesses = dict((f, a[mode])
            for f, a in cls.get_access([model_name])[model_name].items())
        if access:
            return accesses
        for field in fields:
            if not accesses.get(field, True):
                if raise_exception:
                    groups = Group.browse(User.get_groups())
                    raise AccessError(
                        gettext(
                            'ir.msg_access_rule_field_error',
                            **Model.__names__(field)),
                        gettext(
                            'ir.msg_context_groups',
                            groups=', '.join(g.rec_name for g in groups)))
                else:
                    return False
        return True

    @classmethod
    def write(cls, field_accesses, values, *args):
        super(ModelFieldAccess, cls).write(field_accesses, values, *args)
        # Restart the cache
        cls._get_access_cache.clear()
        ModelView._fields_view_get_cache.clear()

    @classmethod
    def create(cls, vlist):
        res = super(ModelFieldAccess, cls).create(vlist)
        # Restart the cache
        cls._get_access_cache.clear()
        ModelView._fields_view_get_cache.clear()
        return res

    @classmethod
    def delete(cls, field_accesses):
        super(ModelFieldAccess, cls).delete(field_accesses)
        # Restart the cache
        cls._get_access_cache.clear()
        ModelView._fields_view_get_cache.clear()


class ModelButton(
        fields.fmany2one(
            'model_ref', 'model', 'ir.model,model', "Model",
            required=True, readonly=True, ondelete='CASCADE'),
        DeactivableMixin, ModelSQL, ModelView):
    "Model Button"
    __name__ = 'ir.model.button'
    name = fields.Char('Name', required=True, readonly=True)
    string = fields.Char("Label", translate=True)
    help = fields.Text("Help", translate=True)
    confirm = fields.Text("Confirm", translate=True,
        help="Text to ask user confirmation when clicking the button.")
    model = fields.Char("Model", required=True, readonly=True)
    rules = fields.One2Many('ir.model.button.rule', 'button', "Rules")
    _rules_cache = Cache('ir.model.button.rules')
    clicks = fields.One2Many('ir.model.button.click', 'button', "Clicks")
    reset_by = fields.Many2Many(
        'ir.model.button-button.reset', 'button_ruled', 'button', "Reset by",
        domain=[
            ('model', '=', Eval('model')),
            ('id', '!=', Eval('id', -1)),
            ],
        help="Button that should reset the rules.")
    reset = fields.Many2Many(
        'ir.model.button-button.reset', 'button', 'button_ruled', "Reset",
        domain=[
            ('model', '=', Eval('model')),
            ('id', '!=', Eval('id', -1)),
            ])
    _reset_cache = Cache('ir.model.button.reset')
    _view_attributes_cache = Cache(
        'ir.model.button.view_attributes', context=False)

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Model = pool.get('ir.model')
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        table_h = cls.__table_handler__(module_name)
        table = cls.__table__()
        model = Model.__table__()

        # Migration from 7.0: model as char
        if (table_h.column_exist('model')
                and table_h.column_is_type('model', 'INTEGER')):
            table_h.column_rename('model', '_temp_model')
            table_h.add_column('model', 'VARCHAR')
            cursor.execute(*table.update(
                    [table.model], [model.model],
                    from_=[model],
                    where=table._temp_model == model.id))
            table_h.drop_column('_temp_model')

        super().__register__(module_name)

        # Migration from 6.2: replace unique by exclude
        table_h.drop_constraint('name_model_uniq')

    @classmethod
    def __setup__(cls):
        super(ModelButton, cls).__setup__()
        cls.__access__.add('model_ref')
        t = cls.__table__()
        cls._sql_constraints += [
            ('name_model_exclude',
                Exclude(t, (t.name, Equal), (t.model, Equal),
                    where=(t.active == Literal(True))),
                'ir.msg_button_name_unique'),
            ]
        cls._order.insert(0, ('model', 'ASC'))

    @classmethod
    def create(cls, vlist):
        result = super(ModelButton, cls).create(vlist)
        cls._rules_cache.clear()
        cls._reset_cache.clear()
        cls._view_attributes_cache.clear()
        return result

    @classmethod
    def write(cls, buttons, values, *args):
        super(ModelButton, cls).write(buttons, values, *args)
        cls._rules_cache.clear()
        cls._reset_cache.clear()
        cls._view_attributes_cache.clear()

    @classmethod
    def delete(cls, buttons):
        super(ModelButton, cls).delete(buttons)
        cls._rules_cache.clear()
        cls._reset_cache.clear()
        cls._view_attributes_cache.clear()

    @classmethod
    def copy(cls, buttons, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('clicks')
        return super(ModelButton, cls).copy(buttons, default=default)

    @classmethod
    @without_check_access
    def get_rules(cls, model, name):
        'Return a list of rules to apply on the named button of the model'
        pool = Pool()
        Rule = pool.get('ir.model.button.rule')
        key = (model, name)
        rule_ids = cls._rules_cache.get(key)
        if rule_ids is not None:
            return Rule.browse(rule_ids)
        buttons = cls.search([
                ('model', '=', model),
                ('name', '=', name),
                ])
        if not buttons:
            rules = []
        else:
            button, = buttons
            rules = button.rules
        cls._rules_cache.set(key, [r.id for r in rules])
        return rules

    @classmethod
    @without_check_access
    def get_reset(cls, model, name):
        "Return a list of button names to reset"
        key = (model, name)
        reset = cls._reset_cache.get(key)
        if reset is not None:
            return reset
        buttons = cls.search([
                ('model', '=', model),
                ('name', '=', name),
                ])
        if not buttons:
            reset = []
        else:
            button, = buttons
            reset = [b.name for b in button.reset]
        cls._reset_cache.set(key, reset)
        return reset

    @classmethod
    def get_view_attributes(cls, model, name):
        "Return the view attributes of the named button of the model"
        key = (model, name, Transaction().language)
        attributes = cls._view_attributes_cache.get(key)
        if attributes is not None:
            return attributes
        buttons = cls.search([
                ('model', '=', model),
                ('name', '=', name),
                ])
        if not buttons:
            attributes = {}
        else:
            button, = buttons
            attributes = {
                'string': button.string,
                'help': button.help,
                'confirm': button.confirm,
                }
        cls._view_attributes_cache.set(key, attributes)
        return attributes


class ModelButtonRule(ModelSQL, ModelView):
    "Model Button Rule"
    __name__ = 'ir.model.button.rule'
    button = fields.Many2One(
        'ir.model.button', "Button", required=True, ondelete='CASCADE')
    description = fields.Char('Description')
    number_user = fields.Integer('Number of User', required=True)
    condition = fields.Char(
        "Condition",
        help='A PYSON statement evaluated with the record represented by '
        '"self"\nIt activate the rule if true.')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('button')

    @classmethod
    def default_number_user(cls):
        return 1

    @classmethod
    def validate_fields(cls, rules, field_names):
        super().validate_fields(rules, field_names)
        cls.check_condition(rules, field_names)

    @classmethod
    def check_condition(cls, rules, field_names=None):
        if field_names and 'condition' not in field_names:
            return
        for rule in rules:
            if not rule.condition:
                continue
            try:
                PYSONDecoder(noeval=True).decode(rule.condition)
            except Exception:
                raise ConditionError(
                    gettext('ir.msg_model_invalid_condition',
                        condition=rule.condition,
                        rule=rule.rec_name))

    def test(self, record, clicks):
        "Test if the rule passes for the record"
        if self.condition:
            env = {}
            env['self'] = EvalEnvironment(record, record.__class__)
            if not PYSONDecoder(env).decode(self.condition):
                return True
        if self.group:
            users = {c.user for c in clicks if self.group in c.user.groups}
        else:
            users = {c.user for c in clicks}
        return len(users) >= self.number_user

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        ModelButton = pool.get('ir.model.button')
        result = super(ModelButtonRule, cls).create(vlist)
        # Restart the cache for get_rules
        ModelButton._rules_cache.clear()
        return result

    @classmethod
    def write(cls, buttons, values, *args):
        pool = Pool()
        ModelButton = pool.get('ir.model.button')
        super(ModelButtonRule, cls).write(buttons, values, *args)
        # Restart the cache for get_rules
        ModelButton._rules_cache.clear()

    @classmethod
    def delete(cls, buttons):
        pool = Pool()
        ModelButton = pool.get('ir.model.button')
        super(ModelButtonRule, cls).delete(buttons)
        # Restart the cache for get_rules
        ModelButton._rules_cache.clear()


class ModelButtonClick(DeactivableMixin, ModelSQL, ModelView):
    "Model Button Click"
    __name__ = 'ir.model.button.click'
    button = fields.Many2One(
        'ir.model.button', "Button", required=True, ondelete='CASCADE')
    record_id = fields.Integer("Record ID", required=True)

    @classmethod
    def __setup__(cls):
        super(ModelButtonClick, cls).__setup__()
        cls.__access__.add('button')
        cls.__rpc__.update({
                'get_click': RPC(),
                })

    @classmethod
    def register(cls, model, name, records):
        pool = Pool()
        Button = pool.get('ir.model.button')

        assert all(r.__class__.__name__ == model for r in records)

        user = Transaction().user
        button, = Button.search([
                ('model.model', '=', model),
                ('name', '=', name),
                ])
        cls.create([{
                    'button': button.id,
                    'record_id': r.id,
                    'user': user,
                    } for r in records])

        clicks = defaultdict(list)
        for records in grouped_slice(records):
            records = cls.search([
                    ('button', '=', button.id),
                    ('record_id', 'in', [r.id for r in records]),
                    ], order=[('record_id', 'ASC')])
            clicks.update(
                (k, list(v)) for k, v in groupby(
                    records, key=lambda c: c.record_id))
        return clicks

    @classmethod
    @without_check_access
    def reset(cls, model, names, records):
        assert all(r.__class__.__name__ == model for r in records)

        clicks = []
        for records in grouped_slice(records):
            clicks.extend(cls.search([
                        ('button.model.model', '=', model),
                        ('button.name', 'in', names),
                        ('record_id', 'in', [r.id for r in records]),
                        ]))
        cls.write(clicks, {
                'active': False,
                })

    @classmethod
    def get_click(cls, model, button, record_id):
        clicks = cls.search([
                ('button.model.model', '=', model),
                ('button.name', '=', button),
                ('record_id', '=', record_id),
                ])
        return {c.user.id: c.user.rec_name for c in clicks}


class ModelButtonReset(ModelSQL):
    "Model Button Reset"
    __name__ = 'ir.model.button-button.reset'
    button_ruled = fields.Many2One(
        'ir.model.button', "Button Ruled",
        required=True, ondelete='CASCADE')
    button = fields.Many2One(
        'ir.model.button', "Button",
        required=True, ondelete='CASCADE')


class ModelData(
        fields.fmany2one(
            'model_ref', 'model', 'ir.model,model', "Model",
            required=True, ondelete='CASCADE'),
        fields.fmany2one(
            'module_ref', 'module', 'ir.module,name', "Module",
            required=True, ondelete='CASCADE'),
        ModelSQL, ModelView):
    "Model data"
    __name__ = 'ir.model.data'
    fs_id = fields.Char('Identifier on File System', required=True,
        help="The id of the record as known on the file system.")
    model = fields.Char('Model', required=True)
    module = fields.Char('Module', required=True)
    db_id = fields.Integer(
        "Resource ID",
        states={
            'required': ~Eval('noupdate', False),
            },
        help="The id of the record in the database.")
    values = fields.Text('Values')
    fs_values = fields.Text('Values on File System')
    noupdate = fields.Boolean('No Update')
    out_of_sync = fields.Function(fields.Boolean('Out of Sync'),
        'get_out_of_sync', searcher='search_out_of_sync')
    _get_id_cache = Cache('ir_model_data.get_id', context=False)
    _has_model_cache = Cache('ir_model_data.has_model', context=False)

    @classmethod
    def __setup__(cls):
        super(ModelData, cls).__setup__()
        table = cls.__table__()
        cls._sql_constraints = [
            ('fs_id_module_model_uniq',
                Unique(table, table.fs_id, table.module, table.model),
                'The triple (fs_id, module, model) must be unique!'),
            ]
        cls._sql_indexes.update({
                Index(
                    table,
                    (table.fs_id, Index.Equality()),
                    (table.module, Index.Equality()),
                    (table.model, Index.Equality())),
                Index(
                    table,
                    (table.module, Index.Equality())),
                })
        cls._buttons.update({
                'sync': {
                    'invisible': ~Eval('out_of_sync'),
                    'depends': ['out_of_sync'],
                    },
                })
        cls.__rpc__.update({
                'sync': RPC(
                    readonly=False, instantiate=0, fresh_session=True),
                })

    @classmethod
    def __register__(cls, module_name):
        super(ModelData, cls).__register__(module_name)

        table_h = cls.__table_handler__(module_name)

        # Migration from 5.0: remove required on db_id
        table_h.not_null_action('db_id', action='remove')

    @staticmethod
    def default_noupdate():
        return False

    def get_out_of_sync(self, name):
        return self.values != self.fs_values and self.fs_values is not None

    @classmethod
    def search_out_of_sync(cls, name, clause):
        table = cls.__table__()
        name, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]
        query = table.select(table.id,
            where=Operator(
                (table.fs_values != table.values) & (table.fs_values != Null),
                value))
        return [('id', 'in', query)]

    @classmethod
    def create(cls, *args):
        records = super(ModelData, cls).create(*args)
        cls._has_model_cache.clear()
        return records

    @classmethod
    def write(cls, data, values, *args):
        super(ModelData, cls).write(data, values, *args)
        # Restart the cache for get_id
        cls._get_id_cache.clear()
        cls._has_model_cache.clear()

    @classmethod
    def delete(cls, records):
        super(ModelData, cls).delete(records)
        cls._has_model_cache.clear()

    @classmethod
    def has_model(cls, model):
        models = cls._has_model_cache.get(None)
        if models is None:
            table = cls.__table__()
            cursor = Transaction().connection.cursor()

            cursor.execute(*table.select(table.model, group_by=[table.model]))
            models = [m for m, in cursor]
            cls._has_model_cache.set(None, models)
        return model in models

    @classmethod
    @without_check_access
    def can_modify(cls, records, values):
        for Model, records in groupby(
                records, key=lambda r: r.__class__):
            for sub_records in grouped_slice(records):
                id2record = {r.id: r for r in sub_records}
                data = cls.search([
                        ('model', '=', Model.__name__),
                        ('db_id', 'in', list(id2record.keys())),
                        ], order=[])
                for data in data:
                    record = id2record[data.db_id]
                    if values is None:
                        if not data.noupdate:
                            raise AccessError(
                                gettext(
                                    'ir.msg_delete_xml_record',
                                    **Model.__names__(record=record)),
                                gettext('ir.msg_base_config_record'))
                    else:
                        if not data.values or data.noupdate:
                            continue
                        xml_values = cls.load_values(data.values)
                        for key, val in values.items():
                            if key in xml_values and val != xml_values[key]:
                                raise AccessError(
                                    gettext(
                                        'ir.msg_write_xml_record',
                                        **cls.__names__(
                                            field=key, record=record)),
                                    gettext('ir.msg_base_config_record'))

    @classmethod
    @without_check_access
    def clean(cls, records):
        data = []
        for name, records in groupby(
                records, key=lambda r: r.__class__.__name__):
            for sub_records in grouped_slice(records):
                ids = [r.id for r in sub_records]
                data += cls.search([
                        ('model', '=', name),
                        ('db_id', 'in', ids),
                        ('noupdate', '=', True),
                        ], order=[])
        cls.write(data, {'db_id': None})

    @classmethod
    @without_check_access
    def get_id(cls, module, fs_id=None):
        """
        Return for an fs_id the corresponding db_id.
        """
        if fs_id is None:
            module, fs_id = module.split('.', 1)
        key = (module, fs_id)
        id_ = cls._get_id_cache.get(key)
        if id_ is not None:
            return id_
        data = cls.search([
            ('module', '=', module),
            ('fs_id', '=', fs_id),
            ], limit=1)
        if not data:
            raise KeyError("Reference to %s not found"
                % ".".join([module, fs_id]))
        id_ = cls.read([d.id for d in data], ['db_id'])[0]['db_id']
        cls._get_id_cache.set(key, id_)
        return id_

    @classmethod
    def dump_values(cls, values):
        return json.dumps(
            sorted(values.items()), cls=JSONEncoder, separators=(',', ':'),
            sort_keys=True)

    @classmethod
    def load_values(cls, values):
        return dict(json.loads(values, object_hook=JSONDecoder()))

    @classmethod
    @ModelView.button
    def sync(cls, records):
        def settable(Model, fieldname):
            try:
                field = Model._fields[fieldname]
            except KeyError:
                return False

            if isinstance(field, fields.Function) and not field.setter:
                return False

            return True

        with Transaction().set_user(0):
            pool = Pool()
            to_write = []
            models_to_write = defaultdict(list)
            for data in records:
                try:
                    Model = pool.get(data.model)
                except KeyError:
                    continue
                values = cls.load_values(data.values)
                fs_values = cls.load_values(data.fs_values)
                # values could be the same once loaded
                # if they come from version < 3.2
                if values != fs_values:
                    values = {f: v for f, v in fs_values.items()
                        if settable(Model, f)}
                    record = Model(data.db_id)
                    models_to_write[Model].extend(([record], values))
                to_write.extend([[data], {
                            'values': cls.dump_values(fs_values),
                            'fs_values': cls.dump_values(fs_values),
                            }])
            for Model, values_to_write in models_to_write.items():
                Model.write(*values_to_write)
            if to_write:
                cls.write(*to_write)


class Log(ResourceAccessMixin, ModelSQL, ModelView):
    "Log"
    __name__ = 'ir.model.log'

    user = fields.Many2One(
        'res.user', "User",
        states={
            'required': Eval('event') != 'transition',
            })
    event = fields.Selection([
            ('write', "Modified"),
            ('delete', "Deleted"),
            ('button', "Clicked on"),
            ('wizard', "Launched"),
            ('transition', "Transitioned to"),
            ], "Event", required=True)
    event_string = event.translated('event')
    target = fields.Char(
        "Target",
        states={
            'required': Eval('event').in_(
                ['write', 'button', 'wizard', 'transition']),
            'invisible': (
                ~Eval('event').in_(
                    ['write', 'button', 'wizard', 'transition'])),
            })
    action = fields.Function(
        fields.Char("Action"), 'get_action', searcher='search_action')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.resource.required = False  # store deleted record
        cls._order = [
            ('create_date', 'DESC'),
            ('id', 'DESC'),
            ]

    @classmethod
    def get_models(cls):
        return super().get_models() + [(None, '')]  # store deleted record

    def get_action(self, name):
        pool = Pool()
        Field = pool.get('ir.model.field')
        Button = pool.get('ir.model.button')
        Wizard = pool.get('ir.action.wizard')
        if self.resource:
            Model = self.resource.__class__
            model = self.resource.__name__
            if self.event == 'write':
                fields = self.target.split(',')
                get_name = Field.get_name
                fields = [get_name(model, f) for f in fields]
                return ', '.join(fields)
            elif self.event == 'button':
                return Button.get_view_attributes(model, self.target).get(
                    'string', self.target)
            elif self.event == 'wizard':
                wiz_name, state_name = self.target.split(':')
                wiz_name = Wizard.get_name(wiz_name, model)
                return f'{state_name} @ {wiz_name}'
            elif self.event == 'transition':
                field_name, state = self.target.split(':')
                field = getattr(Model, field_name, None)
                field_name = Field.get_name(model, field_name)
                if field:
                    selection = field.get_selection(
                        Model, field.name, self.resource)
                    state = field.get_selection_string(selection, state)
                return f'{field_name} : {state}'
        return self.target

    @classmethod
    def search_action(cls, name, clause):
        return [('target', *clause[1:])]


class PrintModelGraphStart(ModelView):
    'Print Model Graph'
    __name__ = 'ir.model.print_model_graph.start'
    level = fields.Integer('Level', required=True)
    filter = fields.Text('Filter', help="Entering a Python "
            "Regular Expression will exclude matching models from the graph.")

    @staticmethod
    def default_level():
        return 1


class PrintModelGraph(Wizard):
    __name__ = 'ir.model.print_model_graph'

    start = StateView('ir.model.print_model_graph.start',
        'ir.print_model_graph_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-ok', default=True),
            ])
    print_ = StateAction('ir.report_model_graph')

    def transition_print_(self):
        return 'end'

    def do_print_(self, action):
        return action, {
            'id': Transaction().context.get('active_id'),
            'ids': Transaction().context.get('active_ids'),
            'level': self.start.level,
            'filter': self.start.filter,
            }


class ModelGraph(Report):
    __name__ = 'ir.model.graph'

    @classmethod
    def execute(cls, ids, data):
        import pydot
        pool = Pool()
        Model = pool.get('ir.model')
        ActionReport = pool.get('ir.action.report')

        if not data['filter']:
            filter = None
        else:
            filter = re.compile(data['filter'], re.VERBOSE)
        action_report_ids = ActionReport.search([
            ('report_name', '=', cls.__name__)
            ])
        if not action_report_ids:
            raise Exception('Error', 'Report (%s) not find!' % cls.__name__)
        action_report = ActionReport(action_report_ids[0])

        models = Model.browse(ids)

        graph = pydot.Dot(fontsize="8")
        graph.set('center', '1')
        graph.set('ratio', 'auto')
        cls.fill_graph(models, graph, level=data['level'], filter=filter)
        data = graph.create(prog='dot', format='png')
        return ('png', fields.Binary.cast(data), False, action_report.name)

    @classmethod
    def fill_graph(cls, models, graph, level=1, filter=None):
        '''
        Fills a pydot graph with a models structure.
        '''
        import pydot
        pool = Pool()
        Model = pool.get('ir.model')

        sub_models = set()
        if level > 0:
            for model in models:
                for field in model.fields:
                    if field.name in ('create_uid', 'write_uid'):
                        continue
                    if field.relation and not graph.get_node(field.relation):
                        sub_models.add(field.relation)
            if sub_models:
                model_ids = Model.search([
                    ('model', 'in', list(sub_models)),
                    ])
                sub_models = Model.browse(model_ids)
                if set(sub_models) != set(models):
                    cls.fill_graph(sub_models, graph, level=level - 1,
                            filter=filter)

        for model in models:
            if filter and re.search(filter, model.model):
                continue
            label = '"{' + model.model + '\\n'
            if model.fields:
                label += '|'
            for field in model.fields:
                if field.name in ('create_uid', 'write_uid',
                        'create_date', 'write_date', 'id'):
                    continue
                label += '+ ' + field.name + ': ' + field.ttype
                if field.relation:
                    label += ' ' + field.relation
                label += '\\l'
            label += '}"'
            node_name = '"%s"' % model.model
            node = pydot.Node(node_name, shape='record', label=label)
            graph.add_node(node)

            for field in model.fields:
                if field.name in ('create_uid', 'write_uid'):
                    continue
                if field.relation:
                    node_name = '"%s"' % field.relation
                    if not graph.get_node(node_name):
                        continue
                    args = {}
                    tail = model.model
                    head = field.relation
                    edge_model_name = '"%s"' % model.model
                    edge_relation_name = '"%s"' % field.relation
                    if field.ttype == 'many2one':
                        edge = graph.get_edge(edge_model_name,
                                edge_relation_name)
                        if edge:
                            continue
                        args['arrowhead'] = "normal"
                    elif field.ttype == 'one2many':
                        edge = graph.get_edge(edge_relation_name,
                                edge_model_name)
                        if edge:
                            continue
                        args['arrowhead'] = "normal"
                        tail = field.relation
                        head = model.model
                    elif field.ttype == 'many2many':
                        if graph.get_edge(edge_model_name, edge_relation_name):
                            continue
                        if graph.get_edge(edge_relation_name, edge_model_name):
                            continue
                        args['arrowtail'] = "inv"
                        args['arrowhead'] = "inv"

                    edge = pydot.Edge(str(tail), str(head), **args)
                    graph.add_edge(edge)


class ModelWorkflowGraph(Report):
    __name__ = 'ir.model.workflow_graph'

    @classmethod
    def execute(cls, ids, data):
        import pydot
        pool = Pool()
        Model = pool.get('ir.model')
        ActionReport = pool.get('ir.action.report')

        action_report_ids = ActionReport.search([
            ('report_name', '=', cls.__name__)
            ])
        if not action_report_ids:
            raise Exception('Error', 'Report (%s) not find!' % cls.__name__)
        action_report = ActionReport(action_report_ids[0])

        models = Model.browse(ids)

        graph = pydot.Dot()
        graph.set('center', '1')
        graph.set('ratio', 'auto')
        direction = Transaction().context.get('language_direction', 'ltr')
        graph.set('rankdir', {'ltr': 'LR', 'rtl': 'RL'}[direction])
        cls.fill_graph(models, graph)
        data = graph.create(prog='dot', format='png')
        return ('png', fields.Binary.cast(data), False, action_report.name)

    @classmethod
    def fill_graph(cls, models, graph):
        'Fills pydot graph with models wizard.'
        import pydot
        pool = Pool()

        for record in models:
            Model = pool.get(record.model)

            if not issubclass(Model, Workflow):
                continue

            subgraph = pydot.Cluster('%s' % record.id, label=record.model)
            graph.add_subgraph(subgraph)

            state_field = getattr(Model, Model._transition_state)
            for state, _ in state_field.selection:
                node = pydot.Node(
                    f'"{record.model}--{state}"', shape='octagon', label=state)
                subgraph.add_node(node)

            for from_, to in Model._transitions:
                edge = pydot.Edge(
                        f'"{record.model}--{from_}"',
                        f'"{record.model}--{to}"',
                        arrowhead='normal')
                subgraph.add_edge(edge)
