# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import warnings

from sql.conditionals import Case

from trytond.pool import Pool
from trytond.rpc import RPC
from trytond.tools import is_instance_method
from trytond.tools.string_ import LazyString
from trytond.transaction import Transaction
from .field import Field


class SelectionMixin(Field):
    translate_selection = True
    sort = True

    def translated(self, name=None):
        "Return a descriptor for the translated value of the field"
        if name is None:
            name = self.name
        if name is None:
            raise ValueError('Missing name argument')
        return TranslatedSelection(name)

    def definition(self, model, language):
        pool = Pool()
        Translation = pool.get('ir.translation')
        definition = super().definition(model, language)
        if not isinstance(self.selection, str) and self.translate_selection:
            name = '%s,%s' % (model.__name__, self.name)
            selection = []
            for key, source in self.selection:
                if not isinstance(source, LazyString):
                    source = Translation.get_source(
                        name, 'selection', language, source) or source
                selection.append((key, str(source)))
        elif hasattr(self.selection, 'copy'):
            selection = self.selection.copy()
        else:
            selection = self.selection
        definition['selection'] = selection
        definition['selection_change_with'] = list(self.selection_change_with)
        definition['sort'] = self.sort
        return definition

    def definition_translations(self, model, language):
        name = '%s,%s' % (model.__name__, self.name)
        selection = []
        if not isinstance(self.selection, str) and self.translate_selection:
            for key, source in self.selection:
                if not isinstance(source, LazyString):
                    selection.append(
                        (name, 'selection', language, source))
        return super().definition_translations(model, language) + selection


class Selection(SelectionMixin, Field):
    '''
    Define a selection field (``str``).
    '''
    _type = 'selection'
    _sql_type = 'VARCHAR'
    _py_type = str

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

    def set_rpc(self, model):
        super(Selection, self).set_rpc(model)
        if not isinstance(self.selection, (list, tuple)):
            assert hasattr(model, self.selection), \
                'Missing %s on model %s' % (self.selection, model.__name__)
            instantiate = 0 if self.selection_change_with else None
            model.__rpc__.setdefault(
                self.selection, RPC(instantiate=instantiate))

    def convert_order(self, name, tables, Model):
        if getattr(Model, 'order_%s' % name, None):
            return super(Selection, self).convert_order(name, tables, Model)

        assert name == self.name
        table, _ = tables[None]
        selections = Model.fields_get([name])[name]['selection']
        if not isinstance(selections, (tuple, list)):
            if not is_instance_method(Model, selections):
                selections = getattr(Model, selections)()
            else:
                selections = []
        column = self.sql_column(table)
        whens = []
        for key, value in selections:
            whens.append((column == key, value))
        if whens:
            return [Case(*whens, else_=column)]
        else:
            return [column]


class TranslatedSelection(object):
    'A descriptor for translated value of Selection field'

    def __init__(self, name):
        self.name = name

    def __get__(self, inst, cls):
        from ..model import Model
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
                switch_value = {None: '', '': None}[value]
                if switch_value in selection:
                    value = switch_value
        # Use Model __name__ for Reference field
        elif isinstance(value, Model):
            value = value.__name__
        if isinstance(value, (list, tuple)):
            values = []
            for item in value:
                values.append(selection.get(item, item))
            return values
        else:
            return selection.get(value, value)
