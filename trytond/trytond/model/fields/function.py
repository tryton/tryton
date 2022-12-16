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

    def __init__(self, field, getter, setter=None, searcher=None):
        '''
        :param field: The field of the function.
        :param getter: The name of the function for getting values.
        :param setter: The name of the function to set value.
        :param searcher: The name of the function to search.
        '''
        assert isinstance(field, Field)
        self._field = field
        self._type = field._type
        self.getter = getter
        self.setter = setter
        if not self.setter:
            self._field.readonly = True
        self.searcher = searcher

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

    def search(self, cursor, user, model, name, clause, context=None):
        '''
        Call the searcher.

        :param cursor: The database cursor.
        :param user: The user id.
        :param model: The model.
        :param name: The name of the field.
        :param clause: The search domain clause. See ModelStorage.search
        :param context: The context.
        :return: a list of domain clause.
        '''
        if not self.searcher:
            model.raise_user_error(cursor, 'search_function_missing',
                    name, context=context)
        return getattr(model, self.searcher)(cursor, user, name, tuple(clause),
                context=context)

    def get(self, cursor, user, ids, model, name, values=None, context=None):
        '''
        Call the getter.
        If the function has ``names`` in the function definition then
        it will call it with a list of name.

        :param cursor: The database cursor.
        :param user: The user id.
        :param ids: A list of ids.
        :param model: The model.
        :param name: The name of the field or a list of name field.
        :param values:
        :param context: The contest.
        :return: a dictionary with ids as key and values as value or
            a dictionary with name as key and a dictionary as value if
            name is a list of field name.
        '''
        if isinstance(name, list):
            names = name
            # Test is the function works with a list of names
            if 'names' in inspect.getargspec(getattr(model, self.getter))[0]:
                return getattr(model, self.getter)(cursor, user, ids, names,
                        context=context)
            res = {}
            for name in names:
                res[name] = getattr(model, self.getter)(cursor, user, ids,
                        name, context=context)
            return res
        else:
            # Test is the function works with a list of names
            if 'names' in inspect.getargspec(getattr(model, self.getter))[0]:
                name = [name]
            return getattr(model, self.getter)(cursor, user, ids, name,
                    context=context)


    def set(self, cursor, user, ids, model, name, value, context=None):
        '''
        Call the setter.

        :param cursor: The database cursor.
        :param user: The user id.
        :param ids: A list of ids.
        :param model: The model.
        :param name: The name of the field.
        :param value: The value to set.
        :param context: The context.
        '''
        if self.setter:
            getattr(model, self.setter)(cursor, user, ids, name, value,
                    context=context)
