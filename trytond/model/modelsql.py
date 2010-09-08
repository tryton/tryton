#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model import ModelStorage, OPERATORS
from trytond.model import fields
from trytond.backend import FIELDS, TableHandler
from trytond.backend import DatabaseIntegrityError, Database
import datetime


class ModelSQL(ModelStorage):
    """
    Define a model with storage in database in Tryton.

    :_table: The name of the database table which is mapped to the class.
        If not set the value of ``_name`` is used with dots converted to
        underscores.
    :_order: A tuple defining by default how the record are returned when searching.
        E.g.:

        ``[('name', 'ASC'), 'age', 'DESC']``
    :_order_name: The name of the field (or an SQL statement) on which the records
         must be sorted when sorting on this model from an other one.
    :_sequence: The  name of the sequence in the database that increments the
        ``id`` field.
    :_history: A boolean to historize record change.
    :_sql_constraints: A list of constraints that are added on the table. E.g.:

        ``('constrain_name, sql_constraint, 'error_msg')`` where
        ``'constrain_name'`` is the name of the SQL constraint for the database,
        ``sql_constraint`` is the actual SQL constraint and
        ``'error_msg'`` is one of the key of ``_error_messages``.
    :_sql_error_messages:  Like ``_error_messages`` for ``_sql_constraints``.
    """
    _table = None # The name of the table in database
    _order = None
    _order_name = None # Use to force order field when sorting on Many2One
    _sequence = None
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

        if not self._sequence:
            self._sequence = self._table+'_id_seq'

    def init(self, cursor, module_name):
        super(ModelSQL, self).init(cursor, module_name)

        if self.table_query():
            return

        # create/update table in the database
        table = TableHandler(cursor, self, module_name)
        if self._history:
            history_table = TableHandler(cursor, self, module_name, history=True)
        datetime_field = FIELDS['datetime']
        integer_field = FIELDS['integer']
        logs = (
            ('create_date', datetime_field.sql_type(None),
                datetime_field.sql_format, lambda *a: datetime.datetime.now()),
            ('write_date', datetime_field.sql_type(None),
                datetime_field.sql_format, None),
            ('create_uid', (integer_field.sql_type(None)[0],
             'INTEGER REFERENCES res_user ON DELETE SET NULL',),
             integer_field.sql_format, lambda *a: 0),
            ('write_uid', (integer_field.sql_type(None)[0],
             'INTEGER REFERENCES res_user ON DELETE SET NULL'),
             integer_field.sql_format, None),
            )
        for log in logs:
            table.add_raw_column(log[0], log[1], log[2],
                    default_fun=log[3], migrate=False)
        if self._history:
            history_logs = (
                    ('create_date', datetime_field.sql_type(None),
                        datetime_field.sql_format),
                    ('write_date', datetime_field.sql_type(None),
                        datetime_field.sql_format),
                    ('create_uid', (integer_field.sql_type(None)[0],
                     'INTEGER REFERENCES res_user ON DELETE SET NULL',),
                     integer_field.sql_format),
                    ('write_uid', (integer_field.sql_type(None)[0],
                     'INTEGER REFERENCES res_user ON DELETE SET NULL'),
                     integer_field.sql_format),
                    )
            for log in history_logs:
                history_table.add_raw_column(log[0], log[1], log[2],
                        migrate=False)
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
                            except:
                                return None
                            clean_results = self._clean_defaults(
                                {field_name: result})
                            return clean_results[field_name]
                        return unpack_result
                    default_fun = unpack_wrapper(default_fun)

                table.add_raw_column(field_name,
                        FIELDS[field._type].sql_type(field),
                        FIELDS[field._type].sql_format, default_fun,
                        hasattr(field, 'size') and field.size or None)
                if self._history:
                    history_table.add_raw_column(field_name,
                            FIELDS[field._type].sql_type(field), None)

                if isinstance(field, (fields.Integer, fields.Float)):
                    table.db_default(field_name, 0)

                if isinstance(field, fields.Many2One):
                    if field.model_name in ('res.user', 'res.group'):
                        ref = field.model_name.replace('.','_')
                    else:
                        ref = self.pool.get(field.model_name)._table
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
                self._rebuild_tree(cursor, 0, field_name, False, 0)

        for ident, constraint, msg in self._sql_constraints:
            table.add_constraint(ident, constraint)

        if self._history:
            self._update_history_table(cursor)
            cursor.execute('SELECT id FROM "' + self._table + '"')
            if cursor.rowcount:
                cursor.execute('SELECT id FROM "' + self._table + '__history"')
                if not cursor.rowcount:
                    columns = ['"' + str(x) + '"' for x in self._columns
                            if not hasattr(self._columns[x], 'set')]
                    cursor.execute('INSERT INTO "' + self._table + '__history" '\
                            '(' + ','.join(columns) + ') ' \
                            'SELECT ' + ','.join(columns) + \
                            ' FROM "' + self._table + '"')
                    cursor.execute('UPDATE "' + self._table + '__history" ' \
                            'SET write_date = NULL')

    def _update_history_table(self, cursor):
        if self._history:
            table = TableHandler(cursor, self)
            history_table = TableHandler(cursor, self, history=True)
            for column_name in table._columns:
                if not history_table.column_exist(column_name):
                    history_table.add_raw_column(column_name,
                            (table._columns[column_name]['typname'],
                                table._columns[column_name]['typname']),
                                None)

    def _get_error_messages(self):
        res = super(ModelSQL, self)._get_error_messages()
        res += self._sql_error_messages.values()
        for _, _, error in self._sql_constraints:
            res.append(error)
        return res

    def table_query(self, context=None):
        '''
        Return None if the model is a real table in the database
        or return a tuple with the SQL query and the arguments.

        :param context: the context
        :return: None or a tuple with a SQL query and arguments
        '''
        return None

    def create(self, cursor, user, values, context=None):
        super(ModelSQL, self).create(cursor, user, values, context=context)

        if context is None:
            context = {}

        if self.table_query(context):
            return False

        values = values.copy()

        # Clean values
        for key in ('create_uid', 'create_date', 'id'):
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
            if (not i in values) \
                    and (not self._inherit_fields[i][0] in avoid_table):
                default.append(i)

        if len(default):
            defaults = self.default_get(cursor, user, default, context=context,
                    with_rec_name=False)
            for field in defaults.keys():
                if '.' in field:
                    del defaults[field]
                if field in ('create_uid', 'create_date',
                        'write_uid', 'write_date'):
                    del defaults[field]
            values.update(self._clean_defaults(defaults))

        # Get new id
        cursor.execute("SELECT NEXTVAL('" + self._sequence + "')")
        (id_new,) = cursor.fetchone()

        (upd0, upd1, upd2) = ('', '', [])
        upd_todo = []

        # Create inherits
        tocreate = {}
        for i in self._inherits:
            if self._inherits[i] not in values:
                tocreate[i] = {}

        for i in values.keys():
            if i in self._inherit_fields:
                (inherits, col, col_detail) = self._inherit_fields[i]
                if i in self._columns:
                    continue
                if inherits in tocreate:
                    tocreate[inherits][i] = values[i]
                if i not in self._columns:
                    del values[i]

        for inherits in tocreate:
            inherits_obj = self.pool.get(inherits)
            inherits_id = inherits_obj.create(cursor, user, tocreate[inherits],
                    context=context)
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
                        self._columns[field].selection)(
                        cursor, user, context=context)):
                        raise Exception('ValidateError',
                        'The value "%s" for the field "%s" ' \
                                'is not in the selection' % \
                                (val, field))
        upd0 += ', create_uid, create_date'
        upd1 += ', %s, now()'
        upd2.append(user)
        try:
            cursor.execute('INSERT INTO "' + self._table + '" ' \
                    '(id' + upd0 + ') ' \
                    'VALUES (' + str(id_new) + upd1 + ')', tuple(upd2))
        except DatabaseIntegrityError, exception:
            database = Database(cursor.database_name).connect()
            cursor2 = database.cursor()
            try:
                for field_name in self._columns:
                    field = self._columns[field_name]
                    # Check required fields
                    if field.required \
                            and not hasattr(field, 'set') \
                            and field_name not in ('create_uid', 'create_date'):
                        if not values.get(field_name):
                            self.raise_user_error(cursor2, 'required_field',
                                    error_args=self._get_error_args(
                                        cursor2, user, field_name,
                                        context=context), context=context)
                    if isinstance(field, fields.Many2One) \
                            and values.get(field_name):
                        model_obj = self.pool.get(field.model_name)
                        create_records = context.get('_create_records', {})\
                                .get(field.model_name, set())
                        delete_records = context.get('_delete_records', {})\
                                .get(field.model_name, set())
                        if not ((model_obj.search(cursor2, 0, [
                            ('id', '=', values[field_name]),
                            ], context=context) \
                                    or values[field_name] in create_records) \
                                and values[field_name] not in delete_records):
                            self.raise_user_error(cursor2,
                                    'foreign_model_missing',
                                    error_args=self._get_error_args(
                                        cursor2, user, field_name,
                                        context=context), context=context)
                for name, _, error in self._sql_constraints:
                    if name in exception[0]:
                        self.raise_user_error(cursor2, error, context=context)
                for name, error in self._sql_error_messages:
                    if name in exception[0]:
                        self.raise_user_error(cursor2, error, context=context)
            finally:
                cursor2.close()
            raise

        context.setdefault('_create_records', {})
        context['_create_records'].setdefault(self._name, set())
        context['_create_records'][self._name].add(id_new)

        upd_todo.sort(lambda x, y: self._columns[x].priority - \
                self._columns[y].priority)
        for field in upd_todo:
            self._columns[field].set(cursor, user, id_new, self, field, values[field],
                    context=context)

        if self._history:
            cursor.execute('INSERT INTO "' + self._table + '__history" ' \
                    '(id' + upd0 + ') ' \
                    'SELECT id' + upd0 + ' ' \
                    'FROM "' + self._table + '" ' \
                    'WHERE id = %s',(id_new,))

        self._validate(cursor, user, [id_new], context=context)

        # Check for Modified Preorder Tree Traversal
        for k in self._columns:
            field = self._columns[k]
            if isinstance(field, fields.Many2One) \
                    and field.model_name == self._name \
                    and field.left and field.right:
                self._update_tree(cursor, user, id_new, k, field.left, field.right)

        return id_new

    def read(self, cursor, user, ids, fields_names=None, context=None):
        rule_obj = self.pool.get('ir.rule')
        translation_obj = self.pool.get('ir.translation')
        super(ModelSQL, self).read(cursor, user, ids,
                fields_names=fields_names, context=context)

        if context is None:
            context = {}

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
        domain1, domain2 = rule_obj.domain_get(cursor, user, self._name,
                context=context)

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

        if self.table_query(context):
            table_query, table_args = self.table_query(context)
            table_query = '(' + table_query + ') AS '

        in_max = cursor.IN_MAX
        history_order = ''
        history_clause = ''
        history_limit = ''
        history_args = []
        if self._history and context.get('_datetime') and not table_query:
            in_max = 1
            table_query = '"' + self._table + '__history" AS '
            history_clause = ' AND (COALESCE(write_date, create_date) <= %s)'
            history_order = ' ORDER BY COALESCE(write_date, create_date) DESC'
            history_limit = ' LIMIT 1'
            history_args = [context['_datetime']]
        if len(fields_pre) :
            fields_pre2 = [(x in ('create_date', 'write_date')) \
                    and ('date_trunc(\'second\', ' + x + ') as ' + x) \
                    or '"' + x + '"' for x in fields_pre \
                    if x != '_timestamp']
            if '_timestamp' in fields_pre:
                if not self.table_query(context):
                    fields_pre2 += ['(COALESCE(write_date, create_date)) ' \
                            'AS _timestamp']
                else:
                    fields_pre2 += ['now()::timestamp AS _timestamp']

            for i in range(0, len(ids), in_max):
                sub_ids = ids[i:i + in_max]
                if domain1:
                    cursor.execute('SELECT ' + \
                            ','.join(fields_pre2 + ['id']) + \
                            ' FROM ' + table_query + '\"' + self._table +'\" ' \
                            'WHERE id IN ' \
                                '(' + ','.join(['%s' for x in sub_ids]) + ')' + \
                            history_clause + \
                            ' AND (' + domain1 + ') ' + history_order + \
                            history_limit,
                            table_args + sub_ids + history_args + domain2)
                else:
                    cursor.execute('SELECT ' + \
                            ','.join(fields_pre2 + ['id']) + \
                            ' FROM ' + table_query + '\"' + self._table + '\" ' \
                            'WHERE id IN ' \
                                '(' + ','.join(['%s' for x in sub_ids]) + ')' + \
                            history_clause + history_order + history_limit,
                            table_args + sub_ids + history_args)
                if not cursor.rowcount == len({}.fromkeys(sub_ids)):
                    if domain1:
                        cursor.execute('SELECT id FROM ' + \
                                table_query + '\"' + self._table + '\" ' \
                                'WHERE id IN ' \
                                '(' + ','.join(['%s' for x in sub_ids]) + ')' + \
                                history_clause + history_order + history_limit,
                                table_args + sub_ids + history_args)
                        if cursor.rowcount == len({}.fromkeys(sub_ids)):
                            self.raise_user_error(cursor, 'access_error',
                                    self._description, context=context)
                    self.raise_user_error(cursor, 'read_error',
                            self._description, context=context)
                res.extend(cursor.dictfetchall())
        else:
            res = [{'id': x} for x in ids]

        for field in fields_pre:
            if field == '_timestamp':
                continue
            if self._columns[field].translate:
                ids = [x['id'] for x in res]
                res_trans = translation_obj._get_ids(cursor,
                        self._name + ',' + field, 'model',
                        context.get('language') or 'en_US', ids)
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
            res2 = self.pool.get(table).read(cursor, user,
                    [x[field] for x in res],
                    fields_names=inherits_fields + inherit_related_fields,
                    context=context)

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
            if isinstance(self._columns[field], fields.Function) \
                    and not isinstance(self._columns[field], fields.Property):
                key = (self._columns[field].fnct, self._columns[field].arg)
                func_fields.setdefault(key, [])
                func_fields[key].append(field)
                continue
            # get the value of that field for all records/ids
            res2 = self._columns[field].get(cursor, user, ids, self, field,
                    values=res, context=context)
            for record in res:
                record[field] = res2[record['id']]
        for i in func_fields:
            field_list = func_fields[i]
            field = field_list[0]
            res2 = self._columns[field].get(cursor, user, ids, self, field_list,
                    values=res, context=context)
            for field in res2:
                for record in res:
                    record[field] = res2[field][record['id']]

        to_del = []
        fields_related2values = {}
        for field in fields_related.keys() + datetime_fields:
            if field not in fields_names:
                to_del.append(field)
            if field not in self._columns:
                continue
            if field not in fields_related.keys():
                continue
            fields_related2values.setdefault(field, {})
            if self._columns[field]._type == 'many2one':
                obj = self.pool.get(self._columns[field].model_name)
                if hasattr(self._columns[field], 'datetime_field') \
                        and self._columns[field].datetime_field:
                    ctx = context.copy()
                    for record in res:
                        ctx['_datetime'] = \
                                record[self._columns[field].datetime_field]
                        record2 = obj.read(cursor, user, record[field],
                                fields_related[field], context=ctx)
                        record_id = record2['id']
                        del record2['id']
                        fields_related2values[field].setdefault(record_id, {})
                        fields_related2values[field][record_id][record['id']] = \
                                record2
                else:
                    for record in obj.read(cursor, user, [x[field] for x in res
                        if x[field]], fields_related[field], context=context):
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
                    if not record_id:
                        continue
                    obj = self.pool.get(model_name)
                    record2 = obj.read(cursor, user, record_id,
                            fields_related[field], context=context)
                    del record2['id']
                    fields_related2values[field][record_id] = record2

        if to_del or fields_related.keys() or datetime_fields:
            for record in res:
                for field in fields_related.keys():
                    if field not in self._columns:
                        continue
                    for related in fields_related[field]:
                        if self._columns[field]._type == 'many2one':
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
                                if not record_id:
                                    continue
                                record[field + '.' + related] = \
                                        fields_related2values[field][
                                                record_id][related]
                for field in to_del:
                    del record[field]

        if int_id:
            return res[0]
        return res

    def write(self, cursor, user, ids, values, context=None):
        super(ModelSQL, self).write(cursor, user, ids, values, context=context)

        if context is None:
            context = {}

        if not ids:
            return True

        if self.table_query(context):
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
                    self.write(cursor, user, object_id, values, context=context)
                return True

        if context.get('_timestamp', False):
            for i in range(0, len(ids), cursor.IN_MAX):
                sub_ids = ids[i:i + cursor.IN_MAX]
                clause = '(id = %s AND ' \
                        '(CASE WHEN write_date IS NOT NULL ' \
                        'THEN write_date ELSE create_date END) ' \
                        ' > %s)'
                args = []
                for i in sub_ids:
                    if context['_timestamp'].get(self._name + ',' + str(i)):
                        args.append(i)
                        args.append(context['_timestamp'][
                            self._name + ',' +str(i)])
                if args:
                    cursor.execute("SELECT id " \
                            'FROM "' + self._table + '" ' \
                            'WHERE ' + ' OR '.join(
                                [clause for x in range(len(args)/2)]), args)
                    if cursor.rowcount:
                        raise Exception('ConcurrencyException',
                                'Records were modified in the meanwhile')
            for i in ids:
                if context['_timestamp'].get(self._name + ',' + str(i)):
                    del context['_timestamp'][self._name + ',' +str(i)]


        if 'write_uid' in values:
            del values['write_uid']
        if 'write_date' in values:
            del values['write_date']
        if 'id' in values:
            del values['id']

        upd0 = []
        upd1 = []
        upd_todo = []
        updend = []
        direct = []
        for field in values:
            if field in self._columns:
                if not hasattr(self._columns[field], 'set'):
                    if (not self._columns[field].translate) \
                            or (context.get('language') or 'en_US') == 'en_US':
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
                        self._columns[field].selection)(
                        cursor, user, context=context)):
                        raise Exception('ValidateError',
                        'The value "%s" for the field "%s" ' \
                                'is not in the selection' % \
                                (val, field))

        upd0.append(('write_uid', '%s'))
        upd0.append(('write_date', 'now()'))
        upd1.append(user)

        domain1, domain2 = self.pool.get('ir.rule').domain_get(cursor,
                user, self._name, context=context)
        if domain1:
            domain1 = ' AND (' + domain1 + ') '
        for i in range(0, len(ids), cursor.IN_MAX):
            sub_ids = ids[i:i + cursor.IN_MAX]
            ids_str = ','.join(['%s' for x in sub_ids])
            if domain1:
                cursor.execute('SELECT id FROM "' + self._table + '" ' \
                        'WHERE id IN (' + ids_str + ') ' + domain1,
                        sub_ids + domain2)
            else:
                cursor.execute('SELECT id FROM "' + self._table + '" ' \
                        'WHERE id IN (' + ids_str + ')', sub_ids)
            if not cursor.rowcount == len({}.fromkeys(sub_ids)):
                if domain1:
                    cursor.execute('SELECT id FROM "' + self._table + '" ' \
                            'WHERE id IN (' + ids_str + ')', sub_ids)
                    if cursor.rowcount == len({}.fromkeys(sub_ids)):
                        self.raise_user_error(cursor, 'access_error',
                            self._description, context=context)
                self.raise_user_error(cursor, 'write_error',
                        self._description, context=context)
            try:
                cursor.execute('UPDATE "' + self._table + '" ' \
                        'SET ' + \
                        ','.join([x[0] + ' = '+ x[1] for x in upd0]) + ' ' \
                        'WHERE id IN (' + ids_str + ') ', upd1 + sub_ids)
            except DatabaseIntegrityError, exception:
                database = Database(cursor.database_name).connect()
                cursor2 = database.cursor()
                try:
                    for field_name in values:
                        if field_name not in self._columns:
                            continue
                        field = self._columns[field_name]
                        # Check required fields
                        if field.required \
                                and not hasattr(field, 'set') \
                                and field_name not in \
                                ('create_uid', 'create_date'):
                            if not values[field_name]:
                                self.raise_user_error(cursor2,
                                        'required_field',
                                        error_args=self._get_error_args(
                                            cursor2, user, field_name,
                                            context=context),
                                        context=context)
                        if isinstance(field, fields.Many2One) \
                                and values[field_name]:
                            model_obj = self.pool.get(field.model_name)
                            create_records = context.get('_create_records', {})\
                                    .get(field.model_name, set())
                            delete_records = context.get('_delete_records', {})\
                                    .get(field.model_name, set())
                            if not ((model_obj.search(cursor2, 0, [
                                ('id', '=', values[field_name]),
                                ], context=context) \
                                        or values[field_name] in create_records) \
                                    and values[field_name] not in delete_records):
                                self.raise_user_error(cursor2,
                                        'foreign_model_missing',
                                        error_args=self._get_error_args(
                                            cursor2, user, field_name,
                                            context=context), context=context)
                    for name, _, error in self._sql_constraints:
                        if name in exception[0]:
                            self.raise_user_error(cursor2, error,
                                    context=context)
                    for name, error in self._sql_error_messages:
                        if name in exception[0]:
                            self.raise_user_error(cursor2, error,
                                    context=context)
                finally:
                    cursor2.close()
                raise

        for field in direct:
            if self._columns[field].translate:
                self.pool.get('ir.translation')._set_ids(cursor, user,
                        self._name + ',' + field, 'model',
                        context.get('language') or 'en_US', ids,
                        values[field])

        # call the 'set' method of fields which are not classic_write
        upd_todo.sort(lambda x, y: self._columns[x].priority - \
                self._columns[y].priority)
        for field in upd_todo:
            for select_id in ids:
                self._columns[field].set(cursor, user, select_id, self, field,
                        values[field], context=context)

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
                ids_str = ','.join(['%s' for x in sub_ids])
                cursor.execute('SELECT DISTINCT "' + col + '" ' \
                        'FROM "' + self._table + '" WHERE id IN (' + ids_str + ')',
                        sub_ids)
                nids.extend([x[0] for x in cursor.fetchall()])

            values2 = {}
            for val in updend:
                if self._inherit_fields[val][0] == table:
                    values2[val] = values[val]
            self.pool.get(table).write(cursor, user, nids, values2,
                    context=context)

        self._validate(cursor, user, ids, context=context)

        # Check for Modified Preorder Tree Traversal
        for k in self._columns:
            field = self._columns[k]
            if isinstance(field, fields.Many2One) \
                    and field.model_name == self._name \
                    and field.left and field.right:
                if field.left in values or field.right in values:
                    raise Exception('ValidateError', 'You can not update fields: ' \
                            '"%s", "%s"' % (field.left, field.right))
                if len(ids) == 1:
                    self._update_tree(cursor, user, ids[0], k,
                            field.left, field.right)
                else:
                    self._rebuild_tree(cursor, 0, k, False, 0)
        return True

    def delete(self, cursor, user, ids, context=None):
        super(ModelSQL, self).delete(cursor, user, ids, context=context)

        if context is None:
            context = {}

        if not ids:
            return True

        if self.table_query(context):
            return True

        if isinstance(ids, (int, long)):
            ids = [ids]

        if context.get('_delete') and context['_delete'].get(self._name):
            ids = ids[:]
            for del_id in context['_delete'][self._name]:
                for i in range(ids.count(del_id)):
                    ids.remove(del_id)

        if context.get('_timestamp', False):
            for i in range(0, len(ids), cursor.IN_MAX):
                sub_ids = ids[i:i + cursor.IN_MAX]
                clause = '(id = %s AND ' \
                        '(CASE WHEN write_date IS NOT NULL ' \
                        'THEN write_date ELSE create_date END) ' \
                        ' > %s)'
                args = []
                for i in sub_ids:
                    if context['_timestamp'].get(self._name + ',' + str(i)):
                        args.append(i)
                        args.append(context['_timestamp'][
                            self._name + ',' +str(i)])
                if args:
                    cursor.execute("SELECT id " \
                            'FROM "' + self._table + '" ' \
                            'WHERE ' + ' OR '.join(
                                [clause for x in range(len(args)/2)]), args)
                    if cursor.rowcount:
                        raise Exception('ConcurrencyException',
                                'Records were modified in the meanwhile')
            for i in ids:
                if context['_timestamp'].get(self._name + ',' + str(i)):
                    del context['_timestamp'][self._name + ',' +str(i)]

        tree_ids = {}
        for k in self._columns:
            field = self._columns[k]
            if isinstance(field, fields.Many2One) \
                    and field.model_name == self._name \
                    and field.left and field.right:
                cursor.execute('SELECT id FROM "' + self._table + '" '\
                        'WHERE "' + k + '" IN (' \
                            + ','.join(['%s' for x in ids]) + ')',
                            ids)
                tree_ids[k] = [x[0] for x in cursor.fetchall()]

        foreign_keys_tocheck = []
        foreign_keys_toupdate = []
        foreign_keys_todelete = []
        for model_name in self.pool.object_name_list():
            model = self.pool.get(model_name)
            if hasattr(model, 'table_query') \
                    and model.table_query(context):
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

        delete_ctx = context.copy()
        delete_ctx.setdefault('_delete', {})
        delete_ctx['_delete'].setdefault(self._name, set())
        delete_ctx['_delete'][self._name].update(ids)

        domain1, domain2 = self.pool.get('ir.rule').domain_get(cursor, user,
                self._name, context=context)
        if domain1:
            domain1 = ' AND (' + domain1 + ') '

        for i in range(0, len(ids), cursor.IN_MAX):
            sub_ids = ids[i:i + cursor.IN_MAX]
            str_d = ','.join(('%s',) * len(sub_ids))
            if domain1:
                cursor.execute('SELECT id FROM "'+self._table+'" ' \
                        'WHERE id IN (' + str_d + ') ' + domain1,
                        sub_ids + domain2)
                if not cursor.rowcount == len({}.fromkeys(sub_ids)):
                    self.raise_user_error(cursor, 'access_error',
                            self._description, context=context)

        for i in range(0, len(ids), cursor.IN_MAX):
            sub_ids = ids[i:i + cursor.IN_MAX]
            str_d = ','.join(('%s',) * len(sub_ids))

            for model, field_name in foreign_keys_toupdate:
                if not hasattr(model, 'search') \
                        or not hasattr(model, 'write'):
                    continue
                cursor.execute('SELECT id FROM "' + model._table + '" ' \
                        'WHERE "' + field_name + '" IN (' + str_d + ')', sub_ids)
                model_ids = [x[0] for x in cursor.fetchall()]
                if model_ids:
                    model.write(cursor, user, model_ids, {
                        field_name: False,
                        }, context=context)

            for model, field_name in foreign_keys_todelete:
                if not hasattr(model, 'search') \
                        or not hasattr(model, 'delete'):
                    continue
                cursor.execute('SELECT id FROM "' + model._table + '" ' \
                        'WHERE "' + field_name + '" IN (' + str_d + ')', sub_ids)
                model_ids = [x[0] for x in cursor.fetchall()]
                if model_ids:
                    model.delete(cursor, user, model_ids, context=delete_ctx)

            context.setdefault('_delete_records', {})
            context['_delete_records'].setdefault(self._name, set())
            context['_delete_records'][self._name].update(sub_ids)
            try:
                cursor.execute('DELETE FROM "'+self._table+'" ' \
                        'WHERE id IN (' + str_d + ')', sub_ids)
            except DatabaseIntegrityError:
                database = Database(cursor.database_name).connect()
                cursor2 = database.cursor()
                try:
                    for model, field_name in foreign_keys_tocheck:
                        if model.search(cursor2, 0, [
                            (field_name, 'in', sub_ids),
                            ], context=context):
                            error_args = []
                            error_args.append(self._get_error_args(cursor2,
                                user, 'id', context=context)[1])
                            error_args.extend(list(model._get_error_args(cursor2,
                                user, field_name, context=context)))
                            self.raise_user_error(cursor2, 'foreign_model_exist',
                                    error_args=tuple(error_args), context=context)
                    for name, _, error in self._sql_constraints:
                        if name in exception[0]:
                            self.raise_user_error(cursor2, error,
                                    context=context)
                    for name, error in self._sql_error_messages:
                        if name in exception[0]:
                            self.raise_user_error(cursor2, error,
                                    context=context)
                finally:
                    cursor2.close()
                raise

        if self._history:
            for obj_id in ids:
                cursor.execute('INSERT INTO "' + self._table + '__history" ' \
                        '(id, write_uid, write_date) VALUES (%s, %s, now())',
                        (obj_id, user))

        for k in tree_ids.keys():
            field = self._columns[k]
            if len(tree_ids[k]) == 1:
                self._update_tree(cursor, user, tree_ids[k][0], k,
                        field.left, field.right)
            else:
                self._rebuild_tree(cursor, 0, k, False, 0)

        return True

    def search(self, cursor, user, domain, offset=0, limit=None, order=None,
            context=None, count=False, query_string=False):
        rule_obj = self.pool.get('ir.rule')

        if context is None:
            context = {}

        # Get domain clauses
        qu1, qu2, tables, tables_args = self.search_domain(cursor, user,
                domain, context=context)

        # Get order by
        order_by = []
        for field, otype in (order or self._order):
            if otype.upper() not in ('DESC', 'ASC'):
                raise Exception('Error', 'Wrong order type (%s)!' % otype)
            order_by2, tables2, tables2_args = self._order_calc(cursor, user,
                    field, otype, context=context)
            order_by += order_by2
            for table in tables2:
                if table not in tables:
                    tables.append(table)
                    if tables2_args.get(table):
                        tables_args.extend(tables2_args.get(table))

        order_by = ','.join(order_by)

        # Get limit
        limit_str = limit and (type(limit) in (float, int, long))\
                    and ' LIMIT %d' % limit or ''

        # Get offset
        offset_str = offset and (type(offset) in (float, int, long))\
                     and ' OFFSET %d' % offset or ''

        # construct a clause for the rules :
        domain1, domain2 = rule_obj.domain_get(cursor, user, self._name,
                context=context)
        if domain1:
            if qu1:
                qu1 += ' AND ' + domain1
            else:
                qu1 = domain1
            qu2 += domain2

        if count:
            cursor.execute('SELECT COUNT("%s".id) FROM ' % self._table +
                    ' '.join(tables) + ' WHERE ' + (qu1 or 'True') +
                    limit_str + offset_str, tables_args + qu2)
            res = cursor.fetchall()
            return res[0][0]
        # execute the "main" query to fetch the ids we were searching for
        select_field = '"' + self._table + '".id'
        if self._history and context.get('_datetime') \
                and not query_string:
            select_field += ', COALESCE("' + self._table + '".write_date, "' + \
                    self._table + '".create_date)'
        query_str = 'SELECT ' + select_field + ' FROM ' + \
                ' '.join(tables) + ' WHERE ' + (qu1 or 'True') + \
                ' ORDER BY ' + order_by + limit_str + offset_str
        if query_string:
            return (query_str, tables_args + qu2)
        cursor.execute(query_str, tables_args + qu2)

        if self._history and context.get('_datetime'):
            res = []
            ids_date = {}
            for row in cursor.fetchall():
                if row[0] in ids_date:
                    if row[1] <= ids_date[row[0]]:
                        continue
                if row[0] in res:
                    res.remove(row[0])
                res.append(row[0])
                ids_date[row[0]] = row[1]
            return res

        res = cursor.fetchall()
        return [x[0] for x in res]

    def search_domain(self, cursor, user, domain, active_test=True, context=None):
        '''
        Return SQL clause and arguments for the domain

        :param cursor: the database cursor
        :param user: the user id
        :param domain: a domain like in search
        :param active_test: a boolean to add 'active' test
        :param context: the context
        :return: a tuple with
            - a SQL clause string
            - a list of arguments for the SQL clause
            - a list a tables used in the SQL clause
            - a list of arguments for the tables
        '''
        domain = self._search_domain_active(domain, active_test=active_test,
                context=context)

        table_query = ''
        tables_args = []
        if self.table_query(context):
            table_query, tables_args = self.table_query(context)
            table_query = '(' + table_query + ') AS '

        if self._history and context.get('_datetime'):
            table_query = self._table + '__history AS '

        tables = [table_query + '"' + self._table + '"']

        qu1, qu2 = self.__search_domain_oper(cursor, user, domain, tables,
                tables_args, context=context)
        if self._history and context.get('_datetime'):
            if qu1:
                qu1 += ' AND'
            qu1 += ' (COALESCE("' + self._table + '".write_date, "' + \
                    self._table + '".create_date) <= %s)'
            qu2 += [context['_datetime']]
        return qu1, qu2, tables, tables_args

    def __search_domain_oper(self, cursor, user, domain, tables, tables_args,
            context=None):
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

        qu1, qu2 = self.__search_domain_calc(cursor, user,
                tuple_args, tables, tables_args, context=context)
        if len(qu1):
            qu1 = (' ' + operator + ' ').join(qu1)
        else:
            qu1 = ''

        for domain2 in list_args:
            qu1b, qu2b = self.__search_domain_oper(cursor, user, domain2,
                    tables, tables_args, context=context)
            if not qu1b:
                qu1b = 'true'
            if qu1 and qu1b:
                qu1 += ' ' + operator + ' ' + qu1b
            elif qu1b:
                qu1 = qu1b
            qu2 += qu2b
        if qu1:
            qu1 = '(' + qu1 + ')'
        return qu1, qu2

    def __search_domain_calc(self, cursor, user, domain, tables, tables_args,
            context=None):
        if context is None:
            context = {}
        domain = domain[:]

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
                itable = self.pool.get(self._inherit_fields[fargs[0]][0])
                table_query = ''
                table_arg = []
                if itable.table_query(context):
                    table_query, table_args = self.table_query(context)
                    table_query = '(' + table_query + ') AS '
                table_join = 'LEFT JOIN ' + table_query + \
                        '"' + itable._table + '" ON ' \
                        '"%s".id = "%s".%s' % (itable._table, self._table,
                                self._inherits[itable._name])
                if table_join not in tables:
                    tables.append(table_join)
                    tables_args += table_arg
            field = table._columns.get(fargs[0], False)
            if not field:
                if not fargs[0] in self._inherit_fields:
                    raise Exception('ValidateError', 'Field "%s" doesn\'t ' \
                            'exist on "%s"' % (fargs[0], self._name))
                table = self.pool.get(self._inherit_fields[fargs[0]][0])
                field = table._columns.get(fargs[0], False)
            if len(fargs) > 1:
                if field._type == 'many2one':
                    if hasattr(field, 'search'):
                        domain.extend([(fargs[0], 'in',
                                self.pool.get(field.model_name).search(cursor, user,
                                    [(fargs[1], domain[i][1], domain[i][2])],
                                    context=context))])
                        domain.pop(i)
                    else:
                        domain[i] = (fargs[0], 'inselect',
                                self.pool.get(field.model_name).search(cursor, user,
                                    [(fargs[1], domain[i][1], domain[i][2])],
                                    context=context, query_string=True), table)
                        i += 1
                    continue
                else:
                    raise Exception('ValidateError', 'Clause on field "%s" ' \
                            'doesn\'t work on "%s"' % (domain[i][0], self._name))
            if hasattr(field, 'search'):
                arg = [domain.pop(i)]
                domain.extend(field.search(cursor, user, table,
                    arg[0][0], arg, context=context))
            elif field._type == 'one2many':
                field_obj = self.pool.get(field.model_name)

                if isinstance(domain[i][2], basestring):
                    # get the ids of the records of the "distant" resource
                    ids2 = [x[0] for x in field_obj.search(cursor, user, [
                        ('rec_name', domain[i][1], domain[i][2]),
                        ], context=context)]
                else:
                    ids2 = domain[i][2]

                table_query = ''
                table_args = []
                if field_obj.table_query(context):
                    table_query, table_args = field_obj.table_query(context)
                    table_query = '(' + table_query + ') AS '

                if ids2 == True or ids2 == False:
                    query1 = 'SELECT "' + field.field + '" ' \
                            'FROM ' + table_query + '"' + field_obj._table + '" ' \
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
                        query1 = 'SELECT "' + field.field + '" ' \
                                'FROM ' + table_query + '"' + field_obj._table + '" ' \
                                'WHERE id IN (' + \
                                    ','.join(['%s' for x in ids2]) + ')'
                        query2 = table_args + ids2
                        domain[i] = ('id', 'inselect', (query1, query2))
                    else:
                        ids3 = []
                        for i in range(0, len(ids2), cursor.IN_MAX):
                            sub_ids2 = ids2[i:i + cursor.IN_MAX]
                            cursor.execute(
                                'SELECT "' + field.field + \
                                '" FROM ' + table_query + '"' + field_obj._table + '" ' \
                                'WHERE id IN (' + \
                                    ','.join(['%s' for x in sub_ids2]) + ')',
                                table_args + sub_ids2)

                            ids3.extend([x[0] for x in cursor.fetchall()])

                        domain[i] = ('id', 'in', ids3)
                i += 1
            elif field._type == 'many2many':
                # XXX must find a solution for long id list
                if hasattr(field, 'model_name'):
                    target_obj = self.pool.get(field.model_name)
                else:
                    target_obj = field.get_target(self.pool)
                if domain[i][1] in ('child_of', 'not child_of'):
                    if isinstance(domain[i][2], basestring):
                        ids2 = [x[0] for x in target_obj.search(cursor, user, [
                            ('rec_name', 'ilike', domain[i][2]),
                            ], context=context)]
                    elif isinstance(domain[i][2], (int, long)):
                        ids2 = [domain[i][2]]
                    else:
                        ids2 = domain[i][2]

                    def _rec_get(ids, table, parent):
                        if not ids:
                            return []
                        ids2 = table.search(cursor, user,
                                [(parent, 'in', ids), (parent, '!=', False)],
                                context=context)
                        return ids + _rec_get(ids2, table, parent)

                    if target_obj._name != table._name:
                        if len(domain[i]) != 4:
                            raise Exception('Error', 'Programming error: ' \
                                    'child_of on field "%s" is not allowed!' % \
                                    (domain[i][0],))
                        ids2 = target_obj.search(cursor, user,
                                [(domain[i][3], 'child_of', ids2)],
                                context=context)
                        relation_obj = self.pool.get(field.relation_name)
                        query1 = 'SELECT "' + field.origin + '" ' \
                                'FROM "' + relation_obj._table + '" ' \
                                'WHERE "' + field.target + '" IN (' + \
                                    ','.join(['%s' for x in ids2]) + ') ' \
                                    'AND "' + field.origin + '" IS NOT NULL'
                        query2 = [str(x) for x in ids2]
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
                        relation_obj = self.pool.get(field.relation_name)
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
                        relation_obj = self.pool.get(field.relation_name)

                        query1, query2 = target_obj.search(cursor, user, [
                                    (target_field, domain[i][1], domain[i][2]),
                                    ], order=[], query_string=True,
                                    context=context)
                        query1 = ('SELECT "%s" FROM "%s" WHERE "%s" IN (%s)' %
                                (field.origin, relation_obj._table,
                                    field.target, query1))
                        domain[i] = ('id', 'inselect', (query1, query2))
                i += 1

            elif field._type == 'many2one':
                # XXX must find a solution for long id list
                if domain[i][1] in ('child_of', 'not child_of'):
                    if isinstance(domain[i][2], basestring):
                        field_obj = self.pool.get(field.model_name)
                        ids2 = [x[0] for x in field_obj.search(cursor, user, [
                            ('rec_name', 'like', domain[i][2]),
                            ], context=context)]
                    elif isinstance(domain[i][2], (int, long)):
                        ids2 = [domain[i][2]]
                    else:
                        ids2 = domain[i][2]

                    def _rec_get(ids, table, parent):
                        if not ids:
                            return []
                        ids2 = table.search(cursor, user,
                                [(parent, 'in', ids), (parent, '!=', False)],
                                context=context)
                        return ids + _rec_get(ids2, table, parent)

                    if field.model_name != table._name:
                        if len(domain[i]) != 4:
                            raise Exception('Error', 'Programming error: ' \
                                    'child_of on field "%s" is not allowed!' % \
                                    (domain[i][0],))
                        ids2 = self.pool.get(field.model_name).search(cursor, user,
                                [(domain[i][3], 'child_of', ids2)],
                                context=context)
                        if domain[i][1] == 'child_of':
                            domain[i] = (domain[i][0], 'in', ids2, table)
                        else:
                            domain[i] = (domain[i][0], 'not in', ids2, table)
                    else:
                        if field.left and field.right and ids2:
                            cursor.execute('SELECT "' + field.left + '", ' \
                                        '"' + field.right + '" ' + \
                                    'FROM "' + self._table + '" ' + \
                                    'WHERE id IN ' + \
                                        '(' + ','.join(['%s' for x in ids2]) + ')',
                                        ids2)
                            clause = 'false '
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
                        field_obj = self.pool.get(field.model_name)
                        res_ids = field_obj.search(cursor, user, [
                            (field_obj._rec_name, domain[i][1], domain[i][2]),
                            ], context=context)
                        domain[i] = (domain[i][0], 'in', res_ids, table)
                    else:
                        domain[i] += (table,)
                i += 1
            else:
                if field.translate:
                    exprs = ['%s', '%s']
                    if domain[i][1] in ('like', 'ilike', 'not like', 'not ilike'):
                        exprs = ['%% %s%%', '%s%%']
                    oper = 'OR'
                    if domain[i][1] in ('not like', 'not ilike', '!='):
                        oper = 'AND'

                    if self._name == 'ir.model':
                        table_join = 'LEFT JOIN "ir_translation" ' \
                                'ON (ir_translation.name = ' \
                                        'ir_model.model||\',%s\' ' \
                                    'AND ir_translation.res_id = 0 ' \
                                    'AND ir_translation.lang = %%s ' \
                                    'AND ir_translation.type = \'model\' ' \
                                    'AND ir_translation.fuzzy = false)' % \
                                (domain[i][0],)
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
                                    'AND ir_translation = %%s ' \
                                    'AND ir_translation.type = \'%s\' ' \
                                    'AND ir_translation.fuzzy = false)' % \
                                (table._table, ttype)
                    else:
                        table_join = 'LEFT JOIN "ir_translation" ' \
                                'ON (ir_translation.res_id = %s.id ' \
                                    'AND ir_translation.name = \'%s,%s\' ' \
                                    'AND ir_translation.lang = %%s ' \
                                    'AND ir_translation.type = \'model\' ' \
                                    'AND ir_translation.fuzzy = false)' % \
                                (table._table, table._name, domain[i][0])
                    table_join_args = [context.get('language') or 'en_US']

                    table_query = ''
                    table_args = []
                    if table.table_query(context):
                        table_query, table_args = table.table_query(context)
                        table_query = '(' + table_query  + ') AS '

                    trans_field = 'COALESCE(NULLIF(' \
                            'ir_translation.value, \'\'), ' \
                            + '"' + table._table + '".' + domain[i][0] + ')'

                    query1 = '(SELECT "' + table._table + '".id ' \
                            'FROM ' + table_query + '"' + table._table + '" ' \
                            + table_join + ' ' \
                            'WHERE (' + trans_field + ' ' + \
                            domain[i][1] + ' %s ' + oper + ' ' + trans_field + ' ' + \
                            domain[i][1] + ' %s))'
                    query2 = table_args + table_join_args + [exprs[0] % domain[i][2],
                            exprs[1] % domain[i][2]]
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
                qu1.append('("%s".%s %s (%s))' % (table._table, arg[0], clause,
                    arg[2][0]))
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
                    #TODO fix max_stack_depth
                    if len(arg2):
                        if arg[0] == 'id':
                            qu1.append(('("%s".id ' + arg[1] + ' (%s))') % \
                                    (table._table,
                                        ','.join(['%s'] * len(arg2)),))
                        else:
                            qu1.append(('("%s".%s ' + arg[1] + ' (%s))') % \
                                    (table._table, arg[0], ','.join(
                                        ['%s'] * len(arg2))))
                        if todel:
                            if table._columns[arg[0]]._type == 'boolean':
                                if arg[1] == 'in':
                                    qu1[-1] = '(' + qu1[-1] + ' OR ' \
                                            '"%s".%s = false)' % \
                                            (table._table, arg[0])
                                else:
                                    qu1[-1] = '(' + qu1[-1] + ' AND ' \
                                            '"%s".%s != false)' % \
                                            (table._table, arg[0])
                            else:
                                if arg[1] == 'in':
                                    qu1[-1] = '(' + qu1[-1] + ' OR ' \
                                            '"%s".%s IS NULL)' % \
                                            (table._table, arg[0])
                                else:
                                    qu1[-1] = '(' + qu1[-1] + ' AND ' \
                                            '"%s".%s IS NOT NULL)' % \
                                            (table._table, arg[0])
                        qu2 += arg2
                    elif todel:
                        if table._columns[arg[0]]._type == 'boolean':
                            if arg[1] == 'in':
                                qu1.append('("%s".%s = false)' % \
                                        (table._table, arg[0]))
                            else:
                                qu1.append('("%s".%s != false)' % \
                                        (table._table, arg[0]))
                        else:
                            if arg[1] == 'in':
                                qu1.append('("%s".%s IS NULL)' % \
                                        (table._table, arg[0]))
                            else:
                                qu1.append('("%s".%s IS NOT NULL)' % \
                                        (table._table, arg[0]))
                else:
                    if arg[1] == 'in':
                        qu1.append(' false')
                    else:
                        qu1.append(' true')
            else:
                if (arg[2] is False) and (arg[1] == '='):
                    if table._columns[arg[0]]._type == 'boolean':
                        qu1.append('("%s".%s = false)' % \
                                (table._table, arg[0]))
                    else:
                        qu1.append('("%s".%s IS NULL)' % \
                                (table._table, arg[0]))
                elif (arg[2] is False) and (arg[1] == '!='):
                    qu1.append('("%s".%s IS NOT NULL)' % \
                            (table._table, arg[0]))
                else:
                    if arg[0] == 'id':
                        qu1.append('("%s".%s %s %%s)' % \
                                (table._table, arg[0], arg[1]))
                        qu2.append(FIELDS[table._columns[arg[0]]._type].\
                                sql_format(arg[2]))
                    else:
                        add_null = False
                        if arg[1] in ('like', 'ilike'):
                            if not arg[2]:
                                qu2.append('%')
                                qu2.append('%')
                                add_null = True
                            else:
                                qu2.append('%% %s%%' % arg[2])
                                qu2.append('%s%%' % arg[2])
                        elif arg[1] in ('not like', 'not ilike'):
                            if not arg[2]:
                                qu2.append('')
                                qu2.append('')
                            else:
                                qu2.append('%% %s%%' % arg[2])
                                qu2.append('%s%%' % arg[2])
                                add_null = True
                        else:
                            if arg[0] in table._columns:
                                qu2.append(FIELDS[table._columns[arg[0]]._type].\
                                        sql_format(arg[2]))
                        if arg[1] in ('like', 'ilike'):
                            qu1.append('("%s".%s %s %s OR "%s".%s %s %s)' % \
                                    (table._table, arg[0], arg[1], '%s',
                                        table._table, arg[0], arg[1], '%s'))
                        elif arg[1] in ('not like', 'not ilike'):
                            qu1.append('("%s".%s %s %s AND "%s".%s %s %s)' % \
                                    (table._table, arg[0], arg[1], '%s',
                                        table._table, arg[0], arg[1], '%s'))
                        else:
                            qu1.append('("%s".%s %s %%s)' % (table._table,
                                arg[0], arg[1]))
                        if add_null:
                            qu1[-1] = '(' + qu1[-1] + ' OR ' + \
                                    '"' + table._table + '".' + arg[0] +' IS NULL)'

        return qu1, qu2

    def _order_calc(self, cursor, user, field, otype, context=None):
        order_by = []
        tables = []
        tables_args = {}
        field_name = None
        table_name = None
        link_field = None

        if context is None:
            context = {}

        if field in self._columns:
            table_name = self._table

            if not hasattr(self._columns[field], 'set'):
                field_name = field

            if self._columns[field].order_field:
                field_name = self._columns[field].order_field

            if isinstance(self._columns[field], fields.Many2One):
                obj = self.pool.get(self._columns[field].model_name)
                table_name = obj._table
                link_field = field
                field_name = None

                if obj._rec_name in obj._columns:
                    field_name = obj._rec_name

                if obj._order_name in obj._columns:
                    field_name = obj._order_name

                if field_name:
                    order_by, tables, tables_args = obj._order_calc(cursor,
                            user, field_name, otype, context=context)
                    table_join = 'LEFT JOIN "' + table_name + '" AS ' \
                            '"' + table_name + '.' + link_field + '" ON ' \
                            '"%s.%s".id = "%s".%s' % (table_name, link_field,
                                    self._table, link_field)
                    for i in range(len(order_by)):
                        if table_name in order_by[i]:
                            order_by[i] = order_by[i].replace(table_name,
                                    table_name + '.' + link_field)
                    for i in range(len(tables)):
                        if table_name in tables[i]:
                            args = tables_args[tables[i]]
                            del tables_args[tables[i]]
                            tables[i] = tables[i].replace(table_name,
                                    table_name + '.' + link_field)
                            tables_args[tables[i]] = args
                    if table_join not in tables:
                        tables.insert(0, table_join)
                    return order_by, tables, tables_args

                obj2 = None
                if obj._rec_name in obj._inherit_fields.keys():
                    obj2 = self.pool.get(
                            obj._inherit_fields[obj._rec_name][0])
                    field_name = obj._rec_name

                if obj._order_name in obj._inherit_fields.keys():
                    obj2 = self.pool.get(
                            obj._inherit_fields[obj._order_name][0])
                    field_name = obj._order_name

                if obj2 and field_name:
                    table_name2 = obj2._table
                    link_field2 = obj._inherits[obj2._name]
                    order_by, tables, tables_args = obj2._order_calc(cursor,
                            user, field_name, otype, context=context)

                    table_join = 'LEFT JOIN "' + table_name + '" AS ' \
                            '"' + table_name + '.' + link_field + '" ON ' \
                            '"%s.%s".id = "%s".%s' % \
                            (table_name, link_field, self._table, link_field)
                    for i in range(len(order_by)):
                        if table_name in order_by[i]:
                            order_by[i] = order_by[i].replace(table_name,
                                    table_name + '.' + link_field)
                    for i in range(len(tables)):
                        if table_name in tables[i]:
                            args = tables_args[tables[i]]
                            del tables_args[tables[i]]
                            tables[i] = tables[i].replace(table_name,
                                    table_name + '.' + link_field)
                            tables_args[tables[i]] = args
                    if table_join not in tables:
                        tables.insert(0, table_join)

                    table_join2 = 'LEFT JOIN "' + table_name2 + '" AS ' \
                            '"' + table_name2 + '.' + link_field2 + '" ON ' \
                            '"%s.%s".id = "%s.%s".%s' % \
                            (table_name2, link_field2, table_name, link_field,
                                    link_field2)
                    for i in range(len(order_by)):
                        if table_name2 in order_by[i]:
                            order_by[i] = order_by[i].replace(table_name2,
                                    table_name2 + '.' + link_field2)
                    for i in range(len(tables)):
                        if table_name2 in tables[i]:
                            args = tables_args[tables[i]]
                            del tables_args[tables[i]]
                            tables[i] = tables[i].replace(table_name2,
                                    table_name2 + '.' + link_field2)
                            tables_args[tables[i]] = args
                    if table_join2 not in tables:
                        tables.insert(1, table_join2)
                    return order_by, tables, tables_args

            if field_name in self._columns \
                    and self._columns[field_name].translate:
                translation_table = 'ir_translation_%s_%s' % \
                        (table_name, field_name)
                if self._name == 'ir.model':
                    table_join = 'LEFT JOIN "ir_translation" ' \
                            'AS "%s" ON ' \
                            '("%s".name = "ir_model".model||\',%s\' ' \
                                'AND "%s".res_id = 0 ' \
                                'AND "%s".lang = %%s ' \
                                'AND "%s".type = \'model\' ' \
                                'AND "%s".fuzzy = false)' % \
                            (translation_table, translation_table, field_name,
                                    translation_table, translation_table,
                                    translation_table, translation_table)
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
                                'AND "%s".fuzzy = false)' % \
                            (translation_table, translation_table, table_name,
                                    translation_table, translation_table,
                                    translation_table, ttype, translation_table)
                else:
                    table_join = 'LEFT JOIN "ir_translation" ' \
                            'AS "%s" ON ' \
                            '("%s".res_id = "%s".id ' \
                                'AND "%s".name = \'%s,%s\' ' \
                                'AND "%s".lang = %%s ' \
                                'AND "%s".type = \'model\' ' \
                                'AND "%s".fuzzy = false)' % \
                            (translation_table, translation_table, table_name,
                                    translation_table, self._name, field_name,
                                    translation_table, translation_table,
                                    translation_table)
                if table_join not in tables:
                    tables.append(table_join)
                    tables_args[table_join] = [context.get('language') or 'en_US']
                order_by.append('COALESCE(NULLIF(' \
                        + '"' + translation_table + '".value, \'\'), ' \
                        + '"' + table_name + '".' + field_name + ') ' + otype)
                return order_by, tables, tables_args

            if field_name in self._columns \
                    and self._columns[field_name]._type == 'selection' \
                    and self._columns[field_name].order_field is None:
                selections = self.fields_get(cursor, user, [field_name],
                        context=context)[field_name]['selection']
                if not isinstance(selections, (tuple, list)):
                    selections = getattr(self,
                            self._columns[field_name].selection)(cursor,
                                    user, context=context)
                order = 'CASE ' + table_name + '.' + field_name
                for selection in selections:
                    order += ' WHEN \'%s\' THEN \'%s\'' % selection
                order += ' ELSE ' + table_name + '.' + field_name + ' END'
                order_by.append(order + ' ' + otype)
                return order_by, tables, tables_args

            if field_name:
                if '%(table)s' in field_name or '%(order)s' in field_name:
                    order_by.append(field_name % {
                        'table': table_name,
                        'order': otype,
                        })
                else:
                    order_by.append('"' + table_name + '".' + field_name + ' ' + otype)
                return order_by, tables, tables_args

        if field in self._inherit_fields.keys():
            obj = self.pool.get(self._inherit_fields[field][0])
            table_name = obj._table
            link_field = self._inherits[obj._name]
            order_by, tables, tables_args = obj._order_calc(cursor, user, field,
                    otype, context=context)
            table_join = 'LEFT JOIN "' + table_name + '" ON ' \
                    '"%s".id = "%s".%s' % \
                    (table_name, self._table, link_field)
            if table_join not in tables:
                tables.insert(0, table_join)
            return order_by, tables, tables_args

        raise Exception('Error', 'Wrong field name (%s) in order!' % field)

    def _rebuild_tree(self, cursor, user, parent, parent_id, left):
        '''
        Rebuild left, right value for the tree.
        '''
        right = left + 1

        child_ids = self.search(cursor, 0, [
            (parent, '=', parent_id),
            ])

        for child_id in child_ids:
            right = self._rebuild_tree(cursor, user, parent, child_id, right)

        field = self._columns[parent]

        if parent_id:
            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET "' + field.left + '" = %s, ' \
                        '"' + field.right + '" = %s ' \
                    'WHERE id = %s', (left, right, parent_id))
        return right + 1

    def _update_tree(self, cursor, user, object_id, field_name, left, right):
        '''
        Update left, right values for the tree.
        Remarks:
            - the value (right - left - 1) / 2 will not give
                the number of children node
            - the order of the tree respects the default _order
        '''
        cursor.execute('SELECT "' + left + '", "' + right + '" ' \
                'FROM "' + self._table + '" ' \
                'WHERE id = %s', (object_id,))
        if not cursor.rowcount:
            return
        old_left, old_right = cursor.fetchone()
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
            if cursor.rowcount:
                parent_right = cursor.fetchone()[0] + 1

        cursor.execute('SELECT id FROM "' + self._table + '" ' \
                'WHERE "' + left + '" >= %s AND "' + right + '" <= %s',
                (old_left, old_right))
        child_ids = [x[0] for x in cursor.fetchall()]

        if len(child_ids) > cursor.IN_MAX:
            return self._rebuild_tree(cursor, 0, field_name, False, 0)

        # ids for left update
        cursor.execute('SELECT id FROM "' + self._table + '" ' \
                'WHERE "' + left + '" >= %s ' \
                    'AND id NOT IN (' + ','.join(['%s' for x in child_ids]) + ')',
                    [parent_right] + child_ids)
        left_ids = [x[0] for x in cursor.fetchall()]

        # ids for right update
        cursor.execute('SELECT id FROM "' + self._table + '" ' \
                'WHERE "' + right + '" >= %s ' \
                    'AND id NOT IN (' + ','.join(['%s' for x in child_ids]) + ')',
                    [parent_right] + child_ids)
        right_ids = [x[0] for x in cursor.fetchall()]

        if left_ids:
            for i in range(0, len(left_ids), cursor.IN_MAX):
                sub_ids = left_ids[i:i + cursor.IN_MAX]
                str_d = ','.join(('%s',) * len(sub_ids))
                cursor.execute('UPDATE "' + self._table + '" ' \
                        'SET "' + left + '" = "' + left + '" + ' \
                            + str(old_right - old_left + 1) + ' ' \
                        'WHERE id IN (' + str_d + ')', sub_ids)
        if right_ids:
            for i in range(0, len(right_ids), cursor.IN_MAX):
                sub_ids = right_ids[i:i + cursor.IN_MAX]
                str_d = ','.join(('%s',) * len(sub_ids))
                cursor.execute('UPDATE "' + self._table + '" ' \
                        'SET "' + right + '" = "' + right + '" + ' \
                            + str(old_right - old_left + 1) + ' ' \
                        'WHERE id IN (' + str_d + ')', sub_ids)

        cursor.execute('UPDATE "' + self._table + '" ' \
                'SET "' + left + '" = "' + left + '" + ' \
                        + str(parent_right - old_left) + ', ' \
                    '"' + right + '" = "' + right + '" + ' \
                        + str(parent_right - old_left) + ' ' \
                'WHERE id IN (' + ','.join(['%s' for x in child_ids]) + ')',
                child_ids)

        # Use root user to by-pass rules
        brother_ids = self.search(cursor, 0, [
            (field_name, '=', parent_id),
            ], context={'active_test': False})
        if brother_ids[-1] != object_id:
            next_id = brother_ids[brother_ids.index(object_id) + 1]
            cursor.execute('SELECT "' + left + '",  "' + right + '" ' \
                    'FROM "' + self._table + '" ' \
                    'WHERE id = %s', (next_id,))
            next_left, next_right = cursor.fetchone()
            cursor.execute('SELECT "' + left + '", "' + right + '" '\
                    'FROM "' + self._table + '" ' \
                    'WHERE id = %s', (object_id,))
            current_left, current_right = cursor.fetchone()


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
                    'WHERE id in (' + ','.join(['%s' for x in child_ids]) + ')',
                    child_ids)
