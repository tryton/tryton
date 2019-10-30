# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import copy
from collections import defaultdict
from functools import total_ordering

from trytond.i18n import lazy_gettext
from trytond.model import fields
from trytond.pool import Pool, PoolBase, PoolMeta
from trytond.pyson import PYSONEncoder, PYSONDecoder
from trytond.transaction import Transaction
from trytond.url import URLMixin
from trytond.rpc import RPC

__all__ = ['Model']


class ModelMeta(PoolMeta):
    @property
    def __queue__(self):
        pool = Pool()
        Queue = pool.get('ir.queue')
        return Queue.caller(self)


@total_ordering
class Model(URLMixin, PoolBase, metaclass=ModelMeta):
    """
    Define a model in Tryton.
    """
    __slots__ = ('_id', '_values', '_init_values')
    _rec_name = 'name'

    id = fields.Integer(lazy_gettext('ir.msg_ID'), readonly=True)

    @classmethod
    def __setup__(cls):
        super(Model, cls).__setup__()
        cls.__rpc__ = {
            'default_get': RPC(cache=dict(seconds=5 * 60)),
            'fields_get': RPC(cache=dict(days=1)),
            'pre_validate': RPC(instantiate=0),
            }

        # Copy fields and update depends
        for attr in dir(cls):
            if attr.startswith('_'):
                continue
            if not isinstance(getattr(cls, attr), fields.Field):
                continue
            field_name = attr
            field = getattr(cls, field_name)
            # Copy the original field definition to prevent side-effect with
            # the mutable attributes
            for parent_cls in cls.__mro__:
                parent_field = getattr(parent_cls, field_name, None)
                if isinstance(parent_field, fields.Field):
                    field = parent_field
            field = copy.deepcopy(field)
            setattr(cls, field_name, field)

    @classmethod
    def __post_setup__(cls):
        super(Model, cls).__post_setup__()

        # Set _fields
        cls._fields = {}
        for attr in dir(cls):
            if attr.startswith('_'):
                continue
            if isinstance(getattr(cls, attr), fields.Field):
                cls._fields[attr] = getattr(cls, attr)

        # Set _defaults
        cls._defaults = {}
        fields_names = list(cls._fields.keys())
        for field_name in fields_names:
            default_method = getattr(cls, 'default_%s' % field_name, False)
            if callable(default_method):
                cls._defaults[field_name] = default_method

        for k in cls._defaults:
            assert k in cls._fields, \
                'Default function defined in %s but field %s does not exist!' \
                % (cls.__name__, k,)

        # Set name to fields
        for name, field in cls._fields.items():
            if field.name is None:
                field.name = name
            else:
                assert field.name == name, (
                    'Duplicate fields on %s: %s, %s'
                    % (cls, field.name, name))

    @classmethod
    def _get_name(cls):
        '''
        Returns the first non-empty line of the model docstring.
        '''
        assert cls.__doc__, '%s has no docstring' % cls
        lines = cls.__doc__.splitlines()
        for line in lines:
            line = line.strip()
            if line:
                return line

    @classmethod
    def __register__(cls, module_name):
        """
        Add model in ir.model and ir.model.field.
        """
        super(Model, cls).__register__(module_name)
        pool = Pool()
        Translation = pool.get('ir.translation')
        Model_ = pool.get('ir.model')
        ModelField = pool.get('ir.model.field')

        model_id = Model_.register(cls, module_name)
        ModelField.register(cls, module_name, model_id)

        Translation.register_model(cls, module_name)
        Translation.register_fields(cls, module_name)

    @classmethod
    def default_get(cls, fields_names, with_rec_name=True):
        '''
        Return a dict with the default values for each field in fields_names.
        If with_rec_name is True, rec_name will be added.
        '''
        pool = Pool()
        value = {}

        default_rec_name = Transaction().context.get('default_rec_name')
        if (default_rec_name
                and cls._rec_name in cls._fields
                and cls._rec_name in fields_names):
            value[cls._rec_name] = default_rec_name

        # get the default values defined in the object
        for field_name in fields_names:
            if field_name in cls._defaults:
                value[field_name] = cls._defaults[field_name]()
            field = cls._fields[field_name]
            if (field._type == 'boolean'
                    and field_name not in value):
                value[field_name] = False
            if (with_rec_name
                    and field._type in ('many2one',)
                    and value.get(field_name)):
                Target = pool.get(field.model_name)
                if 'rec_name' in Target._fields:
                    value.setdefault(
                        field_name + '.', {})['rec_name'] = Target(
                            value[field_name]).rec_name
        return value

    @classmethod
    def fields_get(cls, fields_names=None, level=0):
        """
        Return the definition of each field on the model.
        """
        definition = {}
        pool = Pool()
        Translation = pool.get('ir.translation')
        FieldAccess = pool.get('ir.model.field.access')
        ModelAccess = pool.get('ir.model.access')

        # Add translation to cache
        language = Transaction().language
        trans_args = []
        for fname, field in cls._fields.items():
            if fields_names and fname not in fields_names:
                continue
            trans_args.extend(field.definition_translations(cls, language))
        Translation.get_sources(trans_args)

        encoder = PYSONEncoder()
        decoder = PYSONDecoder(noeval=True)

        accesses = FieldAccess.get_access([cls.__name__])[cls.__name__]
        for fname, field in cls._fields.items():
            if fields_names and fname not in fields_names:
                continue
            definition[fname] = field.definition(cls, language)
            if not accesses.get(fname, {}).get('write', True):
                definition[fname]['readonly'] = True
                states = decoder.decode(definition[fname]['states'])
                states.pop('readonly', None)
                definition[fname]['states'] = encoder.encode(states)
            for right in ['create', 'delete']:
                definition[fname][right] = accesses.get(
                    fname, {}).get(right, True)
            if level > 0:
                relation = definition[fname].get('relation')
                if relation:
                    Relation = pool.get(relation)
                    relation_fields = Relation.fields_get(level=level - 1)
                    definition[fname]['relation_fields'] = relation_fields
                    for name, props in relation_fields.items():
                        # Convert selection into list
                        if isinstance(props.get('selection'), str):
                            change_with = props.get('selection_change_with')
                            if change_with:
                                selection = getattr(
                                    Relation(), props['selection'])()
                            else:
                                selection = getattr(
                                    Relation, props['selection'])()
                            props['selection'] = selection
                schema = definition[fname].get('schema_model')
                if schema:
                    Schema = pool.get(schema)
                    definition[fname]['relation_fields'] = (
                        Schema.get_relation_fields())

        for fname in list(definition.keys()):
            # filter out fields which aren't in the fields_names list
            if fields_names:
                if fname not in fields_names:
                    del definition[fname]
            elif not ModelAccess.check_relation(
                    cls.__name__, fname, mode='read'):
                del definition[fname]
        return definition

    def pre_validate(self):
        pass

    @classmethod
    def __names__(cls, field=None):
        pool = Pool()
        IrModel = pool.get('ir.model')
        IrModelField = pool.get('ir.model.field')

        names = {
            'model': IrModel.get_name(cls.__name__),
            }
        if field:
            names['field'] = IrModelField.get_name(cls.__name__, field)
        return names

    def __init__(self, id=None, **kwargs):
        super(Model, self).__init__()
        if id is not None:
            id = int(id)
        self._id = id
        if kwargs:
            self._values = {}
            parent_values = defaultdict(dict)
            has_context = {}
            for name, value in kwargs.items():
                if not name.startswith('_parent_'):
                    setattr(self, name, value)
                else:
                    name, field = name.split('.', 1)
                    name = name[len('_parent_'):]
                    parent_values[name][field] = value
                    value = parent_values[name]
                if getattr(self.__class__, name).context:
                    has_context[name] = value

            for name, value in parent_values.items():
                setattr(self, name, value)
            # Set field with context a second times
            # to ensure it was evaluated with all the fields
            for name, value in has_context.items():
                setattr(self, name, value)
            self._init_values = self._values.copy()
        else:
            self._values = None
            self._init_values = None

    def __getattr__(self, name):
        try:
            return self._values[name]
        except (KeyError, TypeError):
            raise AttributeError("'%s' Model has no attribute '%s': %s"
                % (self.__name__, name, self._values))

    def __contains__(self, name):
        return name in self._fields

    def __int__(self):
        return int(self.id)

    def __str__(self):
        return '%s,%s' % (self.__name__, self.id)

    def __repr__(self):
        if self.id is None or self.id < 0:
            return "Pool().get('%s')(**%s)" % (self.__name__,
                repr(self._default_values))
        else:
            return "Pool().get('%s')(%s)" % (self.__name__, self.id)

    def __eq__(self, other):
        if not isinstance(other, Model):
            return NotImplemented
        elif self.id is None or other.id is None:
            return id(self) == id(other)
        return (self.__name__, self.id) == (other.__name__, other.id)

    def __lt__(self, other):
        if not isinstance(other, Model) or self.__name__ != other.__name__:
            return NotImplemented
        return self.id < other.id

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash((self.__name__, self.id))

    def __bool__(self):
        return True

    @property
    def _default_values(self):
        """Return the values not stored.
        By default, the value of a field is its internal representation except:
            - for Many2One and One2One field: the id
            - for Reference field: the string model,id
            - for Many2Many: the list of ids
            - for One2Many: the list of `_default_values`
        """
        values = {}
        if self._values:
            for fname, value in self._values.items():
                field = self._fields[fname]
                if field._type in ('many2one', 'one2one', 'reference'):
                    if value:
                        if field._type == 'reference':
                            value = str(value)
                        else:
                            value = value.id
                elif field._type in ('one2many', 'many2many'):
                    if field._type == 'one2many':
                        value = [r._default_values for r in value]
                    else:
                        value = [r.id for r in value]
                values[fname] = value
        return values
