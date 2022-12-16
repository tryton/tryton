#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import re
import datetime
from functools import reduce
from itertools import islice, izip, chain, ifilter

from sql import Table, Column, Literal, Desc, Asc, Expression, Flavor
from sql.functions import Now, Extract
from sql.conditionals import Coalesce
from sql.operators import Or, And, Operator
from sql.aggregate import Count, Max

from trytond.model import ModelStorage, ModelView
from trytond.model import fields
from trytond import backend
from trytond.tools import reduce_ids, grouped_slice
from trytond.const import OPERATORS, RECORD_CACHE_SIZE
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.cache import LRUDict
from trytond.exceptions import ConcurrencyException
from trytond.rpc import RPC
_RE_UNIQUE = re.compile('UNIQUE\s*\((.*)\)', re.I)
_RE_CHECK = re.compile('CHECK\s*\((.*)\)', re.I)


class ModelSQL(ModelStorage):
    """
    Define a model with storage in database.
    """
    _table = None  # The name of the table in database
    _order = None
    _order_name = None  # Use to force order field when sorting on Many2One
    _history = False

    @classmethod
    def __setup__(cls):
        super(ModelSQL, cls).__setup__()
        cls._sql_constraints = []
        cls._order = [('id', 'ASC')]
        cls._sql_error_messages = {}
        if issubclass(cls, ModelView):
            cls.__rpc__.update({
                    'history_revisions': RPC(),
                    })

        if not cls._table:
            cls._table = cls.__name__.replace('.', '_')

        assert cls._table[-9:] != '__history', \
            'Model _table %s cannot end with "__history"' % cls._table

    @classmethod
    def __table__(cls):
        return cls.table_query() or Table(cls._table)

    @classmethod
    def __table_history__(cls):
        if not cls._history:
            raise ValueError('No history table')
        return Table(cls._table + '__history')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        super(ModelSQL, cls).__register__(module_name)

        if cls.table_query():
            return

        pool = Pool()

        # create/update table in the database
        table = TableHandler(Transaction().cursor, cls, module_name)
        if cls._history:
            history_table = TableHandler(Transaction().cursor, cls,
                    module_name, history=True)
            history_table.index_action('id', action='add')

        for field_name, field in cls._fields.iteritems():
            if field_name == 'id':
                continue
            default_fun = None
            try:
                sql_type = field.sql_type()
            except NotImplementedError:
                continue
            if field_name in cls._defaults:
                default_fun = cls._defaults[field_name]

                def unpack_wrapper(fun):
                    def unpack_result(*a):
                        try:
                            # XXX ugly hack: some default fct try
                            # to access the non-existing table
                            result = fun(*a)
                        except Exception:
                            return None
                        clean_results = cls._clean_defaults(
                            {field_name: result})
                        return clean_results[field_name]
                    return unpack_result
                default_fun = unpack_wrapper(default_fun)

            if hasattr(field, 'size') and isinstance(field.size, int):
                field_size = field.size
            else:
                field_size = None

            table.add_raw_column(field_name, sql_type, field.sql_format,
                default_fun, field_size, string=field.string)
            if cls._history:
                history_table.add_raw_column(field_name, sql_type, None,
                    string=field.string)

            if isinstance(field, (fields.Integer, fields.Float)):
                # migration from tryton 2.2
                table.db_default(field_name, None)

            if isinstance(field, (fields.Boolean)):
                table.db_default(field_name, False)

            if isinstance(field, fields.Many2One):
                if field.model_name in ('res.user', 'res.group'):
                    ref = field.model_name.replace('.', '_')
                else:
                    ref = pool.get(field.model_name)._table
                table.add_fk(field_name, ref, field.ondelete)

            table.index_action(
                field_name, action=field.select and 'add' or 'remove')

            required = field.required
            table.not_null_action(
                field_name, action=required and 'add' or 'remove')

        for field_name, field in cls._fields.iteritems():
            if isinstance(field, fields.Many2One) \
                    and field.model_name == cls.__name__ \
                    and field.left and field.right:
                cls._rebuild_tree(field_name, None, 0)

        for ident, constraint, _ in cls._sql_constraints:
            table.add_constraint(ident, constraint)

        if cls._history:
            cls._update_history_table()
            cursor = Transaction().cursor
            table = cls.__table__()
            history_table = cls.__table_history__()
            cursor.execute(*table.select(table.id))
            if cursor.fetchone():
                cursor.execute(*history_table.select(history_table.id))
                if not cursor.fetchone():
                    columns = [n for n, f in cls._fields.iteritems()
                        if not hasattr(f, 'set')]
                    cursor.execute(*history_table.insert(
                            [Column(history_table, c) for c in columns],
                            table.select(*(Column(table, c)
                                    for c in columns))))
                    cursor.execute(*history_table.update(
                            [history_table.write_date], [None]))

    @classmethod
    def _update_history_table(cls):
        TableHandler = backend.get('TableHandler')
        if cls._history:
            table = TableHandler(Transaction().cursor, cls)
            history_table = TableHandler(Transaction().cursor, cls,
                    history=True)
            for column_name in table._columns:
                string = ''
                if column_name in cls._fields:
                    string = cls._fields[column_name].string
                history_table.add_raw_column(column_name,
                    (table._columns[column_name]['typname'],
                        table._columns[column_name]['typname']),
                    None, string=string)

    @classmethod
    def _get_error_messages(cls):
        res = super(ModelSQL, cls)._get_error_messages()
        res += cls._sql_error_messages.values()
        for _, _, error in cls._sql_constraints:
            res.append(error)
        return res

    @staticmethod
    def table_query():
        return None

    @classmethod
    def __raise_integrity_error(cls, exception, values, field_names=None):
        pool = Pool()
        if field_names is None:
            field_names = cls._fields.keys()
        for field_name in field_names:
            if field_name not in cls._fields:
                continue
            field = cls._fields[field_name]
            # Check required fields
            if (field.required
                    and not hasattr(field, 'set')
                    and field_name not in ('create_uid', 'create_date')):
                if values.get(field_name) is None:
                    cls.raise_user_error('required_field',
                        error_args=cls._get_error_args(field_name))
            if isinstance(field, fields.Many2One) and values.get(field_name):
                Model = pool.get(field.model_name)
                create_records = Transaction().create_records.get(
                    field.model_name, set())
                delete_records = Transaction().delete_records.get(
                    field.model_name, set())
                target_records = Model.search([
                        ('id', '=', values[field_name]),
                        ], order=[])
                if not ((target_records
                            or (values[field_name] in create_records))
                        and (values[field_name] not in delete_records)):
                    error_args = cls._get_error_args(field_name)
                    error_args['value'] = values[field_name]
                    cls.raise_user_error('foreign_model_missing',
                        error_args=error_args)
        for name, _, error in cls._sql_constraints:
            if name in exception[0]:
                cls.raise_user_error(error)
        for name, error in cls._sql_error_messages.iteritems():
            if name in exception[0]:
                cls.raise_user_error(error)

    @classmethod
    def history_revisions(cls, ids):
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        User = pool.get('res.user')
        cursor = Transaction().cursor

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
        if revisions and isinstance(revisions[0][0], basestring):
            strptime = datetime.datetime.strptime
            format_ = '%Y-%m-%d %H:%M:%S.%f'
            revisions = [(strptime(timestamp, format_), id_, name)
                for timestamp, id_, name in revisions]
        return revisions

    @classmethod
    def __insert_history(cls, ids, deleted=False):
        transaction = Transaction()
        cursor = transaction.cursor
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
        for fname, field in sorted(fields.iteritems()):
            if hasattr(field, 'set'):
                continue
            columns.append(Column(table, fname))
            hcolumns.append(Column(history, fname))
        for sub_ids in grouped_slice(ids):
            if not deleted:
                where = reduce_ids(table.id, sub_ids)
                cursor.execute(*history.insert(hcolumns,
                        table.select(*columns, where=where)))
            else:
                cursor.execute(*history.insert(hcolumns,
                        [[id_, Now(), user] for id_ in sub_ids]))

    @classmethod
    def restore_history(cls, ids, datetime):
        'Restore record ids from history at the date time'
        if not cls._history:
            return
        transaction = Transaction()
        cursor = transaction.cursor
        table = cls.__table__()
        history = cls.__table_history__()
        columns = []
        hcolumns = []
        fnames = sorted(n for n, f in cls._fields.iteritems()
            if not hasattr(f, 'set'))
        for fname in fnames:
            columns.append(Column(table, fname))
            if fname == 'write_uid':
                hcolumns.append(Literal(transaction.user))
            elif fname == 'write_date':
                hcolumns.append(Now())
            else:
                hcolumns.append(Column(history, fname))

        def is_deleted(values):
            return all(not v for n, v in zip(fnames, values)
                if n not in ['id', 'write_uid', 'write_date'])

        to_delete = []
        to_update = []
        for id_ in ids:
            column_datetime = Coalesce(history.write_date, history.create_date)
            hwhere = (column_datetime <= datetime) & (history.id == id_)
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
            cls.__insert_history(to_delete, True)
        if to_update:
            cls.__insert_history(to_update)

    @classmethod
    def __check_timestamp(cls, ids):
        transaction = Transaction()
        cursor = transaction.cursor
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
                sql_type = fields.Numeric('timestamp').sql_type().base
                where.append((table.id == id_)
                    & (Extract('EPOCH',
                            Coalesce(table.write_date, table.create_date)
                            ).cast(sql_type) > timestamp))
            if where:
                cursor.execute(*table.select(table.id, where=where))
                if cursor.fetchone():
                    raise ConcurrencyException(
                        'Records were modified in the meanwhile')

    @classmethod
    def create(cls, vlist):
        DatabaseIntegrityError = backend.get('DatabaseIntegrityError')
        transaction = Transaction()
        cursor = transaction.cursor
        pool = Pool()
        Translation = pool.get('ir.translation')

        super(ModelSQL, cls).create(vlist)

        if cls.table_query():
            return False

        table = cls.__table__()
        modified_fields = set()
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
            for f in cls._fields.keys():
                if (f not in values
                        and f not in ('create_uid', 'create_date',
                            'write_uid', 'write_date', 'id')):
                    default.append(f)

            if default:
                defaults = cls.default_get(default, with_rec_name=False)
                values.update(cls._clean_defaults(defaults))

            insert_columns = [table.create_uid, table.create_date]
            insert_values = [transaction.user, Now()]

            # Insert record
            for fname, value in values.iteritems():
                field = cls._fields[fname]
                if not hasattr(field, 'set'):
                    insert_columns.append(Column(table, fname))
                    insert_values.append(field.sql_format(value))

            try:
                if cursor.has_returning():
                    cursor.execute(*table.insert(insert_columns,
                            [insert_values], [table.id]))
                    id_new, = cursor.fetchone()
                else:
                    id_new = cursor.nextid(cls._table)
                    if id_new:
                        insert_columns.append(table.id)
                        insert_values.append(id_new)
                        cursor.execute(*table.insert(insert_columns,
                                [insert_values]))
                    else:
                        cursor.execute(*table.insert(insert_columns,
                                [insert_values]))
                        id_new = cursor.lastid()
                new_ids.append(id_new)
            except DatabaseIntegrityError, exception:
                with Transaction().new_cursor(), \
                        Transaction().set_context(_check_access=False):
                    cls.__raise_integrity_error(exception, values)
                raise

        domain = pool.get('ir.rule').domain_get(cls.__name__,
                mode='create')
        if domain:
            for sub_ids in grouped_slice(new_ids):
                sub_ids = list(sub_ids)
                red_sql = reduce_ids(table.id, sub_ids)

                cursor.execute(*table.select(table.id,
                        where=red_sql & table.id.in_(domain)))
                if len(cursor.fetchall()) != len(sub_ids):
                    cls.raise_user_error('access_error', cls.__name__)

        transaction.create_records.setdefault(cls.__name__,
            set()).update(new_ids)

        translation_values = {}
        fields_to_set = {}
        for values, new_id in izip(vlist, new_ids):
            for fname, value in values.iteritems():
                field = cls._fields[fname]
                if (getattr(field, 'translate', False)
                        and not hasattr(field, 'set')):
                    translation_values.setdefault(
                        '%s,%s' % (cls.__name__, fname), {})[new_id] = value
                if hasattr(field, 'set'):
                    fields_to_set.setdefault(fname, []).extend(
                        ([new_id], value))

        if translation_values:
            for name, translations in translation_values.iteritems():
                Translation.set_ids(name, 'model', Transaction().language,
                    translations.keys(), translations.values())

        for fname, fargs in fields_to_set.iteritems():
            field = cls._fields[fname]
            field.set(cls, fname, *fargs)

        cls.__insert_history(new_ids)

        records = cls.browse(new_ids)
        for sub_records in grouped_slice(records, RECORD_CACHE_SIZE):
            cls._validate(sub_records)

        field_names = cls._fields.keys()
        cls._update_mptt(field_names, [new_ids] * len(field_names))

        cls.trigger_create(records)
        return records

    @classmethod
    def read(cls, ids, fields_names=None):
        pool = Pool()
        Rule = pool.get('ir.rule')
        Translation = pool.get('ir.translation')
        ModelAccess = pool.get('ir.model.access')
        if not fields_names:
            fields_names = []
            for field_name in cls._fields.keys():
                if ModelAccess.check_relation(cls.__name__, field_name,
                        mode='read'):
                    fields_names.append(field_name)
        super(ModelSQL, cls).read(ids, fields_names=fields_names)
        cursor = Transaction().cursor

        if not ids:
            return []

        # construct a clause for the rules :
        domain = Rule.domain_get(cls.__name__, mode='read')

        fields_related = {}
        datetime_fields = []
        for field_name in fields_names:
            if field_name == '_timestamp':
                continue
            if '.' in field_name:
                field, field_related = field_name.split('.', 1)
                fields_related.setdefault(field, [])
                fields_related[field].append(field_related)
            else:
                field = cls._fields[field_name]
            if hasattr(field, 'datetime_field') and field.datetime_field:
                datetime_fields.append(field.datetime_field)

        result = []
        table = cls.__table__()
        table_query = cls.table_query()

        in_max = cursor.IN_MAX
        history_order = None
        history_clause = None
        history_limit = None
        if (cls._history
                and Transaction().context.get('_datetime')
                and not table_query):
            in_max = 1
            table = cls.__table_history__()
            column = Coalesce(table.write_date, table.create_date)
            history_clause = (column <= Transaction().context['_datetime'])
            history_order = (column.desc, Column(table, '__id').desc)
            history_limit = 1

        columns = []
        for f in fields_names + fields_related.keys() + datetime_fields:
            if (f in cls._fields and not hasattr(cls._fields[f], 'set')):
                columns.append(Column(table, f).as_(f))
            elif f == '_timestamp' and not table_query:
                sql_type = fields.Char('timestamp').sql_type().base
                columns.append(Extract('EPOCH',
                        Coalesce(table.write_date, table.create_date)
                        ).cast(sql_type).as_('_timestamp'))

        if len(columns):
            if 'id' not in fields_names:
                columns.append(table.id.as_('id'))

            for sub_ids in grouped_slice(ids, in_max):
                sub_ids = list(sub_ids)
                red_sql = reduce_ids(table.id, sub_ids)
                where = red_sql
                if history_clause:
                    where &= history_clause
                if domain:
                    where &= table.id.in_(domain)
                cursor.execute(*table.select(*columns, where=where,
                        order_by=history_order, limit=history_limit))
                dictfetchall = cursor.dictfetchall()
                if not len(dictfetchall) == len({}.fromkeys(sub_ids)):
                    if domain:
                        where = red_sql
                        if history_clause:
                            where &= history_clause
                        where &= table.id.in_(domain)
                        cursor.execute(*table.select(table.id, where=where,
                                order_by=history_order, limit=history_limit))
                        rowcount = cursor.rowcount
                        if rowcount == -1 or rowcount is None:
                            rowcount = len(cursor.fetchall())
                        if rowcount == len({}.fromkeys(sub_ids)):
                            cls.raise_user_error('access_error', cls.__name__)
                    cls.raise_user_error('read_error', cls.__name__)
                result.extend(dictfetchall)
        else:
            result = [{'id': x} for x in ids]

        for column in columns:
            field = column.output_name
            if field == '_timestamp':
                continue
            if (getattr(cls._fields[field], 'translate', False)
                    and not hasattr(field, 'set')):
                translations = Translation.get_ids(cls.__name__ + ',' + field,
                    'model', Transaction().language, ids)
                for row in result:
                    row[field] = translations.get(row['id']) or row[field]

        # all fields for which there is a get attribute
        getter_fields = [f for f in
            fields_names + fields_related.keys() + datetime_fields
            if f in cls._fields and hasattr(cls._fields[f], 'get')]
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

        to_del = set()
        fields_related2values = {}
        for fname in fields_related.keys() + datetime_fields:
            if fname not in fields_names:
                to_del.add(fname)
            if fname not in cls._fields:
                continue
            if fname not in fields_related:
                continue
            fields_related2values.setdefault(fname, {})
            field = cls._fields[fname]
            if field._type in ('many2one', 'one2one'):
                if hasattr(field, 'model_name'):
                    Target = pool.get(field.model_name)
                else:
                    Target = field.get_target()
                if getattr(field, 'datetime_field', None):
                    for row in result:
                        if row[fname] is None:
                            continue
                        with Transaction().set_context(
                                _datetime=row[field.datetime_field]):
                            date_target, = Target.read([row[fname]],
                                fields_related[fname])
                        target_id = date_target.pop('id')
                        fields_related2values[fname].setdefault(target_id, {})
                        fields_related2values[
                            fname][target_id][row['id']] = date_target
                else:
                    for target in Target.read(
                            [r[fname] for r in result if r[fname]],
                            fields_related[fname]):
                        target_id = target.pop('id')
                        fields_related2values[fname].setdefault(target_id, {})
                        for row in result:
                            fields_related2values[
                                fname][target_id][row['id']] = target
            elif field._type == 'reference':
                for row in result:
                    if not row[fname]:
                        continue
                    model_name, record_id = row[fname].split(',', 1)
                    if not model_name:
                        continue
                    record_id = int(record_id)
                    if record_id < 0:
                        continue
                    Target = pool.get(model_name)
                    target, = Target.read([record_id], fields_related[fname])
                    del target['id']
                    fields_related2values[fname][row[fname]] = target

        if to_del or fields_related or datetime_fields:
            for row in result:
                for fname in fields_related:
                    if fname not in cls._fields:
                        continue
                    field = cls._fields[fname]
                    for related in fields_related[fname]:
                        related_name = '%s.%s' % (fname, related)
                        value = None
                        if row[fname]:
                            if field._type in ('many2one', 'one2one'):
                                value = fields_related2values[fname][
                                    row[fname]][row['id']][related]
                            elif field._type == 'reference':
                                model_name, record_id = row[fname
                                    ].split(',', 1)
                                if model_name:
                                    record_id = int(record_id)
                                    if record_id >= 0:
                                        value = fields_related2values[fname][
                                            row[fname]][related]
                        row[related_name] = value
                for field in to_del:
                    del row[field]

        return result

    @classmethod
    def write(cls, records, values, *args):
        DatabaseIntegrityError = backend.get('DatabaseIntegrityError')
        transaction = Transaction()
        cursor = transaction.cursor
        pool = Pool()
        Translation = pool.get('ir.translation')
        Config = pool.get('ir.configuration')

        assert not len(args) % 2
        all_records = sum(((records, values) + args)[0:None:2], [])
        all_ids = [r.id for r in all_records]
        all_field_names = set()

        # Call before cursor cache cleaning
        trigger_eligibles = cls.trigger_write_get_eligibles(all_records)

        super(ModelSQL, cls).write(records, values, *args)

        if cls.table_query():
            return
        table = cls.__table__()

        cls.__check_timestamp(all_ids)

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
            update_values = [transaction.user, Now()]
            store_translation = Transaction().language == Config.get_language()
            for fname, value in values.iteritems():
                field = cls._fields[fname]
                if not hasattr(field, 'set'):
                    if (not getattr(field, 'translate', False)
                            or store_translation):
                        columns.append(Column(table, fname))
                        update_values.append(field.sql_format(value))

            domain = pool.get('ir.rule').domain_get(cls.__name__, mode='write')
            for sub_ids in grouped_slice(ids):
                sub_ids = list(sub_ids)
                red_sql = reduce_ids(table.id, sub_ids)
                where = red_sql
                if domain:
                    where &= table.id.in_(domain)
                cursor.execute(*table.select(table.id, where=where))
                rowcount = cursor.rowcount
                if rowcount == -1 or rowcount is None:
                    rowcount = len(cursor.fetchall())
                if not rowcount == len({}.fromkeys(sub_ids)):
                    if domain:
                        cursor.execute(*table.select(table.id, where=red_sql))
                        rowcount = cursor.rowcount
                        if rowcount == -1 or rowcount is None:
                            rowcount = len(cursor.fetchall())
                        if rowcount == len({}.fromkeys(sub_ids)):
                            cls.raise_user_error('access_error', cls.__name__)
                    cls.raise_user_error('write_error', cls.__name__)
                try:
                    cursor.execute(*table.update(columns, update_values,
                            where=red_sql))
                except DatabaseIntegrityError, exception:
                    with Transaction().new_cursor(), \
                            Transaction().set_context(_check_access=False):
                        cls.__raise_integrity_error(exception, values,
                            values.keys())
                    raise

            for fname, value in values.iteritems():
                field = cls._fields[fname]
                if (getattr(field, 'translate', False)
                        and not hasattr(field, 'set')):
                    Translation.set_ids(
                        '%s,%s' % (cls.__name__, fname), 'model',
                        transaction.language, ids, [value] * len(ids))
                if hasattr(field, 'set'):
                    fields_to_set.setdefault(fname, []).extend((ids, value))

            field_names = values.keys()
            cls._update_mptt(field_names, [ids] * len(field_names), values)
            all_field_names |= set(field_names)

        for fname, fargs in fields_to_set.iteritems():
            field = cls._fields[fname]
            field.set(cls, fname, *fargs)

        cls.__insert_history(all_ids)
        for sub_records in grouped_slice(all_records, RECORD_CACHE_SIZE):
            cls._validate(sub_records, field_names=all_field_names)
        cls.trigger_write(trigger_eligibles)

    @classmethod
    def delete(cls, records):
        DatabaseIntegrityError = backend.get('DatabaseIntegrityError')
        transaction = Transaction()
        cursor = transaction.cursor
        pool = Pool()
        Translation = pool.get('ir.translation')
        ids = map(int, records)

        if not ids:
            return

        if cls.table_query():
            return
        table = cls.__table__()

        if transaction.delete and transaction.delete.get(cls.__name__):
            ids = ids[:]
            for del_id in transaction.delete[cls.__name__]:
                for i in range(ids.count(del_id)):
                    ids.remove(del_id)

        cls.__check_timestamp(ids)

        tree_ids = {}
        for fname, field in cls._fields.iteritems():
            if (isinstance(field, fields.Many2One)
                    and field.model_name == cls.__name__
                    and field.left and field.right):
                tree_ids[fname] = []
                for sub_ids in grouped_slice(ids):
                    where = reduce_ids(Column(table, fname), sub_ids)
                    cursor.execute(*table.select(table.id, where=where))
                    tree_ids[fname] += [x[0] for x in cursor.fetchall()]

        foreign_keys_tocheck = []
        foreign_keys_toupdate = []
        foreign_keys_todelete = []
        for _, model in pool.iterobject():
            if hasattr(model, 'table_query') and model.table_query():
                continue
            if not issubclass(model, ModelStorage):
                continue
            for field_name, field in model._fields.iteritems():
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

        domain = pool.get('ir.rule').domain_get(cls.__name__, mode='delete')

        if domain:
            for sub_ids in grouped_slice(ids):
                sub_ids = list(sub_ids)
                red_sql = reduce_ids(table.id, sub_ids)
                cursor.execute(*table.select(table.id,
                        where=red_sql & table.id.in_(domain)))
                rowcount = cursor.rowcount
                if rowcount == -1 or rowcount is None:
                    rowcount = len(cursor.fetchall())
                if not rowcount == len({}.fromkeys(sub_ids)):
                    cls.raise_user_error('access_error', cls._get_name())

        cls.trigger_delete(records)

        for sub_ids, sub_records in izip(
                grouped_slice(ids), grouped_slice(records)):
            sub_ids = list(sub_ids)
            red_sql = reduce_ids(table.id, sub_ids)

            transaction.delete_records.setdefault(cls.__name__,
                set()).update(sub_ids)

            for Model, field_name in foreign_keys_toupdate:
                if (not hasattr(Model, 'search')
                        or not hasattr(Model, 'write')):
                    continue
                foreign_table = Model.__table__()
                foreign_red_sql = reduce_ids(
                    Column(foreign_table, field_name), sub_ids)
                cursor.execute(*foreign_table.select(foreign_table.id,
                        where=foreign_red_sql))
                models = Model.browse([x[0] for x in cursor.fetchall()])
                if models:
                    Model.write(models, {
                            field_name: None,
                            })

            for Model, field_name in foreign_keys_todelete:
                if (not hasattr(Model, 'search')
                        or not hasattr(Model, 'delete')):
                    continue
                foreign_table = Model.__table__()
                foreign_red_sql = reduce_ids(
                    Column(foreign_table, field_name), sub_ids)
                cursor.execute(*foreign_table.select(foreign_table.id,
                        where=foreign_red_sql))
                models = Model.browse([x[0] for x in cursor.fetchall()])
                if models:
                    Model.delete(models)

            for Model, field_name in foreign_keys_tocheck:
                with Transaction().set_context(_check_access=False):
                    if Model.search([
                                (field_name, 'in', sub_ids),
                                ], order=[]):
                        error_args = Model._get_error_args(field_name)
                        cls.raise_user_error('foreign_model_exist',
                            error_args=error_args)

            super(ModelSQL, cls).delete(list(sub_records))

            try:
                cursor.execute(*table.delete(where=red_sql))
            except DatabaseIntegrityError, exception:
                with Transaction().new_cursor():
                    cls.__raise_integrity_error(exception, {})
                raise

        Translation.delete_ids(cls.__name__, 'model', ids)

        cls.__insert_history(ids, deleted=True)

        cls._update_mptt(tree_ids.keys(), tree_ids.values())

    @classmethod
    def search(cls, domain, offset=0, limit=None, order=None, count=False,
            query=False):
        pool = Pool()
        Rule = pool.get('ir.rule')
        transaction = Transaction()
        cursor = transaction.cursor

        # Get domain clauses
        tables, expression = cls.search_domain(domain)

        # Get order by
        order_by = []
        order_types = {
            'DESC': Desc,
            'ASC': Asc,
            }
        if order is None or order is False:
            order = cls._order
        for fname, otype in order:
            field = cls._fields[fname]
            Order = order_types[otype.upper()]
            forder = field.convert_order(fname, tables, cls)
            order_by.extend((Order(o) for o in forder))

        main_table, _ = tables[None]

        def convert_from(table, tables):
            right, condition = tables[None]
            if table:
                table = table.join(right, 'LEFT', condition)
            else:
                table = right
            for k, sub_tables in tables.iteritems():
                if k is None:
                    continue
                table = convert_from(table, sub_tables)
            return table
        # Don't nested joins as SQLite doesn't support
        table = convert_from(None, tables)

        # construct a clause for the rules :
        domain = Rule.domain_get(cls.__name__, mode='read')
        if domain:
            expression &= main_table.id.in_(domain)

        if count:
            cursor.execute(*table.select(Count(Literal(1)),
                    where=expression, limit=limit, offset=offset))
            return cursor.fetchone()[0]
        # execute the "main" query to fetch the ids we were searching for
        columns = [main_table.id.as_('id')]
        if (cls._history and transaction.context.get('_datetime')
                and not query):
            columns.append(Coalesce(
                    main_table.write_date,
                    main_table.create_date).as_('_datetime'))
            columns.append(Column(main_table, '__id'))
        if not query:
            columns += [Column(main_table, name).as_(name)
                for name, field in cls._fields.iteritems()
                if not hasattr(field, 'get')
                and name != 'id'
                and not getattr(field, 'translate', False)
                and field.loading == 'eager']
            if not cls.table_query():
                sql_type = fields.Char('timestamp').sql_type().base
                columns += [Extract('EPOCH',
                        Coalesce(main_table.write_date, main_table.create_date)
                        ).cast(sql_type).as_('_timestamp')]
        select = table.select(*columns,
            where=expression, order_by=order_by, limit=limit, offset=offset)
        if query:
            return select
        cursor.execute(*select)

        rows = cursor.dictfetchmany(cursor.IN_MAX)
        cache = cursor.get_cache()
        if cls.__name__ not in cache:
            cache[cls.__name__] = LRUDict(RECORD_CACHE_SIZE)
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
                cursor.execute(*history.select(history.id, history.write_date,
                        where=where
                        & (history.write_date != None)
                        & (history.create_date == None)
                        & (history.write_date
                            <= transaction.context['_datetime'])))
                for deleted_id, delete_date in cursor.fetchall():
                    history_date, _ = ids_history[deleted_id]
                    if isinstance(history_date, basestring):
                        strptime = datetime.datetime.strptime
                        format_ = '%Y-%m-%d %H:%M:%S.%f'
                        history_date = strptime(history_date, format_)
                    if history_date <= delete_date:
                        to_delete.add(deleted_id)

            return ifilter(lambda r: history_key(r) == ids_history[r['id']]
                and r['id'] not in to_delete, rows)

        # Can not cache the history value if we are not sure to have fetch all
        # the rows for each records
        if (not (cls._history and transaction.context.get('_datetime'))
                or len(rows) < cursor.IN_MAX):
            rows = list(filter_history(rows))
            keys = None
            for data in islice(rows, 0, cache.size_limit):
                if data['id'] in delete_records:
                    continue
                if keys is None:
                    keys = data.keys()
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

        if len(rows) >= cursor.IN_MAX:
            if (cls._history
                    and Transaction().context.get('_datetime')
                    and not query):
                columns = columns[:3]
            else:
                columns = columns[:1]
            cursor.execute(*table.select(*columns,
                    where=expression, order_by=order_by,
                    limit=limit, offset=offset))
            rows = filter_history(cursor.dictfetchall())

        return cls.browse([x['id'] for x in rows])

    @classmethod
    def search_domain(cls, domain, active_test=True):
        '''
        Return SQL tables and expression
        Set active_test to add it.
        '''
        transaction = Transaction()
        domain = cls._search_domain_active(domain, active_test=active_test)

        tables = {
            None: (cls.__table__(), None)
            }
        if cls._history and transaction.context.get('_datetime'):
            tables[None] = (cls.__table_history__(), None)

        def is_leaf(expression):
            return (isinstance(expression, (list, tuple))
                and len(expression) > 2
                and isinstance(expression[1], basestring)
                and expression[1] in OPERATORS)  # TODO remove OPERATORS test

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
        cursor = Transaction().cursor
        count = None
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
                        & (Column(parent, field.right) == 0)))
                nested_create = cursor.fetchone()

                if count is None:
                    cursor.execute(*table.select(Count(Literal(1))))
                    count, = cursor.fetchone()

                if not nested_create and len(ids) < count / 4:
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
        cursor = Transaction().cursor
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
        cursor = Transaction().cursor
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
                    where=field == None))
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
            cursor.execute(*table.select(Max(right), where=field == None))
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
        cursor = Transaction().cursor
        if cursor.has_constraint():
            return
        # Works only for a single transaction
        ids = map(int, records)
        table = cls.__table__()
        param = Flavor.get().param
        for _, sql, error in cls._sql_constraints:
            match = _RE_UNIQUE.match(sql)
            if match:
                sql = match.group(1)
                columns = sql.split(',')
                sql_clause = ' AND '.join('%s = %s'
                    % (i, param) for i in columns)
                sql_clause = '(id != ' + param + ' AND ' + sql_clause + ')'

                in_max = cursor.IN_MAX / (len(columns) + 1)
                for sub_ids in grouped_slice(ids, in_max):
                    red_sql = reduce_ids(table.id, sub_ids)

                    cursor.execute('SELECT id,' + sql + ' '
                        'FROM "' + cls._table + '" '
                        'WHERE ' + str(red_sql), red_sql.params)

                    fetchall = cursor.fetchall()
                    cursor.execute('SELECT id '
                        'FROM "' + cls._table + '" '
                        'WHERE ' +
                            ' OR '.join((sql_clause,) * len(fetchall)),
                        reduce(lambda x, y: x + list(y), fetchall, []))

                    if cursor.fetchone():
                        cls.raise_user_error(error)
                continue
            match = _RE_CHECK.match(sql)
            if match:
                sql = match.group(1)
                for sub_ids in grouped_slice(ids):
                    red_sql = reduce_ids(table.id, sub_ids)
                    cursor.execute('SELECT id '
                        'FROM "' + cls._table + '" '
                        'WHERE NOT (' + sql + ') '
                            'AND ' + str(red_sql), red_sql.params)
                    if cursor.fetchone():
                        cls.raise_user_error(error)
                    continue
