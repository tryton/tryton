#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import contextlib
from itertools import islice, ifilter, ifilterfalse, chain
from trytond.model import fields
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.cache import LRUDict
from trytond.const import MODEL_CACHE_SIZE, RECORD_CACHE_SIZE, \
        BROWSE_FIELD_TRESHOLD


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

    def __init__(self, record_id, model, ids, local_cache):
        assert isinstance(ids, list)
        if ids:
            assert record_id in ids
        self._cursor = Transaction().cursor
        self._user = Transaction().user
        self.id = record_id
        self._model = model
        self._model_name = self._model._name
        self._context = Transaction().context
        self._pool = Pool()
        self._ids = ids

        cache = self._cursor.get_cache(self._context)
        if model._name not in cache:
            cache[model._name] = LRUDict(RECORD_CACHE_SIZE)
        self._data = cache[model._name]
        self._cache = cache
        assert isinstance(local_cache, LRUDict)
        self._local_data = local_cache

    def __getitem__(self, name):
        # Access to LRUDict must be atomic
        result = self._local_data.get(self.id, {}).get(name)
        if (self.id in self._local_data
                and name in self._local_data[self.id]):
            return result
        result = self._data.get(self.id, {}).get(name)
        if self.id in self._data and name in self._data[self.id]:
            return result

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

        ffields = {}
        if col.loading == 'eager':
            field_access_obj = self._pool.get('ir.model.field.access')
            fread_accesses = {}
            for inherit_name in self._model._inherits:
                inherit_obj = self._pool.get(inherit_name)
                fread_accesses.update(field_access_obj.check(inherit_name,
                    inherit_obj._columns.keys(), 'read', access=True))
            fread_accesses.update(field_access_obj.check(self._model._name,
                self._model._columns.keys(), 'read', access=True))
            to_remove = set(x for x, y in fread_accesses.iteritems()
                    if not y and x != name)

            threshold = BROWSE_FIELD_TRESHOLD
            inherit_threshold = threshold - len(self._model._columns)

            def not_cached(item):
                fname, field = item
                return (fname not in self._data.get(self.id, {})
                    and fname not in self._local_data.get(self.id, {}))
            def to_load(item):
                fname, field = item
                return (field.loading == 'eager'
                    and fname not in to_remove)
            def overrided(item):
                fname, field = item
                return fname in self._model._columns

            if inherit_threshold > 0:
                ifields = ((fname, field)
                    for fname, (_, _, field) in
                    self._model._inherit_fields.iteritems())
                ifields = ifilterfalse(overrided,
                    ifilter(to_load,
                        ifilter(not_cached, ifields)))
                ifields = islice(ifields, 0, inherit_threshold)
                ffields.update(ifields)
                threshold -= inherit_threshold

            ifields = ifilter(to_load,
                ifilter(not_cached,
                    self._model._columns.iteritems()))
            ifields = islice(ifields, 0, threshold)
            ffields.update(ifields)

        ffields[name] = col

        # add datetime_field
        for field in ffields.values():
            if hasattr(field, 'datetime_field') and field.datetime_field:
                if field.datetime_field in self._model._columns:
                    datetime_field = self._model._columns[field.datetime_field]
                else:
                    datetime_field = self._model._inherit_fields[
                            field.datetime_field][2]
                ffields[field.datetime_field] = datetime_field

        def filter_(id_):
            if (id_ in self._local_data
                    and name in self._local_data[id_]):
                return False
            if id_ in self._data and name in self._data[id_]:
                return False
            return True
        index = self._ids.index(self.id)
        ids = chain(islice(self._ids, index, None),
            islice(self._ids, 0, max(index - 1, 0)))
        ids = list(islice(ifilter(filter_, ids), self._cursor.IN_MAX))
        model2ids = {}
        model2cache = {}
        # read the data
        with contextlib.nested(Transaction().set_cursor(self._cursor),
                Transaction().set_user(self._user),
                Transaction().set_context(self._context)):
            # create browse records for 'remote' models
            for data in self._model.read(ids, ffields.keys()):
                for i, j in ffields.iteritems():
                    model = None
                    if (hasattr(j, 'model_name') and
                            j.model_name in
                            self._pool.object_name_list()):
                        model = self._pool.get(j.model_name)
                    elif hasattr(j, 'get_target'):
                        model = j.get_target()
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
                                ids = model2ids.setdefault(model, [])
                                ids.append(data[i])
                                local_cache = model2cache.setdefault(model,
                                    LRUDict(RECORD_CACHE_SIZE))
                                data[i] = BrowseRecord(data[i], model,
                                    ids, local_cache)
                    elif (model
                            and j._type in ('one2many', 'many2many')
                            and len(data[i])):
                        _datetime = None
                        if hasattr(j, 'datetime_field') and j.datetime_field:
                            _datetime = data[j.datetime_field]
                        with Transaction().set_context(
                                _datetime=_datetime):
                            ids = model2ids.setdefault(model, [])
                            ids.extend(data[i])
                            local_cache = model2cache.setdefault(model,
                                LRUDict(RECORD_CACHE_SIZE))
                            data[i] = BrowseRecordList(
                                BrowseRecord(x, model, ids, local_cache)
                                for x in data[i])
                    if (isinstance(j, fields.Function)
                            or isinstance(data[i], (BrowseRecord,
                                    BrowseRecordList))):
                        if data['id'] == self.id and i == name:
                            result = data[i]
                        self._local_data.setdefault(data['id'], {})[i] = data[i]
                        del data[i]
                self._data.setdefault(data['id'], {}).update(data)
                if data['id'] == self.id and name in data:
                    result = data[name]
        return result

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
        return self.id

    def __str__(self):
        return "BrowseRecord(%s, %d)" % (self._model_name, self.id)

    def __eq__(self, other):
        if not isinstance(other, BrowseRecord):
            return False
        return (self._model_name, self.id) == (other._model_name, other.id)

    def __ne__(self, other):
        if not isinstance(other, BrowseRecord):
            return True
        return (self._model_name, self.id) != (other._model_name, other.id)

    # we need to define __unicode__ even though we've already defined __str__
    # because we have overridden __getattr__
    def __unicode__(self):
        return unicode(str(self))

    def __hash__(self):
        return hash((self._model_name, self.id))

    def __nonzero__(self):
        return True

    __repr__ = __str__

    def setLang(self, lang):
        self._context = self._context.copy()
        prev_lang = self._context.get('language') or 'en_US'
        self._context['language'] = lang
        for cache in (self._cache, {self._model_name: self._local_data}):
            language_cache = cache.setdefault('_language_cache', {})
            for model in cache:
                if model == '_language_cache':
                    continue
                for record_id in cache[model]:
                    language_cache.setdefault(prev_lang,
                        LRUDict(MODEL_CACHE_SIZE)).setdefault(model,
                            LRUDict(RECORD_CACHE_SIZE))[record_id] = \
                            cache[model][record_id]
                    if lang in language_cache \
                            and model in language_cache[lang] \
                            and record_id in language_cache[lang][model]:
                        cache[model][record_id] = \
                                language_cache[lang][model][record_id]
                    else:
                        cache[model][record_id] = {}

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
        self._pool = Pool()

    def __getitem__(self, item):
        if item.startswith('_parent_'):
            field = item[8:]
            if field in self._model._columns:
                model_name = self._model._columns[field].model_name
            else:
                model_name = self._model._inherit_fields[field][2].model_name
            model = self._pool.get(model_name)
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
