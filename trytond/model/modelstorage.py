#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model import Model
from trytond.model import fields
from trytond.model.browse import BrowseRecordList, BrowseRecord, \
        BrowseRecordNull
from trytond.model.browse import EvalEnvironment
from trytond.tools import safe_eval
from trytond.pyson import PYSONEncoder, PYSONDecoder, PYSON
from trytond.const import OPERATORS
import datetime
import time
from decimal import Decimal
import logging
from itertools import chain
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
import csv


class ModelStorage(Model):
    """
    Define a model with storage capability in Tryton.
    """

    create_uid = fields.Many2One('res.user', 'Create User', readonly=True)
    create_date = fields.DateTime('Create Date', readonly=True)
    write_uid = fields.Many2One('res.user', 'Write User', readonly=True)
    write_date = fields.DateTime('Write Date', readonly=True)
    rec_name = fields.Function(fields.Char('Name'), 'get_rec_name',
            searcher='search_rec_name')

    def __init__(self):
        super(ModelStorage, self).__init__()
        self._rpc.update({
            'create': True,
            'read': False,
            'write': True,
            'delete': True,
            'copy': True,
            'search': False,
            'search_count': False,
            'search_read': False,
            'export_data': False,
            'import_data': True,
        })
        self._constraints = []

    def default_create_uid(self, cursor, user, context=None):
        "Default value for uid field."
        return int(user)

    def default_create_date(self, cursor, user, context=None):
        "Default value for create_date field."
        return datetime.datetime.today()

    def __clean_xxx2many_cache(self, cursor, user, context=None):
        # Clean cursor cache
        to_clean = [(model._name, field_name)
                for model_name, model in self.pool.iterobject(type='model')
                for field_name, target_name in model._xxx2many_targets
                if target_name == self._name]
        for cache in cursor.cache.values():
            for cache in (cache, cache.get('_language_cache', {}).values()):
                for model_name, field_name in to_clean:
                    if model_name in cache:
                        for model_id in cache[model_name]:
                            if field_name in cache[model_name][model_id]:
                                del cache[model_name][model_id][field_name]

    def create(self, cursor, user, values, context=None):
        '''
        Create records.

        :param cursor: the database cursor
        :param user: the user id
        :param values: a dictionary with fields names as key
                and created values as value
        :param context: the context
        :return: the id of the created record
        '''
        model_access_obj = self.pool.get('ir.model.access')
        model_access_obj.check(cursor, user, self._name, 'create',
                context=context)
        self.__clean_xxx2many_cache(cursor, user, context=context)
        return False

    def read(self, cursor, user, ids, fields_names=None, context=None):
        '''
        Read records.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of ids or an id
        :param fields_names: fields names to read if None read all fields
        :param context: the context
        :return: a list of dictionnary or a dictionnary if ids is an id
            the dictionnaries will have fields names as key
            and fields value as value. The list will not be in the same order.
        '''
        model_access_obj = self.pool.get('ir.model.access')

        model_access_obj.check(cursor, user, self._name, 'read',
                context=context)
        if isinstance(ids, (int, long)):
            return {}
        return []

    def write(self, cursor, user, ids, values, context=None):
        '''
        Write values on records.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of ids or an id
        :param values: a dictionary with fields names as key
                and written values as value
        :param context: the context
        :return: True if succeed
        '''
        model_access_obj = self.pool.get('ir.model.access')

        model_access_obj.check(cursor, user, self._name, 'write',
                context=context)
        if not self.check_xml_record(cursor, user, ids, values,
                context=context):
            self.raise_user_error(cursor, 'write_xml_record',
                                  error_description='xml_record_desc',
                                  context=context)

        # Clean cursor cache
        for cache in cursor.cache.values():
            for cache in (cache, cache.get('_language_cache', {}).values()):
                if self._name in cache:
                    if isinstance(ids, (int, long)):
                        ids = [ids]
                    for i in ids:
                        if i in cache[self._name]:
                            cache[self._name][i] = {}
        if ids:
            self.__clean_xxx2many_cache(cursor, user, context=context)
        return False

    def delete(self, cursor, user, ids, context=None):
        '''
        Delete records.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of ids or an id
        :param context: the context
        :return: True if succeed
        '''
        model_access_obj = self.pool.get('ir.model.access')

        model_access_obj.check(cursor, user, self._name, 'delete',
                context=context)
        if not self.check_xml_record(cursor, user, ids, None, context=context):
            self.raise_user_error(cursor, 'delete_xml_record',
                                  error_description='xml_record_desc',
                                  context=context)

        # Clean cursor cache
        for cache in cursor.cache.values():
            for cache in (cache, cache.get('_language_cache', {}).values()):
                if self._name in cache:
                    if isinstance(ids, (int, long)):
                        ids = [ids]
                    for i in ids:
                        if i in cache[self._name]:
                            del cache[self._name][i]
        if ids:
            self.__clean_xxx2many_cache(cursor, user, context=context)
        return False

    def copy(self, cursor, user, ids, default=None, context=None):
        '''
        Duplicate the record(s) in ids.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of ids or an id
        :param default: a dictionary with field name as keys and
            new value for the field as value
        :param context: the context
        :return: a list of new ids or the new id
        '''
        lang_obj = self.pool.get('ir.lang')
        if default is None:
            default = {}
        if context is None:
            context = {}

        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]

        if 'state' not in default:
            if 'state' in self._defaults:
                default['state'] = self._defaults['state'](cursor, user,
                        context)

        def convert_data(field_defs, data):
            data = data.copy()
            data_o2m = {}
            for field_name in field_defs:
                ftype = field_defs[field_name]['type']

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
                    if data[field_name]:
                        data_o2m[field_name] = data[field_name]
                    data[field_name] = False
                elif ftype == 'many2many':
                    if data[field_name]:
                        data[field_name] = [('set', data[field_name])]
            if 'id' in data:
                del data['id']
            return data, data_o2m

        new_ids = {}
        fields_names = self._columns.keys()
        datas = self.read(cursor, user, ids, fields_names=fields_names,
                context=context)
        field_defs = self.fields_get(cursor, user, fields_names=fields_names,
                context=context)
        for data in datas:
            data_id = data['id']
            data, data_o2m = convert_data(field_defs, data)
            new_ids[data_id] = self.create(cursor, user, data, context=context)
            for field_name in data_o2m:
                relation_model = self.pool.get(
                        field_defs[field_name]['relation'])
                relation_field = field_defs[field_name]['relation_field']
                if relation_field:
                    relation_model.copy(cursor, user, data_o2m[field_name],
                            default={relation_field: new_ids[data_id]},
                            context=context)

        fields_translate = {}
        for field_name, field in field_defs.iteritems():
            if field_name in self._columns and \
                    getattr(self._columns[field_name], 'translate', False):
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
                    datas = self.read(cursor, user, ids,
                            fields_names=fields_translate.keys() + ['id'],
                            context=ctx)
                    for data in datas:
                        data_id = data['id']
                        data, _ = convert_data(fields_translate, data)
                        self.write(cursor, user, new_ids[data_id], data,
                                context=ctx)
        if int_id:
            return new_ids.values()[0]
        return new_ids.values()

    def search(self, cursor, user, domain, offset=0, limit=None, order=None,
            context=None, count=False):
        '''
        Return a list of ids that match the domain.

        :param cursor: the database cursor
        :param user: the user id
        :param domain: a list of tuples or lists
            lists are constructed like this:
            ``['operator', args, args, ...]``
            operator can be 'AND' or 'OR', if it is missing the default
            value will be 'AND'
            tuples are constructed like this:
            ``('field name', 'operator', value)``
            field name: is a field name from the model or a relational field
            by using '.' as separator.
            operator must be in OPERATORS
        :param offset: an integer to specify the offset of the result
        :param limit: an integer to specify the number of result
        :param order: a list of tuples that are constructed like this:
            ``('field name', 'DESC|ASC')``
            allowing to specify the order of result
        :param context: the context
        :param count: a boolean to return only the length of the result
        :return: a list of ids or an integer
        '''
        if count:
            return 0
        return []

    def search_count(self, cursor, user, domain, context=None):
        '''
        Return the number of records that match the domain. (See search)

        :param cursor: the database cursor
        :param user: the user id
        :param domain: a domain like in search
        :param context: the context
        :return: an integer
        '''
        res = self.search(cursor, user, domain, context=context, count=True)
        if isinstance(res, list):
            return len(res)
        return res

    def search_read(self, cursor, user, domain, offset=0, limit=None,
            order=None, context=None, fields_names=None):
        '''
        Call search and read functions at once.
        Useful for the client to reduce the number of calls.

        :param cursor: the database cursor
        :param user: the user id
        :param domain: a domain like in search
        :param offset: an integer to specify the offset for the result
        :param limit: an integer to specify the number of records
        :param order: a list of tuples that are constructed like this:
            ('field name', 'DESC|ASC')
            allowing to to specify the order of result
        :param context: the context
        :param fields_names: fields names to read if None read all fields
        :return: a list of dictionaries or a dictionary if limit is 1
            the dictionaries will have field names as key
            and field values as value
        '''
        ids = self.search(cursor, user, domain, offset=offset, limit=limit,
                order=order, context=context)

        if not fields_names:
            fields_names = list(set(self._columns.keys() \
                    + self._inherit_fields.keys()))
        if 'id' not in fields_names:
            fields_names.append('id')

        res = []
        for model in self.browse(cursor, user, ids, context=context):
            record = {}
            for fields_name in set(fields_names):
                fields_split = fields_name.split('.')
                while fields_split:
                    field_name = fields_split.pop(0)
                    if fields_name not in record:
                        record[fields_name] = model[field_name]
                    else:
                        if isinstance(record[fields_name], BrowseRecordNull):
                            continue
                        record[fields_name] = record[fields_name][field_name]
                if isinstance(record[fields_name], BrowseRecordNull):
                    record[fields_name] = False
                elif isinstance(record[fields_name], BrowseRecord):
                    record[fields_name] = record[fields_name].id
                elif isinstance(record[fields_name], BrowseRecordList):
                    record[fields_name] = [x.id for x in record[fields_name]]
            res.append(record)

        if limit == 1:
            if not ids:
                return []
            return res[0]
        return res

    def _search_domain_active(self, domain, active_test=True, context=None):
        if context is None:
            context = {}

        domain = domain[:]
        # if the object has a field named 'active', filter out all inactive
        # records unless they were explicitely asked for
        if not (('active' in self._columns or \
                'active' in self._inherit_fields.keys()) \
                and (active_test and context.get('active_test', True))):
            return domain

        def process(domain):
            i = 0
            active_found = False
            while i < len(domain):
                arg = domain[i]
                #add test for xmlrpc that doesn't handle tuple
                if isinstance(arg, tuple) or \
                        (isinstance(arg, list) and len(arg) > 2 and \
                        arg[1] in OPERATORS):
                    if arg[0] == 'active':
                        active_found = True
                elif isinstance(arg, list):
                    domain[i] = process(domain[i])
                i += 1
            if not active_found:
                if domain and ((isinstance(domain[0], basestring) \
                        and domain[0] == 'AND') \
                        or (not isinstance(domain[0], basestring))):
                    domain.append(('active', '=', 1))
                else:
                    domain = ['AND', domain, ('active', '=', 1)]
            return domain
        return process(domain)

    def get_rec_name(self, cursor, user, ids, name, context=None):
        '''
        Return a dictionary with id as key and rec_name as value.
        It is used by the Function field rec_name.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of ids
        :param name: the name of the Function field
        :param context: the context
        :return: a dictionary
        '''
        if not ids:
            return {}
        res = {}
        rec_name = self._rec_name
        if rec_name not in self._columns \
                and rec_name not in self._inherit_fields.keys():
            rec_name = 'id'
        for record in self.browse(cursor, user, ids, context=context):
            res[record.id] = unicode(record[rec_name])
        return res

    def search_rec_name(self, cursor, user, name, clause, context=None):
        '''
        Return a list of arguments for search on rec_name.

        :param cursor: the database cursor
        :param user: the user id
        :param name: the name of the Function field
        :param clause: a domain clause
        :param context: the context
        :return: a list of domain clause
        '''
        return [(self._rec_name,) + clause[1:]]

    def browse(self, cursor, user, ids, context=None):
        '''
        Return a BrowseRecordList for the ids
            or BrowseRecord if ids is a integer.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of ids or an id
        :param context: the context
        :return: a BrowseRecordList or a BrowseRecord
        '''
        if isinstance(ids, (int, long)):
            return BrowseRecord(cursor, user, ids, self, context=context)
        local_cache = {}
        return BrowseRecordList((BrowseRecord(cursor, user, x, self,
            local_cache=local_cache, context=context) for x in ids),
            context=context)

    def __export_row(self, cursor, user, record, fields_names, context=None):
        lines = []
        data = ['' for x in range(len(fields_names))]
        done = []
        for fpos in range(len(fields_names)):
            fields_tree = fields_names[fpos]
            if not fields_tree:
                continue
            value = record
            i = 0
            while i < len(fields_tree):
                if not isinstance(value, BrowseRecord):
                    break
                field_name = fields_tree[i]
                model_obj = self.pool.get(value._model_name)
                field = model_obj._columns[field_name]
                if field.states and 'invisible' in field.states:
                    pyson_invisible = PYSONEncoder().encode(
                            field.states['invisible'])
                    env = EvalEnvironment(value, model_obj)
                    env.update(context)
                    env['current_date'] = datetime.datetime.today()
                    env['time'] = time
                    env['context'] = context
                    env['active_id'] = value.id
                    invisible = PYSONDecoder(env).decode(pyson_invisible)
                    if invisible:
                        value = ''
                        break
                value = value[field_name]
                if isinstance(value, (BrowseRecordList, list)):
                    first = True
                    child_fields_names = [(x[:i + 1] == fields_tree[:i + 1] and
                        x[i + 1:]) or [] for x in fields_names]
                    if child_fields_names in done:
                        break
                    done.append(child_fields_names)
                    for child_record in value:
                        child_lines = self.__export_row(cursor, user,
                                child_record, child_fields_names, context)
                        if first:
                            for child_fpos in xrange(len(fields_names)):
                                if child_lines and child_lines[0][child_fpos]:
                                    data[child_fpos] = \
                                            child_lines[0][child_fpos]
                            lines += child_lines[1:]
                            first = False
                        else:
                            lines += child_lines
                    break
                i += 1
            if i == len(fields_tree):
                if value is None:
                    value = ''
                data[fpos] = value
        return [data] + lines

    def export_data(self, cursor, user, ids, fields_names, context=None):
        '''
        Return list of list of values for each id in ids.
        The list of values follows fields_names.
        Relational fields are defined with '/' at any depth.

        :param cursor: the database cursor
        :param ids: a list of ids
        :param fields_names: a list of field names
        :param context: the context
        :return: a list of list of values for each id in ids
        '''
        fields_names = [x.split('/') for x in fields_names]
        datas = []
        for record in self.browse(cursor, user, ids, context):
            datas += self.__export_row(cursor, user, record, fields_names, context)
        return datas

    def import_data(self, cursor, user, fields_names, datas, context=None):
        '''
        Create records for all values in datas.
        The field names of values must be defined in fields_names.

        :param cursor: the database cursor
        :param user: the user id
        :param fields_names: a list of fields names
        :param datas: the data to import
        :param context: the context
        :return: a tuple with
            - the number of records imported
            - the last values if failed
            - the exception if failed
            - the warning if failed
        '''
        def process_lines(self, datas, prefix, fields_def, position=0):

            def warn(msgname, *args):
                msg = self.raise_user_error(cursor, msgname, args,
                      raise_exception=False, context=context)
                warnings.warn(msg)

            def get_selection(selection, value):
                res = False
                if not isinstance(selection, (tuple, list)):
                    selection = getattr(self, selection)(cursor, user,
                            context=context)
                for key, _ in selection:
                    if str(key) == value:
                        res = key
                        break
                if value and not res:
                    warn('not_found_in_selection', value, '/'.join(field))
                return res

            def get_many2one(relation, value):
                if not value:
                    return False
                relation_obj = self.pool.get(relation)
                res = relation_obj.search(cursor, user, [
                    ('rec_name', '=', value),
                    ], limit=2, context=context)
                if len(res) < 1:
                    warn('relation_not_found', value, relation)
                    res = False
                elif len(res) > 1:
                    warn('too_many_relations_found', value, relation)
                    res = False
                else:
                    res = res[0]
                return res

            def get_many2many(relation, value):
                if not value:
                    return False
                res = []
                relation_obj = self.pool.get(relation)
                for word in csv.reader(StringIO.StringIO(value), delimiter=',',
                        quoting=csv.QUOTE_NONE, escapechar='\\').next():
                    res2 = relation_obj.search(cursor, user, [
                        ('rec_name', '=', word),
                        ], limit=2, context=context)
                    if len(res2) < 1:
                        warn('relation_not_found', word, relation)
                    elif len(res2) > 1:
                        warn('too_many_relations_found', word, relation)
                    else:
                        res.extend(res2)
                if len(res):
                    res = [('set', res)]
                return res

            def get_reference(value):
                if not value:
                    return False
                try:
                    relation, value = value.split(',', 1)
                except:
                    warn('reference_syntax_error', value, '/'.join(field))
                    return False
                relation_obj = self.pool.get(relation)
                res = relation_obj.search(cursor, user, [
                    ('rec_name', '=', value),
                    ], limit=2, context=context)
                if len(res) < 1:
                    warn('relation_not_found', value, relation)
                    res = False
                elif len(res) > 1:
                    warn('too_many_relations_found', value, relation)
                    res = False
                else:
                    res = '%s,%s' % (relation, str(res[0]))
                return res

            def get_by_id(value):
                if not value:
                    return False
                relation = None
                ftype = fields_def[field[-1][:-3]]['type']
                if ftype == 'many2many':
                    value = csv.reader(StringIO.StringIO(value), delimiter=',',
                            quoting=csv.QUOTE_NONE, escapechar='\\').next()
                elif ftype == 'reference':
                    try:
                        relation, value = value.split(',', 1)
                    except:
                        warn('reference_syntax_error', value, '/'.join(field))
                        return False
                    value = [value]
                else:
                    value = [value]
                res_ids = []
                for word in value:
                    try:
                        module, xml_id = word.rsplit('.', 1)
                    except:
                        warn('xml_id_syntax_error', word, '/'.join(field))
                        continue
                    db_id = ir_model_data_obj.get_id(cursor, user,
                            module, xml_id)
                    res_ids.append(db_id)
                if ftype == 'many2many' and res_ids:
                    return [('set', res_ids)]
                elif ftype == 'reference' and res_ids:
                    return '%s,%s' % (relation, str(res_ids[0]))
                return res_ids and res_ids[0] or False

            line = datas[position]
            row = {}
            translate = {}
            todo = set()
            prefix_len = len(prefix)
            # Import normal fields_names
            for i, field in enumerate(fields_names):
                if i >= len(line):
                    raise Exception('ImportError',
                            'Please check that all your lines have %d cols.' % \
                            (len(fields_names),))
                is_prefix_len = (len(field) == (prefix_len + 1))
                value = line[i]
                if is_prefix_len and field[-1].endswith(':id'):
                    row[field[0][:-3]] = get_by_id(value)
                elif is_prefix_len and ':lang=' in field[-1]:
                    field_name, lang = field[-1].split(':lang=')
                    translate.setdefault(lang, {})[field_name] = value or False
                elif is_prefix_len and prefix == field[:-1]:
                    this_field_def = fields_def[field[-1]]
                    field_type = this_field_def['type']
                    res = False
                    if field_type == 'boolean':
                        if value.lower() == 'true':
                            res = True
                        elif value.lower() == 'false':
                            res = False
                        else:
                            res = value and bool(int(value))
                    elif field_type == 'integer':
                        res = value and int(value)
                    elif field_type == 'float':
                        res = value and float(value)
                    elif field_type == 'numeric':
                        res = value and Decimal(value)
                    elif field_type == 'date':
                        res = value and datetime.date(*time.strptime(value,
                            '%Y-%m-%d')[:3])
                    elif field_type == 'datetime':
                        res = value and datetime.datetime(*time.strptime(value,
                            '%Y-%m-%d %H:%M:%S')[:6])
                    elif field_type == 'selection':
                        res = get_selection(this_field_def['selection'], value)
                    elif field_type == 'many2one':
                        res = get_many2one(this_field_def['relation'], value)
                    elif field_type == 'many2many':
                        res = get_many2many(this_field_def['relation'], value)
                    elif field_type == 'reference':
                        res = get_reference(value)
                    else:
                        res = value or False
                    row[field[-1]] = res
                elif prefix == field[0:prefix_len]:
                    todo.add(field[prefix_len])
            # Import one2many fields
            nbrmax = 1
            for field in todo:
                newfd = self.pool.get(fields_def[field]['relation']).fields_get(
                        cursor, user, context=context)
                res = process_lines(self, datas, prefix + [field], newfd,
                        position)
                (newrow, max2, _) = res
                nbrmax = max(nbrmax, max2)
                reduce(lambda x, y: x and y, newrow)
                row[field] = (reduce(lambda x, y: x or y, newrow.values()) and
                         [('create', newrow)]) or []
                i = max2
                while (position + i) < len(datas):
                    test = True
                    for j, field2 in enumerate(fields_names):
                        if len(field2) <= (prefix_len + 1) \
                               and datas[position + i][j]:
                            test = False
                            break
                    if not test:
                        break
                    (newrow, max2, _) = \
                            process_lines(self, datas, prefix + [field], newfd,
                                    position + i)
                    if reduce(lambda x, y: x or y, newrow.values()):
                        row[field].append(('create', newrow))
                    i += max2
                    nbrmax = max(nbrmax, i)
            if prefix_len == 0:
                for i in xrange(max(nbrmax, 1)):
                    datas.pop(0)
            return (row, nbrmax, translate)

        ir_model_data_obj = self.pool.get('ir.model.data')

        # logger for collecting warnings for the client
        warnings = logging.Logger("import")
        warning_stream = StringIO.StringIO()
        warnings.addHandler(logging.StreamHandler(warning_stream))

        if context is None:
            context = {}
        len_fields_names = len(fields_names)
        for data in datas:
            assert len(data) == len_fields_names
        fields_names = [x.split('/') for x in fields_names]
        fields_def = self.fields_get(cursor, user, context=context)
        done = 0

        warning = ''
        while len(datas):
            res = {}
            try:
                (res, _, translate) = \
                        process_lines(self, datas, [], fields_def)
                warning = warning_stream.getvalue()
                if warning:
                    cursor.rollback()
                    return (-1, res, warning, '')
                new_id = self.create(cursor, user, res, context=context)
                trans_ctx = context.copy()
                for lang in translate:
                    trans_ctx['language'] = lang
                    self.write(cursor, user, new_id, translate[lang],
                            context=trans_ctx)
            except Exception, exp:
                logger = logging.getLogger('import')
                logger.error(exp)
                cursor.rollback()
                warning = '\n'.join(map(str, exp[1:]) + [warning])
                return (-1, res, exp, warning)
            done += 1
        return (done, 0, 0, 0)

    def check_xml_record(self, cursor, user, ids, values, context=None):
        """
        Check if a list of records and their corresponding fields are
        originating from xml data. This is used by write and delete
        functions: if the return value is True the records can be
        written/deleted, False otherwise. The default behaviour is to
        forbid any modification on records/fields originating from
        xml. Values is the dictionary of written values. If values is
        equal to None, no field by field check is performed, False is
        returned as soon as one of the record comes from the xml.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of ids or an id
        :param values: a dictionary with field names as key and
            written values as value
        :param context: the context
        :return: True or False
        """
        model_data_obj = self.pool.get('ir.model.data')
        # Allow root user to update/delete
        if user == 0:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        model_data_ids = model_data_obj.search(cursor, 0, [
            ('model', '=', self._name),
            ('db_id', 'in', ids),
            ], context=context)
        if not model_data_ids:
            return True
        if values == None:
            return False
        for line in model_data_obj.browse(cursor, 0, model_data_ids,
                context=context):
            if not line.values:
                continue
            xml_values = safe_eval(line.values, {
                'Decimal': Decimal,
                'datetime': datetime,
                })
            for key, val in values.iteritems():
                if key in xml_values and val != xml_values[key]:
                    return False
        return True

    def check_recursion(self, cursor, user, ids, parent='parent'):
        '''
        Function that checks if there is no recursion in the tree
        composed with parent as parent field name.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of ids
        :param parent: the parent field name
        :return: True or False
        '''
        if parent in self._columns:
            parent_type = self._columns[parent]._type
        elif parent in self._inherit_fields:
            parent_type = self._inherit_fields[parent][2]._type
        else:
            raise Exception('Field %s not available on object "%s"' % \
                    (parent, self._name))

        if parent_type not in ('many2one', 'many2many'):
            raise Exception(
                    'Unsupported field type "%s" for field "%s" on "%s"' % \
                    (parent_type, parent, self._name))

        records = self.browse(cursor, user, ids)
        visited = set()

        for record in records:
            walked = set()
            walker = record[parent]
            while walker:
                if parent_type == 'many2many':
                    for walk in walker:
                        walked.add(walk.id)
                        if walk.id == record.id:
                            return False
                    walker = list(chain(*(walk[parent] for walk in walker
                            if walk.id not in visited)))
                else:
                    walked.add(walker.id)
                    if walker.id == record.id:
                        return False
                    walker = walker[parent] not in visited and walker[parent]
            visited.update(walked)

        return True

    def _get_error_args(self, cursor, user, field_name, context=None):
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


    def _validate(self, cursor, user, ids, context=None):
        if context is None:
            context = {}

        if user == 0 and context.get('user'):
            ctx = context.copy()
            del ctx['user']
            return self._validate(cursor, context['user'], ids, context=ctx)

        context = context.copy()
        for field in self._constraints:
            if not getattr(self, field[0])(cursor, user, ids):
                self.raise_user_error(cursor, field[1], context=context)

        if not 'res.user' in self.pool.object_name_list() \
                or user == 0:
            ctx_pref = {
            }
        else:
            user_obj = self.pool.get('res.user')
            ctx_pref = user_obj.get_preferences(cursor, user,
                context_only=True, context=context)

        def is_pyson(test):
            if isinstance(test, PYSON):
                return True
            if isinstance(test, (list, tuple)):
                for i in test:
                    if isinstance(i, PYSON):
                        return True
                    if isinstance(i, (list, tuple)):
                        if is_pyson(i):
                            return True
            return False

        context.update(ctx_pref)
        records = self.browse(cursor, user, ids, context=context)
        for field_name, field in self._columns.iteritems():
            if isinstance(field, fields.Function) and \
                    not field.setter:
                continue
            # validate domain
            if field._type in ('many2one', 'many2many', 'one2many') \
                    and field.domain:
                if field._type in ('many2one', 'one2many'):
                    relation_obj = self.pool.get(field.model_name)
                else:
                    relation_obj = field.get_target(self.pool)
                if is_pyson(field.domain):
                    pyson_domain = PYSONEncoder().encode(field.domain)
                    ctx = context.copy()
                    ctx.update(ctx_pref)
                    for record in records:
                        env = EvalEnvironment(record, self)
                        env.update(ctx)
                        env['current_date'] = datetime.datetime.today()
                        env['time'] = time
                        env['context'] = context
                        env['active_id'] = record.id
                        domain = PYSONDecoder(env).decode(pyson_domain)
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
                                    error_args=self._get_error_args(cursor,
                                        user, field_name, context=context),
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
                            field.domain,
                            ], context=context)
                        if not set(relation_ids) == set(find_ids):
                            self.raise_user_error(cursor,
                                    'domain_validation_record',
                                    error_args=self._get_error_args(cursor,
                                        user, field_name, context=context),
                                    context=context)
            # validate states required
            if field.states and 'required' in field.states:
                if is_pyson(field.states['required']):
                    ctx = context.copy()
                    ctx.update(ctx_pref)
                    pyson_required = PYSONEncoder().encode(
                            field.states['required'])
                    for record in records:
                        env = EvalEnvironment(record, self)
                        env.update(ctx)
                        env['current_date'] = datetime.datetime.today()
                        env['time'] = time
                        env['context'] = context
                        env['active_id'] = record.id
                        required = PYSONDecoder(env).decode(pyson_required)
                        if required and not record[field_name]:
                            self.raise_user_error(cursor,
                                    'required_validation_record',
                                    error_args=self._get_error_args(cursor,
                                        user, field_name, context=context),
                                    context=context)
                else:
                    if field.states['required']:
                        for record in records:
                            if not record[field_name]:
                                self.raise_user_error(cursor,
                                        'required_validation_record',
                                        error_args=self._get_error_args(cursor,
                                            user, field_name, context=context),
                                        context=context)
            # validate required
            if field.required:
                for record in records:
                    if isinstance(record[field_name], (BrowseRecordNull,
                        type(None), type(False))) and not record[field_name]:
                        self.raise_user_error(cursor,
                                'required_validation_record',
                                error_args=self._get_error_args(cursor,
                                    user, field_name, context=context),
                                context=context)
            # validate size
            if hasattr(field, 'size') and field.size:
                for record in records:
                    if len(record[field_name] or '') > field.size:
                        self.raise_user_error(cursor,
                                'size_validation_record',
                                error_args=self._get_error_args(cursor,
                                    user, field_name, context=context),
                                context=context)

            # validate digits
            if hasattr(field, 'digits') and field.digits:
                if is_pyson(field.digits):
                    pyson_digits = PYSONEncoder().encode(field.digits)
                    ctx = context.copy()
                    ctx.update(ctx_pref)
                    for record in records:
                        env = EvalEnvironment(record, self)
                        env.update(ctx)
                        env['current_date'] = datetime.datetime.today()
                        env['time'] = time
                        env['context'] = context
                        env['active_id'] = record.id
                        digits = PYSONDecoder(env).decode(pyson_digits)
                        if not round(record[field_name], digits[1]) == \
                                float(record[field_name]):
                            self.raise_user_error(cursor,
                                    'digits_validation_record',
                                    error_args=self._get_error_args(cursor,
                                        user, field_name, context=context),
                                    context=context)
                else:
                    for record in records:
                        if not round(record[field_name], field.digits[1]) == \
                                float(record[field_name]):
                            self.raise_user_error(cursor,
                                    'digits_validation_record',
                                    error_args=self._get_error_args(cursor,
                                        user, field_name, context=context),
                                    context=context)

    def _clean_defaults(self, defaults):
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
                obj = self.pool.get(fld_def.model_name)
                vals[field] = []
                for defaults2 in defaults[field]:
                    vals2 = obj._clean_defaults(defaults2)
                    vals[field].append(('create', vals2))
            elif fld_def._type in ('many2many',):
                vals[field] = [('set', defaults[field])]
            elif fld_def._type in ('boolean',):
                vals[field] = bool(defaults[field])
            else:
                vals[field] = defaults[field]
        return vals

    def workflow_trigger_trigger(self, cursor, user, ids, context=None):
        '''
        Trigger a trigger event.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of id or an id
        :param context: the context
        '''
        trigger_obj = self.pool.get('workflow.trigger')
        instance_obj = self.pool.get('workflow.instance')

        if isinstance(ids, (int, long)):
            ids = [ids]

        trigger_ids = trigger_obj.search(cursor, 0, [
            ('res_id', 'in', ids),
            ('model', '=', self._name),
            ], context=context)
        instances = set([trigger.instance \
                for trigger in trigger_obj.browse(cursor, 0, trigger_ids,
                    context=context)])
        for instance in instances:
            instance_obj.update(cursor, user, instance, context=context)
