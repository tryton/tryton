# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
'''
A library to access Tryton's models like a client.
'''
__version__ = "3.8.2"
__all__ = ['Model', 'Wizard', 'Report']
import sys
try:
    import cdecimal
    # Use cdecimal globally
    if 'decimal' not in sys.modules:
        sys.modules['decimal'] = cdecimal
except ImportError:
    import decimal
    sys.modules['cdecimal'] = decimal
import threading
import datetime
import functools
from decimal import Decimal
from types import NoneType

import proteus.config

_MODELS = threading.local()


class _EvalEnvironment(dict):
    'Dictionary for evaluation'
    def __init__(self, parent, eval_type='eval'):
        super(_EvalEnvironment, self).__init__()
        self.parent = parent
        assert eval_type in ('eval', 'on_change')
        self.eval_type = eval_type

    def __getitem__(self, item):
        if item == '_parent_' + self.parent._parent_name \
                and self.parent._parent:
            return _EvalEnvironment(self.parent._parent,
                eval_type=self.eval_type)
        if self.eval_type == 'eval':
            return self.parent._get_eval()[item]
        else:
            return self.parent._get_on_change_values(fields=[item])[item]

    def __getattr__(self, item):
        try:
            return self.__getitem__(item)
        except KeyError:
            raise AttributeError(item)

    def get(self, item, default=None):
        try:
            return self.__getitem__(item)
        except KeyError:
            pass
        return super(_EvalEnvironment, self).get(item, default)

    def __nonzero__(self):
        return True

    def __str__(self):
        return str(self.parent)

    __repr__ = __str__

    def __contains__(self, item):
        if item == '_parent_' + self.parent._parent_name \
                and self.parent._parent:
            return True
        if self.eval_type == 'eval':
            return item in self.parent._get_eval()
        else:
            return item in self.parent._fields


class dualmethod(object):
    """Descriptor implementing combination of class and instance method

    When called on an instance, the class is passed as the first argument and a
    list with the instance as the second.
    When called on a class, the class itself is passed as the first argument.

    >>> class Example(object):
    ...     @dualmethod
    ...     def method(cls, instances):
    ...         print len(instances)
    ...
    >>> Example.method([Example()])
    1
    >>> Example().method()
    1
    """
    def __init__(self, func):
        self.func = func

    def __get__(self, instance, owner):

        @functools.wraps(self.func)
        def newfunc(*args, **kwargs):
            if instance:
                return self.func(owner, [instance], *args, **kwargs)
            else:
                return self.func(owner, *args, **kwargs)
        return newfunc


class FieldDescriptor(object):
    default = None

    def __init__(self, name, definition):
        super(FieldDescriptor, self).__init__()
        self.name = name
        self.definition = definition
        self.__doc__ = definition['string']

    def __get__(self, instance, owner):
        if instance.id > 0:
            instance._read(self.name)
        return instance._values.get(self.name, self.default)

    def __set__(self, instance, value):
        if instance.id > 0:
            instance._read(self.name)
        previous = getattr(instance, self.name)
        instance._values[self.name] = value
        if previous != getattr(instance, self.name):
            instance._changed.add(self.name)
            instance._on_change([self.name])
            if instance._parent:
                instance._parent._changed.add(instance._parent_field_name)
                instance._parent._on_change([instance._parent_field_name])


class BooleanDescriptor(FieldDescriptor):
    default = False

    def __set__(self, instance, value):
        assert isinstance(value, bool)
        super(BooleanDescriptor, self).__set__(instance, value)


class CharDescriptor(FieldDescriptor):
    default = None

    def __set__(self, instance, value):
        assert isinstance(value, basestring) or value is None
        super(CharDescriptor, self).__set__(instance, value or '')


class BinaryDescriptor(FieldDescriptor):
    default = None

    def __set__(self, instance, value):
        assert isinstance(value, (bytes, bytearray)) or value is None
        super(BinaryDescriptor, self).__set__(instance, value)


class IntegerDescriptor(FieldDescriptor):

    def __set__(self, instance, value):
        assert isinstance(value, (int, long, NoneType))
        super(IntegerDescriptor, self).__set__(instance, value)


class FloatDescriptor(FieldDescriptor):

    def __set__(self, instance, value):
        assert isinstance(value, (int, long, float, Decimal, NoneType))
        if value is not None:
            value = float(value)
        super(FloatDescriptor, self).__set__(instance, value)


class NumericDescriptor(FieldDescriptor):

    def __set__(self, instance, value):
        assert isinstance(value, (NoneType, Decimal))
        # TODO add digits validation
        super(NumericDescriptor, self).__set__(instance, value)


class ReferenceDescriptor(FieldDescriptor):
    def __get__(self, instance, owner):
        value = super(ReferenceDescriptor, self).__get__(instance, owner)
        if isinstance(value, basestring):
            model_name, id = value.split(',', 1)
            if model_name:
                relation = Model.get(model_name, instance._config)
                value = relation(int(id))
                instance._values[self.name] = value
        return value

    def __set__(self, instance, value):
        assert isinstance(value, (Model, NoneType, basestring))
        if isinstance(value, basestring):
            assert value.startswith(',')
        elif isinstance(value, Model):
            assert value._config == instance._config
        super(ReferenceDescriptor, self).__set__(instance, value)


class DateDescriptor(FieldDescriptor):
    def __get__(self, instance, owner):
        value = super(DateDescriptor, self).__get__(instance, owner)
        if isinstance(value, datetime.datetime):
            value = value.date()
            instance._values[self.name] = value
        return value

    def __set__(self, instance, value):
        assert isinstance(value, datetime.date) or value is None
        super(DateDescriptor, self).__set__(instance, value)


class DateTimeDescriptor(FieldDescriptor):
    def __set__(self, instance, value):
        assert isinstance(value, datetime.datetime) or value is None
        super(DateTimeDescriptor, self).__set__(instance, value)


class TimeDescriptor(FieldDescriptor):
    def __set__(self, instance, value):
        assert isinstance(value, datetime.time) or value is None
        super(TimeDescriptor, self).__set__(instance, value)


class TimeDeltaDescriptor(FieldDescriptor):
    def __set__(self, instance, value):
        assert isinstance(value, datetime.timedelta) or value is None
        super(TimeDeltaDescriptor, self).__set__(instance, value)


class DictDescriptor(FieldDescriptor):
    def __get__(self, instance, owner):
        value = super(DictDescriptor, self).__get__(instance, owner)
        if value:
            value = value.copy()
        return value

    def __set__(self, instance, value):
        assert isinstance(value, dict) or value is None
        super(DictDescriptor, self).__set__(instance, value)


class Many2OneDescriptor(FieldDescriptor):
    def __get__(self, instance, owner):
        relation = Model.get(self.definition['relation'], instance._config)
        value = super(Many2OneDescriptor, self).__get__(instance, owner)
        if isinstance(value, (int, long)):
            value = relation(value)
        if self.name in instance._values:
            instance._values[self.name] = value
        return value

    def __set__(self, instance, value):
        assert isinstance(value, (Model, NoneType))
        if value:
            assert value._config == instance._config
        super(Many2OneDescriptor, self).__set__(instance, value)


class One2OneDescriptor(Many2OneDescriptor):
    pass


class One2ManyDescriptor(FieldDescriptor):
    default = []

    def __get__(self, instance, owner):
        from .pyson import PYSONDecoder
        relation = Model.get(self.definition['relation'], instance._config)
        value = super(One2ManyDescriptor, self).__get__(instance, owner)
        if not isinstance(value, ModelList):
            ctx = instance._context.copy() if instance._context else {}
            if self.definition.get('context'):
                decoder = PYSONDecoder(_EvalEnvironment(instance))
                ctx.update(decoder.decode(self.definition.get('context')))
            with instance._config.set_context(ctx):
                value = ModelList(self.definition, (relation(id)
                        for id in value or []), instance, self.name)
            instance._values[self.name] = value
        return value

    def __set__(self, instance, value):
        raise AttributeError


class Many2ManyDescriptor(One2ManyDescriptor):
    pass


class ValueDescriptor(object):
    def __init__(self, name, definition):
        super(ValueDescriptor, self).__init__()
        self.name = name
        self.definition = definition

    def __get__(self, instance, owner):
        return getattr(instance, self.name)


class ReferenceValueDescriptor(ValueDescriptor):
    def __get__(self, instance, owner):
        value = super(ReferenceValueDescriptor, self).__get__(instance, owner)
        if isinstance(value, Model):
            value = '%s,%s' % (value.__class__.__name__, value.id)
        return value or None


class Many2OneValueDescriptor(ValueDescriptor):
    def __get__(self, instance, owner):
        value = super(Many2OneValueDescriptor, self).__get__(instance, owner)
        return value and value.id or None


class One2OneValueDescriptor(Many2OneValueDescriptor):
    pass


class One2ManyValueDescriptor(ValueDescriptor):
    def __get__(self, instance, owner):
        value = []
        value_list = getattr(instance, self.name)
        parent_name = self.definition.get('relation_field', '')
        to_add = []
        to_create = []
        to_write = []
        for record in value_list:
            if record.id >= 0:
                values = record._get_values(fields=record._changed)
                values.pop(parent_name, None)
                if record._changed and values:
                    to_write.extend(([record.id], values))
                to_add.append(record.id)
            else:
                values = record._get_values()
                values.pop(parent_name, None)
                to_create.append(values)
        if to_add:
            value.append(('add', to_add))
        if to_create:
            value.append(('create', to_create))
        if to_write:
            value.append(('write',) + tuple(to_write))
        if value_list.record_removed:
            value.append(('remove', [x.id for x in value_list.record_removed]))
        if value_list.record_deleted:
            value.append(('delete', [x.id for x in value_list.record_deleted]))
        return value


class Many2ManyValueDescriptor(One2ManyValueDescriptor):
    pass


class EvalDescriptor(object):
    def __init__(self, name, definition):
        super(EvalDescriptor, self).__init__()
        self.name = name
        self.definition = definition

    def __get__(self, instance, owner):
        return getattr(instance, self.name)


class ReferenceEvalDescriptor(EvalDescriptor):
    def __get__(self, instance, owner):
        value = super(ReferenceEvalDescriptor, self).__get__(instance, owner)
        if isinstance(value, Model):
            value = '%s,%s' % (value.__class__.__name__, value.id)
        return value or None


class Many2OneEvalDescriptor(EvalDescriptor):
    def __get__(self, instance, owner):
        value = super(Many2OneEvalDescriptor, self).__get__(instance, owner)
        if value:
            return value.id
        return None


class One2OneEvalDescriptor(Many2OneEvalDescriptor):
    pass


class One2ManyEvalDescriptor(EvalDescriptor):
    def __get__(self, instance, owner):
        # Directly use _values to prevent infinite recursion with
        # One2ManyDescriptor which could evaluate this field to decode the
        # context
        value = instance._values.get(self.name, [])
        if isinstance(value, ModelList):
            return [x.id for x in value]
        else:
            return value


class Many2ManyEvalDescriptor(One2ManyEvalDescriptor):
    pass


class MetaModelFactory(object):
    descriptors = {
        'boolean': BooleanDescriptor,
        'char': CharDescriptor,
        'text': CharDescriptor,
        'binary': BinaryDescriptor,
        'selection': CharDescriptor,  # TODO implement its own descriptor
        'integer': IntegerDescriptor,
        'biginteger': IntegerDescriptor,
        'float': FloatDescriptor,
        'numeric': NumericDescriptor,
        'reference': ReferenceDescriptor,
        'date': DateDescriptor,
        'datetime': DateTimeDescriptor,
        'timestamp': DateTimeDescriptor,
        'time': TimeDescriptor,
        'timedelta': TimeDeltaDescriptor,
        'dict': DictDescriptor,
        'many2one': Many2OneDescriptor,
        'one2many': One2ManyDescriptor,
        'many2many': Many2ManyDescriptor,
        'one2one': One2OneDescriptor,
    }
    value_descriptors = {
        'reference': ReferenceValueDescriptor,
        'many2one': Many2OneValueDescriptor,
        'one2many': One2ManyValueDescriptor,
        'many2many': Many2ManyValueDescriptor,
        'one2one': One2OneValueDescriptor,
    }
    eval_descriptors = {
        'reference': ReferenceEvalDescriptor,
        'many2one': Many2OneEvalDescriptor,
        'one2many': One2ManyEvalDescriptor,
        'many2many': Many2ManyEvalDescriptor,
        'one2one': One2OneEvalDescriptor,
    }

    def __init__(self, model_name, config=None):
        super(MetaModelFactory, self).__init__()
        self.model_name = model_name
        self.config = config or proteus.config.get_config()

    def __call__(self):
        models_key = 'c%su%s' % (id(self.config), self.config.user)
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
                    Descriptor = self.descriptors.get(definition['type'],
                        FieldDescriptor)
                    dict[field_name] = Descriptor(field_name, definition)
                    VDescriptor = self.value_descriptors.get(
                            definition['type'], ValueDescriptor)
                    dict['__%s_value' % field_name] = VDescriptor(
                            field_name, definition)
                    EDescriptor = self.eval_descriptors.get(
                            definition['type'], EvalDescriptor)
                    dict['__%s_eval' % field_name] = EDescriptor(
                            field_name, definition)
                for method in self.config.get_proxy_methods(self.model_name):
                    setattr(mcs, method, getattr(proxy, method))
                res = type.__new__(mcs, name, bases, dict)
                getattr(_MODELS, models_key)[self.model_name] = res
                return res
            __new__.__doc__ = type.__new__.__doc__
        return MetaModel


class ModelList(list):
    'List for Model'

    def __init__(self, definition, sequence=None, parent=None,
            parent_field_name=''):
        self.model_name = definition['relation']
        if sequence is None:
            sequence = []
        self.parent = parent
        if parent:
            assert parent_field_name
        self.parent_field_name = parent_field_name
        self.parent_name = definition.get('relation_field', '')
        self.domain = definition.get('domain', [])
        self.context = definition.get('context')
        self.add_remove = definition.get('add_remove')
        self.record_removed = set()
        self.record_deleted = set()
        result = super(ModelList, self).__init__(sequence)
        for record in self:
            record._parent = parent
            record._parent_field_name = parent_field_name
            record._parent_name = self.parent_name
        return result
    __init__.__doc__ = list.__init__.__doc__

    def _changed(self):
        'Signal change to parent'
        if self.parent:
            self.parent._changed.add(self.parent_field_name)
            self.parent._on_change([self.parent_field_name])

    def _get_context(self):
        from .pyson import PYSONDecoder
        decoder = PYSONDecoder(_EvalEnvironment(self.parent))
        ctx = self.parent._context.copy() if self.parent._context else {}
        ctx.update(decoder.decode(self.context) if self.context else {})
        return ctx

    def __check(self, records):
        config = None
        for record in records:
            assert isinstance(record, Model)
            if self.parent:
                assert record._config == self.parent._config
            elif self:
                assert record._config == self[0]._config
            elif config:
                assert record._config == config
            else:
                config = record._config
        for record in records:
            assert record._parent is None
            assert not record._parent_field_name
            assert not record._parent_name
            record._parent = self.parent
            record._parent_field_name = self.parent_field_name
            record._parent_name = self.parent_name

            # Set parent field to trigger on_change
            if self.parent and self.parent_name in record._fields:
                definition = record._fields[self.parent_name]
                if definition['type'] in ('many2one', 'reference'):
                    setattr(record, self.parent_name, self.parent)

    def append(self, record):
        self.__check([record])
        res = super(ModelList, self).append(record)
        self._changed()
        return res
    append.__doc__ = list.append.__doc__

    def extend(self, iterable):
        iterable = list(iterable)
        self.__check(iterable)
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
        self[index]._parent_field_name = ''
        self[index]._parent_name = ''
        res = super(ModelList, self).pop(index)
        self._changed()
        return res
    pop.__doc__ = list.pop.__doc__

    def remove(self, record, _changed=True):
        if record.id >= 0:
            self.record_deleted.add(record)
        record._parent = None
        record._parent_field_name = ''
        record._parent_name = ''
        res = super(ModelList, self).remove(record)
        if _changed:
            self._changed()
        return res
    remove.__doc__ = list.remove.__doc__

    def reverse(self):
        raise NotImplementedError
    reverse.__doc__ = list.reverse.__doc__

    def sort(self):
        raise NotImplementedError
    sort.__doc__ = list.sort.__doc__

    def new(self, **kwargs):
        'Adds a new record to the ModelList and returns it'
        Relation = Model.get(self.model_name, self.parent._config)
        with Relation._config.set_context(self._get_context()):
            new_record = Relation(**kwargs)
        self.append(new_record)
        return new_record

    def find(self, condition=None, offset=0, limit=None, order=None):
        'Returns records matching condition taking into account list domain'
        from .pyson import PYSONDecoder
        decoder = PYSONDecoder(_EvalEnvironment(self.parent))
        Relation = Model.get(self.model_name, self.parent._config)
        if condition is None:
            condition = []
        field_domain = decoder.decode(self.domain)
        add_remove_domain = (decoder.decode(self.add_remove)
            if self.add_remove else [])
        new_domain = [field_domain, add_remove_domain, condition]
        with Relation._config.set_context(self._get_context()):
            return Relation.find(new_domain, offset, limit, order)


class Model(object):
    'Model class for Tryton records'

    __counter = -1
    _proxy = None
    _config = None
    _fields = None

    def __init__(self, id=None, _default=True, **kwargs):
        super(Model, self).__init__()
        if id:
            assert not kwargs
        self.__id = id or Model.__counter
        if self.__id < 0:
            Model.__counter -= 1
        self._values = {}  # store the values of fields
        self._changed = set()  # store the changed fields
        self._parent = None  # store the parent record
        self._parent_field_name = ''  # store the field name in parent record
        self._parent_name = ''  # store the field name to parent record
        self._context = self._config.context  # store the context
        if self.id < 0 and _default:
            self._default_get()

        for field_name, value in kwargs.iteritems():
            definition = self._fields[field_name]
            if definition['type'] in ('one2many', 'many2many'):
                relation = Model.get(definition['relation'])
                value = [isinstance(x, (int, long)) and relation(x) or x
                        for x in value]
                getattr(self, field_name).extend(value)
            else:
                if definition['type'] == 'many2one':
                    if isinstance(value, (int, long)):
                        relation = Model.get(definition['relation'])
                        value = relation(value)
                setattr(self, field_name, value)
    __init__.__doc__ = object.__init__.__doc__

    @classmethod
    def get(cls, name, config=None):
        'Get a class for the named Model'
        if isinstance(name, unicode):
            name = name.encode('utf-8')

        class Spam(Model):
            __metaclass__ = MetaModelFactory(name, config=config)()
        return Spam

    @classmethod
    def reset(cls, config=None, *names):
        'Reset class definition for Models named'
        config = config or proteus.config.get_config()
        models_key = 'c%su%s' % (id(config), config.user)
        if not names:
            setattr(_MODELS, models_key, {})
        else:
            models = getattr(_MODELS, models_key, {})
            for name in names:
                del models[name]

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
            return cmp((self.__class__.__name__, self.id),
                (other.__class__.__name__, other.id))
        if isinstance(other, (bool, NoneType)):
            return 1
        raise NotImplementedError

    @property
    def id(self):
        'The unique ID'
        return self.__id

    @id.setter
    def id(self, value):
        assert self.__id < 0
        self.__id = int(value)

    @classmethod
    def find(cls, condition=None, offset=0, limit=None, order=None):
        'Return records matching condition'
        if condition is None:
            condition = []
        ids = cls._proxy.search(condition, offset, limit, order,
                cls._config.context)
        return [cls(id) for id in ids]

    @dualmethod
    def reload(cls, records):
        'Reload record'
        for record in records:
            record._values = {}
            record._changed = set()

    @dualmethod
    def save(cls, records):
        'Save records'
        if not records:
            return
        proxy = records[0]._proxy
        config = records[0]._config
        context = config.context
        create, write = [], []
        for record in records:
            assert proxy == record._proxy
            assert config == record._config
            if record.id < 0:
                create.append(record)
            elif record._changed:
                write.append(record)

        if create:
            values = [r._get_values() for r in create]
            ids = proxy.create(values, context)
            for record, id_ in zip(create, ids):
                record.id = id_
        if write:
            values = []
            context['_timestamp'] = {}
            for record in write:
                values.append([record.id])
                values.append(record._get_values(fields=record._changed))
                context['_timestamp'].update(record._get_timestamp())
            values.append(context)
            proxy.write(*values)
        for record in records:
            record.reload()

    @dualmethod
    def delete(cls, records):
        'Delete records'
        if not records:
            return
        proxy = records[0]._proxy
        config = records[0]._config
        context = config.context
        context['_timestamp'] = {}
        delete = []
        for record in records:
            assert proxy == record._proxy
            assert config == record._config
            if record.id > 0:
                context['_timestamp'].update(record._get_timestamp())
                delete.append(record.id)
        if delete:
            proxy.delete(delete, context)
        cls.reload(records)

    @dualmethod
    def duplicate(cls, records, default=None):
        'Duplicate the record'
        ids = cls._proxy.copy([r.id for r in records], default,
            cls._config.context)
        return [cls(id) for id in ids]

    @dualmethod
    def click(cls, records, button, change=None):
        'Click on button'
        if not records:
            return

        proxy = records[0]._proxy
        context = records[0]._config.context
        if change is None:
            cls.save(records)
            cls.reload(records)  # Force reload because save doesn't always
            return getattr(proxy, button)([r.id for r in records], context)
        else:
            record, = records
            values = record._on_change_args(change)
            changes = getattr(proxy, button)(values, context)
            record._set_on_change(changes)

    def _get_values(self, fields=None):
        'Return dictionary values'
        if fields is None:
            fields = self._values.keys()
        return dict((x, getattr(self, '__%s_value' % x)) for x in fields
                if x not in ('id', '_timestamp'))

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
        fields = [name]
        if name in self._values:
            return
        loading = self._fields[name]['loading']
        if loading == 'eager':
            fields = [x for x, y in self._fields.iteritems()
                    if y['loading'] == 'eager']
        if not self._fields:
            fields.append('_timestamp')
        self._values.update(self._proxy.read([self.id], fields,
            self._config.context)[0])
        for field in fields:
            if (field in self._fields
                    and self._fields[field]['type'] == 'float'
                    and isinstance(self._values[field], Decimal)):
                # XML-RPC return Decimal for double
                self._values[field] = float(self._values[field])

    def _default_get(self):
        'Set default values'
        fields = self._fields.keys()
        self._default_set(self._proxy.default_get(fields, False,
            self._config.context))

    def _default_set(self, values):
        fieldnames = []
        for field, value in values.iteritems():
            if '.' in field:
                continue
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
                    records.append(record)
                self._values[field] = ModelList(definition, records, self,
                    field)
            else:
                self._values[field] = value
            fieldnames.append(field)
        self._on_change(sorted(fieldnames))

    def _get_eval(self):
        values = dict((x, getattr(self, '__%s_eval' % x))
                for x in self._fields if x != 'id')
        values['id'] = self.id
        return values

    def _get_on_change_values(self, skip=None, fields=None):
        values = {'id': self.id}
        if fields:
            definitions = ((f, self._fields[f]) for f in fields)
        else:
            definitions = self._fields.iteritems()
        for field, definition in definitions:
            if not fields:
                if field == 'id' or (skip and field in skip):
                    continue
                if (self.id >= 0
                        and (field not in self._values
                            or field not in self._changed)):
                    continue
            if definition['type'] == 'one2many':
                values[field] = [x._get_on_change_values(
                        skip={definition.get('relation_field', '')})
                    for x in getattr(self, field)]
            elif (definition['type'] in ('many2one', 'reference')
                    and self._parent_name == definition['name']
                    and self._parent):
                values[field] = self._parent._get_on_change_values(
                    skip={self._parent_field_name})
                if definition['type'] == 'reference':
                    values[field] = (
                        self._parent.__class__.__name__, values[field])
            else:
                values[field] = getattr(self, '__%s_eval' % field)
        return values

    def _on_change_args(self, args):
        res = {}
        values = _EvalEnvironment(self, 'on_change')
        for arg in args:
            scope = values
            for i in arg.split('.'):
                if i not in scope:
                    break
                scope = scope[i]
            else:
                res[arg] = scope
        res['id'] = self.id
        return res

    def _on_change_set(self, field, value):
        if (self._fields[field]['type'] in ('one2many', 'many2many')
                and not isinstance(value, (list, tuple))):
            to_remove = []
            if value and value.get('remove'):
                for record_id in value['remove']:
                    for record in getattr(self, field):
                        if record.id == record_id:
                            to_remove.append(record)
            for record in to_remove:
                # remove without signal
                getattr(self, field).remove(record, _changed=False)
            if value and (value.get('add') or value.get('update')):
                for index, vals in value.get('add', []):
                    relation = Model.get(self._fields[field]['relation'],
                            self._config)
                    record = relation(_default=False)
                    record._set_on_change(vals)
                    # append without signal
                    if index == -1:
                        list.append(getattr(self, field), record)
                    else:
                        list.insert(getattr(self, field), index, record)
                for vals in value.get('update', []):
                    if 'id' not in vals:
                        continue
                    for record in getattr(self, field):
                        if record.id == vals['id']:
                            record._set_on_change(vals)
        elif (self._fields[field]['type'] in ('one2many', 'many2many')
                and len(value) and not isinstance(value[0], (int, long))):
            self._values[field] = []
            for vals in value:
                relation = Model.get(self._fields[field]['relation'],
                        self._config)
                record = relation(_default=False, **vals)
                getattr(self, field).append(record)
        else:
            self._values[field] = value
        self._changed.add(field)

    def _set_on_change(self, values):
        later = {}
        for field, value in values.iteritems():
            if field not in self._fields:
                continue
            if self._fields[field]['type'] in ('one2many', 'many2many'):
                later[field] = value
                continue
            self._on_change_set(field, value)
        for field, value in later.iteritems():
            self._on_change_set(field, value)

    def _on_change(self, names):
        'Call on_change for field'
        # Import locally to not break installation
        from proteus.pyson import PYSONDecoder

        values = {}
        for name in names:
            definition = self._fields[name]
            on_change = definition.get('on_change')
            if not on_change:
                continue
            if isinstance(on_change, basestring):
                definition['on_change'] = on_change = PYSONDecoder().decode(
                    on_change)
            values.update(self._on_change_args(on_change))
        if values:
            context = self._config.context
            changes = getattr(self._proxy, 'on_change')(values, names, context)
            for change in changes:
                self._set_on_change(change)

        values = {}
        fieldnames = set(names)
        to_change = set()
        later = set()
        for field, definition in self._fields.iteritems():
            on_change_with = definition.get('on_change_with')
            if not on_change_with:
                continue
            if not fieldnames & set(on_change_with):
                continue
            if to_change & set(on_change_with):
                later.add(field)
                continue
            to_change.add(field)
            values.update(self._on_change_args(on_change_with))
        if to_change:
            context = self._config.context
            changes = getattr(self._proxy, 'on_change_with')(values,
                list(to_change), context)
            self._set_on_change(changes)
        for field in later:
            on_change_with = self._fields[field]['on_change_with']
            values = self._on_change_args(on_change_with)
            context = self._config.context
            result = getattr(self._proxy, 'on_change_with_%s' % field)(values,
                    context)
            self._on_change_set(field, result)

        if self._parent:
            self._parent._changed.add(self._parent_field_name)
            self._parent._on_change([self._parent_field_name])


class Wizard(object):
    'Wizard class for Tryton wizards'

    def __init__(self, name, models=None, action=None, config=None,
            context=None):
        if models:
            assert len(set(type(x) for x in models)) == 1
        super(Wizard, self).__init__()
        self.name = name
        self.form = None
        self.form_state = None
        self.actions = []
        self._config = config or proteus.config.get_config()
        self._context = context or {}
        self._proxy = self._config.get_proxy(name, type='wizard')
        result = self._proxy.create(self._config.context)
        self.session_id, self.start_state, self.end_state = result
        self.states = [self.start_state]
        self.models = models
        self.action = action
        self.execute(self.start_state)

    def execute(self, state):
        assert state in self.states

        self.state = state
        while self.state != self.end_state:
            ctx = self._context.copy()
            ctx.update(self._config.context)
            if self.models:
                ctx['active_id'] = self.models[0].id
                ctx['active_ids'] = [model.id for model in self.models]
                ctx['active_model'] = self.models[0].__class__.__name__
            else:
                ctx['active_id'] = None
                ctx['active_ids'] = None
                ctx['active_model'] = None
            if self.action:
                ctx['action_id'] = self.action['id']
            else:
                ctx['action_id'] = None

            if self.form:
                # Filter only modified values
                data = {self.form_state:
                    dict((k, v) for k, v in
                        self.form._get_on_change_values().iteritems()
                        if k in self.form._values)}
            else:
                data = {}

            result = self._proxy.execute(self.session_id, data, self.state,
                ctx)

            if 'view' in result:
                view = result['view']
                self.form = Model.get(view['fields_view']['model'])()
                self.form._default_set(view['defaults'])
                self.states = [b['state'] for b in view['buttons']]
                self.form_state = view['state']
            else:
                self.state = self.end_state

            self.actions = []
            for action in result.get('actions', []):
                proteus_action = _convert_action(*action,
                    context=self._context)
                if proteus_action:
                    self.actions.append(proteus_action)

            if 'view' in result:
                return

        if self.state == self.end_state:
            self._proxy.delete(self.session_id, self._config.context)
            if self.models:
                for record in self.models:
                    record.reload()


class Report(object):
    'Report class for Tryton reports'

    def __init__(self, name, config=None, context=None):
        super(Report, self).__init__()
        self.name = name
        self._config = config or proteus.config.get_config()
        self._context = context or {}
        self._proxy = self._config.get_proxy(name, type='report')

    def execute(self, models=None, data=None):
        if data is None:
            data = {}
        ids = [m.id for m in models] if models else data.get('ids', [])
        return self._proxy.execute(ids, data, self._context)


def _convert_action(action, data=None, context=None, config=None):
    if config is None:
        config = proteus.config.get_config()
    if data is None:
        data = {}
    else:
        data = data.copy()

    if 'type' not in (action or {}):
        return None

    data['action_id'] = action['id']
    if action['type'] == 'ir.action.act_window':
        from .pyson import PYSONDecoder

        action.setdefault('pyson_domain', '[]')
        ctx = {
            'active_model': data.get('model'),
            'active_id': data.get('id'),
            'active_ids': data.get('ids', []),
        }
        ctx.update(config.context)
        ctx['_user'] = config.user
        decoder = PYSONDecoder(ctx)
        action_ctx = decoder.decode(action.get('pyson_context') or '{}')
        ctx.update(action_ctx)
        ctx.update(context)
        action_ctx.update(context)
        if 'date_format' not in action_ctx:
            action_ctx['date_format'] = config.context.get(
                'locale', {}).get('date', '%x')

        ctx['context'] = ctx
        decoder = PYSONDecoder(ctx)
        domain = decoder.decode(action['pyson_domain'])

        res_model = action.get('res_model', data.get('res_model'))
        res_id = action.get('res_id', data.get('res_id'))
        Model_ = Model.get(res_model)
        with config.set_context(action_ctx):
            if res_id is None:
                return Model_.find(domain)
            else:
                return [Model_(id_) for id_ in res_id]
    elif action['type'] == 'ir.action.wizard':
        kwargs = {
            'action': action,
            'config': config,
            'context': context,
            }
        if 'model' in data:
            Model_ = Model.get(data['model'])
            kwargs['models'] = [Model_(id_) for id_ in data.get('ids', [])]
        return Wizard(action['wiz_name'], **kwargs)
    elif action['type'] == 'ir.action.report':
        ActionReport = Report(action['report_name'], context=context)
        return ActionReport.execute(data=data)
    elif action['type'] == 'ir.action.url':
        return action.get('url')
