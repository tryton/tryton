# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import warnings
from functools import wraps

import sql
from sql import (operators, Column, Literal, Select, CombiningQuery, Null,
    Query, Expression, Cast)
from sql.aggregate import Min
from sql.conditionals import Coalesce, NullIf
from sql.operators import Concat

from trytond import backend
from trytond.cache import LRUDictTransaction
from trytond.const import OPERATORS
from trytond.pool import Pool
from trytond.pyson import PYSON, PYSONEncoder, PYSONDecoder, Eval
from trytond.rpc import RPC
from trytond.tools.string_ import StringPartitioned, LazyString
from trytond.transaction import Transaction

_sql_version = tuple(map(int, sql.__version__.split('.')))


def domain_validate(value):
    assert isinstance(value, list), 'domain must be a list'

    def test_domain(dom):
        for arg in dom:
            if isinstance(arg, str):
                if arg not in ('AND', 'OR'):
                    return False
            elif (isinstance(arg, tuple)
                or (isinstance(arg, list)
                    and len(arg) > 2
                    and ((
                                isinstance(arg[1], str)
                                and arg[1] in OPERATORS)
                        or (
                                isinstance(arg[1], PYSON)
                                and arg[1].types() == set([str]))))):
                pass
            elif isinstance(arg, list):
                if not test_domain(arg):
                    return False
        return True
    assert test_domain(value), 'invalid domain'


def states_validate(value):
    assert isinstance(value, dict), 'states must be a dict'
    assert set(value).issubset({'required', 'readonly', 'invisible'}), (
        'extra keys "%(keys)s" in states' % {
            'keys': set(value) - {'required', 'readonly', 'invisible'},
            })
    for state in value:
        assert isinstance(value[state], (bool, PYSON)), \
            'values of states must be PYSON'
        if hasattr(value[state], 'types'):
            assert value[state].types() == set([bool]), \
                'values of states must return boolean'


def depends_validate(value):
    assert isinstance(value, list), 'depends must be a list'


def context_validate(value):
    assert isinstance(value, dict), 'context must be a dict'


def size_validate(value):
    if value is not None:
        assert isinstance(value, (int, PYSON)), 'size must be PYSON'
        if hasattr(value, 'types'):
            assert value.types() == set([int]), \
                'size must return integer'


def search_order_validate(value):
    if value is not None:
        assert isinstance(value, (list, PYSON)), 'search_order must be PYSON'
        if hasattr(value, 'types'):
            assert value.types() == set([list]), 'search_order must be PYSON'


def _set_value(record, field):
    try:
        field, nested = field.split('.', 1)
    except ValueError:
        nested = None
    if field.startswith('_parent_'):
        field = field[8:]  # Strip '_parent_'
    if not hasattr(record, field):
        default = None
        if hasattr(record, '_defaults') and field in record._defaults:
            default = record._defaults[field]()
        setattr(record, field, default)
    elif nested:
        parent = getattr(record, field)
        if parent:
            _set_value(parent, nested)


def depends(*fields, **kwargs):
    methods = kwargs.pop('methods', None)
    assert not kwargs

    def decorator(func):
        depends = getattr(func, 'depends', set())
        depends |= set(fields)
        setattr(func, 'depends', depends)

        if methods:
            depend_methods = getattr(func, 'depend_methods', set())
            depend_methods |= set(methods)
            setattr(func, 'depend_methods', depend_methods)

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            for field in fields:
                _set_value(self, field)
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


def get_eval_fields(value):
    "Return fields evaluated"
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

    encoder = Encoder()
    encoder.encode(value)
    return encoder.fields


def instanciate_values(Target, value, **extra):
    from ..modelstorage import ModelStorage, cache_size
    kwargs = {}
    ids = []
    if issubclass(Target, ModelStorage):
        kwargs['_local_cache'] = LRUDictTransaction(
            cache_size(), Target._record)
        kwargs['_ids'] = ids

    def instance(data):
        if isinstance(data, Target):
            for k, v in extra.items():
                setattr(data, k, v)
            return data
        elif isinstance(data, dict):
            if data.get('id', -1) >= 0:
                values = {}
                values.update(data)
                values.update(kwargs)
                ids.append(data['id'])
            else:
                values = data
            values.update(extra)
            return Target(**values)
        else:
            ids.append(data)
            return Target(data, **extra, **kwargs)
    return tuple(instance(x) for x in (value or []))


def instantiate_context(field, record):
    from ..modelstorage import EvalEnvironment
    ctx = {}
    if field.context:
        pyson_context = PYSONEncoder().encode(field.context)
        ctx.update(PYSONDecoder(
                EvalEnvironment(record, record.__class__)).decode(
                pyson_context))
    datetime_ = None
    if getattr(field, 'datetime_field', None):
        datetime_ = getattr(record, field.datetime_field, None)
        ctx = {'_datetime': datetime_}
    return ctx


def on_change_result(record):
    return record._changed_values


def with_inactive_records(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with Transaction().set_context(active_test=False):
            return func(*args, **kwargs)
    return wrapper


SQL_OPERATORS = {
    '=': operators.Equal,
    '!=': operators.NotEqual,
    'like': operators.Like,
    'not like': operators.NotLike,
    'ilike': operators.ILike,
    'not ilike': operators.NotILike,
    'in': operators.In,
    'not in': operators.NotIn,
    '<=': operators.LessEqual,
    '>=': operators.GreaterEqual,
    '<': operators.Less,
    '>': operators.Greater,
    }


class Field(object):
    _type = None
    _sql_type = None
    _py_type = None

    def __init__(self, string='', help='', required=False, readonly=False,
            domain=None, states=None, select=False, on_change=None,
            on_change_with=None, depends=None, context=None,
            loading='eager'):
        '''
        :param string: A string for label of the field.
        :param help: A multi-line help string.
        :param required: A boolean if ``True`` the field is required.
        :param readonly: A boolean if ``True`` the field is not editable in
            the user interface.
        :param domain: A list that defines a domain constraint.
        :param states: A dictionary. Possible keys are ``required``,
            ``readonly`` and ``invisible``. Values are pyson expressions that
            will be evaluated with record values. This allows to change
            dynamically the attributes of the field.
        :param select: An boolean. When True search will be optimized.
        :param on_change: A list of values. If set, the client will call the
            method ``on_change_<field_name>`` when the user changes the field
            value. It then passes this list of values as arguments to the
            function.
        :param on_change_with: A list of values. Like ``on_change``, but
            defined the other way around. The list contains all the fields that
            must update the current field.
        :param depends: A list of field name on which this one depends.
        :param context: A dictionary which will be given to open the relation
            fields.
        :param loading: Define how the field must be loaded:
            ``lazy`` or ``eager``.
        '''
        if not isinstance(string, LazyString):
            assert string, 'a string is required'
        self.string = string
        self.help = help
        self.required = required
        self.readonly = readonly
        self.__domain = None
        self.domain = domain or []
        self.__states = None
        self.states = states or {}
        self.select = bool(select)
        self.on_change = set()
        if on_change:
            warnings.warn('on_change argument is deprecated, '
                'use the depends decorator',
                DeprecationWarning, stacklevel=3)
            self.on_change |= set(on_change)
        self.on_change_with = set()
        if on_change_with:
            warnings.warn('on_change_with argument is deprecated, '
                'use the depends decorator',
                DeprecationWarning, stacklevel=3)
            self.on_change_with |= set(on_change_with)
        self.__depends = None
        self.depends = depends or []
        self.__context = None
        self.context = context or {}
        assert loading in ('lazy', 'eager'), \
            'loading must be "lazy" or "eager"'
        self.loading = loading
        self.name = None

    @property
    def string(self):
        return self.__string

    @string.setter
    def string(self, value):
        self.__string = StringPartitioned(value)

    @property
    def help(self):
        return self.__help

    @help.setter
    def help(self, value):
        self.__help = StringPartitioned(value)

    def _get_domain(self):
        return self.__domain

    def _set_domain(self, value):
        domain_validate(value)
        self.__domain = value

    domain = property(_get_domain, _set_domain)

    def _get_states(self):
        return self.__states

    def _set_states(self, value):
        states_validate(value)
        self.__states = value

    states = property(_get_states, _set_states)

    def _get_depends(self):
        return self.__depends

    def _set_depends(self, value):
        depends_validate(value)
        self.__depends = value

    depends = property(_get_depends, _set_depends)

    def _get_context(self):
        return self.__context

    def _set_context(self, value):
        context_validate(value)
        self.__context = value

    context = property(_get_context, _set_context)

    def __get__(self, inst, cls):
        if inst is None:
            return self
        assert self.name is not None
        if self.name == 'id':
            return inst._id
        return inst.__getattr__(self.name)

    def __set__(self, inst, value):
        assert self.name is not None
        if inst._values is None:
            inst._values = inst._record()
        inst._values[self.name] = value

    def sql_format(self, value):
        if isinstance(value, (Query, Expression)):
            return value

        assert self._sql_type is not None
        database = Transaction().database
        if (self._py_type and value is not None
                and not isinstance(value, self._py_type)):
            value = self._py_type(value)
        return database.sql_format(self._sql_type, value)

    def sql_type(self):
        database = Transaction().database
        return database.sql_type(self._sql_type)

    def sql_cast(self, expression):
        return Cast(expression, self.sql_type().base)

    def sql_column(self, table):
        return Column(table, self.name)

    def _domain_column(self, operator, column):
        return column

    def _domain_value(self, operator, value):
        if isinstance(value, (Select, CombiningQuery)):
            return value
        if operator in ('in', 'not in'):
            return [self.sql_format(v) for v in value if v is not None]
        else:
            return self.sql_format(value)

    def _domain_add_null(self, column, operator, value, expression):
        if operator in ('in', 'not in'):
            if (not isinstance(value, (Select, CombiningQuery))
                    and any(v is None for v in value)):
                if operator == 'in':
                    expression |= (column == Null)
                else:
                    expression &= (column != Null)
        return expression

    def convert_domain(self, domain, tables, Model):
        "Return a SQL expression for the domain using tables"
        table, _ = tables[None]
        name, operator, value = domain
        assert name == self.name
        method = getattr(Model, 'domain_%s' % name, None)
        if method:
            return method(domain, tables)
        Operator = SQL_OPERATORS[operator]
        column = self.sql_column(table)
        column = self._domain_column(operator, column)
        expression = Operator(column, self._domain_value(operator, value))
        if isinstance(expression, operators.In) and not expression.right:
            expression = Literal(False)
        elif isinstance(expression, operators.NotIn) and not expression.right:
            expression = Literal(True)
        expression = self._domain_add_null(column, operator, value, expression)
        return expression

    def convert_order(self, name, tables, Model):
        "Return a SQL expression to order"
        assert name == self.name
        table, _ = tables[None]
        method = getattr(Model, 'order_%s' % name, None)
        if method:
            return method(tables)
        else:
            return [self.sql_column(table)]

    def set_rpc(self, model):
        for attribute, result in (
                ('on_change', on_change_result),
                ('on_change_with', None),
                ):
            if not getattr(self, attribute):
                continue
            func_name = '%s_%s' % (attribute, self.name)
            assert hasattr(model, func_name), \
                'Missing %s on model %s' % (func_name, model.__name__)
            model.__rpc__.setdefault(
                func_name, RPC(instantiate=0, result=result))

    def definition(self, model, language):
        pool = Pool()
        Translation = pool.get('ir.translation')
        encoder = PYSONEncoder()
        definition = {
            'context': encoder.encode(self.context),
            'loading': self.loading,
            'name': self.name,
            'on_change': list(self.on_change),
            'on_change_with': list(self.on_change_with),
            'readonly': self.readonly,
            'required': self.required,
            'states': encoder.encode(self.states),
            'type': self._type,
            'domain': encoder.encode(self.domain),
            'searchable': hasattr(model, 'search'),
            'sortable': hasattr(model, 'search'),
            }

        # Add id to on_change's if they are not cached
        # Not having the id increase the efficiency of the cache
        for method in ['on_change', 'on_change_with']:
            changes = definition[method]
            if changes:
                method_name = method + '_' + self.name
                if not model.__rpc__[method_name].cache:
                    changes.append('id')

                for name in changes:
                    field = model._fields.get(name)
                    if field and field.context:
                        eval_fields = get_eval_fields(field.context)
                        for context_field_name in eval_fields:
                            if (context_field_name in field.depends
                                    and context_field_name not in changes):
                                changes.append(context_field_name)

        name = '%s,%s' % (model.__name__, self.name)
        for attr, ttype in [('string', 'field'), ('help', 'help')]:
            definition[attr] = ''
            for source in getattr(self, attr):
                if not isinstance(source, LazyString):
                    source = (
                        Translation.get_source(name, ttype, language, source)
                        or source)
                definition[attr] += source
        return definition

    def definition_translations(self, model, language):
        "Returns sources used for definition"
        name = '%s,%s' % (model.__name__, self.name)
        translations = []
        for attr, ttype in [('string', 'field'), ('help', 'help')]:
            for source in getattr(self, attr):
                if not isinstance(source, LazyString):
                    translations.append((name, ttype, language, source))
        return translations


class FieldTranslate(Field):

    def _get_translation_join(self, Model, name,
            translation, model, table, from_, language):
        if Model.__name__ == 'ir.model':
            name_ = Concat(Concat(table.model, ','), name)
            type_ = 'model'
            res_id = -1
        elif Model.__name__ == 'ir.model.field':
            name_ = Concat(Concat(model.model, ','), table.name)
            if name == 'field_description':
                type_ = 'field'
            else:
                type_ = 'help'
            res_id = -1
        else:
            name_ = '%s,%s' % (Model.__name__, name)
            type_ = 'model'
            res_id = table.id
        if backend.name == 'postgresql' and _sql_version >= (1, 1, 0):
            query = translation.select(
                translation.res_id.as_('res_id'),
                translation.value.as_('value'),
                distinct=True,
                distinct_on=[translation.res_id],
                order_by=[translation.res_id, translation.id.desc])
        else:
            query = translation.select(
                translation.res_id.as_('res_id'),
                Min(translation.value).as_('value'),
                group_by=[translation.res_id])
        query.where = (
            (translation.lang == language)
            & (translation.type == type_)
            & (translation.name == name_)
            & (translation.fuzzy == Literal(False))
            )
        return query, from_.join(query, 'LEFT',
            condition=(query.res_id == res_id))

    def convert_domain(self, domain, tables, Model):
        from trytond.ir.lang import get_parent_language
        pool = Pool()
        Translation = pool.get('ir.translation')
        IrModel = pool.get('ir.model')
        if not self.translate:
            return super(FieldTranslate, self).convert_domain(
                domain, tables, Model)

        table = join = Model.__table__()
        model = IrModel.__table__()
        name, operator, value = domain
        language = Transaction().language
        column = None
        while language:
            translation = Translation.__table__()
            translation, join = self._get_translation_join(
                Model, name, translation, model, table, join, language)
            column = Coalesce(NullIf(column, ''), translation.value)
            language = get_parent_language(language)
        column = Coalesce(NullIf(column, ''), self.sql_column(table))
        column = self._domain_column(operator, column)
        Operator = SQL_OPERATORS[operator]
        assert name == self.name
        where = Operator(column, self._domain_value(operator, value))
        if isinstance(where, operators.In) and not where.right:
            where = Literal(False)
        elif isinstance(where, operators.NotIn) and not where.right:
            where = Literal(True)
        where = self._domain_add_null(column, operator, value, where)
        return tables[None][0].id.in_(join.select(table.id, where=where))

    def convert_order(self, name, tables, Model):
        from trytond.ir.lang import get_parent_language
        pool = Pool()
        Translation = pool.get('ir.translation')
        IrModel = pool.get('ir.model')
        if not self.translate:
            return super(FieldTranslate, self).convert_order(name, tables,
                Model)
        assert name == self.name

        table, _ = tables[None]

        join = table
        language = Transaction().language
        column = None
        while language:
            key = name + '.translation-' + language
            if key not in tables:
                translation = Translation.__table__()
                model = IrModel.__table__()
                translation, join = self._get_translation_join(
                    Model, name, translation, model, table, table, language)
                if join.left == table:
                    tables[key] = {
                        None: (join.right, join.condition),
                        }
                else:
                    tables[key] = {
                        None: (join.left.right, join.left.condition),
                        'translation': {
                            None: (join.right, join.condition),
                            },
                        }
            else:
                if 'translation' not in tables[key]:
                    translation, _ = tables[key][None]
                else:
                    translation, _ = tables[key]['translation'][None]
            column = Coalesce(NullIf(column, ''), translation.value)
            language = get_parent_language(language)

        return [Coalesce(NullIf(column, ''), self.sql_column(table))]

    def definition(self, model, language):
        definition = super().definition(model, language)
        definition['translate'] = self.translate
        return definition
