#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import inspect
import copy
from trytond.model.fields.field import Field
from trytond.model.fields.float import digits_validate
from trytond.model.fields.one2many import add_remove_validate
from trytond.pyson import PYSON


class Function(Field):
    '''
    Define function field (any).
    '''

    def __init__(self, field, getter, setter=None, searcher=None,
            loading='lazy'):
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
        self.setter = setter
        if not self.setter:
            self._field.readonly = True
        self.searcher = searcher
        assert loading in ('lazy', 'eager'), 'loading must be "lazy" or "eager"'
        self.loading = loading

    __init__.__doc__ += Field.__init__.__doc__

    def __copy__(self):
        return Function(copy.copy(self._field), self.getter,
                setter=self.setter, searcher=self.searcher)

    def __getattr__(self, name):
        return getattr(self._field, name)

    def __getitem__(self, name):
        return self._field[name]

    def __setattr__(self, name, value):
        if name in ('_field', '_type', 'getter', 'setter', 'searcher'):
            return object.__setattr__(self, name, value)
        return setattr(self._field, name, value)

    def search(self, model, name, clause):
        '''
        Call the searcher.

        :param model: The model.
        :param name: The name of the field.
        :param clause: The search domain clause. See ModelStorage.search
        :return: a list of domain clause.
        '''
        if not self.searcher:
            model.raise_user_error('search_function_missing', name)
        return getattr(model, self.searcher)(name, tuple(clause))

    def get(self, ids, model, name, values=None):
        '''
        Call the getter.
        If the function has ``names`` in the function definition then
        it will call it with a list of name.

        :param ids: A list of ids.
        :param model: The model.
        :param name: The name of the field or a list of name field.
        :param values:
        :return: a dictionary with ids as key and values as value or
            a dictionary with name as key and a dictionary as value if
            name is a list of field name.
        '''
        if isinstance(name, list):
            names = name
            # Test is the function works with a list of names
            if 'names' in inspect.getargspec(getattr(model, self.getter))[0]:
                return getattr(model, self.getter)(ids, names)
            res = {}
            for name in names:
                res[name] = getattr(model, self.getter)(ids, name)
            return res
        else:
            # Test is the function works with a list of names
            if 'names' in inspect.getargspec(getattr(model, self.getter))[0]:
                name = [name]
            return getattr(model, self.getter)(ids, name)


    def set(self, ids, model, name, value):
        '''
        Call the setter.

        :param ids: A list of ids.
        :param model: The model.
        :param name: The name of the field.
        :param value: The value to set.
        '''
        if self.setter:
            getattr(model, self.setter)(ids, name, value)
