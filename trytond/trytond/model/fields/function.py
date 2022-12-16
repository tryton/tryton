#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import inspect
import copy
from trytond.model.fields.field import Field


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
        assert loading in ('lazy', 'eager'), \
            'loading must be "lazy" or "eager"'
        self.loading = loading

    __init__.__doc__ += Field.__init__.__doc__

    def __copy__(self):
        return Function(copy.copy(self._field), self.getter,
                setter=self.setter, searcher=self.searcher)

    def __deepcopy__(self, memo):
        return Function(copy.deepcopy(self._field, memo),
            copy.deepcopy(self.getter, memo),
            setter=copy.deepcopy(self.setter, memo),
            searcher=copy.deepcopy(self.searcher, memo),
            loading=copy.deepcopy(self.loading, memo))

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

    def search(self, model, name, clause):
        '''
        Call the searcher.
        Return a list of clauses.
        '''
        if not self.searcher:
            model.raise_user_error('search_function_missing', name)
        return getattr(model, self.searcher)(name, tuple(clause))

    def get(self, ids, Model, name, values=None):
        '''
        Call the getter.
        If the function has ``names`` in the function definition then
        it will call it with a list of name.
        '''
        method = getattr(Model, self.getter)

        def call(name):
            records = Model.browse(ids)
            if not hasattr(method, 'im_self') or method.im_self:
                return method(records, name)
            else:
                return dict((r.id, method(r, name)) for r in records)
        if isinstance(name, list):
            names = name
            # Test is the function works with a list of names
            if 'names' in inspect.getargspec(method)[0]:
                return call(names)
            return dict((name, call(name)) for name in names)
        else:
            # Test is the function works with a list of names
            if 'names' in inspect.getargspec(method)[0]:
                name = [name]
            return call(name)

    def set(self, ids, Model, name, value):
        '''
        Call the setter.
        '''
        if self.setter:
            getattr(Model, self.setter)(Model.browse(ids), name, value)

    def __set__(self, inst, value):
        self._field.__set__(inst, value)
