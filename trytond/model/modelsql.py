#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import contextlib
import datetime
import re
from functools import reduce
from decimal import Decimal
from itertools import islice, izip

from trytond.model import ModelStorage
from trytond.model import fields
from trytond.backend import FIELDS, TableHandler
from trytond.backend import DatabaseIntegrityError
from trytond.tools import reduce_ids
from trytond.const import OPERATORS, RECORD_CACHE_SIZE
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.cache import LRUDict
from trytond.exceptions import ConcurrencyException
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

        if not cls._table:
            cls._table = cls.__name__.replace('.', '_')

        assert cls._table[-9:] != '__history', \
            'Model _table %s cannot end with "__history"' % cls._table

    @classmethod
    def __register__(cls, module_name):
        super(ModelSQL, cls).__register__(module_name)

        if cls.table_query():
            return

        pool = Pool()

        # create/update table in the database
        table = TableHandler(Transaction().cursor, cls, module_name)
        if cls._history:
            history_table = TableHandler(Transaction().cursor, cls,
                    module_name, history=True)
        timestamp_field = FIELDS['timestamp']
        integer_field = FIELDS['integer']
        logs = (
            ('create_date', timestamp_field.sql_type(None),
                timestamp_field.sql_format, lambda *a: datetime.datetime.now(),
                cls.create_date.string),
            ('write_date', timestamp_field.sql_type(None),
                timestamp_field.sql_format, None, cls.write_date.string),
            ('create_uid', (integer_field.sql_type(None)[0],
             'INTEGER REFERENCES res_user ON DELETE SET NULL',),
             integer_field.sql_format, lambda *a: 0, cls.create_uid.string),
            ('write_uid', (integer_field.sql_type(None)[0],
             'INTEGER REFERENCES res_user ON DELETE SET NULL'),
             integer_field.sql_format, None, cls.write_uid.string),
            )
        for log in logs:
            table.add_raw_column(log[0], log[1], log[2],
                    default_fun=log[3], migrate=False, string=log[4])
        if cls._history:
            history_logs = (
                    ('create_date', timestamp_field.sql_type(None),
                        timestamp_field.sql_format, cls.create_date.string),
                    ('write_date', timestamp_field.sql_type(None),
                        timestamp_field.sql_format, cls.write_date.string),
                    ('create_uid', (integer_field.sql_type(None)[0],
                     'INTEGER REFERENCES res_user ON DELETE SET NULL',),
                     integer_field.sql_format, cls.create_uid.string),
                    ('write_uid', (integer_field.sql_type(None)[0],
                     'INTEGER REFERENCES res_user ON DELETE SET NULL'),
                     integer_field.sql_format, cls.write_uid.string),
                    )
            for log in history_logs:
                history_table.add_raw_column(log[0], log[1], log[2],
                        migrate=False, string=log[3])
            history_table.index_action('id', action='add')

        for field_name, field in cls._fields.iteritems():
            default_fun = None
            if field_name in (
                    'id',
                    'write_uid',
                    'write_date',
                    'create_uid',
                    'create_date',
                    'rec_name',
                    ):
                continue

            if not hasattr(field, 'set'):
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
                table.add_raw_column(field_name,
                        FIELDS[field._type].sql_type(field),
                        FIELDS[field._type].sql_format, default_fun,
                        field_size, string=field.string)
                if cls._history:
                    history_table.add_raw_column(field_name,
                            FIELDS[field._type].sql_type(field), None,
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

            elif not isinstance(field, (fields.One2Many, fields.Function,
                        fields.Many2Many)):
                raise Exception('Unknow field type !')

        for field_name, field in cls._fields.iteritems():
            if isinstance(field, fields.Many2One) \
                    and field.model_name == cls.__name__ \
                    and field.left and field.right:
                with Transaction().set_user(0):
                    cls._rebuild_tree(field_name, False, 0)

        for ident, constraint, _ in cls._sql_constraints:
            table.add_constraint(ident, constraint)

        if cls._history:
            cls._update_history_table()
            cursor = Transaction().cursor
            cursor.execute('SELECT id FROM "' + cls._table + '"')
            if cursor.fetchone():
                cursor.execute('SELECT id FROM "' + cls._table + '__history"')
                if not cursor.fetchone():
                    columns = ['"' + str(x) + '"' for x in cls._fields
                            if not hasattr(cls._fields[x], 'set')]
                    cursor.execute('INSERT INTO "' + cls._table + '__history" '
                        '(' + ','.join(columns) + ') '
                        'SELECT ' + ','.join(columns) +
                        ' FROM "' + cls._table + '"')
                    cursor.execute('UPDATE "' + cls._table + '__history" '
                        'SET write_date = NULL')

    @classmethod
    def _update_history_table(cls):
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
        '''
        Return None if the model is a real table in the database
        or return a tuple with the SQL query and the arguments.
        '''
        return None

    @classmethod
    def create(cls, vlist):
        super(ModelSQL, cls).create(vlist)
        cursor = Transaction().cursor
        pool = Pool()

        if cls.table_query():
            return False

        modified_fields = set()
        new_ids = []
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            # Clean values
            for key in ('create_uid', 'create_date', 'write_uid', 'write_date',
                    'id'):
                if key in values:
                    del values[key]
            modified_fields |= set(values.keys())

            # Get default values
            default = []
            for i in cls._fields.keys():
                if not i in values \
                        and i not in ('create_uid', 'create_date',
                                'write_uid', 'write_date'):
                    default.append(i)

            if len(default):
                defaults = cls.default_get(default, with_rec_name=False)
                for field in defaults.keys():
                    if '.' in field:
                        del defaults[field]
                    if field in ('create_uid', 'create_date',
                            'write_uid', 'write_date'):
                        del defaults[field]
                    if field in values:
                        del defaults[field]
                values.update(cls._clean_defaults(defaults))

            (upd0, upd1, upd2) = ('', '', [])

            # Insert record
            for fname, value in values.iteritems():
                field = cls._fields[fname]
                if not hasattr(field, 'set'):
                    upd0 = upd0 + ',"' + fname + '"'
                    upd1 = upd1 + ', %s'
                    upd2.append(FIELDS[field._type].sql_format(value))
            upd0 += ', create_uid, create_date'
            upd1 += ', %s, %s'
            upd2.append(Transaction().user)
            upd2.append(datetime.datetime.now())

            try:
                if cursor.has_returning():
                    cursor.execute('INSERT INTO "' + cls._table + '" '
                        '(' + upd0[1:] + ') '
                        'VALUES (' + upd1[1:] + ') RETURNING id',
                        tuple(upd2))
                    id_new, = cursor.fetchone()
                else:
                    id_new = cursor.nextid(cls._table)
                    if id_new:
                        cursor.execute('INSERT INTO "' + cls._table + '" '
                            '(id' + upd0 + ') '
                            'VALUES (' + str(id_new) + upd1 + ')',
                            tuple(upd2))
                    else:
                        cursor.execute('INSERT INTO "' + cls._table + '" '
                            '(' + upd0[1:] + ') '
                            'VALUES (' + upd1[1:] + ')',
                            tuple(upd2))
                        id_new = cursor.lastid()
                new_ids.append(id_new)
            except DatabaseIntegrityError, exception:
                with contextlib.nested(Transaction().new_cursor(),
                        Transaction().set_user(0)):
                    for field_name in cls._fields:
                        field = cls._fields[field_name]
                        # Check required fields
                        if (field.required
                                and not hasattr(field, 'set')
                                and field_name not in (
                                    'create_uid', 'create_date')):
                            if values.get(field_name) is None:
                                cls.raise_user_error('required_field',
                                        error_args=cls._get_error_args(
                                            field_name))
                        if isinstance(field, fields.Many2One) \
                                and values.get(field_name):
                            Model = pool.get(field.model_name)
                            create_records = Transaction().create_records.get(
                                    field.model_name, set())
                            delete_records = Transaction().delete_records.get(
                                    field.model_name, set())
                            if not ((Model.search([
                                                ('id', '=',
                                                    values[field_name]),
                                                ], order=[])
                                        or values[field_name] in
                                        create_records)
                                    and values[field_name] not in
                                    delete_records):
                                cls.raise_user_error('foreign_model_missing',
                                        error_args=cls._get_error_args(
                                            field_name))
                    for name, _, error in cls._sql_constraints:
                        if name in exception[0]:
                            cls.raise_user_error(error)
                    for name, error in cls._sql_error_messages.iteritems():
                        if name in exception[0]:
                            cls.raise_user_error(error)
                raise

        domain1, domain2 = pool.get('ir.rule').domain_get(cls.__name__,
                mode='create')
        if domain1:
            in_max = Transaction().cursor.IN_MAX
            for i in range(0, len(new_ids), in_max):
                sub_ids = new_ids[i:i + in_max]
                red_sql, red_ids = reduce_ids('id', sub_ids)

                cursor.execute('SELECT id FROM "' + cls._table + '" WHERE ' +
                        red_sql + ' AND (' + domain1 + ')', red_ids + domain2)
                if len(cursor.fetchall()) != len(sub_ids):
                    cls.raise_user_error('access_error', cls.__name__)

        create_records = Transaction().create_records.setdefault(cls.__name__,
            set()).update(new_ids)

        for values, new_id in izip(vlist, new_ids):
            for fname, value in values.iteritems():
                field = cls._fields[fname]
                if getattr(field, 'translate', False):
                        pool.get('ir.translation').set_ids(
                                cls.__name__ + ',' + fname, 'model',
                                Transaction().language, [new_id], value)
                if hasattr(field, 'set'):
                    field.set([new_id], cls, fname, value)

        if cls._history:
            columns = ['"' + str(x) + '"' for x in cls._fields
                if not hasattr(cls._fields[x], 'set')]
            columns = ','.join(columns)
            for i in range(0, len(new_ids), cursor.IN_MAX):
                sub_ids = new_ids[i:i + cursor.IN_MAX]
                red_sql, red_ids = reduce_ids('id', sub_ids)
                cursor.execute('INSERT INTO "' + cls._table + '__history" '
                    '(' + columns + ') '
                    'SELECT ' + columns + ' '
                    'FROM "' + cls._table + '" '
                    'WHERE ' + red_sql, red_ids)

        records = cls.browse(new_ids)
        cls._validate(records)

        # Check for Modified Preorder Tree Traversal
        for k in cls._fields:
            field = cls._fields[k]
            if (isinstance(field, fields.Many2One)
                    and field.model_name == cls.__name__
                    and field.left and field.right):
                if len(new_ids) == 1:
                    cls._update_tree(new_ids[0], k, field.left, field.right)
                else:
                    with Transaction().set_user(0):
                        cls._rebuild_tree(k, False, 0)

        cls.trigger_create(records)
        return records

    @classmethod
    def read(cls, ids, fields_names=None):
        pool = Pool()
        Rule = pool.get('ir.rule')
        Translation = pool.get('ir.translation')
        super(ModelSQL, cls).read(ids, fields_names=fields_names)
        cursor = Transaction().cursor

        if not fields_names:
            fields_names = cls._fields.keys()

        if not ids:
            return []

        # construct a clause for the rules :
        domain1, domain2 = Rule.domain_get(cls.__name__, mode='read')

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

        fields_pre = [x
            for x in fields_names + fields_related.keys() + datetime_fields
            if (x in cls._fields and not hasattr(cls._fields[x], 'set'))
            or (x == '_timestamp')]

        res = []
        table_query = ''
        table_args = []

        if cls.table_query():
            table_query, table_args = cls.table_query()
            table_query = '(' + table_query + ') AS '

        in_max = cursor.IN_MAX
        history_order = ''
        history_clause = ''
        history_limit = ''
        history_args = []
        if (cls._history
                and Transaction().context.get('_datetime')
                and not table_query):
            in_max = 1
            table_query = '"' + cls._table + '__history" AS '
            history_clause = ' AND (COALESCE(write_date, create_date) <= %s)'
            history_order = ' ORDER BY COALESCE(write_date, create_date) DESC'
            history_limit = cursor.limit_clause('', 1)
            history_args = [Transaction().context['_datetime']]
        if len(fields_pre):
            fields_pre2 = ['"%s"."%s" AS "%s"' % (cls._table, x, x)
                    for x in fields_pre if x != '_timestamp']
            if '_timestamp' in fields_pre:
                if not cls.table_query():
                    fields_pre2 += ['CAST(EXTRACT(EPOCH FROM '
                            '(COALESCE("%s".write_date, "%s".create_date))) '
                            'AS VARCHAR) AS _timestamp' %
                            (cls._table, cls._table)]
            if 'id' not in fields_pre:
                fields_pre2 += ['"%s".id AS id' % cls._table]

            for i in range(0, len(ids), in_max):
                sub_ids = ids[i:i + in_max]
                red_sql, red_ids = reduce_ids('id', sub_ids)
                if domain1:
                    cursor.execute('SELECT ' + ','.join(fields_pre2)
                        + ' FROM ' + table_query + '\"' + cls._table + '\" '
                        'WHERE ' + red_sql + history_clause +
                            ' AND (' + domain1 + ') '
                        + history_order
                        + history_limit,
                        table_args + red_ids + history_args + domain2)
                else:
                    cursor.execute('SELECT ' + ','.join(fields_pre2)
                        + ' FROM ' + table_query + '\"' + cls._table + '\" '
                        'WHERE ' + red_sql + history_clause
                        + history_order
                        + history_limit,
                        table_args + red_ids + history_args)
                dictfetchall = cursor.dictfetchall()
                if not len(dictfetchall) == len({}.fromkeys(sub_ids)):
                    if domain1:
                        cursor.execute('SELECT id '
                            'FROM ' + table_query + '\"' + cls._table + '\" '
                            'WHERE ' + red_sql + history_clause
                            + history_order
                            + history_limit,
                            table_args + red_ids + history_args)
                        rowcount = cursor.rowcount
                        if rowcount == -1 or rowcount is None:
                            rowcount = len(cursor.fetchall())
                        if rowcount == len({}.fromkeys(sub_ids)):
                            cls.raise_user_error('access_error', cls.__name__)
                    cls.raise_user_error('read_error', cls.__name__)
                res.extend(dictfetchall)
        else:
            res = [{'id': x} for x in ids]

        for field in fields_pre:
            if field == '_timestamp':
                continue
            if getattr(cls._fields[field], 'translate', False):
                ids = [x['id'] for x in res]
                res_trans = Translation.get_ids(cls.__name__ + ',' + field,
                    'model', Transaction().language, ids)
                for i in res:
                    i[field] = res_trans.get(i['id'], False) or i[field]

        ids = [x['id'] for x in res]

        # all fields for which there is a get attribute
        fields_post = [x for x in
            fields_names + fields_related.keys() + datetime_fields
            if x in cls._fields and hasattr(cls._fields[x], 'get')]
        func_fields = {}
        for field in fields_post:
            if isinstance(cls._fields[field], fields.Function):
                key = (cls._fields[field].getter,
                    getattr(cls._fields[field], 'datetime_field', None))
                func_fields.setdefault(key, [])
                func_fields[key].append(field)
                continue
            if hasattr(cls._fields[field], 'datetime_field') \
                    and cls._fields[field].datetime_field:
                for record in res:
                    with Transaction().set_context(_datetime=record[
                                cls._fields[field].datetime_field]):
                        res2 = cls._fields[field].get([record['id']], cls,
                            field, values=[record])
                    record[field] = res2[record['id']]
                continue
            # get the value of that field for all records/ids
            res2 = cls._fields[field].get(ids, cls, field, values=res)
            for record in res:
                record[field] = res2[record['id']]
        for key in func_fields:
            field_list = func_fields[key]
            field = field_list[0]
            _, datetime_field = key
            if datetime_field:
                for record in res:
                    with Transaction().set_context(
                            _datetime=record[datetime_field]):
                        res2 = cls._fields[field].get([record['id']], cls,
                                field_list, values=[record])
                    for field in res2:
                        record[field] = res2[field][record['id']]
                continue
            res2 = cls._fields[field].get(ids, cls, field_list, values=res)
            for field in res2:
                for record in res:
                    record[field] = res2[field][record['id']]

        to_del = set()
        fields_related2values = {}
        for field in fields_related.keys() + datetime_fields:
            if field not in fields_names:
                to_del.add(field)
            if field not in cls._fields:
                continue
            if field not in fields_related.keys():
                continue
            fields_related2values.setdefault(field, {})
            if cls._fields[field]._type in ('many2one', 'one2one'):
                if hasattr(cls._fields[field], 'model_name'):
                    obj = pool.get(cls._fields[field].model_name)
                else:
                    obj = cls._fields[field].get_target()
                if hasattr(cls._fields[field], 'datetime_field') \
                        and cls._fields[field].datetime_field:
                    for record in res:
                        if record[field] is None:
                            continue
                        with Transaction().set_context(_datetime=record[
                                    cls._fields[field].datetime_field]):
                            record2, = obj.read([record[field]],
                                    fields_related[field])
                        record_id = record2['id']
                        del record2['id']
                        fields_related2values[field].setdefault(record_id, {})
                        fields_related2values[
                                field][record_id][record['id']] = record2
                else:
                    for record in obj.read([x[field] for x in res
                                if x[field]], fields_related[field]):
                        record_id = record['id']
                        del record['id']
                        fields_related2values[field].setdefault(record_id, {})
                        for record2 in res:
                            fields_related2values[
                                field][record_id][record2['id']] = record
            elif cls._fields[field]._type == 'reference':
                for record in res:
                    if not record[field]:
                        continue
                    model_name, record_id = record[field].split(',', 1)
                    if not model_name:
                        continue
                    record_id = int(record_id)
                    if record_id < 0:
                        continue
                    obj = pool.get(model_name)
                    record2, = obj.read([record_id], fields_related[field])
                    del record2['id']
                    fields_related2values[field][record[field]] = record2

        if to_del or fields_related.keys() or datetime_fields:
            for record in res:
                for field in fields_related.keys():
                    if field not in cls._fields:
                        continue
                    for related in fields_related[field]:
                        if cls._fields[field]._type in (
                                'many2one', 'one2one'):
                            if record[field]:
                                record[field + '.' + related] = (
                                    fields_related2values[field][
                                        record[field]][record['id']][related])
                            else:
                                record[field + '.' + related] = False
                        elif cls._fields[field]._type == 'reference':
                            if record[field]:
                                model_name, record_id = record[field].split(
                                        ',', 1)
                                if not model_name:
                                    continue
                                record_id = int(record_id)
                                if record_id < 0:
                                    continue
                                record[field + '.' + related] = \
                                    fields_related2values[field][
                                        record[field]][related]
                for field in to_del:
                    del record[field]

        return res

    @classmethod
    def write(cls, records, values):
        cursor = Transaction().cursor
        pool = Pool()
        Translation = pool.get('ir.translation')
        Config = pool.get('ir.configuration')
        ids = map(int, records)

        # Call before cursor cache cleaning
        trigger_eligibles = cls.trigger_write_get_eligibles(records)

        super(ModelSQL, cls).write(records, values)

        if not records:
            return True

        if cls.table_query():
            return True

        values = values.copy()

        # _update_tree works if only one record has changed
        update_tree = False
        for k in cls._fields:
            field = cls._fields[k]
            if isinstance(field, fields.Many2One) \
                    and field.model_name == cls.__name__ \
                    and field.left and field.right:
                update_tree = True
        if update_tree and len(records) > 1:
            for record in records:
                cls.write([record], values)
            return True

        if Transaction().timestamp:
            for i in range(0, len(ids), cursor.IN_MAX):
                sub_ids = ids[i:i + cursor.IN_MAX]
                clause = ('(id = %s AND '
                    'CAST(EXTRACT(EPOCH FROM '
                    'COALESCE(write_date, create_date)) AS ' +
                    FIELDS['numeric'].sql_type(cls.create_date)[1] +
                    ') > %s)')
                args = []
                for i in sub_ids:
                    if Transaction().timestamp.get(
                            cls.__name__ + ',' + str(i)):
                        args.append(i)
                        args.append(Decimal(Transaction().timestamp[
                            cls.__name__ + ',' + str(i)]))
                if args:
                    cursor.execute("SELECT id "
                        'FROM "' + cls._table + '" '
                        'WHERE ' + ' OR '.join(
                            (clause,) * (len(args) // 2)), args)
                    if cursor.fetchone():
                        raise ConcurrencyException(
                            'Records were modified in the meanwhile')
            for i in ids:
                if Transaction().timestamp.get(cls.__name__ + ',' + str(i)):
                    del Transaction().timestamp[cls.__name__ + ',' + str(i)]

        # Clean values
        for key in ('create_uid', 'create_date', 'write_uid', 'write_date',
                'id'):
            if key in values:
                del values[key]

        upd0 = []
        upd1 = []
        upd_todo = []
        direct = []
        for field in values:
            if not hasattr(cls._fields[field], 'set'):
                if ((not getattr(cls._fields[field], 'translate', False))
                        or (Transaction().language == Config.get_language())):
                    upd0.append(('"' + field + '"', '%s'))
                    upd1.append(FIELDS[cls._fields[field]._type]
                        .sql_format(values[field]))
                direct.append(field)
            else:
                upd_todo.append(field)

        upd0.append(('write_uid', '%s'))
        upd0.append(('write_date', '%s'))
        upd1.append(Transaction().user)
        upd1.append(datetime.datetime.now())

        domain1, domain2 = pool.get('ir.rule').domain_get(cls.__name__,
                mode='write')
        if domain1:
            domain1 = ' AND (' + domain1 + ') '
        for i in range(0, len(ids), cursor.IN_MAX):
            sub_ids = ids[i:i + cursor.IN_MAX]
            red_sql, red_ids = reduce_ids('id', sub_ids)
            if domain1:
                cursor.execute('SELECT id FROM "' + cls._table + '" '
                    'WHERE ' + red_sql + ' ' + domain1,
                    red_ids + domain2)
            else:
                cursor.execute('SELECT id FROM "' + cls._table + '" '
                    'WHERE ' + red_sql, red_ids)
            rowcount = cursor.rowcount
            if rowcount == -1 or rowcount is None:
                rowcount = len(cursor.fetchall())
            if not rowcount == len({}.fromkeys(sub_ids)):
                if domain1:
                    cursor.execute('SELECT id FROM "' + cls._table + '" '
                        'WHERE ' + red_sql, red_ids)
                    rowcount = cursor.rowcount
                    if rowcount == -1 or rowcount is None:
                        rowcount = len(cursor.fetchall())
                    if rowcount == len({}.fromkeys(sub_ids)):
                        cls.raise_user_error('access_error', cls.__name__)
                cls.raise_user_error('write_error', cls.__name__)
            try:
                cursor.execute('UPDATE "' + cls._table + '" '
                    'SET ' + ','.join([x[0] + ' = ' + x[1] for x in upd0])
                    + ' WHERE ' + red_sql, upd1 + red_ids)
            except DatabaseIntegrityError, exception:
                with contextlib.nested(Transaction().new_cursor(),
                        Transaction().set_user(0)):
                    for field_name in values:
                        if field_name not in cls._fields:
                            continue
                        field = cls._fields[field_name]
                        # Check required fields
                        if field.required and \
                                not hasattr(field, 'set') and \
                                not isinstance(field, (fields.Integer,
                                    fields.Float)) and \
                                field_name not in ('create_uid',
                                    'create_date'):
                            if not values[field_name]:
                                cls.raise_user_error('required_field',
                                        error_args=cls._get_error_args(
                                            field_name))
                        if isinstance(field, fields.Many2One) \
                                and values[field_name]:
                            Model = pool.get(field.model_name)
                            create_records = Transaction().create_records.get(
                                    field.model_name, set())
                            delete_records = Transaction().delete_records.get(
                                    field.model_name, set())
                            if not ((Model.search([
                                                ('id', '=',
                                                    values[field_name]),
                                                ], order=[])
                                        or (values[field_name]
                                            in create_records))
                                    and (values[field_name]
                                        not in delete_records)):
                                cls.raise_user_error('foreign_model_missing',
                                    error_args=cls._get_error_args(
                                        field_name))
                    for name, _, error in cls._sql_constraints:
                        if name in exception[0]:
                            cls.raise_user_error(error)
                    for name, error in cls._sql_error_messages.iteritems():
                        if name in exception[0]:
                            cls.raise_user_error(error)
                raise

        for field in direct:
            if getattr(cls._fields[field], 'translate', False):
                Translation.set_ids(
                        cls.__name__ + ',' + field, 'model',
                        Transaction().language, ids, values[field])

        # call the 'set' method of fields
        for field in upd_todo:
            cls._fields[field].set(ids, cls, field, values[field])

        if cls._history:
            columns = ['"' + str(x) + '"' for x in cls._fields
                    if not hasattr(cls._fields[x], 'set')]
            for obj_id in ids:
                cursor.execute('INSERT INTO "' + cls._table + '__history" '
                    '(' + ','.join(columns) + ') '
                    'SELECT ' + ','.join(columns) + ' ' +
                    'FROM "' + cls._table + '" '
                    'WHERE id = %s', (obj_id,))

        cls._validate(records)

        # Check for Modified Preorder Tree Traversal
        for k in cls._fields:
            field = cls._fields[k]
            if isinstance(field, fields.Many2One) \
                    and field.model_name == cls.__name__ \
                    and field.left and field.right:
                if field.left in values or field.right in values:
                    raise Exception('ValidateError',
                            'You can not update fields: "%s", "%s"' %
                            (field.left, field.right))
                if len(ids) == 1:
                    cls._update_tree(ids[0], k, field.left, field.right)
                else:
                    with Transaction().set_user(0):
                        cls._rebuild_tree(k, False, 0)

        cls.trigger_write(trigger_eligibles)

        return True

    @classmethod
    def delete(cls, records):
        cursor = Transaction().cursor
        pool = Pool()
        Translation = pool.get('ir.translation')
        ids = map(int, records)

        if not ids:
            return True

        if cls.table_query():
            return True

        if Transaction().delete and Transaction().delete.get(cls.__name__):
            ids = ids[:]
            for del_id in Transaction().delete[cls.__name__]:
                for i in range(ids.count(del_id)):
                    ids.remove(del_id)

        if Transaction().timestamp:
            for i in range(0, len(ids), cursor.IN_MAX):
                sub_ids = ids[i:i + cursor.IN_MAX]
                clause = ('(id = %s AND '
                    'CAST(EXTRACT(EPOCH FROM '
                    'COALESCE(write_date, create_date)) AS ' +
                    FIELDS['numeric'].sql_type(cls.create_date)[1] +
                    ') > %s)')
                args = []
                for i in sub_ids:
                    if Transaction().timestamp.get(
                            cls.__name__ + ',' + str(i)):
                        args.append(i)
                        args.append(Transaction().timestamp[
                            cls.__name__ + ',' + str(i)])
                if args:
                    cursor.execute("SELECT id "
                        'FROM "' + cls._table + '" '
                        'WHERE ' + ' OR '.join(
                            (clause,) * (len(args) / 2)), args)
                    if cursor.fetchone():
                        raise ConcurrencyException(
                            'Records were modified in the meanwhile')
            for i in ids:
                if Transaction().timestamp.get(cls.__name__ + ',' + str(i)):
                    del Transaction().timestamp[cls.__name__ + ',' + str(i)]

        tree_ids = {}
        for k in cls._fields:
            field = cls._fields[k]
            if isinstance(field, fields.Many2One) \
                    and field.model_name == cls.__name__ \
                    and field.left and field.right:
                red_sql, red_ids = reduce_ids('"' + k + '"', ids)
                cursor.execute('SELECT id FROM "' + cls._table + '" '
                    'WHERE ' + red_sql, red_ids)
                tree_ids[k] = [x[0] for x in cursor.fetchall()]

        foreign_keys_tocheck = []
        foreign_keys_toupdate = []
        foreign_keys_todelete = []
        for _, model in pool.iterobject():
            if hasattr(model, 'table_query') \
                    and model.table_query():
                continue
            if not issubclass(model, ModelStorage):
                continue
            for field_name, field in model._fields.iteritems():
                if isinstance(field, fields.Many2One) \
                        and field.model_name == cls.__name__:
                    if field.ondelete == 'CASCADE':
                        foreign_keys_todelete.append((model, field_name))
                    elif field.ondelete == 'SET NULL':
                        if field.required:
                            foreign_keys_tocheck.append((model, field_name))
                        else:
                            foreign_keys_toupdate.append((model, field_name))
                    else:
                        foreign_keys_tocheck.append((model, field_name))

        Transaction().delete.setdefault(cls.__name__, set()).update(ids)

        domain1, domain2 = pool.get('ir.rule').domain_get(cls.__name__,
                mode='delete')
        if domain1:
            domain1 = ' AND (' + domain1 + ') '

        for i in range(0, len(ids), cursor.IN_MAX):
            sub_ids = ids[i:i + cursor.IN_MAX]
            red_sql, red_ids = reduce_ids('id', sub_ids)
            if domain1:
                cursor.execute('SELECT id FROM "' + cls._table + '" '
                    'WHERE ' + red_sql + ' ' + domain1,
                    red_ids + domain2)
                rowcount = cursor.rowcount
                if rowcount == -1 or rowcount is None:
                    rowcount = len(cursor.fetchall())
                if not rowcount == len({}.fromkeys(sub_ids)):
                    cls.raise_user_error('access_error',
                        cls._get_name())

        cls.trigger_delete(records)

        for i in range(0, len(ids), cursor.IN_MAX):
            sub_ids = ids[i:i + cursor.IN_MAX]
            sub_records = records[i:i + cursor.IN_MAX]
            red_sql, red_ids = reduce_ids('id', sub_ids)

            Transaction().delete_records.setdefault(cls.__name__,
                    set()).update(sub_ids)

            for Model, field_name in foreign_keys_toupdate:
                if (not hasattr(Model, 'search')
                        or not hasattr(Model, 'write')):
                    continue
                red_sql2, red_ids2 = reduce_ids('"' + field_name + '"',
                    sub_ids)
                cursor.execute('SELECT id FROM "' + Model._table + '" '
                    'WHERE ' + red_sql2, red_ids2)
                models = Model.browse([x[0] for x in cursor.fetchall()])
                if models:
                    Model.write(models, {
                            field_name: None,
                            })

            for Model, field_name in foreign_keys_todelete:
                if (not hasattr(Model, 'search')
                        or not hasattr(Model, 'delete')):
                    continue
                red_sql2, red_ids2 = reduce_ids('"' + field_name + '"',
                    sub_ids)
                cursor.execute('SELECT id FROM "' + Model._table + '" '
                    'WHERE ' + red_sql2, red_ids2)
                models = Model.browse([x[0] for x in cursor.fetchall()])
                if models:
                    Model.delete(models)

            for Model, field_name in foreign_keys_tocheck:
                with Transaction().set_user(0):
                    if Model.search([
                                (field_name, 'in', sub_ids),
                                ], order=[]):
                        error_args = []
                        error_args.append(cls._get_error_args('id')[1])
                        error_args.extend(list(
                                Model._get_error_args(field_name)))
                        cls.raise_user_error('foreign_model_exist',
                            error_args=tuple(error_args))

            super(ModelSQL, cls).delete(sub_records)

            try:
                cursor.execute('DELETE FROM "' + cls._table + '" '
                    'WHERE ' + red_sql, red_ids)
            except DatabaseIntegrityError, exception:
                with Transaction().new_cursor():
                    for name, _, error in cls._sql_constraints:
                        if name in exception[0]:
                            cls.raise_user_error(error)
                    for name, error in cls._sql_error_messages.iteritems():
                        if name in exception[0]:
                            cls.raise_user_error(error)
                raise

        Translation.delete_ids(cls.__name__, 'model', ids)

        if cls._history:
            for obj_id in ids:
                cursor.execute('INSERT INTO "' + cls._table + '__history" '
                    '(id, write_uid, write_date) VALUES (%s, %s, %s)',
                    (obj_id, Transaction().user, datetime.datetime.now()))

        for k in tree_ids.keys():
            field = cls._fields[k]
            if len(tree_ids[k]) == 1:
                cls._update_tree(tree_ids[k][0], k, field.left, field.right)
            else:
                with Transaction().set_user(0):
                    cls._rebuild_tree(k, False, 0)

    @classmethod
    def search(cls, domain, offset=0, limit=None, order=None, count=False,
            query_string=False):
        pool = Pool()
        Rule = pool.get('ir.rule')
        cursor = Transaction().cursor

        # Get domain clauses
        qu1, qu2, tables, tables_args = cls.search_domain(domain)

        # Get order by
        order_by = []
        if order is None or order is False:
            order = cls._order
        for field, otype in order:
            if otype.upper() not in ('DESC', 'ASC'):
                raise Exception('Error', 'Wrong order type (%s)!' % otype)
            order_by2, tables2, tables2_args = cls._order_calc(field, otype)
            order_by += order_by2
            for table in tables2:
                if table not in tables:
                    tables.append(table)
                    if tables2_args.get(table):
                        tables_args.extend(tables2_args.get(table))

        order_by = ','.join(order_by)

        if type(limit) not in (float, int, long, type(None)):
            raise Exception('Error', 'Wrong limit type (%s)!' % type(limit))
        if type(offset) not in (float, int, long, type(None)):
            raise Exception('Error', 'Wrong offset type (%s)!' % type(offset))

        # construct a clause for the rules :
        domain1, domain2 = Rule.domain_get(cls.__name__, mode='read')
        if domain1:
            if qu1:
                qu1 += ' AND ' + domain1
            else:
                qu1 = domain1
            qu2 += domain2

        if count:
            cursor.execute(cursor.limit_clause(
                'SELECT COUNT("%s".id) FROM ' % cls._table +
                    ' '.join(tables) + (qu1 and ' WHERE ' + qu1 or ''),
                    limit, offset), tables_args + qu2)
            res = cursor.fetchall()
            return res[0][0]
        # execute the "main" query to fetch the ids we were searching for
        select_fields = ['"' + cls._table + '".id AS id']
        if cls._history and Transaction().context.get('_datetime') \
                and not query_string:
            select_fields += ['COALESCE("' + cls._table + '".write_date, "'
                + cls._table + '".create_date) AS _datetime']
        if not query_string:
            select_fields += [
                '"' + cls._table + '"."' + name + '" AS "' + name + '"'
                for name, field in cls._fields.iteritems()
                if not hasattr(field, 'get')
                and name != 'id'
                and not getattr(field, 'translate', False)
                and field.loading == 'eager']
            if not cls.table_query():
                select_fields += ['CAST(EXTRACT(EPOCH FROM '
                        '(COALESCE("' + cls._table + '".write_date, '
                        '"' + cls._table + '".create_date))) AS VARCHAR'
                        ') AS _timestamp']
        query_str = cursor.limit_clause(
            'SELECT ' + ','.join(select_fields) + ' FROM ' +
            ' '.join(tables) + (qu1 and ' WHERE ' + qu1 or '') +
            (order_by and ' ORDER BY ' + order_by or ''), limit, offset)
        if query_string:
            return (query_str, tables_args + qu2)
        cursor.execute(query_str, tables_args + qu2)

        rows = cursor.dictfetchmany(cursor.IN_MAX)
        cache = cursor.get_cache(Transaction().context)
        if cls.__name__ not in cache:
            cache[cls.__name__] = LRUDict(RECORD_CACHE_SIZE)
        delete_records = Transaction().delete_records.setdefault(cls.__name__,
                set())
        keys = None
        for data in islice(rows, 0, cache.size_limit):
            if data['id'] in delete_records:
                continue
            if keys is None:
                keys = data.keys()
                for k in keys[:]:
                    if k in ('_timestamp', '_datetime'):
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
            select_fields2 = [select_fields[0]]
            if (cls._history
                    and Transaction().context.get('_datetime')
                    and not query_string):
                select_fields2 += [select_fields[1]]
            cursor.execute(
                'SELECT * FROM (' +
                cursor.limit_clause(
                    'SELECT ' + ','.join(select_fields2) + ' FROM ' +
                    ' '.join(tables) + (qu1 and ' WHERE ' + qu1 or '') +
                    (order_by and ' ORDER BY ' + order_by or ''),
                    limit, offset) + ') AS "' + cls._table + '"',
                tables_args + qu2)
            rows = cursor.dictfetchall()

        if cls._history and Transaction().context.get('_datetime'):
            res = []
            ids_date = {}
            for data in rows:
                if data['id'] in ids_date:
                    if data['_datetime'] <= ids_date[data['id']]:
                        continue
                if data['id'] in res:
                    res.remove(data['id'])
                res.append(data['id'])
                ids_date[data['id']] = data['_datetime']
            to_delete = set()
            for i in range(0, len(res), cursor.IN_MAX):
                sub_ids = res[i:i + cursor.IN_MAX]
                reduced_sql, reduced_ids = reduce_ids('id', sub_ids)
                cursor.execute(('SELECT id, write_date '
                        'FROM "%s__history" WHERE %s'
                        'AND (write_date IS NOT NULL AND create_date IS NULL)'
                        ) % (cls._table, reduced_sql),
                    reduced_ids)
                for deleted_id, delete_date in cursor.fetchall():
                    if ids_date[deleted_id] < delete_date:
                        to_delete.add(deleted_id)
            return cls.browse(filter(lambda x: x not in to_delete, res))

        return cls.browse([x['id'] for x in rows])

    @classmethod
    def search_domain(cls, domain, active_test=True):
        '''
        Return SQL clause, tables to use and arguments for the domain
        Set active_test to add it.
        '''
        domain = cls._search_domain_active(domain, active_test=active_test)

        table_query = ''
        tables_args = []
        if cls.table_query():
            table_query, tables_args = cls.table_query()
            table_query = '(' + table_query + ') AS '

        if cls._history and Transaction().context.get('_datetime'):
            table_query = '"' + cls._table + '__history" AS '

        tables = [table_query + '"' + cls._table + '"']

        qu1, qu2 = cls.__search_domain_oper(domain, tables, tables_args)
        if cls._history and Transaction().context.get('_datetime'):
            if qu1:
                qu1 += ' AND'
            qu1 += ' (COALESCE("' + cls._table + '".write_date, "' + \
                cls._table + '".create_date) <= %s)'
            qu2 += [Transaction().context['_datetime']]
        return qu1, qu2, tables, tables_args

    @classmethod
    def __search_domain_oper(cls, domain, tables, tables_args):
        operator = 'AND'
        if len(domain) and isinstance(domain[0], basestring):
            if domain[0] not in ('AND', 'OR'):
                raise Exception('ValidateError', 'Operator "%s" not supported'
                    % domain[0])
            operator = domain[0]
            domain = domain[1:]
        tuple_args = []
        list_args = []
        for arg in domain:
            #add test for xmlrpc that doesn't handle tuple
            if (isinstance(arg, tuple)
                    or (isinstance(arg, list) and len(arg) > 2
                        and arg[1] in OPERATORS)):
                tuple_args.append(tuple(arg))
            elif isinstance(arg, list):
                list_args.append(arg)

        qu1, qu2 = cls.__search_domain_calc(tuple_args, tables, tables_args)
        if len(qu1):
            qu1 = (' ' + operator + ' ').join(qu1)
        else:
            qu1 = ''

        for domain2 in list_args:
            qu1b, qu2b = cls.__search_domain_oper(domain2, tables,
                    tables_args)
            if not qu1b:
                qu1b = '%s'
                qu2b = [True]
            if qu1 and qu1b:
                qu1 += ' ' + operator + ' ' + qu1b
            elif qu1b:
                qu1 = qu1b
            qu2 += qu2b
        if qu1:
            qu1 = '(' + qu1 + ')'
        return qu1, qu2

    @classmethod
    def __search_domain_calc(cls, domain, tables, tables_args):
        pool = Pool()
        domain = domain[:]
        cursor = Transaction().cursor

        for arg in domain:
            if arg[1] not in OPERATORS:
                raise Exception('ValidateError', 'Argument "%s" not supported'
                    % arg[1])
        i = 0
        joins = []
        while i < len(domain):
            fargs = domain[i][0].split('.', 1)
            field = getattr(cls, fargs[0])
            table = cls
            if len(fargs) > 1:
                if field._type in ('many2one', 'reference'):
                    if field._type == 'many2one':
                        Target = pool.get(field.model_name)
                    else:
                        Target = pool.get(domain[i][3])
                    m2o_search = [(fargs[1], domain[i][1], domain[i][2])]
                    if 'active' in Target._fields:
                        m2o_search += [('active', 'in', (True, False))]
                    if hasattr(field, 'search'):
                        domain.extend([(fargs[0], 'in',
                                    map(int, Target.search(m2o_search,
                                            order=[])))])
                        domain.pop(i)
                    else:
                        in_query = Target.search(m2o_search, order=[],
                            query_string=True)
                        if field._type == 'many2one':
                            domain[i] = (fargs[0], 'inselect', in_query, table)
                        else:
                            sql_type = FIELDS[
                                cls.id._type].sql_type(cls.id)[0]
                            query = ('SELECT id FROM "' + cls._table + '" '
                                'WHERE CAST(SUBSTR("' + fargs[0] + '", '
                                        'POSITION(\',\' IN "' + fargs[0] + '")'
                                        + '+ 1) '
                                    'AS ' + sql_type + ') '
                                'IN (' + in_query[0] + ') '
                                'AND "' + fargs[0] + '" ilike %s')
                            domain[i] = ('id', 'inselect',
                                (query, in_query[1] + [domain[i][3] + ',%']))
                        i += 1
                    continue
                elif field._type in ('one2one', 'many2many', 'one2many'):
                    if hasattr(field, 'model_name'):
                        Target = pool.get(field.model_name)
                    else:
                        Target = field.get_target()
                    if hasattr(field, 'relation_name'):
                        Relation = pool.get(field.relation_name)
                        origin, target = field.origin, field.target
                    else:
                        Relation = Target
                        origin, target = field.field, 'id'
                    rev_field = Relation._fields[origin]
                    if rev_field._type == 'reference':
                        sql_type = FIELDS[
                            cls.id._type].sql_type(cls.id)[0]
                        where = ' AND "' + origin + '" LIKE %s'
                        where_args = [cls.__name__ + ',%']
                        origin = ('CAST(SUBSTR("%s", '
                            'POSITION(\',\' IN "%s") + 1) AS %s)'
                            % (origin, origin, sql_type))
                    else:
                        origin = '"%s"' % origin
                        where = ''
                        where_args = []
                    if hasattr(field, 'search'):
                        domain.extend([(fargs[0], 'in',
                                    map(int, Target.search([
                                                (fargs[1], domain[i][1],
                                                    domain[i][2]),
                                                ], order=[])))])
                        domain.pop(i)
                    else:
                        query1, query2 = Target.search([
                            (fargs[1], domain[i][1], domain[i][2]),
                            ], order=[], query_string=True)
                        query1 = ('SELECT %s FROM "%s" WHERE "%s" IN (%s)' %
                                (origin, Relation._table, target, query1))
                        query1 += where
                        query2 += where_args
                        domain[i] = ('id', 'inselect', (query1, query2))
                        i += 1
                    continue
                else:
                    raise Exception('ValidateError',
                        'Clause on field "%s" doesn\'t work on "%s"'
                        % (domain[i][0], cls.__name__))
            if hasattr(field, 'search'):
                clause = domain.pop(i)
                domain.extend(field.search(table, clause[0], clause))
            elif field._type == 'one2many':
                Field = pool.get(field.model_name)
                table_query = ''
                table_args = []
                if Field.table_query():
                    table_query, table_args = Field.table_query()
                    table_query = '(' + table_query + ') AS '
                rev_field = Field._fields[field.field]
                if rev_field._type == 'reference':
                    sql_type = FIELDS[cls.id._type].sql_type(cls.id)[0]
                    select = ('CAST(SUBSTR("%s", '
                        'POSITION(\',\' IN "%s") + 1) AS %s)'
                        % (field.field, field.field, sql_type))
                    where = ' AND "' + field.field + '" LIKE %s'
                    where_args = [cls.__name__ + ',%']
                else:
                    select = '"' + field.field + '"'
                    where = ''
                    where_args = []

                if isinstance(domain[i][2], bool) or domain[i][2] is None:
                    query1 = ('SELECT ' + select + ' '
                        'FROM ' + table_query + '"' + Field._table + '" '
                        'WHERE "' + field.field + '" IS NOT NULL' + where)
                    query2 = table_args + where_args
                    clause = 'inselect'
                    if not domain[i][2]:
                        clause = 'notinselect'
                    domain[i] = ('id', clause, (query1, query2))
                else:
                    if isinstance(domain[i][2], basestring):
                        target_field = 'rec_name'
                    else:
                        target_field = 'id'
                    query1, query2 = Field.search([
                            (target_field, domain[i][1], domain[i][2]),
                            ], order=[], query_string=True)
                    query1 = ('SELECT ' + select + ' '
                        'FROM ' + table_query +
                            '"' + Field._table + '" '
                        'WHERE id IN (' + query1 + ')' + where)
                    query2 = table_args + query2 + where_args
                    domain[i] = ('id', 'inselect', (query1, query2))
                i += 1
            elif field._type in ('many2many', 'one2one'):
                # XXX must find a solution for long id list
                if hasattr(field, 'model_name'):
                    Target = pool.get(field.model_name)
                else:
                    Target = field.get_target()
                if domain[i][1] in ('child_of', 'not child_of'):
                    if isinstance(domain[i][2], basestring):
                        ids2 = map(int, Target.search([
                                    ('rec_name', 'ilike', domain[i][2]),
                                    ], order=[]))
                    elif not isinstance(domain[i][2], list):
                        ids2 = [domain[i][2]]
                    else:
                        ids2 = domain[i][2]

                    def _rec_get(ids, table, parent):
                        if not ids:
                            return []
                        ids2 = map(int, table.search([
                                    (parent, 'in', ids),
                                    (parent, '!=', None),
                                    ], order=[]))
                        return ids + _rec_get(ids2, table, parent)

                    if Target.__name__ != table.__name__:
                        if len(domain[i]) != 4:
                            raise Exception('Error', 'Programming error: '
                                'child_of on field "%s" is not allowed!'
                                % domain[i][0])
                        ids2 = map(int, Target.search([
                                    (domain[i][3], 'child_of', ids2),
                                    ], order=[]))
                        Relation = pool.get(field.relation_name)
                        red_sql, red_ids = reduce_ids('"' + field.target + '"',
                                ids2)
                        query1 = ('SELECT "' + field.origin + '" '
                            'FROM "' + Relation._table + '" '
                            'WHERE ' + red_sql + ' '
                                'AND "' + field.origin + '" IS NOT NULL')
                        query2 = red_ids
                        if domain[i][1] == 'child_of':
                            domain[i] = ('id', 'inselect', (query1, query2))
                        else:
                            domain[i] = ('id', 'notinselect', (query1, query2))
                    else:
                        if domain[i][1] == 'child_of':
                            domain[i] = ('id', 'in', ids2 + _rec_get(ids2,
                                table, domain[i][0]))
                        else:
                            domain[i] = ('id', 'not in', ids2 + _rec_get(ids2,
                                table, domain[i][0]))
                else:
                    Relation = pool.get(field.relation_name)
                    table_query = ''
                    table_args = []
                    if Relation.table_query():
                        table_query, table_args = Relation.table_query()
                        table_query = '(' + table_query + ') AS '
                    origin_field = Relation._fields[field.origin]
                    if origin_field._type == 'reference':
                        sql_type = FIELDS[cls.id._type].sql_type(cls.id)[0]
                        select = ('CAST(SUBSTR("%s", '
                            'POSITION(\',\' IN "%s") + 1) AS %s)'
                            % (field.origin, field.origin, sql_type))
                        where = ' AND "' + field.origin + '" LIKE %s'
                        where_args = [cls.__name__ + ',%']
                    else:
                        select = '"' + field.origin + '"'
                        where = ''
                        where_args = []
                    if isinstance(domain[i][2], bool) or domain[i][2] is None:
                        query1 = ('SELECT ' + select + ' '
                            'FROM ' + table_query + ' '
                                '"' + Relation._table + '" '
                            'WHERE "' + field.origin + '" IS NOT NULL' + where)
                        query2 = table_args + where_args
                        clause = 'inselect'
                        if not domain[i][2]:
                            clause = 'notinselect'
                        domain[i] = ('id', clause, (query1, query2))
                    else:
                        if isinstance(domain[i][2], basestring):
                            target_field = 'rec_name'
                        else:
                            target_field = 'id'

                        query1, query2 = Target.search([
                                    (target_field, domain[i][1], domain[i][2]),
                                    ], order=[], query_string=True)
                        query1 = ('SELECT ' + select + ' '
                            'FROM ' + table_query +
                                '"' + Relation._table + '" '
                            'WHERE "' + field.target + '" IN (' + query1 + ')'
                            + where)
                        query2 = table_args + query2 + where_args
                        domain[i] = ('id', 'inselect', (query1, query2))
                i += 1

            elif field._type == 'many2one':
                # XXX must find a solution for long id list
                if domain[i][1] in ('child_of', 'not child_of'):
                    if isinstance(domain[i][2], basestring):
                        Field = pool.get(field.model_name)
                        ids2 = map(int, Field.search([
                                    ('rec_name', 'like', domain[i][2]),
                                    ], order=[]))
                    elif not isinstance(domain[i][2], list):
                        ids2 = [domain[i][2]]
                    else:
                        ids2 = domain[i][2]

                    def _rec_get(ids, table, parent):
                        if not ids:
                            return []
                        ids2 = map(int, table.search([
                                    (parent, 'in', ids),
                                    (parent, '!=', None),
                                    ]))
                        return ids + _rec_get(ids2, table, parent)

                    if field.model_name != table.__name__:
                        if len(domain[i]) != 4:
                            raise Exception('Error', 'Programming error: '
                                'child_of on field "%s" is not allowed!'
                                % domain[i][0])
                        ids2 = map(int, pool.get(field.model_name).search([
                                    (domain[i][3], 'child_of', ids2),
                                    ], order=[]))
                        if domain[i][1] == 'child_of':
                            domain[i] = (domain[i][0], 'in', ids2, table)
                        else:
                            domain[i] = (domain[i][0], 'not in', ids2, table)
                    else:
                        if field.left and field.right and ids2:
                            red_sql, red_ids = reduce_ids('id', ids2)
                            cursor.execute('SELECT "' + field.left + '", '
                                    '"' + field.right + '" ' +
                                'FROM "' + cls._table + '" ' +
                                'WHERE ' + red_sql, red_ids)
                            clause = '(1=0) '
                            for left, right in cursor.fetchall():
                                clause += 'OR '
                                clause += ('( "' + field.left + '" >= ' +
                                    str(left) + ' ' +
                                    'AND "' + field.right + '" <= ' +
                                    str(right) + ')')

                            query = ('SELECT id FROM "' + cls._table + '" ' +
                                'WHERE ' + clause)
                            if domain[i][1] == 'child_of':
                                domain[i] = ('id', 'inselect', (query, []))
                            else:
                                domain[i] = ('id', 'notinselect', (query, []))
                        else:
                            if domain[i][1] == 'child_of':
                                domain[i] = ('id', 'in', ids2 + _rec_get(
                                    ids2, table, domain[i][0]), table)
                            else:
                                domain[i] = ('id', 'not in', ids2 + _rec_get(
                                    ids2, table, domain[i][0]), table)
                else:
                    if isinstance(domain[i][2], basestring):
                        Field = pool.get(field.model_name)
                        m2o_search = [('rec_name', domain[i][1], domain[i][2])]
                        if 'active' in Field._fields:
                            m2o_search += [('active', 'in', (True, False))]
                        res_ids = map(int, Field.search(m2o_search, order=[]))
                        domain[i] = (domain[i][0], 'in', res_ids, table)
                    else:
                        domain[i] += (table,)
                i += 1
            else:
                if getattr(field, 'translate', False):
                    if cls.__name__ == 'ir.model':
                        table_join = ('LEFT JOIN "ir_translation" '
                            'ON (ir_translation.name = '
                                    'ir_model.model||\',%s\' '
                                'AND ir_translation.res_id IS NULL '
                                'AND ir_translation.lang = %%s '
                                'AND ir_translation.type = \'model\' '
                                'AND ir_translation.fuzzy = %%s)'
                            % domain[i][0])
                    elif cls.__name__ == 'ir.model.field':
                        if domain[i][0] == 'field_description':
                            ttype = 'field'
                        else:
                            ttype = 'help'
                        table_join = ('LEFT JOIN "ir_model" '
                            'ON ir_model.id = ir_model_field.model '
                            'LEFT JOIN "ir_translation" '
                            'ON (ir_translation.name = '
                                    'ir_model.model||\',\'||%s.name '
                                'AND ir_translation.res_id IS NULL '
                                'AND ir_translation.lang = %%s '
                                'AND ir_translation.type = \'%s\' '
                                'AND ir_translation.fuzzy = %%s)'
                            % (table._table, ttype))
                    else:
                        table_join = ('LEFT JOIN "ir_translation" '
                            'ON (ir_translation.res_id = %s.id '
                                'AND ir_translation.name = \'%s,%s\' '
                                'AND ir_translation.lang = %%s '
                                'AND ir_translation.type = \'model\' '
                                'AND ir_translation.fuzzy = %%s)'
                            % (table._table, table.__name__, domain[i][0]))
                    table_join_args = [Transaction().language, False]

                    table_query = ''
                    table_args = []
                    if table.table_query():
                        table_query, table_args = table.table_query()
                        table_query = '(' + table_query + ') AS '

                    Translation = pool.get('ir.translation')

                    qu1, qu2, tables, table_args = \
                        Translation.search_domain([
                                ('value', domain[i][1], domain[i][2]),
                                ])
                    qu1 = qu1.replace('"ir_translation"."value"',
                        'COALESCE(NULLIF("ir_translation"."value", \'\'), '
                        '"%s"."%s")' % (table._table, domain[i][0]))
                    query1 = ('SELECT "' + table._table + '".id '
                        'FROM ' + table_query + '"' + table._table + '" '
                        + table_join + ' WHERE ' + qu1)
                    query2 = table_args + table_join_args + qu2

                    domain[i] = ('id', 'inselect', (query1, query2), table)
                else:
                    domain[i] += (table,)
                i += 1
        domain.extend(joins)

        qu1, qu2 = [], []
        for arg in domain:
            table = cls
            if len(arg) > 3:
                table = arg[3]
            column = getattr(table, arg[0])
            if arg[1] in ('inselect', 'notinselect'):
                clause = 'IN'
                if arg[1] == 'notinselect':
                    clause = 'NOT IN'
                qu1.append('("%s"."%s" %s (%s))' % (table._table, arg[0],
                    clause, arg[2][0]))
                qu2 += arg[2][1]
            elif arg[1] in ('in', 'not in'):
                if len(arg[2]) > 0:
                    todel = []
                    if column._type != 'boolean':
                        for xitem in range(len(arg[2])):
                            if (arg[2][xitem] is False
                                    or arg[2][xitem] is None):
                                todel.append(xitem)
                    arg2 = arg[2][:]
                    for xitem in todel[::-1]:
                        del arg2[xitem]
                    arg2 = [FIELDS[column._type].sql_format(x)
                            for x in arg2]
                    if len(arg2):
                        if reduce(lambda x, y: (x
                                    and isinstance(y, (int, long))
                                    and not isinstance(y, bool)),
                                arg2, True):
                            red_sql, red_ids = reduce_ids('"%s"."%s"'
                                % (table._table, arg[0]), arg2)
                            if arg[1] == 'not in':
                                red_sql = '(NOT(' + red_sql + '))'
                            qu1.append(red_sql)
                            qu2 += red_ids
                        else:
                            qu1.append(('("%s"."%s" ' + arg[1] + ' (%s))')
                                % (table._table, arg[0], ','.join(
                                        ('%s',) * len(arg2))))
                            qu2 += arg2
                        if todel:
                            if column._type == 'boolean':
                                if arg[1] == 'in':
                                    qu1[-1] = ('(' + qu1[-1] + ' OR '
                                        '"%s"."%s" = %%s)'
                                        % (table._table, arg[0]))
                                    qu2.append(False)
                                else:
                                    qu1[-1] = ('(' + qu1[-1] + ' AND '
                                        '"%s"."%s" != %%s)'
                                        % (table._table, arg[0]))
                                    qu2.append(False)
                            else:
                                if arg[1] == 'in':
                                    qu1[-1] = ('(' + qu1[-1] + ' OR '
                                        '"%s"."%s" IS NULL)'
                                        % (table._table, arg[0]))
                                else:
                                    qu1[-1] = ('(' + qu1[-1] + ' AND '
                                        '"%s"."%s" IS NOT NULL)'
                                        % (table._table, arg[0]))
                    elif todel:
                        if column._type == 'boolean':
                            if arg[1] == 'in':
                                qu1.append('("%s"."%s" = %%s)'
                                    % (table._table, arg[0]))
                                qu2.append(False)
                            else:
                                qu1.append('("%s"."%s" != %%s)'
                                    % (table._table, arg[0]))
                                qu2.append(False)
                        else:
                            if arg[1] == 'in':
                                qu1.append('("%s"."%s" IS NULL)'
                                    % (table._table, arg[0]))
                            else:
                                qu1.append('("%s"."%s" IS NOT NULL)'
                                    % (table._table, arg[0]))
                else:
                    if arg[1] == 'in':
                        qu1.append(' %s')
                        qu2.append(False)
                    else:
                        qu1.append(' %s')
                        qu2.append(True)
            else:
                if (arg[2] is False or arg[2] is None) and (arg[1] == '='):
                    if column._type == 'boolean':
                        qu1.append('(("%s"."%s" = %%s) OR ("%s"."%s" IS NULL))'
                            % (table._table, arg[0], table._table, arg[0]))
                        qu2.append(False)
                    else:
                        qu1.append('("%s"."%s" IS NULL)'
                            % (table._table, arg[0]))
                elif (arg[2] is False or arg[2] is None) and (arg[1] == '!='):
                    if column._type == 'boolean':
                        qu1.append('(("%s"."%s" != %%s) '
                            'AND ("%s"."%s" IS NOT NULL))'
                            % (table._table, arg[0], table._table, arg[0]))
                        qu2.append(False)
                    else:
                        qu1.append('("%s"."%s" IS NOT NULL)'
                            % (table._table, arg[0]))
                else:
                    if arg[0] == 'id':
                        qu1.append('("%s"."%s" %s %%s)'
                            % (table._table, arg[0], arg[1]))
                        qu2.append(FIELDS[column._type]
                            .sql_format(arg[2]))
                    else:
                        add_null = False
                        if arg[1] in ('like', 'ilike'):
                            if not arg[2]:
                                qu2.append('%')
                                add_null = True
                            else:
                                qu2.append(FIELDS[
                                        column._type
                                        ].sql_format(arg[2]))
                        elif arg[1] in ('not like', 'not ilike'):
                            if not arg[2]:
                                qu2.append('')
                            else:
                                qu2.append(FIELDS[
                                        column._type
                                        ].sql_format(arg[2]))
                                add_null = True
                        else:
                            qu2.append(FIELDS[
                                column._type
                                ].sql_format(arg[2]))
                        qu1.append('("%s"."%s" %s %%s)' % (table._table,
                            arg[0], arg[1]))
                        if add_null:
                            qu1[-1] = ('(' + qu1[-1] + ' OR '
                                '"' + table._table + '"."' + arg[0] + '"'
                                ' IS NULL)')

        return qu1, qu2

    @classmethod
    def _order_calc(cls, field, otype):
        pool = Pool()
        order_by = []
        tables = []
        tables_args = {}
        field_name = None
        table_name = None
        link_field = None

        if field in cls._fields:
            table_name = cls._table

            if not hasattr(cls._fields[field], 'set'):
                field_name = field

            if cls._fields[field].order_field:
                field_name = cls._fields[field].order_field

            if isinstance(cls._fields[field], fields.Many2One):
                obj = pool.get(cls._fields[field].model_name)
                table_name = obj._table
                link_field = field
                field_name = None

                if obj._rec_name in obj._fields:
                    field_name = obj._rec_name

                if obj._order_name in obj._fields:
                    field_name = obj._order_name

                if not field_name:
                    field_name = 'id'

                order_by, tables, tables_args = obj._order_calc(field_name,
                        otype)
                table_join = ('LEFT JOIN "' + table_name + '" AS '
                    '"' + table_name + '.' + link_field + '" ON '
                    '"%s.%s".id = "%s"."%s"'
                    % (table_name, link_field, cls._table, link_field))
                for i in range(len(order_by)):
                    if table_name in order_by[i]:
                        order_by[i] = order_by[i].replace(table_name,
                                table_name + '.' + link_field)
                for i in range(len(tables)):
                    if table_name in tables[i]:
                        args = tables_args.pop(tables[i], [])
                        tables[i] = tables[i].replace(table_name,
                                table_name + '.' + link_field)
                        tables_args[tables[i]] = args
                if table_join not in tables:
                    tables.insert(0, table_join)
                return order_by, tables, tables_args

            if (field_name in cls._fields
                    and getattr(cls._fields[field_name], 'translate', False)):
                translation_table = ('ir_translation_%s_%s'
                    % (table_name, field_name))
                if cls.__name__ == 'ir.model':
                    table_join = ('LEFT JOIN "ir_translation" '
                        'AS "%s" ON '
                        '("%s".name = "ir_model".model||\',%s\' '
                            'AND "%s".res_id IS NULL '
                            'AND "%s".lang = %%s '
                            'AND "%s".type = \'model\' '
                            'AND "%s".fuzzy = %%s)'
                        % (translation_table, translation_table, field_name,
                            translation_table, translation_table,
                            translation_table, translation_table))
                elif cls.__name__ == 'ir.model.field':
                    if field_name == 'field_description':
                        ttype = 'field'
                    else:
                        ttype = 'help'
                    table_join = ('LEFT JOIN "ir_model" ON '
                        'ir_model.id = ir_model_field.model')
                    if table_join not in tables:
                        tables.append(table_join)
                    table_join = ('LEFT JOIN "ir_translation" '
                        'AS "%s" ON '
                        '("%s".name = "ir_model".model||\',\'||%s.name '
                            'AND "%s".res_id IS NULL '
                            'AND "%s".lang = %%s '
                            'AND "%s".type = \'%s\' '
                            'AND "%s".fuzzy = %%s)'
                        % (translation_table, translation_table, table_name,
                            translation_table, translation_table,
                            translation_table, ttype, translation_table))
                else:
                    table_join = ('LEFT JOIN "ir_translation" '
                        'AS "%s" ON '
                        '("%s".res_id = "%s".id '
                            'AND "%s".name = \'%s,%s\' '
                            'AND "%s".lang = %%s '
                            'AND "%s".type = \'model\' '
                            'AND "%s".fuzzy = %%s)'
                        % (translation_table, translation_table, table_name,
                            translation_table, cls.__name__, field_name,
                            translation_table, translation_table,
                            translation_table))
                if table_join not in tables:
                    tables.append(table_join)
                    tables_args[table_join] = [Transaction().language, False]
                order_by.append('COALESCE(NULLIF('
                    + '"' + translation_table + '".value, \'\'), '
                    + '"' + table_name + '".' + field_name + ') ' + otype)
                return order_by, tables, tables_args

            if (field_name in cls._fields
                    and cls._fields[field_name]._type == 'selection'
                    and cls._fields[field_name].order_field is None):
                selections = cls.fields_get([field_name]
                    )[field_name]['selection']
                if not isinstance(selections, (tuple, list)):
                    selections = getattr(cls,
                            cls._fields[field_name].selection)()
                order = 'CASE ' + table_name + '.' + field_name
                for selection in selections:
                    order += ' WHEN \'%s\' THEN \'%s\'' % selection
                order += ' ELSE ' + table_name + '.' + field_name + ' END'
                order_by.append(order + ' ' + otype)
                return order_by, tables, tables_args

            if field_name:
                if '%(table)s' in field_name or '%(order)s' in field_name:
                    order_by.append(field_name % {
                        'table': '"%s"' % table_name,
                        'order': otype,
                        })
                else:
                    order_by.append('"%s"."%s" %s'
                        % (table_name, field_name, otype))
                return order_by, tables, tables_args

        raise Exception('Error', 'Wrong field name (%s) for %s in order!' %
            (field, cls.__name__))

    @classmethod
    def _rebuild_tree(cls, parent, parent_id, left):
        '''
        Rebuild left, right value for the tree.
        '''
        cursor = Transaction().cursor
        right = left + 1

        with Transaction().set_user(0):
            childs = cls.search([
                    (parent, '=', parent_id),
                    ])

        for child in childs:
            right = cls._rebuild_tree(parent, child.id, right)

        field = cls._fields[parent]

        if parent_id:
            cursor.execute('UPDATE "' + cls._table + '" '
                'SET "' + field.left + '" = %s, '
                    '"' + field.right + '" = %s '
                'WHERE id = %s', (left, right, parent_id))
        return right + 1

    @classmethod
    def _update_tree(cls, object_id, field_name, left, right):
        '''
        Update left, right values for the tree.
        Remarks:
            - the value (right - left - 1) / 2 will not give
                the number of children node
            - the order of the tree respects the default _order
        '''
        cursor = Transaction().cursor
        cursor.execute('SELECT "' + left + '", "' + right + '" '
            'FROM "' + cls._table + '" '
            'WHERE id = %s', (object_id,))
        fetchone = cursor.fetchone()
        if not fetchone:
            return
        old_left, old_right = fetchone
        if old_left == old_right:
            cursor.execute('UPDATE "' + cls._table + '" '
                'SET "' + right + '" = "' + right + '" + 1 '
                'WHERE id = %s', (object_id,))
            old_right += 1

        parent_right = 1

        cursor.execute('SELECT "' + field_name + '" '
            'FROM "' + cls._table + '" '
            'WHERE id = %s', (object_id,))
        parent_id = cursor.fetchone()[0] or False

        if parent_id:
            cursor.execute('SELECT "' + right + '" '
                'FROM "' + cls._table + '" '
                'WHERE id = %s', (parent_id,))
            parent_right = cursor.fetchone()[0]
        else:
            cursor.execute('SELECT MAX("' + right + '") '
                'FROM "' + cls._table + '" '
                'WHERE "' + field_name + '" IS NULL')
            fetchone = cursor.fetchone()
            if fetchone:
                parent_right = fetchone[0] + 1

        cursor.execute('SELECT id FROM "' + cls._table + '" '
            'WHERE "' + left + '" >= %s AND "' + right + '" <= %s',
            (old_left, old_right))
        child_ids = [x[0] for x in cursor.fetchall()]

        if len(child_ids) > cursor.IN_MAX:
            with Transaction().set_user(0):
                return cls._rebuild_tree(field_name, False, 0)

        red_child_sql, red_child_ids = reduce_ids('id', child_ids)
        # ids for left update
        cursor.execute('SELECT id FROM "' + cls._table + '" '
            'WHERE "' + left + '" >= %s '
                'AND NOT ' + red_child_sql,
            [parent_right] + red_child_ids)
        left_ids = [x[0] for x in cursor.fetchall()]

        # ids for right update
        cursor.execute('SELECT id FROM "' + cls._table + '" '
            'WHERE "' + right + '" >= %s '
                'AND NOT ' + red_child_sql,
            [parent_right] + red_child_ids)
        right_ids = [x[0] for x in cursor.fetchall()]

        if left_ids:
            for i in range(0, len(left_ids), cursor.IN_MAX):
                sub_ids = left_ids[i:i + cursor.IN_MAX]
                red_sub_sql, red_sub_ids = reduce_ids('id', sub_ids)
                cursor.execute('UPDATE "' + cls._table + '" '
                    'SET "' + left + '" = "' + left + '" + '
                        + str(old_right - old_left + 1) + ' '
                    'WHERE ' + red_sub_sql, red_sub_ids)
        if right_ids:
            for i in range(0, len(right_ids), cursor.IN_MAX):
                sub_ids = right_ids[i:i + cursor.IN_MAX]
                red_sub_sql, red_sub_ids = reduce_ids('id', sub_ids)
                cursor.execute('UPDATE "' + cls._table + '" '
                    'SET "' + right + '" = "' + right + '" + '
                        + str(old_right - old_left + 1) + ' '
                    'WHERE ' + red_sub_sql, red_sub_ids)

        cursor.execute('UPDATE "' + cls._table + '" '
            'SET "' + left + '" = "' + left + '" + '
                    + str(parent_right - old_left) + ', '
                '"' + right + '" = "' + right + '" + '
                    + str(parent_right - old_left) + ' '
            'WHERE ' + red_child_sql, red_child_ids)

        # Use root user to by-pass rules
        with contextlib.nested(Transaction().set_user(0),
                Transaction().set_context(active_test=False)):
            brother_ids = map(int, cls.search([
                        (field_name, '=', parent_id),
                        ]))
        if brother_ids[-1] != object_id:
            next_id = brother_ids[brother_ids.index(object_id) + 1]
            cursor.execute('SELECT "' + left + '" '
                'FROM "' + cls._table + '" '
                'WHERE id = %s', (next_id,))
            next_left = cursor.fetchone()[0]
            cursor.execute('SELECT "' + left + '" '
                'FROM "' + cls._table + '" '
                'WHERE id = %s', (object_id,))
            current_left = cursor.fetchone()[0]

            cursor.execute('UPDATE "' + cls._table + '" '
                'SET "' + left + '" = "' + left + '" + '
                        + str(old_right - old_left + 1) + ', '
                    '"' + right + '" = "' + right + '" + '
                        + str(old_right - old_left + 1) + ' '
                'WHERE "' + left + '" >= %s AND "' + right + '" <= %s',
                (next_left, current_left))

            cursor.execute('UPDATE "' + cls._table + '" '
                'SET "' + left + '" = "' + left + '" - '
                        + str(current_left - next_left) + ', '
                    '"' + right + '" = "' + right + '" - '
                        + str(current_left - next_left) + ' '
                'WHERE ' + red_child_sql, red_child_ids)

    @classmethod
    def validate(cls, records):
        super(ModelSQL, cls).validate(records)
        cursor = Transaction().cursor
        if cursor.has_constraint():
            return
        # Works only for a single transaction
        ids = map(int, records)
        for _, sql, error in cls._sql_constraints:
            match = _RE_UNIQUE.match(sql)
            if match:
                sql = match.group(1)
                columns = sql.split(',')
                sql_clause = ' AND '.join('%s = %%s'
                    % i for i in columns)
                sql_clause = '(id != %s AND ' + sql_clause + ')'

                in_max = cursor.IN_MAX / (len(columns) + 1)
                for i in range(0, len(ids), in_max):
                    sub_ids = ids[i:i + in_max]
                    red_sql, red_ids = reduce_ids('id', sub_ids)

                    cursor.execute('SELECT id,' + sql + ' '
                        'FROM "' + cls._table + '" '
                        'WHERE ' + red_sql, red_ids)

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
                for i in range(0, len(ids), cursor.IN_MAX):
                    sub_ids = ids[i:i + cursor.IN_MAX]
                    red_sql, red_ids = reduce_ids('id', sub_ids)
                    cursor.execute('SELECT id '
                        'FROM "' + cls._table + '" '
                        'WHERE NOT (' + sql + ') '
                            'AND ' + red_sql, red_ids)
                    if cursor.fetchone():
                        cls.raise_user_error(error)
                    continue
