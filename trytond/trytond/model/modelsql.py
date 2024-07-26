# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from collections import OrderedDict, defaultdict
from functools import wraps
from itertools import chain, groupby, islice, product, repeat

from sql import (
    Asc, Column, Desc, Expression, For, Literal, Null, NullsFirst, NullsLast,
    Table, Union, Window, With)
from sql.aggregate import Count, Max
from sql.conditionals import Coalesce
from sql.functions import CurrentTimestamp, Extract, RowNumber, Substring
from sql.operators import And, Concat, Equal, Exists, Operator, Or

from trytond import backend
from trytond.cache import freeze
from trytond.config import config
from trytond.exceptions import ConcurrencyException
from trytond.i18n import gettext
from trytond.pool import Pool
from trytond.pyson import PYSONDecoder, PYSONEncoder
from trytond.rpc import RPC
from trytond.tools import cursor_dict, grouped_slice, reduce_ids
from trytond.transaction import (
    Transaction, inactive_records, record_cache_size, without_check_access)

from . import fields
from .descriptors import dualmethod
from .modelstorage import (
    AccessError, ModelStorage, RequiredValidationError, SizeValidationError,
    ValidationError, is_leaf)
from .modelview import ModelView


class ForeignKeyError(ValidationError):
    pass


class SQLConstraintError(ValidationError):
    pass


class Constraint(object):
    __slots__ = ('_table',)

    def __init__(self, table):
        assert isinstance(table, Table)
        self._table = table

    @property
    def table(self):
        return self._table

    def __str__(self):
        raise NotImplementedError

    @property
    def params(self):
        raise NotImplementedError


class Check(Constraint):
    __slots__ = ('_expression',)

    def __init__(self, table, expression):
        super(Check, self).__init__(table)
        assert isinstance(expression, Expression)
        self._expression = expression

    @property
    def expression(self):
        return self._expression

    def __str__(self):
        return 'CHECK(%s)' % self.expression

    @property
    def params(self):
        return self.expression.params


class Unique(Constraint):
    __slots__ = ('_columns',)

    def __init__(self, table, *columns):
        super(Unique, self).__init__(table)
        assert all(isinstance(col, Column) for col in columns)
        self._columns = tuple(columns)

    @property
    def columns(self):
        return self._columns

    @property
    def operators(self):
        return tuple(Equal for c in self._columns)

    def __str__(self):
        return 'UNIQUE(%s)' % (', '.join(map(str, self.columns)))

    @property
    def params(self):
        p = []
        for column in self.columns:
            p.extend(column.params)
        return tuple(p)


class Exclude(Constraint):
    __slots__ = ('_excludes', '_where')

    def __init__(self, table, *excludes, **kwargs):
        super(Exclude, self).__init__(table)
        assert all(isinstance(c, Expression) and issubclass(o, Operator)
            for c, o in excludes), excludes
        self._excludes = tuple(excludes)
        where = kwargs.get('where')
        if where is not None:
            assert isinstance(where, Expression)
        self._where = where

    @property
    def excludes(self):
        return self._excludes

    @property
    def columns(self):
        return tuple(c for c, _ in self._excludes)

    @property
    def operators(self):
        return tuple(o for _, o in self._excludes)

    @property
    def where(self):
        return self._where

    def __str__(self):
        exclude = ', '.join('%s WITH %s' % (column, operator._operator)
            for column, operator in self.excludes)
        where = ''
        if self.where:
            where = ' WHERE ' + str(self.where)
        return 'EXCLUDE (%s)' % exclude + where

    @property
    def params(self):
        p = []
        for column, operator in self._excludes:
            p.extend(column.params)
        if self.where:
            p.extend(self.where.params)
        return tuple(p)


class Index:
    __slots__ = ('table', 'expressions', 'options')

    def __init__(self, table, *expressions, **options):
        self.table = table
        assert all(
            isinstance(e, Expression) and isinstance(u, self.Usage)
            for e, u in expressions)
        self.expressions = expressions
        self.options = options

    def __hash__(self):
        table_def = (
            self.table._name, self.table._schema, self.table._database)
        expressions = (
            (str(e), e.params, hash(u)) for e, u in self.expressions)
        return hash((table_def, *expressions))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplementedError
        return (
            str(self.table) == str(other.table)
            and len(self.expressions) == len(other.expressions)
            and all((str(c), u) == (str(oc), ou)
                for (c, u), (oc, ou) in zip(
                    self.expressions, other.expressions))
            and self._options_cmp == other._options_cmp)

    @property
    def _options_cmp(self):
        def _format(value):
            return str(value) if isinstance(value, Expression) else value
        return {k: _format(v) for k, v in self.options.items()}

    def __lt__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplementedError
        if (self.table != other.table
                or self._options_cmp != other._options_cmp):
            return False
        if self == other:
            return False
        if len(self.expressions) >= len(other.expressions):
            return False
        for (c, u), (oc, ou) in zip(self.expressions, other.expressions):
            if (str(c), u) != (str(oc), ou):
                return False
        return True

    def __le__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplementedError
        return self < other or self == other

    class Unaccent(Expression):
        "Unaccent function if database support for index"
        __slots__ = ('_expression',)

        def __init__(self, expression):
            self._expression = expression

        @property
        def expression(self):
            expression = self._expression
            database = Transaction().database
            if database.has_unaccent_indexable():
                expression = database.unaccent(expression)
            return expression

        def __str__(self):
            return str(self.expression)

        @property
        def params(self):
            return self.expression.params

    class Usage:
        __slots__ = ('options',)

        def __init__(self, **options):
            self.options = options

        def __hash__(self):
            return hash((self.__class__.__name__, *self.options.items()))

        def __eq__(self, other):
            return (self.__class__ == other.__class__
                and self.options == other.options)

    class Equality(Usage):
        __slots__ = ()

    class Range(Usage):
        __slots__ = ()

    class Similarity(Usage):
        __slots__ = ()


def no_table_query(func):
    @wraps(func)
    def wrapper(cls, *args, **kwargs):
        if callable(cls.table_query):
            raise NotImplementedError("On table_query")
        return func(cls, *args, **kwargs)
    return wrapper


class ModelSQL(ModelStorage):
    """
    Define a model with storage in database.
    """
    __slots__ = ()
    _table = None  # The name of the table in database
    _order = None
    _order_name = None  # Use to force order field when sorting on Many2One
    _history = False
    table_query = None

    @classmethod
    def __setup__(cls):
        cls._table = config.get('table', cls.__name__, default=cls._table)
        if not cls._table:
            cls._table = cls.__name__.replace('.', '_')

        assert cls._table[-9:] != '__history', \
            'Model _table %s cannot end with "__history"' % cls._table

        super(ModelSQL, cls).__setup__()

        cls._sql_constraints = []
        cls._sql_indexes = set()
        cls._history_sql_indexes = set()
        if not callable(cls.table_query):
            table = cls.__table__()
            cls._sql_constraints.append(
                ('id_positive', Check(table, table.id >= 0),
                    'ir.msg_id_positive'))
            rec_name_field = getattr(cls, cls._rec_name, None)
            if (isinstance(rec_name_field, fields.Field)
                    and not hasattr(rec_name_field, 'set')):
                column = Column(table, cls._rec_name)
                if getattr(rec_name_field, 'search_unaccented', False):
                    column = Index.Unaccent(column)
                cls._sql_indexes.add(
                    Index(table, (column, Index.Similarity())))
        cls._order = [('id', None)]
        if issubclass(cls, ModelView):
            cls.__rpc__.update({
                    'history_revisions': RPC(),
                    })
        if cls._history:
            history_table = cls.__table_history__()
            cls._history_sql_indexes.update({
                    Index(
                        history_table,
                        (history_table.id, Index.Equality())),
                    Index(
                        history_table,
                        (Coalesce(
                                history_table.write_date,
                                history_table.create_date).desc,
                            Index.Range()),
                        include=[
                            Column(history_table, '__id'),
                            history_table.id]),
                    })

    @classmethod
    def __post_setup__(cls):
        super().__post_setup__()

        # Define Range index to optimise with reduce_ids
        for field in cls._fields.values():
            field_names = set()
            if isinstance(field, fields.One2Many):
                Target = field.get_target()
                if field.field:
                    field_names.add(field.field)
            elif isinstance(field, fields.Many2Many):
                Target = field.get_relation()
                if field.origin:
                    field_names.add(field.origin)
                if field.target:
                    field_names.add(field.target)
            else:
                continue
            field_names.discard('id')
            for field_name in field_names:
                target_field = getattr(Target, field_name)
                if (issubclass(Target, ModelSQL)
                        and not callable(Target.table_query)
                        and not hasattr(target_field, 'set')):
                    target = Target.__table__()
                    column = Column(target, field_name)
                    if not target_field.required and Target != cls:
                        where = column != Null
                    else:
                        where = None
                    if target_field._type == 'reference':
                        Target._sql_indexes.update({
                                Index(
                                    target,
                                    (column, Index.Equality()),
                                    where=where),
                                Index(
                                    target,
                                    (column, Index.Similarity(begin=True)),
                                    (target_field.sql_id(column, Target),
                                        Index.Range()),
                                    where=where),
                                })
                    else:
                        Target._sql_indexes.add(
                            Index(
                                target,
                                (column, Index.Range()),
                                where=where))

    @classmethod
    def __table__(cls):
        if callable(cls.table_query):
            return cls.table_query()
        else:
            return Table(cls._table)

    @classmethod
    def __table_history__(cls):
        if not cls._history:
            raise ValueError('No history table')
        return Table(cls._table + '__history')

    @classmethod
    def __table_handler__(cls, module_name=None, history=False):
        return backend.TableHandler(cls, history=history)

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        super(ModelSQL, cls).__register__(module_name)

        if callable(cls.table_query):
            return

        pool = Pool()
        # Initiate after the callable test to prevent calling table_query which
        # may rely on other model being registered
        sql_table = cls.__table__()

        # create/update table in the database
        table = cls.__table_handler__(module_name)
        if cls._history:
            history_table = cls.__table_handler__(module_name, history=True)

        for field_name, field in cls._fields.items():
            if field_name == 'id':
                continue
            sql_type = field.sql_type()
            if not sql_type:
                continue

            if field_name in cls._defaults:
                def default():
                    default_ = cls._clean_defaults({
                            field_name: cls._defaults[field_name](),
                            })[field_name]
                    return field.sql_format(default_)
            else:
                default = None

            table.add_column(field_name, field._sql_type, default=default)
            if cls._history:
                history_table.add_column(field_name, field._sql_type)

            if isinstance(field, (fields.Integer, fields.Float)):
                # migration from tryton 2.2
                table.db_default(field_name, None)

            if isinstance(field, (fields.Boolean)):
                table.db_default(field_name, False)

            if isinstance(field, fields.Many2One):
                if field.model_name in ('res.user', 'res.group'):
                    # XXX need to merge ir and res
                    ref = field.model_name.replace('.', '_')
                else:
                    ref_model = pool.get(field.model_name)
                    if (issubclass(ref_model, ModelSQL)
                            and not callable(ref_model.table_query)):
                        ref = ref_model._table
                        # Create foreign key table if missing
                        if not backend.TableHandler.table_exist(ref):
                            backend.TableHandler(ref_model)
                    else:
                        ref = None
                if field_name in ['create_uid', 'write_uid']:
                    # migration from 3.6
                    table.drop_fk(field_name)
                elif ref:
                    table.add_fk(field_name, ref, on_delete=field.ondelete)

            required = field.required
            # Do not set 'NOT NULL' for Binary field as the database column
            # will be left empty if stored in the filestore or filled later by
            # the set method.
            if isinstance(field, fields.Binary):
                required = False
            table.not_null_action(
                field_name, action=required and 'add' or 'remove')

        for field_name, field in cls._fields.items():
            if (isinstance(field, fields.Many2One)
                    and field.model_name == cls.__name__):
                if field.path:
                    default_path = cls._defaults.get(
                        field.path, lambda: None)()
                    cursor.execute(*sql_table.select(sql_table.id,
                            where=(
                                Column(sql_table, field.path) == default_path)
                            | (Column(sql_table, field.path) == Null),
                            limit=1))
                    if cursor.fetchone():
                        cls._rebuild_path(field_name)
                if field.left and field.right:
                    left_default = cls._defaults.get(
                        field.left, lambda: None)()
                    right_default = cls._defaults.get(
                        field.right, lambda: None)()
                    cursor.execute(*sql_table.select(sql_table.id,
                            where=(
                                Column(sql_table, field.left) == left_default)
                            | (Column(sql_table, field.left) == Null)
                            | (Column(sql_table, field.right) == right_default)
                            | (Column(sql_table, field.right) == Null),
                            limit=1))
                    if cursor.fetchone():
                        cls._rebuild_tree(field_name, None, 0)

        for ident, constraint, _ in cls._sql_constraints:
            assert (
                not ident.startswith('idx_') and not ident.endswith('_index'))
            table.add_constraint(ident, constraint)

        if cls._history:
            cls._update_history_table()
            h_table = cls.__table_history__()
            cursor.execute(*sql_table.select(sql_table.id, limit=1))
            if cursor.fetchone():
                cursor.execute(
                    *h_table.select(h_table.id, limit=1))
                if not cursor.fetchone():
                    columns = [n for n, f in cls._fields.items()
                        if f.sql_type()]
                    cursor.execute(*h_table.insert(
                            [Column(h_table, c) for c in columns],
                            sql_table.select(*(Column(sql_table, c)
                                    for c in columns))))
                    cursor.execute(*h_table.update(
                            [h_table.write_date], [None]))

    @classmethod
    def _update_sql_indexes(cls, concurrently=False):
        def no_subset(index):
            for j in cls._sql_indexes:
                if j != index and index < j:
                    return False
            return True
        if not callable(cls.table_query):
            table_h = cls.__table_handler__()
            indexes = filter(no_subset, cls._sql_indexes)
            table_h.set_indexes(indexes, concurrently=concurrently)
            if cls._history:
                history_th = cls.__table_handler__(history=True)
                indexes = filter(no_subset, cls._history_sql_indexes)
                history_th.set_indexes(indexes, concurrently=concurrently)

    @classmethod
    def _update_history_table(cls):
        if cls._history:
            history_table = cls.__table_handler__(history=True)
            for field_name, field in cls._fields.items():
                if not field.sql_type():
                    continue
                history_table.add_column(field_name, field._sql_type)

    @classmethod
    @without_check_access
    def __raise_integrity_error(
            cls, exception, values, field_names=None, transaction=None):
        pool = Pool()
        if field_names is None:
            field_names = list(cls._fields.keys())
        if transaction is None:
            transaction = Transaction()
        for field_name in field_names:
            if field_name not in cls._fields:
                continue
            field = cls._fields[field_name]
            # Check required fields
            if (field.required
                    and field.sql_type()
                    and field_name not in ('create_uid', 'create_date')):
                if values.get(field_name) is None:
                    raise RequiredValidationError(
                        gettext('ir.msg_required_validation',
                            **cls.__names__(field_name)))
        for name, _, error in cls._sql_constraints:
            if backend.TableHandler.convert_name(name) in str(exception):
                raise SQLConstraintError(gettext(error))
        # Check foreign key in last because this can raise false positive
        # if the target is created during the same transaction.
        for field_name in field_names:
            if field_name not in cls._fields:
                continue
            field = cls._fields[field_name]
            if isinstance(field, fields.Many2One) and values.get(field_name):
                Model = pool.get(field.model_name)
                create_records = transaction.create_records[field.model_name]
                delete_records = transaction.delete_records[field.model_name]
                target_records = Model.search([
                        ('id', '=', field.sql_format(values[field_name])),
                        ], order=[])
                if not ((
                            target_records
                            or (values[field_name] in create_records))
                        and (values[field_name] not in delete_records)):
                    error_args = cls.__names__(field_name)
                    error_args['value'] = values[field_name]
                    raise ForeignKeyError(
                            gettext('ir.msg_foreign_model_missing',
                                **error_args))

    @classmethod
    @without_check_access
    def __raise_data_error(
            cls, exception, values, field_names=None, transaction=None):
        if field_names is None:
            field_names = list(cls._fields.keys())
        if transaction is None:
            transaction = Transaction()
        for field_name in field_names:
            if field_name not in cls._fields:
                continue
            field = cls._fields[field_name]
            # Check field size
            if (hasattr(field, 'size')
                    and isinstance(field.size, int)
                    and field.sql_type()):
                value = values.get(field_name) or ''
                size = len(value)
                if size > field.size:
                    error_args = cls.__names__(field_name)
                    error_args['value'] = value
                    error_args['size'] = size
                    error_args['max_size'] = field.size
                    raise SizeValidationError(
                        gettext('ir.msg_size_validation', **error_args))

    @classmethod
    def history_revisions(cls, ids):
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        User = pool.get('res.user')
        cursor = Transaction().connection.cursor()

        ModelAccess.check(cls.__name__, 'read')

        table = cls.__table_history__()
        user = User.__table__()
        revisions = []
        for sub_ids in grouped_slice(ids):
            where = reduce_ids(table.id, sub_ids)
            cursor.execute(*table.join(user, 'LEFT',
                    Coalesce(table.write_uid, table.create_uid) == user.id)
                .select(
                    Coalesce(table.write_date, table.create_date),
                    table.id,
                    user.name,
                    where=where))
            revisions.append(cursor.fetchall())
        revisions = list(chain(*revisions))
        revisions.sort(reverse=True)
        # SQLite uses char for COALESCE
        if revisions and isinstance(revisions[0][0], str):
            strptime = datetime.datetime.strptime
            format_ = '%Y-%m-%d %H:%M:%S.%f'
            revisions = [(strptime(timestamp, format_), id_, name)
                for timestamp, id_, name in revisions]
        return revisions

    @classmethod
    def _insert_history(cls, ids, deleted=False):
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        if not cls._history:
            return
        user = transaction.user
        table = cls.__table__()
        history = cls.__table_history__()
        columns = []
        hcolumns = []
        if not deleted:
            fields = cls._fields
        else:
            fields = {
                'id': cls.id,
                'write_uid': cls.write_uid,
                'write_date': cls.write_date,
                }
        for fname, field in sorted(fields.items()):
            if not field.sql_type():
                continue
            columns.append(Column(table, fname))
            hcolumns.append(Column(history, fname))
        for sub_ids in grouped_slice(ids):
            if not deleted:
                where = reduce_ids(table.id, sub_ids)
                cursor.execute(*history.insert(hcolumns,
                        table.select(*columns, where=where)))
            else:
                if transaction.database.has_multirow_insert():
                    cursor.execute(*history.insert(hcolumns,
                            [[id_, CurrentTimestamp(), user]
                                for id_ in sub_ids]))
                else:
                    for id_ in sub_ids:
                        cursor.execute(*history.insert(hcolumns,
                                [[id_, CurrentTimestamp(), user]]))

    @classmethod
    def _restore_history(cls, ids, datetime, _before=False):
        if not cls._history:
            return
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        table = cls.__table__()
        history = cls.__table_history__()

        transaction.counter += 1
        for cache in transaction.cache.values():
            if cls.__name__ in cache:
                cache_cls = cache[cls.__name__]
                for id_ in ids:
                    cache_cls.pop(id_, None)

        columns = []
        hcolumns = []
        fnames = sorted(n for n, f in cls._fields.items()
            if f.sql_type())
        for fname in fnames:
            columns.append(Column(table, fname))
            if fname == 'write_uid':
                hcolumns.append(Literal(transaction.user))
            elif fname == 'write_date':
                hcolumns.append(CurrentTimestamp())
            else:
                hcolumns.append(Column(history, fname))

        def is_deleted(values):
            return all(not v for n, v in zip(fnames, values)
                if n not in ['id', 'write_uid', 'write_date'])

        to_delete = []
        to_update = []
        for id_ in ids:
            column_datetime = Coalesce(history.write_date, history.create_date)
            if not _before:
                hwhere = (column_datetime <= datetime)
            else:
                hwhere = (column_datetime < datetime)
            hwhere &= (history.id == id_)
            horder = (column_datetime.desc, Column(history, '__id').desc)
            cursor.execute(*history.select(*hcolumns,
                    where=hwhere, order_by=horder, limit=1))
            values = cursor.fetchone()
            if not values or is_deleted(values):
                to_delete.append(id_)
            else:
                to_update.append(id_)
                values = list(values)
                cursor.execute(*table.update(columns, values,
                        where=table.id == id_))
                rowcount = cursor.rowcount
                if rowcount == -1 or rowcount is None:
                    cursor.execute(*table.select(table.id,
                            where=table.id == id_))
                    rowcount = len(cursor.fetchall())
                if rowcount < 1:
                    cursor.execute(*table.insert(columns, [values]))

        if to_delete:
            for sub_ids in grouped_slice(to_delete):
                where = reduce_ids(table.id, sub_ids)
                cursor.execute(*table.delete(where=where))
            cls._insert_history(to_delete, True)
        if to_update:
            cls._insert_history(to_update)

    @classmethod
    def restore_history(cls, ids, datetime):
        'Restore record ids from history at the date time'
        cls._restore_history(ids, datetime)

    @classmethod
    def restore_history_before(cls, ids, datetime):
        'Restore record ids from history before the date time'
        cls._restore_history(ids, datetime, _before=True)

    @classmethod
    def __check_timestamp(cls, ids):
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        table = cls.__table__()
        if not transaction.timestamp:
            return
        for sub_ids in grouped_slice(ids):
            where = Or()
            for id_ in sub_ids:
                try:
                    timestamp = transaction.timestamp.pop(
                        '%s,%s' % (cls.__name__, id_))
                except KeyError:
                    continue
                if timestamp is None:
                    continue
                sql_type = fields.Char('timestamp').sql_type().base
                where.append((table.id == id_)
                    & (Extract('EPOCH',
                            Coalesce(table.write_date, table.create_date)
                            ).cast(sql_type) != timestamp))
            if where:
                cursor.execute(*table.select(table.id, where=where, limit=1))
                if cursor.fetchone():
                    raise ConcurrencyException(
                        'Records were modified in the meanwhile')

    @classmethod
    @no_table_query
    def create(cls, vlist):
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        in_max = transaction.database.IN_MAX
        pool = Pool()
        Translation = pool.get('ir.translation')

        super(ModelSQL, cls).create(vlist)

        table = cls.__table__()
        modified_fields = set()
        defaults_cache = {}  # Store already computed default values
        missing_defaults = {}  # Store missing default values by schema
        new_ids = []
        vlist = [v.copy() for v in vlist]

        def db_insert(columns, vlist, column_names):
            if transaction.database.has_multirow_insert():
                vlist = (
                    s for s in grouped_slice(
                        vlist, in_max // (len(column_names) or 1)))
            else:
                vlist = ([v] for v in vlist)

            for values in vlist:
                values = list(values)
                cols = list(columns)
                try:
                    if len(values) > 1:
                        ids = transaction.database.nextid(
                            transaction.connection, cls._table,
                            count=len(values))
                        if ids is not None:
                            assert len(ids) == len(values)
                            cols.append(table.id)
                            for val, id in zip(values, ids):
                                val.append(id)
                            cursor.execute(*table.insert(cols, values))
                            yield from ids
                            continue
                    for i, val in enumerate(values):
                        if transaction.database.has_returning():
                            cursor.execute(*table.insert(
                                    cols, [val], [table.id]))
                            yield from (r[0] for r in cursor)
                        else:
                            id_new = transaction.database.nextid(
                                transaction.connection, cls._table)
                            if id_new:
                                if i == 0:
                                    cols.append(table.id)
                                val.append(id_new)
                                cursor.execute(*table.insert(cols, [val]))
                            else:
                                cursor.execute(*table.insert(cols, [val]))
                                id_new = transaction.database.lastid(cursor)
                            yield id_new
                except (
                        backend.DatabaseIntegrityError,
                        backend.DatabaseDataError
                        ) as exception:
                    if isinstance(exception, backend.DatabaseIntegrityError):
                        raise_func = cls.__raise_integrity_error
                    elif isinstance(exception, backend.DatabaseDataError):
                        raise_func = cls.__raise_data_error
                    with transaction.new_transaction():
                        for value in values:
                            skip = len(['create_uid', 'create_date'])
                            recomposed = dict(zip(column_names, value[skip:]))
                            raise_func(
                                exception, recomposed, transaction=transaction)
                        raise

        to_insert = []
        previous_columns = [table.create_uid, table.create_date]
        previous_column_names = []

        for values in vlist:
            # Clean values
            for key in ('create_uid', 'create_date',
                    'write_uid', 'write_date', 'id'):
                if key in values:
                    del values[key]
            modified_fields |= values.keys()

            # Get default values
            values_schema = tuple(sorted(values))
            if values_schema not in missing_defaults:
                default = []
                missing_defaults[values_schema] = default_values = {}
                for fname, field in cls._fields.items():
                    if fname in values:
                        continue
                    if fname in [
                            'create_uid', 'create_date',
                            'write_uid', 'write_date', 'id']:
                        continue
                    if isinstance(field, fields.Function) and not field.setter:
                        continue
                    if fname in defaults_cache:
                        default_values[fname] = defaults_cache[fname]
                    else:
                        default.append(fname)

                if default:
                    defaults = cls.default_get(default, with_rec_name=False)
                    default_values.update(cls._clean_defaults(defaults))
                    defaults_cache.update(default_values)
            values.update(missing_defaults[values_schema])

            current_column_names = []
            current_columns = [table.create_uid, table.create_date]
            current_values = [transaction.user, CurrentTimestamp()]

            # Insert record
            for fname, value in sorted(values.items()):
                field = cls._fields[fname]
                if not hasattr(field, 'set'):
                    current_columns.append(Column(table, fname))
                    current_values.append(field.sql_format(value))
                    current_column_names.append(fname)

            if current_column_names != previous_column_names:
                if to_insert:
                    new_ids.extend(db_insert(
                            previous_columns, to_insert,
                            previous_column_names))
                    to_insert.clear()
                previous_columns = current_columns
                previous_column_names = current_column_names
            to_insert.append(current_values)
        else:
            if to_insert:
                new_ids.extend(db_insert(
                        current_columns, to_insert, current_column_names))

        transaction.create_records[cls.__name__].update(new_ids)

        # Update path before fields_to_set which could create children
        if cls._path_fields:
            field_names = list(sorted(cls._path_fields))
            cls._set_path(field_names, repeat(new_ids, len(field_names)))
        # Update mptt before fields_to_set which could create children
        if cls._mptt_fields:
            field_names = list(sorted(cls._mptt_fields))
            cls._update_mptt(field_names, repeat(new_ids, len(field_names)))

        translation_values = {}
        fields_to_set = {}
        for values, new_id in zip(vlist, new_ids):
            for fname, value in values.items():
                field = cls._fields[fname]
                if (getattr(field, 'translate', False)
                        and not hasattr(field, 'set')):
                    translation_values.setdefault(
                        '%s,%s' % (cls.__name__, fname), {})[new_id] = (
                            field.sql_format(value))
                if hasattr(field, 'set'):
                    args = fields_to_set.setdefault(fname, [])
                    actions = iter(args)
                    for ids, val in zip(actions, actions):
                        if val == value:
                            ids.append(new_id)
                            break
                    else:
                        args.extend(([new_id], value))

        if translation_values:
            for name, translations in translation_values.items():
                Translation.set_ids(name, 'model', Transaction().language,
                    list(translations.keys()), list(translations.values()))

        for fname in sorted(fields_to_set, key=cls.index_set_field):
            fargs = fields_to_set[fname]
            field = cls._fields[fname]
            field.set(cls, fname, *fargs)

        cls._insert_history(new_ids)

        cls.__check_domain_rule(new_ids, 'create')
        records = cls.browse(new_ids)
        for sub_records in grouped_slice(
                records, record_cache_size(transaction)):
            cls._validate(sub_records)

        cls.trigger_create(records)
        return records

    @classmethod
    def read(cls, ids, fields_names):
        pool = Pool()
        Rule = pool.get('ir.rule')
        Translation = pool.get('ir.translation')
        super(ModelSQL, cls).read(ids, fields_names=fields_names)
        transaction = Transaction()
        cursor = Transaction().connection.cursor()

        if not ids:
            return []

        # construct a clause for the rules :
        domain = Rule.domain_get(cls.__name__, mode='read')

        fields_related = defaultdict(set)
        extra_fields = set()
        if 'write_date' not in fields_names:
            extra_fields.add('write_date')
        for field_name in fields_names:
            if field_name in {'_timestamp', '_write', '_delete'}:
                continue
            if '.' in field_name:
                field_name, field_related = field_name.split('.', 1)
                fields_related[field_name].add(field_related)
            if field_name.endswith(':string'):
                field_name = field_name[:-len(':string')]
                fields_related[field_name]
            field = cls._fields[field_name]
            if hasattr(field, 'datetime_field') and field.datetime_field:
                extra_fields.add(field.datetime_field)
            if field.context:
                extra_fields.update(fields.get_eval_fields(field.context))
        extra_fields.discard('id')
        all_fields = (
            set(fields_names) | fields_related.keys() | extra_fields)

        result = []
        table = cls.__table__()

        in_max = transaction.database.IN_MAX
        history_order = None
        history_clause = None
        history_limit = None
        if (cls._history
                and transaction.context.get('_datetime')
                and not callable(cls.table_query)):
            in_max = 1
            table = cls.__table_history__()
            column = Coalesce(table.write_date, table.create_date)
            history_clause = (column <= Transaction().context['_datetime'])
            history_order = (column.desc, Column(table, '__id').desc)
            history_limit = 1

        columns = {}
        for f in all_fields:
            field = cls._fields.get(f)
            if field and field.sql_type():
                columns[f] = field.sql_column(table).as_(f)
                if backend.name == 'sqlite':
                    columns[f].output_name += ' [%s]' % field.sql_type().base
            elif f in {'_write', '_delete'}:
                if not callable(cls.table_query):
                    rule_domain = Rule.domain_get(
                        cls.__name__, mode=f.lstrip('_'))
                    # No need to compute rule domain if it is the same as the
                    # read rule domain because it is already applied as where
                    # clause.
                    if rule_domain and rule_domain != domain:
                        rule_tables = {None: (table, None)}
                        rule_tables, rule_expression = cls.search_domain(
                            rule_domain, active_test=False, tables=rule_tables)
                        if len(rule_tables) > 1:
                            # The expression uses another table
                            rule_tables, rule_expression = cls.search_domain(
                                rule_domain, active_test=False)
                            rule_from = convert_from(None, rule_tables)
                            rule_table, _ = rule_tables[None]
                            rule_where = rule_table.id == table.id
                            rule_expression = rule_from.select(
                                        rule_expression, where=rule_where)
                        columns[f] = rule_expression.as_(f)
                    else:
                        columns[f] = Literal(True).as_(f)
            elif f == '_timestamp' and not callable(cls.table_query):
                sql_type = fields.Char('timestamp').sql_type().base
                columns[f] = Extract(
                    'EPOCH', Coalesce(table.write_date, table.create_date)
                    ).cast(sql_type).as_('_timestamp')

        if ('write_date' not in fields_names
                and columns.keys() == {'write_date'}):
            columns.pop('write_date')
            extra_fields.discard('write_date')
        if columns or domain:
            if 'id' not in fields_names:
                columns['id'] = table.id.as_('id')

            tables = {None: (table, None)}
            if domain:
                tables, dom_exp = cls.search_domain(
                    domain, active_test=False, tables=tables)
            from_ = convert_from(None, tables)
            for sub_ids in grouped_slice(ids, in_max):
                sub_ids = list(sub_ids)
                red_sql = reduce_ids(table.id, sub_ids)
                where = red_sql
                if history_clause:
                    where &= history_clause
                if domain:
                    where &= dom_exp
                cursor.execute(*from_.select(*columns.values(), where=where,
                        order_by=history_order, limit=history_limit))
                fetchall = list(cursor_dict(cursor))
                if not len(fetchall) == len({}.fromkeys(sub_ids)):
                    cls.__check_domain_rule(ids, 'read')
                    raise RuntimeError("Undetected access error")
                result.extend(fetchall)
        else:
            result = [{'id': x} for x in ids]

        cachable_fields = []
        max_write_date = max(
            (r['write_date'] for r in result if r.get('write_date')),
            default=None)
        for fname, column in columns.items():
            if fname.startswith('_'):
                continue
            field = cls._fields[fname]
            if not hasattr(field, 'get'):
                if getattr(field, 'translate', False):
                    translations = Translation.get_ids(
                        cls.__name__ + ',' + fname, 'model',
                        Transaction().language, ids,
                        cached_after=max_write_date)
                    for row in result:
                        row[fname] = translations.get(row['id']) or row[fname]
                if fname != 'id':
                    cachable_fields.append(fname)

        # all fields for which there is a get attribute
        getter_fields = [f for f in all_fields
            if f in cls._fields and hasattr(cls._fields[f], 'get')]
        getter_fields = sorted(getter_fields, key=cls.index_get_field)

        cache = transaction.get_cache()[cls.__name__]
        if getter_fields and cachable_fields:
            for row in result:
                for fname in cachable_fields:
                    cache[row['id']][fname] = row[fname]

        func_fields = {}
        for fname in getter_fields:
            field = cls._fields[fname]
            if isinstance(field, fields.Function):
                key = (
                    field.getter, field.getter_with_context,
                    getattr(field, 'datetime_field', None))
                func_fields.setdefault(key, [])
                func_fields[key].append(fname)
            elif getattr(field, 'datetime_field', None):
                for row in result:
                    with Transaction().set_context(
                            _datetime=row[field.datetime_field]):
                        date_result = field.get([row['id']], cls, fname,
                            values=[row])
                    row[fname] = date_result[row['id']]
            else:
                # get the value of that field for all records/ids
                getter_result = field.get(ids, cls, fname, values=result)
                for row in result:
                    row[fname] = getter_result[row['id']]

        for key in func_fields:
            field_list = func_fields[key]
            fname = field_list[0]
            field = cls._fields[fname]
            _, getter_with_context, datetime_field = key
            if datetime_field:
                for row in result:
                    with Transaction().set_context(
                            _datetime=row[datetime_field]):
                        date_results = field.get([row['id']], cls, field_list,
                            values=[row])
                    for fname in field_list:
                        date_result = date_results[fname]
                        row[fname] = date_result[row['id']]
            else:
                for sub_results in grouped_slice(
                        result, record_cache_size(transaction)):
                    sub_results = list(sub_results)
                    sub_ids = []
                    sub_values = []
                    for row in sub_results:
                        if (row['id'] not in cache
                                or any(f not in cache[row['id']]
                                    for f in field_list)):
                            sub_ids.append(row['id'])
                            sub_values.append(row)
                        else:
                            for fname in field_list:
                                row[fname] = cache[row['id']][fname]
                    getter_results = field.get(
                        sub_ids, cls, field_list, values=sub_values)
                    for fname in field_list:
                        getter_result = getter_results[fname]
                        for row in sub_values:
                            row[fname] = getter_result[row['id']]
                            if (transaction.readonly
                                    and not getter_with_context):
                                cache[row['id']][fname] = row[fname]

        def read_related(field, Target, rows, fields):
            name = field.name
            target_ids = []
            if field._type.endswith('2many'):
                add = target_ids.extend
            elif field._type == 'reference':
                def add(value):
                    try:
                        id_ = int(value.split(',', 1)[1])
                    except ValueError:
                        pass
                    else:
                        if id_ >= 0:
                            target_ids.append(id_)
            else:
                add = target_ids.append
            for row in rows:
                value = row[name]
                if value is not None:
                    add(value)
            related_read_limit = transaction.context.get('related_read_limit')
            rows = Target.read(target_ids[:related_read_limit], fields)
            if related_read_limit is not None:
                rows += [{'id': i} for i in target_ids[related_read_limit:]]
            return rows

        def add_related(field, rows, targets):
            name = field.name
            key = name + '.'
            if field._type.endswith('2many'):
                for row in rows:
                    row[key] = values = list()
                    for target in row[name]:
                        if target is not None:
                            values.append(targets[target])
            elif field._type in {'selection', 'multiselection'}:
                key = name + ':string'
                for row, target in zip(rows, targets):
                    selection = field.get_selection(cls, name, target)
                    if field._type == 'selection':
                        row[key] = field.get_selection_string(
                            selection, row[name])
                    else:
                        row[key] = [
                            field.get_selection_string(selection, v)
                            for v in row[name]]
            else:
                for row in rows:
                    value = row[name]
                    if isinstance(value, str):
                        try:
                            value = int(value.split(',', 1)[1])
                        except ValueError:
                            value = None
                    if value is not None and value >= 0:
                        row[key] = targets[value]
                    else:
                        row[key] = None

        to_del = set()
        for fname in fields_related.keys() | extra_fields:
            if fname not in fields_names:
                to_del.add(fname)
            if fname not in cls._fields:
                continue
            if fname not in fields_related:
                continue
            field = cls._fields[fname]
            datetime_field = getattr(field, 'datetime_field', None)

            def groupfunc(row):
                ctx = {}
                if field.context:
                    pyson_context = PYSONEncoder().encode(field.context)
                    ctx.update(PYSONDecoder(row).decode(pyson_context))
                if datetime_field:
                    ctx['_datetime'] = row.get(datetime_field)
                if field._type in {'selection', 'multiselection'}:
                    Target = None
                elif field._type == 'reference':
                    value = row[fname]
                    if not value:
                        Target = None
                    else:
                        model, _ = value.split(',', 1)
                        Target = pool.get(model)
                else:
                    Target = field.get_target()
                return Target, ctx

            def orderfunc(row):
                Target, ctx = groupfunc(row)
                return (Target.__name__ if Target else '', freeze(ctx))

            for (Target, ctx), rows in groupby(
                    sorted(result, key=orderfunc), key=groupfunc):
                rows = list(rows)
                with Transaction().set_context(ctx):
                    if Target:
                        targets = read_related(
                            field, Target, rows, list(fields_related[fname]))
                        targets = {t['id']: t for t in targets}
                    else:
                        targets = cls.browse([r['id'] for r in rows])
                    add_related(field, rows, targets)

        for row, field in product(result, to_del):
            del row[field]

        return result

    @classmethod
    @no_table_query
    def write(cls, records, values, *args):
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        pool = Pool()
        Translation = pool.get('ir.translation')
        Config = pool.get('ir.configuration')

        assert not len(args) % 2
        # Remove possible duplicates from all records
        all_records = list(OrderedDict.fromkeys(
                sum(((records, values) + args)[0:None:2], [])))
        all_ids = [r.id for r in all_records]
        all_field_names = set()

        # Call before cursor cache cleaning
        trigger_eligibles = cls.trigger_write_get_eligibles(all_records)

        super(ModelSQL, cls).write(records, values, *args)

        table = cls.__table__()

        cls.__check_timestamp(all_ids)
        cls.__check_domain_rule(all_ids, 'write')

        fields_to_set = {}
        actions = iter((records, values) + args)
        for records, values in zip(actions, actions):
            ids = [r.id for r in records]
            values = values.copy()

            # Clean values
            for key in ('create_uid', 'create_date',
                    'write_uid', 'write_date', 'id'):
                if key in values:
                    del values[key]

            columns = [table.write_uid, table.write_date]
            update_values = [transaction.user, CurrentTimestamp()]
            store_translation = Transaction().language == Config.get_language()
            for fname, value in values.items():
                field = cls._fields[fname]
                if not hasattr(field, 'set'):
                    if (not getattr(field, 'translate', False)
                            or store_translation):
                        columns.append(Column(table, fname))
                        update_values.append(field.sql_format(value))

            for sub_ids in grouped_slice(ids):
                red_sql = reduce_ids(table.id, sub_ids)
                try:
                    cursor.execute(*table.update(columns, update_values,
                            where=red_sql))
                except (
                        backend.DatabaseIntegrityError,
                        backend.DatabaseDataError) as exception:
                    transaction = Transaction()
                    with Transaction().new_transaction():
                        if isinstance(
                                exception, backend.DatabaseIntegrityError):
                            cls.__raise_integrity_error(
                                exception, values, list(values.keys()),
                                transaction=transaction)
                        elif isinstance(exception, backend.DatabaseDataError):
                            cls.__raise_data_error(
                                exception, values, list(values.keys()),
                                transaction=transaction)
                        raise

            for fname, value in values.items():
                field = cls._fields[fname]
                if (getattr(field, 'translate', False)
                        and not hasattr(field, 'set')):
                    Translation.set_ids(
                        '%s,%s' % (cls.__name__, fname), 'model',
                        transaction.language, ids,
                        [field.sql_format(value)] * len(ids))
                if hasattr(field, 'set'):
                    fields_to_set.setdefault(fname, []).extend((ids, value))

            path_fields = cls._path_fields & values.keys()
            if path_fields:
                cls._update_path(
                    list(sorted(path_fields)), repeat(ids, len(path_fields)))

            mptt_fields = cls._mptt_fields & values.keys()
            if mptt_fields:
                cls._update_mptt(
                    list(sorted(mptt_fields)), repeat(ids, len(mptt_fields)),
                    values)
            all_field_names |= values.keys()

        for fname in sorted(fields_to_set, key=cls.index_set_field):
            fargs = fields_to_set[fname]
            field = cls._fields[fname]
            field.set(cls, fname, *fargs)

        cls._insert_history(all_ids)

        cls.__check_domain_rule(all_ids, 'write')
        for sub_records in grouped_slice(
                all_records, record_cache_size(transaction)):
            cls._validate(sub_records, field_names=all_field_names)

        cls.trigger_write(trigger_eligibles)

    @classmethod
    @no_table_query
    def delete(cls, records):
        transaction = Transaction()
        in_max = transaction.database.IN_MAX
        cursor = transaction.connection.cursor()
        pool = Pool()
        Translation = pool.get('ir.translation')
        ids = list(map(int, records))

        if not ids:
            return

        table = cls.__table__()

        if cls.__name__ in transaction.delete_records:
            ids = ids[:]
            for del_id in transaction.delete_records[cls.__name__]:
                while ids:
                    try:
                        ids.remove(del_id)
                    except ValueError:
                        break

        cls.__check_timestamp(ids)
        cls.__check_domain_rule(ids, 'delete')

        tree_ids = {}
        for fname in cls._mptt_fields:
            field = cls._fields[fname]
            tree_ids[fname] = []
            for sub_ids in grouped_slice(ids):
                where = reduce_ids(field.sql_column(table), sub_ids)
                cursor.execute(*table.select(table.id, where=where))
                tree_ids[fname] += [x[0] for x in cursor]

        has_translation = any(
            getattr(f, 'translate', False) and not hasattr(f, 'set')
            for f in cls._fields.values())

        foreign_keys_tocheck = []
        foreign_keys_toupdate = []
        foreign_keys_todelete = []
        for _, model in pool.iterobject():
            if (not issubclass(model, ModelStorage)
                    or callable(getattr(model, 'table_query', None))):
                continue
            for field_name, field in model._fields.items():
                if (isinstance(field, fields.Many2One)
                        and field.model_name == cls.__name__):
                    if field.ondelete == 'CASCADE':
                        foreign_keys_todelete.append((model, field_name))
                    elif field.ondelete == 'SET NULL':
                        if field.required:
                            foreign_keys_tocheck.append((model, field_name))
                        else:
                            foreign_keys_toupdate.append((model, field_name))
                    else:
                        foreign_keys_tocheck.append((model, field_name))

        transaction.delete_records[cls.__name__].update(ids)
        cls.trigger_delete(records)

        if len(records) > in_max:
            # Clean self referencing foreign keys
            # before deleting them by small groups
            # Use the record id as value instead of NULL
            # in case the field is required
            foreign_fields_to_clean = [
                fn for m, fn in foreign_keys_tocheck if m == cls]
            if foreign_fields_to_clean:
                for sub_ids in grouped_slice(ids):
                    columns = [
                        Column(table, n) for n in foreign_fields_to_clean]
                    cursor.execute(*table.update(
                            columns, [table.id] * len(foreign_fields_to_clean),
                            where=reduce_ids(table.id, sub_ids)))

        def get_related_records(Model, field_name, sub_ids):
            if issubclass(Model, ModelSQL):
                foreign_table = Model.__table__()
                foreign_red_sql = reduce_ids(
                    Column(foreign_table, field_name), sub_ids)
                cursor.execute(*foreign_table.select(foreign_table.id,
                        where=foreign_red_sql))
                related_records = Model.browse([x[0] for x in cursor])
            else:
                with without_check_access(), inactive_records():
                    related_records = Model.search(
                        [(field_name, 'in', sub_ids)],
                        order=[])
            if Model == cls:
                related_records = list(set(related_records) - set(records))
            return related_records

        for sub_ids, sub_records in zip(
                grouped_slice(ids), grouped_slice(records)):
            sub_ids = list(sub_ids)
            red_sql = reduce_ids(table.id, sub_ids)

            for Model, field_name in foreign_keys_toupdate:
                related_records = get_related_records(
                    Model, field_name, sub_ids)
                if related_records:
                    Model.write(related_records, {
                            field_name: None,
                            })

            for Model, field_name in foreign_keys_todelete:
                related_records = get_related_records(
                    Model, field_name, sub_ids)
                if related_records:
                    Model.delete(related_records)

            for Model, field_name in foreign_keys_tocheck:
                if get_related_records(Model, field_name, sub_ids):
                    error_args = Model.__names__(field_name)
                    raise ForeignKeyError(
                        gettext('ir.msg_foreign_model_exist',
                            **error_args))

            super(ModelSQL, cls).delete(list(sub_records))

            try:
                cursor.execute(*table.delete(where=red_sql))
            except backend.DatabaseIntegrityError as exception:
                transaction = Transaction()
                with Transaction().new_transaction():
                    cls.__raise_integrity_error(
                        exception, {}, transaction=transaction)
                    raise

        if has_translation:
            Translation.delete_ids(cls.__name__, 'model', ids)

        cls._insert_history(ids, deleted=True)

        cls._update_mptt(list(tree_ids.keys()), list(tree_ids.values()))

    @classmethod
    def __check_domain_rule(cls, ids, mode):
        pool = Pool()
        Lang = pool.get('ir.lang')
        Rule = pool.get('ir.rule')
        Model = pool.get('ir.model')
        try:
            User = pool.get('res.user')
            Group = pool.get('res.group')
        except KeyError:
            User = Group = None
        table = cls.__table__()
        transaction = Transaction()
        in_max = transaction.database.IN_MAX
        history_clause = None
        limit = None
        if (mode == 'read'
                and cls._history
                and transaction.context.get('_datetime')
                and not callable(cls.table_query)):
            in_max = 1
            table = cls.__table_history__()
            column = Coalesce(table.write_date, table.create_date)
            history_clause = (column <= Transaction().context['_datetime'])
            limit = 1
        cursor = transaction.connection.cursor()
        assert mode in Rule.modes

        def test_domain(ids, domain):
            result = []
            tables = {None: (table, None)}
            if domain:
                tables, dom_exp = cls.search_domain(
                    domain, active_test=False, tables=tables)
            from_ = convert_from(None, tables)
            for sub_ids in grouped_slice(ids, in_max):
                sub_ids = set(sub_ids)
                where = reduce_ids(table.id, sub_ids)
                if history_clause:
                    where &= history_clause
                if domain:
                    where &= dom_exp
                cursor.execute(
                    *from_.select(table.id, where=where, limit=limit))
                rowcount = cursor.rowcount
                if rowcount == -1 or rowcount is None:
                    rowcount = len(cursor.fetchall())
                if rowcount != len(sub_ids):
                    cursor.execute(
                        *from_.select(table.id, where=where, limit=limit))
                    result.extend(
                        sub_ids.difference([x for x, in cursor]))
            return result

        domains = []
        if mode in {'read', 'write'}:
            domains.append([])
        domain = Rule.domain_get(cls.__name__, mode=mode)
        if domain:
            domains.append(domain)
        for domain in domains:
            wrong_ids = test_domain(ids, domain)
            if wrong_ids:
                model = cls.__name__
                if Model:
                    model = Model.get_name(cls.__name__)
                ids = ', '.join(map(str, wrong_ids[:5]))
                if len(wrong_ids) > 5:
                    ids += '...'
                if domain:
                    rules = []
                    clause, clause_global = Rule.get(cls.__name__, mode=mode)
                    if clause:
                        dom = list(clause.values())
                        dom.insert(0, 'OR')
                        if test_domain(wrong_ids, dom):
                            rules.extend(clause.keys())

                    for rule, dom in clause_global.items():
                        if test_domain(wrong_ids, dom):
                            rules.append(rule)

                    msg = gettext(
                        f'ir.msg_{mode}_rule_error', ids=ids, model=model,
                        rules='\n'.join(r.name for r in rules))
                else:
                    msg = gettext(
                        f'ir.msg_{mode}_error', ids=ids, model=model)

                ctx_msg = []
                lang = Lang.get()
                if cls._history and transaction.context.get('_datetime'):
                    ctx_msg.append(gettext('ir.msg_context_datetime',
                            datetime=lang.strftime(
                                transaction.context['_datetime'])))
                if domain and User and Group:
                    groups = Group.browse(User.get_groups())
                    ctx_msg.append(gettext('ir.msg_context_groups',
                            groups=', '.join(g.rec_name for g in groups)))
                raise AccessError(msg, '\n'.join(ctx_msg))

    @classmethod
    def __search_query(cls, domain, count, query, order):
        pool = Pool()
        Rule = pool.get('ir.rule')

        rule_domain = Rule.domain_get(cls.__name__, mode='read')
        joined_domains = None
        if domain and domain[0] == 'OR':
            local_domains, subquery_domains = split_subquery_domain(domain)
            if subquery_domains:
                joined_domains = subquery_domains
                if local_domains:
                    local_domains.insert(0, 'OR')
                    joined_domains.append(local_domains)

        def get_local_columns(order_exprs):
            local_columns = []
            for order_expr in order_exprs:
                if (isinstance(order_expr, Column)
                        and isinstance(order_expr._from, Table)
                        and order_expr._from._name == cls._table):
                    local_columns.append(order_expr._name)
                else:
                    raise NotImplementedError
            return local_columns

        # The UNION optimization needs the columns used to order the query
        extra_columns = set()
        if order and joined_domains:
            tables = {
                None: (cls.__table__(), None),
                }
            for oexpr, otype in order:
                fname = oexpr.partition('.')[0]
                field = cls._fields[fname]
                field_orders = field.convert_order(oexpr, tables, cls)
                try:
                    order_columns = get_local_columns(field_orders)
                    extra_columns.update(order_columns)
                except NotImplementedError:
                    joined_domains = None
                    break

        # In case the search uses subqueries it's more efficient to use a UNION
        # of queries than using clauses with some JOIN because databases can
        # used indexes
        if joined_domains is not None:
            union_tables = []
            for sub_domain in joined_domains:
                sub_domain = [sub_domain]  # it may be a clause
                tables, expression = cls.search_domain(sub_domain)
                if rule_domain:
                    tables, domain_exp = cls.search_domain(
                        rule_domain, active_test=False, tables=tables)
                    expression &= domain_exp
                main_table, _ = tables[None]
                table = convert_from(None, tables)
                columns = cls.__searched_columns(main_table,
                    eager=not count and not query,
                    extra_columns=extra_columns)
                union_tables.append(table.select(
                        *columns, where=expression))
            expression = None
            tables = {
                None: (Union(*union_tables, all_=False), None),
                }
        else:
            tables, expression = cls.search_domain(domain)
            if rule_domain:
                tables, domain_exp = cls.search_domain(
                    rule_domain, active_test=False, tables=tables)
                expression &= domain_exp

        return tables, expression

    @classmethod
    def __searched_columns(
            cls, table, *, eager=False, history=False, extra_columns=None):
        if extra_columns is None:
            extra_columns = []
        else:
            extra_columns = sorted(extra_columns - {'id', '__id', '_datetime'})
        columns = [table.id.as_('id')]
        if (cls._history and Transaction().context.get('_datetime')
                and (eager or history)):
            columns.append(
                Coalesce(table.write_date, table.create_date).as_('_datetime'))
            columns.append(Column(table, '__id').as_('__id'))
        for column_name in extra_columns:
            field = cls._fields[column_name]
            sql_column = field.sql_column(table).as_(column_name)
            columns.append(sql_column)
        if eager:
            columns += [f.sql_column(table).as_(n)
                for n, f in sorted(cls._fields.items())
                if not hasattr(f, 'get')
                    and n not in extra_columns
                    and n != 'id'
                    and not getattr(f, 'translate', False)
                    and f.loading == 'eager']
            if not callable(cls.table_query):
                sql_type = fields.Char('timestamp').sql_type().base
                columns += [Extract('EPOCH',
                        Coalesce(table.write_date, table.create_date)
                        ).cast(sql_type).as_('_timestamp')]
        return columns

    @classmethod
    def __search_order(cls, order, tables):
        order_by = []
        order_types = {
            'DESC': Desc,
            'ASC': Asc,
            }
        null_ordering_types = {
            'NULLS FIRST': NullsFirst,
            'NULLS LAST': NullsLast,
            None: lambda _: _
            }
        for oexpr, otype in order:
            fname, _, extra_expr = oexpr.partition('.')
            field = cls._fields[fname]
            if not otype:
                otype, null_ordering = 'ASC', None
            else:
                otype = otype.upper()
                try:
                    otype, null_ordering = otype.split(' ', 1)
                except ValueError:
                    null_ordering = None
            Order = order_types[otype]
            NullOrdering = null_ordering_types[null_ordering]
            forder = field.convert_order(oexpr, tables, cls)
            order_by.extend((NullOrdering(Order(o)) for o in forder))

        return order_by

    @classmethod
    def search(cls, domain, offset=0, limit=None, order=None, count=False,
            query=False):
        transaction = Transaction()
        cursor = transaction.connection.cursor()

        super(ModelSQL, cls).search(
            domain, offset=offset, limit=limit, order=order, count=count)

        if order is None or order is False:
            order = cls._order
        tables, expression = cls.__search_query(domain, count, query, order)

        main_table, _ = tables[None]
        if count:
            table = convert_from(None, tables)
            if (limit is not None and limit < cls.estimated_count()) or offset:
                select = table.select(
                    Literal(1), where=expression, limit=limit, offset=offset
                    ).select(Count(Literal('*')))
            else:
                select = table.select(Count(Literal('*')), where=expression)
            if query:
                return select
            else:
                cursor.execute(*select)
                return cursor.fetchone()[0]

        order_by = cls.__search_order(order, tables)
        # compute it here because __search_order might modify tables
        table = convert_from(None, tables)
        if query:
            columns = [main_table.id.as_('id')]
        else:
            columns = cls.__searched_columns(main_table, eager=True)
            if backend.name == 'sqlite':
                for column in columns:
                    field = cls._fields.get(column.output_name)
                    if field:
                        column.output_name += ' [%s]' % field.sql_type().base
        select = table.select(
            *columns, where=expression, limit=limit, offset=offset,
            order_by=order_by)

        if query:
            return select
        cursor.execute(*select)

        rows = list(cursor_dict(cursor, transaction.database.IN_MAX))
        cache = transaction.get_cache()
        delete_records = transaction.delete_records[cls.__name__]

        # Can not cache the history value if we are not sure to have fetch all
        # the rows for each records
        if (not (cls._history and transaction.context.get('_datetime'))
                or len(rows) < transaction.database.IN_MAX):
            keys = None
            for data in islice(rows, 0, cache.size_limit):
                if data['id'] in delete_records:
                    continue
                if keys is None:
                    keys = list(data.keys())
                    for k in keys[:]:
                        if k in ('_timestamp', '_datetime', '__id'):
                            continue
                        field = cls._fields[k]
                        if not getattr(field, 'datetime_field', None):
                            keys.remove(k)
                            continue
                for k in keys:
                    del data[k]
                cache[cls.__name__][data['id']]._update(data)

        return cls.browse([x['id'] for x in rows])

    @classmethod
    def search_domain(cls, domain, active_test=None, tables=None):
        '''
        Return SQL tables and expression
        Set active_test to add it.
        '''
        transaction = Transaction()
        if active_test is None:
            active_test = transaction.active_records
        domain = cls._search_domain_active(domain, active_test=active_test)

        if tables is None:
            tables = {}
        if None not in tables:
            if cls._history and transaction.context.get('_datetime'):
                tables[None] = (cls.__table_history__(), None)
            else:
                tables[None] = (cls.__table__(), None)

        def convert(domain):
            if is_leaf(domain):
                fname = domain[0].split('.', 1)[0]
                field = cls._fields[fname]
                expression = field.convert_domain(domain, tables, cls)
                if not isinstance(expression, (Operator, Expression)):
                    return convert(expression)
                return expression
            elif not domain or list(domain) in (['OR'], ['AND']):
                return Literal(True)
            elif domain[0] == 'OR':
                return Or((convert(d) for d in domain[1:]))
            else:
                return And((convert(d) for d in (
                            domain[1:] if domain[0] == 'AND' else domain)))

        with without_check_access():
            expression = convert(domain)

        if cls._history and transaction.context.get('_datetime'):
            database = Transaction().database
            if database.has_window_functions():
                table, _ = tables[None]
                history = cls.__table_history__()
                last_change = Coalesce(history.write_date, history.create_date)
                # prefilter the history records for a bit of a speedup
                selected_h_ids = convert_from(None, tables).select(
                    table.id, where=expression)
                most_recent = history.select(
                    history.create_date, Column(history, '__id'),
                    RowNumber(
                        window=Window([history.id],
                            order_by=[
                                last_change.desc,
                                Column(history, '__id').desc])).as_('rank'),
                    where=((last_change <= transaction.context['_datetime'])
                        & history.id.in_(selected_h_ids)))
                # Filter again as the latest records from most_recent might not
                # match the expression
                expression &= Exists(most_recent.select(
                        Literal(1),
                        where=(
                            (Column(table, '__id')
                                == Column(most_recent, '__id'))
                            & (most_recent.create_date != Null)
                            & (most_recent.rank == 1))))
            else:
                table, _ = tables[None]
                history_1 = cls.__table_history__()
                history_2 = cls.__table_history__()
                last_change = Coalesce(
                    history_1.write_date, history_1.create_date)
                latest_change = history_1.select(
                    history_1.id, Max(last_change).as_('date'),
                    where=(last_change <= transaction.context['_datetime']),
                    group_by=[history_1.id])
                most_recent = history_2.join(
                    latest_change,
                    condition=(
                        (history_2.id == latest_change.id)
                        & (Coalesce(
                                history_2.write_date, history_2.create_date)
                            == latest_change.date))
                    ).select(
                        Max(Column(history_2, '__id')).as_('h_id'),
                        where=(history_2.create_date != Null),
                        group_by=[history_2.id])
                expression &= Exists(most_recent.select(
                        Literal(1),
                        where=(Column(table, '__id') == most_recent.h_id)))
        return tables, expression

    @classmethod
    def _rebuild_path(cls, field_name):
        "Rebuild path for the tree."
        cursor = Transaction().connection.cursor()
        field = cls._fields[field_name]
        table = cls.__table__()
        tree = With('id', 'path', recursive=True)
        tree.query = table.select(
            table.id, Concat(table.id, '/'),
            where=Column(table, field_name) == Null)
        tree.query |= (table
            .join(tree,
                condition=Column(table, field_name) == tree.id)
            .select(table.id, Concat(Concat(tree.path, table.id), '/')))
        query = table.update(
            [Column(table, field.path)],
            [tree.path],
            from_=[tree], where=table.id == tree.id,
            with_=[tree])
        cursor.execute(*query)

    @classmethod
    def _set_path(cls, field_names, list_ids):
        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        parent = cls.__table__()
        for field_name, ids in zip(field_names, list_ids):
            field = cls._fields[field_name]
            parent_column = Column(table, field_name)
            path_column = Column(table, field.path)
            query = table.update(
                [path_column],
                [Concat(Concat(Coalesce(
                                parent.select(parent.path,
                                    where=parent.id == parent_column),
                                ''), table.id), '/')])
            for sub_ids in grouped_slice(ids):
                query.where = reduce_ids(table.id, sub_ids)
                cursor.execute(*query)

    @classmethod
    def _update_path(cls, field_names, list_ids):
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        update = transaction.connection.cursor()
        table = cls.__table__()
        parent = cls.__table__()

        def update_path(query, column, sub_ids):
            updated = set()
            query.where = reduce_ids(table.id, sub_ids)
            cursor.execute(*query)
            for old_path, new_path in cursor:
                if old_path == new_path:
                    continue
                if any(old_path.startswith(p) for p in updated):
                    return False
                update.execute(*table.update(
                        [column],
                        [Concat(new_path,
                                Substring(table.path, len(old_path) + 1))],
                        where=table.path.like(old_path + '%')))
                updated.add(old_path)
            return True

        for field_name, ids in zip(field_names, list_ids):
            field = cls._fields[field_name]
            parent_column = Column(table, field_name)
            parent_path_column = Column(parent, field.path)
            path_column = Column(table, field.path)
            query = (table
                .join(parent, 'LEFT',
                    condition=parent_column == parent.id)
                .select(path_column,
                    Concat(Concat(
                            Coalesce(parent_path_column, ''), table.id), '/')))
            for sub_ids in grouped_slice(ids):
                sub_ids = list(sub_ids)
                while not update_path(query, path_column, sub_ids):
                    pass

    @classmethod
    def _update_mptt(cls, field_names, list_ids, values=None):
        for field_name, ids in zip(field_names, list_ids):
            field = cls._fields[field_name]
            if (values is not None
                    and (field.left in values or field.right in values)):
                raise Exception('ValidateError',
                    'You can not update fields: "%s", "%s"' %
                    (field.left, field.right))

            if len(ids) < max(cls.estimated_count() / 4, 4):
                for id_ in ids:
                    cls._update_tree(id_, field_name,
                        field.left, field.right)
            else:
                cls._rebuild_tree(field_name, None, 0)

    @classmethod
    def _rebuild_tree(cls, parent, parent_id, left):
        '''
        Rebuild left, right value for the tree.
        '''
        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        right = left + 1

        cursor.execute(*table.select(table.id,
                where=Column(table, parent) == parent_id))
        for child_id, in cursor:
            right = cls._rebuild_tree(parent, child_id, right)

        field = cls._fields[parent]

        if parent_id:
            cursor.execute(*table.update(
                    [Column(table, field.left), Column(table, field.right)],
                    [left, right],
                    where=table.id == parent_id))
        return right + 1

    @classmethod
    def _update_tree(cls, record_id, field_name, left, right):
        '''
        Update left, right values for the tree.
        Remarks:
            - the value (right - left - 1) / 2 will not give
                the number of children node
        '''
        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        left = Column(table, left)
        right = Column(table, right)
        field = Column(table, field_name)
        cursor.execute(*table.select(left, right, field,
                where=table.id == record_id))
        fetchone = cursor.fetchone()
        if not fetchone:
            return
        old_left, old_right, parent_id = fetchone
        if old_left == old_right == 0:
            cursor.execute(*table.select(Max(right),
                    where=field == Null))
            old_left, = cursor.fetchone()
            old_left += 1
            old_right = old_left + 1
            cursor.execute(*table.update([left, right],
                    [old_left, old_right],
                    where=table.id == record_id))
        size = old_right - old_left + 1

        parent_right = 1

        if parent_id:
            cursor.execute(*table.select(right, where=table.id == parent_id))
            parent_right = cursor.fetchone()[0]
        else:
            cursor.execute(*table.select(Max(right), where=field == Null))
            fetchone = cursor.fetchone()
            if fetchone:
                parent_right = fetchone[0] + 1

        cursor.execute(*table.update([left], [left + size],
                where=left >= parent_right))
        cursor.execute(*table.update([right], [right + size],
                where=right >= parent_right))
        if old_left < parent_right:
            left_delta = parent_right - old_left
            right_delta = parent_right - old_left
            left_cond = old_left
            right_cond = old_right
        else:
            left_delta = parent_right - old_left - size
            right_delta = parent_right - old_left - size
            left_cond = old_left + size
            right_cond = old_right + size
        cursor.execute(*table.update([left, right],
                [left + left_delta, right + right_delta],
                where=(left >= left_cond) & (right <= right_cond)))

    @classmethod
    def validate(cls, records):
        super(ModelSQL, cls).validate(records)
        transaction = Transaction()
        database = transaction.database
        connection = transaction.connection
        has_constraint = database.has_constraint
        lock = database.lock
        cursor = transaction.connection.cursor()
        # Works only for a single transaction
        ids = list(map(int, records))
        for _, sql, error in cls._sql_constraints:
            if has_constraint(sql):
                continue
            table = sql.table
            if isinstance(sql, (Unique, Exclude)):
                lock(connection, cls._table)
                columns = list(sql.columns)
                columns.insert(0, table.id)
                in_max = transaction.database.IN_MAX // (len(columns) + 1)
                for sub_ids in grouped_slice(ids, in_max):
                    where = reduce_ids(table.id, sub_ids)
                    if isinstance(sql, Exclude) and sql.where:
                        where &= sql.where

                    cursor.execute(*table.select(*columns, where=where))

                    where = Literal(False)
                    for row in cursor:
                        clause = table.id != row[0]
                        for column, operator, value in zip(
                                sql.columns, sql.operators, row[1:]):
                            if value is None:
                                # NULL is always unique
                                clause &= Literal(False)
                            clause &= operator(column, value)
                        where |= clause
                    if isinstance(sql, Exclude) and sql.where:
                        where &= sql.where
                    cursor.execute(
                        *table.select(table.id, where=where, limit=1))
                    if cursor.fetchone():
                        raise SQLConstraintError(gettext(error))
            elif isinstance(sql, Check):
                for sub_ids in grouped_slice(ids):
                    red_sql = reduce_ids(table.id, sub_ids)
                    cursor.execute(*table.select(table.id,
                            where=~sql.expression & red_sql,
                            limit=1))
                    if cursor.fetchone():
                        raise SQLConstraintError(gettext(error))

    @dualmethod
    def lock(cls, records=None):
        transaction = Transaction()
        database = transaction.database
        connection = transaction.connection
        table = cls.__table__()

        if records is not None and database.has_select_for():
            for sub_records in grouped_slice(records):
                where = reduce_ids(table.id, sub_records)
                query = table.select(
                    Literal(1), where=where, for_=For('UPDATE', nowait=True))
                with connection.cursor() as cursor:
                    cursor.execute(*query)
        else:
            transaction.lock_table(cls._table)


def convert_from(table, tables, type_='LEFT'):
    # Don't nested joins as SQLite doesn't support
    right, condition = tables[None]
    if table:
        table = table.join(right, type_, condition)
    else:
        table = right
    for k, sub_tables in tables.items():
        if k is None:
            continue
        table = convert_from(table, sub_tables, type_=type_)
    return table


def split_subquery_domain(domain):
    """
    Split a domain in two parts:
        - the first one contains all the sub-domains with only local fields
        - the second one contains all the sub-domains using a related field
    The main operator of the domain will be stripped from the results.
    """
    local_domains, subquery_domains = [], []
    for sub_domain in domain:
        if is_leaf(sub_domain):
            if '.' in sub_domain[0]:
                subquery_domains.append(sub_domain)
            else:
                local_domains.append(sub_domain)
        elif (not sub_domain or list(sub_domain) in [['OR'], ['AND']]
                or sub_domain in ['OR', 'AND']):
            continue
        else:
            sub_ldomains, sub_sqdomains = split_subquery_domain(sub_domain)
            if sub_sqdomains:
                subquery_domains.append(sub_domain)
            else:
                local_domains.append(sub_domain)

    return local_domains, subquery_domains
