#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
# -*- coding: utf-8 -*-
from trytond.netsvc import LocalService
import fields
from trytond.tools import Cache
import md5
import time
import traceback
import datetime
from lxml import etree
import copy
from trytond.sql_db import table_handler
from decimal import Decimal
import logging

OPERATORS = (
        'child_of',
        'not child_of',
        '=',
        '!=',
        'like',
        'not like',
        'ilike',
        'not ilike',
        'in',
        'not in',
        '<=',
        '>=',
        '<',
        '>',
    )

def intersect(i, j):
    return [x for x in j if x in i]

def exclude(i, j):
    return [x for x in i if x not in j]


# TODO: execute an object method on BrowseRecordList
class BrowseRecordList(list):
    '''
    A list of BrowseRecord
    '''

    def __init__(self, lst, context=None):
        super(BrowseRecordList, self).__init__(lst)
        self.context = context

    def get_eval(self):
        res = []
        for record in self:
            res2 = {}
            for field_name, field in record._table._columns.iteritems():
                if not isinstance(record[field_name], BrowseRecordList):
                    res2[field_name] = record.get_eval(field_name)
            res.append(res2)
        return res


class BrowseRecordNull(object):
    '''
    An object that represents an empty record.
    '''

    def __init__(self):
        self.id = False

    def __getitem__(self, name):
        return False

    def __int__(self):
        return False

    def __str__(self):
        return ''

    def __nonzero__(self):
        return False


class BrowseRecord(object):
    '''
    An object that represents record defined by a ORM object.
    '''

    def __init__(self, cursor, user, object_id, table, cache, context=None):
        '''
        table : the object (inherited from orm)
        context : a dictionnary with an optionnal context
        '''
        self._cursor = cursor
        self._user = user
        self._id = object_id
        self._table = table
        self._table_name = self._table._name
        self._context = context
        self._language_cache = {}

        cache.setdefault(table._name, {})
        self._data = cache[table._name]
        if not object_id in self._data:
            self._data[object_id] = {'id': object_id}
        self._cache = cache

    def __getitem__(self, name):
        if name == 'id':
            return self._id
        if name == 'setLang':
            return self.setLang
        if not self._data[self._id].has_key(name):
            # build the list of fields we will fetch

            # fetch the definition of the field which was asked for
            if name in self._table._columns:
                col = self._table._columns[name]
            elif name in self._table._inherit_fields:
                col = self._table._inherit_fields[name][2]
            elif hasattr(self._table, name):
                return getattr(self._table, name)
            else:
                raise Exception('Error', 'Programming error: field "%s" ' \
                        'does not exist in object "%s"!' \
                        % (name, self._table._name))

            # if the field is a classic one or a many2one,
            # we'll fetch all classic and many2one fields
            if col._classic_write:
                # gen the list of "local" (ie not inherited)
                # fields which are classic or many2one
                ffields = [x for x in self._table._columns.items() \
                        if x[1]._classic_write]
                # gen the list of inherited fields
                inherits = [(x[0], x[1][2]) for x in \
                        self._table._inherit_fields.items()]
                # complete the field list with the inherited fields
                # which are classic or many2one
                ffields += [x for x in inherits if x[1]._classic_write]
            # otherwise we fetch only that field
            else:
                ffields = [(name, col)]
            ids = [x for x in self._data.keys() \
                    if not self._data[x].has_key(name)]
            # read the data
            datas = self._table.read(self._cursor, self._user, ids,
                    [x[0] for x in ffields], context=self._context,
                    load="_classic_write")

            # create browse records for 'remote' objects
            for data in datas:
                for i, j in ffields:
                    if not j._obj in self._table.pool.object_name_list():
                        continue
                    obj = self._table.pool.get(j._obj)
                    if j._type in ('many2one',):
                        if not j._classic_write and data[i]:
                            if isinstance(data[i][0], (list, tuple)):
                                ids2 = data[i][0][0]
                            else:
                                ids2 = data[i][0]
                        else:
                            ids2 = data[i]
                        if ids2 is False:
                            data[i] = BrowseRecordNull()
                        else:
                            data[i] = BrowseRecord(self._cursor, self._user,
                                    ids2, obj, self._cache,
                                    context=self._context)
                    elif j._type in ('one2many', 'many2many') and len(data[i]):
                        data[i] = BrowseRecordList([BrowseRecord(self._cursor,
                            self._user, x, obj,
                            self._cache, context=self._context) for x in data[i]],
                            self._context)
                self._data[data['id']].update(data)
        return self._data[self._id][name]

    def __getattr__(self, name):
        # TODO raise an AttributeError exception
        return self[name]

    def __contains__(self, name):
        return (name in self._table._columns) \
                or (name in self._table._inherit_fields) \
                or hasattr(self._table, name)

    def __hasattr__(self, name):
        return name in self

    def __int__(self):
        return self._id

    def __str__(self):
        return "BrowseRecord(%s, %d)" % (self._table_name, self._id)

    def __eq__(self, other):
        return (self._table_name, self._id) == (other._table_name, other._id)

    def __ne__(self, other):
        return (self._table_name, self._id) != (other._table_name, other._id)

    # we need to define __unicode__ even though we've already defined __str__
    # because we have overridden __getattr__
    def __unicode__(self):
        return unicode(str(self))

    def __hash__(self):
        return hash((self._table_name, self._id))

    def __nonzero__(self):
        return bool(self._id)

    __repr__ = __str__

    def setLang(self, lang):
        self._context = self._context.copy()
        prev_lang = self._context.get('language', 'en_US')
        self._context['language'] = lang
        for table in self._cache:
            for obj_id in self._cache[table]:
                self._language_cache.setdefault(prev_lang,
                        {}).setdefault(table, {}).update(
                                self._cache[table][obj_id])
                if lang in self._language_cache \
                        and table in self._language_cache[lang] \
                        and obj_id in self._language_cache[lang][table]:
                    self._cache[table][obj_id] = \
                            self._language_cache[lang][table][obj_id]
                else:
                    self._cache[table][obj_id] = {'id': obj_id}

    def get_eval(self, name):
        res = self[name]
        if isinstance(res, BrowseRecord):
            res = res.id
        if isinstance(res, BrowseRecordList):
            res = res.get_eval()
        if isinstance(res, BrowseRecordNull):
            res = False
        return res


class EvalEnvironment(dict):

    def __init__(self, record, obj):
        super(EvalEnvironment, self).__init__()
        self.record = record
        self.obj = obj

    def __getitem__(self, item):
        if item.startswith('_parent_'):
            field = item[8:]
            if field in self.obj._columns:
                _obj = self.obj._columns[field]._obj
            else:
                _obj = self.obj._inherit_fields[field][2]._obj
            obj = self.obj.pool.get(_obj)
            return EvalEnvironment(self.record[field], obj)
        if item in self.obj._columns \
                or item in self.obj._inherit_fields:
            return self.record.get_eval(item)
        return super(EvalEnvironment, self).__getitem__(item)

    def __getattr__(self, item):
        return self.__getitem__(item)


class ORM(object):
    """
    Object relationnal mapping to postgresql module
       . Hierarchical structure
       . Constraints consistency, validations
       . Object meta Data depends on its status
       . Optimised processing by complex query (multiple actions at once)
       . Default fields value
       . Permissions optimisation
       . Persistant object: DB postgresql
       . Datas conversions
       . Multi-level caching system
       . 2 different inheritancies
       . Fields:
            - classicals (varchar, integer, boolean, ...)
            - relations (one2many, many2one, many2many)
            - functions
    """
    _table = None
    _name = None
    _rec_name = 'name'
    _order_name = None # Use to force order field when sorting on Many2One
    _date_name = 'date'
    _order = None
    _inherits = {} #XXX remove from class instance
    _sequence = None
    _description = ''
    _auto = True
    _sql = ''
    pool = None
    __columns = None
    __defaults = None

    def _reset_columns(self):
        self.__columns = None

    def _getcolumns(self):
        if self.__columns:
            return self.__columns
        res = {}
        for attr in dir(self):
            if attr in ('_columns', '_defaults'):
                continue
            if isinstance(getattr(self, attr), fields.Column):
                res[attr] = getattr(self, attr)
        self.__columns = res
        return res

    _columns = property(fget=_getcolumns)

    def _reset_defaults(self):
        self.__defaults = None

    def _getdefaults(self):
        if self.__defaults:
            return self.__defaults
        res = {}
        columns = self._columns.keys()
        columns += self._inherit_fields.keys()
        for column in columns:
            if getattr(self, 'default_' + column, False):
                res[column] = getattr(self, 'default_' + column)
        self.__defaults = res
        return res

    _defaults = property(fget=_getdefaults)

    def _field_create(self, cursor, module_name):
        cursor.execute("SELECT id FROM ir_model WHERE model = %s",
                (self._name,))
        if not cursor.rowcount:
            # reference model in order to have a description
            # of its fonctionnality in custom_report
            cursor.execute("INSERT INTO ir_model " \
                    "(model, name, info, module) VALUES (%s, %s, %s, %s)",
                    (self._name, self._description, self.__doc__,
                        module_name))
            cursor.execute("SELECT id FROM ir_model WHERE model = %s",
                    (self._name,))
            (model_id,) = cursor.fetchone()
        else:
            (model_id,) = cursor.fetchone()
            cursor.execute('UPDATE ir_model ' \
                    'SET name = %s, ' \
                        'info = %s ' \
                    'WHERE id = %s',
                    (self._description, self.__doc__, model_id))

        cursor.execute('SELECT f.id AS id, f.name AS name, ' \
                    'f.field_description AS field_description, ' \
                    'f.ttype AS ttype, f.relation AS relation, ' \
                    'f.module as module, f.help AS help '\
                'FROM ir_model_field AS f, ir_model AS m ' \
                'WHERE f.model = m.id ' \
                    'AND m.model = %s ',
                        (self._name,))
        columns = {}
        for column in cursor.dictfetchall():
            columns[column['name']] = column
        cursor.execute('SELECT id, name, src, type FROM ir_translation ' \
                'WHERE lang = %s ' \
                    'AND type IN (%s, %s, %s) ' \
                    'AND name IN ' \
                        '(' + ','.join(['%s' for x in self._columns]) + ')',
                        ('en_US', 'field', 'help', 'selection') + \
                                tuple([self._name + ',' + x \
                                    for x in self._columns]))
        trans_columns = {}
        trans_help = {}
        trans_selection = {}
        for trans in cursor.dictfetchall():
            if trans['type'] == 'field':
                trans_columns[trans['name']] = trans
            elif trans['type'] == 'help':
                trans_help[trans['name']] = trans
            elif trans['type'] == 'selection':
                trans_selection.setdefault(trans['name'], {})
                trans_selection[trans['name']][trans['src']] = trans
        for k in self._columns:
            field = self._columns[k]
            if k not in columns:
                cursor.execute("INSERT INTO ir_model_field " \
                        "(model, name, field_description, ttype, " \
                            "relation, help, module) " \
                        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (model_id, k, field.string, field._type,
                            field._obj or '', field.help, module_name))
            elif columns[k]['field_description'] != field.string \
                    or columns[k]['ttype'] != field._type \
                    or columns[k]['relation'] != (field._obj or '') \
                    or columns[k]['help'] != field.help:
                cursor.execute('UPDATE ir_model_field ' \
                        'SET field_description = %s, ' \
                            'ttype = %s, ' \
                            'relation = %s, ' \
                            'help = %s ' \
                        'WHERE id = %s ',
                        (field.string, field._type, field._obj or '',
                            field.help, columns[k]['id']))
            trans_name = self._name + ',' + k
            if trans_name not in trans_columns:
                if k not in ('create_uid', 'create_date',
                            'write_uid', 'write_date', 'id'):
                    cursor.execute('INSERT INTO ir_translation ' \
                            '(name, lang, type, src, value, module, fuzzy) ' \
                            'VALUES (%s, %s, %s, %s, %s, %s, false)',
                            (trans_name, 'en_US', 'field',
                                field.string, '', module_name))
            elif trans_columns[trans_name]['src'] != field.string:
                cursor.execute('UPDATE ir_translation ' \
                        'SET src = %s ' \
                        'WHERE id = %s ',
                        (field.string, trans_columns[trans_name]['id']))
            if trans_name not in trans_help:
                if field.help:
                    cursor.execute('INSERT INTO ir_translation ' \
                            '(name, lang, type, src, value, module, fuzzy) ' \
                            'VALUES (%s, %s, %s, %s, %s, %s, false)',
                            (trans_name, 'en_US', 'help',
                                field.help, '', module_name))
            elif trans_help[trans_name]['src'] != field.help:
                cursor.execute('UPDATE ir_translation ' \
                        'SET src = %s ' \
                        'WHERE id = %s ',
                        (field.help, trans_help[trans_name]['id']))
            if hasattr(field, 'selection') \
                    and isinstance(field.selection, (tuple, list)):
                for (key, val) in field.selection:
                    if trans_name not in trans_selection \
                            or val not in trans_selection[trans_name]:
                        cursor.execute('INSERT INTO ir_translation ' \
                                '(name, lang, type, src, value, ' \
                                    'module, fuzzy) ' \
                                'VALUES (%s, %s, %s, %s, %s, %s, false)',
                                (trans_name, 'en_US', 'selection', val, '',
                                    module_name))
        # Clean ir_model_field from field that are no more existing.
        for k in columns:
            if columns[k]['module'] == module_name and k not in self._columns:
                # XXX This delete field even when it is defined later in the module
                cursor.execute('DELETE FROM ir_model_field '\
                                   'WHERE id = %s',
                               (columns[k]['id'],))

    def auto_init(self, cursor, module_name):
        self.init(cursor, module_name)
        self._auto_init(cursor, module_name)

    def init(self, cursor, module_name):
        cursor.execute('SELECT id, src FROM ir_translation ' \
                'WHERE lang = %s ' \
                    'AND type = %s ' \
                    'AND name = %s',
                ('en_US', 'error', self._name))
        trans_error = {}
        for trans in cursor.dictfetchall():
            trans_error[trans['src']] = trans

        errors = self._error_messages.values() + self._sql_error_messages.values()
        for _, _, error in self._sql_constraints:
            errors.append(error)
        for error in set(errors):
            if error not in trans_error:
                cursor.execute('INSERT INTO ir_translation ' \
                        '(name, lang, type, src, value, module, fuzzy) ' \
                        'VALUES (%s, %s, %s, %s, %s, %s, false)',
                        (self._name, 'en_US', 'error', error, '', module_name))

    def _auto_init(self, cursor, module_name):
        self._field_create(cursor, module_name)
        if not self._auto or self.table_query():
            # No db table for this object.
            return

        table = table_handler(cursor, self._table, self._name, module_name)
        logs = (
            ('create_date', 'timestamp', 'TIMESTAMP',
                fields.DateTime._symbol_set, lambda *a: datetime.datetime.now()),
            ('write_date', 'timestamp', 'TIMESTAMP',
                fields.DateTime._symbol_set, None),
            ('create_uid', 'int4',
             'INTEGER REFERENCES res_user ON DELETE SET NULL',
             fields.Integer._symbol_set, lambda *a: 0),
            ('write_uid', 'int4',
             'INTEGER REFERENCES res_user ON DELETE SET NULL',
             fields.Integer._symbol_set, None),
            )
        for log in logs:
            table.add_raw_column(log[0], (log[1], log[2]), log[3],
                    default_fun=log[4], migrate=False)
        for field_name, field in self._columns.iteritems():
            default_fun = None
            if field_name in (
                    'id',
                    'write_uid',
                    'write_date',
                    'create_uid',
                    'create_date',
                    ):
                continue

            if field._classic_write:
                if field_name in self._defaults:
                    default_fun = self._defaults[field_name]

                    def unpack_wrapper(fun):
                        def unpack_result(*a):
                            try: # XXX ugly hack: some default fct try
                                 # to access the non-existing table
                                result = fun(*a)
                            except:
                                return None
                            clean_results = self.__clean_defaults(
                                {field_name: result})
                            return clean_results[field_name]
                        return unpack_result
                    default_fun = unpack_wrapper(default_fun)

                table.add_raw_column(field_name, field.sql_type(),
                        field._symbol_set, default_fun, field.size)

                if isinstance(field, (fields.Integer, fields.Float)):
                    table.db_default(field_name, 0)

                if isinstance(field, fields.Many2One):
                    if field._obj in ('res.user', 'res.group'):
                        ref = field._obj.replace('.','_')
                    else:
                        ref = self.pool.get(field._obj)._table
                    table.add_fk(field_name, ref, field.ondelete)

                table.index_action(
                        field_name, action=field.select and 'add' or 'remove')

                required = field.required
                if isinstance(field, (fields.Integer, fields.Float,
                    fields.Boolean)):
                    required = True
                table.not_null_action(
                    field_name, action=required and 'add' or 'remove')

            elif isinstance(field, fields.Many2Many):
                if field._obj in ('res.user', 'res.group'):
                    ref = field._obj.replace('.','_')
                else:
                    ref = self.pool.get(field._obj)._table
                table.add_m2m(field_name, ref, field._rel, field.origin,
                        field.target, field.ondelete_origin,
                        field.ondelete_target)

            elif not isinstance(field, (fields.One2Many, fields.Function)):
                raise Exception('Unknow field type !')

        for field_name, field in self._columns.iteritems():
            if isinstance(field, fields.Many2One) \
                    and field._obj == self._name \
                    and field.left and field.right:
                cursor.execute('SELECT id FROM "%s" ' \
                        'WHERE "%s" IS NULL OR "%s" IS NULL '\
                            'OR "%s" = 0 OR "%s" = 0'% \
                        (self._table, field.left, field.right,
                            field.left, field.right))
                if cursor.rowcount:
                    self._rebuild_tree(cursor, 0, field_name, False, 0)


        for ident, constraint, msg in self._sql_constraints:
            table.add_constraint(ident, constraint)

    def __init__(self):
        self._rpc_allowed = [
                'read',
                'write',
                'create',
                'default_get',
                'delete',
                'fields_get',
                'fields_view_get',
                'search',
                'name_get',
                'name_search',
                'copy',
                'import_data',
                'export_data',
                'search_count',
                'search_read',
                ]
        self._sql_constraints = []
        self._constraints = []
        self._inherit_fields = []
        self._order = [('id', 'ASC')]
        self._error_messages = {}
        self._sql_error_messages = {}
        # reinit the cache on _columns and _defaults
        self.__columns = None
        self.__defaults = None

        if not self._table:
            self._table = self._name.replace('.', '_')
        if not self._description:
            self._description = self._name

        self._inherits_reload()
        if not self._sequence:
            self._sequence = self._table+'_id_seq'

        self.create_uid = fields.Many2One('res.user',
                'Create User', required=True, readonly=True)
        self.create_date = fields.DateTime('Create Date',
                required=True, readonly=True)
        self.write_uid = fields.Many2One('res.user',
                   'Write User', readonly=True)
        self.write_date = fields.DateTime(
                'Write Date', readonly=True)
        self.id = fields.Integer('ID', readonly=True)
        # reinit the cache on _columns
        self.__columns = None

        for name in self._columns.keys() + self._inherit_fields.keys():
            if name in self._columns:
                field = self._columns[name]
            else:
                field = self._inherit_fields[name][2]
            if isinstance(field, (fields.Selection, fields.Reference)) \
                    and not isinstance(field.selection, (list, tuple)) \
                    and field.selection not in self._rpc_allowed:
                self._rpc_allowed.append(field.selection)
            if field.on_change:
                on_change = 'on_change_' + name
                if on_change not in self._rpc_allowed:
                    self._rpc_allowed.append(on_change)
            if field.on_change_with:
                on_change_with = 'on_change_with_' + name
                if on_change_with not in self._rpc_allowed:
                    self._rpc_allowed.append(on_change_with)

        for k in self._defaults:
            assert (k in self._columns) or (k in self._inherit_fields), \
            'Default function defined in %s but field %s does not exist!' % \
                (self._name, k,)

    def _inherits_reload_src(self):
        "Update objects that uses this one to update their _inherits fields"
        for obj in self.pool.object_name_pool.values():
            if self._name in obj._inherits:
                obj._inherits_reload()

    def _inherits_reload(self):
        res = {}
        for table in self._inherits:
            res.update(self.pool.get(table)._inherit_fields)
            for col in self.pool.get(table)._columns.keys():
                res[col] = (table, self._inherits[table],
                        self.pool.get(table)._columns[col])
            for col in self.pool.get(table)._inherit_fields.keys():
                res[col] = (table, self._inherits[table],
                        self.pool.get(table)._inherit_fields[col][2])
        self._inherit_fields = res
        self._inherits_reload_src()

    def default_create_uid(self, cursor, user, context=None):
        "Default value for uid field"
        return user

    def default_create_date(self, cursor, user, context=None):
        "Default value for create_date field"
        return datetime.datetime.today()

    def table_query(self, context=None):
        '''
        Return None if the table object is a real table in the database
        or return a tuple wiht the query for the table object and the arguments
        '''
        return None

    def raise_user_error(self, cursor, error, error_args=None,
            error_description='', error_description_args=None,
            raise_exception=True, context=None):
        '''
        Raise an exception that will be display as an error message
        in the client.

        :param cursor: the database cursor
        :param error: the key of the dictionary _error_messages used
            for error message
        :param error_args: the arguments that will be used
            for "%"-based substitution
        :param error_description: the key of the dictionary
            _error_messages used for error description
        :param error_description_args: the arguments that will be used
            for "%"-based substitution
        :param raise_exception: if set to False return the error string
            (or tuple if error_description is not empty) instead of raising an
            exception.
        :param context: the context in which the language key will
            be used for translation
        '''
        translation_obj = self.pool.get('ir.translation')

        if context is None:
            context = {}

        error = self._error_messages.get(error, error)

        res = translation_obj._get_source(cursor, self._name, 'error',
                context.get('language', 'en_US'), error)
        if not res:
            res = translation_obj._get_source(cursor, error, 'error',
                    context.get('language', 'en_US'))
        if not res:
            res = translation_obj._get_source(cursor, error, 'error',
                        'en_US')

        if res:
            error = res

        if error_args:
            try:
                error = error % error_args
            except TypeError:
                pass

        if error_description:
            error_description = self._error_messages.get(error_description,
                    error_description)

            res = translation_obj._get_source(cursor, self._name, 'error',
                    context.get('language', 'en_US'), error_description)
            if not res:
                res = translation_obj._get_source(cursor, error_description,
                        'error', context.get('language', 'en_US'))
            if not res:
                res = translation_obj._get_source(cursor, error_description,
                        'error', 'en_US')

            if res:
                error_description = res

            if error_description_args:
                try:
                    error_description = error_description % \
                            error_description_args
                except TypeError:
                    pass
            if raise_exception:
                raise Exception('UserError', error, error_description)
            else:
                return (error, error_description)
        if raise_exception:
            raise Exception('UserError', error)
        else:
            return error

    def browse(self, cursor, user, ids, context=None):
        '''
        Return a browse a BrowseRecordList for the ids
            or BrowseRecord if ids is a integer.
        '''
        cache = {}
        # need to accepts ints and longs because ids coming from a method
        # launched by button in the interface have a type long...
        if isinstance(ids, (int, long)):
            return BrowseRecord(cursor, user, ids, self, cache,
                    context=context)
        return BrowseRecordList([BrowseRecord(cursor, user, x, self, cache,
            context=context) for x in ids], context)

    def __export_row(self, cursor, user, row, fields_names, context=None):
        lines = []
        data = ['' for x in range(len(fields_names))]
        done = []
        for fpos in range(len(fields_names)):
            field = fields_names[fpos]
            if field:
                row2 = row
                i = 0
                while i < len(field):
                    row2 = row2[field[i]]
                    if not row2:
                        break
                    if isinstance(row2, (BrowseRecordList, list)):
                        first = True
                        fields2 = [(x[:i+1]==field[:i+1] and x[i+1:]) \
                                or [] for x in fields_names]
                        if fields2 in done:
                            break
                        done.append(fields2)
                        for row2 in row2:
                            lines2 = self.__export_row(cursor, user, row2,
                                    fields2, context)
                            if first:
                                for fpos2 in range(len(fields_names)):
                                    if lines2 and lines2[0][fpos2]:
                                        data[fpos2] = lines2[0][fpos2]
                                lines += lines2[1:]
                                first = False
                            else:
                                lines += lines2
                        break
                    i += 1
                if i == len(field):
                    data[fpos] = row2 or ''
        return [data] + lines

    def export_data(self, cursor, user, ids, fields_names, context=None):
        '''
        Return list of list of values for each ids.
        The list of values follow the fields_names.
        Relational fields are defined with '/' at any deep.
        '''
        fields_names = [x.split('/') for x in fields_names]
        datas = []
        for row in self.browse(cursor, user, ids, context):
            datas += self.__export_row(cursor, user, row, fields_names, context)
        return datas

    # TODO: Send a request with the result and multi-thread !
    def import_data(self, cursor, user, fields_names, datas, context=None):
        '''
        Create record for each values in datas.
        The fields name of values must be defined in fields_names.
        '''
        if context is None:
            context = {}
        fields_names = [x.split('/') for x in fields_names]
        logger = logging.getLogger('import')

        def process_liness(self, datas, prefix, fields_def, position=0):
            line = datas[position]
            row = {}
            translate = {}
            todo = []
            warning = ''

            # Import normal fields_names
            for i in range(len(fields_names)):
                if i >= len(line):
                    raise Exception('ImportError',
                            'Please check that all your lines have %d cols.' % \
                            (len(fields_names),))
                field = fields_names[i]
                if (len(field) == len(prefix) + 1) \
                        and field[len(prefix)].endswith(':id'):
                    res_id = False
                    if line[i]:
                        if fields_def[field[len(prefix)][:-3]]['type'] \
                                == 'many2many':
                            res_id = []
                            for word in line[i].split(','):
                                module, xml_id = word.rsplit('.', 1)
                                ir_model_data_obj = \
                                        self.pool.get('ir.model.data')
                                new_id = ir_model_data_obj._get_id(cursor,
                                        user, module, xml_id)
                                res_id2 = ir_model_data_obj.read(cursor, user,
                                        [new_id], ['res_id'])[0]['res_id']
                                if res_id2:
                                    res_id.append(res_id2)
                            if len(res_id):
                                res_id = [('set', res_id)]
                        else:
                            module, xml_id = line[i].rsplit('.', 1)
                            ir_model_data_obj = self.pool.get('ir.model.data')
                            new_id = ir_model_data_obj._get_id(cursor, user,
                                    module, xml_id)
                            res_id = ir_model_data_obj.read(cursor, user,
                                    [new_id], ['res_id'])[0]['res_id']
                    row[field[0][:-3]] = res_id or False
                    continue
                if (len(field) == len(prefix)+1) and \
                        len(field[len(prefix)].split(':lang=')) == 2:
                    field, lang = field[len(prefix)].split(':lang=')
                    translate.setdefault(lang, {})[field]=line[i] or False
                    continue
                if (len(field) == len(prefix)+1) and \
                        (prefix == field[0:len(prefix)]):
                    if fields_def[field[len(prefix)]]['type'] == 'integer':
                        res = line[i] and int(line[i])
                    elif fields_def[field[len(prefix)]]['type'] == 'float':
                        res = line[i] and float(line[i])
                    elif fields_def[field[len(prefix)]]['type'] == 'selection':
                        res = False
                        if isinstance(
                                fields_def[field[len(prefix)]]['selection'],
                                (tuple, list)):
                            sel = fields_def[field[len(prefix)]]['selection']
                        else:
                            sel = getattr(self, fields_def[field[len(prefix)]]\
                                    ['selection'])(cursor, user, context)
                        for key, val in sel:
                            if str(key) == line[i]:
                                res = key
                        if line[i] and not res:
                            logger.warning("key '%s' not found " \
                                               "in selection field '%s'" % \
                                               (line[i], field[len(prefix)]))
                    elif fields_def[field[len(prefix)]]['type'] == 'many2one':
                        res = False
                        if line[i]:
                            relation = \
                                    fields_def[field[len(prefix)]]['relation']
                            res2 = self.pool.get(relation).name_search(cursor,
                                    user, line[i], [], operator='=')
                            res = (res2 and res2[0][0]) or False
                            if not res:
                                warning += ('Relation not found: ' + line[i] + \
                                        ' on ' + relation + ' !\n')
                                logger.warning(
                                    'Relation not found: ' + line[i] + \
                                        ' on ' + relation + ' !\n')
                    elif fields_def[field[len(prefix)]]['type'] == 'many2many':
                        res = []
                        if line[i]:
                            relation = \
                                    fields_def[field[len(prefix)]]['relation']
                            for word in line[i].split(','):
                                res2 = self.pool.get(relation).name_search(
                                        cursor, user, word, [], operator='=')
                                res3 = (res2 and res2[0][0]) or False
                                if not res3:
                                    warning += ('Relation not found: ' + \
                                            line[i] + ' on '+relation + ' !\n')
                                    logger.warning(
                                        'Relation not found: ' + line[i] + \
                                                    ' on '+relation + ' !\n')
                                else:
                                    res.append(res3)
                            if len(res):
                                res = [('set', res)]
                    else:
                        res = line[i] or False
                    row[field[len(prefix)]] = res
                elif (prefix==field[0:len(prefix)]):
                    if field[0] not in todo:
                        todo.append(field[len(prefix)])

            # Import one2many fields
            nbrmax = 1
            for field in todo:
                newfd = self.pool.get(fields_def[field]['relation']).fields_get(
                        cursor, user, context=context)
                res = process_liness(self, datas, prefix + [field], newfd,
                        position)
                (newrow, max2, warning2, translate2) = res
                nbrmax = max(nbrmax, max2)
                warning = warning + warning2
                reduce(lambda x, y: x and y, newrow)
                row[field] = (reduce(lambda x, y: x or y, newrow.values()) and \
                        [('create', newrow)]) or []
                i = max2
                while (position+i)<len(datas):
                    test = True
                    for j in range(len(fields_names)):
                        field2 = fields_names[j]
                        if (len(field2) <= (len(prefix)+1)) \
                                and datas[position+i][j]:
                            test = False
                    if not test:
                        break

                    (newrow, max2, warning2, translate2) = \
                            process_liness(self, datas, prefix+[field], newfd,
                                    position + i)
                    warning = warning + warning2
                    if reduce(lambda x, y: x or y, newrow.values()):
                        row[field].append(('create', newrow))
                    i += max2
                    nbrmax = max(nbrmax, i)

            if len(prefix) == 0:
                for i in range(max(nbrmax, 1)):
                    datas.pop(0)
            result = (row, nbrmax, warning, translate)
            return result

        fields_def = self.fields_get(cursor, user, context=context)
        done = 0

        while len(datas):
            res = {}
            try:
                (res, other, warning, translate) = \
                        process_liness(self, datas, [], fields_def)
                if warning:
                    cursor.rollback()
                    return (-1, res, warning, '')
                new_id = self.create(cursor, user, res, context=context)
                for lang in translate:
                    context2 = context.copy()
                    context2['language'] = lang
                    self.write(cursor, user, new_id, translate[lang],
                            context=context2)
            except Exception, exp:
                logger.error(exp)
                cursor.rollback()
                return (-1, res, exp[0], warning)
            done += 1
        return (done, 0, 0, 0)

    def read(self, cursor, user, ids, fields_names=None, context=None,
            load='_classic_read'):
        '''
        Return list of a dict for each ids or just a dict if ids is an integer.
        The dict have fields_names as keys.
        '''
        self.pool.get('ir.model.access').check(cursor, user, self._name, 'read',
                context=context)
        if not fields_names:
            fields_names = self._columns.keys() + \
                    exclude(self._inherit_fields.keys(), self._columns.keys())
        select = ids
        if isinstance(ids, (int, long)):
            select = [ids]
        result =  self._read_flat(cursor, user, select, fields_names, context,
                load)
        for i in result:
            for key, j in i.items():
                if j is None:
                    i[key] = False
        if isinstance(ids, (int, long)):
            return result[0]
        return result

    def _read_flat(self, cursor, user, ids, fields_names, context=None,
            load='_classic_read'):
        if context is None:
            context = {}
        if not ids:
            return []

        if fields_names is None:
            fields_names = self._columns.keys()

        # construct a clause for the rules :
        domain1, domain2 = self.pool.get('ir.rule').domain_get(cursor, user,
                self._name, context=context)

        # all inherited fields + all non inherited fields
        # for which the attribute whose name is in load is True
        fields_pre = [x for x in fields_names if (x in self._columns \
                and getattr(self._columns[x], '_classic_write')) or \
                (x == '_timestamp')] + \
                self._inherits.values()

        res = []
        table_query = ''
        table_args = []
        if self.table_query(context):
            table_query, table_args = self.table_query(context)
            table_query = '(' + table_query + ') AS '
        if len(fields_pre) :
            fields_pre2 = [(x in ('create_date', 'write_date')) \
                    and ('date_trunc(\'second\', ' + x + ') as ' + x) \
                    or '"' + x + '"' for x in fields_pre \
                    if x != '_timestamp']
            if '_timestamp' in fields_pre:
                if not self.table_query(context):
                    fields_pre2 += ['(CASE WHEN write_date IS NOT NULL ' \
                            'THEN write_date ELSE create_date END) ' \
                            'AS _timestamp']
                else:
                    fields_pre2 += ['now()::timestamp AS _timestamp']

            if len(ids) > cursor.IN_MAX:
                cursor.execute('SELECT id ' \
                        'FROM ' + table_query + '"' + self._table + '" ' \
                        'ORDER BY ' + \
                        ','.join([self._table + '.' + x[0] + ' ' + x[1]
                            for x in self._order]), table_args)

                i = 0
                ids_sorted = {}
                for row in cursor.fetchall():
                    ids_sorted[row[0]] = i
                    i += 1
                ids = ids[:]
                ids.sort(lambda x, y: ids_sorted[x] - ids_sorted[y])

            for i in range(0, len(ids), cursor.IN_MAX):
                sub_ids = ids[i:i + cursor.IN_MAX]
                if domain1:
                    cursor.execute(('SELECT ' + \
                            ','.join(fields_pre2 + ['id']) + \
                            ' FROM ' + table_query + '\"' + self._table +'\" ' \
                            'WHERE id IN ' \
                                '(' + ','.join(['%s' for x in sub_ids]) + ')'\
                            ' AND (' + domain1 + ') ORDER BY ' + \
                            ','.join([self._table + '.' + x[0] + ' ' + x[1] \
                            for x in self._order])),
                            table_args + sub_ids + domain2)
                    if not cursor.rowcount == len({}.fromkeys(sub_ids)):
                        raise Exception('AccessError',
                                'You try to bypass an access rule ' \
                                        '(Document type: %s).' % \
                                        self._description)
                else:
                    cursor.execute('SELECT ' + \
                            ','.join(fields_pre2 + ['id']) + \
                            ' FROM ' + table_query + '\"' + self._table + '\" ' \
                            'WHERE id IN ' \
                                '(' + ','.join(['%s' for x in sub_ids]) + ')'\
                            ' ORDER BY ' + \
                            ','.join([self._table + '.' + x[0] + ' ' + x[1] \
                            for x in self._order]), table_args + sub_ids)
                res.extend(cursor.dictfetchall())
        else:
            res = [{'id': x} for x in ids]

        for field in fields_pre:
            if field == '_timestamp':
                continue
            if self._columns[field].translate:
                ids = [x['id'] for x in res]
                res_trans = self.pool.get('ir.translation')._get_ids(cursor,
                        self._name + ',' + field, 'model',
                        context.get('language', False) or 'en_US', ids)
                for i in res:
                    i[field] = res_trans.get(i['id'], False) or i[field]

        for table in self._inherits:
            col = self._inherits[table]
            cols = intersect(self._inherit_fields.keys(), fields_names)
            cols = exclude(cols, self._columns.keys())
            if not cols:
                continue
            res2 = self.pool.get(table).read(cursor, user,
                    [x[col] for x in res], cols, context, load)

            res3 = {}
            for i in res2:
                res3[i['id']] = i
                del i['id']

            for record in res:
                record.update(res3[record[col]])
                if col not in fields_names:
                    del record[col]

        # all fields which need to be post-processed
        # by a simple function (symbol_get)
        fields_post = [x for x in fields_names if x in self._columns \
                and self._columns[x]._symbol_get]
        if fields_post:
            # maybe it would be faster to iterate on the fields_names then
            # on res,  so that we wouldn't need to get the _symbol_get
            # in each occurence
            for i in res:
                for field in fields_post:
                    i[field] = self._columns[field]._symbol_get(i[field])
        ids = [x['id'] for x in res]

        # all non inherited fields for which the attribute
        # whose name is in load is False
        fields_post = [x for x in fields_names if x in self._columns \
                and not getattr(self._columns[x], load)]
        func_fields = {}
        for field in fields_post:
            if isinstance(self._columns[field], fields.Function) \
                    and not isinstance(self._columns[field], fields.Property):
                key = (self._columns[field]._fnct, self._columns[field]._arg)
                func_fields.setdefault(key, [])
                func_fields[key].append(field)
                continue
            # get the value of that field for all records/ids
            res2 = self._columns[field].get(cursor, self, ids, field, user,
                    context=context, values=res)
            for record in res:
                record[field] = res2[record['id']]
        for i in func_fields:
            field_list = func_fields[i]
            field = field_list[0]
            res2 = self._columns[field].get(cursor, self, ids, field_list, user,
                    context=context, values=res)
            for field in res2:
                for record in res:
                    record[field] = res2[field][record['id']]
        return res

    def _validate(self, cursor, user, ids, context=None):
        if context is None:
            context = {}
        context = context.copy()
        field_error = []
        field_err_str = []
        for field in self._constraints:
            if not getattr(self, field[0])(cursor, user, ids):
                self.raise_user_error(cursor, field[1], context=context)

        if not 'res.user' in self.pool.object_name_list():
            ctx_pref = {
            }
        else:
            user_obj = self.pool.get('res.user')
            ctx_pref = user_obj.get_preferences(cursor, user,
                context_only=True, context=context)

        def get_error_args(field_name):
            model_field_obj = self.pool.get('ir.model.field')
            error_args = (field_name, self._name)
            if model_field_obj:
                model_field_ids = model_field_obj.search(cursor,
                        user, [
                            ('name', '=', field_name),
                            ('model.model', '=', self._name),
                            ], context=context, limit=1)
                if model_field_ids:
                    model_field = model_field_obj.browse(cursor,
                            user, model_field_ids[0],
                            context=context)
                    error_args = (model_field.field_description,
                            model_field.model.name)
            return error_args

        context.update(ctx_pref)
        records = self.browse(cursor, user, ids, context=context)
        for field_name, field in self._columns.iteritems():
            # validate domain
            if field._type in ('many2one', 'many2many', 'one2many') \
                    and field._domain:
                relation_obj = self.pool.get(field._obj)
                if isinstance(field._domain, basestring):
                    ctx = context.copy()
                    ctx.update(ctx_pref)
                    for record in records:
                        env = EvalEnvironment(record, self)
                        env.update(ctx)
                        env['current_date'] = datetime.datetime.today()
                        env['time'] = time
                        env['context'] = context
                        env['active_id'] = record.id
                        domain = eval(field._domain, env)
                        relation_ids = []
                        if record[field_name]:
                            if field._type in ('many2one',):
                                relation_ids.append(record[field_name].id)
                            else:
                                relation_ids.extend(
                                        [x.id for x in record[field_name]])
                        if relation_ids and not relation_obj.search(cursor,
                                user, [
                                    'AND',
                                    [('id', 'in', relation_ids)],
                                    domain,
                                    ], context=context):
                            self.raise_user_error(cursor,
                                    'domain_validation_record',
                                    error_args=get_error_args(field_name),
                                    context=context)
                else:
                    relation_ids = []
                    for record in records:
                        if record[field_name]:
                            if field._type in ('many2one',):
                                relation_ids.append(record[field_name].id)
                            else:
                                relation_ids.extend(
                                        [x.id for x in record[field_name]])
                    if relation_ids:
                        find_ids = relation_obj.search(cursor, user, [
                            'AND',
                            [('id', 'in', relation_ids)],
                            field._domain,
                            ], context=context)
                        if not set(relation_ids) == set(find_ids):
                            self.raise_user_error(cursor,
                                    'domain_validation_record',
                                    error_args=get_error_args(field_name),
                                    context=context)
            # validate states required
            if field.states and 'required' in field.states:
                if isinstance(field.states['required'], basestring):
                    ctx = context.copy()
                    ctx.update(ctx_pref)
                    for record in records:
                        env = EvalEnvironment(record, self)
                        env.update(ctx)
                        env['current_date'] = datetime.datetime.today()
                        env['time'] = time
                        env['context'] = context
                        env['active_id'] = record.id
                        required = eval(field.states['required'], env)
                        if required and not record[field_name]:
                            self.raise_user_error(cursor,
                                    'required_validation_record',
                                    error_args=get_error_args(field_name),
                                    context=context)
                else:
                    if field.states['required']:
                        for record in records:
                            if not record[field_name]:
                                self.raise_user_error(cursor,
                                        'required_validation_record',
                                        error_args=get_error_args(field_name),
                                        context=context)

    def default_get(self, cursor, user, fields_names, context=None):
        '''
        Return a dict with the default values for each fields_names.
        '''
        value = {}
        # get the default values for the inherited fields
        for i in self._inherits.keys():
            value.update(self.pool.get(i).default_get(cursor, user,
                fields_names, context=context))

        # get the default values defined in the object
        for field in fields_names:
            if field in self._defaults:
                value[field] = self._defaults[field](cursor, user, context)
            if field in self._columns:
                if isinstance(self._columns[field], fields.Property):
                    property_obj = self.pool.get('ir.property')
                    value[field] = property_obj.get(cursor, user, field,
                            self._name)
                    if self._columns[field]._type in ('many2one',) \
                            and value[field]:
                        obj = self.pool.get(self._columns[field]._obj)
                        if isinstance(value[field], (int, long)):
                            value[field] = obj.name_get(cursor, user,
                                    value[field], context=context)[0]

        # get the default values set by the user and override the default
        # values defined in the object
        ir_default_obj = self.pool.get('ir.default')
        defaults = ir_default_obj.get_default(cursor, user,
                self._name, False, context=context)
        for field, field_value in defaults.items():
            if field in fields_names:
                fld_def = (field in self._columns) and self._columns[field] \
                        or self._inherit_fields[field][2]
                if fld_def._type in ('many2one',):
                    obj = self.pool.get(fld_def._obj)
                    if not obj.search(cursor, user, [('id', '=', field_value)]):
                        continue
                    if isinstance(field_value, (int, long)):
                        field_value = obj.name_get(cursor, user, field_value,
                                context=context)[0]
                if fld_def._type in ('many2many'):
                    obj = self.pool.get(fld_def._obj)
                    field_value2 = []
                    for i in range(len(field_value)):
                        if not obj.search(cursor, user, [('id', '=',
                            field_value[i])]):
                            continue
                        field_value2.append(field_value[i])
                    field_value = field_value2
                if fld_def._type in ('one2many'):
                    obj = self.pool.get(fld_def._obj)
                    field_value2 = []
                    for i in range(len(field_value or [])):
                        field_value2.append({})
                        for field2 in field_value[i]:
                            if obj._columns[field2]._type \
                                    in ('many2one',):
                                obj2 = self.pool.get(obj._columns[field2]._obj)
                                if not obj2.search(cursor, user,
                                        [('id', '=', field_value[i][field2])]):
                                    continue
                                if isinstance(field_value[i][field2],
                                        (int, long)):
                                    field_value[i][field2] = obj2.name_get(
                                            cursor, user,
                                            field_value[i][field2],
                                            context=context)[0]
                            # TODO add test for many2many and one2many
                            field_value2[i][field2] = field_value[i][field2]
                    field_value = field_value2
                value[field] = field_value
        value = self._default_on_change(cursor, user, value, context=context)
        return value

    def _default_on_change(self, cursor, user, value, context=None):
        res = value.copy()
        val = {}
        for i in self._inherits.keys():
            val.update(self.pool.get(i)._default_on_change(cursor, user,
                value, context=context))
        for field in value.keys():
            if field in self._columns:
                if self._columns[field].on_change:
                    args = {}
                    for arg in self._columns[field].on_change:
                        args[arg] = value.get(arg, False)
                        if arg in self._columns \
                                and self._columns[arg]._type == 'many2one':
                            if isinstance(args[arg], (list, tuple)):
                                args[arg] = args[arg][0]
                    val.update(getattr(self, 'on_change_' + field)(cursor, user,
                        [], args, context=context))
                if self._columns[field]._type in ('one2many',):
                    obj = self.pool.get(self._columns[field]._obj)
                    for val2 in res[field]:
                        val2.update(obj._default_on_change(cursor, user,
                            val2, context=context))
        res.update(val)
        return res

    def delete(self, cursor, user, ids, context=None):
        '''
        Remove the ids.
        '''
        if context is None:
            context = {}
        context = context.copy()
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        if self.table_query(context):
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
                    if context['_timestamp'].get(i):
                        args.append(i)
                        args.append(context['_timestamp'][i])
                if args:
                    cursor.execute("SELECT id " \
                            'FROM "' + self._table + '" ' \
                            'WHERE ' + ' OR '.join(
                                [clause for x in range(len(args)/2)]), args)
                    if cursor.rowcount:
                        raise Exception('ConcurrencyException',
                                'Records were modified in the meanwhile')
            del context['_timestamp']

        self.pool.get('ir.model.access').check(cursor, user, self._name,
                'delete', context=context)

        cursor.execute(
            "SELECT id FROM wkf_instance "\
                "WHERE res_id IN (" + ",".join(["%s" for i in ids]) + ") "\
                "AND res_type = %s AND state != 'complete'",
            ids + [self._name])
        if cursor.rowcount != 0:
            self.raise_user_error(cursor, 'delete_workflow_record',
                    context=context)

        wf_service = LocalService("workflow")
        for obj_id in ids:
            wf_service.trg_delete(user, self._name, obj_id, cursor,
                    context=context)

        if not self.check_xml_record(cursor, user, ids, None, context=context):
            self.raise_user_error(cursor, 'delete_xml_record',
                                  error_description='xml_record_desc',
                                  context=context)

        tree_ids = {}
        for k in self._columns:
            field = self._columns[k]
            if isinstance(field, fields.Many2One) \
                    and field._obj == self._name \
                    and field.left and field.right:
                cursor.execute('SELECT id FROM "' + self._table + '" '\
                        'WHERE "' + k + '" IN (' \
                            + ','.join(['%s' for x in ids]) + ')',
                            ids)
                tree_ids[k] = [x[0] for x in cursor.fetchall()]

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
                    raise Exception('AccessError',
                            'You try to bypass an access rule ' \
                                '(Document type: %s).' % self._description)

            if domain1:
                cursor.execute('DELETE FROM "'+self._table+'" ' \
                        'WHERE id IN (' + str_d + ') ' + domain1,
                        sub_ids + domain2)
            else:
                cursor.execute('DELETE FROM "'+self._table+'" ' \
                        'WHERE id IN (' + str_d + ')', sub_ids)

        for k in tree_ids.keys():
            field = self._columns[k]
            for object_id in tree_ids[k]:
                self._update_tree(cursor, user, object_id, k,
                        field.left, field.right)

        return True

    def check_xml_record(self, cursor, user, ids, values, context=None):
        """
        Check if a list of records and their corresponding fields are
        originating from xml data. This is used by write and delete
        functions: if the return value is True the records can be
        written/deleted, False otherwise. The default behaviour is to
        forbid all modification on records/fields originating from
        xml. Values is the dictionary of written values. If values is
        equal to None, no field by field check is performed, False is
        return has soon has one of the record comes from the xml.
        """
        # Allow root user to update/delete
        if user == 0:
            return True
        cursor.execute('SELECT values ' \
                'FROM ir_model_data ' \
                'WHERE model = %s ' \
                    'AND db_id in (' + ','.join('%s' for x in ids)+ ') ',
                [self._name] + ids)
        if cursor.rowcount == 0:
            return True
        if values == None:
            return False
        for line in cursor.fetchall():
            xml_values = eval(line[0], {
                'Decimal': Decimal,
                'datetime': datetime,
                })
            for key, val in values.iteritems():
                if key in xml_values and val != xml_values[key]:
                    return False
        return True

    def write(self, cursor, user, ids, vals, context=None):
        '''
        Update ids with the content of vals.
        vals is a dict with fields name as keys.
        '''
        if context is None:
            context = {}
        context = context.copy()
        if not ids:
            return True
        if self.table_query(context):
            return True

        vals = vals.copy()

        if isinstance(ids, (int, long)):
            ids = [ids]

        if context.get('_timestamp', False):
            for i in range(0, len(ids), cursor.IN_MAX):
                sub_ids = ids[i:i + cursor.IN_MAX]
                clause = '(id = %s AND ' \
                        '(CASE WHEN write_date IS NOT NULL ' \
                        'THEN write_date ELSE create_date END) ' \
                        ' > %s)'
                args = []
                for i in sub_ids:
                    if context['_timestamp'].get(i):
                        args.append(i)
                        args.append(context['_timestamp'][i])
                if args:
                    cursor.execute("SELECT id " \
                            'FROM "' + self._table + '" ' \
                            'WHERE ' + ' OR '.join(
                                [clause for x in range(len(args)/2)]), args)
                    if cursor.rowcount:
                        raise Exception('ConcurrencyException',
                                'Records were modified in the meanwhile')
            del context['_timestamp']

        self.pool.get('ir.model.access').check(cursor, user, self._name,
                'write', context=context)

        if 'write_uid' in vals:
            del vals['write_uid']
        if 'write_date' in vals:
            del vals['write_date']
        if 'id' in vals:
            del vals['id']

        #for v in self._inherits.values():
        #    assert v not in vals, (v, vals)
        upd0 = []
        upd1 = []
        upd_todo = []
        updend = []
        direct = []
        for field in vals:
            if field in self._columns:
                if self._columns[field]._classic_write:
                    if (not self._columns[field].translate) \
                            or context.get('language', 'en_US') == 'en_US':
                        upd0.append('"' + field + '"=' + \
                                self._columns[field]._symbol_set[0])
                        upd1.append(self._columns[field]._symbol_set[1](
                            vals[field]))
                    direct.append(field)
                else:
                    upd_todo.append(field)
            else:
                updend.append(field)
            if field in self._columns \
                    and hasattr(self._columns[field], 'selection') \
                    and vals[field]:
                if self._columns[field]._type == 'reference':
                    val = vals[field].split(',')[0]
                else:
                    val = vals[field]
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

        if not self.check_xml_record(cursor, user, ids, vals, context=context):
            self.raise_user_error(cursor, 'write_xml_record',
                                  error_description='xml_record_desc',
                                  context=context)

        upd0.append('write_uid = %s')
        upd0.append('write_date = now()')
        upd1.append(user)

        if len(upd0):
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
                    if not cursor.rowcount == len({}.fromkeys(sub_ids)):
                        raise Exception('AccessError',
                                'You try to bypass an access rule ' \
                                        '(Document type: %s).' % \
                                        self._description)
                else:
                    cursor.execute('SELECT id FROM "' + self._table + '" ' \
                            'WHERE id IN (' + ids_str + ')', sub_ids)
                    if not cursor.rowcount == len({}.fromkeys(sub_ids)):
                        raise Exception('AccessError',
                                'You try to bypass an access rule ' \
                                        '(Document type: %s).' % \
                                        self._description)
                if domain1:
                    cursor.execute('UPDATE "' + self._table + '" ' \
                            'SET ' + ','.join(upd0) + ' ' \
                            'WHERE id IN (' + ids_str + ') ' + domain1,
                            upd1 + sub_ids + domain2)
                else:
                    cursor.execute('UPDATE "' + self._table + '" ' \
                            'SET ' + ','.join(upd0) + ' ' \
                            'WHERE id IN (' + ids_str + ') ', upd1 + sub_ids)

            for field in direct:
                if self._columns[field].translate:
                    self.pool.get('ir.translation')._set_ids(cursor, user,
                            self._name + ',' + field, 'model',
                            context.get('language','en_US'), ids, vals[field])

        # call the 'set' method of fields which are not classic_write
        upd_todo.sort(lambda x, y: self._columns[x].priority - \
                self._columns[y].priority)
        for field in upd_todo:
            for select_id in ids:
                self._columns[field].set(cursor, self, select_id, field,
                        vals[field], user, context=context)

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

            vals2 = {}
            for val in updend:
                if self._inherit_fields[val][0] == table:
                    vals2[val] = vals[val]
            self.pool.get(table).write(cursor, user, nids, vals2,
                    context=context)

        self._validate(cursor, user, ids, context=context)

        # Check for Modified Preorder Tree Traversal
        for k in self._columns:
            field = self._columns[k]
            if isinstance(field, fields.Many2One) \
                    and field._obj == self._name \
                    and field.left and field.right:
                if field.left in vals or field.right in vals:
                    raise Exception('ValidateError', 'You can not update fields: ' \
                            '"%s", "%s"' % (field.left, field.right))
                if k in vals:
                    for object_id in ids:
                        self._update_tree(cursor, user, object_id, k,
                                field.left, field.right)

        # Restart rule cache
        if self.pool.get('ir.rule.group').search(cursor, 0, [
            ('model.model', '=', self._name),
            ], context=context):
            self.pool.get('ir.rule').domain_get(cursor.dbname)

        wf_service = LocalService("workflow")
        for obj_id in ids:
            wf_service.trg_write(user, self._name, obj_id, cursor,
                    context=context)
        return True

    def __clean_defaults(self, defaults):
        vals = {}
        for field in defaults.keys():
            fld_def = (field in self._columns) and self._columns[field] \
                    or self._inherit_fields[field][2]
            if fld_def._type in ('many2one',):
                if isinstance(defaults[field], (list, tuple)):
                    vals[field] = defaults[field][0]
                else:
                    vals[field] = defaults[field]
            elif fld_def._type in ('one2many',):
                obj = self.pool.get(self._columns[field]._obj)
                vals[field] = []
                for defaults2 in defaults[field]:
                    vals2 = obj.__clean_defaults(defaults2)
                    vals[field].append(('create', vals2))
            elif fld_def._type in ('many2many',):
                vals[field] = [('set', defaults[field])]
            elif fld_def._type in ('boolean',):
                vals[field] = bool(defaults[field])
            else:
                vals[field] = defaults[field]
        return vals

    def create(self, cursor, user, vals, context=None):
        """
        Create a record with the content of vals.
        vals is a dict with fields name as key.
        """
        if self.table_query(context):
            return False

        vals = vals.copy()

        self.pool.get('ir.model.access').check(cursor, user, self._name,
                'create', context=context)

        if 'create_uid' in vals:
            del vals['create_uid']
        if 'create_date' in vals:
            del vals['create_date']
        if 'id' in vals:
            del vals['id']

        default = []
        avoid_table = []
        for (i, j) in self._inherits.items():
            if j in vals:
                avoid_table.append(i)
        for i in self._columns.keys(): # + self._inherit_fields.keys():
            if not i in vals \
                    and i not in ('create_uid', 'create_date',
                            'write_uid', 'write_date'):
                default.append(i)
        for i in self._inherit_fields.keys():
            if (not i in vals) \
                    and (not self._inherit_fields[i][0] in avoid_table):
                default.append(i)

        if len(default):
            defaults = self.default_get(cursor, user, default, context)
            vals.update(self.__clean_defaults(defaults))

        tocreate = {}
        for i in self._inherits:
            if self._inherits[i] not in vals:
                tocreate[i] = {}

        (upd0, upd1, upd2) = ('', '', [])
        upd_todo = []

        for i in vals.keys():
            if i in self._inherit_fields:
                (table, col, col_detail) = self._inherit_fields[i]
                tocreate[table][i] = vals[i]
                del vals[i]

        cursor.execute("SELECT NEXTVAL('" + self._sequence + "')")
        (id_new,) = cursor.fetchone()
        for table in tocreate:
            new_id = self.pool.get(table).create(cursor, user, tocreate[table],
                    context=context)
            upd0 += ',' + self._inherits[table]
            upd1 += ',%s'
            upd2.append(new_id)

        for field in vals:
            if self._columns[field]._classic_write:
                upd0 = upd0 + ',"' + field + '"'
                upd1 = upd1 + ',' + self._columns[field]._symbol_set[0]
                upd2.append(self._columns[field]._symbol_set[1](vals[field]))
            else:
                upd_todo.append(field)
            if field in self._columns \
                    and hasattr(self._columns[field], 'selection') \
                    and vals[field]:
                if self._columns[field]._type == 'reference':
                    val = vals[field].split(',')[0]
                else:
                    val = vals[field]
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
        cursor.execute('INSERT INTO "' + self._table + '" ' \
                '(id' + upd0 + ') ' \
                'VALUES (' + str(id_new) + upd1 + ')', tuple(upd2))
        upd_todo.sort(lambda x, y: self._columns[x].priority - \
                self._columns[y].priority)
        for field in upd_todo:
            self._columns[field].set(cursor, self, id_new, field, vals[field],
                    user=user, context=context)

        self._validate(cursor, user, [id_new], context=context)

        # Check for Modified Preorder Tree Traversal
        for k in self._columns:
            field = self._columns[k]
            if isinstance(field, fields.Many2One) \
                    and field._obj == self._name \
                    and field.left and field.right:
                self._update_tree(cursor, user, id_new, k, field.left, field.right)

        wf_service = LocalService("workflow")
        wf_service.trg_create(user, self._name, id_new, cursor, context=context)
        return id_new

    def fields_get(self, cursor, user, fields_names=None, context=None):
        """
        Returns the definition of each field in the object
        the optional fields_names parameter can limit the result to some fields
        """
        if context is None:
            context = {}
        res = {}
        translation_obj = self.pool.get('ir.translation')
        model_access_obj = self.pool.get('ir.model.access')
        for parent in self._inherits:
            res.update(self.pool.get(parent).fields_get(cursor, user,
                fields_names, context))
        write_access = model_access_obj.check(cursor, user, self._name, 'write',
                raise_exception=False, context=context)
        if self.table_query(context):
            write_access = False

        if context.get('language'):
            #Add translation to cache
            trans_args = []
            for field in self._columns.keys():
                trans_args.append((self._name + ',' + field, 'field',
                    context['language'], None))
                trans_args.append((self._name + ',' + field, 'help',
                    context['language'], None))
                if hasattr(self._columns[field], 'selection'):
                    if isinstance(self._columns[field].selection, (tuple, list)):
                        sel = self._columns[field].selection
                        for (key, val) in sel:
                            trans_args.append((self._name + ',' + field,
                                'selection', context['language'], val))
            translation_obj._get_sources(cursor, trans_args)

        for field in self._columns.keys():
            res[field] = {'type': self._columns[field]._type}
            for arg in (
                    'string',
                    'readonly',
                    'states',
                    'size',
                    'required',
                    'change_default',
                    'translate',
                    'help',
                    'select',
                    'on_change',
                    'add_remove',
                    'on_change_with',
                    'sort',
                    ):
                if getattr(self._columns[field], arg, None) != None:
                    res[field][arg] = getattr(self._columns[field], arg)
            if not write_access:
                res[field]['readonly'] = True
                if res[field].get('states') and \
                        'readonly' in res[field]['states']:
                    res[field]['states'] = res[field]['states'].copy()
                    del res[field]['states']['readonly']
            for arg in ('digits', 'invisible'):
                if hasattr(self._columns[field], arg) \
                        and getattr(self._columns[field], arg):
                    res[field][arg] = getattr(self._columns[field], arg)
            if isinstance(self._columns[field], fields.Function) \
                    and not self._columns[field].order_field:
                res[field]['sortable'] = False

            if context.get('language'):
                # translate the field label
                res_trans = translation_obj._get_source(cursor,
                        self._name + ',' + field, 'field',
                        context['language'])
                if res_trans:
                    res[field]['string'] = res_trans
                help_trans = translation_obj._get_source(cursor,
                        self._name + ',' + field, 'help',
                        context['language'])
                if help_trans:
                    res[field]['help'] = help_trans

            if hasattr(self._columns[field], 'selection'):
                if isinstance(self._columns[field].selection, (tuple, list)):
                    sel = self._columns[field].selection
                    if context.get('language'):
                        # translate each selection option
                        sel2 = []
                        for (key, val) in sel:
                            val2 = translation_obj._get_source(cursor,
                                    self._name + ',' + field, 'selection',
                                    context.get('language', 'en_US'), val)
                            sel2.append((key, val2 or val))
                        sel = sel2
                    res[field]['selection'] = sel
                else:
                    # call the 'dynamic selection' function
                    res[field]['selection'] = self._columns[field].selection
            if res[field]['type'] in (
                    'one2many',
                    'many2many',
                    'many2one',
                    ):
                res[field]['relation'] = self._columns[field]._obj
                res[field]['domain'] = self._columns[field]._domain
                res[field]['context'] = self._columns[field]._context
            if res[field]['type'] == 'one2many':
                res[field]['relation_field'] = self._columns[field]._field

        if fields_names:
            # filter out fields which aren't in the fields_names list
            for i in res.keys():
                if i not in fields_names:
                    del res[i]
        return res

    def view_header_get(self, cursor, user, value, view_type='form',
            context=None):
        """
        Overload this method if you need a window title
        which depends on the context
        """
        return False

    def __view_look_dom(self, cursor, user, element, type, fields_width=None,
            context=None):
        translation_obj = self.pool.get('ir.translation')

        if fields_width is None:
            fields_width = {}
        if context is None:
            context = {}
        result = False
        fields_attrs = {}
        childs = True

        if element.tag in ('field', 'label', 'separator', 'group'):
            for attr in ('name', 'icon'):
                if element.get(attr):
                    attrs = {}
                    try:
                        if element.get(attr) in self._columns:
                            relation = self._columns[element.get(attr)]._obj
                        else:
                            relation = self._inherit_fields[element.get(attr)][2]._obj
                    except:
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
                                                cursor, self._name, 'view',
                                                context['language'],
                                                field.get('string'))
                                        if trans:
                                            field.set('string', trans)
                                    if field.get('sum'):
                                        trans = translation_obj._get_source(
                                                cursor, self._name, 'view',
                                                context['language'],
                                                field.get('sum'))
                                        if trans:
                                            field.set('sum', trans)
                                    for field_child in field:
                                        _translate_field(field_child)
                                if 'language' in context:
                                    _translate_field(field2)

                                xarch, xfields = self.pool.get(relation
                                        )._view_look_dom_arch(cursor, user,
                                                field2, field.tag,
                                                context=context)
                                views[field.tag] = {
                                    'arch': xarch,
                                    'fields': xfields
                                }
                                element.remove(field)
                        attrs = {'views': views}
                    fields_attrs[element.get(attr)] = attrs
            if element.get('name') in fields_width:
                element.set('width', str(fields_width[element.get('name')]))

        # translate view
        if ('language' in context) and not result:
            if element.get('string'):
                trans = translation_obj._get_source(cursor,
                        self._name, 'view', context['language'],
                        element.get('string'))
                if trans:
                    element.set('string', trans)
            if element.get('sum'):
                trans = translation_obj._get_source(cursor,
                        self._name, 'view', context['language'],
                        element.get('sum'))
                if trans:
                    element.set('sum', trans)

        if element.tag in ('form', 'tree', 'graph'):
            value = ''
            if element.get('string'):
                value = element.get('string')
            result = self.view_header_get(cursor, user, value, element.tag,
                    context)
            if result:
                element.set('string', result)

        if childs:
            for field in element:
                fields_attrs.update(self.__view_look_dom(cursor, user, field,
                    type, fields_width=fields_width, context=context))
        return fields_attrs

    def _view_look_dom_arch(self, cursor, user, tree, type, context=None):
        fields_width = {}
        tree_root = tree.getroottree().getroot()

        if type == 'tree':
            viewtreewidth_obj = self.pool.get('ir.ui.view_tree_width')
            viewtreewidth_ids = viewtreewidth_obj.search(cursor, user, [
                ('model', '=', self._name),
                ('user', '=', user),
                ], context=context)
            for viewtreewidth in viewtreewidth_obj.browse(cursor, user,
                    viewtreewidth_ids, context=context):
                if viewtreewidth.width > 0:
                    fields_width[viewtreewidth.field] = viewtreewidth.width

        fields_def = self.__view_look_dom(cursor, user, tree_root, type,
                fields_width=fields_width, context=context)
        arch = etree.tostring(tree, encoding='utf-8', pretty_print=False)
        fields2 = self.fields_get(cursor, user, fields_def.keys(), context)
        for field in fields_def:
            if field in fields2:
                fields2[field].update(fields_def[field])
        return arch, fields2

    def fields_view_get(self, cursor, user, view_id=None, view_type='form',
            context=None, toolbar=False, hexmd5=None):
        '''
        Return a dict with keys:
            - arch: the xml description of the view.
            - fields: a dict with the definition of each fields.
            - toolbar: if toolbar is True, a dict with 'print', 'action', 'relate'
                keyword action defintion for the view.
            - md5: the check sum of the above dict that will be used for caching.
        view_id can specify the id of the view, if empty the system
            will select the first view
        view_type specify the type of the view if view_id is empty
        If hexmd5 is fill, the function will return True if the view have the same
            md5 or the dict.
        '''

        def _inherit_apply(src, inherit):

            def _find(tree, element):
                if element.tag == 'xpath':
                    res = tree.xpath(element.get('expr'))
                    if res:
                        return res[0]
                return None

            tree_src = etree.fromstring(src)
            tree_inherit = etree.fromstring(inherit)
            root_inherit = tree_inherit.getroottree().getroot()
            for element2 in root_inherit:
                element = _find(tree_src, element2)
                if element is not None:
                    pos = element2.get('position', 'inside')
                    if pos == 'replace':
                        parent = element.getparent()
                        next = element.getnext()
                        if next is not None:
                            for child in element2:
                                index = parent.index(next)
                                parent.insert(index, child)
                        else:
                            parent.extend(element2.getchildren())
                        parent.remove(element)
                    elif pos == 'inside':
                        element.extend(element2.getchildren())
                    elif pos == 'after':
                        parent = element.getparent()
                        next = element.getnext()
                        if next is not None:
                            for child in element2:
                                index = parent.index(next)
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
                    raise AttributeError('Couldn\'t find tag (%s: %s) in parent view!' % (element2.tag, element2.get('expr')))
            return etree.tostring(tree_src, encoding='utf-8')

        result = {'type': view_type, 'model': self._name}

        test = True
        model = True
        sql_res = False
        while test:
            if view_id:
                where = (model and (" and model='%s'" % (self._name,))) or ''
                cursor.execute('SELECT arch, field_childs, id, type, ' \
                            'inherit ' \
                        'FROM ir_ui_view WHERE id = %s ' + where, (view_id,))
            else:
                cursor.execute('SELECT arch, field_childs, id, type, ' \
                        'inherit ' \
                        'FROM ir_ui_view ' \
                        'WHERE model = %s AND type = %s AND inherit IS NULL ' \
                        'ORDER BY priority',
                        (self._name,view_type))
            sql_res = cursor.fetchone()
            if not sql_res:
                break
            test = sql_res[4]
            view_id = test or sql_res[2]
            model = False

        # if a view was found
        if sql_res:
            result['type'] = sql_res[3]
            result['view_id'] = sql_res[2]
            result['arch'] = sql_res[0]

            def _inherit_apply_rec(result, inherit_id):
                # get all views which inherit from (ie modify) this view
                cursor.execute('SELECT arch, id FROM ir_ui_view ' \
                        'WHERE inherit = %s AND model = %s ' \
                        'ORDER BY priority', (inherit_id, self._name))
                sql_inherit = cursor.fetchall()
                for (inherit, view_id) in sql_inherit:
                    result = _inherit_apply(result, inherit)
                    result = _inherit_apply_rec(result, view_id)
                return result

            result['arch'] = _inherit_apply_rec(result['arch'], sql_res[2])

            result['field_childs'] = sql_res[1] or False
        # otherwise, build some kind of default view
        else:
            if view_type == 'form':
                res = self.fields_get(cursor, user, context=context)
                xml = '''<?xml version="1.0" encoding="utf-8"?>''' \
                '''<form string="%s">''' % (self._description,)
                for i in res:
                    if i in ('create_uid', 'create_date',
                            'write_uid', 'write_date', 'id'):
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
                xml = '''<?xml version="1.0" encoding="utf-8"?>''' \
                '''<tree string="%s"><field name="%s"/></tree>''' \
                % (self._description, field)
            elif view_type == 'calendar':
                xml = '''<?xml version="1.0" encoding="utf-8"?>''' \
                '''<calendar string="%s" date_start="%s">''' \
                '''<field name="%s"/></calendar>''' \
                % (self._description, self._date_name, self._rec_name)
            else:
                xml = ''
            result['type'] = view_type
            result['arch'] = xml
            result['field_childs'] = False
            result['view_id'] = 0

        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.fromstring(result['arch'], parser)
        xarch, xfields = self._view_look_dom_arch(cursor, user, tree,
                result['type'], context=context)
        result['arch'] = xarch
        result['fields'] = xfields
        if toolbar:
            action_obj = self.pool.get('ir.action.keyword')
            prints = action_obj.get_keyword(cursor, user, 'form_print',
                    (self._name, 0), context=context)
            actions = action_obj.get_keyword(cursor, user, 'form_action',
                    (self._name, 0), context=context)
            relates = action_obj.get_keyword(cursor, user, 'form_relate',
                    (self._name, 0), context=context)
            result['toolbar'] = {
                'print': prints,
                'action': actions,
                'relate': relates,
            }
        result['md5'] = md5.new(str(result)).hexdigest()
        if hexmd5 == result['md5']:
            return True
        return result

    fields_view_get = Cache('orm.fields_view_get')(fields_view_get)

    def _where_calc(self, cursor, user, args, active_test=True, context=None):
        if context is None:
            context = {}
        args = args[:]
        # if the object has a field named 'active', filter out all inactive
        # records unless they were explicitely asked for
        if ('active' in self._columns or \
                'active' in self._inherit_fields.keys()) \
                and (active_test and context.get('active_test', True)):
            def process_args(args):
                i = 0
                active_found = False
                while i < len(args):
                    if isinstance(args[i], list):
                        args[i] = process_args(args[i])
                    if isinstance(args[i], tuple):
                        if args[i][0] == 'active':
                            active_found = True
                    i += 1
                if not active_found:
                    if args and ((isinstance(args[0], basestring) \
                            and args[0] == 'AND') \
                            or (not isinstance(args[0], basestring))):
                        args.append(('active', '=', 1))
                    else:
                        args = ['AND', args, ('active', '=', 1)]
                return args
            args = process_args(args)

        table_query = ''
        table_args = []
        if self.table_query(context):
            table_query, table_args = self.table_query(context)
            table_query = '(' + table_query + ') AS '

        tables = [table_query + '"' + self._table + '"']
        tables_args = table_args

        qu1, qu2 = self.__where_calc_oper(cursor, user, args, tables,
                tables_args, context=context)
        return qu1, qu2, tables, tables_args


    def __where_calc_oper(self, cursor, user, args, tables, tables_args,
            context=None):
        operator = 'AND'
        if len(args) and isinstance(args[0], basestring):
            if args[0] not in ('AND', 'OR'):
                raise Exception('ValidateError', 'Operator "%s" not supported' \
                        % args[0])
            operator = args[0]
            args = args[1:]
        tuple_args = []
        list_args = []
        for arg in args:
            #add test for xmlrpc that doesn't handle tuple
            if isinstance(arg, tuple) \
                    or (isinstance(arg, list) and len(arg) > 2 \
                    and arg[1] in OPERATORS):
                tuple_args.append(tuple(arg))
            elif isinstance(arg, list):
                list_args.append(arg)

        qu1, qu2 = self.__where_calc(cursor, user,
                tuple_args, tables, tables_args, context=context)
        if len(qu1):
            qu1 = (' ' + operator + ' ').join(qu1)
        else:
            qu1 = ''

        for args2 in list_args:
            qu1b, qu2b = self.__where_calc_oper(cursor,
                    user, args2, tables, tables_args, context=context)
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

    def __where_calc(self, cursor, user, args, tables, tables_args,
            context=None):
        if context is None:
            context = {}
        i = 0
        joins = []
        while i < len(args):
            if args[i][1] not in OPERATORS:
                raise Exception('ValidateError', 'Argument "%s" not supported' \
                        % args[i][1])

            table = self
            fargs = args[i][0].split('.', 1)
            if fargs[0] in self._inherit_fields:
                itable = self.pool.get(self._inherit_fields[fargs[0]][0])
                table_query = ''
                table_arg = []
                if itable.table_query(context):
                    table_query, table_args = self.table_query(context)
                    table_query = '(' + table_query + ') AS '
                table_join = 'LEFT JOIN ' + table_query + \
                        '"' + itable._table + '" ON ' \
                        '%s.id = %s.%s' % (itable._table, self._table,
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
                    args[i] = (fargs[0], 'inselect',
                            self.pool.get(field._obj).search(cursor, user,
                                [(fargs[1], args[i][1], args[i][2])],
                                context=context, query_string=True), table)
                    i += 1
                    continue
                else:
                    raise Exception('ValidateError', 'Clause on field "%s" ' \
                            'doesn\'t work on "%s"' % (args[i][0], self._name))
            if field._properties:
                arg = [args.pop(i)]
                j = i
                while j < len(args):
                    if args[j][0] == arg[0][0]:
                        arg.append(args.pop(j))
                    else:
                        j += 1
                if field._fnct_search:
                    args.extend(field.search(cursor, user, table,
                        arg[0][0], arg, context=context))
            elif field._type == 'one2many':
                field_obj = self.pool.get(field._obj)

                if isinstance(args[i][2], basestring):
                    # get the ids of the records of the "distant" resource
                    ids2 = [x[0] for x in field_obj.name_search(cursor, user,
                        args[i][2], [], args[i][1], context=context)]
                else:
                    ids2 = args[i][2]

                table_query = ''
                table_args = []
                if field_obj.table_query(context):
                    table_query, table_args = field_obj.table_query(context)
                    table_query = '(' + table_query + ') AS '

                if ids2 == True or ids2 == False:
                    query1 = 'SELECT "' + field._field + '" ' \
                            'FROM ' + table_query + '"' + field_obj._table + '" ' \
                            'WHERE "' + field._field + '" IS NOT NULL'
                    query2 = table_args
                    clause = 'inselect'
                    if ids2 == False:
                        clause = 'notinselect'
                    args[i] = ('id', clause, (query1, query2))
                elif not ids2:
                    args[i] = ('id', '=', '0')
                else:
                    if len(ids2) < cursor.IN_MAX:
                        query1 = 'SELECT "' + field._field + '" ' \
                                'FROM ' + table_query + '"' + field_obj._table + '" ' \
                                'WHERE id IN (' + \
                                    ','.join(['%s' for x in ids2]) + ')'
                        query2 = table_args + ids2
                        args[i] = ('id', 'inselect', (query1, query2))
                    else:
                        ids3 = []
                        for i in range(0, len(ids2), cursor.IN_MAX):
                            sub_ids2 = ids2[i:i + cursor.IN_MAX]
                            cursor.execute(
                                'SELECT "' + field._field + \
                                '" FROM ' + table_query + '"' + field_obj._table + '" ' \
                                'WHERE id IN (' + \
                                    ','.join(['%s' for x in sub_ids2]) + ')',
                                table_args + sub_ids2)

                            ids3.extend([x[0] for x in cursor.fetchall()])

                        args[i] = ('id', 'in', ids3)
                i += 1
            elif field._type == 'many2many':
                # XXX must find a solution for long id list
                if args[i][1] in ('child_of', 'not child_of'):
                    if isinstance(args[i][2], basestring):
                        ids2 = [x[0] for x in self.pool.get(
                        field._obj).name_search(cursor, user, args[i][2], [],
                            'like', context=context)]
                    elif isinstance(args[i][2], (int, long)):
                        ids2 = [args[i][2]]
                    else:
                        ids2 = args[i][2]

                    def _rec_get(ids, table, parent):
                        if not ids:
                            return []
                        ids2 = table.search(cursor, user,
                                [(parent, 'in', ids), (parent, '!=', False)],
                                context=context)
                        return ids + _rec_get(ids2, table, parent)

                    if field._obj != table._name:
                        if len(args[i]) != 4:
                            raise Exception('Error', 'Programming error: ' \
                                    'child_of on field "%s" is not allowed!' % \
                                    (args[i][0],))
                        ids2 = self.pool.get(field._obj).search(cursor, user,
                                [(args[i][3], 'child_of', ids2)],
                                context=context)
                        query1 = 'SELECT "' + field.origin + '" ' \
                                'FROM "' + field._rel + '" ' \
                                'WHERE "' + field.target + '" IN (' + \
                                    ','.join(['%s' for x in ids2]) + ') ' \
                                    'AND "' + field.origin + '" IS NOT NULL'
                        query2 = [str(x) for x in ids2]
                        if args[i][1] == 'child_of':
                            args[i] = ('id', 'inselect', (query1, query2))
                        else:
                            args[i] = ('id', 'notinselect', (query1, query2))
                    else:
                        if args[i][1] == 'child_of':
                            args[i] = ('id', 'in', ids2 + _rec_get(ids2,
                                table, args[i][0]))
                        else:
                            args[i] = ('id', 'not in', ids2 + _rec_get(ids2,
                                table, args[i][0]))
                else:
                    if isinstance(args[i][2], basestring):
                        res_ids = [x[0] for x in self.pool.get(field._obj
                            ).name_search(cursor, user, args[i][2], [],
                                args[i][1], context=context)]
                    else:
                        res_ids = args[i][2]
                    if res_ids == True or res_ids == False:
                        query1 = 'SELECT "' + field.origin + '" ' \
                                'FROM "' + field._rel + '" '\
                                'WHERE "' + field.origin + '" IS NOT NULL'
                        query2 = []
                        clause = 'inselect'
                        if res_ids == False:
                            clause = 'notinselect'
                        args[i] = ('id', clause, (query1, query2))
                    elif not res_ids:
                        args[i] = ('id', '=', '0')
                    else:
                        query1 = 'SELECT "' + field.origin + '" ' \
                                'FROM "' + field._rel + '" ' \
                                'WHERE "' + field.target + '" IN (' + \
                                    ','.join(['%s' for x in res_ids]) + ')'
                        query2 = [str(x) for x in res_ids]
                        args[i] = ('id', 'inselect', (query1, query2))
                i += 1

            elif field._type == 'many2one':
                # XXX must find a solution for long id list
                if args[i][1] in ('child_of', 'not child_of'):
                    if isinstance(args[i][2], basestring):
                        ids2 = [x[0] for x in self.pool.get(
                            field._obj).name_search(cursor, user, args[i][2],
                                [], 'like', context=context)]
                    elif isinstance(args[i][2], (int, long)):
                        ids2 = [args[i][2]]
                    else:
                        ids2 = args[i][2]

                    def _rec_get(ids, table, parent):
                        if not ids:
                            return []
                        ids2 = table.search(cursor, user,
                                [(parent, 'in', ids), (parent, '!=', False)],
                                context=context)
                        return ids + _rec_get(ids2, table, parent)

                    if field._obj != table._name:
                        if len(args[i]) != 4:
                            raise Exception('Error', 'Programming error: ' \
                                    'child_of on field "%s" is not allowed!' % \
                                    (args[i][0],))
                        ids2 = self.pool.get(field._obj).search(cursor, user,
                                [(args[i][3], 'child_of', ids2)],
                                context=context)
                        if args[i][1] == 'child_of':
                            args[i] = (args[i][0], 'in', ids2, table)
                        else:
                            args[i] = (args[i][0], 'not in', ids2, table)
                    else:
                        if field.left and field.right:
                            cursor.execute('SELECT "' + field.left + '", ' \
                                        '"' + field.right + '" ' + \
                                    'FROM "' + self._table + '" ' + \
                                    'WHERE id IN ' + \
                                        '(' + ','.join(['%s' for x in ids2]) + ')',
                                        ids2)
                            clause = ''
                            for left, right in cursor.fetchall():
                                if clause:
                                    clause += 'OR '
                                clause += '( "' + field.left + '" >= ' + \
                                        str(left) + ' ' + \
                                        'AND "' + field.right + '" <= ' + \
                                        str(right) + ')'

                            query = 'SELECT id FROM "' + self._table + '" ' + \
                                    'WHERE ' + clause
                            if args[i][1] == 'child_of':
                                args[i] = ('id', 'inselect', (query, []))
                            else:
                                args[i] = ('id', 'notinselect', (query, []))
                        else:
                            if args[i][1] == 'child_of':
                                args[i] = ('id', 'in', ids2 + _rec_get(
                                    ids2, table, args[i][0]), table)
                            else:
                                args[i] = ('id', 'not in', ids2 + _rec_get(
                                    ids2, table, args[i][0]), table)
                else:
                    if isinstance(args[i][2], basestring):
                        res_ids = self.pool.get(field._obj).name_search(cursor,
                                user, args[i][2], [], args[i][1],
                                context=context)
                        args[i] = (args[i][0], 'in', [x[0] for x in res_ids],
                                table)
                    else:
                        args[i] += (table,)
                i += 1
            else:
                if field.translate:
                    exprs = ['%s', '%s']
                    if args[i][1] in ('like', 'ilike', 'not like', 'not ilike'):
                        exprs = ['%% %s%%', '%s%%']
                    oper = 'OR'
                    if args[i][1] in ('not like', 'not ilike', '!='):
                        oper = 'AND'
                    query1 = '(SELECT res_id FROM ir_translation ' \
                            'WHERE name = %s AND lang = %s ' \
                                'AND type = %s ' \
                                'AND (value ' + args[i][1] + ' %s ' \
                                    + oper +' value ' + args[i][1] + ' %s))'
                    query2 = [table._name + ',' + args[i][0],
                            context.get('language', False) or 'en_US',
                            'model', exprs[0] % args[i][2],
                            exprs[1] % args[i][2]]
                    query1 += ' UNION '
                    table_query = ''
                    table_args = []
                    if table.table_query(context):
                        table_query, table_args = table.table_query(context)
                        table_query = '(' + table_query  + ') AS '
                    query1 += '(SELECT id FROM ' + table_query + \
                            '"' + table._table + '" ' \
                            'WHERE ("' + args[i][0] + '" ' + \
                            args[i][1] + ' %s ' + oper + ' "' + args[i][0] + '" ' + \
                            args[i][1] + ' %s))'
                    query2 += table_args + [exprs[0] % args[i][2],
                            exprs[1] % args[i][2]]
                    args[i] = ('id', 'inselect', (query1, query2), table)
                else:
                    args[i] += (table,)
                i += 1
        args.extend(joins)

        qu1, qu2 = [], []
        for arg in args:
            table = self
            if len(arg) > 3:
                table = arg[3]
            if arg[1] in ('inselect', 'notinselect'):
                clause = 'IN'
                if arg[1] == 'notinselect':
                    clause = 'NOT IN'
                qu1.append('(%s.%s %s (%s))' % (table._table, arg[0], clause,
                    arg[2][0]))
                qu2 += arg[2][1]
            elif arg[1] in ('in', 'not in'):
                if len(arg[2]) > 0:
                    todel = []
                    for xitem in range(len(arg[2])):
                        if arg[2][xitem] == False \
                                and isinstance(arg[2][xitem],bool):
                            todel.append(xitem)
                    for xitem in todel[::-1]:
                        del arg[2][xitem]
                    #TODO fix max_stack_depth
                    if len(arg[2]):
                        if arg[0] == 'id':
                            qu1.append(('(%s.id ' + arg[1] + ' (%s))') % \
                                    (table._table,
                                        ','.join(['%s'] * len(arg[2])),))
                        else:
                            qu1.append(('(%s.%s ' + arg[1] + ' (%s))') % \
                                    (table._table, arg[0], ','.join(
                                        [table._columns[arg[0]].\
                                                _symbol_set[0]] * len(arg[2]))))
                        if todel:
                            if arg[1] == 'in':
                                qu1[-1] = '(' + qu1[-1] + ' OR ' \
                                        '%s.%s IS NULL)' % \
                                        (table._table, arg[0])
                            else:
                                qu1[-1] = '(' + qu1[-1] + ' OR ' \
                                        '%s.%s IS NOT NULL)' % \
                                        (table._table, arg[0])
                        qu2 += arg[2]
                    elif todel:
                        qu1.append('(%s.%s IS NULL)' % (table._table, arg[0]))
                else:
                    if arg[1] == 'in':
                        qu1.append(' false')
                    else:
                        qu1.append(' true')
            else:
                if (arg[2] is False) and (arg[1] == '='):
                    if table._columns[arg[0]]._type == 'boolean':
                        qu1.append('(%s.%s = false)' % \
                                (table._table, arg[0]))
                    else:
                        qu1.append('(%s.%s IS NULL)' % \
                                (table._table, arg[0]))
                elif (arg[2] is False) and (arg[1] == '!='):
                    qu1.append('(%s.%s IS NOT NULL)' % \
                            (table._table, arg[0]))
                else:
                    if arg[0] == 'id':
                        qu1.append('(%s.%s %s %%s)' % \
                                (table._table, arg[0], arg[1]))
                        qu2.append(arg[2])
                    else:
                        add_null = False
                        if arg[1] in ('like', 'ilike', 'not like', 'not ilike'):
                            qu2.append('%% %s%%' % arg[2])
                            qu2.append('%s%%' % arg[2])
                            if not arg[2]:
                                add_null = True
                        else:
                            if arg[0] in table._columns:
                                qu2.append(table._columns[arg[0]].\
                                        _symbol_set[1](arg[2]))
                        if arg[0] in table._columns:
                            if arg[1] in ('like', 'ilike'):
                                qu1.append('(%s.%s %s %s OR %s.%s %s %s)' % \
                                        (table._table, arg[0], arg[1], '%s',
                                            table._table, arg[0], arg[1], '%s'))
                            elif arg[1] in ('not like', 'not ilike'):
                                qu1.append('(%s.%s %s %s AND %s.%s %s %s)' % \
                                        (table._table, arg[0], arg[1], '%s',
                                            table._table, arg[0], arg[1], '%s'))
                            else:
                                qu1.append('(%s.%s %s %s)' % (table._table,
                                    arg[0], arg[1],
                                    table._columns[arg[0]]._symbol_set[0]))
                        else:
                            if arg[1] in ('like', 'ilike'):
                                qu1.append('(%s.%s %s \'%s\' or %s.%s %s \'%s\')' % \
                                        (table._table, arg[0], arg[1], arg[2],
                                            table._table, arg[0], arg[1], arg[2]))
                            elif arg[1] in ('not like', 'not ilike'):
                                qu1.append('(%s.%s %s \'%s\' and %s.%s %s \'%s\')' % \
                                        (table._table, arg[0], arg[1], arg[2],
                                            table._table, arg[0], arg[1], arg[2]))
                            else:
                                qu1.append('(%s.%s %s \'%s\')' % \
                                        (table._table, arg[0], arg[1], arg[2]))

                        if add_null:
                            qu1[-1] = '('+qu1[-1]+' OR '+arg[0]+' is null)'

        return qu1, qu2

    def search_count(self, cursor, user, args, context=None):
        '''
        Return the number of record that match the clause defined in args.
        see function search
        '''
        res = self.search(cursor, user, args, context=context, count=True)
        if isinstance(res, list):
            return len(res)
        return res

    def _order_calc(self, cursor, user, field, otype, context=None):
        order_by = []
        tables = []
        field_name = None
        table_name = None
        link_field = None
        clause = ''

        if field in self._columns:
            table_name = self._table

            if self._columns[field]._classic_write:
                field_name = field

            if self._columns[field].order_field:
                field_name = self._columns[field].order_field

            if isinstance(self._columns[field], fields.Many2One):
                obj = self.pool.get(self._columns[field]._obj)
                table_name = obj._table
                link_field = field
                field_name = None

                if obj._rec_name in obj._columns:
                    field_name = obj._rec_name

                if obj._order_name in obj._columns:
                    field_name = obj._order_name

                if field_name:
                    order_by, tables, clause = obj._order_calc(cursor, user,
                            field_name, otype, context=context)
                    table_join = 'LEFT JOIN "' + table_name + '" ON ' \
                            '%s.id = %s.%s' % (table_name, self._table,
                                    link_field)
                    if table_join not in tables:
                        tables.append(table_join)
                    return order_by, tables, clause

                obj2 = None
                if obj._rec_name in obj._inherit_fields.keys():
                    obj2 = self.pool.get(obj._inherit_fields[obj._rec_name][0])
                    field_name = obj._rec_name

                if obj._order_name in obj._inherit_fields.keys():
                    obj2 = self.pool.get(obj._inherit_fields[obj._order_name][0])
                    field_name = obj._order_name

                if obj2 and field_name:
                    table_name2 = obj2._table
                    link_field2 = obj._inherits[obj2._name]
                    order_by, tables, clause = obj2._order_calc(cursor, user,
                            field_name, otype, context=context)

                    table_join = 'LEFT JOIN "' + table_name + '" ON ' \
                            '%s.id = %s.%s' % \
                            (table_name, self._table, link_field)
                    if table_join not in tables:
                        tables.append(table_join)

                    table_join2 = 'LEFT JOIN "' + table_name2 + '" ON ' \
                            '%s.id = %s.%s' % \
                            (table_name2, obj._table, link_field2)
                    if table_join2 not in tables:
                        tables.append(table_join2)
                    return order_by, tables, clause

            if field_name:
                if '%(table)s' in field_name or '%(order)s' in field_name:
                    order_by.append(field_name % {
                        'table': table_name,
                        'order': otype,
                        })
                else:
                    order_by.append(table_name + '.' + field_name + ' ' + otype)
                return order_by, tables, clause

        if field in self._inherit_fields.keys():
            obj = self.pool.get(self._inherit_fields[field][0])
            table_name = obj._table
            link_field = self._inherits[obj._name]
            order_by, tables, clause = obj._order_calc(cursor, user, field,
                    otype, context=context)
            table_join = 'LEFT JOIN "' + table_name + '" ON ' \
                    '%s.id = %s.%s' % \
                    (table_name, self._table, link_field)
            if table_join not in tables:
                tables.append(table_join)
            return order_by, tables, clause

        raise Exception('Error', 'Wrong field name (%s) in order!' \
                % field)

    def search(self, cursor, user, args, offset=0, limit=None, order=None,
            context=None, count=False, query_string=False):
        '''
        Return a list of id that match the clause defined in args.

        :param cursor: the database cursor
        :param user: the user id
        :param args: a list of tuples or lists
            lists are construct like this:
                ['operator', args, args, ...]
                operator can be 'AND' or 'OR', if it is missing the
                default value will be 'AND'
            tuples are construct like this:
                ('field name', 'operator', value)
                field name: is the name of a field of the object
                    or a relational field by using '.' as separator.
                operator must be in OPERATORS
        :param offset: an integer to specify the offset in the result
        :param limit: an integer to limit the number of ids return
        :param order: a list of tupe that are construct like this:
            ('field name', 'DESC|ASC')
            it allow to specify the order of the ids in the return list
        :param count: a boolean to return just the len of the list
        :param query_string: a boolean to return a tuple with
            the SQL query string and the arguments.
        :return: a list of ids
        '''
        (qu1, qu2, tables, tables_args) = self._where_calc(cursor, user, args,
                context=context)

        order_by = []
        for field, otype in (order or self._order):
            if otype.upper() not in ('DESC', 'ASC'):
                raise Exception('Error', 'Wrong order type (%s)!' % otype)
            order_by2, tables2, clause = self._order_calc(cursor, user,
                    field, otype, context=context)
            order_by += order_by2
            for table in tables2:
                if table not in tables:
                    tables.append(table)
            if clause:
                if qu1:
                    qu1 += ' AND ' + clause
                else:
                    qu1 = clause

        order_by = ','.join(order_by)

        limit_str = limit and (type(limit) in (float, int, long))\
                    and ' LIMIT %d' % limit or ''
        offset_str = offset and (type(offset) in (float, int, long))\
                     and ' OFFSET %d' % offset or ''


        # construct a clause for the rules :
        domain1, domain2 = self.pool.get('ir.rule').domain_get(cursor, user,
                self._name, context=context)
        if domain1:
            if qu1:
                qu1 += ' AND ' + domain1
            else:
                qu1 = domain1
            qu2 += domain2

        if count:
            cursor.execute('SELECT COUNT(%s.id) FROM ' % self._table +
                    ' '.join(tables) + ' WHERE ' + (qu1 or 'True') +
                    limit_str + offset_str, tables_args + qu2)
            res = cursor.fetchall()
            return res[0][0]
        # execute the "main" query to fetch the ids we were searching for
        query_str = 'SELECT %s.id FROM ' % self._table + \
                ' '.join(tables) + ' WHERE ' + (qu1 or 'True') + \
                ' ORDER BY ' + order_by + limit_str + offset_str
        if query_string:
            return (query_str, tables_args + qu2)
        cursor.execute(query_str, tables_args + qu2)
        res = cursor.fetchall()
        return [x[0] for x in res]

    def name_get(self, cursor, user, ids, context=None):
        '''
        Return a list of tuple for each ids.
        The tuple contains the id and the name of the record.
        '''
        if not ids:
            return []
        if isinstance(ids, (int, long)):
            ids = [ids]
        return [(r['id'], unicode(r[self._rec_name])) for r in self.read(cursor,
            user, ids, [self._rec_name], context, load='_classic_write')]

    def name_search(self, cursor, user, name='', args=None, operator='ilike',
            context=None, limit=None):
        '''
        Return a list of ids where the name and the args clause matches.
        args is a clause like in the function search.
        operator is the operator used to compare the name.
        limit can be used to limit the number of id.
        '''
        if args is None:
            args = []
        args = args[:]
        if name:
            args = ['AND', args, (self._rec_name, operator, name)]
        ids = self.search(cursor, user, args, limit=limit, context=context)
        res = self.name_get(cursor, user, ids, context=context)
        return res

    def copy(self, cursor, user, object_id, default=None, context=None):
        '''
        Duplicate the object_id record.
        default can be a dict with field name as keys,
        it will replace the value of the record.
        '''
        lang_obj = self.pool.get('ir.lang')
        if default is None:
            default = {}
        if context is None:
            context = {}
        if 'state' not in default:
            if 'state' in self._defaults:
                default['state'] = self._defaults['state'](cursor, user,
                        context)

        def convert_data(fields, data):
            for field_name in fields:
                ftype = fields[field_name]['type']

                if field_name in (
                    'create_date',
                    'create_uid',
                    'write_date',
                    'write_uid',
                    ):
                    del data[field_name]

                if field_name in default:
                    data[field_name] = default[field_name]
                elif ftype == 'function':
                    del data[field_name]
                elif ftype == 'many2one':
                    try:
                        data[field_name] = data[field_name] and \
                                data[field_name][0]
                    except:
                        pass
                elif ftype in ('one2many',):
                    res = []
                    rel = self.pool.get(fields[field_name]['relation'])
                    for rel_id in data[field_name] or []:
                        # the lines are first duplicated using the wrong (old)
                        # parent but then are reassigned to the correct one thanks
                        # to the ('add', ...)
                        res.append(('add', rel.copy(cursor, user, rel_id,
                            context=context)))
                    data[field_name] = res
                elif ftype == 'many2many':
                    if data[field_name]:
                        data[field_name] = [('set', data[field_name])]
            if 'id' in data:
                del data['id']
            for i in self._inherits:
                if self._inherits[i] in data:
                    del data[self._inherits[i]]

        data = self.read(cursor, user, object_id, context=context)
        fields = self.fields_get(cursor, user)
        convert_data(fields, data)
        new_id = self.create(cursor, user, data, context=context)

        fields_translate = {}
        for field_name, field in fields.iteritems():
            if field_name in self._columns and \
                    self._columns[field_name].translate:
                fields_translate[field_name] = field
            elif field_name in self._inherit_fields and \
                    self._inherit_fields[field_name][2].translate:
                fields_translate[field_name] = field

        if fields_translate:
            lang_ids = lang_obj.search(cursor, user, [
                ('translatable', '=', True),
                ], context=context)
            if lang_ids:
                lang_ids += lang_obj.search(cursor, user, [
                    ('code', '=', 'en_US'),
                    ], context=context)
                langs = lang_obj.browse(cursor, user, lang_ids, context=context)
                for lang in langs:
                    ctx = context.copy()
                    ctx['language'] = lang.code
                    data = self.read(cursor, user, object_id,
                            fields_names=fields_translate.keys(), context=ctx)
                    convert_data(fields_translate, data)
                    self.write(cursor, user, new_id, data, context=ctx)
        return new_id

    def search_read(self, cursor, user, args, offset=0, limit=None, order=None,
            context=None, fields_names=None, load='_classic_read'):
        '''
        Call search function and read in once.
        Usefull for the client to reduce the number of calls.
        '''
        ids = self.search(cursor, user, args, offset=offset, limit=limit,
                order=order, context=context)
        if limit == 1:
            ids = ids[0]
        return self.read(cursor, user, ids, fields_names=fields_names,
                context=context, load=load)

    def check_recursion(self, cursor, user, ids, parent='parent'):
        '''
        Function that check if there is no recursion in the tree
        composed with parent as parent field name.
        '''
        ids_parent = ids[:]
        while len(ids_parent):
            ids_parent2 = []
            for i in range(0, len(ids_parent), cursor.IN_MAX):
                sub_ids_parent = ids_parent[i:i + cursor.IN_MAX]
                cursor.execute('SELECT distinct "' + parent + '" ' +
                    'FROM "' + self._table + '" ' +
                    'WHERE id IN ' \
                        '(' + ','.join(['%s' for x in sub_ids_parent]) + ')',
                        sub_ids_parent)
                ids_parent2.extend(filter(None,
                    [x[0] for x in cursor.fetchall()]))
            ids_parent = ids_parent2
            for i in ids_parent:
                if i in ids:
                    return False
        return True

    def default_sequence(self, cursor, user, context=None):
        '''
        Return the default value for sequence field.
        '''
        cursor.execute('SELECT MAX(sequence) ' \
                'FROM "' + self._table + '"')
        res = cursor.fetchone()
        if res:
            return res[0]
        return 0

    def _rebuild_tree(self, cursor, user, parent, parent_id, left):
        '''
        Rebuild left, right value for the tree.
        '''
        right = left + 1

        if not parent_id:
            cursor.execute('SELECT id FROM "' + self._table + '" ' \
                    'WHERE "' + parent + '" IS NULL')
        else:
            cursor.execute('SELECT id FROM "' + self._table + '" ' \
                    'WHERE "' + parent + '" = %s', (parent_id,))
        child_ids = [x[0] for x in cursor.fetchall()]

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
        Remarks: the value (right - left - 1) / 2 will not give
            the number of children node
        '''
        cursor.execute('SELECT "' + left + '", "' + right + '" ' \
                'FROM "' + self._table + '" ' \
                'WHERE id = %s', (object_id,))
        if not cursor.rowcount:
            return
        old_left, old_right = cursor.fetchone()

        cursor.execute('SELECT "' + right + '" ' \
                'FROM "' + self._table + '" ' \
                'WHERE id IN (' \
                    'SELECT "' + field_name + '" FROM "' + self._table + '" ' \
                    'WHERE id = %s)', (object_id,))
        if cursor.rowcount:
            parent_right = cursor.fetchone()[0]

            cursor.execute('SELECT count(1) FROM "' + self._table + '" ' \
                    'WHERE "' + left + '" >= %s AND "' + right + '" <= %s',
                    (old_left, old_right))
            child_number = cursor.fetchone()[0]

            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET "' + left + '" = "' + left + '" + ' \
                        + str(2 * child_number) + ' ' \
                    'WHERE "' + left + '" >= %s ' \
                        'AND NOT ("' + left + '" >= %s AND ' \
                            '"' + right + '" <= %s)',
                        (parent_right, old_left, old_right))
            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET "' + right + '" = "' + right + '" + ' \
                        + str(2 * child_number) + ' ' \
                    'WHERE "' + right + '" >= %s ' \
                        'AND NOT ("' + left + '" >= %s AND ' \
                            '"' + right + '" <= %s)',
                        (parent_right, old_left, old_right))

            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET "' + left + '" = "' + left + '" + ' \
                            + str(parent_right - old_left) + ', ' \
                        '"' + right + '" = "' + right + '" + ' \
                            + str(parent_right - (old_left or -1)) + ' ' \
                    'WHERE "' + left + '" >= %s AND "' + right + '" <= %s',
                    (old_left, old_right))
        else:
            max_right = 0
            cursor.execute('SELECT MAX("' + right + '") ' \
                    'FROM "' + self._table + '" ' \
                    'WHERE "' + field_name + '" IS NULL')
            if cursor.rowcount:
                max_right = cursor.fetchone()[0]

            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET "' + left + '" = "' + left + '" + ' \
                            + str(max_right + 1 - old_left) + ', ' \
                        '"' + right + '" = "' + right + '" + ' \
                            + str(max_right + 1 - (old_left or -1)) + ' ' \
                    'WHERE "' + left + '" >= %s AND "' + right + '" <= %s',
                    (old_left, old_right))
