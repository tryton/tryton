#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import copy
import collections
import warnings

from trytond.model import fields
from trytond.error import WarningErrorMixin
from trytond.pool import Pool, PoolMeta
from trytond.pyson import PYSONEncoder
from trytond.transaction import Transaction
from trytond.url import URLMixin
from trytond.rpc import RPC

__all__ = ['Model']


class ModelMeta(PoolMeta):

    def __getattr__(self, name):
        pool = Pool()
        for model_name, _ in self._inherits.iteritems():
            Model = pool.get(model_name)
            if isinstance(getattr(Model, name, None),
                    collections.Callable):
                meth = getattr(Model, name)
                if not hasattr(meth, 'im_self') or meth.im_self:
                    # Return classmethod bounded to inherited class
                    return meth
                else:
                    for cls in Model.__mro__:
                        if name in cls.__dict__:
                            # Return a method bounded to current class
                            return cls.__dict__[name].__get__(None, self)
        raise AttributeError("'%s' Model has no attribute '%s'"
            % (self.__name__, name))


class Model(WarningErrorMixin, URLMixin):
    """
    Define a model in Tryton.
    """
    __metaclass__ = ModelMeta
    _inherits = {}
    _rec_name = 'name'

    id = fields.Integer('ID', readonly=True)

    @classmethod
    def __setup__(cls):
        cls.__rpc__ = {
            'default_get': RPC(),
            'fields_get': RPC(),
            'on_change_with': RPC(instantiate=0),
            'pre_validate': RPC(instantiate=0),
            }
        cls._error_messages = {}

        # Copy fields
        for attr in dir(cls):
            if attr.startswith('_'):
                continue
            if isinstance(getattr(cls, attr), fields.Field):
                setattr(cls, attr, copy.deepcopy(getattr(cls, attr)))

    @classmethod
    def __post_setup__(cls):
        pool = Pool()

        # Set _fields
        cls._fields = {}
        for attr in dir(cls):
            if attr.startswith('_'):
                continue
            if isinstance(getattr(cls, attr), fields.Field):
                cls._fields[attr] = getattr(cls, attr)

        # Set _inherit_fields
        cls._inherit_fields = {}
        for model_name in cls._inherits:
            Model = pool.get(model_name)
            cls._inherit_fields.update(Model._inherit_fields)
            for field_name in Model._fields.keys():
                cls._inherit_fields[field_name] = (model_name,
                    cls._inherits[model_name],
                    Model._fields[field_name])
            for field_name in Model._inherit_fields.keys():
                cls._inherit_fields[field_name] = (model_name,
                    cls._inherits[model_name],
                    Model._inherit_fields[field_name][2])
        # Update models that uses this one in _inherits
        for _, Model in pool.iterobject():
            if cls.__name__ in Model._inherits:
                Model.__post_setup__()

        # Set _defaults
        cls._defaults = {}
        fields_names = cls._fields.keys()
        fields_names += cls._inherit_fields.keys()
        for field_name in fields_names:
            default_method = getattr(cls, 'default_%s' % field_name, False)
            if not default_method and field_name in cls._inherit_fields:
                icls = pool.get(cls._inherit_fields[field_name][0])
                default_method = getattr(icls, 'default_%s' % field_name,
                    False)
            if isinstance(default_method, collections.Callable):
                cls._defaults[field_name] = default_method

        for k in cls._defaults:
            assert (k in cls._fields) or (k in cls._inherit_fields), \
                'Default function defined in %s but field %s does not exist!' \
                % (cls.__name__, k,)

        # Update __rpc__
        for field_name in cls._fields.keys() + cls._inherit_fields.keys():
            if field_name in cls._fields:
                field = cls._fields[field_name]
            else:
                field = cls._inherit_fields[field_name][2]
            if isinstance(field, (fields.Selection, fields.Reference)) \
                    and not isinstance(field.selection, (list, tuple)) \
                    and field.selection not in cls.__rpc__:
                cls.__rpc__[field.selection] = RPC()

            for attribute in ('on_change', 'on_change_with', 'autocomplete'):
                function_name = '%s_%s' % (attribute, field_name)
                if getattr(field, attribute, False):
                    cls.__rpc__.setdefault(function_name, RPC(instantiate=0))

        # Set name to fields
        for name, field in cls._fields.iteritems():
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
        pool = Pool()
        Translation = pool.get('ir.translation')
        Property = pool.get('ir.property')

        cursor = Transaction().cursor
        # Add model in ir_model
        cursor.execute("SELECT id FROM ir_model WHERE model = %s",
                (cls.__name__,))
        model_id = None
        if cursor.rowcount == -1 or cursor.rowcount is None:
            data = cursor.fetchone()
            if data:
                model_id, = data
        elif cursor.rowcount != 0:
            model_id, = cursor.fetchone()
        if not model_id:
            cursor.execute("INSERT INTO ir_model "
                "(model, name, info, module) VALUES (%s, %s, %s, %s)",
                (cls.__name__, cls._get_name(), cls.__doc__,
                    module_name))
            Property._models_get_cache.clear()
            cursor.execute("SELECT id FROM ir_model WHERE model = %s",
                    (cls.__name__,))
            (model_id,) = cursor.fetchone()
        elif cls.__doc__:
            cursor.execute('UPDATE ir_model '
                'SET name = %s, '
                    'info = %s '
                'WHERE id = %s',
                (cls._get_name(), cls.__doc__, model_id))

        # Update translation of model
        if cls.__doc__:
            name = cls.__name__ + ',name'
            src = cls._get_name()
            cursor.execute('SELECT id FROM ir_translation ' \
                    'WHERE lang = %s ' \
                        'AND type = %s ' \
                        'AND name = %s ' \
                        'AND (res_id IS NULL OR res_id = %s)',
                    ('en_US', 'model', name, 0))
            trans_id = None
            if cursor.rowcount == -1 or cursor.rowcount is None:
                data = cursor.fetchone()
                if data:
                    trans_id, = data
            elif cursor.rowcount != 0:
                trans_id, = cursor.fetchone()
            src_md5 = Translation.get_src_md5(src)
            if trans_id is None:
                cursor.execute('INSERT INTO ir_translation '
                    '(name, lang, type, src, src_md5, value, module, fuzzy) '
                    'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                    (name, 'en_US', 'model', src, src_md5, '', module_name,
                        False))
            else:
                cursor.execute('UPDATE ir_translation '
                    'SET src = %s, src_md5 = %s '
                    'WHERE id = %s',
                        (src, src_md5, trans_id))

        # Add field in ir_model_field and update translation
        cursor.execute('SELECT f.id AS id, f.name AS name, ' \
                    'f.field_description AS field_description, ' \
                    'f.ttype AS ttype, f.relation AS relation, ' \
                    'f.module as module, f.help AS help '\
                'FROM ir_model_field AS f, ir_model AS m ' \
                'WHERE f.model = m.id ' \
                    'AND m.model = %s ',
                        (cls.__name__,))
        model_fields = {}
        for field in cursor.dictfetchall():
            model_fields[field['name']] = field

        # Prefetch field translations
        if cls._fields:
            cursor.execute('SELECT id, name, src, type FROM ir_translation ' \
                    'WHERE lang = %s ' \
                        'AND type IN (%s, %s, %s) ' \
                        'AND name IN ' \
                            '(' + ','.join(('%s',) * len(cls._fields)) + ')',
                            ('en_US', 'field', 'help', 'selection') + \
                                    tuple([cls.__name__ + ',' + x \
                                        for x in cls._fields]))
        trans_fields = {}
        trans_help = {}
        trans_selection = {}
        for trans in cursor.dictfetchall():
            if trans['type'] == 'field':
                trans_fields[trans['name']] = trans
            elif trans['type'] == 'help':
                trans_help[trans['name']] = trans
            elif trans['type'] == 'selection':
                trans_selection.setdefault(trans['name'], {})
                trans_selection[trans['name']][trans['src']] = trans

        for field_name in cls._fields:
            field = cls._fields[field_name]
            relation = ''
            if hasattr(field, 'model_name'):
                relation = field.model_name
            elif hasattr(field, 'relation_name'):
                relation = field.relation_name
            if field_name not in model_fields:
                cursor.execute("INSERT INTO ir_model_field " \
                        "(model, name, field_description, ttype, " \
                            "relation, help, module) " \
                        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (model_id, field_name, field.string, field._type,
                            relation, field.help, module_name))
            elif (model_fields[field_name]['field_description'] != field.string
                    or model_fields[field_name]['ttype'] != field._type
                    or model_fields[field_name]['relation'] != relation
                    or model_fields[field_name]['help'] != field.help):
                cursor.execute('UPDATE ir_model_field ' \
                        'SET field_description = %s, ' \
                            'ttype = %s, ' \
                            'relation = %s, ' \
                            'help = %s ' \
                        'WHERE id = %s ',
                        (field.string, field._type, relation,
                            field.help, model_fields[field_name]['id']))
            trans_name = cls.__name__ + ',' + field_name
            string_md5 = Translation.get_src_md5(field.string)
            if trans_name not in trans_fields:
                cursor.execute('INSERT INTO ir_translation '
                    '(name, lang, type, src, src_md5, value, module, fuzzy) '
                    'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                    (trans_name, 'en_US', 'field', field.string,
                        string_md5, '', module_name, False))
            elif trans_fields[trans_name]['src'] != field.string:
                cursor.execute('UPDATE ir_translation '
                    'SET src = %s, src_md5 = %s '
                    'WHERE id = %s ',
                    (field.string, string_md5, trans_fields[trans_name]['id']))
            help_md5 = Translation.get_src_md5(field.help)
            if trans_name not in trans_help:
                if field.help:
                    cursor.execute('INSERT INTO ir_translation '
                        '(name, lang, type, src, src_md5, value, module, '
                            'fuzzy) '
                        'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                        (trans_name, 'en_US', 'help', field.help, help_md5, '',
                            module_name, False))
            elif trans_help[trans_name]['src'] != field.help:
                cursor.execute('UPDATE ir_translation '
                    'SET src = %s, src_md5 = %s '
                    'WHERE id = %s ',
                    (field.help, help_md5, trans_help[trans_name]['id']))
            if hasattr(field, 'selection') \
                    and isinstance(field.selection, (tuple, list)) \
                    and ((hasattr(field, 'translate_selection') \
                        and field.translate_selection)
                        or not hasattr(field, 'translate_selection')):
                for (_, val) in field.selection:
                    if trans_name not in trans_selection \
                            or val not in trans_selection[trans_name]:
                        val_md5 = Translation.get_src_md5(val)
                        cursor.execute('INSERT INTO ir_translation '
                            '(name, lang, type, src, src_md5, value, module, '
                                'fuzzy) '
                            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                            (trans_name, 'en_US', 'selection', val, val_md5,
                                '', module_name, False))
        # Clean ir_model_field from field that are no more existing.
        for field_name in model_fields:
            if model_fields[field_name]['module'] == module_name \
                    and field_name not in cls._fields:
                #XXX This delete field even when it is defined later
                # in the module
                cursor.execute('DELETE FROM ir_model_field '\
                                   'WHERE id = %s',
                               (model_fields[field_name]['id'],))

        # Add error messages in ir_translation
        cursor.execute('SELECT id, src FROM ir_translation ' \
                'WHERE lang = %s ' \
                    'AND type = %s ' \
                    'AND name = %s',
                ('en_US', 'error', cls.__name__))
        trans_error = {}
        for trans in cursor.dictfetchall():
            trans_error[trans['src']] = trans

        errors = cls._get_error_messages()
        for error in set(errors):
            if error not in trans_error:
                error_md5 = Translation.get_src_md5(error)
                cursor.execute('INSERT INTO ir_translation '
                    '(name, lang, type, src, src_md5, value, module, fuzzy) '
                    'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                    (cls.__name__, 'en_US', 'error', error, error_md5, '',
                        module_name, False))

    @classmethod
    def _get_error_messages(cls):
        return cls._error_messages.values()

    @classmethod
    def default_get(cls, fields_names, with_rec_name=True):
        '''
        Return a dict with the default values for each field in fields_names.
        If with_rec_name is True, rec_name will be added.
        '''
        pool = Pool()
        Property = pool.get('ir.property')
        value = {}

        # get the default values defined in the object
        for field_name in fields_names:
            if field_name in cls._defaults:
                value[field_name] = cls._defaults[field_name]()
            if field_name in cls._fields:
                field = cls._fields[field_name]
            else:
                field = cls._inherit_fields[field_name][2]
            if (field._type == 'boolean'
                    and not field_name in value):
                value[field_name] = False
            if isinstance(field, fields.Property):
                value[field_name] = Property.get(field_name, cls.__name__)
            if (with_rec_name
                    and field._type in ('many2one',)
                    and value.get(field_name)):
                Target = pool.get(field.model_name)
                if 'rec_name' in Target._fields:
                    value[field_name + '.rec_name'] = Target(
                        value[field_name]).rec_name

        value = cls._default_on_change(value)
        if not with_rec_name:
            for field in value.keys():
                if field.endswith('.rec_name'):
                    del value[field]
        return value

    @classmethod
    def _default_on_change(cls, value):
        """
        Call on_change function for the default value
        and return new default value
        """
        pool = Pool()
        res = value.copy()
        val = {}
        for i in cls._inherits.keys():
            val.update(pool.get(i)._default_on_change(value))
        for field in value.keys():
            if field in cls._fields:
                if cls._fields[field].on_change:
                    inst = cls()
                    for fname in cls._fields[field].on_change:
                        setattr(inst, fname, value.get(fname))
                    val.update(getattr(inst, 'on_change_' + field)())
                if cls._fields[field]._type in ('one2many',):
                    Target = pool.get(cls._fields[field].model_name)
                    for val2 in res[field]:
                        val2.update(Target._default_on_change(val2))
        res.update(val)
        return res

    @classmethod
    def fields_get(cls, fields_names=None):
        """
        Return the definition of each field on the model.
        """
        res = {}
        pool = Pool()
        Translation = pool.get('ir.translation')
        FieldAccess = pool.get('ir.model.field.access')

        for parent in cls._inherits:
            res.update(pool.get(parent).fields_get(fields_names))

        #Add translation to cache
        language = Transaction().language
        trans_args = []
        for field in (x for x in cls._fields.keys()
                if ((not fields_names) or x in fields_names)):
            trans_args.append((cls.__name__ + ',' + field, 'field', language,
                None))
            trans_args.append((cls.__name__ + ',' + field, 'help', language,
                None))
            if hasattr(cls._fields[field], 'selection'):
                if isinstance(cls._fields[field].selection, (tuple, list)) \
                        and ((hasattr(cls._fields[field],
                            'translate_selection') \
                            and cls._fields[field].translate_selection) \
                            or not hasattr(cls._fields[field],
                                'translate_selection')):
                    sel = cls._fields[field].selection
                    for (key, val) in sel:
                        trans_args.append((cls.__name__ + ',' + field,
                            'selection', language, val))
        Translation.get_sources(trans_args)

        encoder = PYSONEncoder()

        fwrite_accesses = FieldAccess.check(cls.__name__, fields_names or
            cls._fields.keys(), 'write', access=True)
        fcreate_accesses = FieldAccess.check(cls.__name__, fields_names or
            cls._fields.keys(), 'create', access=True)
        fdelete_accesses = FieldAccess.check(cls.__name__, fields_names or
            cls._fields.keys(), 'delete', access=True)
        for field in (x for x in cls._fields.keys()
                if ((not fields_names) or x in fields_names)):
            res[field] = {
                'type': cls._fields[field]._type,
                'name': field,
                }
            for arg in (
                    'string',
                    'readonly',
                    'states',
                    'size',
                    'required',
                    'translate',
                    'help',
                    'select',
                    'on_change',
                    'add_remove',
                    'on_change_with',
                    'autocomplete',
                    'sort',
                    'datetime_field',
                    'loading',
                    'filename',
                    ):
                if getattr(cls._fields[field], arg, None) is not None:
                    res[field][arg] = copy.copy(getattr(cls._fields[field],
                        arg))
            if not fwrite_accesses.get(field, True):
                res[field]['readonly'] = True
                if res[field].get('states') and \
                        'readonly' in res[field]['states']:
                    del res[field]['states']['readonly']
            for arg in ('digits', 'invisible'):
                if hasattr(cls._fields[field], arg) \
                        and getattr(cls._fields[field], arg):
                    res[field][arg] = copy.copy(getattr(cls._fields[field],
                        arg))
            if isinstance(cls._fields[field],
                    (fields.Function, fields.One2Many)) \
                    and not cls._fields[field].order_field:
                res[field]['sortable'] = False
            if ((isinstance(cls._fields[field], fields.Function)
                    and not cls._fields[field].searcher)
                    or cls._fields[field]._type in ('binary', 'sha')):
                res[field]['searchable'] = False
            else:
                res[field]['searchable'] = True

            if Transaction().context.get('language'):
                # translate the field label
                res_trans = Translation.get_source(
                    cls.__name__ + ',' + field, 'field',
                    Transaction().context['language'])
                if res_trans:
                    res[field]['string'] = res_trans
                help_trans = Translation.get_source(
                    cls.__name__ + ',' + field, 'help',
                    Transaction().context['language'])
                if help_trans:
                    res[field]['help'] = help_trans

            if hasattr(cls._fields[field], 'selection'):
                if isinstance(cls._fields[field].selection, (tuple, list)):
                    sel = copy.copy(cls._fields[field].selection)
                    if Transaction().context.get('language') and \
                            ((hasattr(cls._fields[field],
                                'translate_selection') \
                                and cls._fields[field].translate_selection) \
                                or not hasattr(cls._fields[field],
                                    'translate_selection')):
                        # translate each selection option
                        sel2 = []
                        for (key, val) in sel:
                            val2 = Translation.get_source(
                                cls.__name__ + ',' + field, 'selection',
                                language, val)
                            sel2.append((key, val2 or val))
                        sel = sel2
                    res[field]['selection'] = sel
                else:
                    # call the 'dynamic selection' function
                    res[field]['selection'] = copy.copy(
                            cls._fields[field].selection)
            if res[field]['type'] in (
                    'one2many',
                    'many2many',
                    'many2one',
                    'one2one',
                    ):
                if hasattr(cls._fields[field], 'model_name'):
                    relation = copy.copy(cls._fields[field].model_name)
                else:
                    relation = copy.copy(
                        cls._fields[field].get_target().__name__)
                res[field]['relation'] = relation
                res[field]['domain'] = copy.copy(cls._fields[field].domain)
                res[field]['context'] = copy.copy(cls._fields[field].context)
                res[field]['create'] = fcreate_accesses.get(field, True)
                res[field]['delete'] = fdelete_accesses.get(field, True)
            if res[field]['type'] == 'one2many' \
                    and getattr(cls._fields[field], 'field', None):
                res[field]['relation_field'] = copy.copy(
                        cls._fields[field].field)
            if res[field]['type'] in ('datetime', 'time'):
                res[field]['format'] = copy.copy(cls._fields[field].format)

            # convert attributes into pyson
            for attr in ('states', 'domain', 'context', 'digits', 'size',
                    'add_remove', 'format'):
                if attr in res[field]:
                    res[field][attr] = encoder.encode(res[field][attr])

        if fields_names:
            # filter out fields which aren't in the fields_names list
            for i in res.keys():
                if i not in fields_names:
                    del res[i]
        return res

    def on_change_with(self, fieldnames):
        changes = {}
        for fieldname in fieldnames:
            method_name = 'on_change_with_%s' % fieldname
            changes[fieldname] = getattr(self, method_name)()
        return changes

    def pre_validate(self):
        pass

    def __init__(self, id=None, **kwargs):
        super(Model, self).__init__()
        if id is not None:
            id = int(id)
        self.__dict__['id'] = id
        self._values = None
        parent_values = {}
        for name, value in kwargs.iteritems():
            if not name.startswith('_parent_'):
                setattr(self, name, value)
            else:
                parent_values[name] = value
        for name, value in parent_values.iteritems():
            parent_name, field = name.split('.', 1)
            parent_name = parent_name[8:]  # Strip '_parent_'
            parent = getattr(self, parent_name, None)
            if parent is not None:
                setattr(parent, field, value)
            else:
                setattr(self, parent_name, {field: value})

    def __getattr__(self, name):
        if name == 'id':
            return self.__dict__['id']
        if (name not in self._fields
                and name not in self._inherit_fields):
            # Search for method on inherits parents
            pool = Pool()
            for model_name, _ in self._inherits.iteritems():
                iModel = pool.get(model_name)
                if isinstance(getattr(iModel, name, None),
                        collections.Callable):
                    for cls in iModel.__mro__:
                        if name in cls.__dict__:
                            # Return a method bounded to current class
                            return cls.__dict__[name].__get__(self,
                                self.__class__)
        elif self._values and name in self._values:
            return self._values.get(name)
        raise AttributeError("'%s' Model has no attribute '%s': %s"
            % (self.__name__, name, self._values))

    def __setattr__(self, name, value):
        if name == 'id':
            self.__dict__['id'] = value
            return
        if (name not in self._fields
                and name in self._inherit_fields):
            field = self._inherit_fields[name][2]
            field.__set__(self, value)
            return
        super(Model, self).__setattr__(name, value)

    def __getitem__(self, name):
        warnings.warn('Use __getattr__ instead of __getitem__',
            DeprecationWarning, stacklevel=2)
        return getattr(self, name)

    def __contains__(self, name):
        return (name in self._fields
            or name in self._inherit_fields)

    def __int__(self):
        return int(self.id)

    def __str__(self):
        return '%s,%s' % (self.__name__, self.id)

    def __unicode__(self):
        return u'%s,%s' % (self.__name__, self.id)

    def __repr__(self):
        if self.id < 0:
            return "Pool().get('%s')(**%s)" % (self.__name__,
                repr(self._default_values))
        else:
            return "Pool().get('%s')(%s)" % (self.__name__, self.id)

    def __eq__(self, other):
        if not isinstance(other, Model):
            return NotImplemented
        if self.id is None or other.id is None:
            return False
        return (self.__name__, self.id) == (other.__name__, other.id)

    def __ne__(self, other):
        if not isinstance(other, Model):
            return NotImplemented
        if self.id is None or other.id is None:
            return True
        return (self.__name__, self.id) != (other.__name__, other.id)

    def __hash__(self):
        return hash((self.__name__, self.id))

    def __nonzero__(self):
        return True

    @property
    def _default_values(self):
        if self.id >= 0:
            return self.id
        values = {}
        if self._values:
            for fname, value in self._values.iteritems():
                if fname in self._fields:
                    field = self._fields[fname]
                else:
                    field = self._inherit_fields[fname][2]
                if isinstance(field, fields.Reference):
                    if value is not None:
                        value = str(value)
                elif isinstance(value, Model):
                    value = value._default_values
                elif isinstance(value, list):
                    value = [r._default_values for r in value]
                values[fname] = value
        return values
