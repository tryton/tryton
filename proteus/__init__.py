#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
'''
A library to access Tryton's models like a client.
'''
__version__ = "0.0.1"
from types import NoneType
import threading
import datetime
from decimal import Decimal
import proteus.config
from proteus.pyson import PYSONDecoder

_MODELS = threading.local()

class _EvalEnvironment(dict):
    'Dictionary for evaluation'
    def __init__(self, parent):
        super(_EvalEnvironment, self).__init__()
        self.parent = parent

    def __getitem__(self, item):
        if item == '_parent_' + self.parent.parent_field_name \
                and self.parent.parent:
            return _EvalEnvironment(self.parent.parent)
        return self.parent._get_eval()[item]

    def __getattr__(self, item):
        return self.__getitem__(item)

    def get(self, item, default=None):
        try:
            return self.__getattr__(item)
        except:
            pass
        return super(_EvalEnvironment, self).get(item, default)

    def __nonzero__(self):
        return True

    def __str__(self):
        return str(self.parent)

    __repr__ = __str__

    def __contains__(self, item):
        return item in self.parent._fields

def _getmethod(name, definition):
    def getmethod(self):
        if self.id > 0 and name not in self._values:
            self._read(name)
        if definition['type'] == 'many2one':
            if isinstance(self._values.get(name), (int, long)) \
                    and self._values.get(name) is not False:
                relation = Model.get(definition['relation'], self._config)
                self._values[name] = relation(self._values.get(name))
            elif not self._values.get(name):
                self._values[name] = None
        elif definition['type'] in ('one2many', 'many2many'):
            relation = Model.get(definition['relation'], self._config)
            if not isinstance(self._values.get(name), ModelList):
                self._values[name] = ModelList((relation(id) for id
                        in self._values.get(name) or []), self, name)
                for record in self._values[name]:
                    record._parent = self
                    record._parent_field_name = name
        elif definition['type'] == 'date':
            if isinstance(self._values.get(name), datetime.datetime):
                self._values[name] = self._values.get(name).date()
        elif definition['type'] == 'reference':
            if isinstance(self._values.get(name), basestring):
                ref_model, ref_id = self._values[name].split(',', 1)
                if ref_model:
                    relation = Model.get(ref_model, self._config)
                    self._values[name] = relation(int(ref_id))
            elif not self._values.get(name):
                self._values[name] = None
        return self._values.get(name)
    return getmethod

def _setmethod(name, definition):
    def set_method(self, value):
        assert definition['type'] not in ('one2many', 'many2many')

        if definition['type'] in ('many2one'):
            assert isinstance(value, (Model, NoneType))
            if value:
                assert value.id > 0 and not value._changed
                assert value._config == self._config
        elif definition['type'] == 'datetime':
            assert isinstance(value, datetime.datetime)
        elif definition['type'] == 'date':
            assert isinstance(value, datetime.date)
        elif definition['type'] == 'reference':
            assert isinstance(value, (Model, NoneType, basestring))
            if isinstance(value, basestring):
                assert value.startswith(',')
            elif isinstance(value, Model):
                assert value.id > 0 and not value._changed
                assert value._config == self._config
        elif definition['type'] in ('char', 'sha', 'selection'):
            assert isinstance(value, basestring)
        elif definition['type'] in ('float_time', 'float'):
            assert isinstance(value, float)
        elif definition['type'] in ('integer', 'biginteger'):
            assert isinstance(value, (int, long))
        elif definition['type'] == 'numeric':
            assert isinstance(value, Decimal)
        elif definition['type'] == 'boolean':
            assert isinstance(value, bool)

        if self.id > 0 and name not in self._values:
            self._read(name)
        previous = getattr(self, name)
        self._values[name] = value
        if previous != getattr(self, name):
            self._changed.add(name)
            self._on_change(name)
            if self._parent:
                self._parent._changed.add(self._parent_field_name)
                self._parent._on_change(self._parent_field_name)
    return set_method

class MetaModelFactory(object):
    def __init__(self, model_name, config=None):
        super(MetaModelFactory, self).__init__()
        self.model_name = model_name
        self.config = config or proteus.config.get_config()

    def __call__(self):
        models_key = 'c%s' % id(self.config)
        if not hasattr(_MODELS, models_key):
            setattr(_MODELS, models_key, {})
        class MetaModel(type):
            'Meta class for Model'
            def __new__(mcs, name, bases, dict):
                if self.model_name in getattr(_MODELS, models_key):
                    return getattr(_MODELS, models_key)[self.model_name]
                proxy = self.config.get_proxy(self.model_name)
                context = self.config.context
                name = self.model_name
                dict['_proxy'] = proxy
                dict['_config'] = self.config
                dict['_fields'] = proxy.fields_get(None, context)
                for field_name, definition in dict['_fields'].iteritems():
                    if field_name == 'id':
                        continue
                    dict[field_name] = property(_getmethod(field_name,
                        definition), _setmethod(field_name, definition))
                for method in self.config.get_proxy_methods(self.model_name):
                    setattr(mcs, method, getattr(proxy, method))
                res = type.__new__(mcs, name, bases, dict)
                getattr(_MODELS, models_key)[self.model_name] = res
                return res
            __new__.__doc__ = type.__new__.__doc__
        return MetaModel


class ModelList(list):
    'List for Model'

    def __init__(self, sequence=None, parent=None, parent_field_name=None):
        if sequence is None:
            sequence = []
        self.parent = parent
        self.parent_field_name = parent_field_name
        if parent:
            assert parent_field_name
        self.record_removed = set()
        self.record_deleted = set()
        return super(ModelList, self).__init__(sequence)
    __init__.__doc__ = list.__init__.__doc__

    def _changed(self):
        'Signal change to parent'
        if self.parent:
            self.parent._changed.add(self.parent_field_name)
            self.parent._on_change(self.parent_field_name)

    def append(self, record):
        assert isinstance(record, Model)
        if self.parent:
            assert record._config == self.parent._config
        elif self:
            assert record._config == self[0]._config
        assert record._parent is None
        assert record._parent_field_name is None
        record._parent = self.parent
        record._parent_field_name = self.parent_field_name
        res = super(ModelList, self).append(record)
        self._changed()
        return res
    append.__doc__ = list.append.__doc__

    def extend(self, iterable):
        iterable = list(iterable)
        config = None
        for record in iterable:
            assert isinstance(record, Model)
            if self.parent:
                assert record._config == self.parent._config
            elif self:
                assert record._config == self[0]._config
            elif config:
                assert record._config == config
            else:
                config = record._config
        for record in iterable:
            assert record._parent is None
            assert record._parent_field_name is None
            record._parent = self.parent
            record._parent_field_name = self.parent_field_name
        res = super(ModelList, self).extend(iterable)
        self._changed()
        return res
    extend.__doc__ = list.extend.__doc__

    def insert(self, index, record):
        raise NotImplementedError
    insert.__doc__ = list.insert.__doc__

    def pop(self, index=-1):
        self.record_removed.add(self[index])
        self[index]._parent = None
        self[index]._parent_field_name = None
        res = super(ModelList, self).pop(index)
        self._changed()
        return res
    pop.__doc__ = list.pop.__doc__

    def remove(self, record):
        self.record_deleted.add(record)
        record._parent = None
        record._parent_field_name = None
        res = super(ModelList, self).remove(record)
        self._changed()
        return res
    remove.__doc__ = list.remove.__doc__

    def reverse(self):
        raise NotImplementedError
    reverse.__doc__ = list.reverse.__doc__

    def sort(self):
        raise NotImplementedError
    sort.__doc__ = list.sort.__doc__


class Model(object):
    'Model class for Tryton records'

    __counter = -1
    _proxy = None
    _config = None
    _fields = None

    def __init__(self, id=None, **kwargs):
        super(Model, self).__init__()
        self.__id = id or Model.__counter
        if self.__id < 0:
            Model.__counter -= 1
        self._values = {} # store the values of fields
        self._changed = set() # store the changed fields
        self._parent = None # store the parent record
        self._parent_field_name = None # store the field name in parent record
        if self.id < 0:
            self._default_get()

        for field_name, value in kwargs.iteritems():
            definition = self._fields[field_name]
            if definition['type'] in ('one2many', 'many2many'):
                getattr(self, field_name).extend(value)
            else:
                setattr(self, field_name, value)
    __init__.__doc__ = object.__init__.__doc__

    @classmethod
    def get(cls, name, config=None):
        'Get a class for the named Model'
        class Spam(Model):
            __metaclass__ = MetaModelFactory(name, config=config)()
        return Spam

    def __str__(self):
        return '<%s(%d)>' % (self.__class__.__name__, self.id)
    __str__.__doc__ = object.__str__.__doc__

    def __repr__(self):
        if self._config == proteus.config.get_config():
            return "proteus.Model.get('%s')(%d)" % (self.__class__.__name__,
                    self.id)
        return "proteus.Model.get('%s', %s)(%d)" % (self.__class__.__name__,
                repr(self._config), self.id)
    __repr__.__doc__ = object.__repr__.__doc__

    def __cmp__(self, other):
        'Compare with other'
        if isinstance(other, Model):
            return cmp(self.id, other.id)
        if isinstance(other, (bool, NoneType)):
            return 1
        raise NotImplementedError

    @property
    def id(self):
        'The unique ID'
        return self.__id

    @classmethod
    def find(cls, condition=None):
        'Return records matching condition'
        if condition is None:
            condition = []
        ids = cls._proxy.search(condition, 0, None, None,
                cls._config.context)
        return [cls(id) for id in ids]

    def reload(self):
        'Reload record'
        self._values = {}
        self._changed = set()

    def save(self):
        'Save the record'
        context = self._config.context
        if self.id < 0:
            values = self._get_values()
            self.__id = self._proxy.create(values, context)
        else:
            if not self._changed:
                return
            values = self._get_values(fields=self._changed)
            context['_timestamp'] = self._get_timestamp()
            self._proxy.write(self.id, values, context)
        self.reload()

    def delete(self):
        'Delete the record'
        if self.id > 0:
            context = self._config.context
            context['_timestamp'] = self._get_timestamp()
            return self._proxy.delete(self.id, context)
        self.reload()
        return True

    def _get_values(self, fields=None):
        'Return dictionary values'
        if fields is None:
            fields = self._values.keys()
        values = {}
        for field_name in fields:
            if field_name == '_timestamp':
                continue
            definition = self._fields[field_name]
            if definition['type'] == 'many2one':
                if getattr(self, field_name):
                    values[field_name] = getattr(self, field_name).id
                else:
                    values[field_name] = False
            elif definition['type'] in ('one2many', 'many2many'):
                values[field_name] = [('add', [])]
                for record in getattr(self, field_name):
                    if record.id > 0:
                        if record._changed:
                            values[field_name].append(('write', record.id,
                                record._get_values()))
                        else:
                            values[field_name][0][1].append(record.id)
                    else:
                        values[field_name].append(('create',
                            record._get_values()))
                if getattr(self, field_name).record_removed:
                    values[field_name].append(('unlink', [x.id for x
                        in getattr(self, field_name).record_removed]))
                if getattr(self, field_name).record_deleted:
                    values[field_name].append(('delete', [x.id for x
                        in getattr(self, field_name).record_deleted]))
            elif definition['type'] == 'reference' \
                    and isinstance(getattr(self, field_name), Model):
                record = getattr(self, field_name)
                values[field_name] = '%s,%s' % (record.__class__.__name__,
                        record.id)
            else:
                values[field_name] = getattr(self, field_name)
        return values

    @property
    def _timestamp(self):
        'Get _timestamp'
        return self._values.get('_timestamp')

    def _get_timestamp(self):
        'Return dictionary with timestamps'
        result = {'%s,%s' % (self.__class__.__name__, self.id):
                self._timestamp}
        for field, definition in self._fields.iteritems():
            if field not in self._values:
                continue
            if definition['type'] in ('one2many', 'many2many'):
                for record in getattr(self, field):
                    result.update(record._get_timestamp())
        return result

    def _read(self, name):
        'Read field'
        fields = []
        if not self._values:
            fields = [x for x, y in self._fields.iteritems()
                    if y['type'] not in ('one2many', 'many2many', 'binary')]
            fields.append('_timestamp')
        fields.append(name)
        self._values.update(self._proxy.read(self.id, fields,
            self._config.context))

    def _default_get(self):
        'Set default values'
        fields = self._fields.keys()
        self._default_set(self._proxy.default_get(fields, False,
            self._config.context))

    def _default_set(self, values):
        for field, value in values.iteritems():
            definition = self._fields[field]
            if definition['type'] in ('one2many', 'many2many'):
                if value and len(value) and isinstance(value[0], (int, long)):
                    self._values[field] = value
                    continue
                relation = Model.get(definition['relation'], self._config)
                records = []
                for vals in (value or []):
                    record = relation()
                    record._default_set(vals)
                    record._parent = self
                    record._parent_field_name = field
                    records.append(record)
                self._values[field] = ModelList(records, self, field)
            else:
                self._values[field] = value

    def _get_eval(self):
        values = {}
        for field, definition in self._fields.iteritems():
            if definition['type'] in ('one2many', 'many2many'):
                values[field] = [x.id for x in getattr(self, field) or []]
            elif definition['type'] == 'many2one':
                if getattr(self, field):
                    values[field] = getattr(self, field).id
                else:
                    values[field] = False
            elif definition['type'] == 'reference':
                if isinstance(getattr(self, field), Model):
                    record = getattr(self, field)
                    values[field] = '%s,%s' % (record.__class__.__name__,
                            record.id)
                else:
                    values[field] = getattr(self, field) or False
            else:
                values[field] = getattr(self, field)
        values['id'] = self.id
        return values

    def _on_change_args(self, args):
        res = {}
        values = self._get_eval()
        del values['id']
        for field, definition in self._fields.iteritems():
            if definition['type'] in ('one2many', 'many2many'):
                values[field] = [x._get_eval() for x in getattr(self, field)]
        if self._parent:
            values['_parent_%s' % self._parent_field_name] = \
                    _EvalEnvironment(self._parent)
        for arg in args:
            scope = values
            for i in arg.split('.'):
                if i not in scope:
                    scope = False
                    break
                scope = scope[i]
            res[arg] = scope
        return res

    def _set_on_change(self, field, value):
        if self._fields[field]['type'] in ('one2many', 'many2many'):
            if isinstance(value, (list, tuple)):
                self._values[field] = value
                self._changed.add(field)
                return
            to_remove = []
            if value and value.get('remove'):
                for record_id in value['remove']:
                    for record in getattr(self, field):
                        if record.id == record_id:
                            to_remove.append(record)
            for record in to_remove:
                # remove without signal
                list.remove(getattr(self, field), record)
            if value and value.get('add') or value.get('update'):
                for vals in value.get('add', []):
                    relation = Model.get(self._fields[field]['relation'],
                            self._config)
                    # append without signal
                    list.append(getattr(self, field), relation(*vals))
                for vals in value.get('update', []):
                    if 'id' not in vals:
                        continue
                    for record in getattr(self, field):
                        if record.id == vals['id']:
                            for i, j in vals.iteritems:
                                record._values[i] = j
                                record._changed.add(i)
        else:
            self._values[field] = value
            self._changed.add(field)

    def _on_change(self, name):
        'Call on_change for field'
        definition = self._fields[name]
        if definition.get('on_change'):
            if isinstance(definition['on_change'], basestring):
                definition['on_change'] = PYSONDecoder().decode(
                        definition['on_change'])
            args = self._on_change_args(definition['on_change'])
            context = self._config.context
            res = getattr(self._proxy, 'on_change_%s' % name)(args, context)
            later = {}
            for field, value in res.iteritems():
                if field not in self._fields:
                    continue
                if self._fields[field]['type'] in ('one2many', 'many2many'):
                    later[field] = value
                    continue
                self._set_on_change(field, value)
            for field, value in later.iteritems():
                self._set_on_change(field, value)
            if self._parent:
                self._parent._changed.add(self._parent_field_name)
        if definition.get('change_default'):
            context = self._config.context
            default = Model.get('ir.default', config=self._config)
            self._default_set(default.get_default(self.__class__.__name__,
                '%s=%s' % (name, self._get_values([name])[name]), context))
        for field, definition in self._fields.iteritems():
            if not definition.get('on_change_with'):
                continue
            if name not in definition['on_change_with']:
                continue
            if field == name:
                continue
            args = self._on_change_args(definition['on_change_with'])
            context = self._config.context
            res = getattr(self._proxy, 'on_change_with_%s' % field)(args,
                    context)
            self._set_on_change(field, res)
