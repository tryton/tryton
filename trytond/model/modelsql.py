#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import contextlib
import datetime
import re
from functools import reduce
from decimal import Decimal
from itertools import islice
from trytond.model import ModelStorage
from trytond.model import fields
from trytond.backend import FIELDS, TableHandler
from trytond.backend import DatabaseIntegrityError, Database
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
    _table = None # The name of the table in database
    _order = None
    _order_name = None # Use to force order field when sorting on Many2One
    _history = False

    def __init__(self):
        super(ModelSQL, self).__init__()
        self._sql_constraints = []
        self._order = [('id', 'ASC')]
        self._sql_error_messages = {}

        if not self._table:
            self._table = self._name.replace('.', '_')

        assert self._table[-9:] != '__history', \
                'Model _table %s cannot end with "__history"' % self._table

    def init(self, module_name):
        super(ModelSQL, self).init(module_name)

        if self.table_query():
            return

        pool = Pool()

        # create/update table in the database
        table = TableHandler(Transaction().cursor, self, module_name)
        if self._history:
            history_table = TableHandler(Transaction().cursor, self,
                    module_name, history=True)
        timestamp_field = FIELDS['timestamp']
        integer_field = FIELDS['integer']
        logs = (
            ('create_date', timestamp_field.sql_type(None),
                timestamp_field.sql_format, lambda *a: datetime.datetime.now(),
                self.create_date.string),
            ('write_date', timestamp_field.sql_type(None),
                timestamp_field.sql_format, None, self.write_date.string),
            ('create_uid', (integer_field.sql_type(None)[0],
             'INTEGER REFERENCES res_user ON DELETE SET NULL',),
             integer_field.sql_format, lambda *a: 0, self.create_uid.string),
            ('write_uid', (integer_field.sql_type(None)[0],
             'INTEGER REFERENCES res_user ON DELETE SET NULL'),
             integer_field.sql_format, None, self.write_uid.string),
            )
        for log in logs:
            table.add_raw_column(log[0], log[1], log[2],
                    default_fun=log[3], migrate=False, string=log[4])
        if self._history:
            history_logs = (
                    ('create_date', timestamp_field.sql_type(None),
                        timestamp_field.sql_format, self.create_date.string),
                    ('write_date', timestamp_field.sql_type(None),
                        timestamp_field.sql_format, self.write_date.string),
                    ('create_uid', (integer_field.sql_type(None)[0],
                     'INTEGER REFERENCES res_user ON DELETE SET NULL',),
                     integer_field.sql_format, self.create_uid.string),
                    ('write_uid', (integer_field.sql_type(None)[0],
                     'INTEGER REFERENCES res_user ON DELETE SET NULL'),
                     integer_field.sql_format, self.write_uid.string),
                    )
            for log in history_logs:
                history_table.add_raw_column(log[0], log[1], log[2],
                        migrate=False, string=log[3])
            history_table.index_action('id', action='add')

        for field_name, field in self._columns.iteritems():
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
                if field_name in self._defaults:
                    default_fun = self._defaults[field_name]

                    def unpack_wrapper(fun):
                        def unpack_result(*a):
                            try: # XXX ugly hack: some default fct try
                                 # to access the non-existing table
                                result = fun(*a)
                            except Exception:
                                return None
                            clean_results = self._clean_defaults(
                                {field_name: result})
                            return clean_results[field_name]
                        return unpack_result
                    default_fun = unpack_wrapper(default_fun)

                table.add_raw_column(field_name,
                        FIELDS[field._type].sql_type(field),
                        FIELDS[field._type].sql_format, default_fun,
                        hasattr(field, 'size') and field.size or None,
                        string=field.string)
                if self._history:
                    history_table.add_raw_column(field_name,
                            FIELDS[field._type].sql_type(field), None,
                            string=field.string)

                if isinstance(field, (fields.Integer, fields.Float)):
                    table.db_default(field_name, 0)

                if isinstance(field, (fields.Boolean)):
                    table.db_default(field_name, False)

                if isinstance(field, fields.Many2One):
                    if field.model_name in ('res.user', 'res.group'):
                        ref = field.model_name.replace('.','_')
                    else:
                        ref = pool.get(field.model_name)._table
                    table.add_fk(field_name, ref, field.ondelete)

                table.index_action(
                        field_name, action=field.select and 'add' or 'remove')

                required = field.required
                if isinstance(field, (fields.Integer, fields.Float,
                    fields.Boolean)):
                    required = True
                table.not_null_action(
                    field_name, action=required and 'add' or 'remove')

            elif not isinstance(field, (fields.One2Many, fields.Function,
                fields.Many2Many)):
                raise Exception('Unknow field type !')

        for field_name, field in self._columns.iteritems():
            if isinstance(field, fields.Many2One) \
                    and field.model_name == self._name \
                    and field.left and field.right:
                with Transaction().set_user(0):
                    self._rebuild_tree(field_name, False, 0)

        for ident, constraint, _ in self._sql_constraints:
            table.add_constraint(ident, constraint)

        if self._history:
            self._update_history_table()
            cursor = Transaction().cursor
            cursor.execute('SELECT id FROM "' + self._table + '"')
            if cursor.fetchone():
                cursor.execute('SELECT id FROM "' + self._table + '__history"')
                if not cursor.fetchone():
                    columns = ['"' + str(x) + '"' for x in self._columns
                            if not hasattr(self._columns[x], 'set')]
                    cursor.execute('INSERT ' \
                            'INTO "' + self._table + '__history" '\
                            '(' + ','.join(columns) + ') ' \
                            'SELECT ' + ','.join(columns) + \
                            ' FROM "' + self._table + '"')
                    cursor.execute('UPDATE "' + self._table + '__history" ' \
                            'SET write_date = NULL')

    def _update_history_table(self):
        if self._history:
            table = TableHandler(Transaction().cursor, self)
            history_table = TableHandler(Transaction().cursor, self,
                    history=True)
            for column_name in table._columns:
                string = ''
                if column_name in self._columns:
                    string = self._columns[column_name].string
                history_table.add_raw_column(column_name,
                        (table._columns[column_name]['typname'],
                            table._columns[column_name]['typname']),
                            None, string=string)

    def _get_error_messages(self):
        res = super(ModelSQL, self)._get_error_messages()
        res += self._sql_error_messages.values()
        for _, _, error in self._sql_constraints:
            res.append(error)
        return res

    def default_sequence(self):
        '''
        Return the default value for sequence field.
        '''
        pool = Pool()
        table = self._table
        if 'sequence' not in self._columns:
            for model in self._inherits:
                model_obj = pool.get(model)
                if 'sequence' in model_obj._columns:
                    table = model_obj._table
                    break
        cursor = Transaction().cursor
        cursor.execute('SELECT MAX(sequence) ' \
                'FROM "' + table + '"')
        res = cursor.fetchone()
        if res:
            return res[0]
        return 0

    def table_query(self):
        '''
        Return None if the model is a real table in the database
        or return a tuple with the SQL query and the arguments.

        :return: None or a tuple with a SQL query and arguments
        '''
        return None

    def create(self, values):
        super(ModelSQL, self).create(values)
        cursor = Transaction().cursor
        pool = Pool()

        if self.table_query():
            return False

        values = values.copy()

        # Clean values
        for key in ('create_uid', 'create_date', 'write_uid', 'write_date',
                'id'):
            if key in values:
                del values[key]

        # Get default values
        default = []
        avoid_table = []
        for (i, j) in self._inherits.items():
            if j in values:
                avoid_table.append(i)
        for i in self._columns.keys(): # + self._inherit_fields.keys():
            if not i in values \
                    and i not in ('create_uid', 'create_date',
                            'write_uid', 'write_date'):
                default.append(i)
        for i in self._inherit_fields.keys():
            if ((not i in values)
                    and (not self._inherit_fields[i][0] in avoid_table)
                    and i in self._defaults):
                default.append(i)

        if len(default):
            defaults = self.default_get(default, with_rec_name=False)
            for field in defaults.keys():
                if '.' in field:
                    del defaults[field]
                if field in ('create_uid', 'create_date',
                        'write_uid', 'write_date'):
                    del defaults[field]
                if field in values:
                    del defaults[field]
            values.update(self._clean_defaults(defaults))

        (upd0, upd1, upd2) = ('', '', [])
        upd_todo = []

        # Create inherits
        tocreate = {}
        for i in self._inherits:
            if self._inherits[i] not in values:
                tocreate[i] = {}

        for i in values.keys():
            if i in self._inherit_fields:
                (inherits, _, _) = self._inherit_fields[i]
                if i in self._columns:
                    continue
                if inherits in tocreate:
                    tocreate[inherits][i] = values[i]
                del values[i]

        for inherits in tocreate:
            inherits_obj = pool.get(inherits)
            inherits_id = inherits_obj.create(tocreate[inherits])
            values[self._inherits[inherits]] = inherits_id

        # Insert record
        for field in values:
            if not hasattr(self._columns[field], 'set'):
                upd0 = upd0 + ',"' + field + '"'
                upd1 = upd1 + ', %s'
                upd2.append(FIELDS[self._columns[field]._type].sql_format(
                    values[field]))
            else:
                upd_todo.append(field)
            if field in self._columns \
                    and hasattr(self._columns[field], 'selection') \
                    and self._columns[field].selection \
                    and values[field]:
                if self._columns[field]._type == 'reference':
                    val = values[field].split(',')[0]
                else:
                    val = values[field]
                if isinstance(self._columns[field].selection, (tuple, list)):
                    if val not in dict(self._columns[field].selection):
                        raise Exception('ValidateError',
                        'The value "%s" for the field "%s" ' \
                                'is not in the selection' % \
                                (val, field))
                else:
                    if val not in dict(getattr(self,
                        self._columns[field].selection)()):
                        raise Exception('ValidateError',
                        'The value "%s" for the field "%s" ' \
                                'is not in the selection' % \
                                (val, field))
        upd0 += ', create_uid, create_date'
        upd1 += ', %s, %s'
        upd2.append(Transaction().user)
        upd2.append(datetime.datetime.now())
        try:
            if cursor.has_returning():
                cursor.execute('INSERT INTO "' + self._table + '" '
                    '(' + upd0[1:] + ') '
                    'VALUES (' + upd1[1:] + ') RETURNING id',
                    tuple(upd2))
                id_new, = cursor.fetchone()
            else:
                id_new = cursor.nextid(self._table)
                if id_new:
                    cursor.execute('INSERT INTO "' + self._table + '" '
                        '(id' + upd0 + ') '
                        'VALUES (' + str(id_new) + upd1 + ')',
                        tuple(upd2))
                else:
                    cursor.execute('INSERT INTO "' + self._table + '" '
                        '(' + upd0[1:] + ') '
                        'VALUES (' + upd1[1:] + ')',
                        tuple(upd2))
                    id_new = cursor.lastid()
        except DatabaseIntegrityError, exception:
            with contextlib.nested(Transaction().new_cursor(),
                    Transaction().set_user(0)):
                for field_name in self._columns:
                    field = self._columns[field_name]
                    # Check required fields
                    if field.required and \
                            not hasattr(field, 'set') and \
                            not isinstance(field, (fields.Integer,
                                fields.Float)) and \
                            field_name not in ('create_uid', 'create_date'):
                        if not values.get(field_name):
                            self.raise_user_error('required_field',
                                    error_args=self._get_error_args(
                                        field_name))
                    if isinstance(field, fields.Many2One) \
                            and values.get(field_name):
                        model_obj = pool.get(field.model_name)
                        create_records = Transaction().create_records.get(
                                field.model_name, set())
                        delete_records = Transaction().delete_records.get(
                                field.model_name, set())
                        if not ((model_obj.search([
                            ('id', '=', values[field_name]),
                            ], order=[])
                            or values[field_name] in create_records)
                            and values[field_name] not in delete_records):
                            self.raise_user_error('foreign_model_missing',
                                    error_args=self._get_error_args(
                                        field_name))
                for name, _, error in self._sql_constraints:
                    if name in exception[0]:
                        self.raise_user_error(error)
                for name, error in self._sql_error_messages:
                    if name in exception[0]:
                        self.raise_user_error(error)
            raise

        domain1, domain2 = pool.get('ir.rule').domain_get(self._name,
                mode='create')
        if domain1:
            cursor.execute('SELECT id FROM "' + self._table + '" ' \
                    'WHERE id = %s AND (' + domain1 + ')',
                    [id_new] + domain2)
            if not cursor.fetchone():
                self.raise_user_error('access_error', self._description)

        Transaction().create_records.setdefault(self._name, set()).add(id_new)

        for field in values:
            if getattr(self._columns[field], 'translate', False):
                pool.get('ir.translation')._set_ids(
                        self._name + ',' + field, 'model',
                        Transaction().language, [id_new], values[field])

        for field in upd_todo:
            self._columns[field].set([id_new], self, field, values[field])

        if self._history:
            cursor.execute('INSERT INTO "' + self._table + '__history" ' \
                    '(id' + upd0 + ') ' \
                    'SELECT id' + upd0 + ' ' \
                    'FROM "' + self._table + '" ' \
                    'WHERE id = %s',(id_new,))

        self._validate([id_new])

        # Check for Modified Preorder Tree Traversal
        for k in self._columns:
            field = self._columns[k]
            if isinstance(field, fields.Many2One) \
                    and field.model_name == self._name \
                    and field.left and field.right:
                self._update_tree(id_new, k, field.left, field.right)

        self.trigger_create(id_new)

        return id_new

    def read(self, ids, fields_names=None):
        pool = Pool()
        rule_obj = pool.get('ir.rule')
        translation_obj = pool.get('ir.translation')
        super(ModelSQL, self).read(ids, fields_names=fields_names)
        cursor = Transaction().cursor

        if not fields_names:
            fields_names = list(set(self._columns.keys() \
                    + self._inherit_fields.keys()))

        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]

        if not ids:
            return []

        # construct a clause for the rules :
        domain1, domain2 = rule_obj.domain_get(self._name, mode='read')

        fields_related = {}
        datetime_fields = []
        for field_name in fields_names:
            if field_name == '_timestamp':
                continue
            if '.' in field_name:
                field, field_related = field_name.split('.', 1)
                fields_related.setdefault(field, [])
                fields_related[field].append(field_related)
            elif field_name in self._columns:
                field = self._columns[field_name]
            else:
                field = self._inherit_fields[field_name][2]
            if hasattr(field, 'datetime_field') and field.datetime_field:
                datetime_fields.append(field.datetime_field)

        # all inherited fields + all non inherited fields
        fields_pre = [x for x in \
                fields_names + fields_related.keys() + datetime_fields \
                if (x in self._columns and \
                not hasattr(self._columns[x], 'set')) or \
                (x == '_timestamp')] + \
                self._inherits.values()

        res = []
        table_query = ''
        table_args = []

        if self.table_query():
            table_query, table_args = self.table_query()
            table_query = '(' + table_query + ') AS '

        in_max = cursor.IN_MAX
        history_order = ''
        history_clause = ''
        history_limit = ''
        history_args = []
        if (self._history
                and Transaction().context.get('_datetime')
                and not table_query):
            in_max = 1
            table_query = '"' + self._table + '__history" AS '
            history_clause = ' AND (COALESCE(write_date, create_date) <= %s)'
            history_order = ' ORDER BY COALESCE(write_date, create_date) DESC'
            history_limit = cursor.limit_clause('', 1)
            history_args = [Transaction().context['_datetime']]
        if len(fields_pre) :
            fields_pre2 = ['"%s"."%s" AS "%s"' % (self._table, x, x)
                    for x in fields_pre if x != '_timestamp']
            if '_timestamp' in fields_pre:
                if not self.table_query():
                    fields_pre2 += ['CAST(EXTRACT(EPOCH FROM '
                            '(COALESCE("%s".write_date, "%s".create_date))) '
                            'AS VARCHAR) AS _timestamp' %
                            (self._table, self._table)]

            for i in range(0, len(ids), in_max):
                sub_ids = ids[i:i + in_max]
                red_sql, red_ids = reduce_ids('id', sub_ids)
                if domain1:
                    cursor.execute('SELECT ' + \
                            ','.join(fields_pre2 +
                                ['"%s".id AS id' % self._table]) + \
                            ' FROM ' + table_query + '\"' + self._table +'\" ' \
                            'WHERE ' + red_sql  + \
                            history_clause + \
                            ' AND (' + domain1 + ') ' + history_order + \
                            history_limit,
                            table_args + red_ids + history_args + domain2)
                else:
                    cursor.execute('SELECT ' + \
                            ','.join(fields_pre2 +
                                ['"%s".id AS id' % self._table]) + \
                            ' FROM ' + table_query + '\"' + self._table + '\" '\
                            'WHERE ' + red_sql + \
                            history_clause + history_order + history_limit,
                            table_args + red_ids + history_args)
                dictfetchall = cursor.dictfetchall()
                if not len(dictfetchall) == len({}.fromkeys(sub_ids)):
                    if domain1:
                        cursor.execute('SELECT id FROM ' + \
                                table_query + '\"' + self._table + '\" ' \
                                'WHERE ' + red_sql + \
                                history_clause + history_order + history_limit,
                                table_args + red_ids + history_args)
                        rowcount = cursor.rowcount
                        if rowcount == -1 or rowcount is None:
                            rowcount = len(cursor.fetchall())
                        if rowcount == len({}.fromkeys(sub_ids)):
                            self.raise_user_error('access_error',
                                    self._description)
                    self.raise_user_error('read_error', self._description)
                res.extend(dictfetchall)
        else:
            res = [{'id': x} for x in ids]

        for field in fields_pre:
            if field == '_timestamp':
                continue
            if getattr(self._columns[field], 'translate', False):
                ids = [x['id'] for x in res]
                res_trans = translation_obj._get_ids( self._name + ',' + field,
                        'model', Transaction().language, ids)
                for i in res:
                    i[field] = res_trans.get(i['id'], False) or i[field]

        for table in self._inherits:
            field = self._inherits[table]
            inherits_fields = list(
                    set(self._inherit_fields.keys()).intersection(
                    set(fields_names + fields_related.keys() + datetime_fields)
                    ).difference(set(self._columns.keys())))
            if not inherits_fields:
                for record in res:
                    if field not in fields_names + fields_related.keys() + \
                            datetime_fields:
                        del record[field]
                continue
            inherit_related_fields = []
            for inherit_field in inherits_fields:
                if inherit_field in fields_related:
                    for field_related in fields_related[inherit_field]:
                        inherit_related_fields.append(
                                inherit_field + '.' + field_related)
            res2 = pool.get(table).read([x[field] for x in res],
                    fields_names=inherits_fields + inherit_related_fields)

            res3 = {}
            for i in res2:
                res3[i['id']] = i
                del i['id']

            for record in res:
                record.update(res3[record[field]])
                if field not in \
                        fields_names + fields_related.keys() + datetime_fields:
                    del record[field]

        ids = [x['id'] for x in res]

        # all non inherited fields for which there is a get attribute
        fields_post = [x for x in \
                fields_names + fields_related.keys() + datetime_fields \
                if x in self._columns \
                and hasattr(self._columns[x], 'get')]
        func_fields = {}
        for field in fields_post:
            if isinstance(self._columns[field], fields.Function):
                key = (self._columns[field].getter,
                        getattr(self._columns[field], 'datetime_field', None))
                func_fields.setdefault(key, [])
                func_fields[key].append(field)
                continue
            if hasattr(self._columns[field], 'datetime_field') \
                    and self._columns[field].datetime_field:
                for record in res:
                    with Transaction().set_context(_datetime=
                            record[self._columns[field].datetime_field]):
                        res2 = self._columns[field].get( [record['id']], self,
                                field, values=[record])
                    record[field] = res2[record['id']]
                continue
            # get the value of that field for all records/ids
            res2 = self._columns[field].get(ids, self, field, values=res)
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
                        res2 = self._columns[field].get([record['id']], self,
                                field_list, values=[record])
                    for field in res2:
                        record[field] = res2[field][record['id']]
                continue
            res2 = self._columns[field].get(ids, self, field_list, values=res)
            for field in res2:
                for record in res:
                    record[field] = res2[field][record['id']]

        to_del = set()
        fields_related2values = {}
        for field in fields_related.keys() + datetime_fields:
            if field not in fields_names:
                to_del.add(field)
            if field not in self._columns:
                continue
            if field not in fields_related.keys():
                continue
            fields_related2values.setdefault(field, {})
            if self._columns[field]._type in ('many2one', 'one2one'):
                if hasattr(self._columns[field], 'model_name'):
                    obj = pool.get(self._columns[field].model_name)
                else:
                    obj = self._columns[field].get_target()
                if hasattr(self._columns[field], 'datetime_field') \
                        and self._columns[field].datetime_field:
                    for record in res:
                        if not record[field]:
                            continue
                        with Transaction().set_context(_datetime=
                                record[self._columns[field].datetime_field]):
                            record2 = obj.read(record[field],
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
                            fields_related2values[field][record_id]\
                                    [record2['id']] = record
            elif self._columns[field]._type == 'reference':
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
                    record2 = obj.read(record_id, fields_related[field])
                    del record2['id']
                    fields_related2values[field][record_id] = record2

        if to_del or fields_related.keys() or datetime_fields:
            for record in res:
                for field in fields_related.keys():
                    if field not in self._columns:
                        continue
                    for related in fields_related[field]:
                        if self._columns[field]._type in ('many2one', 'one2one'):
                            if record[field]:
                                record[field + '.' + related] = \
                                        fields_related2values[field]\
                                        [record[field]][record['id']][related]
                            else:
                                record[field + '.' + related] = False
                        elif self._columns[field]._type == 'reference':
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
                                                record_id][related]
                for field in to_del:
                    del record[field]

        if int_id:
            return res[0]
        return res

    def write(self, ids, values):
        cursor = Transaction().cursor
        pool = Pool()
        translation_obj = pool.get('ir.translation')

        # Call before cursor cache cleaning
        trigger_eligibles = self.trigger_write_get_eligibles(
                isinstance(ids, (int, long)) and [ids] or ids)

        super(ModelSQL, self).write(ids, values)

        if not ids:
            return True

        if self.table_query():
            return True

        values = values.copy()

        if isinstance(ids, (int, long)):
            ids = [ids]
        else:
            # _update_tree works if only one record has changed
            update_tree = False
            for k in self._columns:
                field = self._columns[k]
                if isinstance(field, fields.Many2One) \
                        and field.model_name == self._name \
                        and field.left and field.right:
                    update_tree = True
            if update_tree:
                for object_id in ids:
                    self.write(object_id, values)
                return True

        if Transaction().timestamp:
            for i in range(0, len(ids), cursor.IN_MAX):
                sub_ids = ids[i:i + cursor.IN_MAX]
                clause = ('(id = %s AND '
                        'CAST(EXTRACT(EPOCH FROM '
                        'COALESCE(write_date, create_date)) AS ' + \
                        FIELDS['numeric'].sql_type(self.create_date)[1] + \
                        ') > %s)')
                args = []
                for i in sub_ids:
                    if Transaction().timestamp.get(self._name + ',' + str(i)):
                        args.append(i)
                        args.append(Decimal(Transaction().timestamp[
                            self._name + ',' +str(i)]))
                if args:
                    cursor.execute("SELECT id " \
                            'FROM "' + self._table + '" ' \
                            'WHERE ' + ' OR '.join(
                                (clause,) * (len(args) // 2)), args)
                    if cursor.fetchone():
                        raise ConcurrencyException(
                            'Records were modified in the meanwhile')
            for i in ids:
                if Transaction().timestamp.get(self._name + ',' + str(i)):
                    del Transaction().timestamp[self._name + ',' +str(i)]

        # Clean values
        for key in ('create_uid', 'create_date', 'write_uid', 'write_date',
                'id'):
            if key in values:
                del values[key]

        upd0 = []
        upd1 = []
        upd_todo = []
        updend = []
        direct = []
        for field in values:
            if field in self._columns:
                if not hasattr(self._columns[field], 'set'):
                    if ((not getattr(self._columns[field], 'translate', False))
                            or (Transaction().language == 'en_US')):
                        upd0.append(('"' + field + '"', '%s'))
                        upd1.append(FIELDS[self._columns[field]._type]\
                                .sql_format(values[field]))
                    direct.append(field)
                else:
                    upd_todo.append(field)
            else:
                updend.append(field)
            if field in self._columns \
                    and hasattr(self._columns[field], 'selection') \
                    and self._columns[field].selection \
                    and values[field]:
                if self._columns[field]._type == 'reference':
                    val = values[field].split(',')[0]
                else:
                    val = values[field]
                if isinstance(self._columns[field].selection, (tuple, list)):
                    if val not in dict(self._columns[field].selection):
                        raise Exception('ValidateError',
                        'The value "%s" for the field "%s" ' \
                                'is not in the selection' % \
                                (val, field))
                else:
                    if val not in dict(getattr(self,
                        self._columns[field].selection)()):
                        raise Exception('ValidateError',
                        'The value "%s" for the field "%s" ' \
                                'is not in the selection' % \
                                (val, field))

        upd0.append(('write_uid', '%s'))
        upd0.append(('write_date', '%s'))
        upd1.append(Transaction().user)
        upd1.append(datetime.datetime.now())

        domain1, domain2 = pool.get('ir.rule').domain_get(self._name,
                mode='write')
        if domain1:
            domain1 = ' AND (' + domain1 + ') '
        for i in range(0, len(ids), cursor.IN_MAX):
            sub_ids = ids[i:i + cursor.IN_MAX]
            red_sql, red_ids = reduce_ids('id', sub_ids)
            if domain1:
                cursor.execute('SELECT id FROM "' + self._table + '" ' \
                        'WHERE ' + red_sql + ' ' + domain1,
                        red_ids + domain2)
            else:
                cursor.execute('SELECT id FROM "' + self._table + '" ' \
                        'WHERE ' + red_sql, red_ids)
            rowcount = cursor.rowcount
            if rowcount == -1 or rowcount is None:
                rowcount = len(cursor.fetchall())
            if not rowcount == len({}.fromkeys(sub_ids)):
                if domain1:
                    cursor.execute('SELECT id FROM "' + self._table + '" ' \
                            'WHERE ' + red_sql, red_ids)
                    rowcount = cursor.rowcount
                    if rowcount == -1 or rowcount is None:
                        rowcount = len(cursor.fetchall())
                    if rowcount == len({}.fromkeys(sub_ids)):
                        self.raise_user_error('access_error',
                                self._description)
                self.raise_user_error('write_error', self._description)
            try:
                cursor.execute('UPDATE "' + self._table + '" ' \
                        'SET ' + \
                        ','.join([x[0] + ' = '+ x[1] for x in upd0]) + ' ' \
                        'WHERE ' + red_sql, upd1 + red_ids)
            except DatabaseIntegrityError, exception:
                with contextlib.nested(Transaction().new_cursor(),
                        Transaction().set_user(0)):
                    for field_name in values:
                        if field_name not in self._columns:
                            continue
                        field = self._columns[field_name]
                        # Check required fields
                        if field.required and \
                                not hasattr(field, 'set') and \
                                not isinstance(field, (fields.Integer,
                                    fields.Float)) and \
                                field_name not in ('create_uid',
                                    'create_date'):
                            if not values[field_name]:
                                self.raise_user_error('required_field',
                                        error_args=self._get_error_args(
                                            field_name))
                        if isinstance(field, fields.Many2One) \
                                and values[field_name]:
                            model_obj = pool.get(field.model_name)
                            create_records = Transaction().create_records.get(
                                    field.model_name, set())
                            delete_records = Transaction().delete_records.get(
                                    field.model_name, set())
                            if not ((model_obj.search([
                                ('id', '=', values[field_name]),
                                ], order=[])
                                or values[field_name] in create_records)
                                and values[field_name] not in delete_records):
                                self.raise_user_error( 'foreign_model_missing',
                                        error_args=self._get_error_args(
                                            field_name))
                    for name, _, error in self._sql_constraints:
                        if name in exception[0]:
                            self.raise_user_error(error)
                    for name, error in self._sql_error_messages:
                        if name in exception[0]:
                            self.raise_user_error(error)
                raise

        for field in direct:
            if getattr(self._columns[field], 'translate', False):
                translation_obj._set_ids(
                        self._name + ',' + field, 'model',
                        Transaction().language, ids, values[field])

        # call the 'set' method of fields
        for field in upd_todo:
            self._columns[field].set(ids, self, field, values[field])

        if self._history:
            columns = ['"' + str(x) + '"' for x in self._columns
                    if not hasattr(self._columns[x], 'set')]
            for obj_id in ids:
                cursor.execute('INSERT INTO "' + self._table + '__history" ' \
                        '(' + ','.join(columns) + ') ' \
                        'SELECT ' + ','.join(columns) + ' ' + \
                        'FROM "' + self._table + '" ' \
                        'WHERE id = %s', (obj_id,))

        for table in self._inherits:
            col = self._inherits[table]
            nids = []
            for i in range(0, len(ids), cursor.IN_MAX):
                sub_ids = ids[i:i + cursor.IN_MAX]
                red_sql, red_ids = reduce_ids('id', sub_ids)
                cursor.execute('SELECT DISTINCT "' + col + '" ' \
                        'FROM "' + self._table + '" WHERE ' + red_sql,
                        red_ids)
                nids.extend([x[0] for x in cursor.fetchall()])

            values2 = {}
            for val in updend:
                if self._inherit_fields[val][0] == table:
                    values2[val] = values[val]
            pool.get(table).write(nids, values2)

        self._validate(ids)

        # Check for Modified Preorder Tree Traversal
        for k in self._columns:
            field = self._columns[k]
            if isinstance(field, fields.Many2One) \
                    and field.model_name == self._name \
                    and field.left and field.right:
                if field.left in values or field.right in values:
                    raise Exception('ValidateError',
                            'You can not update fields: "%s", "%s"' %
                            (field.left, field.right))
                if len(ids) == 1:
                    self._update_tree(ids[0], k, field.left, field.right)
                else:
                    with Transaction().set_user(0):
                        self._rebuild_tree(k, False, 0)

        self.trigger_write(trigger_eligibles)

        return True

    def delete(self, ids):
        cursor = Transaction().cursor
        pool = Pool()
        if not ids:
            return True

        if self.table_query():
            return True

        if isinstance(ids, (int, long)):
            ids = [ids]

        if Transaction().delete and Transaction().delete.get(self._name):
            ids = ids[:]
            for del_id in Transaction().delete[self._name]:
                for i in range(ids.count(del_id)):
                    ids.remove(del_id)

        if Transaction().timestamp:
            for i in range(0, len(ids), cursor.IN_MAX):
                sub_ids = ids[i:i + cursor.IN_MAX]
                clause = ('(id = %s AND '
                        'CAST(EXTRACT(EPOCH FROM '
                        'COALESCE(write_date, create_date)) AS ' + \
                        FIELDS['numeric'].sql_type(self.create_date)[1] + \
                        ') > %s)')
                args = []
                for i in sub_ids:
                    if Transaction().timestamp.get(self._name + ',' + str(i)):
                        args.append(i)
                        args.append(Transaction().timestamp[
                            self._name + ',' +str(i)])
                if args:
                    cursor.execute("SELECT id " \
                            'FROM "' + self._table + '" ' \
                            'WHERE ' + ' OR '.join(
                                (clause,) * (len(args)/2)), args)
                    if cursor.fetchone():
                        raise ConcurrencyException(
                            'Records were modified in the meanwhile')
            for i in ids:
                if Transaction().timestamp.get(self._name + ',' + str(i)):
                    del Transaction().timestamp[self._name + ',' +str(i)]

        tree_ids = {}
        for k in self._columns:
            field = self._columns[k]
            if isinstance(field, fields.Many2One) \
                    and field.model_name == self._name \
                    and field.left and field.right:
                red_sql, red_ids = reduce_ids('"' + k + '"', ids)
                cursor.execute('SELECT id FROM "' + self._table + '" '\
                        'WHERE ' + red_sql, red_ids)
                tree_ids[k] = [x[0] for x in cursor.fetchall()]

        foreign_keys_tocheck = []
        foreign_keys_toupdate = []
        foreign_keys_todelete = []
        for _, model in pool.iterobject():
            if hasattr(model, 'table_query') \
                    and model.table_query():
                continue
            if not isinstance(model, ModelStorage):
                continue
            for field_name, field in model._columns.iteritems():
                if isinstance(field, fields.Many2One) \
                        and field.model_name == self._name:
                    if field.ondelete == 'CASCADE':
                        foreign_keys_todelete.append((model, field_name))
                    elif field.ondelete == 'SET NULL':
                        if field.required:
                            foreign_keys_tocheck.append((model, field_name))
                        else:
                            foreign_keys_toupdate.append((model, field_name))
                    else:
                        foreign_keys_tocheck.append((model, field_name))

        Transaction().delete.setdefault(self._name, set()).update(ids)

        domain1, domain2 = pool.get('ir.rule').domain_get(self._name,
                mode='delete')
        if domain1:
            domain1 = ' AND (' + domain1 + ') '

        for i in range(0, len(ids), cursor.IN_MAX):
            sub_ids = ids[i:i + cursor.IN_MAX]
            red_sql, red_ids = reduce_ids('id', sub_ids)
            if domain1:
                cursor.execute('SELECT id FROM "'+self._table+'" ' \
                        'WHERE ' + red_sql + ' ' + domain1,
                        red_ids + domain2)
                rowcount = cursor.rowcount
                if rowcount == -1 or rowcount is None:
                    rowcount = len(cursor.fetchall())
                if not rowcount == len({}.fromkeys(sub_ids)):
                    self.raise_user_error('access_error', self._description)

        self.trigger_delete(ids)

        for i in range(0, len(ids), cursor.IN_MAX):
            sub_ids = ids[i:i + cursor.IN_MAX]
            red_sql, red_ids = reduce_ids('id', sub_ids)

            Transaction().delete_records.setdefault(self._name,
                    set()).update(sub_ids)

            for model, field_name in foreign_keys_toupdate:
                if not hasattr(model, 'search') \
                        or not hasattr(model, 'write'):
                    continue
                red_sql2, red_ids2 = reduce_ids('"' + field_name + '"', sub_ids)
                cursor.execute('SELECT id FROM "' + model._table + '" ' \
                        'WHERE ' + red_sql2, red_ids2)
                model_ids = [x[0] for x in cursor.fetchall()]
                if model_ids:
                    model.write(model_ids, {
                        field_name: False,
                        })

            for model, field_name in foreign_keys_todelete:
                if not hasattr(model, 'search') \
                        or not hasattr(model, 'delete'):
                    continue
                red_sql2, red_ids2 = reduce_ids('"' + field_name + '"', sub_ids)
                cursor.execute('SELECT id FROM "' + model._table + '" ' \
                        'WHERE ' + red_sql2, red_ids2)
                model_ids = [x[0] for x in cursor.fetchall()]
                if model_ids:
                    model.delete(model_ids)

            for model, field_name in foreign_keys_tocheck:
                with Transaction().set_user(0):
                    if model.search([
                        (field_name, 'in', sub_ids),
                        ], order=[]):
                        error_args = []
                        error_args.append(self._get_error_args('id')[1])
                        error_args.extend(list(
                            model._get_error_args(field_name)))
                        self.raise_user_error('foreign_model_exist',
                                error_args=tuple(error_args))

            super(ModelSQL, self).delete(sub_ids)

            try:
                cursor.execute('DELETE FROM "'+self._table+'" ' \
                        'WHERE ' + red_sql, red_ids)
            except DatabaseIntegrityError, exception:
                with Transaction().new_cursor():
                    for name, _, error in self._sql_constraints:
                        if name in exception[0]:
                            self.raise_user_error(error)
                    for name, error in self._sql_error_messages:
                        if name in exception[0]:
                            self.raise_user_error(error)
                raise

        if self._history:
            for obj_id in ids:
                cursor.execute('INSERT INTO "' + self._table + '__history" ' \
                        '(id, write_uid, write_date) VALUES (%s, %s, %s)',
                        (obj_id, Transaction().user, datetime.datetime.now()))

        for k in tree_ids.keys():
            field = self._columns[k]
            if len(tree_ids[k]) == 1:
                self._update_tree(tree_ids[k][0], k, field.left, field.right)
            else:
                with Transaction().set_user(0):
                    self._rebuild_tree(k, False, 0)

        return True

    def search(self, domain, offset=0, limit=None, order=None, count=False,
            query_string=False):
        pool = Pool()
        rule_obj = pool.get('ir.rule')
        cursor = Transaction().cursor

        # Get domain clauses
        qu1, qu2, tables, tables_args = self.search_domain(domain)

        # Get order by
        order_by = []
        if order is None or order is False:
            order = self._order
        for field, otype in order:
            if otype.upper() not in ('DESC', 'ASC'):
                raise Exception('Error', 'Wrong order type (%s)!' % otype)
            order_by2, tables2, tables2_args = self._order_calc(field, otype)
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
        domain1, domain2 = rule_obj.domain_get(self._name, mode='read')
        if domain1:
            if qu1:
                qu1 += ' AND ' + domain1
            else:
                qu1 = domain1
            qu2 += domain2

        if count:
            cursor.execute(cursor.limit_clause(
                'SELECT COUNT("%s".id) FROM ' % self._table +
                    ' '.join(tables) + (qu1 and ' WHERE ' + qu1 or ''),
                    limit, offset), tables_args + qu2)
            res = cursor.fetchall()
            return res[0][0]
        # execute the "main" query to fetch the ids we were searching for
        select_fields = ['"' + self._table + '".id AS id']
        if self._history and Transaction().context.get('_datetime') \
                and not query_string:
            select_fields += ['COALESCE("' + self._table + '".write_date, "' + \
                    self._table + '".create_date) AS _datetime']
        if not query_string:
            select_fields += [
                    '"' + self._table + '"."' + name + '" AS "' + name + '"' \
                    for name, field in self._columns.iteritems() \
                    if not hasattr(field, 'get')
                    and name != 'id'
                    and not getattr(field, 'translate', False)
                    and field.loading == 'eager']
            if not self.table_query():
                select_fields += ['CAST(EXTRACT(EPOCH FROM '
                        '(COALESCE("' + self._table + '".write_date, '
                        '"' + self._table + '".create_date))) AS VARCHAR'
                        ') AS _timestamp']
        query_str = cursor.limit_clause(
                'SELECT ' + ','.join(select_fields) + ' FROM ' + \
                ' '.join(tables) + (qu1 and ' WHERE ' + qu1 or '') + \
                (order_by and ' ORDER BY ' + order_by or ''), limit, offset)
        if query_string:
            return (query_str, tables_args + qu2)
        cursor.execute(query_str, tables_args + qu2)

        datas = cursor.dictfetchmany(cursor.IN_MAX)
        cache = cursor.get_cache()
        cache.setdefault(self._name, LRUDict(RECORD_CACHE_SIZE))
        delete_records = Transaction().delete_records.setdefault(self._name,
                set())
        keys = None
        for data in islice(datas, 0, cache.size_limit):
            if data['id'] in delete_records:
                continue
            if not keys:
                keys = data.keys()
                for k in keys[:]:
                    if k in ('_timestamp', '_datetime'):
                        keys.remove(k)
                        continue
                    field = self._columns[k]
                    if field._type not in ('many2one',):
                        keys.remove(k)
                        continue
            for k in keys:
                del data[k]
            cache[self._name].setdefault(data['id'], {}).update(data)

        if len(datas) >= cursor.IN_MAX:
            select_fields2 = [select_fields[0]]
            if (self._history
                    and Transaction().context.get('_datetime')
                    and not query_string):
                select_fields2 += [select_fields[1]]
            cursor.execute(
                'SELECT * FROM (' + \
                    cursor.limit_clause(
                        'SELECT ' + ','.join(select_fields2) + ' FROM ' + \
                        ' '.join(tables) + (qu1 and ' WHERE ' + qu1 or '') + \
                        (order_by and ' ORDER BY ' + order_by or ''),
                        limit, offset) + ') AS "' + self._table + '"',
                    tables_args + qu2)
            datas = cursor.dictfetchall()

        if self._history and Transaction().context.get('_datetime'):
            res = []
            ids_date = {}
            for data in datas:
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
                        ) % (self._table, reduced_sql),
                    reduced_ids)
                for deleted_id, delete_date in cursor.fetchall():
                    if ids_date[deleted_id] < delete_date:
                        to_delete.add(deleted_id)
            return filter(lambda x: x not in to_delete, res)

        return [x['id'] for x in datas]

    def search_domain(self, domain, active_test=True):
        '''
        Return SQL clause and arguments for the domain

        :param domain: a domain like in search
        :param active_test: a boolean to add 'active' test
        :return: a tuple with
            - a SQL clause string
            - a list of arguments for the SQL clause
            - a list of tables used in the SQL clause
            - a list of arguments for the tables
        '''
        domain = self._search_domain_active(domain, active_test=active_test)

        table_query = ''
        tables_args = []
        if self.table_query():
            table_query, tables_args = self.table_query()
            table_query = '(' + table_query + ') AS '

        if self._history and Transaction().context.get('_datetime'):
            table_query = '"' + self._table + '__history" AS '

        tables = [table_query + '"' + self._table + '"']

        qu1, qu2 = self.__search_domain_oper(domain, tables, tables_args)
        if self._history and Transaction().context.get('_datetime'):
            if qu1:
                qu1 += ' AND'
            qu1 += ' (COALESCE("' + self._table + '".write_date, "' + \
                    self._table + '".create_date) <= %s)'
            qu2 += [Transaction().context['_datetime']]
        return qu1, qu2, tables, tables_args

    def __search_domain_oper(self, domain, tables, tables_args):
        pool = Pool()
        operator = 'AND'
        if len(domain) and isinstance(domain[0], basestring):
            if domain[0] not in ('AND', 'OR'):
                raise Exception('ValidateError', 'Operator "%s" not supported' \
                        % domain[0])
            operator = domain[0]
            domain = domain[1:]
        tuple_args = []
        list_args = []
        for arg in domain:
            #add test for xmlrpc that doesn't handle tuple
            if isinstance(arg, tuple) \
                    or (isinstance(arg, list) and len(arg) > 2 \
                    and arg[1] in OPERATORS):
                tuple_args.append(tuple(arg))
            elif isinstance(arg, list):
                list_args.append(arg)

        qu1, qu2 = self.__search_domain_calc(tuple_args, tables, tables_args)
        if len(qu1):
            qu1 = (' ' + operator + ' ').join(qu1)
        else:
            qu1 = ''

        for domain2 in list_args:
            qu1b, qu2b = self.__search_domain_oper(domain2, tables,
                    tables_args)
            if not qu1b:
                qu1b = FIELDS['boolean'].sql_format(True)
            if qu1 and qu1b:
                qu1 += ' ' + operator + ' ' + qu1b
            elif qu1b:
                qu1 = qu1b
            qu2 += qu2b
        if qu1:
            qu1 = '(' + qu1 + ')'
        return qu1, qu2

    def __search_domain_calc(self, domain, tables, tables_args):
        pool = Pool()
        domain = domain[:]
        cursor = Transaction().cursor

        for arg in domain:
            if arg[1] not in OPERATORS:
                raise Exception('ValidateError', 'Argument "%s" not supported' \
                        % arg[1])
        i = 0
        joins = []
        while i < len(domain):
            table = self
            fargs = domain[i][0].split('.', 1)
            if fargs[0] in self._inherit_fields:
                itable = pool.get(self._inherit_fields[fargs[0]][0])
                table_query = ''
                table_arg = []
                if itable.table_query():
                    table_query, table_args = self.table_query()
                    table_query = '(' + table_query + ') AS '
                table_join = 'LEFT JOIN ' + table_query + \
                        '"' + itable._table + '" ON ' \
                        '"%s".id = "%s"."%s"' % (itable._table, self._table,
                                self._inherits[itable._name])
                if table_join not in tables:
                    tables.append(table_join)
                    tables_args.extend(table_arg)
            field = table._columns.get(fargs[0], False)
            if not field:
                if not fargs[0] in self._inherit_fields:
                    raise Exception('ValidateError', 'Field "%s" doesn\'t ' \
                            'exist on "%s"' % (fargs[0], self._name))
                table = pool.get(self._inherit_fields[fargs[0]][0])
                field = table._columns.get(fargs[0], False)
            if len(fargs) > 1:
                if field._type == 'many2one':
                    target_obj = pool.get(field.model_name)
                    m2o_search = [(fargs[1], domain[i][1], domain[i][2])]
                    if ('active' in target_obj._columns
                            or 'active' in target_obj._inherit_fields):
                        m2o_search += [('active', 'in', (True, False))]
                    if hasattr(field, 'search'):
                        domain.extend([(fargs[0], 'in',
                                    target_obj.search(m2o_search, order=[]))])
                        domain.pop(i)
                    else:
                        domain[i] = (fargs[0], 'inselect',
                            target_obj.search(m2o_search, order=[],
                                query_string=True), table)
                        i += 1
                    continue
                elif field._type in ('one2one', 'many2many', 'one2many'):
                    if hasattr(field, 'model_name'):
                        target_obj = pool.get(field.model_name)
                    else:
                        target_obj = field.get_target()
                    if hasattr(field, 'relation_name'):
                        relation_obj = pool.get(field.relation_name)
                        origin, target = field.origin, field.target
                    else:
                        relation_obj = target_obj
                        origin, target = field.field, 'id'
                    if hasattr(field, 'search'):
                        domain.extend([(fargs[0], 'in', target_obj.search([
                            (fargs[1], domain[i][1], domain[i][2]),
                            ], order=[]))])
                        domain.pop(i)
                    else:
                        query1, query2 = target_obj.search([
                            (fargs[1], domain[i][1], domain[i][2]),
                            ], order=[], query_string=True)
                        query1 = ('SELECT "%s" FROM "%s" WHERE "%s" IN (%s)' %
                                (origin, relation_obj._table, target, query1))
                        domain[i] = ('id', 'inselect', (query1, query2))
                        i += 1
                    continue
                else:
                    raise Exception('ValidateError', 'Clause on field "%s" ' \
                            'doesn\'t work on "%s"' %
                            (domain[i][0], self._name))
            if hasattr(field, 'search'):
                clause = domain.pop(i)
                domain.extend(field.search(table, clause[0], clause))
            elif field._type == 'one2many':
                field_obj = pool.get(field.model_name)

                if isinstance(domain[i][2], basestring):
                    # get the ids of the records of the "distant" resource
                    ids2 = [x[0] for x in field_obj.search([
                        ('rec_name', domain[i][1], domain[i][2]),
                        ], order=[])]
                else:
                    ids2 = domain[i][2]

                table_query = ''
                table_args = []
                if field_obj.table_query():
                    table_query, table_args = field_obj.table_query()
                    table_query = '(' + table_query + ') AS '

                if ids2 == True or ids2 == False:
                    query1 = 'SELECT "' + field.field + '" ' \
                            'FROM ' + table_query + \
                                '"' + field_obj._table + '" ' \
                            'WHERE "' + field.field + '" IS NOT NULL'
                    query2 = table_args
                    clause = 'inselect'
                    if ids2 == False:
                        clause = 'notinselect'
                    domain[i] = ('id', clause, (query1, query2))
                elif not ids2:
                    domain[i] = ('id', '=', '0')
                else:
                    if len(ids2) < cursor.IN_MAX:
                        red_sql, red_ids = reduce_ids('id', ids2)
                        query1 = 'SELECT "' + field.field + '" ' \
                                'FROM ' + table_query + \
                                    '"' + field_obj._table + '" ' \
                                'WHERE ' + red_sql
                        query2 = table_args + red_ids
                        domain[i] = ('id', 'inselect', (query1, query2))
                    else:
                        ids3 = []
                        for i in range(0, len(ids2), cursor.IN_MAX):
                            sub_ids2 = ids2[i:i + cursor.IN_MAX]
                            red_sql, red_ids = reduce_ids('id', sub_ids2)
                            cursor.execute(
                                'SELECT "' + field.field + '" ' \
                                'FROM ' + table_query + \
                                    '"' + field_obj._table + '" ' \
                                'WHERE ' + red_sql,
                                table_args + red_ids)

                            ids3.extend([x[0] for x in cursor.fetchall()])

                        domain[i] = ('id', 'in', ids3)
                i += 1
            elif field._type in ('many2many', 'one2one'):
                # XXX must find a solution for long id list
                if hasattr(field, 'model_name'):
                    target_obj = pool.get(field.model_name)
                else:
                    target_obj = field.get_target()
                if domain[i][1] in ('child_of', 'not child_of'):
                    if isinstance(domain[i][2], basestring):
                        ids2 = [x[0] for x in target_obj.search([
                            ('rec_name', 'ilike', domain[i][2]),
                            ], order=[])]
                    elif isinstance(domain[i][2], (int, long)):
                        ids2 = [domain[i][2]]
                    else:
                        ids2 = domain[i][2]

                    def _rec_get(ids, table, parent):
                        if not ids:
                            return []
                        ids2 = table.search([
                            (parent, 'in', ids),
                            (parent, '!=', False),
                            ], order=[])
                        return ids + _rec_get(ids2, table, parent)

                    if target_obj._name != table._name:
                        if len(domain[i]) != 4:
                            raise Exception('Error', 'Programming error: ' \
                                    'child_of on field "%s" is not allowed!' % \
                                    (domain[i][0],))
                        ids2 = target_obj.search([
                            (domain[i][3], 'child_of', ids2),
                            ], order=[])
                        relation_obj = pool.get(field.relation_name)
                        red_sql, red_ids = reduce_ids('"' + field.target + '"',
                                ids2)
                        query1 = 'SELECT "' + field.origin + '" ' \
                                'FROM "' + relation_obj._table + '" ' \
                                'WHERE ' + red_sql + ' ' \
                                    'AND "' + field.origin + '" IS NOT NULL'
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
                    if isinstance(domain[i][2], bool):
                        relation_obj = pool.get(field.relation_name)
                        query1 = 'SELECT "' + field.origin + '" ' \
                                'FROM "' + relation_obj._table + '" '\
                                'WHERE "' + field.origin + '" IS NOT NULL'
                        query2 = []
                        clause = 'inselect'
                        if domain[i][2] == False:
                            clause = 'notinselect'
                        domain[i] = ('id', clause, (query1, query2))
                    else:
                        if isinstance(domain[i][2], basestring):
                            target_field = 'rec_name'
                        else:
                            target_field = 'id'
                        relation_obj = pool.get(field.relation_name)

                        query1, query2 = target_obj.search([
                                    (target_field, domain[i][1], domain[i][2]),
                                    ], order=[], query_string=True)
                        query1 = ('SELECT "%s" FROM "%s" WHERE "%s" IN (%s)' %
                                (field.origin, relation_obj._table,
                                    field.target, query1))
                        domain[i] = ('id', 'inselect', (query1, query2))
                i += 1

            elif field._type == 'many2one':
                # XXX must find a solution for long id list
                if domain[i][1] in ('child_of', 'not child_of'):
                    if isinstance(domain[i][2], basestring):
                        field_obj = pool.get(field.model_name)
                        ids2 = [x[0] for x in field_obj.search([
                            ('rec_name', 'like', domain[i][2]),
                            ], order=[])]
                    elif isinstance(domain[i][2], (int, long)):
                        ids2 = [domain[i][2]]
                    else:
                        ids2 = domain[i][2]

                    def _rec_get(ids, table, parent):
                        if not ids:
                            return []
                        ids2 = table.search([
                            (parent, 'in', ids),
                            (parent, '!=', False),
                            ])
                        return ids + _rec_get(ids2, table, parent)

                    if field.model_name != table._name:
                        if len(domain[i]) != 4:
                            raise Exception('Error', 'Programming error: ' \
                                    'child_of on field "%s" is not allowed!' % \
                                    (domain[i][0],))
                        ids2 = pool.get(field.model_name).search([
                            (domain[i][3], 'child_of', ids2),
                            ], order=[])
                        if domain[i][1] == 'child_of':
                            domain[i] = (domain[i][0], 'in', ids2, table)
                        else:
                            domain[i] = (domain[i][0], 'not in', ids2, table)
                    else:
                        if field.left and field.right and ids2:
                            red_sql, red_ids = reduce_ids('id', ids2)
                            cursor.execute('SELECT "' + field.left + '", ' \
                                        '"' + field.right + '" ' + \
                                    'FROM "' + self._table + '" ' + \
                                    'WHERE ' + red_sql, red_ids)
                            clause = FIELDS['boolean'].sql_format(False) + ' '
                            for left, right in cursor.fetchall():
                                clause += 'OR '
                                clause += '( "' + field.left + '" >= ' + \
                                        str(left) + ' ' + \
                                        'AND "' + field.right + '" <= ' + \
                                        str(right) + ')'

                            query = 'SELECT id FROM "' + self._table + '" ' + \
                                    'WHERE ' + clause
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
                        field_obj = pool.get(field.model_name)
                        m2o_search = [('rec_name', domain[i][1], domain[i][2])]
                        if ('active' in field_obj._columns
                                or 'active' in field_obj._inherit_fields):
                            m2o_search += [('active', 'in', (True, False))]
                        res_ids = field_obj.search(m2o_search, order=[])
                        domain[i] = (domain[i][0], 'in', res_ids, table)
                    else:
                        domain[i] += (table,)
                i += 1
            else:
                if getattr(field, 'translate', False):
                    if self._name == 'ir.model':
                        table_join = 'LEFT JOIN "ir_translation" ' \
                                'ON (ir_translation.name = ' \
                                        'ir_model.model||\',%s\' ' \
                                    'AND ir_translation.res_id = 0 ' \
                                    'AND ir_translation.lang = %%s ' \
                                    'AND ir_translation.type = \'model\' ' \
                                    'AND ir_translation.fuzzy = %s)' % \
                                (domain[i][0],
                                        FIELDS['boolean'].sql_format(False))
                    elif self._name == 'ir.model.field':
                        if domain[i][0] == 'field_description':
                            ttype = 'field'
                        else:
                            ttype = 'help'
                        table_join = 'LEFT JOIN "ir_model" ' \
                                'ON ir_model.id = ir_model_field.model ' \
                                'LEFT JOIN "ir_translation" ' \
                                'ON (ir_translation.name = ' \
                                        'ir_model.model||\',\'||%s.name ' \
                                    'AND ir_translation.res_id = 0 ' \
                                    'AND ir_translation.lang = %%s ' \
                                    'AND ir_translation.type = \'%s\' ' \
                                    'AND ir_translation.fuzzy = %s)' % \
                                (table._table, ttype,
                                        FIELDS['boolean'].sql_format(False))
                    else:
                        table_join = 'LEFT JOIN "ir_translation" ' \
                                'ON (ir_translation.res_id = %s.id ' \
                                    'AND ir_translation.name = \'%s,%s\' ' \
                                    'AND ir_translation.lang = %%s ' \
                                    'AND ir_translation.type = \'model\' ' \
                                    'AND ir_translation.fuzzy = %s)' % \
                                (table._table, table._name, domain[i][0],
                                        FIELDS['boolean'].sql_format(False))
                    table_join_args = [Transaction().language]

                    table_query = ''
                    table_args = []
                    if table.table_query():
                        table_query, table_args = table.table_query()
                        table_query = '(' + table_query  + ') AS '

                    translation_obj = pool.get('ir.translation')

                    qu1, qu2, tables, table_args = \
                            translation_obj.search_domain([
                                ('value', domain[i][1], domain[i][2]),
                                ])
                    qu1 = qu1.replace('"ir_translation"."value"',
                            'COALESCE(NULLIF("ir_translation"."value", \'\'), '
                            '"%s"."%s")' % (table._table, domain[i][0]))
                    query1 = 'SELECT "' + table._table + '".id ' \
                            'FROM ' + table_query + '"' + table._table + '" ' \
                            + table_join + ' WHERE ' + qu1
                    query2 = table_args + table_join_args + qu2

                    domain[i] = ('id', 'inselect', (query1, query2), table)
                else:
                    domain[i] += (table,)
                i += 1
        domain.extend(joins)

        qu1, qu2 = [], []
        for arg in domain:
            table = self
            if len(arg) > 3:
                table = arg[3]
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
                    if table._columns[arg[0]]._type != 'boolean':
                        for xitem in range(len(arg[2])):
                            if arg[2][xitem] == False \
                                    and isinstance(arg[2][xitem],bool):
                                todel.append(xitem)
                    arg2 = arg[2][:]
                    for xitem in todel[::-1]:
                        del arg2[xitem]
                    arg2 = [FIELDS[table._columns[arg[0]]._type].sql_format(x)
                            for x in arg2]
                    if len(arg2):
                        if reduce(lambda x, y: x and isinstance(y, (int, long)),
                                arg2, True):
                            red_sql, red_ids = reduce_ids('"%s"."%s"' % \
                                    (table._table, arg[0]), arg2)
                            if arg[1] == 'not in':
                                red_sql = '(NOT(' + red_sql + '))'
                            qu1.append(red_sql)
                            qu2 += red_ids
                        else:
                            qu1.append(('("%s"."%s" ' + arg[1] + ' (%s))') % \
                                    (table._table, arg[0], ','.join(
                                        ('%s',) * len(arg2))))
                            qu2 += arg2
                        if todel:
                            if table._columns[arg[0]]._type == 'boolean':
                                if arg[1] == 'in':
                                    qu1[-1] = '(' + qu1[-1] + ' OR ' \
                                            '"%s"."%s" = %%s)' % \
                                            (table._table, arg[0])
                                    qu2.append(False)
                                else:
                                    qu1[-1] = '(' + qu1[-1] + ' AND ' \
                                            '"%s"."%s" != %%s)' % \
                                            (table._table, arg[0])
                                    qu2.append(False)
                            else:
                                if arg[1] == 'in':
                                    qu1[-1] = '(' + qu1[-1] + ' OR ' \
                                            '"%s"."%s" IS NULL)' % \
                                            (table._table, arg[0])
                                else:
                                    qu1[-1] = '(' + qu1[-1] + ' AND ' \
                                            '"%s"."%s" IS NOT NULL)' % \
                                            (table._table, arg[0])
                    elif todel:
                        if table._columns[arg[0]]._type == 'boolean':
                            if arg[1] == 'in':
                                qu1.append('("%s"."%s" = %%s)' % \
                                        (table._table, arg[0]))
                                qu2.append(False)
                            else:
                                qu1.append('("%s"."%s" != %%s)' % \
                                        (table._table, arg[0]))
                                qu2.append(False)
                        else:
                            if arg[1] == 'in':
                                qu1.append('("%s"."%s" IS NULL)' % \
                                        (table._table, arg[0]))
                            else:
                                qu1.append('("%s"."%s" IS NOT NULL)' % \
                                        (table._table, arg[0]))
                else:
                    if arg[1] == 'in':
                        qu1.append(' %s')
                        qu2.append(False)
                    else:
                        qu1.append(' %s')
                        qu2.append(True)
            else:
                if (arg[2] is False) and (arg[1] == '='):
                    if table._columns[arg[0]]._type == 'boolean':
                        qu1.append('(("%s"."%s" = %%s) OR ("%s"."%s" IS NULL))'
                            % (table._table, arg[0], table._table, arg[0]))
                        qu2.append(False)
                    else:
                        qu1.append('("%s"."%s" IS NULL)' % \
                                (table._table, arg[0]))
                elif (arg[2] is False) and (arg[1] == '!='):
                    if table._columns[arg[0]]._type == 'boolean':
                        qu1.append('(("%s"."%s" != %%s) '
                            'AND ("%s"."%s" IS NOT NULL))'
                            % (table._table, arg[0], table._table, arg[0]))
                        qu2.append(False)
                    else:
                        qu1.append('("%s"."%s" IS NOT NULL)' % \
                                 (table._table, arg[0]))
                else:
                    if arg[0] == 'id':
                        qu1.append('("%s"."%s" %s %%s)' % \
                                (table._table, arg[0], arg[1]))
                        qu2.append(FIELDS[table._columns[arg[0]]._type].\
                                sql_format(arg[2]))
                    else:
                        add_null = False
                        if arg[1] in ('like', 'ilike'):
                            if not arg[2]:
                                qu2.append('%')
                                add_null = True
                            else:
                                qu2.append(FIELDS[
                                        table._columns[arg[0]]._type
                                        ].sql_format(arg[2]))
                        elif arg[1] in ('not like', 'not ilike'):
                            if not arg[2]:
                                qu2.append('')
                            else:
                                qu2.append(FIELDS[
                                        table._columns[arg[0]]._type
                                        ].sql_format(arg[2]))
                                add_null = True
                        else:
                            if arg[0] in table._columns:
                                qu2.append(FIELDS[
                                    table._columns[arg[0]]._type
                                    ].sql_format(arg[2]))
                        qu1.append('("%s"."%s" %s %%s)' % (table._table,
                            arg[0], arg[1]))
                        if add_null:
                            qu1[-1] = '(' + qu1[-1] + ' OR ' \
                                    '"' + table._table + '"."' + arg[0] + '"' \
                                        ' IS NULL)'

        return qu1, qu2

    def _order_calc(self, field, otype):
        pool = Pool()
        order_by = []
        tables = []
        tables_args = {}
        field_name = None
        table_name = None
        link_field = None

        if field in self._columns:
            table_name = self._table

            if not hasattr(self._columns[field], 'set'):
                field_name = field

            if self._columns[field].order_field:
                field_name = self._columns[field].order_field

            if isinstance(self._columns[field], fields.Many2One):
                obj = pool.get(self._columns[field].model_name)
                table_name = obj._table
                link_field = field
                field_name = None

                if obj._rec_name in obj._columns:
                    field_name = obj._rec_name

                if obj._order_name in obj._columns:
                    field_name = obj._order_name

                if field_name:
                    order_by, tables, tables_args = obj._order_calc(field_name,
                            otype)
                    table_join = 'LEFT JOIN "' + table_name + '" AS ' \
                            '"' + table_name + '.' + link_field + '" ON ' \
                            '"%s.%s".id = "%s"."%s"' % (table_name, link_field,
                                    self._table, link_field)
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

                obj2 = None
                if obj._rec_name in obj._inherit_fields.keys():
                    obj2 = pool.get(
                            obj._inherit_fields[obj._rec_name][0])
                    field_name = obj._rec_name

                if obj._order_name in obj._inherit_fields.keys():
                    obj2 = pool.get(
                            obj._inherit_fields[obj._order_name][0])
                    field_name = obj._order_name

                if obj2 and field_name:
                    table_name2 = obj2._table
                    link_field2 = obj._inherits[obj2._name]
                    order_by, tables, tables_args = \
                            obj2._order_calc(field_name, otype)

                    table_join = 'LEFT JOIN "' + table_name + '" AS ' \
                            '"' + table_name + '.' + link_field + '" ON ' \
                            '"%s.%s".id = "%s"."%s"' % \
                            (table_name, link_field, self._table, link_field)
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
                        tables_args[table_join] = []

                    table_join2 = 'LEFT JOIN "' + table_name2 + '" AS ' \
                            '"' + table_name2 + '.' + link_field2 + '" ON ' \
                            '"%s.%s".id = "%s.%s"."%s"' % \
                            (table_name2, link_field2, table_name, link_field,
                                    link_field2)
                    for i in range(len(order_by)):
                        if table_name2 in order_by[i]:
                            order_by[i] = order_by[i].replace(table_name2,
                                    table_name2 + '.' + link_field2)
                    for i in range(1, len(tables)):
                        if table_name2 in tables[i]:
                            args = tables_args.pop(tables[i], [])
                            tables[i] = tables[i].replace(table_name2,
                                    table_name2 + '.' + link_field2)
                            tables_args[tables[i]] = args
                    if table_join2 not in tables:
                        tables.insert(1, table_join2)
                        tables_args[table_join2] = []
                    return order_by, tables, tables_args

            if field_name in self._columns \
                    and getattr(self._columns[field_name], 'translate', False):
                translation_table = 'ir_translation_%s_%s' % \
                        (table_name, field_name)
                if self._name == 'ir.model':
                    table_join = 'LEFT JOIN "ir_translation" ' \
                            'AS "%s" ON ' \
                            '("%s".name = "ir_model".model||\',%s\' ' \
                                'AND "%s".res_id = 0 ' \
                                'AND "%s".lang = %%s ' \
                                'AND "%s".type = \'model\' ' \
                                'AND "%s".fuzzy = %s)' % \
                            (translation_table, translation_table, field_name,
                                    translation_table, translation_table,
                                    translation_table, translation_table,
                                    FIELDS['boolean'].sql_format(False))
                elif self._name == 'ir.model.field':
                    if field_name == 'field_description':
                        ttype = 'field'
                    else:
                        ttype = 'help'
                    table_join = 'LEFT JOIN "ir_model" ON ' \
                            'ir_model.id = ir_model_field.model'
                    if table_join not in tables:
                        tables.append(table_join)
                    table_join = 'LEFT JOIN "ir_translation" ' \
                            'AS "%s" ON ' \
                            '("%s".name = "ir_model".model||\',\'||%s.name ' \
                                'AND "%s".res_id = 0 ' \
                                'AND "%s".lang = %%s ' \
                                'AND "%s".type = \'%s\' ' \
                                'AND "%s".fuzzy = %s)' % \
                            (translation_table, translation_table, table_name,
                                    translation_table, translation_table,
                                    translation_table, ttype, translation_table,
                                    FIELDS['boolean'].sql_format(False))
                else:
                    table_join = 'LEFT JOIN "ir_translation" ' \
                            'AS "%s" ON ' \
                            '("%s".res_id = "%s".id ' \
                                'AND "%s".name = \'%s,%s\' ' \
                                'AND "%s".lang = %%s ' \
                                'AND "%s".type = \'model\' ' \
                                'AND "%s".fuzzy = %s)' % \
                            (translation_table, translation_table, table_name,
                                    translation_table, self._name, field_name,
                                    translation_table, translation_table,
                                    translation_table,
                                    FIELDS['boolean'].sql_format(False))
                if table_join not in tables:
                    tables.append(table_join)
                    tables_args[table_join] = [Transaction().language]
                order_by.append('COALESCE(NULLIF(' \
                        + '"' + translation_table + '".value, \'\'), ' \
                        + '"' + table_name + '".' + field_name + ') ' + otype)
                return order_by, tables, tables_args

            if field_name in self._columns \
                    and self._columns[field_name]._type == 'selection' \
                    and self._columns[field_name].order_field is None:
                selections = self.fields_get([field_name]
                        )[field_name]['selection']
                if not isinstance(selections, (tuple, list)):
                    selections = getattr(self,
                            self._columns[field_name].selection)()
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

        if field in self._inherit_fields.keys():
            obj = pool.get(self._inherit_fields[field][0])
            table_name = obj._table
            link_field = self._inherits[obj._name]
            order_by, tables, tables_args = obj._order_calc(field, otype)
            table_join = 'LEFT JOIN "' + table_name + '" ON ' \
                    '"%s".id = "%s"."%s"' % \
                    (table_name, self._table, link_field)
            if table_join not in tables:
                tables.insert(0, table_join)
            return order_by, tables, tables_args

        raise Exception('Error', 'Wrong field name (%s) for %s in order!' %
            (field, self._name))

    def _rebuild_tree(self, parent, parent_id, left):
        '''
        Rebuild left, right value for the tree.
        '''
        cursor = Transaction().cursor
        right = left + 1

        with Transaction().set_user(0):
            child_ids = self.search([
                (parent, '=', parent_id),
                ])

        for child_id in child_ids:
            right = self._rebuild_tree(parent, child_id, right)

        field = self._columns[parent]

        if parent_id:
            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET "' + field.left + '" = %s, ' \
                        '"' + field.right + '" = %s ' \
                    'WHERE id = %s', (left, right, parent_id))
        return right + 1

    def _update_tree(self, object_id, field_name, left, right):
        '''
        Update left, right values for the tree.
        Remarks:
            - the value (right - left - 1) / 2 will not give
                the number of children node
            - the order of the tree respects the default _order
        '''
        cursor = Transaction().cursor
        cursor.execute('SELECT "' + left + '", "' + right + '" ' \
                'FROM "' + self._table + '" ' \
                'WHERE id = %s', (object_id,))
        fetchone = cursor.fetchone()
        if not fetchone:
            return
        old_left, old_right = fetchone
        if old_left == old_right:
            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET "' + right + '" = "' + right + '" + 1 ' \
                    'WHERE id = %s', (object_id,))
            old_right += 1

        parent_right = 1

        cursor.execute('SELECT "' + field_name + '" ' \
                'FROM "' + self._table + '" ' \
                'WHERE id = %s', (object_id,))
        parent_id = cursor.fetchone()[0] or False

        if parent_id:
            cursor.execute('SELECT "' + right + '" ' \
                    'FROM "' + self._table + '" ' \
                    'WHERE id = %s', (parent_id,))
            parent_right = cursor.fetchone()[0]
        else:
            cursor.execute('SELECT MAX("' + right + '") ' \
                    'FROM "' + self._table + '" ' \
                    'WHERE "' + field_name + '" IS NULL')
            fetchone = cursor.fetchone()
            if fetchone:
                parent_right = fetchone[0] + 1

        cursor.execute('SELECT id FROM "' + self._table + '" ' \
                'WHERE "' + left + '" >= %s AND "' + right + '" <= %s',
                (old_left, old_right))
        child_ids = [x[0] for x in cursor.fetchall()]

        if len(child_ids) > cursor.IN_MAX:
            with Transaction().set_user(0):
                return self._rebuild_tree(field_name, False, 0)

        red_child_sql, red_child_ids = reduce_ids('id', child_ids)
        # ids for left update
        cursor.execute('SELECT id FROM "' + self._table + '" ' \
                'WHERE "' + left + '" >= %s ' \
                    'AND NOT ' + red_child_sql,
                    [parent_right] + red_child_ids)
        left_ids = [x[0] for x in cursor.fetchall()]

        # ids for right update
        cursor.execute('SELECT id FROM "' + self._table + '" ' \
                'WHERE "' + right + '" >= %s ' \
                    'AND NOT ' + red_child_sql,
                    [parent_right] + red_child_ids)
        right_ids = [x[0] for x in cursor.fetchall()]

        if left_ids:
            for i in range(0, len(left_ids), cursor.IN_MAX):
                sub_ids = left_ids[i:i + cursor.IN_MAX]
                red_sub_sql, red_sub_ids = reduce_ids('id', sub_ids)
                cursor.execute('UPDATE "' + self._table + '" ' \
                        'SET "' + left + '" = "' + left + '" + ' \
                            + str(old_right - old_left + 1) + ' ' \
                        'WHERE ' + red_sub_sql, red_sub_ids)
        if right_ids:
            for i in range(0, len(right_ids), cursor.IN_MAX):
                sub_ids = right_ids[i:i + cursor.IN_MAX]
                red_sub_sql, red_sub_ids = reduce_ids('id', sub_ids)
                cursor.execute('UPDATE "' + self._table + '" ' \
                        'SET "' + right + '" = "' + right + '" + ' \
                            + str(old_right - old_left + 1) + ' ' \
                        'WHERE ' + red_sub_sql, red_sub_ids)

        cursor.execute('UPDATE "' + self._table + '" ' \
                'SET "' + left + '" = "' + left + '" + ' \
                        + str(parent_right - old_left) + ', ' \
                    '"' + right + '" = "' + right + '" + ' \
                        + str(parent_right - old_left) + ' ' \
                'WHERE ' + red_child_sql, red_child_ids)

        # Use root user to by-pass rules
        with contextlib.nested(Transaction().set_user(0),
                Transaction().set_context(active_test=False)):
            brother_ids = self.search([
                (field_name, '=', parent_id),
                ])
        if brother_ids[-1] != object_id:
            next_id = brother_ids[brother_ids.index(object_id) + 1]
            cursor.execute('SELECT "' + left + '" ' \
                    'FROM "' + self._table + '" ' \
                    'WHERE id = %s', (next_id,))
            next_left = cursor.fetchone()[0]
            cursor.execute('SELECT "' + left + '" '\
                    'FROM "' + self._table + '" ' \
                    'WHERE id = %s', (object_id,))
            current_left = cursor.fetchone()[0]


            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET "' + left + '" = "' + left + '" + ' \
                            + str(old_right - old_left + 1) + ', ' \
                        '"' + right + '" = "' + right + '" + ' \
                            + str(old_right - old_left + 1) + ' ' \
                    'WHERE "' + left + '" >= %s AND "' + right + '" <= %s',
                    (next_left, current_left))

            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET "' + left + '" = "' + left + '" - ' \
                            + str(current_left - next_left) + ', ' \
                        '"' + right + '" = "' + right + '" - ' \
                            + str(current_left - next_left) + ' ' \
                    'WHERE ' + red_child_sql, red_child_ids)

    def _validate(self, ids):
        super(ModelSQL, self)._validate(ids)
        cursor = Transaction().cursor
        if cursor.has_constraint():
            return
        # Works only for a single transaction
        for _, sql, error in self._sql_constraints:
            match = _RE_UNIQUE.match(sql)
            if match:
                sql = match.group(1)
                sql_clause = ' AND '.join('%s = %%s' % \
                        i for i in sql.split(','))
                sql_clause = '(id != %s AND ' + sql_clause + ')'

                for i in range(0, len(ids), cursor.IN_MAX):
                    sub_ids = ids[i:i + cursor.IN_MAX]
                    red_sql, red_ids = reduce_ids('id', sub_ids)

                    cursor.execute('SELECT id,' + sql + ' ' \
                            'FROM "' + self._table + '" ' \
                            'WHERE ' + red_sql, red_ids)

                    fetchall = cursor.fetchall()
                    cursor.execute('SELECT id ' \
                            'FROM "' + self._table + '" ' \
                            'WHERE ' + \
                                ' OR '.join((sql_clause,) * len(fetchall)),
                            reduce(lambda x, y: x + list(y), fetchall, []))

                    if cursor.fetchone():
                        self.raise_user_error(error)
                continue
            match = _RE_CHECK.match(sql)
            if match:
                sql = match.group(1)
                for i in range(0, len(ids), cursor.IN_MAX):
                    sub_ids = ids[i:i + cursor.IN_MAX]
                    red_sql, red_ids = reduce_ids('id', sub_ids)
                    cursor.execute('SELECT id ' \
                            'FROM "' + self._table + '" ' \
                            'WHERE NOT (' + sql + ') ' \
                                'AND ' + red_sql, red_ids)
                    if cursor.fetchone():
                        self.raise_user_error(error)
                    continue
