#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

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
from functools import reduce
import traceback
import sys
from trytond.model import Model
from trytond.model import fields
from trytond.model.browse import BrowseRecordList, BrowseRecord, \
        BrowseRecordNull
from trytond.model.browse import EvalEnvironment
from trytond.tools import safe_eval, reduce_domain
from trytond.pyson import PYSONEncoder, PYSONDecoder, PYSON
from trytond.const import OPERATORS, RECORD_CACHE_SIZE
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.cache import LRUDict
from trytond.config import CONFIG
from .modelview import ModelView


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
        if isinstance(self, ModelView):
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

    def default_create_uid(self):
        "Default value for uid field."
        return int(Transaction().user)

    def default_create_date(self):
        "Default value for create_date field."
        return datetime.datetime.today()

    def __clean_xxx2many_cache(self):
        # Clean cursor cache
        to_clean = [(model._name, field_name)
                for model_name, model in Pool().iterobject(type='model')
                for field_name, target_name in model._xxx2many_targets
                if target_name == self._name]
        for cache in Transaction().cursor.cache.values():
            for cache in (cache, cache.get('_language_cache', {}).values()):
                for model_name, field_name in to_clean:
                    if model_name in cache:
                        for model_id in cache[model_name]:
                            if field_name in cache[model_name][model_id]:
                                del cache[model_name][model_id][field_name]

    def create(self, values):
        '''
        Create records.

        :param values: a dictionary with fields names as key
                and created values as value
        :return: the id of the created record
        '''
        pool = Pool()
        model_access_obj = pool.get('ir.model.access')
        model_field_access_obj = pool.get('ir.model.field.access')

        model_access_obj.check(self._name, 'create')
        model_field_access_obj.check(self._name,
                [x for x in values if x in self._columns], 'write')
        self.__clean_xxx2many_cache()
        return False

    def trigger_create(self, id):
        '''
        Trigger create actions

        :param id: the created id
        '''
        trigger_obj = Pool().get('ir.trigger')
        trigger_ids = trigger_obj.get_triggers(self._name, 'create')
        if not trigger_ids:
            return
        record = self.browse(id)
        triggers = trigger_obj.browse(trigger_ids)
        for trigger in triggers:
            if trigger_obj.eval(trigger, record):
                trigger_obj.trigger_action([id], trigger.id)

    def read(self, ids, fields_names=None):
        '''
        Read records.

        :param ids: a list of ids or an id
        :param fields_names: fields names to read if None read all fields
        :return: a list of dictionnary or a dictionnary if ids is an id
            the dictionnaries will have fields names as key
            and fields value as value. The list will not be in the same order.
        '''
        pool = Pool()
        model_access_obj = pool.get('ir.model.access')
        model_field_access_obj = pool.get('ir.model.field.access')

        model_access_obj.check(self._name, 'read')
        model_field_access_obj.check(self._name,
                fields_names or self._columns.keys(), 'read')
        if isinstance(ids, (int, long)):
            return {}
        return []

    def write(self, ids, values):
        '''
        Write values on records.

        :param ids: a list of ids or an id
        :param values: a dictionary with fields names as key
                and written values as value
        :return: True if succeed
        '''
        pool = Pool()
        model_access_obj = pool.get('ir.model.access')
        model_field_access_obj = pool.get('ir.model.field.access')

        model_access_obj.check(self._name, 'write')
        model_field_access_obj.check(self._name,
                [x for x in values if x in self._columns], 'write')
        if not self.check_xml_record(ids, values):
            self.raise_user_error('write_xml_record',
                    error_description='xml_record_desc')

        # Clean cursor cache
        for cache in Transaction().cursor.cache.values():
            for cache in (cache, cache.get('_language_cache', {}).values()):
                if self._name in cache:
                    if isinstance(ids, (int, long)):
                        ids = [ids]
                    for i in ids:
                        if i in cache[self._name]:
                            cache[self._name][i] = {}
        if ids:
            self.__clean_xxx2many_cache()
        return False

    def trigger_write_get_eligibles(self, ids):
        '''
        Return eligible ids for write actions by triggers

        :param ids: a list of ids
        :return: a dictionary of the lists of eligible ids by triggers
        '''
        trigger_obj = Pool().get('ir.trigger')
        trigger_ids = trigger_obj.get_triggers(self._name, 'write')
        if not trigger_ids:
            return {}
        records = self.browse(ids)
        triggers = trigger_obj.browse(trigger_ids)
        eligibles = {}
        for trigger in triggers:
            eligibles[trigger.id] = []
            for record in records:
                if not trigger_obj.eval(trigger, record):
                    eligibles[trigger.id].append(record.id)
        return eligibles

    def trigger_write(self, eligibles):
        '''
        Trigger write actions

        :param eligibles: a dictionary of the lists of eligible ids by triggers
        '''
        trigger_obj = Pool().get('ir.trigger')
        trigger_ids = eligibles.keys()
        if not trigger_ids:
            return
        records = self.browse(list(chain(*eligibles.values())))
        id2record = dict((x.id, x) for x in records)
        triggers = trigger_obj.browse(trigger_ids)
        for trigger in triggers:
            triggered_ids = []
            for record_id in eligibles[trigger.id]:
                record = id2record[record_id]
                if trigger_obj.eval(trigger, record):
                    triggered_ids.append(record.id)
            if triggered_ids:
                trigger_obj.trigger_action(triggered_ids, trigger.id)

    def delete(self, ids):
        '''
        Delete records.

        :param ids: a list of ids or an id
        :return: True if succeed
        '''
        model_access_obj = Pool().get('ir.model.access')

        model_access_obj.check(self._name, 'delete')
        if not self.check_xml_record(ids, None):
            self.raise_user_error('delete_xml_record',
                    error_description='xml_record_desc')

        # Clean cursor cache
        for cache in Transaction().cursor.cache.values():
            for cache in (cache, cache.get('_language_cache', {}).values()):
                if self._name in cache:
                    if isinstance(ids, (int, long)):
                        ids = [ids]
                    for i in ids:
                        if i in cache[self._name]:
                            del cache[self._name][i]
        if ids:
            self.__clean_xxx2many_cache()
        return False

    def trigger_delete(self, ids):
        '''
        Trigger delete actions

        :param ids: the deleted ids
        '''
        trigger_obj = Pool().get('ir.trigger')
        trigger_ids = trigger_obj.get_triggers(self._name, 'delete')
        if not trigger_ids:
            return
        records = self.browse(ids)
        triggers = trigger_obj.browse(trigger_ids)
        for trigger in triggers:
            triggered_ids = []
            for record in records:
                if trigger_obj.eval(trigger, record):
                    triggered_ids.append(record.id)
            if triggered_ids:
                trigger_obj.trigger_action(triggered_ids, trigger.id)

    def copy(self, ids, default=None):
        '''
        Duplicate the record(s) in ids.

        :param ids: a list of ids or an id
        :param default: a dictionary with field name as keys and
            new value for the field as value
        :return: a list of new ids or the new id
        '''
        pool = Pool()
        lang_obj = pool.get('ir.lang')
        if default is None:
            default = {}

        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]

        if 'state' not in default:
            if 'state' in self._defaults:
                default['state'] = self._defaults['state']()

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
                elif ftype in ('many2one', 'one2one'):
                    try:
                        data[field_name] = data[field_name] and \
                                data[field_name][0]
                    except Exception:
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
        datas = self.read(ids, fields_names=fields_names)
        field_defs = self.fields_get(fields_names=fields_names)
        for data in datas:
            data_id = data['id']
            data, data_o2m = convert_data(field_defs, data)
            new_ids[data_id] = self.create(data)
            for field_name in data_o2m:
                relation_model = pool.get(
                        field_defs[field_name]['relation'])
                relation_field = field_defs[field_name]['relation_field']
                if relation_field:
                    relation_model.copy(data_o2m[field_name],
                            default={relation_field: new_ids[data_id]})

        fields_translate = {}
        for field_name, field in field_defs.iteritems():
            if field_name in self._columns and \
                    getattr(self._columns[field_name], 'translate', False):
                fields_translate[field_name] = field

        if fields_translate:
            lang_ids = lang_obj.search([
                ('translatable', '=', True),
                ])
            if lang_ids:
                lang_ids += lang_obj.search([
                    ('code', '=', 'en_US'),
                    ])
                langs = lang_obj.browse(lang_ids)
                for lang in langs:
                    with Transaction().set_context(language=lang.code):
                        datas = self.read(ids,
                                fields_names=fields_translate.keys() + ['id'])
                        for data in datas:
                            data_id = data['id']
                            data, _ = convert_data(fields_translate, data)
                            self.write(new_ids[data_id], data)
        if int_id:
            return new_ids.values()[0]
        return new_ids.values()

    def search(self, domain, offset=0, limit=None, order=None, count=False):
        '''
        Return a list of ids that match the domain.

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
        :param count: a boolean to return only the length of the result
        :return: a list of ids or an integer
        '''
        if count:
            return 0
        return []

    def search_count(self, domain):
        '''
        Return the number of records that match the domain. (See search)

        :param domain: a domain like in search
        :return: an integer
        '''
        res = self.search(domain, count=True)
        if isinstance(res, list):
            return len(res)
        return res

    def search_read(self, domain, offset=0, limit=None, order=None,
            fields_names=None):
        '''
        Call search and read functions at once.
        Useful for the client to reduce the number of calls.

        :param domain: a domain like in search
        :param offset: an integer to specify the offset for the result
        :param limit: an integer to specify the number of records
        :param order: a list of tuples that are constructed like this:
            ('field name', 'DESC|ASC')
            allowing to to specify the order of result
        :param fields_names: fields names to read if None read all fields
        :return: a list of dictionaries or a dictionary if limit is 1
            the dictionaries will have field names as key
            and field values as value
        '''
        ids = self.search(domain, offset=offset, limit=limit, order=order)

        if not fields_names:
            fields_names = list(set(self._columns.keys() \
                    + self._inherit_fields.keys()))
        if 'id' not in fields_names:
            fields_names.append('id')

        res = []
        for model in self.browse(ids):
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

    def _search_domain_active(self, domain, active_test=True):
        # reduce_domain return a new instance so we can safety modify domain
        domain = reduce_domain(domain)
        # if the object has a field named 'active', filter out all inactive
        # records unless they were explicitely asked for
        if not (('active' in self._columns
            or 'active' in self._inherit_fields.keys())
            and (active_test
                and Transaction().context.get('active_test', True))):
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

    def get_rec_name(self, ids, name):
        '''
        Return a dictionary with id as key and rec_name as value.
        It is used by the Function field rec_name.

        :param ids: a list of ids
        :param name: the name of the Function field
        :return: a dictionary
        '''
        if not ids:
            return {}
        res = {}
        rec_name = self._rec_name
        if rec_name not in self._columns \
                and rec_name not in self._inherit_fields.keys():
            rec_name = 'id'
        for record in self.browse(ids):
            res[record.id] = unicode(record[rec_name])
        return res

    def search_rec_name(self, name, clause):
        '''
        Return a list of arguments for search on rec_name.

        :param name: the name of the Function field
        :param clause: a domain clause
        :return: a list of domain clause
        '''
        rec_name = self._rec_name
        if (rec_name not in self._columns
                and rec_name not in self._inherit_fields):
            return []
        return [(rec_name,) + clause[1:]]

    def browse(self, ids):
        '''
        Return a BrowseRecordList for the ids
            or BrowseRecord if ids is a integer.

        :param ids: a list of ids or an id
        :return: a BrowseRecordList or a BrowseRecord
        '''
        local_cache = LRUDict(RECORD_CACHE_SIZE)
        if isinstance(ids, (int, long)):
            return BrowseRecord(ids, self, [ids], local_cache)
        return BrowseRecordList((BrowseRecord(x, self, ids, local_cache)
            for x in ids))

    def __export_row(self, record, fields_names):
        pool = Pool()
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
                model_obj = pool.get(value._model_name)
                if field_name in model_obj._columns:
                    field = model_obj._columns[field_name]
                elif field_name in model_obj._inherit_fields:
                    field = model_obj._inherit_fields[field_name][2]
                else:
                    raise Exception('Field %s not available on object "%s"'
                        % (field_name, model_obj._name))
                if field.states and 'invisible' in field.states:
                    pyson_invisible = PYSONEncoder().encode(
                            field.states['invisible'])
                    env = EvalEnvironment(value, model_obj)
                    env.update(Transaction().context)
                    env['current_date'] = datetime.datetime.today()
                    env['time'] = time
                    env['context'] = Transaction().context
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
                        child_lines = self.__export_row(child_record,
                                child_fields_names)
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

    def export_data(self, ids, fields_names):
        '''
        Return list of list of values for each id in ids.
        The list of values follows fields_names.
        Relational fields are defined with '/' at any depth.

        :param ids: a list of ids
        :param fields_names: a list of field names
        :return: a list of list of values for each id in ids
        '''
        fields_names = [x.split('/') for x in fields_names]
        datas = []
        for record in self.browse(ids):
            datas += self.__export_row(record, fields_names)
        return datas

    def import_data(self, fields_names, datas):
        '''
        Create records for all values in datas.
        The field names of values must be defined in fields_names.

        :param fields_names: a list of fields names
        :param datas: the data to import
        :return: a tuple with
            - the number of records imported
            - the last values if failed
            - the exception if failed
            - the warning if failed
        '''
        pool = Pool()
        def process_lines(self, datas, prefix, fields_def, position=0):

            def warn(msgname, *args):
                msg = self.raise_user_error(msgname, args,
                        raise_exception=False)
                warnings.warn(msg)

            def get_selection(selection, value):
                res = False
                if not isinstance(selection, (tuple, list)):
                    selection = getattr(self, selection)()
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
                relation_obj = pool.get(relation)
                res = relation_obj.search([
                    ('rec_name', '=', value),
                    ], limit=2)
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
                relation_obj = pool.get(relation)
                for word in csv.reader(StringIO.StringIO(value), delimiter=',',
                        quoting=csv.QUOTE_NONE, escapechar='\\').next():
                    res2 = relation_obj.search([
                        ('rec_name', '=', word),
                        ], limit=2)
                    if len(res2) < 1:
                        warn('relation_not_found', word, relation)
                    elif len(res2) > 1:
                        warn('too_many_relations_found', word, relation)
                    else:
                        res.extend(res2)
                if len(res):
                    res = [('set', res)]
                return res

            def get_one2one(relation, value):
                return ('set', get_many2one(relation, value))

            def get_reference(value):
                if not value:
                    return False
                try:
                    relation, value = value.split(',', 1)
                except Exception:
                    warn('reference_syntax_error', value, '/'.join(field))
                    return False
                relation_obj = pool.get(relation)
                res = relation_obj.search([
                    ('rec_name', '=', value),
                    ], limit=2)
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
                    except Exception:
                        warn('reference_syntax_error', value, '/'.join(field))
                        return False
                    value = [value]
                else:
                    value = [value]
                res_ids = []
                for word in value:
                    try:
                        module, xml_id = word.rsplit('.', 1)
                    except Exception:
                        warn('xml_id_syntax_error', word, '/'.join(field))
                        continue
                    db_id = ir_model_data_obj.get_id(module, xml_id)
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
                    elif field_type == 'one2one':
                        res = get_one2one(this_field_def['relation'], value)
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
                newfd = pool.get(fields_def[field]['relation']
                        ).fields_get()
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

        ir_model_data_obj = pool.get('ir.model.data')

        # logger for collecting warnings for the client
        warnings = logging.Logger("import")
        warning_stream = StringIO.StringIO()
        warnings.addHandler(logging.StreamHandler(warning_stream))

        len_fields_names = len(fields_names)
        for data in datas:
            assert len(data) == len_fields_names
        fields_names = [x.split('/') for x in fields_names]
        fields_def = self.fields_get()
        done = 0

        warning = ''
        while len(datas):
            res = {}
            try:
                (res, _, translate) = \
                        process_lines(self, datas, [], fields_def)
                warning = warning_stream.getvalue()
                if warning:
                    # XXX should raise Exception
                    Transaction().cursor.rollback()
                    return (-1, res, warning, '')
                new_id = self.create(res)
                for lang in translate:
                    with Transaction().set_context(language=lang):
                        self.write(new_id, translate[lang])
            except Exception, exp:
                logger = logging.getLogger('import')
                logger.error(exp)
                # XXX should raise Exception
                Transaction().cursor.rollback()
                tb_s = reduce(lambda x, y: x + y,
                        traceback.format_exception(*sys.exc_info()))
                warning = '%s\n%s' % (tb_s, warning)
                return (-1, res, exp, warning)
            done += 1
        return (done, 0, 0, 0)

    def check_xml_record(self, ids, values):
        """
        Check if a list of records and their corresponding fields are
        originating from xml data. This is used by write and delete
        functions: if the return value is True the records can be
        written/deleted, False otherwise. The default behaviour is to
        forbid any modification on records/fields originating from
        xml. Values is the dictionary of written values. If values is
        equal to None, no field by field check is performed, False is
        returned as soon as one of the record comes from the xml.

        :param ids: a list of ids or an id
        :param values: a dictionary with field names as key and
            written values as value
        :return: True or False
        """
        model_data_obj = Pool().get('ir.model.data')
        # Allow root user to update/delete
        if Transaction().user == 0:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        with Transaction().set_user(0):
            model_data_ids = model_data_obj.search([
                ('model', '=', self._name),
                ('db_id', 'in', ids),
                ])
            if not model_data_ids:
                return True
            if values == None:
                return False
            for line in model_data_obj.browse(model_data_ids):
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

    def check_recursion(self, ids, parent='parent'):
        '''
        Function that checks if there is no recursion in the tree
        composed with parent as parent field name.

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

        records = self.browse(ids)
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

    def _get_error_args(self, field_name):
        pool = Pool()
        model_field_obj = pool.get('ir.model.field')
        error_args = (field_name, self._name)
        if model_field_obj:
            model_field_ids = model_field_obj.search([
                        ('name', '=', field_name),
                        ('model.model', '=', self._name),
                        ], limit=1)
            if model_field_ids:
                model_field = model_field_obj.browse(model_field_ids[0])
                error_args = (model_field.field_description,
                        model_field.model.name)
        return error_args


    def _validate(self, ids):
        pool = Pool()
        if (Transaction().user == 0
                and Transaction().context.get('user')):
            with Transaction().set_user(Transaction().context.get('user')):
                return self._validate(ids)

        for field in self._constraints:
            if not getattr(self, field[0])(ids):
                self.raise_user_error(field[1])

        if not 'res.user' in pool.object_name_list() \
                or Transaction().user == 0:
            ctx_pref = {
            }
        else:
            user_obj = pool.get('res.user')
            ctx_pref = user_obj.get_preferences(context_only=True)

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

        with Transaction().set_context(ctx_pref):
            records = self.browse(ids)
            for field_name, field in self._columns.iteritems():
                if isinstance(field, fields.Function) and \
                        not field.setter:
                    continue
                # validate domain
                if (field._type in
                        ('many2one', 'many2many', 'one2many', 'one2one')
                    and field.domain):
                    if field._type in ('many2one', 'one2many'):
                        relation_obj = pool.get(field.model_name)
                    else:
                        relation_obj = field.get_target()
                    if is_pyson(field.domain):
                        pyson_domain = PYSONEncoder().encode(field.domain)
                        for record in records:
                            env = EvalEnvironment(record, self)
                            env.update(Transaction().context)
                            env['current_date'] = datetime.datetime.today()
                            env['time'] = time
                            env['context'] = Transaction().context
                            env['active_id'] = record.id
                            domain = PYSONDecoder(env).decode(pyson_domain)
                            relation_ids = []
                            if record[field_name]:
                                if field._type in ('many2one',):
                                    relation_ids.append(record[field_name].id)
                                else:
                                    relation_ids.extend(
                                            [x.id for x in record[field_name]])
                            if relation_ids and not relation_obj.search([
                                        'AND',
                                        [('id', 'in', relation_ids)],
                                        domain,
                                        ]):
                                self.raise_user_error(
                                        'domain_validation_record',
                                        error_args=self._get_error_args(
                                            field_name))
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
                            find_ids = relation_obj.search([
                                'AND',
                                [('id', 'in', relation_ids)],
                                field.domain,
                                ])
                            if not set(relation_ids) == set(find_ids):
                                self.raise_user_error(
                                        'domain_validation_record',
                                        error_args=self._get_error_args(
                                            field_name))
                # validate states required
                if field.states and 'required' in field.states:
                    if is_pyson(field.states['required']):
                        pyson_required = PYSONEncoder().encode(
                                field.states['required'])
                        for record in records:
                            env = EvalEnvironment(record, self)
                            env.update(Transaction().context)
                            env['current_date'] = datetime.datetime.today()
                            env['time'] = time
                            env['context'] = Transaction().context
                            env['active_id'] = record.id
                            required = PYSONDecoder(env).decode(pyson_required)
                            if required and not record[field_name]:
                                self.raise_user_error(
                                        'required_validation_record',
                                        error_args=self._get_error_args(
                                            field_name))
                    else:
                        if field.states['required']:
                            for record in records:
                                if not record[field_name]:
                                    self.raise_user_error(
                                            'required_validation_record',
                                            error_args=self._get_error_args(
                                                field_name))
                # validate required
                if field.required:
                    for record in records:
                        if isinstance(record[field_name], (BrowseRecordNull,
                            type(None), type(False))) and not record[field_name]:
                            self.raise_user_error(
                                    'required_validation_record',
                                    error_args=self._get_error_args(field_name))
                # validate size
                if hasattr(field, 'size') and field.size:
                    for record in records:
                        if len(record[field_name] or '') > field.size:
                            self.raise_user_error(
                                    'size_validation_record',
                                    error_args=self._get_error_args(field_name))

                def digits_test(value, digits, field_name):
                    def raise_user_error():
                        self.raise_user_error('digits_validation_record',
                            error_args=self._get_error_args(field_name))
                    if isinstance(value, Decimal):
                        if not (value.quantize(Decimal(str(10.0**-digits[1])))
                                == value):
                            raise_user_error()
                    elif CONFIG.options['db_type'] != 'mysql':
                        if not (round(value, digits[1]) == float(value)):
                            raise_user_error()
                # validate digits
                if hasattr(field, 'digits') and field.digits:
                    if is_pyson(field.digits):
                        pyson_digits = PYSONEncoder().encode(field.digits)
                        for record in records:
                            env = EvalEnvironment(record, self)
                            env.update(Transaction().context)
                            env['current_date'] = datetime.datetime.today()
                            env['time'] = time
                            env['context'] = Transaction().context
                            env['active_id'] = record.id
                            digits = PYSONDecoder(env).decode(pyson_digits)
                            digits_test(record[field_name], digits, field_name)
                    else:
                        for record in records:
                            digits_test(record[field_name], field.digits,
                                field_name)

    def _clean_defaults(self, defaults):
        pool = Pool()
        vals = {}
        for field in defaults.keys():
            fld_def = (field in self._columns) and self._columns[field] \
                    or self._inherit_fields[field][2]
            if fld_def._type in ('many2one', 'one2one'):
                if isinstance(defaults[field], (list, tuple)):
                    vals[field] = defaults[field][0]
                else:
                    vals[field] = defaults[field]
            elif fld_def._type in ('one2many',):
                obj = pool.get(fld_def.model_name)
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

    def workflow_trigger_trigger(self, ids):
        '''
        Trigger a trigger event.

        :param ids: a list of id or an id
        '''
        pool = Pool()
        trigger_obj = pool.get('workflow.trigger')
        instance_obj = pool.get('workflow.instance')

        if isinstance(ids, (int, long)):
            ids = [ids]

        with Transaction().set_user(0):
            trigger_ids = trigger_obj.search([
                ('res_id', 'in', ids),
                ('model', '=', self._name),
                ])
            instances = set([trigger.instance for trigger in
                trigger_obj.browse(trigger_ids)])
        for instance in instances:
            instance_obj.update(instance)
