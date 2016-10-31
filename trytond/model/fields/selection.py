# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import warnings

from sql.conditionals import Case

from ... import backend
from ...transaction import Transaction
from ...tools import is_instance_method
from .field import Field, SQLType


class Selection(Field):
    '''
    Define a selection field (``str``).
    '''
    _type = 'selection'

    def __init__(self, selection, string='', sort=True,
            selection_change_with=None, translate=True, help='',
            required=False, readonly=False, domain=None, states=None,
            select=False, on_change=None, on_change_with=None, depends=None,
            context=None, loading='eager'):
        '''
        :param selection: A list or a function name that returns a list.
            The list must be a list of tuples. First member is the value
            to store and the second is the value to display.
        :param sort: A boolean to sort or not the selections.
        '''
        super(Selection, self).__init__(string=string, help=help,
            required=required, readonly=readonly, domain=domain, states=states,
            select=select, on_change=on_change, on_change_with=on_change_with,
            depends=depends, context=context, loading=loading)
        if hasattr(selection, 'copy'):
            self.selection = selection.copy()
        else:
            self.selection = selection
        self.selection_change_with = set()
        if selection_change_with:
            warnings.warn('selection_change_with argument is deprecated, '
                'use the depends decorator',
                DeprecationWarning, stacklevel=2)
            self.selection_change_with |= set(selection_change_with)
        self.sort = sort
        self.translate_selection = translate
    __init__.__doc__ += Field.__init__.__doc__

    def sql_type(self):
        db_type = backend.name()
        if db_type == 'mysql':
            return SQLType('CHAR', 'VARCHAR(255)')
        return SQLType('VARCHAR', 'VARCHAR')

    def convert_order(self, name, tables, Model):
        if getattr(Model, 'order_%s' % name, None):
            return super(Selection, self).convert_order(name, tables, Model)

        assert name == self.name
        table, _ = tables[None]
        selections = Model.fields_get([name])[name]['selection']
        if not isinstance(selections, (tuple, list)):
            selections = getattr(Model, selections)()
        column = self.sql_column(table)
        whens = []
        for key, value in selections:
            whens.append((column == key, value))
        return [Case(*whens, else_=column)]

    def translated(self, name=None):
        "Return a descriptor for the translated value of the field"
        if name is None:
            name = self.name
        if name is None:
            raise ValueError('Missing name argument')
        return TranslatedSelection(name)


class TranslatedSelection(object):
    'A descriptor for translated value of Selection field'

    def __init__(self, name):
        self.name = name

    def __get__(self, inst, cls):
        if inst is None:
            return self
        with Transaction().set_context(getattr(inst, '_context', {})):
            selection = cls.fields_get([self.name])[self.name]['selection']
            if not isinstance(selection, (tuple, list)):
                sel_func = getattr(cls, selection)
                if not is_instance_method(cls, selection):
                    selection = sel_func()
                else:
                    selection = sel_func(inst)
            selection = dict(selection)
        value = getattr(inst, self.name)
        # None and '' are equivalent
        if value is None or value == '':
            if value not in selection:
                value = {None: '', '': None}[value]
        return selection[value]
