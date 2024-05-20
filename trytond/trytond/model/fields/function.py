# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import copy
import inspect
from functools import wraps

from trytond.i18n import gettext
from trytond.tools import is_instance_method
from trytond.transaction import Transaction, without_check_access

from .field import Field, domain_method


def getter_context(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.getter_with_context:
            transaction = Transaction()
            context = {
                k: v for k, v in transaction.context.items()
                if k in transaction.cache_keys}
            with transaction.reset_context(), \
                    transaction.set_context(context):
                return func(self, *args, **kwargs)
        else:
            return func(self, *args, **kwargs)
    return wrapper


class Function(Field):
    '''
    Define function field (any).
    '''

    def __init__(self, field, getter, setter=None, searcher=None,
            getter_with_context=True, loading='lazy'):
        '''
        :param field: The field of the function.
        :param getter: The name of the function for getting values.
        :param setter: The name of the function to set value.
        :param searcher: The name of the function to search.
        :param loading: Define how the field must be loaded:
            ``lazy`` or ``eager``.
        '''
        assert isinstance(field, Field)
        self._field = field
        self._type = field._type
        self.getter = getter
        self.getter_with_context = getter_with_context
        self.setter = setter
        if not self.setter:
            self._field.readonly = True
        self.searcher = searcher
        assert loading in ('lazy', 'eager'), \
            'loading must be "lazy" or "eager"'
        self.loading = loading

    __init__.__doc__ += Field.__init__.__doc__

    def __copy__(self):
        return Function(copy.copy(self._field), self.getter,
            setter=self.setter, searcher=self.searcher,
            getter_with_context=self.getter_with_context,
            loading=self.loading)

    def __deepcopy__(self, memo):
        return Function(copy.deepcopy(self._field, memo), self.getter,
            setter=self.setter, searcher=self.searcher,
            getter_with_context=self.getter_with_context,
            loading=self.loading)

    def __getattr__(self, name):
        return getattr(self._field, name)

    def __getitem__(self, name):
        return self._field[name]

    def __setattr__(self, name, value):
        if name in ('_field', '_type', 'getter', 'setter', 'searcher', 'name'):
            object.__setattr__(self, name, value)
            if name != 'name':
                return
        setattr(self._field, name, value)

    def set_rpc(self, model):
        self._field.set_rpc(model)

    def sql_format(self, value):
        return self._field.sql_format(value)

    def sql_type(self):
        return None

    @domain_method
    def convert_domain(self, domain, tables, Model):
        if self.searcher:
            return getattr(Model, self.searcher)(self.name, domain)
        raise NotImplementedError(gettext(
                'ir.msg_search_function_missing',
                **Model.__names__(self.name)))

    @getter_context
    @without_check_access
    def get(self, ids, Model, name, values=None):
        '''
        Call the getter.
        If the function has ``names`` in the function definition then
        it will call it with a list of name.
        '''
        method = getattr(Model, self.getter)
        instance_method = is_instance_method(Model, self.getter)
        multiple = self.getter_multiple(method)

        records = Model.browse(ids)
        for record, value in zip(records, values):
            assert record.id == value['id']
            for fname, val in value.items():
                field = Model._fields.get(fname)
                if field and field._type not in {
                        'many2one', 'reference',
                        'one2many', 'many2many', 'one2one'}:
                    record._local_cache[record.id][fname] = val

        def call(name):
            if not instance_method:
                values = method(records, name)
                if isinstance(name, str):
                    return convert_dict(values, name)
                else:
                    return {n: convert_dict(values[n], n) for n in name}
            else:
                if isinstance(name, str):
                    return {
                        r.id: convert(method(r, name), name) for r in records}
                else:
                    results = {n: {} for n in name}
                    for r in records:
                        values = method(r, name)
                        for n in name:
                            results[n][r.id] = values[n]
                    return results

        def convert(value, name):
            from ..model import Model as BaseModel
            field = Model._fields[name]._field
            if field._type in {'many2one', 'one2one', 'reference'}:
                if isinstance(value, BaseModel):
                    if field._type == 'reference':
                        value = str(value)
                    else:
                        value = int(value)
            elif field._type in {'one2many', 'many2many'}:
                if value:
                    value = [int(r) for r in value]
            return value

        def convert_dict(values, name):
            # Keep the same class
            values = values.copy()
            values.update((k, convert(v, name)) for k, v in values.items())
            return values

        if isinstance(name, list):
            names = name
            if multiple:
                return call(names)
            return dict((name, call(name)) for name in names)
        else:
            if multiple:
                name = [name]
            return call(name)

    @without_check_access
    def set(self, Model, name, ids, value, *args):
        '''
        Call the setter.
        '''
        if self.setter:
            # TODO change setter API to use sequence of records, value
            setter = getattr(Model, self.setter)
            args = iter((ids, value) + args)
            for ids, value in zip(args, args):
                setter(Model.browse(ids), name, value)
        else:
            raise NotImplementedError(gettext(
                    'ir.msg_setter_function_missing',
                    **Model.__names__(self.name)))

    def __get__(self, inst, cls):
        try:
            return super().__get__(inst, cls)
        except AttributeError:
            if not self.getter.startswith('on_change_with'):
                raise
            value = getattr(inst, self.getter)(self.name)
            # Use temporary instance to not modify instance values
            temp_inst = cls()
            # Set the value to have proper type
            self.__set__(temp_inst, value)
            return super().__get__(temp_inst, cls)

    def __set__(self, inst, value):
        self._field.__set__(inst, value)

    def definition(self, model, language):
        definition = self._field.definition(model, language)
        definition['searchable'] = self.searchable(model)
        definition['sortable'] = self.sortable(model)
        return definition

    def searchable(self, model):
        return super().searchable(model) and (
            bool(self.searcher) or hasattr(model, f'domain_{self.name}'))

    def sortable(self, model):
        return super().sortable(model) and hasattr(model, f'order_{self.name}')

    def getter_multiple(self, method):
        "Returns True if getter function accepts multiple fields"
        signature = inspect.signature(method)
        return 'names' in signature.parameters


for name in [
        'string', 'help', 'domain', 'states', 'depends', 'display_depends',
        'edition_depends', 'validation_depends', 'context']:
    def getter(name):
        return lambda self: getattr(self._field, name)

    def setter(name):
        return lambda self, value: setattr(self._field, name, value)

    setattr(Function, name, property(getter(name), setter(name)))


class MultiValue(Function):

    def __init__(self, field, loading='lazy'):
        super(MultiValue, self).__init__(
            field, '_multivalue_getter', setter='_multivalue_setter',
            loading=loading)

    def __copy__(self):
        return MultiValue(copy.copy(self._field), loading=self.loading)

    def __deepcopy__(self, memo):
        return MultiValue(
            copy.deepcopy(self._field, memo), loading=self.loading)
