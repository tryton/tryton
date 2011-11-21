#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from __future__ import with_statement
import contextlib
from trytond.model import fields
from trytond.transaction import Transaction

class BrowseRecordList(list):
    '''
    A list of BrowseRecord
    '''
    #TODO: execute an object method on BrowseRecordList

    def __init__(self, lst):
        super(BrowseRecordList, self).__init__(lst)

    def get_eval(self):
        return [record.id for record in self]


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

    def __init__(self, record_id, model, local_cache=None):
        self._cursor = Transaction().cursor
        self._user = Transaction().user
        self._id = record_id
        self._model = model
        self._model_name = self._model._name
        self._context = Transaction().context

        cache = self._cursor.get_cache(self._context)
        cache.setdefault(model._name, {})
        cache.setdefault('_language_cache', {})
        self._data = cache[model._name]
        if not record_id in self._data:
            self._data[record_id] = {'id': record_id}
        self._cache = cache
        if local_cache is None:
            local_cache = {}
        self._local_cache = local_cache
        self._local_cache.setdefault(model._name, {})
        self._local_cache.setdefault('_language_cache', {})
        self._local_data = self._local_cache[model._name]
        if not record_id in self._local_data:
            self._local_data[record_id] = {}

    def __getitem__(self, name):
        if name == 'id':
            return self._id
        if name == 'setLang':
            return self.setLang
        if not self._data[self._id].has_key(name) \
                and not self._local_data[self._id].has_key(name):
            # build the list of fields we will fetch

            # fetch the definition of the field which was asked for
            if name in self._model._columns:
                col = self._model._columns[name]
            elif name in self._model._inherit_fields:
                col = self._model._inherit_fields[name][2]
            elif hasattr(self._model, name):
                return getattr(self._model, name)
            else:
                raise Exception('Error', 'Programming error: field "%s" ' \
                        'does not exist in model "%s"!' \
                        % (name, self._model._name))

            if col.loading == 'eager':
                field_access_obj = self._model.pool.get('ir.model.field.access')
                fread_accesses = {}
                for inherit_name in self._model._inherits:
                    inherit_obj = self._model.pool.get(inherit_name)
                    fread_accesses.update(field_access_obj.check(inherit_name,
                        inherit_obj._columns.keys(), 'read', access=True))
                fread_accesses.update(field_access_obj.check(self._model._name,
                    self._model._columns.keys(), 'read', access=True))
                to_remove = set(x for x, y in fread_accesses.iteritems()
                        if not y and x != name)

                ffields = dict((fname, field) for fname, (_, _, field)
                        in self._model._inherit_fields.iteritems()
                        if field.loading == 'eager'
                        and fname not in self._model._columns
                        and fname not in to_remove)
                ffields.update(dict((fname, field) for fname, field
                        in self._model._columns.iteritems()
                        if field.loading == 'eager'
                        and fname not in to_remove))
            else:
                ffields = {name: col}

            # add datetime_field
            for field in ffields.values():
                if hasattr(field, 'datetime_field') and field.datetime_field:
                    if field.datetime_field in self._model._columns:
                        datetime_field = self._model._columns[field.datetime_field]
                    else:
                        datetime_field = self._model._inherit_fields[
                                field.datetime_field][2]
                    ffields[field.datetime_field] = datetime_field

            if len(self._data) <= self._cursor.IN_MAX:
                iterids = self._data.iterkeys()
            else:
                iterids = self._local_data.iterkeys()
            ids = [x for x in iterids \
                    if not self._data.setdefault(x, {}).has_key(name) \
                    and not self._local_data.setdefault(x, {}).has_key(name)]
            # read the data
            with contextlib.nested(Transaction().set_cursor(self._cursor),
                    Transaction().set_user(self._user),
                    Transaction().set_context(self._context)):
                datas = self._model.read(ids, ffields.keys())

                # create browse records for 'remote' models
                for data in datas:
                    for i, j in ffields.iteritems():
                        model = None
                        if (hasattr(j, 'model_name') and
                                j.model_name in
                                self._model.pool.object_name_list()):
                            model = self._model.pool.get(j.model_name)
                        elif hasattr(j, 'get_target'):
                            model = j.get_target(self._model.pool)
                        if model and j._type in ('many2one', 'one2one'):
                            if (not data[i]
                                    and not (isinstance(data[i], (int, long))
                                        and not isinstance(data[i],
                                            type(False)))):
                                data[i] = BrowseRecordNull()
                            else:
                                _datetime = None
                                if (hasattr(j, 'datetime_field')
                                        and j.datetime_field):
                                    _datetime = data[j.datetime_field]
                                with Transaction().set_context(
                                        _datetime=_datetime):
                                    data[i] = BrowseRecord(data[i], model,
                                            local_cache=self._local_cache)
                        elif (model
                                and j._type in ('one2many', 'many2many')
                                and len(data[i])):
                            _datetime = None
                            if hasattr(j, 'datetime_field') and j.datetime_field:
                                _datetime = data[j.datetime_field]
                            with Transaction().set_context(
                                    _datetime=_datetime):
                                data[i] = BrowseRecordList(BrowseRecord(
                                    x, model, local_cache=self._local_cache)
                                    for x in data[i])
                        if (isinstance(j, fields.Function)
                                or isinstance(data[i], (BrowseRecord,
                                        BrowseRecordList))):
                            self._local_data.setdefault(data['id'], {})[i] = data[i]
                            del data[i]
                    self._data[data['id']].update(data)
        if name in self._local_data[self._id]:
            return self._local_data[self._id][name]
        return self._data[self._id][name]

    def __getattr__(self, name):
        # TODO raise an AttributeError exception
        return self[name]

    def __contains__(self, name):
        return (name in self._model._columns) \
                or (name in self._model._inherit_fields) \
                or hasattr(self._model, name)

    def __hasattr__(self, name):
        return name in self

    def __int__(self):
        return self._id

    def __str__(self):
        return "BrowseRecord(%s, %d)" % (self._model_name, self._id)

    def __eq__(self, other):
        return (self._model_name, self._id) == (other._model_name, other._id)

    def __ne__(self, other):
        return (self._model_name, self._id) != (other._model_name, other._id)

    # we need to define __unicode__ even though we've already defined __str__
    # because we have overridden __getattr__
    def __unicode__(self):
        return unicode(str(self))

    def __hash__(self):
        return hash((self._model_name, self._id))

    def __nonzero__(self):
        return True

    __repr__ = __str__

    def setLang(self, lang):
        self._context = self._context.copy()
        prev_lang = self._context.get('language') or 'en_US'
        self._context['language'] = lang
        for cache in (self._cache, {self._model_name: self._local_data}):
            language_cache = cache['_language_cache']
            for model in cache:
                if model == '_language_cache':
                    continue
                for record_id in cache[model]:
                    language_cache.setdefault(prev_lang,
                            {}).setdefault(model, {})[record_id] = \
                                    cache[model][record_id]
                    if lang in language_cache \
                            and model in language_cache[lang] \
                            and record_id in language_cache[lang][model]:
                        cache[model][record_id] = \
                                language_cache[lang][model][record_id]
                    else:
                        cache[model][record_id] = {'id': record_id}

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

    def __init__(self, record, model):
        super(EvalEnvironment, self).__init__()
        self._record = record
        self._model = model

    def __getitem__(self, item):
        if item.startswith('_parent_'):
            field = item[8:]
            if field in self._model._columns:
                model_name = self._model._columns[field].model_name
            else:
                model_name = self._model._inherit_fields[field][2].model_name
            model = self._model.pool.get(model_name)
            return EvalEnvironment(self._record[field], model)
        if item in self._model._columns \
                or item in self._model._inherit_fields:
            return self._record.get_eval(item)
        return super(EvalEnvironment, self).__getitem__(item)

    def __getattr__(self, item):
        return self.__getitem__(item)

    def get(self, item, default=None):
        try:
            return self.__getitem__(item)
        except Exception:
            pass
        return super(EvalEnvironment, self).get(item, default)

    def __nonzero__(self):
        return bool(self._record)
