# This file is part of Tryton.  The COPYRIGHT file at the toplevel of this
# repository contains the full copyright notices and license terms.
import json
from functools import partial

from sql import operators, Literal

from trytond.rpc import RPC
from trytond.transaction import Transaction
from .field import Field
from .selection import SelectionMixin

# Use canonical form
dumps = partial(json.dumps, separators=(',', ':'), sort_keys=True)


class MultiSelection(SelectionMixin, Field):
    "Define a multi-selection field."
    _type = 'multiselection'
    _sql_type = 'VARCHAR'
    _py_type = list

    def __init__(self, selection, string='', sort=True, translate=True,
            help='', help_selection=None, required=False, readonly=False,
            domain=None, states=None, select=False, on_change=None,
            on_change_with=None, depends=None, context=None, loading='eager'):
        """
        :param selection: A list or a function name that returns a list.
            The list must be a list of tuples. First member is the value
            to store and the second is the value to display.
        :param sort: A boolean to sort or not the selections.
        """
        super().__init__(string=string, help=help,
            required=required, readonly=readonly, domain=domain, states=states,
            select=select, on_change=on_change, on_change_with=on_change_with,
            depends=depends, context=context, loading=loading)
        if hasattr(selection, 'copy'):
            self.selection = selection.copy()
        else:
            self.selection = selection
        self.selection_change_with = set()
        self.sort = sort
        self.translate_selection = translate
        self.help_selection = help_selection
    __init__.__doc__ += Field.__init__.__doc__

    def set_rpc(self, model):
        super().set_rpc(model)
        if not isinstance(self.selection, (list, tuple)):
            assert hasattr(model, self.selection), \
                'Missing %s on model %s' % (self.selection, model.__name__)
            instantiate = 0 if self.selection_change_with else None
            model.__rpc__.setdefault(
                self.selection, RPC(instantiate=instantiate))

    def get(self, ids, model, name, values=None):
        lists = {id: None for id in ids}
        for value in values or []:
            data = value[name]
            if data:
                # If stored as JSON conversion is done on backend
                if isinstance(data, str):
                    data = json.loads(data)
                lists[value['id']] = tuple(data)
        return lists

    def sql_format(self, value):
        value = super().sql_format(value)
        if isinstance(value, list):
            value = dumps(sorted(set(value)))
        return value

    def __set__(self, inst, value):
        if value:
            value = tuple(value)
        super().__set__(inst, value)

    def _domain_column(self, operator, column):
        database = Transaction().database
        return database.json_get(super()._domain_column(operator, column))

    def _domain_value(self, operator, value):
        database = Transaction().database
        domain_value = super()._domain_value(operator, value)
        if value is not None:
            domain_value = database.json_get(domain_value)
        return domain_value

    def convert_domain(self, domain, tables, Model):
        name, operator, value = domain[:3]
        if operator not in {'in', 'not in'}:
            return super().convert_domain(domain, tables, Model)
        database = Transaction().database
        table, _ = tables[None]
        raw_column = self.sql_column(table)
        if isinstance(value, str):
            try:
                expression = database.json_key_exists(raw_column, value)
            except NotImplementedError:
                expression = operators.Like(
                    raw_column, '%' + dumps(value) + '%')
        else:
            try:
                expression = database.json_any_keys_exist(
                    raw_column, list(value))
            except NotImplementedError:
                expression = Literal(False)
                for item in value:
                    expression |= operators.Like(
                        raw_column, '%' + dumps(item) + '%')
        if operator == 'not in':
            expression = operators.Not(expression)
        return expression
