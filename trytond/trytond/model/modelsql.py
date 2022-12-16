# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from itertools import islice, chain, product, groupby
from collections import OrderedDict, defaultdict
from functools import wraps

from sql import (Table, Column, Literal, Desc, Asc, Expression, Null,
    NullsFirst, NullsLast, For)
from sql.functions import CurrentTimestamp, Extract
from sql.conditionals import Coalesce
from sql.operators import Or, And, Operator, Equal
from sql.aggregate import Count, Max

from trytond.i18n import gettext
from trytond.model import ModelStorage, ModelView
from trytond.model import fields
from trytond import backend
from trytond.tools import reduce_ids, grouped_slice, cursor_dict
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.pyson import PYSONEncoder, PYSONDecoder
from trytond.cache import LRUDict, freeze
from trytond.exceptions import ConcurrencyException
from trytond.rpc import RPC
from trytond.config import config

from .modelstorage import (cache_size, is_leaf,
    ValidationError, RequiredValidationError, AccessError)
from .descriptors import dualmethod


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
        if not callable(cls.table_query):
            table = cls.__table__()
            cls._sql_constraints.append(
                ('id_positive', Check(table, table.id >= 0),
                    'ir.msg_id_positive'))
        cls._order = [('id', 'ASC')]
        if issubclass(cls, ModelView):
            cls.__rpc__.update({
                    'history_revisions': RPC(),
                    })

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
        TableHandler = backend.get('TableHandler')
        return TableHandler(cls, module_name, history=history)

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        TableHandler = backend.get('TableHandler')
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
            history_table.index_action('id', action='add')

        for field_name, field in cls._fields.items():
            if field_name == 'id':
                continue
            sql_type = field.sql_type()
            if not sql_type:
                continue

            default = None
            if field_name in cls._defaults:
                def default():
                    default_ = cls._clean_defaults({
                            field_name: cls._defaults[field_name](),
                            })[field_name]
                    return field.sql_format(default_)

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
                        if not TableHandler.table_exist(ref):
                            TableHandler(ref_model)
                    else:
                        ref = None
                if field_name in ['create_uid', 'write_uid']:
                    # migration from 3.6
                    table.drop_fk(field_name)
                elif ref:
                    table.add_fk(field_name, ref, field.ondelete)

            table.index_action(
                field_name, action=field.select and 'add' or 'remove')

            required = field.required
            # Do not set 'NOT NULL' for Binary field as the database column
            # will be left empty if stored in the filestore or filled later by
            # the set method.
            if isinstance(field, fields.Binary):
                required = False
            table.not_null_action(
                field_name, action=required and 'add' or 'remove')

        for field_name, field in cls._fields.items():
            if isinstance(field, fields.Many2One) \
                    and field.model_name == cls.__name__ \
                    and field.left and field.right:
                left_default = cls._defaults.get(field.left, lambda: None)()
                right_default = cls._defaults.get(field.right, lambda: None)()
                cursor.execute(*sql_table.select(sql_table.id,
                        where=(Column(sql_table, field.left) == left_default)
                        | (Column(sql_table, field.left) == Null)
                        | (Column(sql_table, field.right) == right_default)
                        | (Column(sql_table, field.right) == Null),
                        limit=1))
                if cursor.fetchone():
                    cls._rebuild_tree(field_name, None, 0)

        for ident, constraint, _ in cls._sql_constraints:
            table.add_constraint(ident, constraint)

        if cls._history:
            cls._update_history_table()
            history_table = cls.__table_history__()
            cursor.execute(*sql_table.select(sql_table.id, limit=1))
            if cursor.fetchone():
                cursor.execute(
                    *history_table.select(history_table.id, limit=1))
                if not cursor.fetchone():
                    columns = [n for n, f in cls._fields.items()
                        if f.sql_type()]
                    cursor.execute(*history_table.insert(
                            [Column(history_table, c) for c in columns],
                            sql_table.select(*(Column(sql_table, c)
                                    for c in columns))))
                    cursor.execute(*history_table.update(
                            [history_table.write_date], [None]))

    @classmethod
    def _update_history_table(cls):
        if cls._history:
            history_table = cls.__table_handler__(history=True)
            for field_name, field in cls._fields.items():
                if not field.sql_type():
                    continue
                history_table.add_column(field_name, field._sql_type)

    @classmethod
    def __raise_integrity_error(
            cls, exception, values, field_names=None, transaction=None):
        pool = Pool()
        TableHandler = backend.get('TableHandler')
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
                        gettext('ir.msg_required_validation_record',
                            **cls.__names__(field_name)))
        for name, _, error in cls._sql_constraints:
            if TableHandler.convert_name(name) in str(exception):
                raise SQLConstraintError(gettext(error))
        # Check foreign key in last because this can raise false positive
        # if the target is created during the same transaction.
        for field_name in field_names:
            if field_name not in cls._fields:
                continue
            field = cls._fields[field_name]
            if isinstance(field, fields.Many2One) and values.get(field_name):
                Model = pool.get(field.model_name)
                create_records = transaction.create_records.get(
                    field.model_name, set())
                delete_records = transaction.delete_records.get(
                    field.model_name, set())
                target_records = Model.search([
                        ('id', '=', field.sql_format(values[field_name])),
                        ], order=[])
                if not ((target_records
                            or (values[field_name] in create_records))
                        and (values[field_name] not in delete_records)):
                    error_args = cls.__names__(field_name)
                    error_args['value'] = values[field_name]
                    raise ForeignKeyError(
                            gettext('ir.msg_foreign_model_missing',
                                **error_args))

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
        DatabaseIntegrityError = backend.get('DatabaseIntegrityError')
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        pool = Pool()
        Translation = pool.get('ir.translation')

        super(ModelSQL, cls).create(vlist)

        table = cls.__table__()
        modified_fields = set()
        defaults_cache = {}  # Store already computed default values
        new_ids = []
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            # Clean values
            for key in ('create_uid', 'create_date',
                    'write_uid', 'write_date', 'id'):
                if key in values:
                    del values[key]
            modified_fields |= set(values.keys())

            # Get default values
            default = []
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
                    values[fname] = defaults_cache[fname]
                else:
                    default.append(fname)

            if default:
                defaults = cls.default_get(default, with_rec_name=False)
                defaults = cls._clean_defaults(defaults)
                values.update(defaults)
                defaults_cache.update(defaults)

            insert_columns = [table.create_uid, table.create_date]
            insert_values = [transaction.user, CurrentTimestamp()]

            # Insert record
            for fname, value in values.items():
                field = cls._fields[fname]
                if not hasattr(field, 'set'):
                    insert_columns.append(Column(table, fname))
                    insert_values.append(field.sql_format(value))

            try:
                if transaction.database.has_returning():
                    cursor.execute(*table.insert(insert_columns,
                            [insert_values], [table.id]))
                    id_new, = cursor.fetchone()
                else:
                    id_new = transaction.database.nextid(
                        transaction.connection, cls._table)
                    if id_new:
                        insert_columns.append(table.id)
                        insert_values.append(id_new)
                        cursor.execute(*table.insert(insert_columns,
                                [insert_values]))
                    else:
                        cursor.execute(*table.insert(insert_columns,
                                [insert_values]))
                        id_new = transaction.database.lastid(cursor)
                new_ids.append(id_new)
            except DatabaseIntegrityError as exception:
                transaction = Transaction()
                with Transaction().new_transaction(), \
                        Transaction().set_context(_check_access=False):
                    cls.__raise_integrity_error(
                        exception, values, transaction=transaction)
                raise

        transaction.create_records.setdefault(cls.__name__,
            set()).update(new_ids)

        translation_values = {}
        fields_to_set = {}
        for values, new_id in zip(vlist, new_ids):
            for fname, value in values.items():
                field = cls._fields[fname]
                if (getattr(field, 'translate', False)
                        and not hasattr(field, 'set')):
                    translation_values.setdefault(
                        '%s,%s' % (cls.__name__, fname), {})[new_id] = value
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

        field_names = list(cls._fields.keys())
        cls._update_mptt(field_names, [new_ids] * len(field_names))

        cls.__check_domain_rule(new_ids, 'create')
        records = cls.browse(new_ids)
        for sub_records in grouped_slice(records, cache_size()):
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
        for field_name in fields_names:
            if field_name == '_timestamp':
                continue
            if '.' in field_name:
                field_name, field_related = field_name.split('.', 1)
                fields_related[field_name].add(field_related)
            field = cls._fields[field_name]
            if hasattr(field, 'datetime_field') and field.datetime_field:
                extra_fields.add(field.datetime_field)
            if field.context:
                extra_fields.update(fields.get_eval_fields(field.context))
        extra_fields.discard('id')
        all_fields = (
            set(fields_names) | set(fields_related.keys()) | extra_fields)

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

        columns = []
        for f in all_fields:
            field = cls._fields.get(f)
            if field and field.sql_type():
                columns.append(field.sql_column(table).as_(f))
            elif f == '_timestamp' and not callable(cls.table_query):
                sql_type = fields.Char('timestamp').sql_type().base
                columns.append(Extract('EPOCH',
                        Coalesce(table.write_date, table.create_date)
                        ).cast(sql_type).as_('_timestamp'))

        if len(columns):
            if 'id' not in fields_names:
                columns.append(table.id.as_('id'))

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
                cursor.execute(*from_.select(*columns, where=where,
                        order_by=history_order, limit=history_limit))
                fetchall = list(cursor_dict(cursor))
                if not len(fetchall) == len({}.fromkeys(sub_ids)):
                    cls.__check_domain_rule(
                        ids, 'read', nodomain='ir.msg_read_error')
                    cls.__check_domain_rule(ids, 'read')
                    raise RuntimeError("Undetected access error")
                result.extend(fetchall)
        else:
            result = [{'id': x} for x in ids]

        cachable_fields = []
        for column in columns:
            # Split the output name to remove SQLite type detection
            fname = column.output_name.split()[0]
            if fname == '_timestamp':
                continue
            field = cls._fields[fname]
            if not hasattr(field, 'get'):
                if getattr(field, 'translate', False):
                    translations = Translation.get_ids(
                        cls.__name__ + ',' + fname, 'model',
                        Transaction().language, ids)
                    for row in result:
                        row[fname] = translations.get(row['id']) or row[fname]
                if fname != 'id':
                    cachable_fields.append(fname)

        # all fields for which there is a get attribute
        getter_fields = [f for f in all_fields
            if f in cls._fields and hasattr(cls._fields[f], 'get')]

        if getter_fields and cachable_fields:
            cache = transaction.get_cache().setdefault(
                cls.__name__, LRUDict(cache_size()))
            for row in result:
                if row['id'] not in cache:
                    cache[row['id']] = {}
                for fname in cachable_fields:
                    cache[row['id']][fname] = row[fname]

        func_fields = {}
        for fname in getter_fields:
            field = cls._fields[fname]
            if isinstance(field, fields.Function):
                key = (field.getter, getattr(field, 'datetime_field', None))
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
            _, datetime_field = key
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
                getter_results = field.get(ids, cls, field_list, values=result)
                for fname in field_list:
                    getter_result = getter_results[fname]
                    for row in result:
                        row[fname] = getter_result[row['id']]

        def read_related(field, Target, rows, fields):
            name = field.name
            target_ids = []
            if field._type.endswith('2many'):
                add = target_ids.extend
            elif field._type == 'reference':
                def add(value):
                    id_ = int(value.split(',', 1)[1])
                    if id_ >= 0:
                        target_ids.append(id_)
            else:
                add = target_ids.append
            for row in rows:
                value = row[name]
                if value is not None:
                    add(value)
            return Target.read(target_ids, fields)

        def add_related(field, rows, targets):
            name = field.name
            key = name + '.'
            if field._type.endswith('2many'):
                for row in rows:
                    row[key] = values = list()
                    for target in row[name]:
                        if target is not None:
                            values.append(targets[target])
            else:
                for row in rows:
                    value = row[name]
                    if isinstance(value, str):
                        value = int(value.split(',', 1)[1])
                    if value is not None and value >= 0:
                        row[key] = targets[value]
                    else:
                        row[key] = None

        to_del = set()
        for fname in set(fields_related.keys()) | extra_fields:
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
                if field._type == 'reference':
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
                        targets = {}
                    add_related(field, rows, targets)

        for row, field in product(result, to_del):
            del row[field]

        return result

    @classmethod
    @no_table_query
    def write(cls, records, values, *args):
        DatabaseIntegrityError = backend.get('DatabaseIntegrityError')
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
        cls.__check_domain_rule(
            all_ids, 'write', nodomain='ir.msg_write_error')

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
                except DatabaseIntegrityError as exception:
                    transaction = Transaction()
                    with Transaction().new_transaction(), \
                            Transaction().set_context(_check_access=False):
                        cls.__raise_integrity_error(
                            exception, values, list(values.keys()),
                            transaction=transaction)
                    raise

            for fname, value in values.items():
                field = cls._fields[fname]
                if (getattr(field, 'translate', False)
                        and not hasattr(field, 'set')):
                    Translation.set_ids(
                        '%s,%s' % (cls.__name__, fname), 'model',
                        transaction.language, ids, [value] * len(ids))
                if hasattr(field, 'set'):
                    fields_to_set.setdefault(fname, []).extend((ids, value))

            field_names = list(values.keys())
            cls._update_mptt(field_names, [ids] * len(field_names), values)
            all_field_names |= set(field_names)

        for fname in sorted(fields_to_set, key=cls.index_set_field):
            fargs = fields_to_set[fname]
            field = cls._fields[fname]
            field.set(cls, fname, *fargs)

        cls._insert_history(all_ids)

        cls.__check_domain_rule(all_ids, 'write')
        for sub_records in grouped_slice(all_records, cache_size()):
            cls._validate(sub_records, field_names=all_field_names)

        cls.trigger_write(trigger_eligibles)

    @classmethod
    @no_table_query
    def delete(cls, records):
        DatabaseIntegrityError = backend.get('DatabaseIntegrityError')
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        pool = Pool()
        Translation = pool.get('ir.translation')
        ids = list(map(int, records))

        if not ids:
            return

        table = cls.__table__()

        if transaction.delete and transaction.delete.get(cls.__name__):
            ids = ids[:]
            for del_id in transaction.delete[cls.__name__]:
                for i in range(ids.count(del_id)):
                    ids.remove(del_id)

        cls.__check_timestamp(ids)
        cls.__check_domain_rule(ids, 'delete')

        has_translation = False
        tree_ids = {}
        for fname, field in cls._fields.items():
            if (isinstance(field, fields.Many2One)
                    and field.model_name == cls.__name__
                    and field.left and field.right):
                tree_ids[fname] = []
                for sub_ids in grouped_slice(ids):
                    where = reduce_ids(field.sql_column(table), sub_ids)
                    cursor.execute(*table.select(table.id, where=where))
                    tree_ids[fname] += [x[0] for x in cursor.fetchall()]
            if (getattr(field, 'translate', False)
                    and not hasattr(field, 'set')):
                has_translation = True

        foreign_keys_tocheck = []
        foreign_keys_toupdate = []
        foreign_keys_todelete = []
        for _, model in pool.iterobject():
            if callable(getattr(model, 'table_query', None)):
                continue
            if not issubclass(model, ModelStorage):
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

        transaction.delete.setdefault(cls.__name__, set()).update(ids)
        cls.trigger_delete(records)

        def get_related_records(Model, field_name, sub_ids):
            if issubclass(Model, ModelSQL):
                foreign_table = Model.__table__()
                foreign_red_sql = reduce_ids(
                    Column(foreign_table, field_name), sub_ids)
                cursor.execute(*foreign_table.select(foreign_table.id,
                        where=foreign_red_sql))
                records = Model.browse([x[0] for x in cursor.fetchall()])
            else:
                with transaction.set_context(active_test=False):
                    records = Model.search([(field_name, 'in', sub_ids)])
            return records

        for sub_ids, sub_records in zip(
                grouped_slice(ids), grouped_slice(records)):
            sub_ids = list(sub_ids)
            red_sql = reduce_ids(table.id, sub_ids)

            transaction.delete_records.setdefault(cls.__name__,
                set()).update(sub_ids)

            for Model, field_name in foreign_keys_toupdate:
                if (not hasattr(Model, 'search')
                        or not hasattr(Model, 'write')):
                    continue
                records = get_related_records(Model, field_name, sub_ids)
                if records:
                    Model.write(records, {
                            field_name: None,
                            })

            for Model, field_name in foreign_keys_todelete:
                if (not hasattr(Model, 'search')
                        or not hasattr(Model, 'delete')):
                    continue
                records = get_related_records(Model, field_name, sub_ids)
                if records:
                    Model.delete(records)

            for Model, field_name in foreign_keys_tocheck:
                with Transaction().set_context(_check_access=False):
                    if Model.search([
                                (field_name, 'in', sub_ids),
                                ], order=[]):
                        error_args = Model.__names__(field_name)
                        raise ForeignKeyError(
                            gettext('ir.msg_foreign_model_exist',
                                **error_args))

            super(ModelSQL, cls).delete(list(sub_records))

            try:
                cursor.execute(*table.delete(where=red_sql))
            except DatabaseIntegrityError as exception:
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
    def __check_domain_rule(cls, ids, mode, nodomain=None):
        pool = Pool()
        Rule = pool.get('ir.rule')
        Model = pool.get('ir.model')
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

        domain = Rule.domain_get(cls.__name__, mode=mode)
        if not domain and not nodomain:
            return
        wrong_ids = test_domain(ids, domain)
        if wrong_ids:
            model = cls.__name__
            if Model:
                models = Model.search([
                        ('model', '=', cls.__name__),
                        ], limit=1)
                if models:
                    model, = models
                    model = model.name
            ids = ', '.join(map(str, ids[:5]))
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
                    'ir.msg_%s_rule_error' % mode, ids=ids, model=model,
                    rules='\n'.join(r.name for r in rules))
            else:
                msg = gettext(nodomain, ids=ids, model=model)
            raise AccessError(msg)

    @classmethod
    def search(cls, domain, offset=0, limit=None, order=None, count=False,
            query=False):
        pool = Pool()
        Rule = pool.get('ir.rule')
        transaction = Transaction()
        cursor = transaction.connection.cursor()

        super(ModelSQL, cls).search(
            domain, offset=offset, limit=limit, order=order, count=count)

        # Get domain clauses
        tables, expression = cls.search_domain(domain)

        # Get order by
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
        if order is None or order is False:
            order = cls._order
        for oexpr, otype in order:
            fname, _, extra_expr = oexpr.partition('.')
            field = cls._fields[fname]
            otype = otype.upper()
            try:
                otype, null_ordering = otype.split(' ', 1)
            except ValueError:
                null_ordering = None
            Order = order_types[otype]
            NullOrdering = null_ordering_types[null_ordering]
            forder = field.convert_order(oexpr, tables, cls)
            order_by.extend((NullOrdering(Order(o)) for o in forder))

        # construct a clause for the rules :
        domain = Rule.domain_get(cls.__name__, mode='read')
        if domain:
            tables, dom_exp = cls.search_domain(
                domain, active_test=False, tables=tables)
            expression &= dom_exp

        main_table, _ = tables[None]
        table = convert_from(None, tables)

        if count:
            cursor.execute(*table.select(Count(Literal('*')),
                    where=expression, limit=limit, offset=offset))
            return cursor.fetchone()[0]
        # execute the "main" query to fetch the ids we were searching for
        columns = [main_table.id.as_('id')]
        if (cls._history and transaction.context.get('_datetime')
                and not query):
            columns.append(Coalesce(
                    main_table.write_date,
                    main_table.create_date).as_('_datetime'))
            columns.append(Column(main_table, '__id').as_('__id'))
        if not query:
            columns += [f.sql_column(main_table).as_(n)
                for n, f in cls._fields.items()
                if not hasattr(f, 'get')
                and n != 'id'
                and not getattr(f, 'translate', False)
                and f.loading == 'eager']
            if not callable(cls.table_query):
                sql_type = fields.Char('timestamp').sql_type().base
                columns += [Extract('EPOCH',
                        Coalesce(main_table.write_date, main_table.create_date)
                        ).cast(sql_type).as_('_timestamp')]
        select = table.select(*columns,
            where=expression, order_by=order_by, limit=limit, offset=offset)
        if query:
            return select
        cursor.execute(*select)

        rows = list(cursor_dict(cursor, transaction.database.IN_MAX))
        cache = transaction.get_cache()
        if cls.__name__ not in cache:
            cache[cls.__name__] = LRUDict(cache_size())
        delete_records = transaction.delete_records.setdefault(cls.__name__,
            set())

        def filter_history(rows):
            if not (cls._history and transaction.context.get('_datetime')):
                return rows

            def history_key(row):
                return row['_datetime'], row['__id']

            ids_history = {}
            for row in rows:
                key = history_key(row)
                if row['id'] in ids_history:
                    if key < ids_history[row['id']]:
                        continue
                ids_history[row['id']] = key

            to_delete = set()
            history = cls.__table_history__()
            for sub_ids in grouped_slice([r['id'] for r in rows]):
                where = reduce_ids(history.id, sub_ids)
                cursor.execute(*history.select(
                        history.id.as_('id'),
                        history.write_date.as_('write_date'),
                        where=where
                        & (history.write_date != Null)
                        & (history.create_date == Null)
                        & (history.write_date
                            <= transaction.context['_datetime'])))
                for deleted_id, delete_date in cursor.fetchall():
                    history_date, _ = ids_history[deleted_id]
                    if isinstance(history_date, str):
                        strptime = datetime.datetime.strptime
                        format_ = '%Y-%m-%d %H:%M:%S.%f'
                        history_date = strptime(history_date, format_)
                    if history_date <= delete_date:
                        to_delete.add(deleted_id)

            return filter(lambda r: history_key(r) == ids_history[r['id']]
                and r['id'] not in to_delete, rows)

        # Can not cache the history value if we are not sure to have fetch all
        # the rows for each records
        if (not (cls._history and transaction.context.get('_datetime'))
                or len(rows) < transaction.database.IN_MAX):
            rows = list(filter_history(rows))
            keys = None
            for data in islice(rows, 0, cache.size_limit):
                if data['id'] in delete_records:
                    continue
                if keys is None:
                    keys = list(data.keys())
                    for k in keys[:]:
                        if k in ('_timestamp', '_datetime', '__id'):
                            keys.remove(k)
                            continue
                        field = cls._fields[k]
                        if not getattr(field, 'datetime_field', None):
                            keys.remove(k)
                            continue
                for k in keys:
                    del data[k]
                cache[cls.__name__].setdefault(data['id'], {}).update(data)

        if len(rows) >= transaction.database.IN_MAX:
            if (cls._history
                    and transaction.context.get('_datetime')
                    and not query):
                columns = columns[:3]
            else:
                columns = columns[:1]
            cursor.execute(*table.select(*columns,
                    where=expression, order_by=order_by,
                    limit=limit, offset=offset))
            rows = filter_history(list(cursor_dict(cursor)))

        return cls.browse([x['id'] for x in rows])

    @classmethod
    def search_domain(cls, domain, active_test=True, tables=None):
        '''
        Return SQL tables and expression
        Set active_test to add it.
        '''
        transaction = Transaction()
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

        expression = convert(domain)

        if cls._history and transaction.context.get('_datetime'):
            table, _ = tables[None]
            expression &= (Coalesce(table.write_date, table.create_date)
                <= transaction.context['_datetime'])
        return tables, expression

    @classmethod
    def _update_mptt(cls, field_names, list_ids, values=None):
        cursor = Transaction().connection.cursor()
        for field_name, ids in zip(field_names, list_ids):
            field = cls._fields[field_name]
            if (isinstance(field, fields.Many2One)
                    and field.model_name == cls.__name__
                    and field.left and field.right):
                if (values is not None
                        and (field.left in values or field.right in values)):
                    raise Exception('ValidateError',
                        'You can not update fields: "%s", "%s"' %
                        (field.left, field.right))

                # Nested creation require a rebuild
                # because initial values are 0
                # and thus _update_tree can not find the children
                table = cls.__table__()
                parent = cls.__table__()
                cursor.execute(*table.join(parent,
                        condition=Column(table, field_name) == parent.id
                        ).select(table.id,
                        where=(Column(parent, field.left) == 0)
                        & (Column(parent, field.right) == 0),
                        limit=1))
                nested_create = cursor.fetchone()

                if not nested_create and len(ids) < 2:
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
        childs = cursor.fetchall()

        for child_id, in childs:
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
                    for row in cursor.fetchall():
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
    def lock(cls, records):
        transaction = Transaction()
        database = transaction.database
        connection = transaction.connection
        table = cls.__table__()

        if database.has_select_for():
            for sub_records in grouped_slice(records):
                where = reduce_ids(table.id, sub_records)
                query = table.select(
                    Literal(1), where=where, for_=For('UPDATE', nowait=True))
                with connection.cursor() as cursor:
                    cursor.execute(*query)
        else:
            database.lock(connection, cls._table)


def convert_from(table, tables):
    # Don't nested joins as SQLite doesn't support
    right, condition = tables[None]
    if table:
        table = table.join(right, 'LEFT', condition)
    else:
        table = right
    for k, sub_tables in tables.items():
        if k is None:
            continue
        table = convert_from(table, sub_tables)
    return table
